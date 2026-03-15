#!/usr/bin/env python3
"""
Mean Reversion (RSI-2) Executor.

Loads watchlist_mean_reversion.json, places BUY orders with tight stops
(1.0 ATR stop, 1.5 ATR TP). Monitors existing MR positions for RSI(2) > 70 exit.
Uses clientId=107. Writes to shared EXECUTION_LOG.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd
import yfinance as yf
from ib_insync import IB, LimitOrder, MarketOrder, Order, Stock

from order_rth import apply_rth_to_order, get_entry_order
from atr_stops import (
    calculate_position_size,
    compute_stop_tp,
    compute_trailing_amount,
    fetch_atr,
)
from enriched_record import build_enriched_record
from execution_gates import check_all_gates
from live_allocation import get_effective_equity as _apply_alloc
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

from paths import TRADING_DIR

_env_path = TRADING_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "4001"))

WATCHLIST_MR_FILE = TRADING_DIR / "watchlist_mean_reversion.json"
EXECUTION_LOG = TRADING_DIR / "logs" / "executions.json"
MR_POSITIONS_FILE = TRADING_DIR / "logs" / "mr_positions.json"
LOSS_TRACKER = TRADING_DIR / "logs" / "daily_loss.json"

# MR-specific: tight stops (1.0 ATR) and TP (1.5 ATR)
MR_STOP_ATR_MULT = 1.0
MR_TP_ATR_MULT = 1.5
MR_TRAILING_ATR_MULT = 1.0
MR_RSI_EXIT_THRESHOLD = 70.0

IBKR_CLIENT_ID = 107
MAX_CANDIDATES_PER_RUN = 10

# Ensure log directory exists before configuring handler
(TRADING_DIR / "logs").mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(TRADING_DIR / "logs" / "execute_mr.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def _ensure_log_dir() -> None:
    """Ensure logs directory exists."""
    EXECUTION_LOG.parent.mkdir(parents=True, exist_ok=True)


def _current_long_symbols(ib: IB) -> Set[str]:
    """Return set of symbols we are currently long."""
    out: Set[str] = set()
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


def _load_mr_positions() -> List[str]:
    """Load list of symbols we've placed as MR (for RSI exit monitoring)."""
    if not MR_POSITIONS_FILE.exists():
        return []
    try:
        data = json.loads(MR_POSITIONS_FILE.read_text())
        symbols = data.get("symbols", [])
        if isinstance(symbols, list):
            return [s for s in symbols if isinstance(s, str) and s.strip()]
    except (OSError, ValueError, TypeError) as e:
        logger.warning("Failed to load MR positions: %s", e)
    return []


def _save_mr_positions(symbols: List[str]) -> None:
    """Persist MR position symbols."""
    _ensure_log_dir()
    try:
        MR_POSITIONS_FILE.write_text(
            json.dumps({"symbols": symbols, "updated_at": datetime.now().isoformat()}),
            encoding="utf-8",
        )
    except OSError as e:
        logger.error("Failed to save MR positions: %s", e)


def _compute_rsi2(symbol: str) -> Optional[float]:
    """Fetch recent data and compute RSI(2). Returns None on failure."""
    try:
        df = yf.download(symbol, period="1mo", progress=False)
        if df is None or df.empty or len(df) < 4:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        close = df["Close"].values
        if len(close) < 3:
            return None
        diffs = np.diff(close[-3:])
        gains = np.mean(diffs[diffs > 0]) if np.any(diffs > 0) else 0.0
        losses = np.mean(-diffs[diffs < 0]) if np.any(diffs < 0) else 0.0001
        rs = gains / losses if losses > 0 else 100.0
        return float(100 - (100 / (1 + rs)))
    except Exception as e:
        logger.debug("RSI(2) fetch failed for %s: %s", symbol, e)
        return None


