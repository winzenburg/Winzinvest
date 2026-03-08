#!/usr/bin/env python3
"""
Long-only executor: load watchlist_longs.json, place BUY orders with 2% stop / 3% TP.

Skips symbols already long. Logs to shared executions.json with source_script + type. Uses clientId=102.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from ib_insync import IB, Stock, MarketOrder, StopOrder, LimitOrder, Order

from atr_stops import calculate_position_size, compute_stop_tp, compute_trailing_amount, fetch_atr
from candidate_ranking import long_conviction
from enriched_record import build_enriched_record
from execution_gates import check_all_gates
from regime_detector import detect_market_regime
from risk_config import (
    get_absolute_max_shares,
    get_daily_loss_limit_pct,
    get_max_long_positions,
    get_max_position_pct_of_equity,
    get_max_sector_concentration_pct,
    get_net_liquidation_and_effective_equity,
    get_risk_per_trade_pct,
)
from sector_gates import SECTOR_MAP, portfolio_sector_exposure

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            Path(__file__).resolve().parent.parent / "logs" / "execute_longs.log"
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

from paths import TRADING_DIR
WATCHLIST_LONGS_FILE = TRADING_DIR / "watchlist_longs.json"
# Single shared execution log (same as execute_candidates / execute_dual_mode)
EXECUTION_LOG = TRADING_DIR / "logs" / "executions.json"

LONG_PARAMS: dict = {}
LOSS_TRACKER = TRADING_DIR / "logs" / "daily_loss.json"


def _current_long_symbols(ib: IB) -> set:
    out = set()
    try:
        for pos in ib.positions():
            if getattr(pos.contract, "secType", "") != "STK":
                continue
            if getattr(pos, "position", 0) > 0:
                sym = getattr(pos.contract, "symbol", "")
                if isinstance(sym, str) and sym.strip():
                    out.add(sym.strip().upper())
    except Exception as e:
        logger.warning("Could not fetch positions: %s", e)
    return out


def _load_long_candidates() -> list:
    if not WATCHLIST_LONGS_FILE.exists():
        logger.error("Watchlist not found: %s", WATCHLIST_LONGS_FILE)
        return []
    try:
        data = json.loads(WATCHLIST_LONGS_FILE.read_text())
    except (OSError, ValueError) as e:
        logger.warning("Failed to load watchlist: %s", e)
        return []
    candidates = data.get("long_candidates", [])
    if not isinstance(candidates, list):
        return []
    return [
        {
            "symbol": c.get("symbol", "").strip().upper(),
            "price": float(c.get("price", 0)),
        }
        for c in candidates
        if isinstance(c, dict) and c.get("symbol") and isinstance(c.get("price"), (int, float))
    ]


async def execute_one_long(
    ib: IB,
    candidate: dict,
    current_longs: set,
    account_value: float = 100_000.0,
    risk_per_trade_pct: float = 0.01,
    max_position_pct: float = 0.05,
    absolute_max_shares: int = 5000,
    regime: str = "CHOPPY",
) -> tuple:
    """Execute one long with account-relative sizing. Returns (success, enriched_record_or_None)."""
    symbol = candidate["symbol"]
    if symbol in current_longs:
        logger.info("Skipping %s: already long", symbol)
        return False, None
    price = candidate["price"]

    try:
        contract = Stock(symbol, "SMART", "USD")
        qualified = await ib.qualifyContractsAsync(contract)
        if not qualified:
            logger.error("Contract qualification failed: %s", symbol)
            return False, None
        contract = qualified[0]

        atr = fetch_atr(symbol, ib=ib)
        conv = long_conviction(candidate)
        qty = calculate_position_size(
            account_value, price, atr=atr,
            risk_pct=risk_per_trade_pct,
            max_position_pct=max_position_pct,
            absolute_max_shares=absolute_max_shares,
            conviction=conv,
        )

        order = MarketOrder("BUY", qty)
        trade = ib.placeOrder(contract, order)
        for _ in range(20):
            await asyncio.sleep(0.5)
            if trade.isDone():
                break
        status = trade.orderStatus.status
        if status != "Filled" and status != "PartiallyFilled":
            ib.cancelOrder(trade.order)
            logger.warning("Long order not filled, cancelled: %s %s", symbol, status)
            return False, None

        entry_price = float(trade.orderStatus.avgFillPrice or price)
        fill_slippage = abs(entry_price - price) if entry_price > 0 else 0.0
        fill_commission = 0.0
        try:
            for fill in trade.fills:
                cr = getattr(fill, "commissionReport", None)
                if cr and getattr(cr, "commission", 0):
                    fill_commission += float(cr.commission)
        except Exception:
            pass
        stop_price, tp_price = compute_stop_tp(entry_price, "BUY", atr=atr)
        trail_amt = compute_trailing_amount(atr=atr, entry_price=entry_price)

        trailing_stop = Order(
            action="SELL", orderType="TRAIL", totalQuantity=qty,
            auxPrice=trail_amt, tif="GTC",
        )
        ib.placeOrder(contract, trailing_stop)
        ib.placeOrder(contract, LimitOrder("SELL", qty, tp_price))

        rec = build_enriched_record(
            symbol=symbol, side="LONG", action="BUY",
            source_script="execute_longs.py", status=status,
            order_id=trade.order.orderId, quantity=qty,
            entry_price=entry_price, stop_price=stop_price, profit_price=tp_price,
            regime_at_entry=regime, conviction_score=conv, atr_at_entry=atr,
            rs_pct=candidate.get("rs_pct") or candidate.get("score"),
            composite_score=candidate.get("composite_score"),
            structure_quality=candidate.get("structure_quality"),
            rvol_atr=candidate.get("rvol_atr"),
            signal_price=price,
            slippage=fill_slippage,
            extra={"commission": fill_commission},
        )
        logger.info(
            "Long placed: %s entry=%.2f trail=%.2f tp=%.2f slip=%.4f",
            symbol, entry_price, trail_amt, tp_price, fill_slippage,
        )
        return True, rec
    except Exception as e:
        logger.error("Execution error %s: %s", symbol, e)
        return False, None


async def run() -> None:
    logger.info("=== LONG EXECUTOR ===")
    ib = IB()
    try:
        await ib.connectAsync("127.0.0.1", 4002, clientId=102)
    except Exception as e:
        logger.error("Connection failed: %s", e)
        return

    try:
        try:
            from agents.risk_monitor import is_kill_switch_active
            if is_kill_switch_active():
                logger.warning("Kill switch is active. No executions.")
                return
        except ImportError:
            pass

        regime = detect_market_regime(ib=ib)
        logger.info("Market regime: %s", regime)

        current_longs = _current_long_symbols(ib)
        candidates = _load_long_candidates()
        if not candidates:
            logger.info("No long candidates")
            return

        net_liq, effective_equity = get_net_liquidation_and_effective_equity(ib, TRADING_DIR)

        risk_per_trade_pct = get_risk_per_trade_pct(TRADING_DIR)
        max_position_pct = get_max_position_pct_of_equity(TRADING_DIR, side="long")
        absolute_max_shares = get_absolute_max_shares(TRADING_DIR)
        daily_loss_limit_pct = get_daily_loss_limit_pct(TRADING_DIR)

        logger.info(
            "Net liq $%s | Effective $%s | Risk %.1f%% per trade | Max position %.1f%% ($%s)",
            f"{net_liq:,.0f}", f"{effective_equity:,.0f}", risk_per_trade_pct * 100,
            max_position_pct * 100, f"{effective_equity * max_position_pct:,.0f}",
        )

        daily_loss = 0.0
        if LOSS_TRACKER.exists():
            try:
                data = json.loads(LOSS_TRACKER.read_text())
                if data.get("date") == datetime.now().date().isoformat():
                    daily_loss = float(data.get("loss", 0) or 0)
            except (OSError, ValueError, TypeError):
                pass

        sector_exposure, total_notional = portfolio_sector_exposure(ib)
        max_sector_pct = get_max_sector_concentration_pct(TRADING_DIR)
        max_longs = get_max_long_positions(TRADING_DIR)

        if len(current_longs) >= max_longs:
            logger.warning("Max long positions reached (%d/%d). No new longs.", len(current_longs), max_longs)
            return

        executions = []
        for candidate in candidates[:5]:
            if len(current_longs) >= max_longs:
                logger.info("Max long positions reached mid-loop (%d/%d). Stopping.", len(current_longs), max_longs)
                break
            symbol = candidate["symbol"]
            estimated_notional = min(
                effective_equity * max_position_pct,
                candidate["price"] * absolute_max_shares,
            )
            gates_ok, failed_gates = check_all_gates(
                signal_type="LONG",
                symbol=symbol,
                notional=estimated_notional,
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
                logger.info("Skipping long %s: gates failed: %s", symbol, ", ".join(failed_gates))
                continue
            ok, rec = await execute_one_long(
                ib, candidate, current_longs,
                account_value=effective_equity,
                risk_per_trade_pct=risk_per_trade_pct,
                max_position_pct=max_position_pct,
                absolute_max_shares=absolute_max_shares,
                regime=regime,
            )
            if ok and rec is not None:
                current_longs.add(symbol)
                sector = SECTOR_MAP.get(symbol, "Unknown")
                sector_exposure[sector] = sector_exposure.get(sector, 0.0) + estimated_notional
                total_notional += estimated_notional
                executions.append(rec)
            await asyncio.sleep(1)

        if executions:
            try:
                from trade_log_db import insert_trade
                for e in executions:
                    insert_trade(e)
            except ImportError:
                pass
            EXECUTION_LOG.parent.mkdir(parents=True, exist_ok=True)
            with open(EXECUTION_LOG, "a") as f:
                for e in executions:
                    f.write(json.dumps(e) + "\n")
            logger.info("Logged %d executions to %s", len(executions), EXECUTION_LOG)
    finally:
        ib.disconnect()


if __name__ == "__main__":
    asyncio.run(run())
