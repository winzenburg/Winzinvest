#!/usr/bin/env python3
"""
Pre-Trade Guard — Cross-strategy position flip prevention.

Call assert_no_flip() before placing ANY directional stock order.
If the order would flip an existing position to the opposite side,
it raises PreTradeViolation and logs a critical alert.

Usage (in any executor):

    from pre_trade_guard import assert_no_flip, PreTradeViolation

    try:
        assert_no_flip(ib, symbol="AAPL", intended_side="SHORT")
    except PreTradeViolation as e:
        logger.error(str(e))
        return  # skip the trade

Background:
    The dual-mode executor once shorted symbols that the MR executor held long,
    causing accidental position flips (NIO, GUSH, AAPL — Mar 2026). This module
    is the single authoritative guard against that class of error.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class PreTradeViolation(RuntimeError):
    """Raised when an order would flip an existing position to the opposite side."""


def _get_position(ib: Any, symbol: str) -> float:
    """Return current net position quantity for a stock symbol. 0.0 if not held."""
    try:
        for pos in ib.positions():
            contract = getattr(pos, "contract", None)
            if contract is None:
                continue
            if getattr(contract, "secType", "") != "STK":
                continue
            if getattr(contract, "symbol", "").upper() == symbol.upper():
                qty = getattr(pos, "position", 0)
                return float(qty) if qty is not None else 0.0
    except Exception as exc:
        logger.warning("pre_trade_guard: could not fetch positions for %s: %s", symbol, exc)
    return 0.0


def assert_no_flip(ib: Any, symbol: str, intended_side: str) -> None:
    """
    Raise PreTradeViolation if the intended order would flip the existing position.

    Args:
        ib:             Connected ib_insync.IB instance.
        symbol:         Ticker symbol (case-insensitive).
        intended_side:  'LONG' / 'BUY' or 'SHORT' / 'SELL'.

    Raises:
        PreTradeViolation: when current position is on the opposite side.
        ValueError:         when intended_side is not recognised.
    """
    side = intended_side.upper()
    if side in ("LONG", "BUY"):
        going_long = True
    elif side in ("SHORT", "SELL"):
        going_long = False
    else:
        raise ValueError(f"intended_side must be LONG/BUY or SHORT/SELL, got: {intended_side!r}")

    current_qty = _get_position(ib, symbol)

    if current_qty > 0 and not going_long:
        msg = (
            f"PRE-TRADE VIOLATION: cannot open SHORT on {symbol} — "
            f"currently held LONG ({current_qty:+.0f} shares). "
            f"Close the long first before shorting."
        )
        logger.critical(msg)
        try:
            from notifications import notify_critical
            notify_critical("Pre-Trade Flip Blocked", msg)
        except Exception:
            pass
        raise PreTradeViolation(msg)

    if current_qty < 0 and going_long:
        msg = (
            f"PRE-TRADE VIOLATION: cannot open LONG on {symbol} — "
            f"currently held SHORT ({current_qty:+.0f} shares). "
            f"Close the short first before going long."
        )
        logger.critical(msg)
        try:
            from notifications import notify_critical
            notify_critical("Pre-Trade Flip Blocked", msg)
        except Exception:
            pass
        raise PreTradeViolation(msg)

    # All clear
    side_label = "LONG" if going_long else "SHORT"
    logger.debug(
        "pre_trade_guard: %s %s OK (current_qty=%+.0f)",
        side_label, symbol.upper(), current_qty,
    )
