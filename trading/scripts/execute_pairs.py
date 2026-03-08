#!/usr/bin/env python3
"""
Pairs Executor — Simultaneous long/short execution with bracket orders.

Loads watchlist_pairs.json, connects to IBKR (clientId=106), places MarketOrder
BUY on long leg and MarketOrder SELL on short leg with 2 ATR stop / 3 ATR TP each.
Tracks open pairs in pairs_positions.json. Exit logic: close both legs when
spread z-score reverts to < 0.5 or after 15 days.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ib_insync import IB, Stock, MarketOrder, LimitOrder, StopOrder, Order

from atr_stops import compute_stop_tp, fetch_atr
from enriched_record import build_enriched_record
from execution_gates import check_all_gates
from risk_config import (
    get_daily_loss_limit_pct,
    get_max_sector_concentration_pct,
    get_net_liquidation_and_effective_equity,
)
from sector_gates import SECTOR_MAP, portfolio_sector_exposure

from paths import TRADING_DIR
WATCHLIST_PAIRS_FILE = TRADING_DIR / "watchlist_pairs.json"
PAIRS_POSITIONS_FILE = TRADING_DIR / "logs" / "pairs_positions.json"
EXECUTION_LOG = TRADING_DIR / "logs" / "executions.json"
LOSS_TRACKER = TRADING_DIR / "logs" / "daily_loss.json"
LOG_FILE = TRADING_DIR / "logs" / "execute_pairs.log"

MAX_PAIRS_PER_RUN = 5
NOTIONAL_PER_LEG = 20_000.0
NOTIONAL_PCT_PER_LEG = 0.02
PAIRS_STOP_ATR_MULT = 2.0
PAIRS_TP_ATR_MULT = 3.0
PAIRS_MAX_DAYS = 15
PAIRS_EXIT_ZSCORE = 0.5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def _load_watchlist_pairs() -> List[Dict[str, Any]]:
    """Load pairs from watchlist_pairs.json."""
    if not WATCHLIST_PAIRS_FILE.exists():
        return []
    try:
        data = json.loads(WATCHLIST_PAIRS_FILE.read_text(encoding="utf-8"))
        pairs = data.get("pairs", [])
        if not isinstance(pairs, list):
            return []
        return [p for p in pairs if isinstance(p, dict) and p.get("long_sym") and p.get("short_sym")]
    except (OSError, ValueError) as e:
        logger.error("Failed to load watchlist_pairs.json: %s", e)
        return []


def _load_pairs_positions() -> List[Dict[str, Any]]:
    """Load open pairs from pairs_positions.json."""
    if not PAIRS_POSITIONS_FILE.exists():
        return []
    try:
        data = json.loads(PAIRS_POSITIONS_FILE.read_text(encoding="utf-8"))
        positions = data.get("positions", [])
        if not isinstance(positions, list):
            return []
        return positions
    except (OSError, ValueError):
        return []


def _save_pairs_positions(positions: List[Dict[str, Any]]) -> None:
    """Save open pairs to pairs_positions.json."""
    PAIRS_POSITIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {"positions": positions, "updated_at": datetime.now().isoformat()}
    PAIRS_POSITIONS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _current_position_symbols(ib: IB) -> Tuple[Set[str], Set[str]]:
    """Return (long_symbols, short_symbols) from ib.positions()."""
    longs: Set[str] = set()
    shorts: Set[str] = set()
    try:
        for pos in ib.positions():
            if getattr(pos.contract, "secType", "") != "STK":
                continue
            position = getattr(pos, "position", 0)
            sym = getattr(pos.contract, "symbol", "")
            if not isinstance(sym, str) or not sym.strip():
                continue
            sym = sym.strip().upper()
            if position > 0:
                longs.add(sym)
            elif position < 0:
                shorts.add(sym)
    except Exception as e:
        logger.warning("Could not fetch positions: %s", e)
    return longs, shorts




def _load_daily_loss() -> float:
    """Load today's realized loss from daily_loss.json."""
    if not LOSS_TRACKER.exists():
        return 0.0
    try:
        data = json.loads(LOSS_TRACKER.read_text())
        if data.get("date") == datetime.now().date().isoformat():
            return float(data.get("loss", 0) or 0)
    except (OSError, ValueError, TypeError):
        pass
    return 0.0


def _notional_per_leg(account_equity: float) -> float:
    """Equal dollar notional per leg: min($20K, 2% of equity)."""
    pct_amount = account_equity * NOTIONAL_PCT_PER_LEG
    return min(NOTIONAL_PER_LEG, pct_amount)


