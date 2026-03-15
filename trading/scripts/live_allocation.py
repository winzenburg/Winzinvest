#!/usr/bin/env python3
"""
Live Allocation Helper

Caps all position-sizing equity to LIVE_ALLOCATION_PCT of the real NLV.
On paper trading (default), the full NLV is used (LIVE_ALLOCATION_PCT=1.0).
On live trading with 10% allocation, every executor treats the account as
NLV * 0.10 for sizing, risk checks, and notional caps.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_TRADING_DIR = Path(__file__).resolve().parents[1]
_env_path = _TRADING_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

LIVE_ALLOCATION_PCT = float(os.getenv("LIVE_ALLOCATION_PCT", "1.0"))
TRADING_MODE = os.getenv("TRADING_MODE", "paper")

if not (0.0 < LIVE_ALLOCATION_PCT <= 1.0):
    raise ValueError(
        f"LIVE_ALLOCATION_PCT must be in (0.0, 1.0], got {LIVE_ALLOCATION_PCT}"
    )


def get_effective_equity(raw_nlv: float) -> float:
    """Return the portion of NLV available for sizing under the current allocation.

    On paper (LIVE_ALLOCATION_PCT=1.0) this is a no-op.
    On live with 10% allocation, a $2M NLV returns $200k.
    """
    capped = raw_nlv * LIVE_ALLOCATION_PCT
    if LIVE_ALLOCATION_PCT < 1.0:
        logger.info(
            "Live allocation: %.1f%% of $%.0f → effective equity $%.0f",
            LIVE_ALLOCATION_PCT * 100,
            raw_nlv,
            capped,
        )
    return capped
