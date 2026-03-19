#!/usr/bin/env python3
"""Central kill-switch check for trading executors."""

from __future__ import annotations

import json
from pathlib import Path


def kill_switch_active(trading_dir: Path | None = None) -> bool:
    """
    Return True if kill_switch.json exists with active=True.

    On missing file: False. On unreadable JSON: True (fail-closed).
    """
    try:
        from paths import TRADING_DIR as _td

        root = trading_dir if trading_dir is not None else _td
        path = Path(root) / "kill_switch.json"
        if not path.exists():
            return False
        data = json.loads(path.read_text(encoding="utf-8"))
        return bool(data.get("active"))
    except Exception:
        return True
