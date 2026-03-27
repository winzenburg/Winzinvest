#!/usr/bin/env python3
"""
Trim Oversized Positions

Scans the live IBKR portfolio for positions that exceed a configured NLV
percentage cap (default 7 %).  For each oversized name it:

  • Calculates the trim qty needed to bring the position back to the target.
  • Places a direct market order via IBKR to execute the trim immediately.
  • Logs every action to logs/trim_oversized.log.

Safe-guards:
  - Min trim qty: 1 share (never rounds to 0)
  - Will NOT trim TZA/SQQQ/SPXU hedge ETFs
  - Will NOT trim options positions
  - Dry-run mode (--dry-run) prints the plan without placing orders

Usage:
    python3 trim_oversized_positions.py            # live trim
    python3 trim_oversized_positions.py --dry-run  # preview only
    python3 trim_oversized_positions.py --max-pct 0.08  # different threshold
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

_scripts_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_scripts_dir))

from paths import TRADING_DIR

_env_path = TRADING_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

LOG_DIR = TRADING_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "trim_oversized.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

IB_HOST   = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT   = int(os.getenv("IB_PORT", "4001"))
CLIENT_ID = 134   # dedicated client ID for trim script

SKIP_SYMBOLS: set[str] = {"TZA", "SQQQ", "SPXU", "SDOW", "SPXS", "UVXY", "VXX"}

# Positions whose trim qty would be ≤ this many shares are skipped (too small to bother)
MIN_TRIM_SHARES = 2


def _connect_ib() -> "ib_insync.IB":
    import ib_insync  # type: ignore[import]
    ib = ib_insync.IB()
    for cid in [CLIENT_ID, CLIENT_ID + 1, CLIENT_ID + 2]:
        try:
            ib.connect(IB_HOST, IB_PORT, clientId=cid, timeout=10, readonly=False)
            logger.info("Connected to IBKR at %s:%s (clientId=%s)", IB_HOST, IB_PORT, cid)
            return ib
        except Exception as exc:
            logger.warning("clientId %s failed: %s", cid, exc)
    raise RuntimeError("Could not connect to IBKR — is TWS/IBG running and API enabled?")


def _get_nlv(ib: "ib_insync.IB") -> float:
    import ib_insync
    vals = ib.accountValues()
    for v in vals:
        if v.tag == "NetLiquidation" and v.currency == "USD":
            return float(v.value)
    raise RuntimeError("Could not read NetLiquidation from account")


def _get_portfolio(ib: "ib_insync.IB") -> list[dict]:
    """Return list of stock positions with symbol, qty, market_value, avg_cost."""
    positions = []
    for item in ib.portfolio():
        contract = item.contract
        if getattr(contract, "secType", "") != "STK":
            continue
        sym = getattr(contract, "symbol", "")
        if not sym or sym in SKIP_SYMBOLS:
            continue
        positions.append({
            "symbol": sym,
            "qty": int(item.position),
            "market_value": float(item.marketValue),
            "avg_cost": float(item.averageCost),
            "last_price": abs(float(item.marketValue) / int(item.position)) if item.position else 0.0,
            "contract": contract,
        })
    return positions


def _build_trim_plan(portfolio: list[dict], nlv: float, max_pct: float) -> list[dict]:
    """Return list of trim actions needed to bring all positions under max_pct."""
    plan = []
    limit = nlv * max_pct
    for pos in portfolio:
        mv = abs(pos["market_value"])
        pct = mv / nlv * 100
        if mv <= limit:
            continue  # already within limit
        price = pos["last_price"]
        if price <= 0:
            logger.warning("Skipping %s — no price data", pos["symbol"])
            continue
        qty = pos["qty"]
        side = "LONG" if qty > 0 else "SHORT"

        # shares at target allocation
        target_shares = int(limit / price)
        trim_qty = abs(qty) - target_shares
        if trim_qty < MIN_TRIM_SHARES:
            logger.info(
                "%s: trim_qty=%d < minimum %d — skipping", pos["symbol"], trim_qty, MIN_TRIM_SHARES
            )
            continue

        action = "SELL" if side == "LONG" else "BUY"  # BUY to cover a short
        plan.append({
            "symbol": pos["symbol"],
            "side": side,
            "action": action,
            "trim_qty": trim_qty,
            "current_qty": qty,
            "target_qty": target_shares if side == "LONG" else -target_shares,
            "current_pct": round(pct, 1),
            "target_pct": round(max_pct * 100, 1),
            "price": price,
            "trim_notional": round(trim_qty * price, 2),
            "contract": pos["contract"],
        })
    return plan


def _place_trim_order(ib: "ib_insync.IB", item: dict, dry_run: bool) -> bool:
    """Place a market order for the trim. Returns True on success."""
    import ib_insync
    sym = item["symbol"]
    action = item["action"]
    qty = item["trim_qty"]
    contract = item["contract"]
    side = item["side"]  # "LONG" or "SHORT"

    if dry_run:
        logger.info(
            "[DRY-RUN] Would %s %d %s @ ~$%.2f  (%.1f%% NLV → %.1f%% NLV)",
            action, qty, sym, item["price"], item["current_pct"], item["target_pct"],
        )
        return True

    # SAFETY: verify this trim does not accidentally flip the position direction.
    # Trimming a long (SELL qty <= held shares) and covering a short (BUY qty <= held short)
    # are both fine. Only crossing zero is forbidden. assert_no_flip enforces this at the IB
    # level when given the order side and quantity.
    try:
        from pre_trade_guard import PreTradeViolation, assert_no_flip
        intended_side = "SELL" if action.upper() == "SELL" else "BUY"
        assert_no_flip(ib, sym, intended_side, qty=qty)
    except PreTradeViolation as e:
        logger.error("TRIM BLOCKED by pre-trade guard for %s: %s", sym, e)
        return False
    except ImportError:
        logger.warning("pre_trade_guard not available — skipping flip check for %s", sym)

    # Portfolio contracts from ib.portfolio() lack exchange; IBKR requires exchange="SMART"
    order_contract = ib_insync.Stock(
        conId=contract.conId,
        symbol=contract.symbol,
        exchange="SMART",
        currency=contract.currency,
    )
    ib.qualifyContracts(order_contract)

    order = ib_insync.MarketOrder(action=action, totalQuantity=qty, tif="DAY")
    try:
        trade = ib.placeOrder(order_contract, order)
        ib.sleep(1.0)
        logger.info(
            "PLACED: %s %d %s — order status: %s",
            action, qty, sym, trade.orderStatus.status,
        )
        return True
    except Exception as exc:
        logger.error("Failed to place %s %d %s: %s", action, qty, sym, exc)
        return False


def _default_max_pct() -> float:
    """Read max_position_pct_of_equity from risk.json (long side), default 0.07."""
    try:
        from risk_config import get_max_position_pct_of_equity
        return get_max_position_pct_of_equity(TRADING_DIR, side="long")
    except Exception:
        return 0.07


def run(max_pct: float | None = None, dry_run: bool = False) -> None:
    if max_pct is None:
        max_pct = _default_max_pct()
    logger.info("=== Trim Oversized Positions (max_pct=%.0f%%, dry_run=%s) ===",
                max_pct * 100, dry_run)

    ib = _connect_ib()
    try:
        nlv = _get_nlv(ib)
        logger.info("NLV: $%s | Cap per position: $%s (%.0f%%)",
                    f"{nlv:,.2f}", f"{nlv * max_pct:,.2f}", max_pct * 100)

        portfolio = _get_portfolio(ib)
        logger.info("Portfolio: %d stock positions", len(portfolio))

        plan = _build_trim_plan(portfolio, nlv, max_pct)

        if not plan:
            logger.info("No positions exceed %.0f%% NLV — nothing to trim.", max_pct * 100)
            return

        logger.info("Trim plan: %d position(s) to reduce:", len(plan))
        for item in plan:
            logger.info(
                "  %s [%s] qty %d → %d | %.1f%% → %.1f%% NLV | trim %d shares @ ~$%.2f (≈$%s)",
                item["symbol"], item["side"], item["current_qty"], item["target_qty"],
                item["current_pct"], item["target_pct"],
                item["trim_qty"], item["price"], f"{item['trim_notional']:,.0f}",
            )

        placed, failed = 0, 0
        for item in plan:
            ok = _place_trim_order(ib, item, dry_run)
            if ok:
                placed += 1
            else:
                failed += 1
            time.sleep(0.5)

        status = "DRY-RUN" if dry_run else "LIVE"
        logger.info("[%s] Trim complete: %d placed, %d failed.", status, placed, failed)

    finally:
        ib.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trim oversized positions to NLV cap")
    parser.add_argument("--max-pct", type=float, default=None,
                        help="Max allowed position size as fraction of NLV (reads risk.json if omitted)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the trim plan without placing any orders")
    args = parser.parse_args()
    run(max_pct=args.max_pct, dry_run=args.dry_run)
