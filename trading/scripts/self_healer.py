#!/usr/bin/env python3
"""
Self-Healing Error Monitor

Polls the Mission Control dashboard API every 60 seconds, matches errors
and service outages against config-driven remediation rules, and auto-
executes fixes: service restarts, job re-runs, and error suppression.

Every action is logged to trading/logs/self_healer.log and optionally
sent as a Telegram notification.

Safety guards:
  - Max 3 restarts per service per hour
  - Max 2 re-runs per script per hour
  - Max 10 auto-suppressed patterns total
  - Never restarts IB Gateway itself
  - Respects risk.json kill switch for executor re-runs
"""

import json
import logging
import os
import re
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

TRADING_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = TRADING_DIR / "scripts"
DASHBOARD_DIR = TRADING_DIR / "dashboard"
CONFIG_DIR = TRADING_DIR / "config"
LOGS_DIR = TRADING_DIR / "logs"
PIDS_DIR = TRADING_DIR / ".pids"
PYTHON = sys.executable

DASHBOARD_BASE = "http://localhost:8002"
POLL_INTERVAL = 60
MAX_RESTARTS_PER_HOUR = 3
MAX_RERUNS_PER_HOUR = 2
MAX_AUTO_SUPPRESSED = 10
SCRIPT_TIMEOUT = 300

LOGS_DIR.mkdir(exist_ok=True)
PIDS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [self_healer] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(LOGS_DIR / "self_healer.log")),
    ],
)
logger = logging.getLogger("self_healer")

ENV_PATH = TRADING_DIR / ".env"
if ENV_PATH.exists():
    for line in ENV_PATH.read_text().split("\n"):
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID")

# ── Service launch configs (mirrors watchdog.py) ────────────────────

SERVICE_CONFIGS: Dict[str, Dict[str, Any]] = {
    "scheduler": {
        "script": str(SCRIPTS_DIR / "scheduler.py"),
        "cwd": str(SCRIPTS_DIR),
        "pid_file": str(PIDS_DIR / "scheduler.pid"),
        "log": str(LOGS_DIR / "scheduler.log"),
        "match": "scheduler.py",
    },
    "dashboard": {
        "script": str(DASHBOARD_DIR / "api.py"),
        "cwd": str(DASHBOARD_DIR),
        "pid_file": str(PIDS_DIR / "dashboard.pid"),
        "log": str(LOGS_DIR / "dashboard.log"),
        "match": "api.py",
    },
    "agents": {
        "script": str(SCRIPTS_DIR / "agents" / "run_all.py"),
        "cwd": str(SCRIPTS_DIR),
        "pid_file": str(PIDS_DIR / "agents.pid"),
        "log": str(LOGS_DIR / "agents.log"),
        "match": "agents/run_all.py",
    },
}

# ── Cooldown tracking ───────────────────────────────────────────────

_action_history: Dict[str, List[datetime]] = defaultdict(list)


def _prune_history(key: str, window_minutes: int = 60) -> None:
    cutoff = datetime.now() - timedelta(minutes=window_minutes)
    _action_history[key] = [t for t in _action_history[key] if t > cutoff]


def _count_recent(key: str, window_minutes: int = 60) -> int:
    _prune_history(key, window_minutes)
    return len(_action_history[key])


def _record_action(key: str) -> None:
    _action_history[key].append(datetime.now())


def _cooldown_ok(rule: Dict[str, Any]) -> bool:
    """Check whether enough time has passed since the last execution of this rule."""
    key = rule["id"]
    cooldown = rule.get("cooldown_minutes", 5)
    _prune_history(key, cooldown)
    return len(_action_history[key]) == 0


# ── Telegram ────────────────────────────────────────────────────────

def send_telegram(text: str) -> bool:
    if not (TG_TOKEN and TG_CHAT):
        return False
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    data = urllib.parse.urlencode(
        {"chat_id": TG_CHAT, "text": text, "parse_mode": "Markdown"}
    ).encode()
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


# ── HTTP helpers ────────────────────────────────────────────────────

def _api_get(path: str) -> Optional[Dict[str, Any]]:
    try:
        url = f"{DASHBOARD_BASE}{path}"
        with urllib.request.urlopen(url, timeout=8) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


