"""
portfolio_correct.py — One-time corrective orders for doubled rebalance execution.

The rebalance script ran twice (overnight + morning), causing:
  - SELL orders to double → flipped USO/ADI/MRVL from long → unintended shorts
  - BUY-to-cover orders to double → flipped META/TSLA/etc from short → unintended longs
  - Tiny SELL orders to double → created micro short positions
"""
import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ib_insync import IB, MarketOrder, Stock, util

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            Path(__file__).parent.parent / "logs" / "portfolio_correct.log"
        ),
    ],
)
logger = logging.getLogger(__name__)

TRADING_DIR = Path(__file__).parent.parent

_env_path = TRADING_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# ── Corrective orders ─────────────────────────────────────────────────────────
# Accidentally created longs (were shorts, covered correctly, then bought again)
# → SELL to return to flat
SELL_ACCIDENTAL_LONGS: List[Dict[str, Any]] = [
    {"symbol": "META",  "qty": 200, "reason": "Accidental long from double-cover — SELL to close"},
    {"symbol": "TSLA",  "qty": 200, "reason": "Accidental long from double-cover — SELL to close"},
    {"symbol": "MSFT",  "qty": 200, "reason": "Accidental long from double-cover — SELL to close"},
    {"symbol": "AVGO",  "qty": 200, "reason": "Accidental long from double-cover — SELL to close"},
    {"symbol": "GOOGL", "qty": 200, "reason": "Accidental long from double-cover — SELL to close"},
    {"symbol": "ADBE",  "qty": 200, "reason": "Accidental long from double-cover — SELL to close"},
    {"symbol": "AMZN",  "qty": 200, "reason": "Accidental long from double-cover — SELL to close"},
    {"symbol": "NVDA",  "qty": 200, "reason": "Accidental long from double-cover — SELL to close"},
    {"symbol": "QCOM",  "qty": 200, "reason": "Accidental long from double-cover — SELL to close"},
    {"symbol": "YINN",  "qty": 200, "reason": "Accidental long from double-cover — SELL to close"},
]

# Accidentally created shorts (were longs, trim doubled → flipped short)
# → BUY to return to flat / target
BUY_ACCIDENTAL_SHORTS: List[Dict[str, Any]] = [
    {"symbol": "USO",  "qty": 3439, "reason": "Accidental short from double-trim — BUY to close"},
    {"symbol": "ADI",  "qty": 497,  "reason": "Accidental short from double-trim — BUY to close"},
    {"symbol": "MRVL", "qty": 1319, "reason": "Accidental short from double-trim — BUY to close"},
]

# Micro shorts from double tiny-position cleanup → BUY to close
BUY_MICRO_SHORTS: List[Dict[str, Any]] = [
    {"symbol": "AMAT", "qty": 4, "reason": "Micro short from double-sell — BUY to close"},
    {"symbol": "LRCX", "qty": 4, "reason": "Micro short from double-sell — BUY to close"},
    {"symbol": "MRNA", "qty": 4, "reason": "Micro short from double-sell — BUY to close"},
    {"symbol": "WBD",  "qty": 4, "reason": "Micro short from double-sell — BUY to close"},
    {"symbol": "ASML", "qty": 4, "reason": "Micro short from double-sell — BUY to close"},
    {"symbol": "REM",  "qty": 5, "reason": "Micro short from double-sell — BUY to close"},
]

# ── Order helper ──────────────────────────────────────────────────────────────
async def place_order(
    ib: IB,
    symbol: str,
    action: str,
    qty: int,
    reason: str,
) -> Tuple[bool, str]:
    contract = Stock(symbol, "SMART", "USD")
    try:
        await ib.qualifyContractsAsync(contract)
    except Exception as e:
        msg = f"FAILED to qualify {symbol}: {e}"
        logger.error(msg)
        return False, msg

    order = MarketOrder(action, qty)
    order.outsideRth = False
    order.tif = "DAY"

    trade = ib.placeOrder(contract, order)
    # Wait up to 15 s for status update
    deadline = asyncio.get_event_loop().time() + 15
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.5)
        status = trade.orderStatus.status
        if status in ("PreSubmitted", "Submitted", "Filled"):
            break

    status = trade.orderStatus.status
    order_id = trade.order.orderId
    msg = (
        f"QUEUED {action} {qty} {symbol} (order #{order_id}, status={status}) "
        f"— {reason}"
    )
    logger.info(msg)
    return True, msg


# ── Main ──────────────────────────────────────────────────────────────────────
async def run() -> None:
    ib = IB()
    logger.info("=" * 70)
    logger.info("PORTFOLIO CORRECTION — fixing doubled rebalance execution")
    logger.info("=" * 70)

    for attempt in range(3):
        try:
            await ib.connectAsync(os.getenv("IB_HOST", "127.0.0.1"), int(os.getenv("IB_PORT", "4001")), clientId=125)
            logger.info("Connected with clientId=125")
            break
        except Exception as e:
            if attempt == 2:
                logger.error("Cannot connect to IB after 3 attempts: %s", e)
                return
            await asyncio.sleep(5)

    successes = 0
    failures = 0
    results = []

    logger.info("--- SELL accidental longs (were shorts, over-covered) ---")
    for entry in SELL_ACCIDENTAL_LONGS:
        ok, msg = await place_order(ib, entry["symbol"], "SELL", entry["qty"], entry["reason"])
        (successes if ok else failures).__class__  # noqa
        if ok:
            successes += 1
        else:
            failures += 1
        results.append(msg)
        await asyncio.sleep(1)

    logger.info("--- BUY to close accidental shorts (longs over-trimmed) ---")
    for entry in BUY_ACCIDENTAL_SHORTS:
        ok, msg = await place_order(ib, entry["symbol"], "BUY", entry["qty"], entry["reason"])
        if ok:
            successes += 1
        else:
            failures += 1
        results.append(msg)
        await asyncio.sleep(1)

    logger.info("--- BUY to close micro shorts (tiny positions over-sold) ---")
    for entry in BUY_MICRO_SHORTS:
        ok, msg = await place_order(ib, entry["symbol"], "BUY", entry["qty"], entry["reason"])
        if ok:
            successes += 1
        else:
            failures += 1
        results.append(msg)
        await asyncio.sleep(1)

    logger.info("=" * 70)
    logger.info(
        "CORRECTION COMPLETE: %d succeeded, %d failed out of %d orders",
        successes, failures, successes + failures,
    )
    logger.info("=" * 70)
    for r in results:
        logger.info("  %s", r)

    summary = {
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        "total_orders": successes + failures,
        "successes": successes,
        "failures": failures,
        "orders": results,
    }
    summary_path = TRADING_DIR / "logs" / "correction_summary.json"
    fd, tmp = tempfile.mkstemp(suffix=".json", dir=str(TRADING_DIR / "logs"))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(summary, f, indent=2)
        os.replace(tmp, str(summary_path))
    except OSError:
        if os.path.exists(tmp):
            os.unlink(tmp)

    ib.disconnect()


if __name__ == "__main__":
    asyncio.run(run())
