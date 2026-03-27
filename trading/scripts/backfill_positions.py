#!/usr/bin/env python3
"""
Backfill Orphaned Positions into trades.db
-------------------------------------------
Reads IB positions, cross-references with trades.db open records, and
inserts stub entries for any orphaned positions (exist in IB but not DB).

This allows:
  - portfolio heat to count their stop risk
  - trade_outcome_resolver to track exit P&L
  - execution gates to have accurate position state

Usage:
  python3 backfill_positions.py            # dry-run (prints what would be inserted)
  python3 backfill_positions.py --live     # writes to trades.db
  python3 backfill_positions.py --symbol OXY --live  # single symbol
"""

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SCRIPTS_DIR = Path(__file__).resolve().parent
TRADING_DIR = SCRIPTS_DIR.parent
LOGS_DIR = TRADING_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "backfill_positions.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(SCRIPTS_DIR))

import os
from env_loader import load_env
load_env(TRADING_DIR / ".env")

from ib_insync import IB, Stock
from trade_log_db import get_open_trades, insert_trade, DEFAULT_DB_PATH


IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", 4001))
IB_CLIENT_ID = 122  # Dedicated client ID for backfill (read-only use)

ATR_STOP_MULT = 1.5   # Stop placed 1.5 ATR from current price
ATR_TP_MULT   = 2.5   # Take-profit at 2.5 ATR


def _yf_price_and_atr(symbol: str) -> tuple[float, float]:
    """Fetch last close price and 14-day ATR from yfinance. Returns (0, 0) on failure."""
    try:
        import yfinance as yf
        import numpy as np
        df = yf.download(symbol, period="30d", interval="1d", progress=False)
        if df is None or df.empty or len(df) < 2:
            return 0.0, 0.0
        if hasattr(df.columns, "levels"):
            df.columns = df.columns.get_level_values(0)
        high = df["High"].values
        low  = df["Low"].values
        close = df["Close"].values
        # True range
        tr = np.maximum(high[1:] - low[1:], np.abs(high[1:] - close[:-1]))
        tr = np.maximum(tr, np.abs(low[1:] - close[:-1]))
        atr = float(np.mean(tr[-14:]))
        last = float(close[-1])
        return last, atr
    except Exception as exc:
        logger.warning("yfinance failed for %s: %s", symbol, exc)
        return 0.0, 0.0


def get_ib_stock_positions(ib: IB) -> list[dict]:
    """Return list of {symbol, qty, avg_cost, market_value} for all stock positions."""
    out = []
    for pos in ib.positions():
        c = pos.contract
        if getattr(c, "secType", "") != "STK":
            continue
        qty = int(getattr(pos, "position", 0))
        if qty == 0:
            continue
        symbol = getattr(c, "symbol", "").strip().upper()
        if not symbol:
            continue
        avg_cost = float(getattr(pos, "avgCost", 0.0))
        mv = float(getattr(pos, "marketValue", 0.0) if hasattr(pos, "marketValue") else 0.0)
        out.append({
            "symbol":       symbol,
            "qty":          qty,
            "avg_cost":     avg_cost,
            "market_value": mv,
        })
    return out


def get_db_open_symbols() -> set[str]:
    """Return set of uppercase symbols that have open (unfilled exit) records in trades.db."""
    try:
        open_trades = get_open_trades()
        return {
            (t.get("symbol") or "").strip().upper()
            for t in open_trades
            if t.get("symbol")
        }
    except Exception as exc:
        logger.error("Could not read trades.db: %s", exc)
        return set()


