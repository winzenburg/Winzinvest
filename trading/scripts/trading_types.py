"""
Shared type definitions for signals, orders, positions, and execution records.

Use these in function signatures and when reading/writing JSON so the AI and
tools generate consistent, explicit code. Import from types when in trading/scripts.
"""

from typing import Any, Literal, TypedDict

try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired  # Python < 3.11

# ----- Signals (screener output / executor input) -----


class ShortCandidate(TypedDict):
    """One short candidate from the screener (watchlist_multimode short lists)."""
    symbol: str
    price: float
    score: NotRequired[float]  # e.g. rs_pct
    momentum: NotRequired[float]  # e.g. recent_return


class LongCandidate(TypedDict):
    """One long candidate from the long screener (watchlist_longs.json)."""
    symbol: str
    price: float
    rs_pct: NotRequired[float]
    recent_return: NotRequired[float]
    reason: NotRequired[str]
    mtf_score: NotRequired[float]
    earnings_boost: NotRequired[float]
    earnings_date: NotRequired[str]
    sector_multiplier: NotRequired[float]
    sector: NotRequired[str]
    hybrid_score: NotRequired[float]
    composite: NotRequired[float]
    structure: NotRequired[float]
    rvol_atr: NotRequired[float]


# ----- Execution log (audit trail) -----


SignalType = Literal["SHORT", "LONG"]
OrderAction = Literal["BUY", "SELL"]


class ExecutionRecord(TypedDict, total=False):
    """One line in the shared execution log (executions.json)."""
    symbol: str
    type: SignalType
    source_script: str
    timestamp: str
    status: str
    action: NotRequired[OrderAction]
    orderId: NotRequired[int]
    quantity: NotRequired[int]
    entry_price: NotRequired[float]
    stop_price: NotRequired[float]
    profit_price: NotRequired[float]
    score: NotRequired[float]
    momentum: NotRequired[float]
    reason: NotRequired[str]  # e.g. SKIPPED reason


# ----- Regime and allocation -----


RegimeType = Literal["STRONG_DOWNTREND", "MIXED", "STRONG_UPTREND", "CHOPPY", "UNFAVORABLE"]


class Allocation(TypedDict):
    """Regime-based allocation caps per side (independent, do NOT sum to 1.0)."""
    shorts: float
    longs: float


# ----- Position snapshot (for portfolio / sector exposure) -----


class PositionSnapshot(TypedDict, total=False):
    """Minimal position info (e.g. from IB or a snapshot file)."""
    symbol: str
    position: int  # signed: negative = short
    marketValue: float
    marketPrice: NotRequired[float]


# ----- Webhook payload (TradingView or other) -----


class WebhookPayload(TypedDict, total=False):
    """Expected shape of a TradingView (or similar) webhook body. Validate before use."""
    symbol: str
    action: NotRequired[str]  # e.g. "buy" / "sell"
    side: NotRequired[str]   # e.g. "long" / "short"
    quantity: NotRequired[float]
    qty: NotRequired[float]
    order_type: NotRequired[str]  # e.g. "market", "limit"
    price: NotRequired[float]
    limit_price: NotRequired[float]
    strategy: NotRequired[str]
    source: NotRequired[str]


def is_valid_short_candidate(obj: Any) -> bool:
    """Type guard: dict has symbol and price suitable for a short candidate."""
    if not isinstance(obj, dict):
        return False
    s = obj.get("symbol")
    p = obj.get("price")
    return isinstance(s, str) and len(s.strip()) > 0 and isinstance(p, (int, float)) and float(p) > 0


def is_valid_long_candidate(obj: Any) -> bool:
    """Type guard: dict has symbol and price suitable for a long candidate."""
    if not isinstance(obj, dict):
        return False
    s = obj.get("symbol")
    p = obj.get("price")
    return isinstance(s, str) and len(s.strip()) > 0 and isinstance(p, (int, float)) and float(p) > 0
