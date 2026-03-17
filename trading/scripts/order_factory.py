"""
Order factory — pure function: OrderIntent + policy → IBKR order object(s).

This is one of the few modules permitted to import ib_insync.
Strategy code must never import from this module directly; the
order_router is the only consumer.

Design principles:
  - Pure function: no side effects, no network calls, no state mutation.
  - Every order gets the intent_id stamped into orderRef for reconciliation.
  - Tick-size rounding via configurable rules (defaults to 0.01).
  - outsideRth flags read from the intent, not from risk.json (the strategy
    layer already decided that when building the intent).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from ib_insync import LimitOrder, MarketOrder, Order, TagValue

from contract_cache import ResolvedContract
from execution_policy import ExecutionPolicy, OrderIntent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_TICK_SIZE = 0.01
OPTIONS_TICK_SIZE = 0.05

# IB Adaptive algo parameters
ADAPTIVE_PRIORITY_NORMAL = "Normal"
ADAPTIVE_PRIORITY_PATIENT = "Patient"
ADAPTIVE_PRIORITY_URGENT = "Urgent"


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class BuiltOrder:
    """One or more IBKR orders produced from a single OrderIntent."""

    intent_id: str
    parent: Order
    children: List[Order]
    resolved_contract: ResolvedContract

    @property
    def all_orders(self) -> List[Order]:
        return [self.parent] + self.children


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_orders(
    intent: OrderIntent,
    resolved: ResolvedContract,
    tick_size: float = DEFAULT_TICK_SIZE,
    bid: Optional[float] = None,
    ask: Optional[float] = None,
) -> BuiltOrder:
    """Translate an OrderIntent + execution policy into concrete IBKR orders.

    Parameters
    ----------
    intent : OrderIntent
        The strategy's declared intent.
    resolved : ResolvedContract
        The fully-qualified contract from the contract cache.
    tick_size : float
        Minimum price increment for rounding.
    bid, ask : float, optional
        Current bid/ask prices.  Required for PASSIVE_ENTRY and
        AGGRESSIVE_ENTRY to pick the right price level.  If not provided,
        falls back to the intent's limit_price.

    Returns
    -------
    BuiltOrder
        Contains the parent order and any child orders (stops, TPs).

    Raises
    ------
    ValueError
        If the intent is missing required fields for its policy.
    """
    if tick_size == DEFAULT_TICK_SIZE and resolved.sec_type == "OPT":
        tick_size = OPTIONS_TICK_SIZE

    policy = intent["policy"]
    builder = _POLICY_BUILDERS.get(policy)
    if builder is None:
        raise ValueError(f"No builder registered for policy: {policy}")

    return builder(intent, resolved, tick_size, bid, ask)


# ---------------------------------------------------------------------------
# Policy builders (private)
# ---------------------------------------------------------------------------


def _build_passive_entry(
    intent: OrderIntent, resolved: ResolvedContract,
    tick_size: float, bid: Optional[float], ask: Optional[float],
) -> BuiltOrder:
    """Limit at bid (or bid + 1 tick for buys, ask − 1 tick for sells). GTC."""
    side = intent["side"]
    qty = intent["quantity"]
    limit = intent.get("limit_price")

    if bid is not None and side == "BUY":
        limit = bid
    elif ask is not None and side == "SELL":
        limit = ask
    if limit is None:
        raise ValueError("PASSIVE_ENTRY requires limit_price or bid/ask")

    limit = _round_to_tick(limit, tick_size)
    order = LimitOrder(side, qty, limit)
    order.tif = "GTC"
    _stamp(order, intent)
    return BuiltOrder(intent["intent_id"], order, [], resolved)


def _build_aggressive_entry(
    intent: OrderIntent, resolved: ResolvedContract,
    tick_size: float, bid: Optional[float], ask: Optional[float],
) -> BuiltOrder:
    """Limit at ask (buys) or bid (sells). DAY. Fill-or-revise."""
    side = intent["side"]
    qty = intent["quantity"]
    limit = intent.get("limit_price")

    if ask is not None and side == "BUY":
        limit = ask
    elif bid is not None and side == "SELL":
        limit = bid
    if limit is None:
        raise ValueError("AGGRESSIVE_ENTRY requires limit_price or bid/ask")

    limit = _round_to_tick(limit, tick_size)
    order = LimitOrder(side, qty, limit)
    order.tif = "DAY"
    _stamp(order, intent)
    return BuiltOrder(intent["intent_id"], order, [], resolved)


def _build_spread_aware_entry(
    intent: OrderIntent, resolved: ResolvedContract,
    tick_size: float, bid: Optional[float], ask: Optional[float],
) -> BuiltOrder:
    """IB Adaptive algo with patience=Normal. Works the spread."""
    side = intent["side"]
    qty = intent["quantity"]
    limit = intent.get("limit_price")

    if limit is None:
        if side == "BUY" and ask is not None:
            limit = ask
        elif side == "SELL" and bid is not None:
            limit = bid
    if limit is None:
        raise ValueError("SPREAD_AWARE_ENTRY requires limit_price or bid/ask")

    limit = _round_to_tick(limit, tick_size)
    order = LimitOrder(side, qty, limit)
    order.tif = "DAY"
    order.algoStrategy = "Adaptive"
    order.algoParams = [TagValue("adaptivePriority", ADAPTIVE_PRIORITY_NORMAL)]
    _stamp(order, intent)
    return BuiltOrder(intent["intent_id"], order, [], resolved)


def _build_bracketed_swing_entry(
    intent: OrderIntent, resolved: ResolvedContract,
    tick_size: float, bid: Optional[float], ask: Optional[float],
) -> BuiltOrder:
    """Parent limit + child stop + child take-profit, linked via OCA group."""
    side = intent["side"]
    qty = intent["quantity"]
    limit = intent.get("limit_price")
    stop = intent.get("stop_price")
    tp = intent.get("take_profit_price")

    if limit is None or stop is None:
        raise ValueError("BRACKETED_SWING_ENTRY requires limit_price and stop_price")

    limit = _round_to_tick(limit, tick_size)
    oca_group = f"bracket-{intent['intent_id']}"

    parent = LimitOrder(side, qty, limit)
    parent.tif = "GTC"
    parent.transmit = False
    _stamp(parent, intent)

    exit_side: str = "SELL" if side == "BUY" else "BUY"
    children: List[Order] = []

    stop_order = Order()
    stop_order.action = exit_side
    stop_order.orderType = "STP"
    stop_order.totalQuantity = qty
    stop_order.auxPrice = _round_to_tick(stop, tick_size)
    stop_order.tif = "GTC"
    stop_order.ocaGroup = oca_group
    stop_order.ocaType = 1
    stop_order.transmit = tp is None
    _stamp(stop_order, intent, suffix="stop")
    children.append(stop_order)

    if tp is not None:
        tp_order = LimitOrder(exit_side, qty, _round_to_tick(tp, tick_size))
        tp_order.tif = "GTC"
        tp_order.ocaGroup = oca_group
        tp_order.ocaType = 1
        tp_order.transmit = True
        _stamp(tp_order, intent, suffix="tp")
        children.append(tp_order)

    return BuiltOrder(intent["intent_id"], parent, children, resolved)


def _build_urgent_exit(
    intent: OrderIntent, resolved: ResolvedContract,
    tick_size: float, bid: Optional[float], ask: Optional[float],
) -> BuiltOrder:
    """Market order. DAY. Only for margin relief or stop-triggered exits."""
    order = MarketOrder(intent["side"], intent["quantity"])
    order.tif = "DAY"
    _stamp(order, intent)
    return BuiltOrder(intent["intent_id"], order, [], resolved)


def _build_normal_exit(
    intent: OrderIntent, resolved: ResolvedContract,
    tick_size: float, bid: Optional[float], ask: Optional[float],
) -> BuiltOrder:
    """Limit at bid (sells) or ask (covers). DAY."""
    side = intent["side"]
    qty = intent["quantity"]
    limit = intent.get("limit_price")

    if side == "SELL" and bid is not None:
        limit = bid
    elif side == "BUY" and ask is not None:
        limit = ask
    if limit is None:
        raise ValueError("NORMAL_EXIT requires limit_price or bid/ask")

    limit = _round_to_tick(limit, tick_size)
    order = LimitOrder(side, qty, limit)
    order.tif = "DAY"
    _stamp(order, intent)
    return BuiltOrder(intent["intent_id"], order, [], resolved)


def _build_stop_protect(
    intent: OrderIntent, resolved: ResolvedContract,
    tick_size: float, bid: Optional[float], ask: Optional[float],
) -> BuiltOrder:
    """Stop-limit: trigger at stop price, limit = stop − 1 tick."""
    side = intent["side"]
    qty = intent["quantity"]
    stop = intent.get("stop_price")
    if stop is None:
        raise ValueError("STOP_PROTECT requires stop_price")

    stop = _round_to_tick(stop, tick_size)
    if side == "SELL":
        limit = _round_to_tick(stop - tick_size, tick_size)
    else:
        limit = _round_to_tick(stop + tick_size, tick_size)

    order = Order()
    order.action = side
    order.orderType = "STP LMT"
    order.totalQuantity = qty
    order.auxPrice = stop
    order.lmtPrice = limit
    order.tif = "GTC"
    _stamp(order, intent)
    return BuiltOrder(intent["intent_id"], order, [], resolved)


def _build_trailing_stop(
    intent: OrderIntent, resolved: ResolvedContract,
    tick_size: float, bid: Optional[float], ask: Optional[float],
) -> BuiltOrder:
    """Trailing stop with configurable trail amount. GTC."""
    side = intent["side"]
    qty = intent["quantity"]
    trail = intent.get("trail_amount")
    if trail is None:
        raise ValueError("TRAILING_STOP requires trail_amount")

    order = Order()
    order.action = side
    order.orderType = "TRAIL"
    order.totalQuantity = qty
    order.auxPrice = round(trail, 2)
    order.tif = "GTC"
    _stamp(order, intent)
    if intent.get("outside_rth"):
        order.outsideRth = True
    return BuiltOrder(intent["intent_id"], order, [], resolved)


# ---------------------------------------------------------------------------
# Policy → builder registry
# ---------------------------------------------------------------------------

_POLICY_BUILDERS = {
    ExecutionPolicy.PASSIVE_ENTRY: _build_passive_entry,
    ExecutionPolicy.AGGRESSIVE_ENTRY: _build_aggressive_entry,
    ExecutionPolicy.SPREAD_AWARE_ENTRY: _build_spread_aware_entry,
    ExecutionPolicy.BRACKETED_SWING_ENTRY: _build_bracketed_swing_entry,
    ExecutionPolicy.URGENT_EXIT: _build_urgent_exit,
    ExecutionPolicy.NORMAL_EXIT: _build_normal_exit,
    ExecutionPolicy.STOP_PROTECT: _build_stop_protect,
    ExecutionPolicy.TRAILING_STOP: _build_trailing_stop,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _round_to_tick(price: float, tick_size: float) -> float:
    """Round a price to the nearest valid tick."""
    if tick_size <= 0:
        return round(price, 2)
    return round(round(price / tick_size) * tick_size, 8)


def _stamp(order: Order, intent: OrderIntent, suffix: str = "") -> None:
    """Stamp orderRef with the intent_id for reconciliation and dedup."""
    ref = intent["intent_id"]
    if suffix:
        ref = f"{ref}:{suffix}"
    order.orderRef = ref

    if intent.get("outside_rth") and order.orderType != "MKT":
        order.outsideRth = True
