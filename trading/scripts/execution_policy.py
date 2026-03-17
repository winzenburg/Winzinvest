"""
Execution policy layer — strategy code declares intent, broker layer decides order construction.

This module defines the ExecutionPolicy enum and the OrderIntent domain model.
Strategy code imports only from this module to express what it wants done.
The order_factory translates OrderIntent + policy into concrete IBKR orders.

No ib_insync imports are allowed in this file.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Literal, Optional

try:
    from typing import NotRequired, TypedDict
except ImportError:
    from typing_extensions import NotRequired, TypedDict  # Python < 3.11

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Execution policy enum
# ---------------------------------------------------------------------------

class ExecutionPolicy(str, Enum):
    """How urgently / carefully the broker layer should execute an order.

    Strategy code picks one of these; the order_factory translates it into
    the concrete IBKR order type, TIF, algo params, etc.
    """

    PASSIVE_ENTRY = "passive_entry"
    """Limit at bid (or bid + 1 tick).  GTC.  No urgency."""

    AGGRESSIVE_ENTRY = "aggressive_entry"
    """Limit at ask.  DAY.  Fill-or-revise logic."""

    SPREAD_AWARE_ENTRY = "spread_aware_entry"
    """IB Adaptive algo, patience=Normal.  Works the spread."""

    BRACKETED_SWING_ENTRY = "bracketed_swing_entry"
    """Parent limit + child stop + child take-profit.  OCA group."""

    URGENT_EXIT = "urgent_exit"
    """Market order, DAY.  Only for margin relief or stop-triggered exits."""

    NORMAL_EXIT = "normal_exit"
    """Limit at bid (sells) or ask (covers).  DAY."""

    STOP_PROTECT = "stop_protect"
    """Stop-limit: trigger at stop price, limit = stop − 1 tick."""

    TRAILING_STOP = "trailing_stop"
    """Trailing stop with configurable trail amount.  GTC."""


# ---------------------------------------------------------------------------
# Order side
# ---------------------------------------------------------------------------

OrderSide = Literal["BUY", "SELL"]


# ---------------------------------------------------------------------------
# Order lifecycle states
# ---------------------------------------------------------------------------

class OrderStatus(str, Enum):
    """Explicit state-machine states for order lifecycle."""

    CREATED = "created"
    """Intent recorded locally; not yet sent to broker."""

    SUBMITTED = "submitted"
    """Sent to broker; awaiting acknowledgement."""

    ACKNOWLEDGED = "acknowledged"
    """Broker accepted; order is live on the exchange."""

    PARTIALLY_FILLED = "partially_filled"
    """Some shares filled; remainder still working."""

    FILLED = "filled"
    """Fully filled."""

    CANCELLED = "cancelled"
    """Cancelled by us or broker."""

    REJECTED = "rejected"
    """Broker rejected the order."""

    CANCEL_PENDING = "cancel_pending"
    """Cancel request sent; awaiting confirmation."""

    ERROR = "error"
    """Unrecoverable error during lifecycle."""


# Valid state transitions — the state store enforces these.
VALID_TRANSITIONS: Dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.CREATED: frozenset({OrderStatus.SUBMITTED, OrderStatus.CANCELLED, OrderStatus.ERROR}),
    OrderStatus.SUBMITTED: frozenset({OrderStatus.ACKNOWLEDGED, OrderStatus.REJECTED, OrderStatus.CANCELLED, OrderStatus.ERROR}),
    OrderStatus.ACKNOWLEDGED: frozenset({OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED, OrderStatus.CANCEL_PENDING, OrderStatus.CANCELLED, OrderStatus.ERROR}),
    OrderStatus.PARTIALLY_FILLED: frozenset({OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED, OrderStatus.CANCEL_PENDING, OrderStatus.CANCELLED, OrderStatus.ERROR}),
    OrderStatus.CANCEL_PENDING: frozenset({OrderStatus.CANCELLED, OrderStatus.FILLED, OrderStatus.ERROR}),
    OrderStatus.FILLED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
    OrderStatus.REJECTED: frozenset(),
    OrderStatus.ERROR: frozenset(),
}


def is_terminal(status: OrderStatus) -> bool:
    """True if the order is in a final state and will not transition further."""
    return status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.ERROR)


def validate_transition(current: OrderStatus, target: OrderStatus) -> bool:
    """Return True if transitioning from *current* to *target* is valid."""
    return target in VALID_TRANSITIONS.get(current, frozenset())


# ---------------------------------------------------------------------------
# OrderIntent — the domain object that strategy code produces
# ---------------------------------------------------------------------------

class OrderIntent(TypedDict):
    """What the strategy wants done.  No broker concepts."""

    intent_id: str
    """Deterministic, unique key for this order intent.
    Generated via generate_intent_id().  Prevents duplicates across
    retries, reconnects, and restarts."""

    symbol: str
    """Ticker symbol (resolved to ConId by contract_cache before submission)."""

    side: OrderSide
    """BUY or SELL."""

    quantity: int
    """Number of shares / contracts."""

    policy: ExecutionPolicy
    """How to execute — the order_factory translates this to an IBKR order."""

    source_script: str
    """Which executor created this intent (for audit trail)."""

    # -- Optional fields --

    sec_type: NotRequired[str]
    """Security type: "STK" (default) or "OPT".  When "OPT", the options
    fields (expiry, strike, right) are required and the router resolves
    the contract via ContractCache.resolve_option()."""

    expiry: NotRequired[str]
    """Option expiration in YYYYMMDD format.  Required when sec_type="OPT"."""

    strike: NotRequired[float]
    """Option strike price.  Required when sec_type="OPT"."""

    right: NotRequired[str]
    """Option right: "C" (call) or "P" (put).  Required when sec_type="OPT"."""

    limit_price: NotRequired[Optional[float]]
    """Reference price for limit-based policies.  Required for PASSIVE_ENTRY,
    AGGRESSIVE_ENTRY, STOP_PROTECT.  Ignored for URGENT_EXIT."""

    stop_price: NotRequired[Optional[float]]
    """Stop trigger price for STOP_PROTECT and BRACKETED_SWING_ENTRY."""

    take_profit_price: NotRequired[Optional[float]]
    """Take-profit limit for BRACKETED_SWING_ENTRY."""

    trail_amount: NotRequired[Optional[float]]
    """Dollar trail amount for TRAILING_STOP policy."""

    outside_rth: NotRequired[bool]
    """Whether the order should be active outside regular trading hours."""

    metadata: NotRequired[Dict[str, Any]]
    """Arbitrary strategy metadata (regime, conviction, scores) for logging.
    Never read by the broker layer."""


# ---------------------------------------------------------------------------
# Intent ID generation
# ---------------------------------------------------------------------------

def generate_intent_id(
    symbol: str,
    side: OrderSide,
    policy: ExecutionPolicy,
    source_script: str,
    date_str: Optional[str] = None,
    sequence: int = 0,
    *,
    sec_type: str = "STK",
    expiry: str = "",
    strike: float = 0.0,
    right: str = "",
) -> str:
    """Create a deterministic, unique intent ID.

    The ID is a short hash of (symbol, side, policy, source, date, sequence)
    plus options fields when ``sec_type="OPT"``.  Two calls with the same
    inputs produce the same ID — this is the idempotency guarantee.

    Returns a string like ``NVDA-BUY-passive_entry-20260307-0-a1b2c3d4``.
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")

    raw = f"{symbol.upper()}|{side}|{policy.value}|{source_script}|{date_str}|{sequence}"
    if sec_type == "OPT":
        raw += f"|OPT|{expiry}|{strike}|{right.upper()}"
    digest = hashlib.sha256(raw.encode()).hexdigest()[:8]
    return f"{symbol.upper()}-{side}-{policy.value}-{date_str}-{sequence}-{digest}"