def _load_mr_candidates() -> List[Dict[str, object]]:
    """Load MR candidates from watchlist. Returns list of candidate dicts."""
    if not WATCHLIST_MR_FILE.exists():
        logger.error("Watchlist not found: %s", WATCHLIST_MR_FILE)
        return []
    try:
        data = json.loads(WATCHLIST_MR_FILE.read_text())
        candidates = data.get("candidates", [])
        if not isinstance(candidates, list):
            return []
        out: List[Dict[str, object]] = []
        for c in candidates:
            if not isinstance(c, dict):
                continue
            sym = c.get("symbol")
            price = c.get("price")
            if not isinstance(sym, str) or not sym.strip():
                continue
            if not isinstance(price, (int, float)) or float(price) <= 0:
                continue
            out.append({
                "symbol": sym.strip().upper(),
                "price": float(price),
                "rsi2": c.get("rsi2"),
                "sma200": c.get("sma200"),
                "score": c.get("score"),
                "reason": c.get("reason"),
            })
        return out
    except (OSError, ValueError, TypeError) as e:
        logger.warning("Failed to load watchlist: %s", e)
        return []


async def _close_mr_position(
    ib: IB, symbol: str, quantity: int
) -> Tuple[bool, Optional[Dict[str, object]]]:
    """Place market SELL to close MR position. Returns (success, enriched_record)."""
    try:
        contract = Stock(symbol, "SMART", "USD")
        qualified = await ib.qualifyContractsAsync(contract)
        if not qualified:
            logger.error("Contract qualification failed for close: %s", symbol)
            return False, None
        contract = qualified[0]

        order = MarketOrder("SELL", quantity)
        trade = ib.placeOrder(contract, order)
        for _ in range(20):
            await asyncio.sleep(0.5)
            if trade.isDone():
                break
        status = trade.orderStatus.status
        if status not in ("Filled", "PartiallyFilled"):
            ib.cancelOrder(trade.order)
            logger.warning("MR close order not filled: %s %s", symbol, status)
            return False, None

        entry_price = float(trade.orderStatus.avgFillPrice or 0)
        rec = build_enriched_record(
            symbol=symbol,
            side="LONG",
            action="SELL",
            source_script="execute_mean_reversion.py",
            status=status,
            order_id=trade.order.orderId,
            quantity=quantity,
            entry_price=entry_price,
            stop_price=0.0,
            profit_price=0.0,
            reason="RSI(2) > 70 exit",
            extra={"strategy": "mean_reversion", "exit_reason": "rsi_overbought"},
        )
        logger.info("MR position closed: %s qty=%d status=%s", symbol, quantity, status)
        return True, rec
    except Exception as e:
        logger.error("Close error %s: %s", symbol, e)
        return False, None


async def _monitor_mr_exits(ib: IB) -> List[Dict[str, object]]:
    """
    Check MR positions for RSI(2) > 70 exit. Close those positions.
    Returns list of enriched records for closed positions.
    """
    mr_symbols = _load_mr_positions()
    current_longs = _current_long_symbols(ib)
    closed_records: List[Dict[str, object]] = []
    remaining_mr: List[str] = []

    for symbol in mr_symbols:
        if symbol not in current_longs:
            remaining_mr.append(symbol)
            continue

        rsi2 = _compute_rsi2(symbol)
        if rsi2 is None:
            remaining_mr.append(symbol)
            continue

        if rsi2 <= MR_RSI_EXIT_THRESHOLD:
            remaining_mr.append(symbol)
            continue

        # RSI(2) > 70: close position
        qty = 0
        try:
            for pos in ib.positions():
                if getattr(pos.contract, "symbol", "") == symbol and getattr(
                    pos, "position", 0
                ) > 0:
                    qty = int(pos.position)
                    break
        except Exception as e:
            logger.warning("Could not get position size for %s: %s", symbol, e)
            remaining_mr.append(symbol)
            continue

        if qty <= 0:
            remaining_mr.append(symbol)
            continue

        ok, rec = await _close_mr_position(ib, symbol, qty)
        if ok and rec is not None:
            closed_records.append(rec)
            # Do not add to remaining_mr (we closed it)
        else:
            remaining_mr.append(symbol)
        await asyncio.sleep(1)

    _save_mr_positions(remaining_mr)
    return closed_records


