"""
Implied Volatility Rank utilities for options premium selling.

IV Rank = (current_iv - 52w_low_iv) / (52w_high_iv - 52w_low_iv)
Ranges from 0 (IV at yearly low) to 1 (IV at yearly high).
Premium sellers prefer IV rank > 0.50 (selling rich premium).

Data sources: IBKR (generic tick 106) or yfinance options chain.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

MIN_IV_RANK_FOR_PREMIUM = 0.45


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


def fetch_iv_rank(symbol: str) -> Optional[float]:
    """
    Fetch IV rank via yfinance HV proxy.

    Returns [0, 1] or None. For IBKR fallback, use
    broker_data_helpers.iv_rank_from_ib() in executor code.
    """
    return fetch_iv_rank_yfinance(symbol)