# ---------------------------------------------------------------------------
# Helper: build an OrderIntent safely
# ---------------------------------------------------------------------------

def build_intent(
    *,
    symbol: str,
    side: OrderSide,
    quantity: int,
    policy: ExecutionPolicy,
    source_script: str,
    sec_type: str = "STK",
    expiry: Optional[str] = None,
    strike: Optional[float] = None,
    right: Optional[str] = None,
    limit_price: Optional[float] = None,
    stop_price: Optional[float] = None,
    take_profit_price: Optional[float] = None,
    trail_amount: Optional[float] = None,
    outside_rth: bool = False,
    sequence: int = 0,
    metadata: Optional[Dict[str, Any]] = None,
) -> OrderIntent:
    """Construct and validate an OrderIntent.

    For options, pass ``sec_type="OPT"`` along with ``expiry`` (YYYYMMDD),
    ``strike``, and ``right`` ("C" or "P").

    Raises ValueError if required fields for the chosen policy are missing,
    or if options fields are incomplete.
    """
    symbol = symbol.strip().upper()
    sec_type = sec_type.strip().upper()
    if quantity <= 0:
        raise ValueError(f"quantity must be positive, got {quantity}")

    if sec_type == "OPT":
        if not expiry or strike is None or not right:
            raise ValueError(
                "Options intents (sec_type='OPT') require expiry, strike, and right"
            )
        right = right.strip().upper()
        if right not in ("C", "P"):
            raise ValueError(f"right must be 'C' or 'P', got '{right}'")

    _validate_policy_fields(policy, limit_price, stop_price, trail_amount)

    intent_id = generate_intent_id(
        symbol, side, policy, source_script,
        sequence=sequence,
        sec_type=sec_type,
        expiry=expiry or "",
        strike=strike or 0.0,
        right=right or "",
    )

    intent: OrderIntent = {
        "intent_id": intent_id,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "policy": policy,
        "source_script": source_script,
    }

    if sec_type == "OPT":
        intent["sec_type"] = "OPT"
        intent["expiry"] = expiry  # type: ignore[assignment]
        intent["strike"] = strike  # type: ignore[assignment]
        intent["right"] = right  # type: ignore[assignment]

    if limit_price is not None:
        intent["limit_price"] = limit_price
    if stop_price is not None:
        intent["stop_price"] = stop_price
    if take_profit_price is not None:
        intent["take_profit_price"] = take_profit_price
    if trail_amount is not None:
        intent["trail_amount"] = trail_amount
    if outside_rth:
        intent["outside_rth"] = True
    if metadata:
        intent["metadata"] = metadata

    return intent


def _validate_policy_fields(
    policy: ExecutionPolicy,
    limit_price: Optional[float],
    stop_price: Optional[float],
    trail_amount: Optional[float],
) -> None:
    """Raise ValueError when required price fields are missing for a policy."""

    needs_limit = {
        ExecutionPolicy.PASSIVE_ENTRY,
        ExecutionPolicy.AGGRESSIVE_ENTRY,
        ExecutionPolicy.NORMAL_EXIT,
        ExecutionPolicy.BRACKETED_SWING_ENTRY,
    }
    needs_stop = {
        ExecutionPolicy.STOP_PROTECT,
        ExecutionPolicy.BRACKETED_SWING_ENTRY,
    }
    needs_trail = {
        ExecutionPolicy.TRAILING_STOP,
    }

    if policy in needs_limit and limit_price is None:
        raise ValueError(f"Policy {policy.value} requires limit_price")
    if policy in needs_stop and stop_price is None:
        raise ValueError(f"Policy {policy.value} requires stop_price")
    if policy in needs_trail and trail_amount is None:
        raise ValueError(f"Policy {policy.value} requires trail_amount")