def backfill_one(pos: dict, dry_run: bool) -> bool:
    """Insert a stub record for a single orphaned position. Returns True on success."""
    symbol = pos["symbol"]
    qty    = pos["qty"]
    side   = "BUY" if qty > 0 else "SELL"
    abs_qty = abs(qty)

    # Use IB average cost as entry price; fall back to live yf price if unavailable
    entry_price = pos["avg_cost"]
    if entry_price <= 0:
        entry_price, _ = _yf_price_and_atr(symbol)

    if entry_price <= 0:
        logger.warning("No price available for %s — skipping", symbol)
        return False

    # ATR-based stop and take-profit
    import math
    _, atr = _yf_price_and_atr(symbol)
    if atr <= 0 or math.isnan(atr):
        atr = entry_price * 0.015   # fallback: 1.5% of price

    if side == "BUY":
        stop_price   = round(entry_price - ATR_STOP_MULT * atr, 2)
        profit_price = round(entry_price + ATR_TP_MULT   * atr, 2)
    else:
        stop_price   = round(entry_price + ATR_STOP_MULT * atr, 2)
        profit_price = round(entry_price - ATR_TP_MULT   * atr, 2)

    record = {
        "symbol":        symbol,
        "action":        side,   # _normalize_side() reads "action" or "type", not "side"
        "qty":           abs_qty,
        "entry_price":   round(entry_price, 4),
        "stop_price":    stop_price,
        "profit_price":  profit_price,
        "timestamp":     datetime.now(timezone.utc).isoformat(),
        "strategy":      "backfill",
        "source_script": "backfill_positions.py",
        "status":        "Filled",
        "reason":        "Backfilled — position existed in IB without a trades.db record",
        "atr_at_entry":  round(atr, 4),
    }

    if dry_run:
        logger.info(
            "[DRY RUN] Would insert: %s %s qty=%d entry=%.2f stop=%.2f tp=%.2f atr=%.2f",
            side, symbol, abs_qty, entry_price, stop_price, profit_price, atr,
        )
        return True

    row_id = insert_trade(record)
    if row_id:
        logger.info(
            "Backfilled %s %s qty=%d  entry=%.2f  stop=%.2f  tp=%.2f  (row %d)",
            side, symbol, abs_qty, entry_price, stop_price, profit_price, row_id,
        )
        return True
    else:
        logger.error("Failed to insert backfill record for %s", symbol)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill orphaned IB positions into trades.db")
    parser.add_argument("--live",   action="store_true", help="Write to trades.db (default is dry-run)")
    parser.add_argument("--symbol", type=str, default=None, help="Only backfill a specific symbol")
    args = parser.parse_args()

    dry_run = not args.live
    filter_symbol = args.symbol.upper() if args.symbol else None

    logger.info("=== Backfill Orphaned Positions (%s) ===", "LIVE" if args.live else "DRY RUN")
    logger.info("Database: %s", DEFAULT_DB_PATH)

    ib = IB()
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, readonly=True)
    except Exception as exc:
        logger.error("Could not connect to IBKR: %s", exc)
        sys.exit(1)

    try:
        ib_positions = get_ib_stock_positions(ib)
        db_symbols   = get_db_open_symbols()

        logger.info("IB positions: %d  |  DB open records: %d", len(ib_positions), len(db_symbols))

        orphans = [
            p for p in ib_positions
            if p["symbol"] not in db_symbols
            and (filter_symbol is None or p["symbol"] == filter_symbol)
        ]

        if not orphans:
            logger.info("✅ No orphaned positions found%s.",
                        f" for {filter_symbol}" if filter_symbol else "")
            return

        logger.info("\nOrphaned positions (%d):", len(orphans))
        for p in orphans:
            side = "LONG" if p["qty"] > 0 else "SHORT"
            logger.info("  %s %s qty=%d  avg_cost=%.2f  mv=%.0f",
                        side, p["symbol"], abs(p["qty"]), p["avg_cost"], p["market_value"])

        inserted = 0
        for pos in orphans:
            if backfill_one(pos, dry_run):
                inserted += 1

        if dry_run:
            logger.info("\nDry run complete. %d record(s) would be inserted. Re-run with --live to commit.", inserted)
        else:
            logger.info("\nBackfill complete: %d/%d record(s) inserted.", inserted, len(orphans))

    finally:
        ib.disconnect()


if __name__ == "__main__":
    main()
