#!/usr/bin/env python3
"""
RTH (Regular Trading Hours) and Outside RTH order helpers for IBKR.

Reads execution config from risk.json and applies outsideRth to orders so that:
- Take-profit limit orders can fill outside RTH (IBKR "Outside RTH Take-Profit")
- Optionally, entry orders can execute outside RTH (use LimitOrder with outsideRth=True)
- Optionally, stop/trailing orders can trigger outside RTH

IBKR note: Market orders cannot use outsideRth (error 2109). Use LimitOrder for entry when
allow_outside_rth_entry is True.

Usage:
    from order_rth import apply_rth_to_order, get_entry_order
    from risk_config import get_allow_outside_rth_entry, get_outside_rth_take_profit, get_outside_rth_stop

    # Entry: use get_entry_order when you have price (for LimitOrder when outside RTH entry enabled)
    order = get_entry_order("BUY", qty, price, workspace)
    apply_rth_to_order(order, "entry", workspace)
    # Or for TP/stop after creating order:
    tp_order = LimitOrder("SELL", qty, tp_price)
    apply_rth_to_order(tp_order, "take_profit", workspace)
"""

from pathlib import Path
from typing import Any

from risk_config import (
    get_allow_outside_rth_entry,
    get_outside_rth_stop,
    get_outside_rth_take_profit,
)

# Order kinds for apply_rth_to_order
RTH_KIND_ENTRY = "entry"
RTH_KIND_TAKE_PROFIT = "take_profit"
RTH_KIND_STOP = "stop"

# Limit order offset for entry when outside RTH (allow slight slippage so order fills)
# BUY: limit = price * (1 + offset), SELL: limit = price * (1 - offset)
OUTSIDE_RTH_ENTRY_OFFSET = 0.005  # 0.5%


def apply_rth_to_order(
    order: Any,
    kind: str,
    workspace: Path,
) -> None:
    """
    Set outsideRth on an order based on execution config.

    Modifies the order in place. Use for take-profit limit orders and stop/trailing orders.
    For entry, use get_entry_order() which returns the appropriate order type and applies RTH.

    kind: "entry" | "take_profit" | "stop"
    workspace: Path to trading dir (e.g. TRADING_DIR from paths).
    """
    if kind == RTH_KIND_ENTRY:
        if get_allow_outside_rth_entry(workspace):
            setattr(order, "outsideRth", True)
    elif kind == RTH_KIND_TAKE_PROFIT:
        if get_outside_rth_take_profit(workspace):
            setattr(order, "outsideRth", True)
    elif kind == RTH_KIND_STOP:
        if get_outside_rth_stop(workspace):
            setattr(order, "outsideRth", True)


def get_entry_order(
    action: str,
    quantity: int,
    price: float,
    workspace: Path,
) -> Any:
    """
    Return an entry order (MarketOrder or LimitOrder) suitable for RTH and optionally outside RTH.

    When allow_outside_rth_entry is False: returns MarketOrder(action, quantity).
    When allow_outside_rth_entry is True: returns LimitOrder at price with a small offset so the
    order can fill in extended hours (IBKR rejects MarketOrder with outsideRth). Limit is
    price * (1 + 0.5%) for BUY, price * (1 - 0.5%) for SELL.

    Caller must: from ib_insync import MarketOrder, LimitOrder
    """
    from ib_insync import LimitOrder, MarketOrder

    if not get_allow_outside_rth_entry(workspace):
        order = MarketOrder(action, quantity)
        return order

    # Outside RTH entry: use limit order so it can fill in extended hours
    if action.upper() == "BUY":
        limit_price = round(price * (1 + OUTSIDE_RTH_ENTRY_OFFSET), 2)
    else:
        limit_price = round(price * (1 - OUTSIDE_RTH_ENTRY_OFFSET), 2)
    order = LimitOrder(action, quantity, limit_price)
    order.tif = "GTC"
    setattr(order, "outsideRth", True)
    return order
