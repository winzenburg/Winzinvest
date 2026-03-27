#!/usr/bin/env python3
"""
Energy concentration trim — one-time execution.
Sells partial lots of COP, OXY, VLO to reduce sector over-allocation.

Trim plan (leaves remaining shares in place):
  COP  SELL 150 of 250  → keep 100
  OXY  SELL 150 of 250  → keep 100
  VLO  SELL  50 of 100  → keep  50
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    from ib_insync import IB, Stock, MarketOrder
except ImportError:
    print("ERROR: ib_insync not installed.")
    sys.exit(1)

# Load .env from trading dir
_TRADING_DIR = Path(__file__).resolve().parent.parent
_env_path = _TRADING_DIR / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", 4001))
TRADING_MODE = os.getenv("TRADING_MODE", "live")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(_TRADING_DIR / "logs" / "trim_energy.log"),
    ],
)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kill_switch_guard import kill_switch_active

# Shares to SELL (partial trim — not full close)
TRIM_PLAN: Dict[str, int] = {
    "COP": 150,   # 250 → 100
    "OXY": 150,   # 250 → 100
    "VLO": 50,    #  100 →  50
}


async def _verify_position(ib: IB, symbol: str, expected_min_qty: int) -> Optional[int]:
    """Confirm we hold at least expected_min_qty shares before selling."""
    for item in ib.portfolio():
        if getattr(item.contract, "symbol", "") == symbol and getattr(item.contract, "secType", "") == "STK":
            qty = int(item.position)
            if qty >= expected_min_qty:
                logger.info(
                    "%s: confirmed %d shares (avg_cost=%.4f, mkt=%.4f, uPnL=%.2f)",
                    symbol, qty, item.averageCost, item.marketPrice, item.unrealizedPNL,
                )
                return qty
            else:
                logger.error("%s: only %d shares held — need %d to trim", symbol, qty, expected_min_qty)
                return None
    logger.error("%s: not found in portfolio", symbol)
    return None


async def trim_position(ib: IB, symbol: str, sell_qty: int) -> Optional[Dict]:
    """Place a DAY market sell order and wait up to 30s for fill."""
    current_qty = await _verify_position(ib, symbol, sell_qty)
    if current_qty is None:
        return None

    contract = Stock(symbol, "SMART", "USD")
    qualified = await ib.qualifyContractsAsync(contract)
    if not qualified:
        logger.error("%s: contract qualification failed", symbol)
        return None
    contract = qualified[0]

    # SAFETY: ensure this one-off trim cannot flip a long to a short.
    # Selling up to current_qty is allowed; crossing zero is blocked.
    try:
        from pre_trade_guard import PreTradeViolation, assert_no_flip
        assert_no_flip(ib, symbol, "SELL", qty=sell_qty)
    except PreTradeViolation as e:
        logger.error("%s: trim blocked by pre_trade_guard: %s", symbol, e)
        return None
    except Exception as e:
        logger.warning("%s: pre_trade_guard unavailable or failed (%s) — proceeding without flip check", symbol, e)

    order = MarketOrder("SELL", sell_qty)
    trade = ib.placeOrder(contract, order)
    logger.info("%s: placed SELL %d (orderId=%s)", symbol, sell_qty, trade.order.orderId)

    start = datetime.now()
    while not trade.isDone():
        elapsed = (datetime.now() - start).total_seconds()
        status = trade.orderStatus.status

        # After hours: IB queues the order as PreSubmitted to execute at next open.
        # Accept this as success — do NOT cancel it.
        if status == "PreSubmitted" and elapsed >= 5:
            logger.info(
                "%s: order queued PreSubmitted (after hours) — will fill at market open. orderId=%s",
                symbol, trade.order.orderId,
            )
            return {
                "symbol": symbol,
                "action": "SELL",
                "qty_trimmed": sell_qty,
                "qty_remaining": current_qty - sell_qty,
                "fill_price": None,
                "status": "QUEUED_PRESUBMITTED",
                "timestamp": datetime.now().isoformat(),
                "order_id": trade.order.orderId,
            }

        if elapsed > 60:
            logger.error("%s: order timeout after 60s — cancelling", symbol)
            ib.cancelOrder(trade.order)
            return None
        await asyncio.sleep(0.5)

    fills = trade.fills
    if not fills:
        status = trade.orderStatus.status
        logger.error("%s: order done but no fills (status=%s)", symbol, status)
        return None

    total_shares = sum(f.execution.shares for f in fills)
    avg_price = sum(f.execution.shares * f.execution.price for f in fills) / total_shares

    result = {
        "symbol": symbol,
        "action": "SELL",
        "qty_trimmed": int(total_shares),
        "qty_remaining": current_qty - int(total_shares),
        "fill_price": round(avg_price, 4),
        "timestamp": datetime.now().isoformat(),
        "order_id": trade.order.orderId,
    }
    logger.info(
        "%s: FILLED %.0f @ %.4f  (remaining: %d shares)",
        symbol, total_shares, avg_price, result["qty_remaining"],
    )
    return result


async def run() -> None:
    if TRADING_MODE != "live":
        logger.error("TRADING_MODE=%s — refusing to run on non-live account", TRADING_MODE)
        sys.exit(1)

    logger.info("=== ENERGY TRIM — port=%d mode=%s ===", IB_PORT, TRADING_MODE)
    logger.info("Plan: COP -150, OXY -150, VLO -50")

    if kill_switch_active():
        logger.error("Kill switch is ACTIVE — energy trim aborted.")
        sys.exit(1)

    ib = IB()
    results: List[Dict] = []
    errors: List[str] = []

    for client_id in (130, 131, 132):
        try:
            await ib.connectAsync(IB_HOST, IB_PORT, clientId=client_id, timeout=15)
            logger.info("Connected with clientId=%d", client_id)
            break
        except Exception as e:
            logger.warning("clientId=%d failed: %s", client_id, e)
    else:
        logger.error("Could not connect to IB Gateway at %s:%d", IB_HOST, IB_PORT)
        sys.exit(1)

    try:
        # Allow IB to push portfolio data (streams automatically after connect)
        await asyncio.sleep(3)

        for symbol, sell_qty in TRIM_PLAN.items():
            result = await trim_position(ib, symbol, sell_qty)
            if result:
                results.append(result)
            else:
                errors.append(symbol)
            await asyncio.sleep(1)

    finally:
        ib.disconnect()

    # Summary
    logger.info("")
    logger.info("=== TRIM SUMMARY ===")
    for r in results:
        price_str = f"${r['fill_price']:.4f}" if r.get("fill_price") else "queued for open"
        logger.info("  %-6s SELL %d @ %s  → %d shares remain (%s)", r["symbol"], r["qty_trimmed"], price_str, r["qty_remaining"], r.get("status", "FILLED"))
    if errors:
        logger.warning("  FAILED: %s", ", ".join(errors))
    logger.info(
        "  %d/%d positions trimmed successfully",
        len(results), len(TRIM_PLAN),
    )

    # Write result log
    log_path = _TRADING_DIR / "logs" / "trim_energy_result.json"
    log_path.write_text(json.dumps({
        "timestamp": datetime.now().isoformat(),
        "results": results,
        "errors": errors,
    }, indent=2))
    logger.info("Results written to %s", log_path)

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