async def _execute_pair(
    ib: IB,
    pair: Dict[str, Any],
    long_symbols: Set[str],
    short_symbols: Set[str],
    notional_per_leg: float,
    sector_exposure: Dict[str, float],
    total_notional: float,
    max_sector_pct: float,
    daily_loss: float,
    daily_loss_limit_pct: float,
    account_equity_net: float,
    account_equity_effective: float,
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Execute one pair: BUY long leg, SELL short leg. Returns (success, [exec_records]).
    Skips if either leg already in position. Uses 2 ATR stop, 3 ATR TP each.
    """
    long_sym = (pair.get("long_sym") or "").strip().upper()
    short_sym = (pair.get("short_sym") or "").strip().upper()
    sector = pair.get("sector", "Unknown")

    if not long_sym or not short_sym:
        return False, []

    if long_sym in long_symbols or short_sym in short_symbols:
        logger.info("Skipping pair %s/%s: leg already in position", long_sym, short_sym)
        return False, []

    long_price = float(pair.get("long_price") or 0)
    short_price = float(pair.get("short_price") or 0)
    if long_price <= 0 or short_price <= 0:
        logger.warning("Pair %s/%s: missing prices", long_sym, short_sym)
        return False, []

    long_qty = max(1, int(notional_per_leg / long_price))
    short_qty = max(1, int(notional_per_leg / short_price))
    long_notional = long_qty * long_price
    short_notional = short_qty * short_price

    # SAFETY: Run gates for both legs
    for sym, side, notional in [(long_sym, "LONG", long_notional), (short_sym, "SHORT", short_notional)]:
        gates_ok, failed = check_all_gates(
            signal_type=side,
            symbol=sym,
            notional=notional,
            daily_loss=daily_loss,
            account_equity=account_equity_net,
            daily_loss_limit_pct=daily_loss_limit_pct,
            sector_exposure=sector_exposure,
            total_notional=total_notional,
            max_sector_pct=max_sector_pct,
            minutes_before_close=60,
            max_notional_pct_of_equity=0.5,
            ib=ib,
            account_equity_effective=account_equity_effective,
        )
        if not gates_ok:
            logger.info("Skipping pair %s/%s: gates failed for %s: %s", long_sym, short_sym, sym, ", ".join(failed))
            return False, []

    try:
        long_contract = Stock(long_sym, "SMART", "USD")
        short_contract = Stock(short_sym, "SMART", "USD")
        long_qualified = await ib.qualifyContractsAsync(long_contract)
        short_qualified = await ib.qualifyContractsAsync(short_contract)
        if not long_qualified or not short_qualified:
            logger.error("Contract qualification failed: %s or %s", long_sym, short_sym)
            return False, []
        long_contract = long_qualified[0]
        short_contract = short_qualified[0]

        long_atr = fetch_atr(long_sym, ib=ib)
        short_atr = fetch_atr(short_sym, ib=ib)

        # Place market orders first
        long_order = MarketOrder("BUY", long_qty)
        short_order = MarketOrder("SELL", short_qty)
        long_trade = ib.placeOrder(long_contract, long_order)
        short_trade = ib.placeOrder(short_contract, short_order)

        for _ in range(20):
            await asyncio.sleep(0.5)
            if long_trade.isDone() and short_trade.isDone():
                break

        long_status = long_trade.orderStatus.status
        short_status = short_trade.orderStatus.status
        if long_status not in ("Filled", "PartiallyFilled") or short_status not in ("Filled", "PartiallyFilled"):
            ib.cancelOrder(long_trade.order)
            ib.cancelOrder(short_trade.order)
            logger.warning("Pair %s/%s: orders not filled (long=%s short=%s)", long_sym, short_sym, long_status, short_status)
            return False, []

        long_entry = float(long_trade.orderStatus.avgFillPrice or long_price)
        short_entry = float(short_trade.orderStatus.avgFillPrice or short_price)
        long_fill_qty = int(long_trade.orderStatus.filled or long_qty)
        short_fill_qty = int(short_trade.orderStatus.filled or short_qty)

        # Place bracket orders: stop and TP for each leg
        long_stop, long_tp = compute_stop_tp(long_entry, "BUY", atr=long_atr, stop_mult=PAIRS_STOP_ATR_MULT, tp_mult=PAIRS_TP_ATR_MULT)
        short_stop, short_tp = compute_stop_tp(short_entry, "SELL", atr=short_atr, stop_mult=PAIRS_STOP_ATR_MULT, tp_mult=PAIRS_TP_ATR_MULT)

        ib.placeOrder(long_contract, StopOrder("SELL", long_fill_qty, long_stop, tif="GTC"))
        ib.placeOrder(long_contract, LimitOrder("SELL", long_fill_qty, long_tp, tif="GTC"))
        ib.placeOrder(short_contract, StopOrder("BUY", short_fill_qty, short_stop, tif="GTC"))
        ib.placeOrder(short_contract, LimitOrder("BUY", short_fill_qty, short_tp, tif="GTC"))

        long_rec = build_enriched_record(
            symbol=long_sym,
            side="LONG",
            action="BUY",
            source_script="execute_pairs.py",
            status=long_status,
            order_id=long_trade.order.orderId,
            quantity=long_fill_qty,
            entry_price=long_entry,
            stop_price=long_stop,
            profit_price=long_tp,
            atr_at_entry=long_atr,
            composite_score=pair.get("long_score"),
            signal_price=long_price,
            reason=f"pairs_long {sector} {short_sym}",
            extra={"strategy": "pairs_long", "pair_short": short_sym, "sector": sector},
        )
        short_rec = build_enriched_record(
            symbol=short_sym,
            side="SHORT",
            action="SELL",
            source_script="execute_pairs.py",
            status=short_status,
            order_id=short_trade.order.orderId,
            quantity=short_fill_qty,
            entry_price=short_entry,
            stop_price=short_stop,
            profit_price=short_tp,
            atr_at_entry=short_atr,
            composite_score=pair.get("short_score"),
            signal_price=short_price,
            reason=f"pairs_short {sector} {long_sym}",
            extra={"strategy": "pairs_short", "pair_long": long_sym, "sector": sector},
        )

        logger.info(
            "Pair placed: %s BUY %d @ %.2f (stop=%.2f tp=%.2f) | %s SELL %d @ %.2f (stop=%.2f tp=%.2f)",
            long_sym, long_fill_qty, long_entry, long_stop, long_tp,
            short_sym, short_fill_qty, short_entry, short_stop, short_tp,
        )
        return True, [long_rec, short_rec]
    except Exception as e:
        logger.error("Pair execution error %s/%s: %s", long_sym, short_sym, e)
        return False, []


async def _check_exits(ib: IB) -> List[Dict[str, Any]]:
    """
    Check open pairs for exit: spread z-score < 0.5 or 15 days.
    Returns list of exit records for logging.
    """
    # TODO: Implement full exit logic (requires live spread z-score + entry date)
    # For now, exit logic is a placeholder; actual exit would need:
    # - Load pairs_positions with entry dates
    # - Recompute spread z-score from current prices
    # - Place MarketOrder to close both legs when conditions met
    return []


async def run() -> None:
    """Main entry: load pairs, execute up to MAX_PAIRS_PER_RUN, track positions."""
    logger.info("=== PAIRS EXECUTOR (clientId=106) ===")
    ib = IB()
    try:
        await ib.connectAsync("127.0.0.1", 4002, clientId=106)
    except Exception as e:
        logger.error("Connection failed: %s", e)
        return

    try:
        net_liq, effective_equity = get_net_liquidation_and_effective_equity(ib, TRADING_DIR)
        daily_loss = _load_daily_loss()
        daily_loss_limit_pct = get_daily_loss_limit_pct(TRADING_DIR)
        max_sector_pct = get_max_sector_concentration_pct(TRADING_DIR)
        sector_exposure, total_notional = portfolio_sector_exposure(ib)
        notional_per_leg = _notional_per_leg(effective_equity)
        long_symbols, short_symbols = _current_position_symbols(ib)

        if daily_loss >= net_liq * daily_loss_limit_pct:
            logger.warning("Daily loss limit exceeded. No executions.")
            return

        pairs = _load_watchlist_pairs()
        if not pairs:
            logger.info("No pairs in watchlist")
            return

        await _check_exits(ib)

        executions: List[Dict[str, Any]] = []
        open_positions = _load_pairs_positions()

        for pair in pairs[:MAX_PAIRS_PER_RUN]:
            if len(executions) >= MAX_PAIRS_PER_RUN * 2:
                break
            ok, recs = await _execute_pair(
                ib, pair,
                long_symbols, short_symbols,
                notional_per_leg,
                sector_exposure, total_notional, max_sector_pct,
                daily_loss, daily_loss_limit_pct, net_liq, effective_equity,
            )
            if ok and recs:
                executions.extend(recs)
                long_sym = (pair.get("long_sym") or "").strip().upper()
                short_sym = (pair.get("short_sym") or "").strip().upper()
                long_symbols.add(long_sym)
                short_symbols.add(short_sym)
                open_positions.append({
                    "long_sym": long_sym,
                    "short_sym": short_sym,
                    "sector": pair.get("sector"),
                    "entry_date": datetime.now().date().isoformat(),
                    "spread_zscore_at_entry": pair.get("spread_zscore"),
                })
                total_notional += notional_per_leg * 2
                sector = pair.get("sector", "Unknown")
                sector_exposure[sector] = sector_exposure.get(sector, 0.0) + notional_per_leg - notional_per_leg
            await asyncio.sleep(1)

        if executions:
            try:
                from trade_log_db import insert_trade
                for e in executions:
                    insert_trade(e)
            except ImportError:
                pass
            EXECUTION_LOG.parent.mkdir(parents=True, exist_ok=True)
            with open(EXECUTION_LOG, "a", encoding="utf-8") as f:
                for e in executions:
                    f.write(json.dumps(e) + "\n")
            logger.info("Logged %d executions to %s", len(executions), EXECUTION_LOG)

        if open_positions:
            _save_pairs_positions(open_positions)
    finally:
        ib.disconnect()


if __name__ == "__main__":
    asyncio.run(run())
