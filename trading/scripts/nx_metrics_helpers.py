#!/usr/bin/env python3
"""
NX metrics technical helpers — RSI, Bollinger Bands, True Range / ATR.

Used by Composite (Step 2), ATR RVol (Step 4), and Structure (Step 5).
Reference: NX_SCREENER_TECHNICAL_SPEC.md, NX_TIER5_FULL_METRICS_STEPS.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Tuple

try:
    import yfinance as yf
except ImportError:
    yf = None  # type: ignore

def _ensure_series(close: pd.Series | pd.DataFrame) -> pd.Series:
    """If close is a DataFrame with one column, return that column as Series."""
    if isinstance(close, pd.DataFrame):
        if "Close" in close.columns:
            return close["Close"].copy()
        return close.iloc[:, 0]
    return close.copy()


def calculate_rsi(close: pd.Series | pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Standard RSI (Relative Strength Index).
    delta = close.diff(); gain = max(delta, 0); loss = max(-delta, 0);
    rs = gain.rolling(period).mean() / loss.rolling(period).mean();
    rsi = 100 - (100 / (1 + rs)).
    When loss is zero, RSI is set to 100.
    """
    c = _ensure_series(close)
    delta = c.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = np.where(avg_loss > 0, avg_gain / avg_loss, np.inf)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    rsi = np.where(np.isposinf(rs), 100.0, rsi)
    rsi = np.where(np.isnan(rsi), 50.0, rsi)  # not enough data
    return pd.Series(rsi, index=c.index)


