#!/usr/bin/env python3
"""
Sector Rebalancer
-----------------
Automatically reduces over-weight sectors by closing the weakest positions
until each sector is back within its concentration limit.

Weakness ranking (ascending = close first):
  1. Unrealized P&L % from average cost (most negative = weakest)
  2. Tie-break: absolute market value (smallest first — least disruption)

Covered-call handling:
  Before selling shares, any open covered calls on that position are bought
  to close first. The script will not leave naked calls.

Usage:
  python3 sector_rebalancer.py            # dry-run (no orders sent)
  python3 sector_rebalancer.py --live     # real orders
  python3 sector_rebalancer.py --live --sector Energy  # specific sector only
"""

import argparse
import json
import logging
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from ib_insync import IB, MarketOrder, Option, Stock

SCRIPTS_DIR = Path(__file__).resolve().parent
TRADING_DIR = SCRIPTS_DIR.parent
LOGS_DIR = TRADING_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "sector_rebalancer.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(SCRIPTS_DIR))
from sector_concentration_manager import SECTOR_MAP

# ── Configuration ────────────────────────────────────────────────────────────

IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", 4001))
IB_CLIENT_ID = 112  # dedicated client ID for rebalancer

# Per-sector max as fraction of NLV.
# Sectors not listed here are unconstrained.
SECTOR_LIMITS: dict[str, float] = {
    "Energy":                0.25,
    "Technology":            0.25,
    "Financials":            0.25,
    "Healthcare":            0.25,
    "Consumer Discretionary":0.25,
    "Consumer Staples":      0.25,
    "Industrials":           0.25,
    "Materials":             0.25,
    "Real Estate":           0.20,
    "Utilities":             0.20,
    "Commodities":           0.25,
}

# Don't close a position if it would take the portfolio below this minimum
# market value per name (avoids sliver positions that cost more in commissions)
MIN_POSITION_VALUE = 500.0

# Maximum number of positions to close in a single run (safety cap)
MAX_CLOSES_PER_RUN = 10

# ── Data structures ──────────────────────────────────────────────────────────

class StockPosition(NamedTuple):
    symbol: str
    sector: str
    shares: int
    market_value: float   # positive = long
    avg_cost: float
    unrealized_pnl: float
    unrealized_pct: float  # (market_value - cost_basis) / cost_basis


class OpenCall(NamedTuple):
    symbol: str
    strike: float
    expiry: str
    qty: int              # negative (short)
    avg_cost: float


# ── IB helpers ───────────────────────────────────────────────────────────────

def get_nlv(ib: IB) -> float:
    ib.reqAccountSummary()
    ib.sleep(2)
    for item in ib.accountSummary():
        if item.tag == "NetLiquidation" and item.currency == "USD":
            return float(item.value)
    for av in ib.accountValues():
        if av.tag == "NetLiquidation" and av.currency == "USD":
            return float(av.value)
    return 0.0


def get_stock_positions(ib: IB) -> list[StockPosition]:
    positions = []
    for pos in ib.positions():
        c = pos.contract
        if c.secType != "STK":
            continue
        shares = int(pos.position)
        if shares <= 0:
            continue  # long only; ignore shorts for sector reduction
        mv = float(pos.marketValue) if hasattr(pos, "marketValue") else 0.0
        if mv == 0.0:
            mv = shares * float(c.lastTradeDateOrContractMonth or 0)
        avg = float(pos.avgCost)
        cost_basis = avg * shares
        unreal = mv - cost_basis
        unreal_pct = (unreal / cost_basis * 100) if cost_basis > 0 else 0.0
        sector = SECTOR_MAP.get(c.symbol.upper(), "Unknown")
        positions.append(StockPosition(
            symbol=c.symbol,
            sector=sector,
            shares=shares,
            market_value=mv,
            avg_cost=avg,
            unrealized_pnl=unreal,
            unrealized_pct=unreal_pct,
        ))
    return positions


def get_open_calls(ib: IB) -> dict[str, list[OpenCall]]:
    """Return dict of symbol → list of open short covered calls."""
    calls: dict[str, list[OpenCall]] = defaultdict(list)
    for pos in ib.positions():
        c = pos.contract
        if c.secType == "OPT" and c.right == "C" and int(pos.position) < 0:
            calls[c.symbol].append(OpenCall(
                symbol=c.symbol,
                strike=float(c.strike),
                expiry=str(c.lastTradeDateOrContractMonth),
                qty=int(pos.position),
                avg_cost=float(pos.avgCost),
            ))
    return dict(calls)


