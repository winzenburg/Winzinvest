#!/usr/bin/env python3
"""
Drawdown Circuit Breaker
========================
Graduated risk response based on intraday drawdown from start-of-day equity.

Tiers (configurable in risk.json → drawdown_breaker):
  Tier 1 (-3%): Reduce new position sizes by 50%
  Tier 2 (-5%): Stop all new entries entirely
  Tier 3 (-8%): Activate kill switch

State is written to drawdown_breaker_state.json and checked by all executors.
Resets automatically at start of each trading day.

Usage:
  # Check breaker state (called by executors before trading)
  from drawdown_circuit_breaker import get_breaker_state, get_position_scale

  state = get_breaker_state()
  if state["tier"] >= 2:
      print("Entries halted by drawdown breaker")
      return

  scale = get_position_scale()  # 1.0 normally, 0.5 at tier 1, 0.0 at tier 2+
"""

import json
import logging
import os
import tempfile
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

SCRIPTS_DIR = Path(__file__).resolve().parent
TRADING_DIR = SCRIPTS_DIR.parent
LOGS_DIR = TRADING_DIR / "logs"
RISK_PATH = TRADING_DIR / "risk.json"
STATE_PATH = LOGS_DIR / "drawdown_breaker_state.json"
SOD_EQUITY_FILE = LOGS_DIR / "sod_equity.json"
DAILY_LOSS_FILE = LOGS_DIR / "daily_loss.json"
KILL_SWITCH_PATH = TRADING_DIR / "kill_switch.json"

LOGS_DIR.mkdir(exist_ok=True)


def _load_config() -> Dict[str, Any]:
    defaults = {
        "tier1_pct": -3.0,
        "tier1_action": "reduce_size",
        "tier1_scale": 0.50,
        "tier2_pct": -5.0,
        "tier2_action": "stop_entries",
        "tier3_pct": -8.0,
        "tier3_action": "kill_switch",
    }
    try:
        if RISK_PATH.exists():
            cfg = json.loads(RISK_PATH.read_text()).get("drawdown_breaker", {})
            defaults.update(cfg)
    except Exception:
        pass
    return defaults


def _read_sod_equity() -> float:
    try:
        if SOD_EQUITY_FILE.exists():
            data = json.loads(SOD_EQUITY_FILE.read_text())
            return float(data.get("equity", 0))
    except Exception:
        pass
    return 0.0


def _read_current_equity() -> float:
    try:
        if DAILY_LOSS_FILE.exists():
            data = json.loads(DAILY_LOSS_FILE.read_text())
            return float(data.get("current_equity", 0))
    except Exception:
        pass
    return 0.0


def _load_state() -> Dict[str, Any]:
    default = {
        "date": date.today().isoformat(),
        "tier": 0,
        "drawdown_pct": 0.0,
        "sod_equity": 0.0,
        "current_equity": 0.0,
        "last_checked": "",
        "actions_taken": [],
    }
    try:
        if STATE_PATH.exists():
            data = json.loads(STATE_PATH.read_text())
            if data.get("date") == date.today().isoformat():
                return data
    except Exception:
        pass
    return default


