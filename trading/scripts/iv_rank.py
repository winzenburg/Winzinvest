"""
Implied Volatility Rank utilities for options premium selling.

IV Rank = (current_iv - 52w_low_iv) / (52w_high_iv - 52w_low_iv)
Ranges from 0 (IV at yearly low) to 1 (IV at yearly high).
Premium sellers prefer IV rank > 0.50 (selling rich premium).

Data sources: IBKR (generic tick 106) or yfinance options chain.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

MIN_IV_RANK_FOR_PREMIUM = 0.50


def fetch_iv_rank_ib(symbol: str, ib: Any) -> Optional[float]:
    """
    Fetch IV rank from IBKR using implied volatility historical data.
    Returns IV rank [0, 1] or None on failure.
    """
    if ib is None:
        return None
    try:
        from ib_insync import Stock, util
    except ImportError:
        return None
    if not getattr(ib, "isConnected", lambda: False)():
        return None
    try:
        contract = Stock(symbol, "SMART", "USD")
        bars = ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr="1 Y",
            barSizeSetting="1 day",
            whatToShow="OPTION_IMPLIED_VOLATILITY",
            useRTH=True,
            formatDate=1,
        )
        if not bars or len(bars) < 20:
            return None
        df = util.df(bars)
        col = "close" if "close" in df.columns else "Close"
        iv_series = df[col].dropna()
        if len(iv_series) < 20:
            return None
        current_iv = float(iv_series.iloc[-1])
        iv_low = float(iv_series.min())
        iv_high = float(iv_series.max())
        if iv_high <= iv_low:
            return None
        rank = (current_iv - iv_low) / (iv_high - iv_low)
        return max(0.0, min(1.0, rank))
    except Exception as e:
        logger.debug("IBKR IV rank fetch failed for %s: %s", symbol, e)
        return None


def fetch_iv_rank_yfinance(symbol: str) -> Optional[float]:
    """
    Estimate IV rank from yfinance options chain.
    Uses the ATM put's implied volatility vs the stock's historical volatility
    as a proxy. Returns [0, 1] or None.
    """
    try:
        import yfinance as yf
        import numpy as np
    except ImportError:
        return None
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1y")
        if hist is None or hist.empty or len(hist) < 60:
            return None

        close = hist["Close"]
        log_returns = np.log(close / close.shift(1)).dropna()
        hv_current = float(log_returns.tail(20).std() * np.sqrt(252))
        hv_all = log_returns.rolling(20).std() * np.sqrt(252)
        hv_all = hv_all.dropna()
        if len(hv_all) < 20 or hv_current <= 0:
            return None
        hv_low = float(hv_all.min())
        hv_high = float(hv_all.max())
        if hv_high <= hv_low:
            return None
        rank = (hv_current - hv_low) / (hv_high - hv_low)
        return max(0.0, min(1.0, rank))
    except Exception as e:
        logger.debug("yfinance IV rank failed for %s: %s", symbol, e)
        return None


def fetch_iv_rank(symbol: str, ib: Any = None) -> Optional[float]:
    """
    Fetch IV rank. Tries IBKR first, then yfinance HV proxy.
    Returns [0, 1] or None.
    """
    if ib is not None:
        rank = fetch_iv_rank_ib(symbol, ib)
        if rank is not None:
            return rank
    return fetch_iv_rank_yfinance(symbol)
