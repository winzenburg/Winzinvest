#!/usr/bin/env python3
"""
Retrofit Trailing Stops — one-time run for existing positions.

Places a GTC TRAIL stop (3.0× ATR) + independent GTC limit take-profit (3.5× ATR)
for every long stock position currently held in IBKR that does NOT already have
an open stop or TP order.

Run once during market hours after the ATR stops in pending_trades.json are set:

    python3 trading/scripts/retrofit_trailing_stops.py

Re-running is safe — existing open stops/TPs are detected and skipped.

Design notes
------------
TRAIL and LMT are placed as *independent* GTC orders, NOT inside an OCA group.
IB's OCA implementation with TRAIL orders is unreliable: the TRAIL partner stays
"PreSubmitted" indefinitely when paired with a LMT inside the same OCA group,
meaning it never reaches the exchange and cannot fire.  By placing them
independently both orders are immediately "Submitted" (active).  If the TP limit
fills first the trailing stop remains open as a harmless resting sell order; the
user should cancel it manually or let update_atr_stops.py clean it up next run.

Why native IB orders instead of soft stops?
  Soft stops (price_below in pending_trades.json) are checked once per day at
  market open. A TRAIL in IBKR tracks the high-water mark tick-by-tick and fires
  at the exact threshold — it does not rely on the scheduler or a snapshot price.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

# ── path bootstrap ────────────────────────────────────────────────────────────
_scripts_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_scripts_dir))

from paths import TRADING_DIR

_env_path = TRADING_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# ── logging ───────────────────────────────────────────────────────────────────
LOG_DIR = TRADING_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "retrofit_trailing_stops.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ── IBKR connection params ────────────────────────────────────────────────────
IB_HOST   = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT   = int(os.getenv("IB_PORT", "4001"))
CLIENT_ID = 132   # dedicated client ID — avoids conflicts with scheduler/executor

# ── ATR multipliers (must match atr_stops.py defaults) ───────────────────────
TRAILING_ATR_MULT = 3.0
TP_ATR_MULT       = 3.5
FALLBACK_TRAIL_PCT = 0.025   # 2.5% if ATR unavailable
FALLBACK_TP_PCT    = 0.10    # 10% if ATR unavailable

# Symbols to skip (hedges, ETFs, or positions already managed elsewhere)
SKIP_SYMBOLS = {"TZA", "SQQQ", "SPXU"}


def _fetch_open_stop_symbols(ib: object) -> set[str]:
    """Return set of symbols that already have an open GTC stop or TP order in IB.

    Uses reqAllOpenOrders() so we see orders placed by ALL clientIds (e.g.
    update_atr_stops.py uses clientId 129/130).  ib.trades() only returns orders
    from the current session and would falsely show every position as unprotected.
    Caller must have already called ib.reqAllOpenOrders() + sleep before this.
    """
    open_stops: set[str] = set()
    try:
        trades = ib.openTrades()  # type: ignore[attr-defined]  — populated by reqAllOpenOrders
        for t in trades:
            order = t.order
            status = t.orderStatus.status
            if status in ("Submitted", "PreSubmitted"):
                action = getattr(order, "action", "").upper()
                order_type = getattr(order, "orderType", "").upper()
                tif = getattr(order, "tif", "").upper()
                sym = (t.contract.symbol or "").upper()
                if action == "SELL" and tif == "GTC" and order_type in (
                    "TRAIL", "LMT", "STP", "STP LMT"
                ):
                    open_stops.add(sym)
                    logger.info(
                        "  %s already has open GTC SELL order (%s %s) — will skip",
                        sym, order_type, status,
                    )
    except Exception as exc:
        logger.warning("Could not check open orders: %s", exc)
    return open_stops


def _place_trailing_stop_and_tp(
    ib: object,
    symbol: str,
    qty: int,
    last_price: float,
    atr: Optional[float],
) -> bool:
    """Place independent GTC TRAIL stop + GTC limit TP for a long position.

    Orders are placed as *separate, independent* GTC orders — NOT in an OCA group.
    IB's OCA implementation with TRAIL orders keeps the TRAIL in "PreSubmitted"
    indefinitely when paired with a LMT inside the same OCA group, meaning it
    never reaches the exchange.  Independent orders are both immediately "Submitted".

    Returns True on success, False on error.
    """
    import math
    from ib_insync import Stock, Order, LimitOrder  # type: ignore[import]
    from atr_stops import compute_stop_tp, compute_trailing_amount

    trail_amt = compute_trailing_amount(
        atr=atr, entry_price=last_price, trailing_mult=TRAILING_ATR_MULT,
        fallback_pct=FALLBACK_TRAIL_PCT,
    )
    _stop_px, tp_px = compute_stop_tp(
        entry_price=last_price,
        side="BUY",
        atr=atr,
        stop_mult=TRAILING_ATR_MULT,
        tp_mult=TP_ATR_MULT,
        fallback_stop_pct=FALLBACK_TRAIL_PCT,
        fallback_tp_pct=FALLBACK_TP_PCT,
    )
    approx_stop = round(last_price - trail_amt, 2)

    # SAFETY: validate computed values before placing any order
    if not trail_amt or math.isnan(trail_amt) or trail_amt <= 0:
        logger.error("  %s: trail_amt invalid (%.4f) — skipping", symbol, trail_amt)
        return False
    if not tp_px or math.isnan(tp_px) or tp_px <= last_price:
        logger.error(
            "  %s: tp_px invalid or not above last_price (tp=%.2f, last=%.2f) — "
            "placing TRAIL only, no TP", symbol, tp_px or 0, last_price,
        )
        tp_px = None  # will skip TP placement below

    logger.info(
        "  %s: qty=%d  last=$%.2f  trail=$%.2f (≈stop $%.2f)  tp=%s  [atr=%s]",
        symbol, qty, last_price, trail_amt, approx_stop,
        f"${tp_px:.2f}" if tp_px else "skipped",
        f"{atr:.2f}" if atr else "fallback",
    )

    stk = Stock(symbol, "SMART", "USD")
    try:
        qualified = ib.qualifyContracts(stk)  # type: ignore[attr-defined]
        if not qualified:
            logger.error("  %s: qualify failed — skipping", symbol)
            return False
        contract = qualified[0]
    except Exception as exc:
        logger.error("  %s: qualify error: %s — skipping", symbol, exc)
        return False

    # ── Place TRAIL stop (independent — no OCA group) ─────────────────────────
    trail_order = Order(
        action="SELL",
        totalQuantity=qty,
        orderType="TRAIL",
        auxPrice=trail_amt,
        tif="GTC",
        outsideRth=False,
    )

    try:
        ib.placeOrder(contract, trail_order)   # type: ignore[attr-defined]
        ib.sleep(0.75)                         # type: ignore[attr-defined]
    except Exception as exc:
        logger.error("  %s: TRAIL order placement error: %s", symbol, exc)
        return False

    # ── Place TP limit (independent — no OCA group) ───────────────────────────
    if tp_px is not None:
        tp_order = LimitOrder("SELL", qty, tp_px)
        tp_order.tif        = "GTC"
        tp_order.outsideRth = False
        try:
            ib.placeOrder(contract, tp_order)  # type: ignore[attr-defined]
            ib.sleep(0.75)                     # type: ignore[attr-defined]
            logger.info(
                "  %s: ✅ placed TRAIL (trail=$%.2f ≈stop $%.2f) + TP LMT ($%.2f)",
                symbol, trail_amt, approx_stop, tp_px,
            )
        except Exception as exc:
            # TRAIL already placed — log TP failure but don't mark position as failed
            logger.warning(
                "  %s: TRAIL placed but TP LMT failed: %s — TRAIL alone is active",
                symbol, exc,
            )
    else:
        logger.info(
            "  %s: ✅ placed TRAIL only (trail=$%.2f ≈stop $%.2f) — TP skipped",
            symbol, trail_amt, approx_stop,
        )

    return True


def run() -> None:
    try:
        from ib_insync import IB  # type: ignore[import]
        import logging as _logging
        _logging.getLogger("ib_insync").setLevel(_logging.CRITICAL)
    except ImportError:
        logger.error("ib_insync not installed — cannot place trailing stops")
        sys.exit(1)

    from atr_stops import fetch_atr

    ib = IB()
    ports_to_try = [IB_PORT, 4001, 7496, 7497]
    connected = False
    for port in ports_to_try:
        try:
            ib.connect(IB_HOST, port, clientId=CLIENT_ID, timeout=15)
            logger.info("Connected to IBKR on port %d (clientId=%d)", port, CLIENT_ID)
            connected = True
            break
        except Exception:
            continue

    if not connected:
        logger.error("Could not connect to IBKR on any port: %s", ports_to_try)
        sys.exit(1)

    try:
        logger.info("=== Retrofit Trailing Stops — %s ===", __import__("datetime").date.today())

        # 1. Get all current stock positions
        positions = [
            p for p in ib.positions()  # type: ignore[attr-defined]
            if p.contract.secType == "STK" and p.position > 0
        ]
        if not positions:
            logger.info("No long stock positions found — nothing to do")
            return

        logger.info("Found %d long stock position(s)", len(positions))

        # 2. Find symbols that already have GTC stop/TP orders
        ib.reqAllOpenOrders()
        ib.sleep(2)
        already_protected = _fetch_open_stop_symbols(ib)

        # 3. Request market data and place orders for unprotected positions
        skipped, placed, failed = [], [], []

        for pos in positions:
            sym = pos.contract.symbol.upper()
            qty = int(pos.position)

            if sym in SKIP_SYMBOLS:
                logger.info("  %s: in skip list (hedge/ETF) — skipping", sym)
                skipped.append(sym)
                continue

            if sym in already_protected:
                logger.info("  %s: already has GTC stop/TP — skipping", sym)
                skipped.append(sym)
                continue

            # Fetch last price via IB market data snapshot, fall back to yfinance
            last_price: Optional[float] = None
            try:
                from ib_insync import Stock as _Stock  # type: ignore[import]
                import math as _math
                stk = _Stock(sym, "SMART", "USD")
                qualified = ib.qualifyContracts(stk)  # type: ignore[attr-defined]
                if qualified:
                    ticker = ib.reqMktData(qualified[0], "", True, False)  # type: ignore[attr-defined]
                    ib.sleep(2)  # type: ignore[attr-defined]
                    for raw in (ticker.last, ticker.close, ticker.bid, ticker.ask):
                        if raw is not None and not _math.isnan(float(raw)) and float(raw) > 0:
                            last_price = float(raw)
                            break
                    ib.cancelMktData(qualified[0])  # type: ignore[attr-defined]
            except Exception as exc:
                logger.warning("  %s: IB price fetch failed (%s) — trying yfinance", sym, exc)

            # yfinance fallback when IB snapshot returns NaN/None
            if not last_price or last_price <= 0:
                try:
                    import yfinance as _yf
                    df = _yf.download(sym, period="1d", interval="1m", progress=False)
                    if df is not None and not df.empty:
                        last_price = float(df["Close"].iloc[-1].item())
                        logger.info("  %s: using yfinance price $%.2f", sym, last_price)
                except Exception as exc2:
                    logger.warning("  %s: yfinance price also failed: %s", sym, exc2)

            if not last_price or last_price <= 0:
                logger.warning("  %s: no live price available — skipping", sym)
                skipped.append(sym)
                continue

            # Fetch ATR (yfinance, background)
            logger.info("  %s: fetching ATR (qty=%d, last=$%.2f)…", sym, qty, last_price)
            atr = fetch_atr(sym)
            if atr:
                logger.info("  %s: ATR(14)=$%.2f  trail_dist=$%.2f  tp_dist=$%.2f",
                            sym, atr, atr * TRAILING_ATR_MULT, atr * TP_ATR_MULT)
            else:
                logger.warning("  %s: ATR unavailable — using fallback pct", sym)

            ok = _place_trailing_stop_and_tp(ib, sym, qty, last_price, atr)
            if ok:
                placed.append(sym)
            else:
                failed.append(sym)

            # Polite pause between symbols to avoid IB request throttling
            time.sleep(1.5)

    finally:
        ib.disconnect()
        logger.info("Disconnected from IBKR")

    # ── Summary ───────────────────────────────────────────────────────────────
    logger.info("")
    logger.info("═══ RETROFIT COMPLETE ═══")
    logger.info("  Placed:  %d  %s", len(placed),  placed)
    logger.info("  Skipped: %d  %s", len(skipped), skipped)
    logger.info("  Failed:  %d  %s", len(failed),  failed)

    if failed:
        logger.warning(
            "Some positions failed — re-run during market hours or check IBKR logs. "
            "Soft stops in pending_trades.json remain active as fallback."
        )


if __name__ == "__main__":
    run()