async def _execute_one_mr(
    ib: IB,
    candidate: Dict[str, object],
    current_longs: Set[str],
    account_value: float,
    risk_per_trade_pct: float,
    max_position_pct: float,
    absolute_max_shares: int,
    cap_equity: float | None = None,
) -> Tuple[bool, Optional[Dict[str, object]]]:
    """
    Execute one MR buy. Returns (success, enriched_record_or_None).
    Uses 1.0 ATR stop, 1.5 ATR TP, 1.0 ATR trailing.
    """
    symbol = str(candidate.get("symbol", "")).strip().upper()
    if symbol in current_longs:
        logger.info("Skipping %s: already long", symbol)
        return False, None
    price = float(candidate.get("price", 0))

    try:
        contract = Stock(symbol, "SMART", "USD")
        qualified = await ib.qualifyContractsAsync(contract)
        if not qualified:
            logger.error("Contract qualification failed: %s", symbol)
            return False, None
        contract = qualified[0]

        atr = fetch_atr(symbol, ib=ib)
        qty = calculate_position_size(
            account_value,
            price,
            atr=atr,
            risk_pct=risk_per_trade_pct,
            max_position_pct=max_position_pct,
            absolute_max_shares=absolute_max_shares,
            stop_mult=MR_STOP_ATR_MULT,
            conviction=None,
            cap_equity=cap_equity,
        )

        order = get_entry_order("BUY", qty, price, TRADING_DIR)
        trade = ib.placeOrder(contract, order)
        for _ in range(20):
            await asyncio.sleep(0.5)
            if trade.isDone():
                break
        status = trade.orderStatus.status
        if status not in ("Filled", "PartiallyFilled"):
            ib.cancelOrder(trade.order)
            logger.warning("MR order not filled, cancelled: %s %s", symbol, status)
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

        stop_price, tp_price = compute_stop_tp(
            entry_price,
            "BUY",
            atr=atr,
            stop_mult=MR_STOP_ATR_MULT,
            tp_mult=MR_TP_ATR_MULT,
        )
        trail_amt = compute_trailing_amount(
            atr=atr,
            entry_price=entry_price,
            trailing_mult=MR_TRAILING_ATR_MULT,
        )

        trailing_stop = Order(
            action="SELL",
            orderType="TRAIL",
            totalQuantity=qty,
            auxPrice=trail_amt,
            tif="GTC",
        )
        apply_rth_to_order(trailing_stop, "stop", TRADING_DIR)
        ib.placeOrder(contract, trailing_stop)
        tp_order = LimitOrder("SELL", qty, tp_price)
        apply_rth_to_order(tp_order, "take_profit", TRADING_DIR)
        ib.placeOrder(contract, tp_order)

        rec = build_enriched_record(
            symbol=symbol,
            side="LONG",
            action="BUY",
            source_script="execute_mean_reversion.py",
            status=status,
            order_id=trade.order.orderId,
            quantity=qty,
            entry_price=entry_price,
            stop_price=stop_price,
            profit_price=tp_price,
            atr_at_entry=atr,
            rs_pct=candidate.get("score"),
            signal_price=price,
            slippage=fill_slippage,
            reason=candidate.get("reason"),
            extra={
                "commission": fill_commission,
                "strategy": "mean_reversion",
                "rsi2": candidate.get("rsi2"),
            },
        )
        logger.info(
            "MR placed: %s entry=%.2f trail=%.2f tp=%.2f slip=%.4f",
            symbol,
            entry_price,
            trail_amt,
            tp_price,
            fill_slippage,
        )
        return True, rec
    except Exception as e:
        logger.error("Execution error %s: %s", symbol, e)
        return False, None