# ── Order execution ───────────────────────────────────────────────────────────

def place_and_wait(ib: IB, contract, action: str, qty: int, label: str, dry_run: bool) -> tuple[str, float]:
    if dry_run:
        logger.info("  [DRY RUN] %s %dx %s", action, qty, label)
        return "dry_run", 0.0
    order = MarketOrder(action, qty)
    trade = ib.placeOrder(contract, order)
    ib.sleep(5)
    status = trade.orderStatus.status
    fill = trade.orderStatus.avgFillPrice
    logger.info("  %-55s  %-10s  fill=$%.2f", label, status, fill)
    return status, fill


def btc_calls_for_symbol(
    ib: IB,
    symbol: str,
    open_calls: list[OpenCall],
    dry_run: bool,
) -> list[dict]:
    """Buy to close all short calls on a symbol. Returns list of result dicts."""
    results = []
    for call in open_calls:
        qty_to_close = abs(call.qty)
        contract = Option(symbol, call.expiry, call.strike, "C", "SMART")
        ib.qualifyContracts(contract)
        ib.sleep(0.3)
        label = f"BTC {qty_to_close}x {symbol} {call.expiry} ${call.strike}C"
        status, fill = place_and_wait(ib, contract, "BUY", qty_to_close, label, dry_run)
        results.append({
            "action": "BTC",
            "symbol": symbol,
            "right": "C",
            "strike": call.strike,
            "expiry": call.expiry,
            "qty": qty_to_close,
            "status": status,
            "fill_price": fill,
            "executed_at": datetime.now().isoformat(),
        })
    return results


def sell_stock(ib: IB, symbol: str, shares: int, dry_run: bool) -> dict:
    contract = Stock(symbol, "SMART", "USD")
    ib.qualifyContracts(contract)
    ib.sleep(0.3)
    label = f"SELL {shares}x {symbol}"
    status, fill = place_and_wait(ib, contract, "SELL", shares, label, dry_run)
    return {
        "action": "SELL",
        "symbol": symbol,
        "qty": shares,
        "status": status,
        "fill_price": fill,
        "executed_at": datetime.now().isoformat(),
    }


# ── Core rebalance logic ─────────────────────────────────────────────────────

def compute_sector_exposures(
    positions: list[StockPosition],
    nlv: float,
) -> dict[str, float]:
    """Net long market value per sector as fraction of NLV."""
    totals: dict[str, float] = defaultdict(float)
    for pos in positions:
        totals[pos.sector] += pos.market_value
    return {s: mv / nlv for s, mv in totals.items()}


def sectors_over_limit(
    exposures: dict[str, float],
    target_sector: str | None = None,
) -> list[tuple[str, float, float]]:
    """Return list of (sector, current_pct, limit_pct) for over-limit sectors."""
    over = []
    for sector, limit in SECTOR_LIMITS.items():
        if target_sector and sector != target_sector:
            continue
        current = exposures.get(sector, 0.0)
        if current > limit:
            over.append((sector, current, limit))
    return sorted(over, key=lambda x: -(x[1] - x[2]))


def rank_positions_by_weakness(positions: list[StockPosition]) -> list[StockPosition]:
    """Sort positions weakest first: most negative unrealized % → smallest mv."""
    return sorted(positions, key=lambda p: (p.unrealized_pct, p.market_value))