def bollinger_bands(
    close: pd.Series | pd.DataFrame,
    window: int = 20,
    num_std: float = 2.0,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Bollinger Bands: middle = SMA(close), upper/lower = middle ± num_std * std(close).
    Returns (upper, middle, lower).
    """
    c = _ensure_series(close)
    middle = c.rolling(window=window, min_periods=1).mean()
    std = c.rolling(window=window, min_periods=1).std()
    std = std.fillna(0)
    upper = middle + num_std * std
    lower = middle - num_std * std
    return (upper, middle, lower)


def calculate_true_range(high: float, low: float, close_prev: float) -> float:
    """
    True Range for one bar: max(high - low, |high - close_prev|, |low - close_prev|).
    """
    return float(
        max(
            high - low,
            abs(high - close_prev),
            abs(low - close_prev),
        )
    )


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Average True Range (ATR). df must have High, Low, Close.
    TR = max(High-Low, |High - Close_prev|, |Low - Close_prev|);
    ATR = rolling mean of TR over period.
    """
    if "High" not in df.columns or "Low" not in df.columns or "Close" not in df.columns:
        return pd.Series(dtype=float)
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    close_prev = close.shift(1)
    tr = np.maximum(
        high - low,
        np.maximum(
            (high - close_prev).abs(),
            (low - close_prev).abs(),
        ),
    )
    atr = tr.rolling(window=period, min_periods=1).mean()
    return atr


def calculate_composite_score(df: pd.DataFrame) -> float | None:
    """
    Composite trend strength (NX spec): momentum_20d (norm) + BB position + RSI (norm).
    Weights: 0.4, 0.3, 0.3. Returns value in [0, 1] or None if insufficient data.
    """
    if df is None or len(df) < 20:
        return None
    close = _ensure_series(df["Close"] if "Close" in df.columns else df.iloc[:, 3])

    # Momentum 20d: normalize to [0, 1] via clamp(-0.15, 0.15) then (x/0.15+1)/2
    momentum = (close.iloc[-1] - close.iloc[-20]) / close.iloc[-20]
    momentum_norm = max(-0.15, min(0.15, float(momentum))) / 0.15
    momentum_norm = (momentum_norm + 1.0) / 2.0

    # Bollinger Band position
    upper, middle, lower = bollinger_bands(close, window=20, num_std=2.0)
    bb_range = upper.iloc[-1] - lower.iloc[-1]
    bb_pos = (
        (close.iloc[-1] - lower.iloc[-1]) / bb_range
        if bb_range > 0 and not np.isnan(bb_range)
        else 0.5
    )
    bb_pos = max(0.0, min(1.0, float(bb_pos)))

    # RSI normalization: (RSI - 30) / 40, clamp [0, 1]
    rsi_series = calculate_rsi(close, 14)
    rsi_val = rsi_series.iloc[-1]
    rsi_norm = (float(rsi_val) - 30.0) / 40.0
    rsi_norm = max(0.0, min(1.0, rsi_norm))

    composite = (momentum_norm * 0.4) + (bb_pos * 0.3) + (rsi_norm * 0.3)
    return max(0.0, min(1.0, float(composite)))


def calculate_rs_252d(
    stock_data: pd.DataFrame,
    spy_data: pd.Series | pd.DataFrame,
) -> float | None:
    """
    252-day Relative Strength (NX spec): (stock_return_252 - spy_return_252) / spy_vol,
    then clamp to [-1, 1] via rs_pct / 0.5.
    Returns None if insufficient data (< 252 bars).
    """
    if stock_data is None or len(stock_data) < 252:
        return None
    spy_close = _ensure_series(spy_data)
    if len(spy_close) < 252:
        return None
    close = _ensure_series(stock_data["Close"] if "Close" in stock_data.columns else stock_data.iloc[:, 3])
    stock_return_252 = (close.iloc[-1] - close.iloc[-252]) / close.iloc[-252]
    spy_return_252 = (spy_close.iloc[-1] - spy_close.iloc[-252]) / spy_close.iloc[-252]
    spy_daily_returns = spy_close.pct_change().dropna()
    spy_vol = spy_daily_returns.std()
    if spy_vol is None or spy_vol <= 0 or np.isnan(spy_vol):
        return None
    rs_pct = (float(stock_return_252) - float(spy_return_252)) / float(spy_vol)
    rs_pct = max(-1.0, min(1.0, rs_pct / 0.5))
    return rs_pct


def calculate_rvol_atr(
    stock_data: pd.DataFrame,
    spy_data: pd.DataFrame,
) -> float | None:
    """
    ATR-based Relative Volatility: stock_ATR(14) / spy_ATR(14).
    Both DataFrames must have High, Low, Close. Returns None if insufficient data.
    """
    if stock_data is None or spy_data is None or len(stock_data) < 14 or len(spy_data) < 14:
        return None
    stock_atr = calculate_atr(stock_data, 14)
    spy_atr = calculate_atr(spy_data, 14)
    if stock_atr is None or spy_atr is None or len(stock_atr) == 0 or len(spy_atr) == 0:
        return None
    s_atr = stock_atr.iloc[-1]
    sp_atr = spy_atr.iloc[-1]
    if sp_atr is None or sp_atr <= 0 or np.isnan(sp_atr):
        return None
    return float(s_atr / sp_atr)


def calculate_structure_quality(df: pd.DataFrame) -> float | None:
    """
    Structure quality (NX spec): BB squeeze (0.25) + SMA alignment downtrend (0.35)
    + RSI divergence (0.25) + volume confirmation (0.15). Returns [0, 1] or None.
    Needs at least 20 rows; SMA alignment uses 200-bar SMA if available.
    """
    if df is None or len(df) < 20:
        return None
    close = _ensure_series(df["Close"] if "Close" in df.columns else df.iloc[:, 3])

    # 1. BB squeeze: width = (2*std)/mean, norm to [0,1] (cap at 0.1 = 1.0)
    bb_mean = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_std = bb_std.fillna(0)
    bb_width = (2.0 * bb_std) / bb_mean.replace(0, np.nan)
    bb_width = bb_width.fillna(0)
    w = bb_width.iloc[-1]
    bb_width_norm = min(float(w) / 0.1, 1.0) if w > 0 else 0.0

    # 2. SMA alignment (downtrend: 20 < 50 < 200, price < 20)
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean() if len(close) >= 200 else sma50  # fallback
    s20, s50, s200 = sma20.iloc[-1], sma50.iloc[-1], sma200.iloc[-1]
    price = close.iloc[-1]
    if s20 < s50 < s200 and price < s20:
        sma_alignment = 1.0
    elif s20 < s50:
        sma_alignment = 0.6
    else:
        sma_alignment = 0.0

    # 3. RSI divergence (for downtrend: oversold = stronger)
    rsi_series = calculate_rsi(close, 14)
    rsi_val = rsi_series.iloc[-1]
    if rsi_val < 30:
        rsi_div = 0.8
    elif rsi_val < 40:
        rsi_div = 0.6
    else:
        rsi_div = 0.2

    # 4. Volume confirmation
    if "Volume" not in df.columns:
        vol_confirm = 0.5
    else:
        vol = df["Volume"]
        vol_avg = vol.rolling(20).mean()
        if len(vol) >= 2 and len(vol_avg) > 0 and vol_avg.iloc[-1] > 0:
            if vol.iloc[-1] > 1.2 * vol_avg.iloc[-1] and close.iloc[-1] < close.iloc[-2]:
                vol_confirm = 1.0
            else:
                vol_confirm = 0.5
        else:
            vol_confirm = 0.5

    structure = (bb_width_norm * 0.25) + (sma_alignment * 0.35) + (rsi_div * 0.25) + (vol_confirm * 0.15)
    return max(0.0, min(1.0, float(structure)))


def calculate_htf_bias(ticker: str, period_4h: str = "250d") -> float | None:
    """
    HTF bias (4H): price vs 200-period SMA on 4H bars.
    1.0 = uptrend (bullish), 0.0 = downtrend (bearish), 0.5 = neutral (within 2% of SMA).
    Returns None if insufficient data or fetch fails. Short entry threshold: htf_bias < 0.50.
    """
    if yf is None:
        return None
    try:
        df_4h = yf.download(ticker, period=period_4h, interval="4h", progress=False, auto_adjust=True)
        if df_4h is None or df_4h.empty or len(df_4h) < 200:
            return None
        if isinstance(df_4h.columns, pd.MultiIndex):
            df_4h.columns = df_4h.columns.get_level_values(0)
        close = _ensure_series(df_4h["Close"] if "Close" in df_4h.columns else df_4h.iloc[:, 3])
        sma_200_4h = close.rolling(200).mean()
        current_price = close.iloc[-1]
        sma_val = sma_200_4h.iloc[-1]
        if pd.isna(sma_val) or sma_val <= 0:
            return None
        if current_price > sma_val:
            return 1.0
        if current_price < sma_val:
            return 0.0
        dist_pct = abs(float(current_price - sma_val) / float(sma_val))
        return 0.5 if dist_pct < 0.02 else 0.5
    except Exception:
        return None
