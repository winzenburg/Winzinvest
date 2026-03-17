#!/usr/bin/env python3
"""
Multi-Timeframe Confirmation — weekly + daily + intraday alignment scoring.

Computes whether a symbol's trend is aligned across three timeframes:
  - Weekly  (65-day ROC + price vs 50-day MA)
  - Daily   (20-day ROC + price vs 20-day MA)
  - Intraday proxy (5-day ROC + 5-day momentum slope)

Returns a score from 0.0 (no alignment) to 1.0 (all three timeframes
bullish or all three bearish). Used by screeners to boost hybrid_score
for strongly-aligned setups and penalize conflicting signals.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _safe_roc(close: np.ndarray, lookback: int) -> float:
    """Return rate of change over lookback periods, or 0.0 if insufficient data."""
    if len(close) < lookback + 1 or close[-lookback - 1] <= 0:
        return 0.0
    return (close[-1] - close[-lookback - 1]) / close[-lookback - 1]


def _sma(close: np.ndarray, period: int) -> float:
    """Simple moving average of the last `period` bars."""
    if len(close) < period:
        return float(close[-1]) if len(close) > 0 else 0.0
    return float(np.mean(close[-period:]))


def _slope_normalized(values: np.ndarray, window: int = 5) -> float:
    """Linear regression slope of the last `window` values, normalized to [-1, 1]."""
    if len(values) < window:
        return 0.0
    segment = values[-window:]
    x = np.arange(window, dtype=float)
    x_mean = x.mean()
    y_mean = segment.mean()
    if y_mean == 0:
        return 0.0
    denom = np.sum((x - x_mean) ** 2)
    if denom == 0:
        return 0.0
    slope = np.sum((x - x_mean) * (segment - y_mean)) / denom
    normalized = slope / abs(y_mean)
    return float(np.clip(normalized * 10, -1.0, 1.0))


def compute_mtf_score(
    ohlcv: pd.DataFrame,
    side: str = "LONG",
) -> Optional[float]:
    """Score multi-timeframe alignment from daily OHLCV data.

    Each timeframe produces a directional signal in [-1, 1]:
      - Weekly:   65d ROC sigmoid + price vs 50-day MA
      - Daily:    20d ROC sigmoid + price vs 20-day MA
      - Intraday: 5d ROC + 5-day slope of closes

    For longs, positive signals are bullish. For shorts, negative signals are bullish.
    The final score measures agreement: 1.0 = all aligned, 0.0 = conflicting.

    Returns None if insufficient data.
    """
    try:
        close = ohlcv["Close"].values
        if len(close) < 65:
            return None
    except (KeyError, AttributeError):
        return None

    def _sigmoid(x: float, scale: float = 10.0) -> float:
        """Tanh-based sigmoid mapping value to [-1, 1]."""
        return float(np.tanh(x * scale))

    weekly_roc = _safe_roc(close, 65)
    weekly_ma = _sma(close, 50)
    weekly_price_rel = (close[-1] / weekly_ma - 1.0) if weekly_ma > 0 else 0.0
    weekly_signal = 0.6 * _sigmoid(weekly_roc, 8.0) + 0.4 * _sigmoid(weekly_price_rel, 15.0)

    daily_roc = _safe_roc(close, 20)
    daily_ma = _sma(close, 20)
    daily_price_rel = (close[-1] / daily_ma - 1.0) if daily_ma > 0 else 0.0
    daily_signal = 0.6 * _sigmoid(daily_roc, 12.0) + 0.4 * _sigmoid(daily_price_rel, 20.0)

    intra_roc = _safe_roc(close, 5)
    intra_slope = _slope_normalized(close, 5)
    intra_signal = 0.5 * _sigmoid(intra_roc, 15.0) + 0.5 * intra_slope

    is_short = side.upper() in ("SHORT", "SELL")
    if is_short:
        weekly_signal = -weekly_signal
        daily_signal = -daily_signal
        intra_signal = -intra_signal

    signs = [
        1 if weekly_signal > 0 else (-1 if weekly_signal < 0 else 0),
        1 if daily_signal > 0 else (-1 if daily_signal < 0 else 0),
        1 if intra_signal > 0 else (-1 if intra_signal < 0 else 0),
    ]
    agreement = sum(signs)

    avg_magnitude = (abs(weekly_signal) + abs(daily_signal) + abs(intra_signal)) / 3.0

    if agreement == 3:
        score = 0.7 + 0.3 * avg_magnitude
    elif agreement == 2:
        score = 0.5 + 0.2 * avg_magnitude
    elif agreement == 1:
        score = 0.3 + 0.1 * avg_magnitude
    else:
        score = max(0.0, 0.2 * avg_magnitude)

    return round(float(np.clip(score, 0.0, 1.0)), 3)


def compute_mtf_details(
    ohlcv: pd.DataFrame,
    side: str = "LONG",
) -> dict:
    """Return detailed MTF breakdown for diagnostics.

    Returns dict with weekly_signal, daily_signal, intra_signal, mtf_score,
    and alignment (STRONG, MODERATE, WEAK, CONFLICTING).
    """
    try:
        close = ohlcv["Close"].values
        if len(close) < 65:
            return {"mtf_score": None, "alignment": "INSUFFICIENT_DATA"}
    except (KeyError, AttributeError):
        return {"mtf_score": None, "alignment": "INSUFFICIENT_DATA"}

    def _sigmoid(x: float, scale: float = 10.0) -> float:
        return float(np.tanh(x * scale))

    weekly_roc = _safe_roc(close, 65)
    weekly_ma = _sma(close, 50)
    weekly_price_rel = (close[-1] / weekly_ma - 1.0) if weekly_ma > 0 else 0.0
    weekly_signal = 0.6 * _sigmoid(weekly_roc, 8.0) + 0.4 * _sigmoid(weekly_price_rel, 15.0)

    daily_roc = _safe_roc(close, 20)
    daily_ma = _sma(close, 20)
    daily_price_rel = (close[-1] / daily_ma - 1.0) if daily_ma > 0 else 0.0
    daily_signal = 0.6 * _sigmoid(daily_roc, 12.0) + 0.4 * _sigmoid(daily_price_rel, 20.0)

    intra_roc = _safe_roc(close, 5)
    intra_slope = _slope_normalized(close, 5)
    intra_signal = 0.5 * _sigmoid(intra_roc, 15.0) + 0.5 * intra_slope

    is_short = side.upper() in ("SHORT", "SELL")
    if is_short:
        weekly_signal = -weekly_signal
        daily_signal = -daily_signal
        intra_signal = -intra_signal

    score = compute_mtf_score(ohlcv, side)

    if score is not None and score >= 0.7:
        alignment = "STRONG"
    elif score is not None and score >= 0.5:
        alignment = "MODERATE"
    elif score is not None and score >= 0.3:
        alignment = "WEAK"
    else:
        alignment = "CONFLICTING"

    return {
        "weekly_signal": round(weekly_signal, 3),
        "daily_signal": round(daily_signal, 3),
        "intra_signal": round(intra_signal, 3),
        "mtf_score": score,
        "alignment": alignment,
    }
