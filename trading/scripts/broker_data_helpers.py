"""
Broker-specific data helpers — IB fallback paths for ATR, regime, and IV rank.

This module centralizes all ib_insync data-fetching that was previously
scattered across shared signal modules (atr_stops, regime_detector, iv_rank).

Only execution code (executors, order_router) should import from here.
Signal/screener code must use the yfinance-only paths in the original modules.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ATR from IBKR
# ---------------------------------------------------------------------------


def atr_from_ib(symbol: str, ib: object) -> Optional[float]:
    """Fetch 14-period daily ATR via IBKR historical data.

    Returns None if ib_insync is unavailable, IB is disconnected, or data
    is insufficient. Callers should fall back to yfinance-based ATR.
    """
    try:
        from ib_insync import Stock, util
    except ImportError:
        return None

    if not getattr(ib, "isConnected", lambda: False)():
        return None

    try:
        import numpy as np

        contract = Stock(symbol, "SMART", "USD")
        bars = ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr="1 M",
            barSizeSetting="1 day",
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
        )
        if not bars or len(bars) < 15:
            return None

        df = util.df(bars)
        col_map = {c.lower(): c for c in df.columns}
        h = df[col_map.get("high", "High")]
        low = df[col_map.get("low", "Low")]
        c = df[col_map.get("close", "Close")]
        cp = c.shift(1)
        tr = np.maximum(h - low, np.maximum((h - cp).abs(), (low - cp).abs()))
        return float(tr.rolling(14, min_periods=1).mean().iloc[-1])
    except Exception as exc:
        logger.debug("IBKR ATR fetch failed for %s: %s", symbol, exc)
        return None


# ---------------------------------------------------------------------------
# Regime from IBKR
# ---------------------------------------------------------------------------


def regime_from_ib(ib: object) -> Optional[str]:
    """Fetch SPY/VIX from IBKR and classify regime.

    Returns a RegimeType string or None on failure.
    """
    try:
        from ib_insync import Index, Stock, util
    except ImportError:
        return None

    if not getattr(ib, "isConnected", lambda: False)():
        return None

    try:
        from regime_detector import _regime_from_spy_vix

        spy_contract = Stock("SPY", "SMART", "USD")
        bars = ib.reqHistoricalData(
            spy_contract,
            endDateTime="",
            durationStr="1 Y",
            barSizeSetting="1 day",
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
        )
        if not bars or len(bars) < 200:
            return None

        df = util.df(bars)
        close_col = "close" if "close" in df.columns else "Close"
        close = df[close_col]
        current_price = float(close.iloc[-1])
        sma_200 = float(close.rolling(200).mean().iloc[-1])
        if sma_200 <= 0:
            return None

        current_vix = 20.0
        try:
            vix_contract = Index("VIX", "CBOE", "USD")
            vix_bars = ib.reqHistoricalData(
                vix_contract,
                endDateTime="",
                durationStr="5 D",
                barSizeSetting="1 day",
                whatToShow="TRADES",
                useRTH=True,
                formatDate=1,
            )
            if vix_bars and len(vix_bars) > 0:
                vix_df = util.df(vix_bars)
                vc = "close" if "close" in vix_df.columns else "Close"
                current_vix = float(vix_df[vc].iloc[-1])
        except Exception:
            pass

        spy_20d_std = None
        if len(close) >= 20:
            spy_20d_std = float(close.pct_change().iloc[-20:].std())

        return _regime_from_spy_vix(current_price, sma_200, current_vix, spy_20d_std)
    except Exception as exc:
        logger.debug("IBKR regime fetch failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# IV Rank from IBKR
# ---------------------------------------------------------------------------


def iv_rank_from_ib(symbol: str, ib: object) -> Optional[float]:
    """Fetch IV rank from IBKR using option implied volatility history.

    Returns IV rank [0, 1] or None on failure.
    """
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
    except Exception as exc:
        logger.debug("IBKR IV rank fetch failed for %s: %s", symbol, exc)
        return None


# ---------------------------------------------------------------------------
# Portfolio metrics from IBKR
# ---------------------------------------------------------------------------


def fetch_portfolio_metrics_from_ib(ib: object) -> Optional[dict]:
    """Fetch account metrics from a connected IB instance.

    Returns a dict with NetLiquidation, MaintMarginReq, EquityWithLoanValue,
    and num_positions.  Used by risk_manager as a replacement for its
    previously-internal IB connection.

    Returns None if fetching fails.
    """
    try:
        accounts = ib.accountSummary()
        result: dict = {}
        for account in accounts:
            tag = getattr(account, "tag", "")
            if tag in ("NetLiquidation", "MaintMarginReq", "EquityWithLoanValue"):
                try:
                    result[tag] = float(account.value)
                except (TypeError, ValueError):
                    pass

        positions = []
        try:
            positions = list(ib.positions())
        except Exception:
            pass
        result["num_positions"] = len([p for p in positions if getattr(p, "position", 0) != 0])

        return result if "NetLiquidation" in result else None
    except Exception as exc:
        logger.error("Failed to fetch portfolio metrics from IB: %s", exc)
        return None
