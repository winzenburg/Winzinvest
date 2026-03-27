#!/usr/bin/env python3
"""
Portfolio Margin helpers — dynamic position sizing via IB whatIfOrder().

Under Portfolio Margin, each position's margin requirement depends on the
specific security, existing portfolio composition, and IB's TIMS risk model.
This module queries IB for the *actual* margin impact of a proposed trade,
allowing position sizing to use real PM requirements instead of static caps.

All functions degrade gracefully: on timeout, import error, or IB
disconnection they return ``None`` so callers fall back to static caps.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    pass  # ib_insync types used dynamically

logger = logging.getLogger(__name__)

# In-memory cache: (symbol, action) → MarginImpact, cleared each run
_cache: Dict[tuple, "MarginImpact"] = {}


@dataclass(frozen=True)
class MarginImpact:
    """Result of an IB whatIfOrder() call for a proposed trade."""
    init_margin: float
    maint_margin: float
    init_margin_change: float
    maint_margin_change: float
    equity_with_loan: float
    maint_margin_per_share: float
    test_qty: int


def clear_cache() -> None:
    """Reset the per-run margin cache.  Call at the start of each executor run."""
    _cache.clear()


def query_margin_impact(
    ib: Any,
    symbol: str,
    action: str,
    qty: int = 100,
    timeout_sec: float = 5.0,
) -> Optional[MarginImpact]:
    """Query IB for the margin impact of buying/selling ``qty`` shares.

    Uses ``ib.whatIfOrder()`` which returns projected margin changes without
    actually submitting the order.

    Args:
        ib: Connected ``ib_insync.IB`` instance.
        symbol: Ticker symbol (e.g. "AAPL").
        action: "BUY" or "SELL".
        qty: Number of shares to test (default 100).
        timeout_sec: Max seconds to wait for IB response.

    Returns:
        MarginImpact with per-share margin data, or None on failure.
    """
    cache_key = (symbol.upper(), action.upper(), qty)
    if cache_key in _cache:
        return _cache[cache_key]

    try:
        from ib_insync import Stock, MarketOrder
    except ImportError:
        logger.debug("ib_insync not available for PM margin query")
        return None

    if ib is None or not ib.isConnected():
        return None

    try:
        contract = Stock(symbol, "SMART", "USD")
        qualified = ib.qualifyContracts(contract)
        if not qualified:
            logger.debug("Could not qualify %s for whatIfOrder", symbol)
            return None

        order = MarketOrder(action=action.upper(), totalQuantity=qty)

        what_if = ib.whatIfOrder(contract, order)

        init_margin = _parse_margin_value(what_if.initMarginChange)
        maint_margin = _parse_margin_value(what_if.maintMarginChange)
        init_after = _parse_margin_value(what_if.initMarginAfter)
        maint_after = _parse_margin_value(what_if.maintMarginAfter)
        equity_wl = _parse_margin_value(what_if.equityWithLoanAfter)

        if maint_margin is None or maint_margin <= 0:
            logger.debug(
                "whatIfOrder for %s %s %d returned non-positive maint margin change: %s",
                action, symbol, qty, what_if.maintMarginChange,
            )
            return None

        maint_per_share = maint_margin / qty if qty > 0 else 0.0

        impact = MarginImpact(
            init_margin=init_after if init_after is not None else 0.0,
            maint_margin=maint_after if maint_after is not None else 0.0,
            init_margin_change=init_margin if init_margin is not None else 0.0,
            maint_margin_change=maint_margin,
            equity_with_loan=equity_wl if equity_wl is not None else 0.0,
            maint_margin_per_share=maint_per_share,
            test_qty=qty,
        )
        _cache[cache_key] = impact
        logger.debug(
            "PM margin for %s %s %d: init_chg=$%.0f  maint_chg=$%.0f  "
            "maint/share=$%.2f",
            action, symbol, qty, impact.init_margin_change,
            impact.maint_margin_change, maint_per_share,
        )
        return impact

    except Exception as exc:
        logger.debug("whatIfOrder failed for %s %s %d: %s", action, symbol, qty, exc)
        return None


def compute_pm_max_shares(
    ib: Any,
    symbol: str,
    action: str,
    excess_liquidity: float,
    margin_budget_pct: float = 0.08,
    entry_price: float = 0.0,
    timeout_sec: float = 5.0,
) -> Optional[int]:
    """Compute the maximum shares affordable within a margin budget.

    Uses ``query_margin_impact()`` to get per-share margin cost, then divides
    the margin budget (``excess_liquidity * margin_budget_pct``) by that cost.

    Returns None if the margin query fails (caller should use static caps).
    """
    if excess_liquidity <= 0 or margin_budget_pct <= 0:
        return None

    impact = query_margin_impact(ib, symbol, action, qty=100, timeout_sec=timeout_sec)
    if impact is None or impact.maint_margin_per_share <= 0:
        return None

    budget = excess_liquidity * margin_budget_pct
    max_shares = int(math.floor(budget / impact.maint_margin_per_share))

    if max_shares < 1:
        logger.debug(
            "PM budget $%.0f (%.0f%% of EL $%.0f) too small for %s at "
            "$%.2f maint/share",
            budget, margin_budget_pct * 100, excess_liquidity,
            symbol, impact.maint_margin_per_share,
        )
        return 0

    logger.debug(
        "PM max shares for %s: %d (budget $%.0f / $%.2f per share)",
        symbol, max_shares, budget, impact.maint_margin_per_share,
    )
    return max_shares


def get_excess_liquidity(ib: Any) -> Optional[float]:
    """Read ExcessLiquidity from IB account values.  Returns None on failure."""
    if ib is None or not ib.isConnected():
        return None
    try:
        for av in ib.accountValues():
            if getattr(av, "tag", "") == "ExcessLiquidity" and getattr(av, "currency", "") == "USD":
                return float(av.value)
    except Exception as exc:
        logger.debug("Could not read ExcessLiquidity: %s", exc)
    return None


def _parse_margin_value(raw: Any) -> Optional[float]:
    """Parse a margin string from whatIfOrder (IB sometimes returns empty or '1.7976931348623157E308')."""
    if raw is None or raw == "":
        return None
    try:
        val = float(raw)
        if val > 1e300:
            return None
        return abs(val)
    except (TypeError, ValueError):
        return None
