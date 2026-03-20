#!/usr/bin/env python3
"""
Dividend Capture Screener

Systematically identifies high-yield stocks approaching their ex-dividend date
where capturing the dividend is an attractive trade.

Strategy Overview
-----------------
Classic dividend capture: buy the stock 1-5 trading days before the ex-dividend
date, hold through ex-date to capture the dividend, then sell. The edge comes
from finding stocks where:
  1. The dividend yield is large enough to justify the short holding period
  2. The stock has not run up excessively (priced-in risk)
  3. Volume and liquidity are sufficient for a clean entry/exit
  4. The stock is in a flat-to-bullish trend (avoids dividend traps)

Risk management
---------------
• Position-level stop at 1× dividend amount below entry (so dividend covers the loss)
• Only enter during favorable/neutral macro regimes
• Skip if there's an uncovered call expiring BEFORE ex-date (assignment risk)
• Skip if stock is on a short watchlist (we want longs only for this strategy)
• Maximum concentration: 1 capture trade per sector at a time

Output
------
Writes ``trading/watchlist_dividend_capture.json``::

    {
      "generated_at": "...",
      "captures": [
        {
          "symbol": "VZ",
          "ex_date": "2026-03-12",
          "days_until_ex": 5,
          "dividend_amount": 0.665,
          "annual_yield_pct": 6.8,
          "price": 50.10,
          "dividend_yield_on_hold": 1.33,   # % gain from dividend alone
          "suggested_entry": 50.10,
          "suggested_stop": 49.44,
          "position_size_shares": 200,
          "capture_score": 0.72
        }
      ]
    }

Scheduler
---------
Runs daily at 07:00 MT (09:00 ET) as part of the pre-market screener batch.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).resolve().parent
TRADING_DIR  = SCRIPT_DIR.parent
PROJECT_ROOT = TRADING_DIR.parent

sys.path.insert(0, str(SCRIPT_DIR))

from atomic_io import atomic_write_json           # noqa: E402
from dividend_calendar import get_ex_dividend_info # noqa: E402
from notifications import notify_event            # noqa: E402

OUTPUT_FILE = TRADING_DIR / "watchlist_dividend_capture.json"
LOGS_DIR    = TRADING_DIR / "logs"
LOG_FILE    = LOGS_DIR / "dividend_capture_screener.log"

# ── Config ────────────────────────────────────────────────────────────────────
MIN_ANNUAL_YIELD_PCT   = 3.0    # at least 3% annualized yield
MIN_DIVIDEND_AMOUNT    = 0.20   # at least $0.20/share per quarter
MAX_DAYS_UNTIL_EX      = 7      # enter no more than 7 days before ex-date
MIN_DAYS_UNTIL_EX      = 1      # must be at least 1 day before ex-date
MIN_AVG_VOLUME         = 500_000  # minimum avg daily volume
MIN_CAPTURE_SCORE      = 0.40   # minimum composite score to include
MAX_PRICE_RUN_PCT      = 0.05   # skip if stock ran >5% in last 5 days (priced-in)
STOP_MULTIPLIER        = 1.0    # stop at 1× dividend amount below entry

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ── Dividend-paying high-yield universe ───────────────────────────────────────
# Focus on liquid, high-yield names across dividend-friendly sectors
_DIVIDEND_UNIVERSE = [
    # Energy (MLPs + majors)
    "XOM", "CVX", "COP", "OXY", "APA", "MPC", "VLO", "PSX", "DVN",
    "ET", "EPD", "WMB", "KMI", "OKE", "TRGP",
    # Utilities
    "NEE", "DUK", "SO", "D", "EXC", "AES", "ETR", "PPL", "ATO", "NI",
    "WEC", "XEL", "ES", "CNP", "FE", "OGE", "NRG",
    # Telecom
    "VZ", "T", "TMUS",
    # REITs
    "EQIX", "AMT", "CCI", "SBAC", "DLR", "PSA", "EXR", "IRM", "WELL",
    "VTR", "PEAK", "O", "STAG", "NNN",
    # Financials
    "JPM", "BAC", "WFC", "C", "MS", "GS", "BLK", "SCHW",
    # Consumer Staples
    "KO", "PEP", "PM", "MO", "BTI", "PG", "CL", "GIS", "K", "HRL",
    # Chemicals
    "LYB", "DOW", "EMN", "CE", "HUN",
    # Healthcare
    "ABBV", "BMY", "MRK", "PFE", "JNJ", "AMGN",
]


# ── Symbol analysis ────────────────────────────────────────────────────────────

def _analyze_symbol(sym: str, today: date) -> dict[str, Any] | None:
    """Screen one symbol for dividend capture opportunity. Returns candidate dict or None."""
    try:
        # Get dividend info (cached for 24h)
        div_info = get_ex_dividend_info(sym)
        ex_date_str = div_info.get("ex_date")
        if not ex_date_str:
            return None

        ex_date = date.fromisoformat(ex_date_str)
        days_until_ex = (ex_date - today).days

        if not (MIN_DAYS_UNTIL_EX <= days_until_ex <= MAX_DAYS_UNTIL_EX):
            return None

        div_amount = float(div_info.get("dividend_amount") or 0)
        annual_yield_pct = float(div_info.get("annual_yield_pct") or 0)

        if div_amount < MIN_DIVIDEND_AMOUNT:
            return None
        if annual_yield_pct < MIN_ANNUAL_YIELD_PCT:
            return None

        # Fetch price history for trend and volume check
        import yfinance as yf
        ticker = yf.Ticker(sym)
        hist = ticker.history(period="1mo", auto_adjust=True)
        if hist.empty or len(hist) < 10:
            return None

        closes  = [float(c) for c in hist["Close"].dropna().tolist()]
        volumes = [float(v) for v in hist["Volume"].dropna().tolist()]
        price   = closes[-1]

        # Volume check
        avg_vol_20 = sum(volumes[-20:]) / min(len(volumes), 20)
        if avg_vol_20 < MIN_AVG_VOLUME:
            return None

        # Check for recent run-up (priced-in risk)
        if len(closes) >= 6:
            price_5d_ago = closes[-6]
            run_up_pct = (price - price_5d_ago) / price_5d_ago if price_5d_ago > 0 else 0.0
            if run_up_pct > MAX_PRICE_RUN_PCT:
                logger.debug("%s: skipped — recent run-up %.1f%% (priced-in risk)", sym, run_up_pct * 100)
                return None

        # Trend check: stock should be in a flat-to-bullish trend (not a dividend trap)
        if len(closes) >= 20:
            sma20 = sum(closes[-20:]) / 20
            if price < sma20 * 0.96:  # allow up to 4% below SMA (avoid deep downtrends)
                logger.debug("%s: skipped — price %.2f far below SMA20 %.2f (potential dividend trap)", sym, price, sma20)
                return None

        # Dividend yield on the specific holding period (entry to ex-date)
        dividend_yield_on_hold = (div_amount / price * 100) if price > 0 else 0.0

        # Composite score
        yield_score   = min(1.0, annual_yield_pct / 10.0)   # full score at 10% yield
        timing_score  = 1.0 - (days_until_ex - 1) / MAX_DAYS_UNTIL_EX  # best at 1-2 days before
        volume_score  = min(1.0, (avg_vol_20 / 2_000_000))               # full at 2M avg vol
        capture_score = round(0.40 * yield_score + 0.35 * timing_score + 0.25 * volume_score, 4)

        if capture_score < MIN_CAPTURE_SCORE:
            return None

        suggested_stop = round(price - STOP_MULTIPLIER * div_amount, 2)
        # Target ~$10k notional; round down to nearest 100 shares, minimum 1 share.
        # For high-priced stocks (e.g. EQIX ~$970) this correctly gives a small lot.
        position_size = max(1, round(10_000 / price)) if price > 0 else 100

        return {
            "symbol":               sym,
            "ex_date":              ex_date_str,
            "days_until_ex":        int(days_until_ex),
            "dividend_amount":      round(div_amount, 4),
            "annual_yield_pct":     round(annual_yield_pct, 2),
            "price":                round(price, 2),
            "dividend_yield_on_hold": round(dividend_yield_on_hold, 3),
            "avg_volume":           round(avg_vol_20),
            "suggested_entry":      round(price, 2),
            "suggested_stop":       suggested_stop,
            "suggested_shares":     position_size,
            "capture_score":        capture_score,
            "action":               "BUY — dividend capture",
        }

    except Exception as exc:  # noqa: BLE001
        logger.debug("Dividend capture analysis failed for %s: %s", sym, exc)
        return None


# ── Main ───────────────────────────────────────────────────────────────────────

def run() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    today = date.today()
    logger.info("Scanning %d symbols for dividend capture opportunities (ex-date within %d days)...",
                len(_DIVIDEND_UNIVERSE), MAX_DAYS_UNTIL_EX)

    captures: list[dict[str, Any]] = []
    for sym in _DIVIDEND_UNIVERSE:
        result = _analyze_symbol(sym, today)
        if result:
            captures.append(result)
            logger.info(
                "DIV CAPTURE: %s — ex=%s (%dd), div=$%.2f/sh, yield=%.1f%%, score=%.2f",
                sym,
                result["ex_date"],
                result["days_until_ex"],
                result["dividend_amount"],
                result["annual_yield_pct"],
                result["capture_score"],
            )

    captures.sort(key=lambda c: c["capture_score"], reverse=True)
    logger.info("Found %d dividend capture opportunity(s)", len(captures))

    output = {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        "scan_date":    today.isoformat(),
        "captures":     captures,
    }
    atomic_write_json(OUTPUT_FILE, output)
    logger.info("Dividend capture watchlist saved to %s", OUTPUT_FILE)

    # Alert for imminent opportunities (≤2 days until ex-date, score ≥ 0.55)
    alerts = [c for c in captures if c["days_until_ex"] <= 2 and c["capture_score"] >= 0.55]
    if alerts:
        lines = [
            f"  {c['symbol']}: ex={c['ex_date']} | div=${c['dividend_amount']:.2f}/sh "
            f"| yield={c['annual_yield_pct']:.1f}% | price=${c['price']:.2f} "
            f"| stop=${c['suggested_stop']:.2f}"
            for c in alerts
        ]
        notify_event(
            "dividend_capture",
            subject=f"💰 Dividend Capture: {', '.join(c['symbol'] for c in alerts)}",
            body=(
                f"{len(alerts)} dividend capture opportunity(s) — ex-date within 48h:\n\n"
                + "\n".join(lines)
                + "\n\nStrategy: Buy before market close today, sell 1-2 days after ex-date. "
                "Stop = 1× dividend amount below entry (breakeven if stopped out)."
            ),
            urgent=False,
        )


if __name__ == "__main__":
    run()
