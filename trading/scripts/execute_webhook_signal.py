#!/usr/bin/env python3
"""
Execute a single signal from the TradingView webhook (one-off order).

Invoked by webhook_server after validate_and_record_last. Connects to IB,
checks kill switch and gates, places one order via OrderRouter, appends to
execution log.

Usage: python execute_webhook_signal.py '<json payload>'

All broker interaction is routed through OrderRouter — no direct
ib_insync order calls outside this orchestration layer.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from ib_insync import IB, Stock

from atr_stops import (
    calculate_position_size,
    compute_stop_tp,
    compute_trailing_amount,
    fetch_atr,
)
from broker_data_helpers import atr_from_ib
from enriched_record import build_enriched_record
from execution_policy import ExecutionPolicy, build_intent
from order_router import OrderRouter, SubmitResult
from regime_detector import detect_market_regime
from risk_config import get_outside_rth_stop, get_outside_rth_take_profit

PULLBACK_STOP_ATR_MULT = 1.0
PULLBACK_TP_ATR_MULT = 2.5

from paths import TRADING_DIR

_env_path = TRADING_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

EXECUTION_LOG = TRADING_DIR / "logs" / "executions.json"
STATE_STORE_PATH = TRADING_DIR / "logs" / "order_state_webhook.jsonl"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            Path(__file__).resolve().parent.parent / "logs" / "execute_webhook_signal.log"
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def _normalize_action(action: str) -> str:
    a = (action or "").strip().lower()
    if a in ("sell", "short"):
        return "SELL"
    if a in ("buy", "long"):
        return "BUY"
    return ""


async def run(payload: dict) -> bool:
    symbol = (payload.get("symbol") or payload.get("ticker") or "").strip().upper()
    action = _normalize_action(str(payload.get("action") or payload.get("side") or ""))
    if not symbol or not action:
        logger.error("Missing symbol or action in payload")
        return False

    try:
        from position_filter import load_current_short_symbols
        from risk_config import (
            get_absolute_max_shares,
            get_daily_loss_limit_pct,
            get_max_position_pct_of_equity,
            get_max_sector_concentration_pct,
            get_max_short_positions,
            get_risk_per_trade_pct,
        )
        from sector_gates import portfolio_sector_exposure
        from execution_gates import check_all_gates
    except ImportError as e:
        logger.error("Import error: %s", e)
        return False

    try:
        from agents.risk_monitor import is_kill_switch_active
        if is_kill_switch_active():
            logger.warning("Kill switch active; aborting webhook execution")
            _append_execution(symbol, action, "SKIPPED", reason="kill_switch_active")
            return False
    except ImportError:
        pass

    ib = IB()
    try:
        await ib.connectAsync(
            os.getenv("IB_HOST", "127.0.0.1"),
            int(os.getenv("IB_PORT", "4001")),
            clientId=109,
        )
        ib.reqMarketDataType(3)
    except Exception as e:
        logger.error("IB connection failed: %s", e)
        _append_execution(symbol, action, "ERROR", reason=str(e))
        return False

    router = OrderRouter(ib, state_store_path=STATE_STORE_PATH)

    try:
        await router.startup()

        current_shorts = load_current_short_symbols(TRADING_DIR, ib)
        sector_exposure, total_notional = portfolio_sector_exposure(ib)
        max_sector_pct = get_max_sector_concentration_pct(TRADING_DIR)
        max_shorts = get_max_short_positions(TRADING_DIR)
        risk_per_trade_pct = get_risk_per_trade_pct(TRADING_DIR)
        max_position_pct = get_max_position_pct_of_equity(
            TRADING_DIR, side="short" if action == "SELL" else "long",
        )
        absolute_max_shares = get_absolute_max_shares(TRADING_DIR)
        daily_loss_limit_pct = get_daily_loss_limit_pct(TRADING_DIR)

        from risk_config import get_net_liquidation_and_effective_equity
        net_liq, effective_equity = get_net_liquidation_and_effective_equity(ib, TRADING_DIR)

        daily_loss = 0.0
        try:
            loss_file = TRADING_DIR / "logs" / "daily_loss.json"
            if loss_file.exists():
                data = json.loads(loss_file.read_text())
                if data.get("date") == datetime.now().date().isoformat():
                    daily_loss = float(data.get("loss", 0) or 0)
        except Exception:
            pass

        price_estimate = float(payload.get("price") or 0)
        if price_estimate <= 0:
            try:
                ticker = ib.reqMktData(Stock(symbol, "SMART", "USD"))
                for _ in range(20):
                    await asyncio.sleep(0.25)
                    if ticker.marketPrice() and ticker.marketPrice() > 0:
                        price_estimate = float(ticker.marketPrice())
                        break
                ib.cancelMktData(ticker.contract)
            except Exception:
                pass
        if price_estimate <= 0:
            logger.error("Could not resolve price for %s", symbol)
            _append_execution(symbol, action, "ERROR", reason="no_price")
            return False

        atr = fetch_atr(symbol)
        if atr is None:
            atr = atr_from_ib(symbol, ib)

        qty = calculate_position_size(
            effective_equity, price_estimate, atr=atr,
            risk_pct=risk_per_trade_pct,
            max_position_pct=max_position_pct,
            absolute_max_shares=absolute_max_shares,
            cap_equity=net_liq,
        )
        notional = price_estimate * qty
        logger.info(
            "Webhook sizing: %s %d shares @ $%.2f ($%s notional, effective $%s)",
            symbol, qty, price_estimate, f"{notional:,.0f}", f"{effective_equity:,.0f}",
        )

        if action == "SELL":
            if symbol in current_shorts:
                logger.info("Already short %s; skipping", symbol)
                _append_execution(symbol, action, "SKIPPED", reason="already_short")
                return False
            if len(current_shorts) >= max_shorts:
                logger.warning("Max short positions reached")
                _append_execution(symbol, action, "SKIPPED", reason="max_short_positions")
                return False
            gates_ok, failed_gates = check_all_gates(
                signal_type="SHORT",
                symbol=symbol,
                notional=notional,
                daily_loss=daily_loss,
                account_equity=net_liq,
                daily_loss_limit_pct=daily_loss_limit_pct,
                sector_exposure=sector_exposure,
                total_notional=total_notional,
                max_sector_pct=max_sector_pct,
                minutes_before_close=60,
                max_notional_pct_of_equity=0.5,
                ib=ib,
                account_equity_effective=effective_equity,
            )
            if not gates_ok:
                reason = "gates: " + ", ".join(failed_gates)
                logger.info("Gates failed: %s", reason)
                _append_execution(symbol, action, "SKIPPED", reason=reason)
                return False

        # Position flip guard — block orders that would reverse an existing position
        try:
            from pre_trade_guard import PreTradeViolation, assert_no_flip
            assert_no_flip(ib, symbol, "LONG" if action == "BUY" else "SHORT")
        except PreTradeViolation as e:
            logger.error("Trade blocked by flip guard: %s", e)
            _append_execution(symbol, action, "SKIPPED", reason=str(e))
            return False

        entry_intent = build_intent(
            symbol=symbol,
            side=action,
            quantity=qty,
            policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script="execute_webhook_signal.py",
            limit_price=price_estimate,
            metadata={
                "signal_price": price_estimate,
                "entry_type": payload.get("entry_type", "standard"),
                "timeframe": payload.get("timeframe", "D"),
            },
        )

        result = await router.submit(
            entry_intent,
            bid=price_estimate if action == "SELL" else None,
            ask=price_estimate if action == "BUY" else None,
        )

        if not result.success or (not result.is_filled and not result.is_partial):
            logger.warning(
                "Webhook order not filled for %s: status=%s error=%s",
                symbol,
                result.status.value if result.status else "None",
                result.error or "",
            )
            _append_execution(
                symbol, action, "CANCELLED",
                reason=f"not filled: {result.status.value if result.status else 'unknown'}",
            )
            return False

        entry_price = result.avg_fill_price
        filled_qty = result.filled_qty
        fill_commission = result.total_commission
        fill_slippage = abs(entry_price - price_estimate) if entry_price > 0 else 0.0

        entry_type = (payload.get("entry_type") or "").strip().lower()
        is_pullback = entry_type == "pullback"
        exit_action = "SELL" if action == "BUY" else "BUY"

        if is_pullback and action == "BUY":
            stop_price, profit_price = compute_stop_tp(
                entry_price, action, atr=atr,
                stop_mult=PULLBACK_STOP_ATR_MULT,
                tp_mult=PULLBACK_TP_ATR_MULT,
            )
            trail_amt = compute_trailing_amount(
                atr=atr, entry_price=entry_price, trailing_mult=1.5,
            )

            trailing_intent = build_intent(
                symbol=symbol,
                side="SELL",
                quantity=filled_qty,
                policy=ExecutionPolicy.TRAILING_STOP,
                source_script="execute_webhook_signal.py",
                trail_amount=trail_amt,
                outside_rth=get_outside_rth_stop(TRADING_DIR),
            )
            tp_intent = build_intent(
                symbol=symbol,
                side="SELL",
                quantity=filled_qty,
                policy=ExecutionPolicy.PASSIVE_ENTRY,
                source_script="execute_webhook_signal.py",
                limit_price=profit_price,
                outside_rth=get_outside_rth_take_profit(TRADING_DIR),
            )

            await router.submit_protective_orders(
                parent_result=result,
                follow_ups=[trailing_intent, tp_intent],
            )
            logger.info(
                "Pullback entry: %s stop=%.2f trail=%.2f tp=%.2f (tighter: 1.0 ATR stop)",
                symbol, stop_price, trail_amt, profit_price,
            )
        else:
            stop_price, profit_price = compute_stop_tp(entry_price, action, atr=atr)

            stop_intent = build_intent(
                symbol=symbol,
                side=exit_action,
                quantity=filled_qty,
                policy=ExecutionPolicy.STOP_PROTECT,
                source_script="execute_webhook_signal.py",
                stop_price=stop_price,
                limit_price=stop_price,
                outside_rth=get_outside_rth_stop(TRADING_DIR),
            )
            tp_intent = build_intent(
                symbol=symbol,
                side=exit_action,
                quantity=filled_qty,
                policy=ExecutionPolicy.PASSIVE_ENTRY,
                source_script="execute_webhook_signal.py",
                limit_price=profit_price,
                outside_rth=get_outside_rth_take_profit(TRADING_DIR),
            )

            protective_results = await router.submit_protective_orders(
                parent_result=result,
                follow_ups=[stop_intent, tp_intent],
            )
            for pr in protective_results:
                if not pr.success:
                    logger.error("Protective order failed for %s: %s", symbol, pr.error)

        regime = detect_market_regime()
        side = "SHORT" if action == "SELL" else "LONG"
        strategy = "mtf_pullback" if is_pullback else "momentum"
        support_level = payload.get("support", "")

        rec = build_enriched_record(
            symbol=symbol, side=side, action=action,
            source_script="execute_webhook_signal.py",
            status="Filled" if result.is_filled else "PartiallyFilled",
            order_id=result.broker_order_id or 0,
            quantity=filled_qty,
            entry_price=entry_price, stop_price=stop_price, profit_price=profit_price,
            regime_at_entry=regime, atr_at_entry=atr,
            rs_pct=payload.get("rs_pct"),
            composite_score=payload.get("composite_score"),
            structure_quality=payload.get("structure_quality"),
            signal_price=price_estimate,
            slippage=fill_slippage,
            extra={
                "commission": fill_commission,
                "strategy": strategy,
                "entry_type": entry_type or "standard",
                "support_level": support_level,
                "timeframe": payload.get("timeframe", "D"),
            },
        )
        _append_execution_record(rec)
        logger.info(
            "Webhook order %s %d %s: entry=%.2f ($%s)",
            action, filled_qty, symbol, entry_price, f"{entry_price * filled_qty:,.0f}",
        )
        return True
    except Exception as e:
        logger.exception("Webhook execution failed")
        _append_execution(symbol, action, "ERROR", reason=str(e))
        return False
    finally:
        await router.shutdown()
        ib.disconnect()


def _append_execution(symbol: str, action: str, status: str, reason: str = "") -> None:
    EXECUTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "symbol": symbol,
        "type": "SHORT" if action == "SELL" else "LONG",
        "action": action,
        "source_script": "execute_webhook_signal.py",
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "reason": reason,
    }
    try:
        from trade_log_db import insert_trade
        insert_trade(rec)
    except Exception as exc:
        logger.warning("trade_log_db insert failed (non-fatal): %s", exc)
    from file_utils import append_jsonl
    append_jsonl(EXECUTION_LOG, rec)


def _append_execution_record(rec: dict) -> None:
    EXECUTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        from trade_log_db import insert_trade
        insert_trade(rec)
    except Exception as exc:
        logger.warning("trade_log_db insert failed (non-fatal): %s", exc)
    from file_utils import append_jsonl
    append_jsonl(EXECUTION_LOG, rec)


def main() -> None:
    if len(sys.argv) < 2:
        logger.error("Usage: python execute_webhook_signal.py '<json payload>'")
        sys.exit(1)
    try:
        payload = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON: %s", e)
        sys.exit(1)
    if not isinstance(payload, dict):
        logger.error("Payload must be a JSON object")
        sys.exit(1)
    ok = asyncio.run(run(payload))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
