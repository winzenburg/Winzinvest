"""Shared paths for agents (trading dir, logs, state files)."""
from paths import TRADING_DIR, LOGS_DIR

KILL_SWITCH_FILE = TRADING_DIR / "kill_switch.json"
LAST_SIGNAL_FILE = LOGS_DIR / "last_signal.json"
EXECUTIONS_LOG = LOGS_DIR / "executions.json"
RECENT_SIGNALS_FILE = LOGS_DIR / "recent_signal_ids.json"