async def run() -> None:
    """Main executor: monitor RSI exits, then place new MR orders."""
    _mode = os.getenv("TRADING_MODE", "paper")
    if _mode == "live":
        logger.warning("🔴 LIVE TRADING MODE — real money at risk")
    logger.info("=== MEAN REVERSION EXECUTOR [%s] ===", _mode.upper())
    _ensure_log_dir()

    ib = IB()
    try:
        await ib.connectAsync(IB_HOST, IB_PORT, clientId=IBKR_CLIENT_ID)
    except Exception as e:
        logger.error("Connection failed: %s", e)
        try:
            from notifications import notify_executor_error
            notify_executor_error("execute_mean_reversion.py", str(e), context="IB connection")
        except Exception:
            pass
        return

    try:
        try:
            from agents.risk_monitor import is_kill_switch_active

            if is_kill_switch_active():
                logger.warning("Kill switch is active. No executions.")
                return
        except ImportError:
            pass

        # 1. Monitor existing MR positions for RSI(2) > 70 exit
        exit_records = await _monitor_mr_exits(ib)
        if exit_records:
            for rec in exit_records:
                try:
                    from trade_log_db import insert_trade

                    insert_trade(rec)
                except Exception as exc:
                    logger.warning("trade_log_db insert failed (non-fatal): %s", exc)
            from file_utils import append_jsonl
            for rec in exit_records:
                append_jsonl(EXECUTION_LOG, rec)
            logger.info("Logged %d MR exit(s) to %s", len(exit_records), EXECUTION_LOG)

        # 2. Load candidates and place new orders
        current_longs = _current_long_symbols(ib)
        candidates = _load_mr_candidates()
        if not candidates:
            logger.info("No MR candidates")
            return

        raw_nlv, raw_eq = get_net_liquidation_and_effective_equity(ib, TRADING_DIR)
        net_liq = _apply_alloc(raw_nlv)
        effective_equity = _apply_alloc(raw_eq)

        risk_per_trade_pct = get_risk_per_trade_pct(TRADING_DIR)
        max_position_pct = get_max_position_pct_of_equity(TRADING_DIR, side="long")
        absolute_max_shares = get_absolute_max_shares(TRADING_DIR)
        daily_loss_limit_pct = get_daily_loss_limit_pct(TRADING_DIR)
        max_longs = get_max_long_positions(TRADING_DIR)
        max_sector_pct = get_max_sector_concentration_pct(TRADING_DIR)

        daily_loss = 0.0
        if LOSS_TRACKER.exists():
            try:
                data = json.loads(LOSS_TRACKER.read_text())
                if data.get("date") == datetime.now().date().isoformat():
                    daily_loss = float(data.get("loss", 0) or 0)
            except (OSError, ValueError, TypeError):
                pass

        sector_exposure, total_notional = portfolio_sector_exposure(ib)

        if len(current_longs) >= max_longs:
            logger.warning(
                "Max long positions reached (%d/%d). No new MR orders.",
                len(current_longs),
                max_longs,
            )
            return

        executions: List[Dict[str, object]] = []
        mr_symbols = _load_mr_positions()

        for candidate in candidates[:MAX_CANDIDATES_PER_RUN]:
            if len(current_longs) >= max_longs:
                break
            symbol = str(candidate.get("symbol", "")).strip().upper()
            price = float(candidate.get("price", 0))
            estimated_notional = min(
                net_liq * max_position_pct,
                price * absolute_max_shares,
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
                logger.info(
                    "Skipping MR %s: gates failed: %s",
                    symbol,
                    ", ".join(failed_gates),
                )
                continue

            ok, rec = await _execute_one_mr(
                ib,
                candidate,
                current_longs,
                account_value=effective_equity,
                risk_per_trade_pct=risk_per_trade_pct,
                max_position_pct=max_position_pct,
                absolute_max_shares=absolute_max_shares,
                cap_equity=net_liq,
            )
            if ok and rec is not None:
                current_longs.add(symbol)
                mr_symbols.append(symbol)
                sector = SECTOR_MAP.get(symbol, "Unknown")
                sector_exposure[sector] = sector_exposure.get(sector, 0.0) + estimated_notional
                total_notional += estimated_notional
                executions.append(rec)
            await asyncio.sleep(1)

        if mr_symbols:
            _save_mr_positions(mr_symbols)

        if executions:
            try:
                from trade_log_db import insert_trade

                for e in executions:
                    insert_trade(e)
            except Exception as exc:
                logger.warning("trade_log_db insert failed (non-fatal): %s", exc)
            from file_utils import append_jsonl as _append_jsonl
            for e in executions:
                _append_jsonl(EXECUTION_LOG, e)
            logger.info("Logged %d MR execution(s) to %s", len(executions), EXECUTION_LOG)
    finally:
        ib.disconnect()


if __name__ == "__main__":
    asyncio.run(run())
