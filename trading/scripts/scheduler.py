#!/usr/bin/env python3
"""
Fully automated trading scheduler — runs the complete pipeline on market hours.

Schedule (all times Mountain Time / America/Denver):
  07:00  Pre-market: sync positions, run screeners, export TV watchlist
  07:30  Market open: run executors (longs, dual-mode, mean reversion)
  08:00  Mid-morning: run options executor
  10:00  Midday: re-run screeners for fresh signals
  10:15  Midday: re-run executors on fresh signals
  12:00  Afternoon: run options / pairs check
  14:00  Pre-close: portfolio snapshot, daily report
  14:30  Post-close: adaptive params, strategy analytics
  Every 60s: risk monitor loop (runs via agents/run_all.py)

Usage:
  python scheduler.py              # Run scheduler (foreground)
  python scheduler.py --dry-run    # Print schedule without executing

Requires: pip install apscheduler
"""

import argparse
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("scheduler")

SCRIPTS_DIR = Path(__file__).resolve().parent
TRADING_DIR = SCRIPTS_DIR.parent
LOGS_DIR = TRADING_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

PYTHON = sys.executable
TIMEZONE = "America/Denver"


def _run_script(name: str, args: Optional[list[str]] = None, timeout: int = 600) -> bool:
    """Run a Python script from the scripts directory. Returns True on success."""
    script_path = SCRIPTS_DIR / name
    if not script_path.exists():
        logger.error("Script not found: %s", script_path)
        return False

    cmd = [PYTHON, str(script_path)]
    if args:
        cmd.extend(args)

    logger.info(">>> Running: %s %s", name, " ".join(args or []))
    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(SCRIPTS_DIR),
            timeout=timeout,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": str(SCRIPTS_DIR)},
        )
        elapsed = time.time() - start
        if result.returncode == 0:
            logger.info("    %s completed in %.1fs", name, elapsed)
        else:
            logger.warning("    %s failed (exit %d) in %.1fs", name, result.returncode, elapsed)
            if result.stderr:
                for line in result.stderr.strip().splitlines()[-5:]:
                    logger.warning("    stderr: %s", line)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        logger.error("    %s timed out after %ds", name, timeout)
        return False
    except Exception as exc:
        logger.error("    %s error: %s", name, exc)
        return False


def job_premarket() -> None:
    """07:00 MT — Sync positions, run screeners, export candidates."""
    logger.info("=== PRE-MARKET ===")
    _run_script("sync_current_shorts.py")
    _run_script("nx_screener_production.py", ["--mode", "all"], timeout=900)
    _run_script("nx_screener_longs.py", timeout=900)
    _run_script("mr_screener.py", timeout=300)
    _run_script("export_tv_watchlist.py")
    logger.info("=== PRE-MARKET COMPLETE ===")


def job_market_open() -> None:
    """07:30 MT — Execute trades from screener output."""
    logger.info("=== MARKET OPEN EXECUTION ===")
    _run_script("execute_longs.py", timeout=300)
    _run_script("execute_dual_mode.py", timeout=300)
    _run_script("execute_mean_reversion.py", timeout=300)
    logger.info("=== MARKET OPEN EXECUTION COMPLETE ===")


def job_options() -> None:
    """08:00 MT — Run options strategies."""
    logger.info("=== OPTIONS EXECUTION ===")
    _run_script("auto_options_executor.py", timeout=300)
    logger.info("=== OPTIONS EXECUTION COMPLETE ===")


def job_midday_screen() -> None:
    """10:00 MT — Refresh screeners for midday signals."""
    logger.info("=== MIDDAY SCREEN ===")
    _run_script("nx_screener_longs.py", timeout=900)
    _run_script("nx_screener_production.py", ["--mode", "all"], timeout=900)
    _run_script("export_tv_watchlist.py")
    logger.info("=== MIDDAY SCREEN COMPLETE ===")


def job_midday_execute() -> None:
    """10:15 MT — Execute on fresh midday signals."""
    logger.info("=== MIDDAY EXECUTION ===")
    _run_script("execute_longs.py", timeout=300)
    _run_script("execute_dual_mode.py", timeout=300)
    logger.info("=== MIDDAY EXECUTION COMPLETE ===")


def job_afternoon() -> None:
    """12:00 MT — Afternoon options and pairs check."""
    logger.info("=== AFTERNOON CHECK ===")
    _run_script("pairs_screener.py", timeout=300)
    _run_script("execute_pairs.py", timeout=300)
    logger.info("=== AFTERNOON CHECK COMPLETE ===")


def job_preclose() -> None:
    """14:00 MT — Portfolio snapshot and daily report."""
    logger.info("=== PRE-CLOSE ===")
    _run_script("portfolio_snapshot.py", timeout=120)
    _run_script("daily_report.py", timeout=120)
    logger.info("=== PRE-CLOSE COMPLETE ===")