# ── Config loaders ──────────────────────────────────────────────────

def load_healing_rules() -> List[Dict[str, Any]]:
    path = CONFIG_DIR / "healing_rules.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        logger.error("Failed to load healing_rules.json: %s", exc)
        return []


def load_ignored_errors() -> Dict[str, Any]:
    path = CONFIG_DIR / "ignored_errors.json"
    if not path.exists():
        return {"patterns": [], "auto_added": []}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {"patterns": [], "auto_added": []}


def save_ignored_errors(data: Dict[str, Any]) -> None:
    path = CONFIG_DIR / "ignored_errors.json"
    path.write_text(json.dumps(data, indent=2) + "\n")


def is_kill_switch_active() -> bool:
    risk_path = TRADING_DIR / "risk.json"
    try:
        risk = json.loads(risk_path.read_text()) if risk_path.exists() else {}
        return bool(risk.get("kill_switch", {}).get("active", False))
    except Exception:
        return False


# ── Process management ──────────────────────────────────────────────

def _is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _kill_pid(pid: int, name: str) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
        logger.info("Sent SIGTERM to %s (pid %d)", name, pid)
        time.sleep(2)
        if _is_alive(pid):
            os.kill(pid, signal.SIGKILL)
            logger.info("Sent SIGKILL to %s (pid %d)", name, pid)
    except OSError:
        pass


def _find_pids(match: str) -> List[int]:
    pids: List[int] = []
    try:
        result = subprocess.run(
            ["pgrep", "-f", match], capture_output=True, text=True
        )
        for line in result.stdout.strip().splitlines():
            try:
                pids.append(int(line.strip()))
            except ValueError:
                pass
    except Exception:
        pass
    return [p for p in pids if p != os.getpid()]


def restart_service(name: str) -> bool:
    """Kill existing process and re-launch the service."""
    cfg = SERVICE_CONFIGS.get(name)
    if cfg is None:
        logger.warning("Unknown service: %s", name)
        return False

    rate_key = f"restart:{name}"
    if _count_recent(rate_key) >= MAX_RESTARTS_PER_HOUR:
        logger.warning("Restart rate limit hit for %s (%d in last hour)", name, MAX_RESTARTS_PER_HOUR)
        return False

    existing = _find_pids(cfg["match"])
    for pid in existing:
        _kill_pid(pid, name)

    time.sleep(1)

    try:
        log_path = cfg["log"]
        with open(log_path, "a") as log_fh:
            proc = subprocess.Popen(
                [PYTHON, cfg["script"]],
                cwd=cfg["cwd"],
                stdout=log_fh,
                stderr=log_fh,
                start_new_session=True,
            )
        Path(cfg["pid_file"]).write_text(str(proc.pid))
        _record_action(rate_key)
        logger.info("Restarted %s (pid %d)", name, proc.pid)
        return True
    except Exception as exc:
        logger.error("Failed to restart %s: %s", name, exc)
        return False


def rerun_script(target: str) -> bool:
    """Re-run a script by relative path (e.g. 'scripts/sector_rotation.py')."""
    script_path = TRADING_DIR / target
    if not script_path.exists():
        logger.warning("Script not found: %s", script_path)
        return False

    rate_key = f"rerun:{target}"
    if _count_recent(rate_key) >= MAX_RERUNS_PER_HOUR:
        logger.warning("Re-run rate limit hit for %s (%d in last hour)", target, MAX_RERUNS_PER_HOUR)
        return False

    if is_kill_switch_active() and "execute" in target:
        logger.warning("Kill switch active — skipping executor re-run: %s", target)
        return False

    logger.info("Re-running %s (timeout %ds)...", target, SCRIPT_TIMEOUT)
    try:
        result = subprocess.run(
            [PYTHON, str(script_path)],
            cwd=str(script_path.parent),
            capture_output=True,
            text=True,
            timeout=SCRIPT_TIMEOUT,
        )
        _record_action(rate_key)
        if result.returncode == 0:
            logger.info("Re-run %s succeeded", target)
        else:
            logger.warning("Re-run %s exited %d: %s", target, result.returncode, result.stderr[-200:] if result.stderr else "")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        logger.error("Re-run %s timed out after %ds", target, SCRIPT_TIMEOUT)
        return False
    except Exception as exc:
        logger.error("Re-run %s failed: %s", target, exc)
        return False


