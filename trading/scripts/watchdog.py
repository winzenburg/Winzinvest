#!/usr/bin/env python3
"""
watchdog.py — Monitors and auto-restarts Mission Control services.

Checks every 60 seconds:
  - scheduler.py       (job scheduler)
  - api.py             (dashboard, port 8002)

If a process is not running, restarts it and updates the PID file.
Kills duplicates if more than one instance is found.

Usage:
  nohup python3 watchdog.py >> /tmp/watchdog.log 2>&1 &
"""

import asyncio
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [watchdog] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/tmp/watchdog.log"),
    ],
)
logger = logging.getLogger(__name__)

TRADING_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = TRADING_DIR / "scripts"
DASHBOARD_DIR = TRADING_DIR / "dashboard"
PIDS_DIR = TRADING_DIR / ".pids"
PYTHON = sys.executable

CHECK_INTERVAL = 60  # seconds

LOGS_DIR = TRADING_DIR / "logs"

SERVICES = {
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
        "port": 8002,
    },
    "self_healer": {
        "script": str(SCRIPTS_DIR / "self_healer.py"),
        "cwd": str(SCRIPTS_DIR),
        "pid_file": str(PIDS_DIR / "self_healer.pid"),
        "log": str(LOGS_DIR / "self_healer.log"),
        "match": "self_healer.py",
    },
}


def find_pids(match: str) -> list[int]:
    """Return all PIDs whose cmdline contains `match`."""
    pids = []
    try:
        result = subprocess.run(
            ["pgrep", "-f", match],
            capture_output=True, text=True
        )
        for line in result.stdout.strip().splitlines():
            try:
                pids.append(int(line.strip()))
            except ValueError:
                pass
    except Exception:
        pass
    # Exclude self
    pids = [p for p in pids if p != os.getpid()]
    return pids


def is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def kill_pid(pid: int, name: str) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
        logger.info("Sent SIGTERM to %s (pid %d)", name, pid)
        time.sleep(2)
        if is_alive(pid):
            os.kill(pid, signal.SIGKILL)
            logger.info("Sent SIGKILL to %s (pid %d)", name, pid)
    except OSError:
        pass


def write_pid(pid_file: str, pid: int) -> None:
    Path(pid_file).parent.mkdir(parents=True, exist_ok=True)
    Path(pid_file).write_text(str(pid))


def start_service(name: str, cfg: dict) -> Optional[int]:
    """Start a service subprocess and return its PID."""
    log_path = cfg["log"]
    try:
        with open(log_path, "a") as log_fh:
            proc = subprocess.Popen(
                [PYTHON, cfg["script"]],
                cwd=cfg["cwd"],
                stdout=log_fh,
                stderr=log_fh,
                start_new_session=True,
            )
        write_pid(cfg["pid_file"], proc.pid)
        logger.info("Started %s (pid %d)", name, proc.pid)
        return proc.pid
    except Exception as e:
        logger.error("Failed to start %s: %s", name, e)
        return None


def check_service(name: str, cfg: dict) -> None:
    match = cfg["match"]
    pids = find_pids(match)

    if len(pids) > 1:
        # Kill all duplicates, keep the lowest PID (oldest)
        pids_sorted = sorted(pids)
        for dup in pids_sorted[1:]:
            logger.warning("Duplicate %s found (pid %d) — killing", name, dup)
            kill_pid(dup, name)
        write_pid(cfg["pid_file"], pids_sorted[0])
        logger.info("%s deduped — keeping pid %d", name, pids_sorted[0])

    elif len(pids) == 1:
        # Healthy — just keep PID file in sync
        write_pid(cfg["pid_file"], pids[0])

    else:
        # Not running — restart
        logger.warning("%s is NOT running — restarting...", name)
        new_pid = start_service(name, cfg)
        if new_pid:
            # Give it a moment to initialize
            time.sleep(3)
            if not is_alive(new_pid):
                logger.error("%s failed to stay up after restart", name)
        else:
            logger.error("Could not restart %s", name)


def main() -> None:
    logger.info("Watchdog started (PID %d) — monitoring: %s", os.getpid(), ", ".join(SERVICES))
    # Write own PID
    PIDS_DIR.mkdir(parents=True, exist_ok=True)
    (PIDS_DIR / "watchdog.pid").write_text(str(os.getpid()))

    while True:
        for name, cfg in SERVICES.items():
            try:
                check_service(name, cfg)
            except Exception as e:
                logger.error("Error checking %s: %s", name, e)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