def _atomic_write(path: Path, data: Dict[str, Any]) -> None:
    """Write JSON to a temp file in the same directory, then atomically replace the target."""
    dir_ = path.parent
    dir_.mkdir(parents=True, exist_ok=True)
    try:
        fd, tmp_path = tempfile.mkstemp(dir=dir_, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump(data, fh, indent=2)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except Exception as exc:
        logger.error("Atomic write failed for %s: %s", path, exc)
        raise


def _save_state(state: Dict[str, Any]) -> None:
    try:
        _atomic_write(STATE_PATH, state)
    except Exception as e:
        logger.error("Could not save breaker state: %s", e)


def _activate_kill_switch(reason: str) -> None:
    ks = {
        "active": True,
        "reason": reason,
        "timestamp": datetime.now().isoformat(),
    }
    try:
        _atomic_write(KILL_SWITCH_PATH, ks)
        logger.critical("KILL SWITCH ACTIVATED: %s", reason)
    except Exception as e:
        logger.error("Failed to activate kill switch: %s", e)


def _notify(msg: str, *, urgent: bool = False, ungated: bool = False) -> None:
    """Send a Telegram alert for a breaker event.

    Args:
        urgent:  Passes the urgent flag to the Telegram sender (disables notification silencing).
        ungated: If True, bypasses the ``drawdown_circuit_breaker`` event toggle and always sends.
                 Used for Tier 3 (kill-switch) alerts where suppression would be dangerous.
    """
    logger.warning(msg)
    try:
        from notifications import is_event_enabled, send_telegram
        if ungated or is_event_enabled("drawdown_circuit_breaker"):
            send_telegram(f"[BREAKER] {msg}", urgent=urgent)
    except ImportError:
        # Fallback if notifications module unavailable
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat = os.getenv("TELEGRAM_CHAT_ID", "")
        if token and chat:
            try:
                import urllib.request
                import urllib.parse
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                data = urllib.parse.urlencode({
                    "chat_id": chat, "text": f"[BREAKER] {msg}", "parse_mode": "HTML",
                    "disable_notification": str(not urgent).lower(),
                }).encode()
                urllib.request.urlopen(url, data=data, timeout=5)
            except Exception:
                pass


def evaluate_breaker() -> Dict[str, Any]:
    """Evaluate drawdown and update breaker tier. Called by risk_monitor."""
    cfg = _load_config()
    state = _load_state()

    sod_equity = _read_sod_equity()
    current_equity = _read_current_equity()

    if sod_equity <= 0 or current_equity <= 0:
        state["last_checked"] = datetime.now().isoformat()
        _save_state(state)
        return state

    drawdown_pct = (current_equity - sod_equity) / sod_equity * 100
    state["drawdown_pct"] = round(drawdown_pct, 2)
    state["sod_equity"] = sod_equity
    state["current_equity"] = current_equity
    state["date"] = date.today().isoformat()
    state["last_checked"] = datetime.now().isoformat()

    prev_tier = state.get("tier", 0)
    new_tier = 0

    tier3_pct = float(cfg["tier3_pct"])
    tier2_pct = float(cfg["tier2_pct"])
    tier1_pct = float(cfg["tier1_pct"])

    if drawdown_pct <= tier3_pct:
        new_tier = 3
    elif drawdown_pct <= tier2_pct:
        new_tier = 2
    elif drawdown_pct <= tier1_pct:
        new_tier = 1

    if new_tier > prev_tier:
        state["tier"] = new_tier
        action = f"tier{new_tier}_action"
        action_name = cfg.get(action, "unknown")

        if new_tier == 1:
            scale = cfg.get("tier1_scale", 0.5)
            msg = (f"⚠️ <b>TIER 1 BREAKER</b>: {drawdown_pct:.1f}% drawdown\n"
                   f"Position sizes reduced to {scale:.0%}")
            state["actions_taken"].append(f"T1 at {drawdown_pct:.1f}% ({datetime.now().strftime('%H:%M')})")
            _notify(msg)

        elif new_tier == 2:
            msg = (f"🛑 <b>TIER 2 BREAKER</b>: {drawdown_pct:.1f}% drawdown\n"
                   f"All new entries HALTED")
            state["actions_taken"].append(f"T2 at {drawdown_pct:.1f}% ({datetime.now().strftime('%H:%M')})")
            _notify(msg, urgent=True)

        elif new_tier == 3:
            msg = (f"🚨 <b>TIER 3 BREAKER — KILL SWITCH</b>: {drawdown_pct:.1f}% drawdown\n"
                   f"All trading STOPPED")
            state["actions_taken"].append(f"T3 KILL at {drawdown_pct:.1f}% ({datetime.now().strftime('%H:%M')})")
            # ungated=True: kill-switch alerts must always fire regardless of notification preferences
            _notify(msg, urgent=True, ungated=True)
            _activate_kill_switch(f"Drawdown circuit breaker tier 3: {drawdown_pct:.1f}% daily loss")

    elif new_tier < prev_tier:
        # Partial de-escalation: allow tier 3→2→1→0 transitions, not just full reset to 0.
        # This means entries can resume at tier 1 (half size) once drawdown recovers from -5% to -3%.
        state["tier"] = new_tier
        if new_tier == 0:
            _notify(f"✅ Drawdown recovered to {drawdown_pct:.1f}% — all breakers cleared")
            state["actions_taken"].append(f"Cleared at {drawdown_pct:.1f}% ({datetime.now().strftime('%H:%M')})")
        else:
            _notify(
                f"↗️ <b>BREAKER REDUCED TO TIER {new_tier}</b>: drawdown recovered to {drawdown_pct:.1f}%\n"
                f"{'Position sizes at 50% — entries permitted' if new_tier == 1 else 'Entries still halted'}"
            )
            state["actions_taken"].append(
                f"T{new_tier} (recovered from T{prev_tier}) at {drawdown_pct:.1f}% "
                f"({datetime.now().strftime('%H:%M')})"
            )

    _save_state(state)
    return state


def get_breaker_state() -> Dict[str, Any]:
    """Read current breaker state without re-evaluating. Fast read for executors."""
    return _load_state()


def get_position_scale() -> float:
    """Return the position sizing multiplier based on current breaker tier.

    1.0 = normal, 0.5 = tier 1 reduced, 0.0 = tier 2+ halted.
    """
    state = _load_state()
    tier = state.get("tier", 0)
    if tier >= 2:
        return 0.0
    if tier == 1:
        cfg = _load_config()
        return float(cfg.get("tier1_scale", 0.5))
    return 1.0


def is_entries_halted() -> bool:
    """Quick check: are new entries currently blocked?"""
    state = _load_state()
    return state.get("tier", 0) >= 2
