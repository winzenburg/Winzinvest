#!/usr/bin/env python3
"""
Post-Entry Premium Utility
===========================
Every time a new long stock position is opened, call `write_covered_call()`
to immediately look for a covered call opportunity on the same name.

This enforces the "wheel strategy" discipline: we never sit on uncovered
long shares when premium can be collected.

Usage (from any entry script):
    from post_entry_premium import write_covered_call

    result = write_covered_call(ib, symbol="AAPL", shares_held=200)
    if result["status"] == "executed":
        logger.info("CC written: %s", result)
    elif result["status"] == "skipped":
        logger.info("CC skipped: %s", result["reason"])

Returns a dict with keys:
    status        : "executed" | "working" | "skipped" | "error"
                    ("working" = GTC order on book, not filled within wait window)
    symbol        : str
    strike        : float | None
    expiry        : str | None
    qty           : int (contracts)
    mid_price     : float
    premium_total : float
    reason        : str (populated when skipped or error)
    order_id      : int | None
    order_status  : str | None
    timestamp     : str
"""

import logging
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
TRADING_DIR = SCRIPTS_DIR.parent
LOGS_DIR    = TRADING_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)
sys.path.insert(0, str(SCRIPTS_DIR))

from ib_fill_wait import wait_ib_order_filled

log = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
TARGET_DTE_MIN  = 21
TARGET_DTE_MAX  = 45
TARGET_DTE_IDEAL = 35
OTM_FALLBACK_PCT = 0.10     # 10% OTM fallback if delta selector fails
TARGET_DELTA_CC  = 0.20
MIN_PREMIUM_USD  = 0.10     # skip if mid < $0.10 (not worth the commission)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _nearest_expiry(ib: Any, symbol: str, target_dte: int = TARGET_DTE_IDEAL) -> str | None:
    """Return the nearest listed monthly expiry within TARGET_DTE_MIN–MAX window."""
    from ib_insync import Stock
    stk = Stock(symbol, "SMART", "USD")
    try:
        ib.qualifyContracts(stk)
    except Exception:
        pass
    chains = ib.reqSecDefOptParams(symbol, "", "STK", stk.conId)
    ib.sleep(0.3)
    if not chains:
        return None
    today = date.today()
    target_date = today + timedelta(days=target_dte)
    # Pick expiry closest to target_dte within allowed window
    candidates = []
    for exp_str in sorted(chains[0].expirations):
        exp_date = datetime.strptime(exp_str, "%Y%m%d").date()
        dte = (exp_date - today).days
        if TARGET_DTE_MIN <= dte <= TARGET_DTE_MAX:
            candidates.append((abs((exp_date - target_date).days), exp_str))
    if candidates:
        candidates.sort()
        return candidates[0][1]
    # Relax: nearest expiry > 14 DTE
    for exp_str in sorted(chains[0].expirations):
        dte = (datetime.strptime(exp_str, "%Y%m%d").date() - today).days
        if dte >= 14:
            return exp_str
    return None


def _spot_price(symbol: str) -> float | None:
    """Get current spot price via yfinance."""
    try:
        import yfinance as yf
        h = yf.download(symbol, period="2d", progress=False, auto_adjust=True)
        if h.empty:
            return None
        cl = h["Close"]
        if hasattr(cl, "columns"):
            cl = cl.iloc[:, 0]
        return float(cl.iloc[-1])
    except Exception:
        return None


def _target_strike(ib: Any, symbol: str, expiry: str, spot: float) -> float:
    """Select strike by delta (0.20) or fall back to 10% OTM."""
    try:
        from delta_strike_selector import select_strike_by_delta
        strike = select_strike_by_delta(ib, symbol, "C", expiry, TARGET_DELTA_CC)
        if strike is not None and strike > spot:
            return float(strike)
    except Exception:
        pass
    # Fallback: 10% OTM rounded to nearest listed strike
    raw = spot * (1 + OTM_FALLBACK_PCT)
    if spot > 200:
        return round(raw / 5) * 5
    elif spot > 50:
        return round(raw / 2.5) * 2.5
    else:
        return round(raw)


