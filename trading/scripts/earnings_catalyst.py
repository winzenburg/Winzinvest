#!/usr/bin/env python3
"""
Earnings Catalyst Detector — post-earnings drift scoring.

Detects recent earnings events and scores the post-announcement price action
to capture the well-documented Post-Earnings Announcement Drift (PEAD) anomaly.

A strong earnings beat followed by a gap-up and sustained momentum in the
subsequent 1-5 days signals institutional accumulation. This module produces
a conviction boost (0.0 to 0.25) that is additive to the screener's
hybrid_score and the executor's conviction multiplier.

Data source: yfinance earnings_dates (no paid API required).
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

EARNINGS_LOOKBACK_DAYS = 10
DRIFT_WINDOW_DAYS = 5

MIN_GAP_PCT = 0.02
MIN_FOLLOWTHROUGH_PCT = 0.01

MAX_BOOST = 0.25


def _fetch_earnings_date(symbol: str) -> Optional[datetime]:
    """Return the most recent past earnings date for a symbol, or None."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        dates = ticker.earnings_dates
        if dates is None or dates.empty:
            return None
        now = pd.Timestamp.now(tz="America/New_York")
        past_dates = dates.index[dates.index <= now]
        if past_dates.empty:
            return None
        most_recent = past_dates.max()
        return most_recent.to_pydatetime().replace(tzinfo=None)
    except Exception as exc:
        logger.debug("Could not fetch earnings date for %s: %s", symbol, exc)
        return None


def compute_earnings_boost(
    symbol: str,
    ohlcv: pd.DataFrame,
    side: str = "LONG",
    lookback_days: int = EARNINGS_LOOKBACK_DAYS,
) -> Dict[str, Any]:
    """Compute post-earnings drift conviction boost.

    Returns a dict with:
      - earnings_boost: float in [0.0, MAX_BOOST] — additive to hybrid_score
      - earnings_date: ISO string of the most recent earnings, or None
      - gap_pct: overnight gap percentage after earnings
      - drift_pct: price change from earnings day close to latest close
      - is_catalyst: bool — True if boost > 0
    """
    result: Dict[str, Any] = {
        "earnings_boost": 0.0,
        "earnings_date": None,
        "gap_pct": 0.0,
        "drift_pct": 0.0,
        "is_catalyst": False,
    }

    try:
        close = ohlcv["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        if len(close) < 10:
            return result
    except (KeyError, AttributeError):
        return result

    earnings_date = _fetch_earnings_date(symbol)
    if earnings_date is None:
        return result

    cutoff = datetime.now() - timedelta(days=lookback_days)
    if earnings_date < cutoff:
        return result

    result["earnings_date"] = earnings_date.strftime("%Y-%m-%d")

    try:
        idx = close.index
        if hasattr(idx, "tz") and idx.tz is not None:
            earnings_ts = pd.Timestamp(earnings_date, tz=idx.tz)
        else:
            earnings_ts = pd.Timestamp(earnings_date)

        mask = idx >= earnings_ts
        if not mask.any():
            return result

        first_post_idx = idx[mask][0]
        post_pos = idx.get_loc(first_post_idx)
        if post_pos < 1:
            return result

        pre_close = float(close.iloc[post_pos - 1])
        post_open_close = float(close.iloc[post_pos])
        current_close = float(close.iloc[-1])

        if pre_close <= 0:
            return result

        gap_pct = (post_open_close - pre_close) / pre_close
        drift_pct = (current_close - post_open_close) / post_open_close if post_open_close > 0 else 0.0

        result["gap_pct"] = round(gap_pct, 4)
        result["drift_pct"] = round(drift_pct, 4)

    except Exception as exc:
        logger.debug("Earnings price analysis failed for %s: %s", symbol, exc)
        return result

    is_short = side.upper() in ("SHORT", "SELL")

    if is_short:
        bullish_gap = gap_pct < -MIN_GAP_PCT
        bullish_drift = drift_pct < -MIN_FOLLOWTHROUGH_PCT
    else:
        bullish_gap = gap_pct > MIN_GAP_PCT
        bullish_drift = drift_pct > MIN_FOLLOWTHROUGH_PCT

    if not bullish_gap:
        return result

    gap_magnitude = min(abs(gap_pct) / 0.10, 1.0)
    gap_score = gap_magnitude * 0.6

    drift_score = 0.0
    if bullish_drift:
        drift_magnitude = min(abs(drift_pct) / 0.08, 1.0)
        drift_score = drift_magnitude * 0.4

    days_since = (datetime.now() - earnings_date).days
    recency_decay = max(0.0, 1.0 - (days_since / lookback_days))

    boost = (gap_score + drift_score) * recency_decay * MAX_BOOST

    result["earnings_boost"] = round(float(np.clip(boost, 0.0, MAX_BOOST)), 4)
    result["is_catalyst"] = result["earnings_boost"] > 0.0

    if result["is_catalyst"]:
        logger.info(
            "Earnings catalyst %s: gap=%.1f%%, drift=%.1f%%, boost=%.3f (days_since=%d)",
            symbol, gap_pct * 100, drift_pct * 100, result["earnings_boost"], days_since,
        )

    return result


def batch_earnings_boost(
    symbols: list,
    data_map: Dict[str, pd.DataFrame],
    side: str = "LONG",
) -> Dict[str, Dict[str, Any]]:
    """Compute earnings boost for a batch of symbols. Returns {symbol: boost_dict}."""
    results: Dict[str, Dict[str, Any]] = {}
    for sym in symbols:
        if sym not in data_map:
            continue
        results[sym] = compute_earnings_boost(sym, data_map[sym], side=side)
    catalysts = sum(1 for v in results.values() if v.get("is_catalyst"))
    if catalysts:
        logger.info("Earnings catalysts found: %d/%d symbols", catalysts, len(symbols))
    return results
