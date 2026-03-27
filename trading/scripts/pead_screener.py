#!/usr/bin/env python3
"""
PEAD Screener — Post-Earnings Announcement Drift

Scans for stocks that have reported earnings in the last 1-10 days and show
the classic PEAD pattern: a strong gap-up on earnings followed by sustained
institutional accumulation (positive follow-through drift).

Why PEAD works
--------------
Markets systematically underreact to earnings surprises. Institutions need
multiple days to fully build positions, creating a predictable drift window
(days 1-10 post-announcement) that can be exploited with position sizing
calibrated to the gap magnitude and follow-through confirmation.

Selection criteria
------------------
1. Earnings reported 1-10 calendar days ago (PEAD window)
2. Earnings gap ≥ 3% (minimum surprise to indicate real beat)
3. Positive follow-through drift after the gap day (institutional accumulation)
4. Above 50-day SMA on the gap day (structural uptrend supports continuation)
5. Volume on gap day ≥ 2× 20-day average volume (institutional participation)
6. RSI(14) ≤ 75 after gap (not yet overbought — still room to run)

Output
------
Writes ``trading/watchlist_pead.json``::

    {
      "generated_at": "2026-03-07T09:00:00",
      "candidates": [
        {
          "symbol": "XYZ",
          "earnings_date": "2026-03-05",
          "gap_pct": 0.082,
          "drift_pct": 0.031,
          "days_since_earnings": 2,
          "volume_ratio": 3.4,
          "rsi": 61.0,
          "pead_score": 0.76,
          "price": 145.20,
          "suggested_action": "BUY"
        }
      ]
    }

Scheduler integration
---------------------
Runs at 09:35 ET daily alongside update_atr_stops.py and reentry_watchlist.py.
Results are also exposed on the dashboard via /api/pead.

The ``nx_screener_longs.py`` and ``nx_screener_production.py`` scripts already
apply the PEAD conviction *boost* to ranked candidates. This screener adds a
dedicated, high-frequency scan that catches PEAD setups in a wider universe
(S&P 500 + Russell 1000) and emits alerts within the first 24h.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).resolve().parent
TRADING_DIR  = SCRIPT_DIR.parent
PROJECT_ROOT = TRADING_DIR.parent

sys.path.insert(0, str(SCRIPT_DIR))

from atomic_io import atomic_write_json          # noqa: E402
from notifications import notify_event           # noqa: E402

WATCHLIST_FILE  = TRADING_DIR / "watchlist_pead.json"
UNIVERSE_CSV    = TRADING_DIR / "data" / "sp500_universe.csv"
LOGS_DIR        = TRADING_DIR / "logs"
LOG_FILE        = LOGS_DIR / "pead_screener.log"

# ── Config ────────────────────────────────────────────────────────────────────
PEAD_WINDOW_DAYS   = 10     # maximum days since earnings to consider
MIN_GAP_PCT        = 0.03   # minimum gap % to qualify
MIN_DRIFT_PCT      = 0.005  # minimum follow-through drift after gap day
MIN_VOLUME_RATIO   = 1.5    # gap-day volume must be ≥ N× 20-day avg
MAX_RSI            = 75     # skip overbought stocks
RSI_PERIOD         = 14
MIN_PEAD_SCORE     = 0.35   # minimum composite score to include in output
TOP_N              = 10     # max candidates to emit

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# ── Universe ──────────────────────────────────────────────────────────────────

# Compact fallback universe (diversified large-caps likely to beat estimates)
_FALLBACK_UNIVERSE = [
    "AAPL","MSFT","GOOGL","AMZN","META","NVDA","TSLA","BRK-B","JPM","V",
    "UNH","XOM","JNJ","WMT","PG","MA","HD","AVGO","LLY","MRK",
    "ABBV","PEP","COST","KO","ADBE","CRM","ORCL","NFLX","ACN","TMO",
    "ABT","DHR","NKE","TXN","QCOM","IBM","INTC","AMD","MU","AMAT",
    "LRCX","KLAC","SNPS","CDNS","PANW","CRWD","ZS","DDOG","SNOW","NET",
    "CMG","MCD","SBUX","YUM","DPZ","BKNG","MAR","HLT","LVS","MGM",
    "BA","CAT","DE","HON","MMM","GE","RTX","LMT","NOC","GD",
    "XLE","XLF","XLI","XLK","XLV","XLY","XLP","XLRE","XLU","XLB",
    "CHRD","MTDR","OXY","COP","APA","MPC","VLO","PSX","DVN","PXD",
    "CF","NTR","MOS","FMC","CTVA","CE","LYB","DOW","EMN","HUN",
    "WMB","KMI","OKE","TRGP","ET","EPD","MMP","MPLX","PAA","DCP",
    "DKNG","PENN","RSI","CHDN","MGM","CZR","WYNN","LVS","MLCO",
    "EQIX","AMT","CCI","SBAC","DLR","PSA","EXR","CUBE","LSI","IRM",
    "SFM","CASY","WEIS","VLGEA","KR","SFM","LNTH","ATO","VZ",
]


def _load_universe() -> list[str]:
    """Load screener universe from CSV or fall back to hardcoded list."""
    if UNIVERSE_CSV.exists():
        try:
            import csv
            with UNIVERSE_CSV.open() as f:
                reader = csv.DictReader(f)
                syms = [r.get("symbol") or r.get("Symbol") or "" for r in reader]
                syms = [s.strip().upper() for s in syms if s.strip()]
                if syms:
                    logger.info("Loaded %d symbols from %s", len(syms), UNIVERSE_CSV)
                    return syms
        except Exception as exc:
            logger.warning("Could not read universe CSV: %s", exc)
    logger.info("Using fallback universe (%d symbols)", len(_FALLBACK_UNIVERSE))
    return list(dict.fromkeys(_FALLBACK_UNIVERSE))  # deduplicate, preserve order


# ── Technical helpers ─────────────────────────────────────────────────────────

def _wilder_rsi(closes: list[float], period: int = RSI_PERIOD) -> float | None:
    if len(closes) < period * 2 + 1:
        return None
    seed = closes[: period + 1]
    avg_gain = sum(max(seed[i] - seed[i - 1], 0) for i in range(1, period + 1)) / period
    avg_loss = sum(max(seed[i - 1] - seed[i], 0) for i in range(1, period + 1)) / period
    for close, prev in zip(closes[period + 1:], closes[period:]):
        d = close - prev
        avg_gain = (avg_gain * (period - 1) + max(d, 0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-d, 0)) / period
    if avg_loss == 0:
        return 100.0
    return round(100 - 100 / (1 + avg_gain / avg_loss), 1)


# ── PEAD analysis ─────────────────────────────────────────────────────────────

def _analyze_symbol(sym: str) -> dict[str, Any] | None:
    """Screen one symbol for PEAD setup. Returns candidate dict or None."""
    try:
        import yfinance as yf
        import pandas as pd

        ticker = yf.Ticker(sym)

        # Fetch earnings dates (attribute has changed across yfinance versions)
        edates = None
        for attr in ("earnings_dates", "earnings_history"):
            try:
                edates = getattr(ticker, attr, None)
                if edates is not None and not (hasattr(edates, "empty") and edates.empty):
                    break
                edates = None
            except Exception:
                edates = None

        if edates is None or (hasattr(edates, "empty") and edates.empty):
            return None

        now = pd.Timestamp.now(tz="America/New_York")
        past_dates = edates.index[edates.index <= now]
        if past_dates.empty:
            return None

        latest_earnings = past_dates.max()
        days_since = (now - latest_earnings).days
        if days_since < 1 or days_since > PEAD_WINDOW_DAYS:
            return None

        # Fetch price history (3 months for sufficient indicator data)
        hist = ticker.history(period="3mo", auto_adjust=True)
        if hist.empty or len(hist) < 30:
            return None

        closes  = [float(c) for c in hist["Close"].dropna().tolist()]
        volumes = [float(v) for v in hist["Volume"].dropna().tolist()]
        idx     = hist.index

        price = closes[-1]

        # Find the bar on or after earnings date
        earnings_ts = latest_earnings
        idx_tz_aware = hasattr(idx, "tz") and idx.tz is not None
        ts_tz_aware  = earnings_ts.tzinfo is not None

        if idx_tz_aware and not ts_tz_aware:
            import pytz
            earnings_ts = pytz.timezone("America/New_York").localize(latest_earnings.to_pydatetime())
        elif not idx_tz_aware and ts_tz_aware:
            earnings_ts = earnings_ts.replace(tzinfo=None)

        mask = idx >= earnings_ts
        if not mask.any():
            return None

        # Use searchsorted for safe integer location (get_loc may return slice on duplicate index)
        import numpy as np
        gap_bar_loc = int(np.searchsorted(idx, idx[mask][0]))
        if gap_bar_loc < 1:
            return None

        pre_close  = closes[gap_bar_loc - 1]
        gap_close  = closes[gap_bar_loc]
        gap_volume = volumes[gap_bar_loc]

        if pre_close <= 0 or gap_close <= 0:
            return None

        gap_pct = (gap_close - pre_close) / pre_close

        # Must be a positive gap of at least MIN_GAP_PCT
        if gap_pct < MIN_GAP_PCT:
            return None

        # Volume ratio on gap day
        avg_vol_20 = sum(volumes[max(0, gap_bar_loc - 20): gap_bar_loc]) / min(gap_bar_loc, 20)
        volume_ratio = gap_volume / avg_vol_20 if avg_vol_20 > 0 else 0.0
        if volume_ratio < MIN_VOLUME_RATIO:
            return None

        # Follow-through drift from gap close to today
        drift_pct = (price - gap_close) / gap_close if gap_close > 0 else 0.0
        if drift_pct < MIN_DRIFT_PCT:
            return None

        # 50-day SMA check (stock must be above SMA on gap day)
        sma50_bars = closes[max(0, gap_bar_loc - 50): gap_bar_loc]
        if len(sma50_bars) < 20:
            return None
        sma50 = sum(sma50_bars) / len(sma50_bars)
        if gap_close < sma50:
            return None

        # RSI check — not yet overbought
        rsi = _wilder_rsi(closes)
        if rsi is not None and rsi > MAX_RSI:
            return None

        # Composite PEAD score (0-1)
        gap_score      = min(1.0, gap_pct / 0.12)           # full score at 12% gap
        drift_score    = min(1.0, drift_pct / 0.06)         # full score at 6% drift
        volume_score   = min(1.0, (volume_ratio - 1) / 3.0) # full score at 4× avg volume
        recency_score  = max(0.0, 1.0 - (days_since / PEAD_WINDOW_DAYS))
        pead_score     = round(
            0.30 * gap_score +
            0.25 * drift_score +
            0.25 * volume_score +
            0.20 * recency_score,
            4,
        )

        if pead_score < MIN_PEAD_SCORE:
            return None

        return {
            "symbol":              sym,
            "earnings_date":       latest_earnings.strftime("%Y-%m-%d"),
            "gap_pct":             round(gap_pct, 4),
            "drift_pct":           round(drift_pct, 4),
            "days_since_earnings": int(days_since),
            "volume_ratio":        round(volume_ratio, 2),
            "rsi":                 rsi,
            "pead_score":          pead_score,
            "price":               round(price, 2),
            "sma50":               round(sma50, 2),
            "suggested_action":    "BUY",
        }

    except Exception as exc:  # noqa: BLE001
        logger.debug("PEAD analysis failed for %s: %s", sym, exc)
        return None


# ── Main ───────────────────────────────────────────────────────────────────────

def run() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    universe = _load_universe()
    logger.info("Scanning %d symbols for PEAD setups...", len(universe))

    candidates: list[dict[str, Any]] = []
    earnings_none_count = 0
    for sym in universe:
        result = _analyze_symbol(sym)
        if result is None:
            # Track symbols that returned None at the earnings-dates step
            earnings_none_count += 1
        else:
            candidates.append(result)
            logger.info(
                "PEAD candidate: %s — gap=%.1f%%, drift=%.1f%%, days=%d, score=%.2f",
                sym,
                result["gap_pct"] * 100,
                result["drift_pct"] * 100,
                result["days_since_earnings"],
                result["pead_score"],
            )

    # Warn if the earnings data source appears broken (>90% of symbols returned None)
    if len(universe) > 10 and earnings_none_count / len(universe) > 0.90:
        logger.warning(
            "PEAD screener: %.0f%% of symbols returned no earnings data (%d/%d). "
            "The earnings_dates API may be unavailable or broken.",
            earnings_none_count / len(universe) * 100,
            earnings_none_count,
            len(universe),
        )

    # Sort by score descending, cap at TOP_N
    candidates.sort(key=lambda c: c["pead_score"], reverse=True)
    top_candidates = candidates[:TOP_N]

    logger.info("Found %d PEAD candidate(s) (emitting top %d)", len(candidates), len(top_candidates))

    # Persist output
    output = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "total_scanned": len(universe),
        "candidates": top_candidates,
    }
    atomic_write_json(WATCHLIST_FILE, output)
    logger.info("PEAD watchlist saved to %s", WATCHLIST_FILE)

    # Alert if any fresh high-conviction setups found (within 2 days of earnings)
    urgent_alerts = [c for c in top_candidates if c["days_since_earnings"] <= 2 and c["pead_score"] >= 0.55]
    if urgent_alerts:
        lines = []
        for c in urgent_alerts:
            lines.append(
                f"  {c['symbol']}: gap={c['gap_pct']*100:.1f}% | drift={c['drift_pct']*100:.1f}% "
                f"| vol={c['volume_ratio']:.1f}× | score={c['pead_score']:.2f}"
            )
        notify_event(
            "pead_signal",
            subject=f"📊 PEAD Signal(s): {', '.join(c['symbol'] for c in urgent_alerts)}",
            body=(
                f"{len(urgent_alerts)} fresh post-earnings drift setup(s) detected "
                f"(within 48h of announcement):\n\n"
                + "\n".join(lines)
                + "\n\nPEAD window is 1-10 days post-earnings. "
                "Act within the first 2-3 days for maximum drift capture."
            ),
            urgent=False,
        )


if __name__ == "__main__":
    run()