def _nearest_listed_strike(ib: Any, symbol: str, expiry: str, target: float, spot: float) -> float | None:
    """Snap target strike to the nearest strike listed in the IB chain."""
    from ib_insync import Stock
    stk = Stock(symbol, "SMART", "USD")
    try:
        ib.qualifyContracts(stk)
    except Exception:
        pass
    chains = ib.reqSecDefOptParams(symbol, "", "STK", stk.conId)
    ib.sleep(0.2)
    if not chains:
        return None
    available = sorted(chains[0].strikes)
    otm_strikes = [s for s in available if s > spot]
    if not otm_strikes:
        return None
    return min(otm_strikes, key=lambda x: abs(x - target))


def _get_mid(ib: Any, symbol: str, expiry: str, strike: float) -> float:
    """Get option mid price; tries live then delayed."""
    from ib_insync import Option
    try:
        opt = Option(symbol, expiry, strike, "C", "SMART")
        ib.qualifyContracts(opt)
        for mdt in (1, 3, 4):
            ib.reqMarketDataType(mdt)
            ib.reqMktData(opt, "", False, False)
            ib.sleep(1.5)
            t = ib.ticker(opt)
            bid = t.bid or 0.0
            ask = t.ask or 0.0
            if bid > 0 and ask > 0:
                ib.cancelMktData(opt)
                return round((bid + ask) / 2, 2)
            if t.last and t.last > 0:
                ib.cancelMktData(opt)
                return round(float(t.last), 2)
        ib.cancelMktData(opt)
    except Exception as e:
        log.debug("Mid price lookup failed for %s: %s", symbol, e)
    return 0.0


# ── Main public function ───────────────────────────────────────────────────────

