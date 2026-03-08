#!/usr/bin/env python3
"""
Options Executor Watchdog
Monitors IB Gateway and executor health, auto-restarts on failure.
Runs continuously as a background service.
"""

import subprocess
import time
import json
import os
from datetime import datetime
from pathlib import Path

# Configuration
LOG_DIR = Path.home() / ".openclaw" / "workspace" / "trading" / "logs"
LOG_FILE = LOG_DIR / "executor_watchdog.log"
STATUS_FILE = LOG_DIR / "executor_status.json"
EXECUTOR_SCRIPT = Path.home() / ".openclaw" / "workspace" / "trading" / "scripts" / "auto_options_executor.py"
IB_GATEWAY_PORT = 4002
CHECK_INTERVAL = 300  # 5 minutes
RESTART_COOLDOWN = 60  # Wait 60s before restart attempt
MAX_CONSECUTIVE_FAILURES = 3

# Ensure log directory exists
LOG_DIR.mkdir(parents=True, exist_ok=True)

def log(message, level="INFO"):
    """Write to watchdog log file."""
    timestamp = datetime.now().isoformat()
    log_line = f"[{timestamp}] [{level}] {message}\n"
    with open(LOG_FILE, "a") as f:
        f.write(log_line)
    print(log_line.strip())

def check_ib_gateway():
    """Check if IB Gateway API port is responding."""
    try:
        # Try direct port connection
        result = subprocess.run(
            ["nc", "-z", "-w", "2", "127.0.0.1", str(IB_GATEWAY_PORT)],
            capture_output=True,
            timeout=5
        )
        port_open = result.returncode == 0
        
        if not port_open:
            log(f"⚠️ IB Gateway port {IB_GATEWAY_PORT} is NOT listening", "CRITICAL")
        
        return port_open
    except Exception as e:
        log(f"IB Gateway check failed: {e}", "WARN")
        return False

def check_executor_running():
    """Check if executor process is still running."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "auto_options_executor.py"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception as e:
        log(f"Executor check failed: {e}", "WARN")
        return False

def restart_executor():
    """Start a fresh executor process."""
    try:
        log("Starting options executor...", "INFO")
        # Run executor in background
        subprocess.Popen(
            ["python3", str(EXECUTOR_SCRIPT)],
            cwd=str(EXECUTOR_SCRIPT.parent.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        log("Options executor started", "INFO")
        return True
    except Exception as e:
        log(f"Failed to start executor: {e}", "ERROR")
        return False

def update_status(status, reason=""):
    """Write current status to JSON file."""
    status_data = {
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "reason": reason,
        "ib_gateway_alive": check_ib_gateway(),
        "executor_running": check_executor_running()
    }
    try:
        with open(STATUS_FILE, "w") as f:
            json.dump(status_data, f, indent=2)
    except Exception as e:
        log(f"Failed to write status file: {e}", "WARN")

def main():
    """Main watchdog loop."""
    log("Options Executor Watchdog started", "INFO")
    consecutive_failures = 0
    
    while True:
        try:
            ib_alive = check_ib_gateway()
            executor_running = check_executor_running()
            
            if not ib_alive:
                log("⚠️  IB Gateway not responding", "WARN")
                update_status("IB_GATEWAY_DOWN", "API port not responding")
                consecutive_failures += 1
            elif not executor_running:
                log("⚠️  Executor not running", "WARN")
                update_status("EXECUTOR_STOPPED", "Process exited")
                consecutive_failures += 1
                
                # Restart if failures exceed threshold
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    log(f"Max failures ({MAX_CONSECUTIVE_FAILURES}) reached, restarting executor", "INFO")
                    restart_executor()
                    consecutive_failures = 0
                    time.sleep(RESTART_COOLDOWN)
                    continue
            else:
                # All systems nominal
                if consecutive_failures > 0:
                    log(f"✅ System recovered after {consecutive_failures} failures", "INFO")
                consecutive_failures = 0
                update_status("HEALTHY", "All systems operational")
            
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            log("Watchdog stopped by user", "INFO")
            break
        except Exception as e:
            log(f"Watchdog error: {e}", "ERROR")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
