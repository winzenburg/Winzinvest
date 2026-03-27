#!/usr/bin/env python3
"""
Replace PreSubmitted TRAIL Orders

Finds every GTC TRAIL SELL order stuck in PreSubmitted status (caused by the
old OCA-group bug), cancels it, then places a fresh independent TRAIL stop
using the same ATR multipliers as retrofit_trailing_stops.py.

The paired LMT take-profit (Submitted) is left untouched — it is already
active on the exchange and does not need replacing.

Safe to re-run — only PreSubmitted TRAIL orders are touched.
"""
from __future__ import annotations

import logging
import math
import os
import sys
import time
from pathlib import Path
from typing import Optional

_scripts_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_scripts_dir))

from paths import TRADING_DIR

_env_path = TRADING_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

IB_HOST   = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT   = int(os.getenv("IB_PORT", "4001"))
CLIENT_ID = 133   # dedicated — avoids conflict with retrofit (132) or scheduler

TRAILING_ATR_MULT  = 3.0
FALLBACK_TRAIL_PCT = 0.025   # 2.5% fallback when ATR unavailable


def run() -> None:
    try:
        from ib_insync import IB, Order, Stock  # type: ignore[import]
        import logging as _log
        _log.getLogger("ib_insync").setLevel(_log.CRITICAL)
    except ImportError:
        logger.error("ib_insync not installed")
        sys.exit(1)

    from atr_stops import fetch_atr, compute_trailing_amount

    ib = IB()
    for port in [IB_PORT, 4001, 7496, 7497]:
        try:
            ib.connect(IB_HOST, port, clientId=CLIENT_ID, timeout=15)
            logger.info("Connected on port %d (clientId=%d)", port, CLIENT_ID)
            break
        except Exception:
            continue
    else:
        logger.error("Could not connect to IBKR")
        sys.exit(1)

    try:
        # ── Step 1: collect all PreSubmitted TRAIL SELL GTC orders ────────────
        ib.reqAllOpenOrders()
        ib.sleep(2)

        presubmitted: list[tuple[str, int, object, object]] = []  # (symbol, qty, contract, trade)
        for trade in ib.openTrades():
            o  = trade.order
            st = trade.orderStatus.status
            if (
                st == "PreSubmitted"
                and getattr(o, "action",    "").upper() == "SELL"
                and getattr(o, "orderType", "").upper() == "TRAIL"
                and getattr(o, "tif",       "").upper() == "GTC"
            ):
                sym = trade.contract.symbol.upper()
                qty = int(o.totalQuantity)
                presubmitted.append((sym, qty, trade.contract, trade))
                logger.info("  Found PreSubmitted TRAIL — %s qty=%d orderId=%s",
                            sym, qty, o.orderId)

        if not presubmitted:
            logger.info("No PreSubmitted TRAIL orders found — nothing to replace.")
            return

        logger.info("\nWill cancel + replace %d PreSubmitted TRAIL order(s)", len(presubmitted))

        # ── Step 2: get current positions for qty validation ──────────────────
        pos_map: dict[str, int] = {
            p.contract.symbol.upper(): int(p.position)
            for p in ib.positions()
            if p.contract.secType == "STK" and p.position > 0
        }

        placed, failed = [], []

        for sym, _order_qty, contract, trade in presubmitted:
            logger.info("\n── %s ──────────────────────────", sym)

            # Use live position qty, fall back to order qty
            qty = pos_map.get(sym, _order_qty)
            if qty <= 0:
                logger.warning("  %s: no long position found — skipping cancel+replace", sym)
                failed.append(sym)
                continue

            # Cancel the PreSubmitted TRAIL
            try:
                ib.cancelOrder(trade.order)  # type: ignore[attr-defined]
                logger.info("  %s: cancel request sent for orderId=%s", sym, trade.order.orderId)
                ib.sleep(1.5)   # let IB process the cancel
            except Exception as exc:
                logger.error("  %s: cancel failed: %s — skipping replacement", sym, exc)
                failed.append(sym)
                continue

            # ── Fetch live price ──────────────────────────────────────────────
            last_price: Optional[float] = None
            try:
                qualified = ib.qualifyContracts(Stock(sym, "SMART", "USD"))
                if qualified:
                    ticker = ib.reqMktData(qualified[0], "", True, False)
                    ib.sleep(2)
                    for raw in (ticker.last, ticker.close, ticker.bid, ticker.ask):
                        if raw is not None and not math.isnan(float(raw)) and float(raw) > 0:
                            last_price = float(raw)
                            break
                    ib.cancelMktData(qualified[0])
            except Exception as exc:
                logger.warning("  %s: IB price failed (%s) — trying yfinance", sym, exc)

            if not last_price or last_price <= 0:
                try:
                    import yfinance as _yf
                    df = _yf.download(sym, period="1d", interval="1m", progress=False)
                    if df is not None and not df.empty:
                        last_price = float(df["Close"].iloc[-1].item())
                except Exception as exc2:
                    logger.warning("  %s: yfinance also failed: %s", sym, exc2)

            if not last_price or last_price <= 0:
                logger.error("  %s: no price — TRAIL cancelled but replacement NOT placed", sym)
                failed.append(sym)
                continue

            # ── Fetch ATR ─────────────────────────────────────────────────────
            atr = fetch_atr(sym)
            trail_amt = compute_trailing_amount(
                atr=atr,
                entry_price=last_price,
                trailing_mult=TRAILING_ATR_MULT,
                fallback_pct=FALLBACK_TRAIL_PCT,
            )

            if not trail_amt or math.isnan(trail_amt) or trail_amt <= 0:
                logger.error("  %s: trail_amt invalid (%.4f) — skipping placement", sym, trail_amt or 0)
                failed.append(sym)
                continue

            approx_stop = round(last_price - trail_amt, 2)
            logger.info(
                "  %s: last=$%.2f  trail=$%.2f  ≈stop=$%.2f  atr=%s",
                sym, last_price, trail_amt, approx_stop,
                f"{atr:.2f}" if atr else "fallback",
            )

            # ── Place fresh independent TRAIL ─────────────────────────────────
            try:
                qualified = ib.qualifyContracts(Stock(sym, "SMART", "USD"))
                if not qualified:
                    raise RuntimeError("qualify returned empty")
                fresh_trail = Order(
                    action="SELL",
                    totalQuantity=qty,
                    orderType="TRAIL",
                    auxPrice=trail_amt,
                    tif="GTC",
                    outsideRth=False,
                )
                ib.placeOrder(qualified[0], fresh_trail)
                ib.sleep(1.0)
                logger.info("  %s: ✅ fresh TRAIL placed (trail=$%.2f ≈stop=$%.2f)", sym, trail_amt, approx_stop)
                placed.append(sym)
            except Exception as exc:
                logger.error("  %s: placement failed: %s", sym, exc)
                failed.append(sym)

            time.sleep(1.0)   # polite pause between symbols

    finally:
        ib.disconnect()
        logger.info("\nDisconnected from IBKR")

    logger.info("\n═══ REPLACEMENT COMPLETE ═══")
    logger.info("  Replaced: %d  %s", len(placed), placed)
    logger.info("  Failed:   %d  %s", len(failed), failed)
    if failed:
        logger.warning("Failed symbols — check logs and retry or place manually in TWS.")


if __name__ == "__main__":
    run()
