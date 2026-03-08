"""
Centralized path configuration for the trading system.

All scripts import TRADING_DIR from here instead of hardcoding paths.

Resolution order:
  1. TRADING_HOME environment variable (if set)
  2. The project's trading/ directory (auto-detected from this file's location)

Set TRADING_HOME in .env or your shell profile to override, e.g.:
  export TRADING_HOME=/Users/ryanwinzenburg/path/to/trading
"""

import os
from pathlib import Path


def _resolve_trading_dir() -> Path:
    env = os.environ.get("TRADING_HOME")
    if env:
        p = Path(env).expanduser().resolve()
        if p.exists():
            return p

    # This file lives at trading/scripts/paths.py → parent.parent = trading/
    return Path(__file__).resolve().parent.parent


TRADING_DIR: Path = _resolve_trading_dir()
WORKSPACE: Path = TRADING_DIR.parent
SCRIPTS_DIR: Path = TRADING_DIR / "scripts"
LOGS_DIR: Path = TRADING_DIR / "logs"
WATCHLISTS_DIR: Path = TRADING_DIR / "watchlists"
RISK_JSON: Path = TRADING_DIR / "risk.json"

LOGS_DIR.mkdir(parents=True, exist_ok=True)
WATCHLISTS_DIR.mkdir(parents=True, exist_ok=True)