def write_covered_call(
    ib: Any,
    symbol: str,
    shares_held: int,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Look for and execute a covered call on `symbol`.

    Args:
        ib           : connected IB instance
        symbol       : stock ticker
        shares_held  : total shares in account (determines max contracts)
        dry_run      : if True, price and log but do not place order

    Returns result dict (see module docstring).
    """
    from ib_insync import Option, LimitOrder

    # Leveraged ETFs have no listed options and are short-term momentum plays.
    # Selling a covered call caps the upside on a position that may 3x rapidly.
    # The spotlight_monitor.py wheel skip rule is mirrored here as a hard guard
    # so that any call path (base_executor, spotlight, etc.) gets the same safety.
    _LEVERAGED_ETF_NO_CC = frozenset({
        "GDXU", "KORU", "TQQQ", "SOXL", "LABU", "SPXL", "TNA",
        "MEXX", "HIBL", "NAIL", "FNGU", "DFEN", "WANT", "CURE",
        "ERX",  "TECL", "WEBL", "DPST", "RETL", "UTSL", "INDL",
    })
    if symbol.upper() in _LEVERAGED_ETF_NO_CC:
        return {
            "status": "skipped", "symbol": symbol, "strike": None, "expiry": None,
            "qty": 0, "mid_price": 0.0, "premium_total": 0.0,
            "reason": f"{symbol} is a leveraged ETF — covered calls not written (upside uncapped)",
            "order_id": None, "order_status": None,
            "timestamp": datetime.now().isoformat(),
        }

    ts = datetime.now().isoformat()
    base: dict[str, Any] = {
        "symbol": symbol, "strike": None, "expiry": None,
        "qty": 0, "mid_price": 0.0, "premium_total": 0.0,
        "reason": "", "order_id": None, "order_status": None,
        "timestamp": ts,
    }

    contracts = shares_held // 100
    if contracts < 1:
        return {**base, "status": "skipped", "reason": f"only {shares_held} shares — need ≥100 for 1 contract"}

    # ── 1. Spot price ─────────────────────────────────────────────────────────
    spot = _spot_price(symbol)
    if not spot:
        return {**base, "status": "error", "reason": "could not fetch spot price"}

    # ── 2. Expiry ─────────────────────────────────────────────────────────────
    expiry = _nearest_expiry(ib, symbol)
    if not expiry:
        return {**base, "status": "skipped", "reason": "no suitable expiry found (need 21–45 DTE)"}

    exp_date = datetime.strptime(expiry, "%Y%m%d").date()
    dte = (exp_date - date.today()).days

    # ── 3. Dividend check ─────────────────────────────────────────────────────
    try:
        from dividend_calendar import should_skip_call_for_dividend
        # Price first pass with rough premium estimate
        rough_strike = spot * (1 + OTM_FALLBACK_PCT)
        rough_premium = rough_strike * 0.005   # ~0.5% rough estimate
        div_check = should_skip_call_for_dividend(symbol, expiry, rough_premium, spot)
        if div_check.get("skip"):
            return {**base, "status": "skipped",
                    "reason": f"dividend conflict: {div_check.get('reason', '')}"}
    except Exception as e:
        log.debug("Dividend check failed for %s: %s — proceeding", symbol, e)

    # ── 4. Strike selection ───────────────────────────────────────────────────
    target = _target_strike(ib, symbol, expiry, spot)
    strike = _nearest_listed_strike(ib, symbol, expiry, target, spot)
    if not strike:
        return {**base, "status": "skipped", "reason": "could not resolve a listed strike"}

    otm_pct = (strike - spot) / spot * 100
    if otm_pct < 5.0:
        return {**base, "status": "skipped",
                "reason": f"nearest strike ${strike} is only {otm_pct:.1f}% OTM — too tight"}

    # ── 5. Price ──────────────────────────────────────────────────────────────
    mid = _get_mid(ib, symbol, expiry, strike)
    if mid < MIN_PREMIUM_USD:
        return {**base, "status": "skipped",
                "reason": f"mid price ${mid:.2f} below minimum ${MIN_PREMIUM_USD} — not worth writing"}

    premium_total = round(mid * contracts * 100, 2)

    log.info(
        "CC opportunity: %s %s $%.2f C  x%d contracts  mid=$%.2f  "
        "premium=$%.0f  DTE=%d  OTM=%.1f%%",
        symbol, expiry, strike, contracts, mid, premium_total, dte, otm_pct,
    )

    if dry_run:
        return {
            **base, "status": "dry_run",
            "strike": strike, "expiry": expiry, "qty": contracts,
            "mid_price": mid, "premium_total": premium_total,
            "reason": f"DTE={dte} OTM={otm_pct:.1f}% contracts={contracts}",
        }

    # ── 6. Place limit STO order ──────────────────────────────────────────────
    try:
        opt = Option(symbol, expiry, strike, "C", "SMART")
        ib.qualifyContracts(opt)

        order = LimitOrder("SELL", contracts, mid)
        order.tif      = "GTC"
        order.transmit = True

        trade = ib.placeOrder(opt, order)
        wait_sec = int(os.environ.get("POST_ENTRY_CC_FILL_WAIT_SEC", "30"))
        filled, status = wait_ib_order_filled(ib, trade, max_sec=wait_sec)
        log.info(
            "STO order: %s %s $%.2f C x%d  status=%s  order_id=%d  filled=%s",
            symbol, expiry, strike, contracts, status, trade.order.orderId, filled,
        )

        if filled:
            return {
                **base,
                "status": "executed",
                "strike": strike, "expiry": expiry, "qty": contracts,
                "mid_price": mid, "premium_total": premium_total,
                "order_id": trade.order.orderId, "order_status": status,
                "reason": f"DTE={dte} OTM={otm_pct:.1f}% delta~{TARGET_DELTA_CC}",
            }

        return {
            **base,
            "status": "working",
            "strike": strike, "expiry": expiry, "qty": contracts,
            "mid_price": mid, "premium_total": premium_total,
            "order_id": trade.order.orderId, "order_status": status,
            "reason": (
                f"GTC limit not filled within {wait_sec}s (status={status}) — "
                f"order may still be working; DTE={dte} OTM={otm_pct:.1f}%"
            ),
        }

    except Exception as e:
        log.error("STO order failed for %s: %s", symbol, e)
        return {**base, "status": "error", "reason": str(e),
                "strike": strike, "expiry": expiry, "qty": contracts, "mid_price": mid}
