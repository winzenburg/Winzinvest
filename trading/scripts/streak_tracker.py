"""
Losing streak tracker — tracks consecutive losses and adjusts risk exposure.

Paul Tudor Jones: "Losing begets losing."

When consecutive_losses >= 3: risk_per_trade_pct is halved.
When consecutive_losses >= 5: a cooldown flag pauses new entries for 24 hours.

State is persisted to trading/logs/streak_state.json so it survives restarts.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

from paths import WORKSPACE
STREAK_STATE_FILE = WORKSPACE / "trading" / "logs" / "streak_state.json"

REDUCE_AFTER = 3
PAUSE_AFTER = 5
COOLDOWN_HOURS = 24
SIZE_REDUCTION_FACTOR = 0.5


def _load_state() -> dict:
    try:
        if STREAK_STATE_FILE.exists():
            return json.loads(STREAK_STATE_FILE.read_text())
    except (OSError, ValueError, TypeError):
        pass
    return {"consecutive_losses": 0, "cooldown_until": None, "updated_at": None}


def _save_state(state: dict) -> None:
    try:
        STREAK_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        state["updated_at"] = datetime.now().isoformat()
        STREAK_STATE_FILE.write_text(json.dumps(state, indent=2))
    except OSError as e:
        logger.warning("Could not save streak state: %s", e)


def record_win() -> None:
    """Reset the consecutive loss counter on a winning trade."""
    state = _load_state()
    if state.get("consecutive_losses", 0) > 0:
        logger.info("Winning trade resets consecutive losses from %d to 0", state["consecutive_losses"])
    state["consecutive_losses"] = 0
    state["cooldown_until"] = None
    _save_state(state)


def record_loss() -> None:
    """Increment consecutive loss counter; set cooldown if threshold exceeded."""
    state = _load_state()
    state["consecutive_losses"] = state.get("consecutive_losses", 0) + 1
    losses = state["consecutive_losses"]

    if losses >= PAUSE_AFTER:
        cooldown_end = (datetime.now() + timedelta(hours=COOLDOWN_HOURS)).isoformat()
        state["cooldown_until"] = cooldown_end
        logger.warning(
            "LOSING STREAK: %d consecutive losses — PAUSING new entries until %s",
            losses, cooldown_end,
        )
        try:
            from notifications import notify_critical
            notify_critical(
                "Losing Streak — Trading Paused",
                f"{losses} consecutive losses. New entries paused until {cooldown_end}.",
            )
        except Exception:
            pass
    elif losses >= REDUCE_AFTER:
        logger.warning(
            "LOSING STREAK: %d consecutive losses — reducing size by %.0f%%",
            losses, (1 - SIZE_REDUCTION_FACTOR) * 100,
        )

    _save_state(state)


def get_consecutive_losses() -> int:
    """Return current consecutive loss count."""
    return _load_state().get("consecutive_losses", 0)


def is_on_cooldown() -> bool:
    """Return True if currently in a post-streak cooldown period."""
    state = _load_state()
    cd = state.get("cooldown_until")
    if not cd:
        return False
    try:
        return datetime.now() < datetime.fromisoformat(cd)
    except (ValueError, TypeError):
        return False


def get_streak_risk_multiplier() -> float:
    """Return risk multiplier based on current streak state.

    1.0 = normal, 0.5 = after 3 consecutive losses, 0.0 = on cooldown.
    """
    if is_on_cooldown():
        return 0.0
    losses = get_consecutive_losses()
    if losses >= REDUCE_AFTER:
        return SIZE_REDUCTION_FACTOR
    return 1.0