def rebalance(
    ib: IB,
    dry_run: bool = True,
    target_sector: str | None = None,
) -> list[dict]:
    """
    Main rebalance routine. Returns list of all trade results.
    """
    nlv = get_nlv(ib)
    if nlv <= 0:
        logger.error("Could not read NLV — aborting")
        return []

    logger.info("NLV: $%,.0f  |  mode: %s", nlv, "DRY RUN" if dry_run else "LIVE")

    stock_positions = get_stock_positions(ib)
    open_calls = get_open_calls(ib)

    exposures = compute_sector_exposures(stock_positions, nlv)

    logger.info("\nCurrent sector exposures:")
    for sector, pct in sorted(exposures.items(), key=lambda x: -x[1]):
        limit = SECTOR_LIMITS.get(sector)
        flag = "  ⚠️  OVER LIMIT" if limit and pct > limit else ""
        logger.info("  %-28s  %5.1f%%  (limit %s)%s",
                    sector, pct * 100,
                    f"{limit*100:.0f}%" if limit else "—", flag)

    over = sectors_over_limit(exposures, target_sector)
    if not over:
        logger.info("\n✅ All sectors within limits — no rebalancing needed.")
        return []

    all_results: list[dict] = []
    closes_done = 0

    for sector, current_pct, limit_pct in over:
        excess_value = (current_pct - limit_pct) * nlv
        logger.info(
            "\n⚠️  %s at %.1f%% — limit %.0f%% — need to reduce by $%,.0f",
            sector, current_pct * 100, limit_pct * 100, excess_value,
        )

        sector_positions = [p for p in stock_positions if p.sector == sector]
        ranked = rank_positions_by_weakness(sector_positions)

        logger.info("  Candidates (weakest first):")
        for p in ranked:
            calls_flag = f"  [{len(open_calls.get(p.symbol, []))} calls to BTC]" if p.symbol in open_calls else ""
            logger.info("    %-8s  $%8,.0f  unreal=%+.1f%%%s",
                        p.symbol, p.market_value, p.unrealized_pct, calls_flag)

        remaining_excess = excess_value
        for pos in ranked:
            if remaining_excess <= 0:
                break
            if closes_done >= MAX_CLOSES_PER_RUN:
                logger.warning("  Max closes per run (%d) reached — stopping", MAX_CLOSES_PER_RUN)
                break
            if pos.market_value < MIN_POSITION_VALUE:
                logger.info("  Skipping %s — below minimum position value", pos.symbol)
                continue

            logger.info("\n  → Closing %s ($%,.0f, %+.1f%% unreal)",
                        pos.symbol, pos.market_value, pos.unrealized_pct)

            # BTC covered calls first
            if pos.symbol in open_calls:
                btc_results = btc_calls_for_symbol(ib, pos.symbol, open_calls[pos.symbol], dry_run)
                all_results.extend(btc_results)
                if not dry_run:
                    ib.sleep(2)

            # Sell shares
            sell_result = sell_stock(ib, pos.symbol, pos.shares, dry_run)
            all_results.append(sell_result)
            closes_done += 1

            remaining_excess -= pos.market_value
            logger.info("  Remaining excess after this close: $%,.0f", max(0, remaining_excess))

        if remaining_excess > 0:
            logger.info(
                "\n  ℹ️  Could not fully reduce %s to %.0f%% in this run "
                "(%.1f%% excess remains). Run again or adjust limits.",
                sector, limit_pct * 100, remaining_excess / nlv * 100,
            )

    return all_results


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Sector concentration rebalancer")
    parser.add_argument("--live", action="store_true",
                        help="Send real orders (default is dry-run)")
    parser.add_argument("--sector", type=str, default=None,
                        help="Only rebalance a specific sector (e.g. Energy)")
    args = parser.parse_args()

    dry_run = not args.live

    if not dry_run:
        logger.info("🔴 LIVE MODE — real orders will be placed")
    else:
        logger.info("🟡 DRY-RUN MODE — no orders will be placed (pass --live to execute)")

    ib = IB()
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=10)
        logger.info("Connected to IB Gateway")
    except Exception as e:
        logger.error("Failed to connect to IB: %s", e)
        sys.exit(1)

    try:
        results = rebalance(ib, dry_run=dry_run, target_sector=args.sector)
    finally:
        ib.disconnect()
        logger.info("Disconnected")

    if results:
        log_path = LOGS_DIR / f"rebalance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        log_path.write_text(json.dumps({
            "executed_at": datetime.now().isoformat(),
            "mode": "live" if not dry_run else "dry_run",
            "trades": results,
        }, indent=2))
        logger.info("\nResults logged to %s", log_path.name)

        filled = [r for r in results if r.get("status") == "Filled"]
        logger.info("Summary: %d/%d orders filled", len(filled), len(results))
    else:
        logger.info("No trades executed.")


if __name__ == "__main__":
    main()
