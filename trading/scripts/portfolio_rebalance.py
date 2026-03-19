#!/usr/bin/env python3
"""
One-time portfolio rebalance: close positions that don't match strategy,
trim oversized positions to 5% of NLV.

Orders are MKT with outsideRth=False so they queue for next market open
if placed after hours.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ib_insync import IB, Stock, MarketOrder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            Path(__file__).resolve().parent.parent / "logs" / "portfolio_rebalance.log"
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

from paths import TRADING_DIR

MAX_POSITION_PCT = 0.05
# Fallback NLV only if account summary is unavailable (logged when used)
NLV_FALLBACK = 170_917.72

CLOSE_LONGS: List[Dict[str, Any]] = []

TRIM_LONGS: List[Dict[str, Any]] = []

NEW_LONGS: List[Dict[str, Any]] = [
    {"symbol": "DELL", "qty": 50,  "reason": "Non-energy diversifier (tech), score 0.582, strong RS bounce, 7x RVOL"},
    {"symbol": "MASI", "qty": 45,  "reason": "Non-energy diversifier (healthcare tech), score 0.571, RS=0.340"},
    {"symbol": "LYB",  "qty": 100, "reason": "Sector breakout (chemicals), score 0.621, commodity-adjacent diversifier"},
]

CLOSE_SHORTS: List[Dict[str, Any]] = []
TRIM_SHORTS: List[Dict[str, Any]] = []
CLOSE_TINY_LONGS: List[Dict[str, Any]] = []
CLOSE_TINY_SHORTS: List[Dict[str, Any]] = []


async def place_order(
    ib: IB, symbol: str, action: str, qty: int, reason: str
) -> Tuple[bool, str]:
    """Place a MKT order. Returns (success, status_message)."""
    try:
        contract = Stock(symbol, "SMART", "USD")
        qualified = await ib.qualifyContractsAsync(contract)
        if not qualified:
            msg = f"FAILED to qualify {symbol}"
            logger.error(msg)
            return False, msg
        contract = qualified[0]

        order = MarketOrder(action, qty)
        order.outsideRth = False
        order.tif = "DAY"

        trade = ib.placeOrder(contract, order)

        for _ in range(30):
            await asyncio.sleep(0.5)
            if trade.isDone():
                break

        status = trade.orderStatus.status
        fill_price = float(trade.orderStatus.avgFillPrice or 0)
        order_id = trade.order.orderId

        if status in ("Filled", "PartiallyFilled"):
            filled = int(trade.orderStatus.filled or qty)
            msg = (
                f"FILLED {action} {filled} {symbol} @ ${fill_price:.2f} "
                f"(order #{order_id}) — {reason}"
            )
            logger.info(msg)
            return True, msg
        if status in ("PreSubmitted", "Submitted"):
            msg = (
                f"QUEUED (not filled) {action} {qty} {symbol} (order #{order_id}, status={status}) "
                f"— {reason}"
            )
            logger.warning(msg)
            return False, msg
        else:
            msg = f"UNEXPECTED status for {action} {qty} {symbol}: {status} (order #{order_id})"
            logger.warning(msg)
            return False, msg

    except Exception as e:
        msg = f"ERROR placing {action} {qty} {symbol}: {e}"
        logger.error(msg)
        return False, msg


async def _fetch_net_liquidity(ib: IB) -> float:
    """Read NetLiquidation from IB account summary; fall back to NLV_FALLBACK."""
    try:
        ib.reqAccountSummary()
        await asyncio.sleep(2.0)
        for row in ib.accountSummary():
            if getattr(row, "tag", "") == "NetLiquidation" and getattr(row, "currency", "USD") in (
                "USD",
                "",
            ):
                return float(row.value)
    except Exception as exc:
        logger.warning("Could not read NetLiquidation from IB: %s — using fallback", exc)
    return NLV_FALLBACK


async def run() -> None:
    import os as _os

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from env_loader import load_env as _load_env
    from kill_switch_guard import kill_switch_active

    _load_env()

    ib_host = _os.getenv("IB_HOST", "127.0.0.1")
    ib_port = int(_os.getenv("IB_PORT", "4001"))
    mode = _os.getenv("TRADING_MODE", "paper")

    logger.info("=" * 70)
    logger.info("PORTFOLIO REBALANCE [%s] — %s", mode.upper(), datetime.now().isoformat())
    logger.info("=" * 70)

    if kill_switch_active():
        logger.error("Kill switch is ACTIVE — portfolio rebalance aborted.")
        return

    ib = IB()
    try:
        await ib.connectAsync(ib_host, ib_port, clientId=120, timeout=60)
    except Exception as e:
        logger.error("Connection failed: %s", e)
        return

    try:
        nlv = await _fetch_net_liquidity(ib)
        max_notional = nlv * MAX_POSITION_PCT
        logger.info("NLV (from IB or fallback)=$%.2f  max position (5%%)=$%.2f", nlv, max_notional)

        live_positions: Dict[str, float] = {}
        try:
            await ib.reqPositionsAsync()
            await asyncio.sleep(2)
            for pos in ib.positions():
                live_positions[pos.contract.symbol] = pos.position
            logger.info("Live positions loaded: %d symbols", len(live_positions))
        except Exception as e:
            logger.error("Could not load live positions — aborting to avoid double-orders: %s", e)
            return

        results: List[str] = []
        successes = 0
        failures = 0

        # 1. Close no-signal longs (SELL all)
        logger.info("--- CLOSING NO-SIGNAL LONGS ---")
        for entry in CLOSE_LONGS:
            sym = entry["symbol"]
            live_pos = live_positions.get(sym, 0)
            if live_pos <= 0:
                msg = f"SKIP {sym}: position is {live_pos} (not long) — already sold or never held"
                logger.info(msg)
                results.append(msg)
                continue
            sell_qty = min(entry["qty"], int(live_pos))
            ok, msg = await place_order(ib, sym, "SELL", sell_qty, entry["reason"])
            results.append(msg)
            if ok:
                successes += 1
            else:
                failures += 1
            await asyncio.sleep(0.5)

        # 2. Trim oversized longs (SELL partial)
        logger.info("--- TRIMMING OVERSIZED LONGS ---")
        for entry in TRIM_LONGS:
            sym = entry["symbol"]
            live_pos = live_positions.get(sym, 0)
            if live_pos <= entry["keep_qty"]:
                msg = f"SKIP {sym}: position is {live_pos} (already at/below target {entry['keep_qty']})"
                logger.info(msg)
                results.append(msg)
                continue
            sell_qty = int(live_pos) - entry["keep_qty"]
            ok, msg = await place_order(ib, sym, "SELL", sell_qty, entry["reason"])
            results.append(msg)
            if ok:
                successes += 1
            else:
                failures += 1
            await asyncio.sleep(0.5)

        # 3. Open new long positions (BUY)
        logger.info("--- OPENING NEW LONG POSITIONS ---")
        for entry in NEW_LONGS:
            sym = entry["symbol"]
            live_pos = live_positions.get(sym, 0)
            if live_pos > 0:
                msg = f"SKIP {sym}: already long {live_pos} shares"
                logger.info(msg)
                results.append(msg)
                continue
            ok, msg = await place_order(ib, sym, "BUY", entry["qty"], entry["reason"])
            results.append(msg)
            if ok:
                successes += 1
            else:
                failures += 1
            await asyncio.sleep(0.5)

        # Summary
        logger.info("=" * 70)
        logger.info(
            "REBALANCE COMPLETE: %d succeeded, %d failed out of %d orders",
            successes,
            failures,
            len(results),
        )
        logger.info("=" * 70)
        for r in results:
            logger.info("  %s", r)

        summary = {
            "timestamp": datetime.now().isoformat(),
            "nlv_used": round(nlv, 2),
            "max_notional_5pct": round(max_notional, 2),
            "total_orders": len(results),
            "successes": successes,
            "failures": failures,
            "orders": results,
        }
        summary_path = TRADING_DIR / "logs" / "rebalance_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2))
        logger.info("Summary written to %s", summary_path)
    finally:
        ib.disconnect()


if __name__ == "__main__":
    asyncio.run(run())
