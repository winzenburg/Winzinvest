#!/usr/bin/env python3
"""
Signal Validator Agent — sits between TradingView webhook and order execution.

Cross-references incoming signals against: schema, portfolio state, recent signals
(dedup), market hours, and risk limits. Returns allow/reject + reason.
Call this before queuing a signal for execution.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Import from parent scripts dir when run from trading/scripts/
try:
    from execution_gates import check_gap_risk_window
except ImportError:
    check_gap_risk_window = None  # type: ignore

from agents._paths import LAST_SIGNAL_FILE, LOGS_DIR, RECENT_SIGNALS_FILE, TRADING_DIR
from atomic_io import atomic_write_json

# How long to remember a signal id for dedup (seconds)
SIGNAL_DEDUP_TTL_SEC = 300
# Max recent signal ids to keep in file
MAX_RECENT_SIGNAL_IDS = 500
# Stale signal threshold (seconds)
STALE_SIGNAL_SEC = 60


def _load_recent_signal_ids() -> Dict[str, float]:
    """Load { order_id: timestamp_epoch } from file; prune expired."""
    if not RECENT_SIGNALS_FILE.exists():
        return {}
    try:
        data = json.loads(RECENT_SIGNALS_FILE.read_text())
        if not isinstance(data, dict):
            return {}
        now = datetime.now().timestamp()
        cutoff = now - SIGNAL_DEDUP_TTL_SEC
        return {k: v for k, v in data.items() if isinstance(v, (int, float)) and v > cutoff}
    except (OSError, ValueError, TypeError):
        return {}


def _save_recent_signal_ids(ids: Dict[str, float]) -> None:
    """Persist recent signal ids (trim to MAX_RECENT_SIGNAL_IDS)."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    items = sorted(ids.items(), key=lambda x: -x[1])[:MAX_RECENT_SIGNAL_IDS]
    atomic_write_json(RECENT_SIGNALS_FILE, dict(items))


def _is_signal_stale(signal: Dict[str, Any]) -> bool:
    """True if signal timestamp is older than STALE_SIGNAL_SEC."""
    ts = signal.get("timestamp") or signal.get("timenow") or signal.get("time")
    if ts is None:
        return False  # No timestamp → cannot enforce staleness
    try:
        if isinstance(ts, (int, float)):
            t = float(ts)
        else:
            t = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return True
    return (datetime.now().timestamp() - t) > STALE_SIGNAL_SEC


def validate_signal(
    signal: Dict[str, Any],
    *,
    portfolio_shorts: Optional[Set[str]] = None,
    portfolio_longs: Optional[Set[str]] = None,
    secret: Optional[str] = None,
    check_market_hours: bool = True,
    check_dedup: bool = True,
) -> Tuple[bool, str]:
    """
    Decide if a signal is allowed through to execution.
    Returns (allowed, reason). If allowed is False, reason explains why.
    """
    if not isinstance(signal, dict):
        return False, "invalid payload"

    # Schema: require symbol/ticker and action
    symbol = (signal.get("symbol") or signal.get("ticker") or "").strip().upper()
    if not symbol:
        return False, "missing symbol/ticker"
    action = (signal.get("action") or signal.get("side") or "").strip().lower()
    if action not in ("buy", "sell", "long", "short", "close"):
        return False, "missing or invalid action"

    # Optional: shared secret
    if secret is not None and secret != signal.get("secret"):
        return False, "invalid or missing secret"

    # Stale signal
    if _is_signal_stale(signal):
        return False, "signal older than 60s"

    # Dedup: order_id or symbol+action+timestamp
    if check_dedup:
        order_id = signal.get("order_id") or f"{symbol}_{action}_{signal.get('timestamp', '')}"
        recent = _load_recent_signal_ids()
        if order_id in recent:
            return False, "duplicate signal (order_id already seen)"
        recent[order_id] = datetime.now().timestamp()
        _save_recent_signal_ids(recent)

    # Market hours (gap risk)
    if check_market_hours and check_gap_risk_window is not None and not check_gap_risk_window():
        return False, "outside market hours (gap risk)"

    # Portfolio: already have position?
    if portfolio_shorts is not None and action in ("sell", "short") and symbol in portfolio_shorts:
        return False, "already short this symbol"
    if portfolio_longs is not None and action in ("buy", "long") and symbol in portfolio_longs:
        return False, "already long this symbol"

    return True, "ok"


def validate_and_record_last(signal: Dict[str, Any], **kwargs: Any) -> Tuple[bool, str]:
    """
    Call validate_signal; if allowed, write last_signal to logs/last_signal.json for health check.
    """
    allowed, reason = validate_signal(signal, **kwargs)
    if allowed:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": datetime.now().isoformat(),
            "symbol": (signal.get("symbol") or signal.get("ticker") or "").strip().upper(),
            "action": signal.get("action") or signal.get("side"),
            "order_id": signal.get("order_id"),
        }
        try:
            atomic_write_json(LAST_SIGNAL_FILE, payload)
        except OSError as e:
            logger.warning("Could not write last_signal: %s", e)
    return allowed, reason