def suppress_error(pattern: str) -> bool:
    """Append a pattern to the auto_added list in ignored_errors.json."""
    data = load_ignored_errors()
    all_patterns = data.get("patterns", []) + data.get("auto_added", [])

    if pattern in all_patterns:
        return True

    if len(data.get("auto_added", [])) >= MAX_AUTO_SUPPRESSED:
        logger.warning("Auto-suppress limit reached (%d) — not adding: %s", MAX_AUTO_SUPPRESSED, pattern)
        return False

    data.setdefault("auto_added", []).append(pattern)
    save_ignored_errors(data)
    logger.info("Auto-suppressed error pattern: %s", pattern)
    return True


# ── Rule matching ───────────────────────────────────────────────────

def _matches_rule(error: Dict[str, str], rule: Dict[str, Any]) -> bool:
    """Check whether an error dict matches a healing rule."""
    text = f"{error.get('service', '')}:{error.get('message', '')}"
    match_str = rule.get("match", "")
    match_type = rule.get("match_type", "substring")

    if match_type == "regex":
        return bool(re.search(match_str, text))
    return match_str in text


# ── Main loop ───────────────────────────────────────────────────────

def heal_cycle() -> List[str]:
    """Run one healing cycle. Returns list of actions taken."""
    actions_taken: List[str] = []

    # 1. Poll errors
    error_data = _api_get("/api/errors?minutes=60")
    errors = error_data.get("errors", []) if error_data else []

    # 2. Poll service status
    status_data = _api_get("/api/status")

    # 3. Auto-heal down services
    if status_data:
        services = status_data.get("services", {})
        for svc_key, svc_info in services.items():
            if svc_key == "ib_gateway":
                continue
            if not svc_info.get("running", True) and svc_key in SERVICE_CONFIGS:
                desc = f"Restarted {svc_key} (was down)"
                if restart_service(svc_key):
                    actions_taken.append(desc)
                    logger.info(desc)

    # 4. Match errors against healing rules
    rules = load_healing_rules()
    handled_rule_ids: set[str] = set()

    for error in errors:
        for rule in rules:
            rule_id = rule.get("id", rule.get("match", ""))
            if rule_id in handled_rule_ids:
                continue
            if not _matches_rule(error, rule):
                continue
            if not _cooldown_ok(rule):
                logger.debug("Cooldown active for rule %s", rule_id)
                continue

            action = rule.get("action")
            target = rule.get("target", "")
            desc = rule.get("description", f"{action} {target}")

            success = False
            if action == "restart_service" and target:
                success = restart_service(target)
            elif action == "rerun_script" and target:
                success = rerun_script(target)
            elif action == "suppress":
                match_pattern = rule.get("match", "")
                success = suppress_error(match_pattern)

            if success:
                _record_action(rule_id)
                actions_taken.append(desc)
                logger.info("Healed: %s", desc)

            handled_rule_ids.add(rule_id)

    # 5. Handle dashboard being unreachable (api itself is down)
    if error_data is None and status_data is None:
        desc = "Dashboard API unreachable — restarting"
        if restart_service("dashboard"):
            actions_taken.append(desc)
            logger.info(desc)

    return actions_taken


def main() -> None:
    logger.info("Self-healer started (PID %d)", os.getpid())
    (PIDS_DIR / "self_healer.pid").write_text(str(os.getpid()))

    while True:
        try:
            actions = heal_cycle()
            if actions:
                summary = "\n".join(f"  - {a}" for a in actions)
                logger.info("Cycle complete — %d action(s):\n%s", len(actions), summary)
                tg_msg = f"🔧 *Self-Healer* — {len(actions)} action(s):\n"
                for a in actions:
                    tg_msg += f"  • {a}\n"
                send_telegram(tg_msg)
        except Exception as exc:
            logger.error("Heal cycle error: %s", exc)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