def job_postclose() -> None:
    """14:30 MT — Adaptive learning, strategy analytics."""
    logger.info("=== POST-CLOSE ===")
    _run_script("strategy_analytics.py", timeout=300)
    _run_script("adaptive_params.py", timeout=120)
    _run_script("sector_rotation.py", timeout=120)
    _run_script("sync_current_shorts.py")
    logger.info("=== POST-CLOSE COMPLETE ===")


def _is_trading_day() -> bool:
    """Check if today is a US market trading day (Mon-Fri, skip major holidays)."""
    today = datetime.now()
    if today.weekday() >= 5:
        return False
    # Major US market holidays (approximate — a proper calendar library is better)
    month_day = (today.month, today.day)
    closed_dates = {
        (1, 1), (1, 20), (2, 17), (4, 18), (5, 26),
        (6, 19), (7, 4), (9, 1), (11, 27), (12, 25),
    }
    return month_day not in closed_dates


def run_scheduler() -> None:
    """Start the APScheduler with the full trading schedule."""
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.error("APScheduler not installed. Run: pip install apscheduler")
        sys.exit(1)

    sched = BlockingScheduler(timezone=TIMEZONE)

    sched.add_job(job_premarket, CronTrigger(
        day_of_week="mon-fri", hour=7, minute=0, timezone=TIMEZONE,
    ), id="premarket", name="Pre-market screeners")

    sched.add_job(job_market_open, CronTrigger(
        day_of_week="mon-fri", hour=7, minute=30, timezone=TIMEZONE,
    ), id="market_open", name="Market open execution")

    sched.add_job(job_options, CronTrigger(
        day_of_week="mon-fri", hour=8, minute=0, timezone=TIMEZONE,
    ), id="options", name="Options execution")

    sched.add_job(job_midday_screen, CronTrigger(
        day_of_week="mon-fri", hour=10, minute=0, timezone=TIMEZONE,
    ), id="midday_screen", name="Midday screeners")

    sched.add_job(job_midday_execute, CronTrigger(
        day_of_week="mon-fri", hour=10, minute=15, timezone=TIMEZONE,
    ), id="midday_execute", name="Midday execution")

    sched.add_job(job_afternoon, CronTrigger(
        day_of_week="mon-fri", hour=12, minute=0, timezone=TIMEZONE,
    ), id="afternoon", name="Afternoon pairs/options")

    sched.add_job(job_preclose, CronTrigger(
        day_of_week="mon-fri", hour=14, minute=0, timezone=TIMEZONE,
    ), id="preclose", name="Pre-close snapshot")

    sched.add_job(job_postclose, CronTrigger(
        day_of_week="mon-fri", hour=14, minute=30, timezone=TIMEZONE,
    ), id="postclose", name="Post-close analytics")

    logger.info("Scheduler started. Jobs:")
    for job in sched.get_jobs():
        next_run = getattr(job, "next_run_time", None)
        logger.info("  %s → %s", job.id, next_run)

    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")


def print_schedule() -> None:
    """Print the schedule without starting it."""
    schedule = [
        ("07:00 MT", "Pre-market", "sync_current_shorts → nx_screener_production → nx_screener_longs → mr_screener → export_tv_watchlist"),
        ("07:30 MT", "Market Open", "execute_longs → execute_dual_mode → execute_mean_reversion"),
        ("08:00 MT", "Options", "auto_options_executor"),
        ("10:00 MT", "Midday Screen", "nx_screener_longs → nx_screener_production → export_tv_watchlist"),
        ("10:15 MT", "Midday Execute", "execute_longs → execute_dual_mode"),
        ("12:00 MT", "Afternoon", "pairs_screener → execute_pairs"),
        ("14:00 MT", "Pre-Close", "portfolio_snapshot → daily_report"),
        ("14:30 MT", "Post-Close", "strategy_analytics → adaptive_params → sector_rotation → sync_current_shorts"),
        ("Always", "Background", "risk_monitor + reconnection_agent + trade_outcome_resolver (via run_all.py)"),
        ("Always", "Webhook", "FastAPI server listening for TradingView pullback alerts"),
    ]
    print("\n  AUTOMATED TRADING SCHEDULE (Mon-Fri)")
    print("  " + "=" * 80)
    for time_str, phase, scripts in schedule:
        print(f"  {time_str:<12} {phase:<16} {scripts}")
    print("  " + "=" * 80)
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Automated trading scheduler")
    parser.add_argument("--dry-run", action="store_true", help="Print schedule without starting")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(LOGS_DIR / "scheduler.log"),
            logging.StreamHandler(),
        ],
    )

    if args.dry_run:
        print_schedule()
        return

    logger.info("Trading scheduler starting")
    logger.info("Scripts dir: %s", SCRIPTS_DIR)
    logger.info("Python: %s", PYTHON)
    logger.info("Timezone: %s", TIMEZONE)
    print_schedule()
    run_scheduler()


if __name__ == "__main__":
    main()
