#!/usr/bin/env python3
"""Poll ib_insync order status until fill or timeout (synchronous)."""

from __future__ import annotations

import os
import time
from typing import Tuple

_FILLED_OK = frozenset({"Filled", "PartiallyFilled"})


def wait_ib_order_filled(ib, trade, max_sec: int | None = None) -> Tuple[bool, str]:
    """
    Poll until Filled/PartiallyFilled or timeout.

    Returns (True, status) when filled (full or partial); (False, last_status) on timeout
    or if the order reaches a terminal non-fill state before the loop ends (last status
    is still returned at timeout — callers may inspect trade.log for cancellations).
    """
    if max_sec is None:
        max_sec = int(os.environ.get("IB_ORDER_FILL_WAIT_SEC", "30"))
    deadline = time.time() + float(max_sec)
    while time.time() < deadline:
        ib.sleep(0.5)
        status = getattr(trade.orderStatus, "status", "") or ""
        if status in _FILLED_OK:
            return True, status
    status = getattr(trade.orderStatus, "status", "") or ""
    return False, status
