"""
Pre-trade correlation gate — Dalio's "Holy Grail" principle.

Before adding a new position, check its average return correlation against
all existing portfolio positions. Block if the average correlation exceeds
a configurable threshold (default 0.6), since highly correlated positions
are effectively a single concentrated bet.

Uses 20-day rolling returns from yfinance (fast, ~1s).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional, Set

if TYPE_CHECKING:
    from broker_protocols import BrokerClient

logger = logging.getLogger(__name__)

DEFAULT_MAX_AVG_CORRELATION = 0.60
LOOKBACK_DAYS = 20
MIN_POSITIONS_TO_CHECK = 2


def _get_current_position_symbols(ib: BrokerClient) -> Set[str]:
    """Get symbols of open stock positions from IB."""
    symbols: Set[str] = set()
    try:
        for pos in ib.positions():
            if getattr(pos.contract, "secType", "") != "STK":
                continue
            qty = getattr(pos, "position", 0)
            if qty == 0:
                continue
            sym = getattr(pos.contract, "symbol", "")
            if isinstance(sym, str) and sym.strip():
                symbols.add(sym.strip().upper())
    except Exception as e:
        logger.warning("Could not fetch positions for correlation check: %s", e)
    return symbols


def check_correlation(
    new_symbol: str,
    ib: Optional[BrokerClient] = None,
    existing_symbols: Optional[Set[str]] = None,
    max_avg_corr: float = DEFAULT_MAX_AVG_CORRELATION,
) -> bool:
    """Return True if the new symbol passes the correlation gate.

    Computes 20-day return correlation between new_symbol and each existing
    position. Blocks if the average correlation exceeds max_avg_corr.
    """
    if existing_symbols is None and ib is not None:
        existing_symbols = _get_current_position_symbols(ib)
    if not existing_symbols or len(existing_symbols) < MIN_POSITIONS_TO_CHECK:
        return True

    new_symbol = new_symbol.strip().upper()
    check_against = [s for s in existing_symbols if s != new_symbol]
    if len(check_against) < MIN_POSITIONS_TO_CHECK:
        return True

    try:
        import yfinance as yf
        import pandas as pd

        all_symbols = [new_symbol] + check_against
        data = yf.download(all_symbols, period="1mo", progress=False)
        if data is None or data.empty:
            return True

        if isinstance(data.columns, pd.MultiIndex):
            close = data["Close"]
        else:
            close = data[["Close"]]
            close.columns = [new_symbol]

        if close.shape[1] < 2:
            return True

        returns = close.pct_change().dropna()
        if len(returns) < 5:
            return True

        if new_symbol not in returns.columns:
            return True

        correlations: List[float] = []
        for sym in check_against:
            if sym in returns.columns:
                corr = returns[new_symbol].corr(returns[sym])
                if not pd.isna(corr):
                    correlations.append(abs(corr))

        if not correlations:
            return True

        avg_corr = sum(correlations) / len(correlations)
        if avg_corr > max_avg_corr:
            logger.warning(
                "[GATE] Correlation: %s avg correlation %.2f with existing positions "
                "(threshold %.2f) — BLOCKED",
                new_symbol, avg_corr, max_avg_corr,
            )
            return False

        logger.debug(
            "Correlation gate passed: %s avg=%.2f (threshold %.2f)",
            new_symbol, avg_corr, max_avg_corr,
        )
        return True

    except ImportError:
        logger.debug("yfinance not available for correlation check")
        return True
    except Exception as e:
        logger.warning("Correlation check failed for %s: %s — allowing trade", new_symbol, e)
        return True
