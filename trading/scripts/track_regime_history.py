#!/usr/bin/env python3
"""
Track Regime History — Timeline Data Generation

Maintains a running log of regime transitions for visualization.
Appends to logs/regime_history.jsonl (one entry per change).

Runs every time regime detection runs (daily via scheduler).
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from paths import TRADING_DIR

logger = logging.getLogger(__name__)

REGIME_CONTEXT = TRADING_DIR / "logs" / "regime_context.json"
REGIME_HISTORY = TRADING_DIR / "logs" / "regime_history.jsonl"
REGIME_STATE = TRADING_DIR / "logs" / "regime_state.json"


def load_current_regime() -> Optional[Dict[str, Any]]:
    """Load current execution regime from regime_context.json."""
    if not REGIME_CONTEXT.exists():
        return None
    
    try:
        data = json.loads(REGIME_CONTEXT.read_text())
        return {
            "regime": data.get("regime"),
            "note": data.get("note"),
            "updated_at": data.get("updated_at"),
        }
    except Exception as e:
        logger.warning("Could not load regime context: %s", e)
        return None


def load_last_recorded_regime() -> Optional[str]:
    """Get the most recent regime from history log."""
    if not REGIME_HISTORY.exists():
        return None
    
    try:
        lines = REGIME_HISTORY.read_text().strip().splitlines()
        if not lines:
            return None
        
        last_line = lines[-1]
        obj = json.loads(last_line)
        return obj.get("regime")
    
    except Exception as e:
        logger.warning("Could not load regime history: %s", e)
        return None


def append_regime_change(regime: str, note: str) -> None:
    """Append new regime entry to history log."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "regime": regime,
        "note": note,
    }
    
    try:
        REGIME_HISTORY.parent.mkdir(parents=True, exist_ok=True)
        
        with REGIME_HISTORY.open("a") as f:
            f.write(json.dumps(entry) + "\n")
        
        logger.info("✓ Regime change recorded: %s", regime)
    
    except Exception as e:
        logger.error("Failed to append regime history: %s", e)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    
    logger.info("Checking for regime changes...")
    
    try:
        current = load_current_regime()
        if not current or not current.get("regime"):
            logger.warning("No current regime found")
            return 1
        
        current_regime = current["regime"]
        last_regime = load_last_recorded_regime()
        
        # Record if first run or regime changed
        if last_regime is None:
            logger.info("First regime tracking run — recording: %s", current_regime)
            append_regime_change(current_regime, current.get("note", ""))
        
        elif last_regime != current_regime:
            logger.info("Regime changed: %s → %s", last_regime, current_regime)
            append_regime_change(current_regime, current.get("note", ""))
        
        else:
            logger.info("No regime change (still %s)", current_regime)
    
    except Exception as e:
        logger.error("Failed to track regime: %s", e, exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
