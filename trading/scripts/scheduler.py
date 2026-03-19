#!/usr/bin/env python3
"""
Fully automated trading scheduler — runs the complete pipeline on market hours.

Schedule (all times Mountain Time / America/Denver, ET in parens):
  02:00 (04:00 ET)  Overnight SOD: capture start-of-day equity at overnight open (daily P&L includes overnight moves)
  07:00 (09:00 ET)  Pre-market: sync positions, run screeners, export TV watchlist
  07:30 (09:30 ET)  Market open: run executors (longs, dual-mode, mean reversion)
  08:00 (10:00 ET)  Mid-morning: run options executor
  08:15 (10:15 ET)  Post-open: re-screen after opening noise settles
  08:30 (10:30 ET)  Post-open: execute on confirmed intraday signals
  11:30 (13:30 ET)  Afternoon: re-screen as institutional volume returns
  11:45 (13:45 ET)  Afternoon: execute on afternoon signals + pairs
  13:30 (15:30 ET)  Pre-close screen: final screen 30 min before close
  14:00 (16:00 ET)  Pre-close: portfolio snapshot, daily report
  14:30 (16:30 ET)  Post-close: adaptive params, strategy analytics
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


def _send_failure_alert(name: str, detail: str) -> None:
    """Send Telegram alert when a scheduled script fails."""
    try:
        from notifications import notify_executor_error
        notify_executor_error(name, detail, context="scheduler")
    except Exception:
        pass


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
            stderr_tail = ""
            if result.stderr:
                for line in result.stderr.strip().splitlines()[-5:]:
                    logger.warning("    stderr: %s", line)
                stderr_tail = result.stderr.strip().splitlines()[-1]
            _send_failure_alert(name, f"exit {result.returncode}: {stderr_tail}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        logger.error("    %s timed out after %ds", name, timeout)
        _send_failure_alert(name, f"timed out after {timeout}s")
        return False
    except Exception as exc:
        logger.error("    %s error: %s", name, exc)
        _send_failure_alert(name, str(exc))
        return False


def job_pm_upgrade_check() -> None:
    """Mon 07:01 MT (one-time) — Log margin comparison after Portfolio Margin activation."""
    logger.info("=== PORTFOLIO MARGIN UPGRADE CHECK ===")
    _run_script("dashboard_data_aggregator.py", timeout=120)
    try:
        import json
        from pathlib import Path
        snap_path = TRADING_DIR / "logs" / "dashboard_snapshot.json"
        if snap_path.exists():
            snap = json.loads(snap_path.read_text())
            acct = snap.get("account", {})
            nlv = acct.get("net_liquidation", 0)
            bp = acct.get("buying_power", 0)
            margin_used = acct.get("maintenance_margin", 0)
            margin_pct = snap.get("risk", {}).get("margin_utilization_pct", 0)
            msg = (
                f"Portfolio Margin activated — snapshot:\n"
                f"  NLV:              ${nlv:>12,.0f}\n"
                f"  Buying Power:     ${bp:>12,.0f}\n"
                f"  Margin Used:      ${margin_used:>12,.0f}\n"
                f"  Margin Util:      {margin_pct:>11.1f}%\n"
                f"  BP/NLV Ratio:     {bp/nlv:.2f}x" if nlv else "  (no data)"
            )
            logger.info(msg)
            try:
                from notifications import notify_info
                notify_info(f"<b>Portfolio Margin Active</b>\nNLV: ${nlv:,.0f} | BP: ${bp:,.0f} | Margin: {margin_pct:.1f}%")
            except Exception:
                pass
    except Exception as exc:
        logger.warning("PM upgrade check failed (non-fatal): %s", exc)
    logger.info("=== PORTFOLIO MARGIN UPGRADE CHECK COMPLETE ===")


def job_overnight_sod() -> None:
    """02:00 MT (04:00 ET) — Capture SOD at overnight market open so daily P&L includes overnight moves."""
    logger.info("=== OVERNIGHT SOD CAPTURE ===")
    _run_script("portfolio_snapshot.py", timeout=60)
    _run_script("overnight_sod_capture.py", timeout=30)
    _run_script("dashboard_data_aggregator.py", timeout=120)
    logger.info("=== OVERNIGHT SOD CAPTURE COMPLETE ===")


def job_position_integrity() -> None:
    """Position integrity check — detect and alert on accidental position flips."""
    if not _is_trading_day():
        return
    logger.info("=== POSITION INTEGRITY CHECK ===")
    result = _run_script("position_integrity_check.py", timeout=60)
    if not result:  # _run_script returns bool (True=success); False != 0 is False in Python
        logger.critical(
            "Position integrity check FAILED — review logs/position_integrity_%s.json",
            datetime.now().strftime("%Y%m%d"),
        )
        try:
            from notifications import notify_critical
            notify_critical(
                "Position Integrity FAIL",
                "One or more positions appear to be on the wrong side. "
                "Check position_integrity_check.log before trading.",
            )
        except Exception:
            pass
    logger.info("=== POSITION INTEGRITY CHECK COMPLETE ===")


def job_premarket() -> None:
    """07:00 MT — Sync positions, run screeners, export candidates."""
    logger.info("=== PRE-MARKET ===")
    # Integrity check first — block trading if positions are in a bad state
    job_position_integrity()
    _run_script("sync_current_shorts.py")
    _run_script("nx_screener_production.py", ["--mode", "all"], timeout=1800)
    _run_script("nx_screener_longs.py", timeout=900)
    _run_script("mr_screener.py", timeout=300)
    _run_script("export_tv_watchlist.py")
    # Run intelligence pipeline: Greeks → Scenarios → Decisions
    _run_script("portfolio_greeks.py", timeout=120)
    _run_script("scenario_engine.py", timeout=60)
    _run_script("portfolio_intelligence.py", timeout=60)
    logger.info("=== PRE-MARKET COMPLETE ===")


def job_market_open() -> None:
    """07:30 MT — Execute trades from screener output."""
    logger.info("=== MARKET OPEN EXECUTION ===")
    # Deferred/pending trades run first so capital is available before screener entries
    _run_script("execute_pending_trades.py", timeout=120)
    _run_script("execute_longs.py", timeout=300)
    _run_script("execute_dual_mode.py", timeout=300)
    _run_script("execute_mean_reversion.py", timeout=300)
    logger.info("=== MARKET OPEN EXECUTION COMPLETE ===")


def job_options() -> None:
    """08:00 MT — Run options strategies, then send daily options email."""
    logger.info("=== OPTIONS EXECUTION ===")
    _run_script("auto_options_executor.py", timeout=300)
    _run_script("daily_options_email.py", timeout=120)
    logger.info("=== OPTIONS EXECUTION COMPLETE ===")


def job_cash_monitor() -> None:
    """Every 30 min during market hours — deploy idle cash / close leverage gap."""
    logger.info("=== CASH & LEVERAGE MONITOR ===")
    try:
        sys.path.insert(0, str(SCRIPTS_DIR))
        from drawdown_circuit_breaker import evaluate_breaker
        state = evaluate_breaker()
        tier = state.get("tier", 0)
        dd = state.get("drawdown_pct", 0)
        if tier > 0:
            logger.warning("Drawdown breaker TIER %d active (%.1f%% drawdown)", tier, dd)
        else:
            logger.info("Drawdown breaker: clear (%.1f%%)", dd)
    except Exception as e:
        logger.debug("Drawdown breaker check skipped: %s", e)
    _run_script("cash_monitor.py", timeout=600)
    logger.info("=== CASH & LEVERAGE MONITOR COMPLETE ===")


def job_options_manager() -> None:
    """Every 30 min during market hours — manage existing options positions."""
    logger.info("=== OPTIONS POSITION MANAGER ===")
    _run_script("options_position_manager.py", timeout=300)
    _run_script("assignment_risk_monitor.py", timeout=120)
    _run_script("spotlight_monitor.py", timeout=60)
    logger.info("=== OPTIONS POSITION MANAGER COMPLETE ===")


def job_gap_risk_eod() -> None:
    """13:55 MT (3:55 PM ET) — EOD gap risk check before close."""
    logger.info("=== GAP RISK EOD CHECK ===")
    _run_script("gap_risk_eod_check.py", timeout=120)
    logger.info("=== GAP RISK EOD CHECK COMPLETE ===")


def job_postopen_screen() -> None:
    """08:15 MT (10:15 ET) — Re-screen after opening noise settles.

    The first 45 min of trading is noisy. By 10:15 ET the opening range is
    established, giving higher-conviction signals for intraday RS, failed
    bounces, and volume confirmation.
    """
    logger.info("=== POST-OPEN SCREEN (10:15 ET) ===")
    _run_script("nx_screener_longs.py", timeout=900)
    _run_script("nx_screener_production.py", ["--mode", "all"], timeout=1800)
    _run_script("mr_screener.py", timeout=300)
    _run_script("export_tv_watchlist.py")
    logger.info("=== POST-OPEN SCREEN COMPLETE ===")


def job_postopen_execute() -> None:
    """08:30 MT (10:30 ET) — Execute on confirmed post-open signals."""
    logger.info("=== POST-OPEN EXECUTION (10:30 ET) ===")
    _run_script("execute_longs.py", timeout=300)
    _run_script("execute_dual_mode.py", timeout=300)
    _run_script("execute_mean_reversion.py", timeout=300)
    logger.info("=== POST-OPEN EXECUTION COMPLETE ===")


def job_sector_rebalance() -> None:
    """08:45 MT (10:45 ET) — Auto-close weakest positions in over-weight sectors.

    Runs after post-open execution so any new entries are counted before the
    concentration check. Closes weakest longs first (most negative unrealized %),
    buying back covered calls before selling shares to avoid naked positions.
    Only fires when a sector exceeds its limit — no-ops when all sectors are in range.
    """
    logger.info("=== SECTOR REBALANCE CHECK (10:45 ET) ===")
    _run_script("sector_rebalancer.py", ["--live"], timeout=300)
    logger.info("=== SECTOR REBALANCE COMPLETE ===")


def job_afternoon_screen() -> None:
    """11:30 MT (13:30 ET) — Afternoon screen as institutional volume returns.

    Avoids the 11:30-13:00 ET lunch lull. By 13:30 ET institutional order
    flow is back, revealing afternoon trend continuations and reversals.
    """
    logger.info("=== AFTERNOON SCREEN (13:30 ET) ===")
    _run_script("nx_screener_longs.py", timeout=900)
    _run_script("nx_screener_production.py", ["--mode", "all"], timeout=1800)
    _run_script("mr_screener.py", timeout=300)
    _run_script("pairs_screener.py", timeout=300)
    _run_script("export_tv_watchlist.py")
    logger.info("=== AFTERNOON SCREEN COMPLETE ===")


def job_afternoon_execute() -> None:
    """11:45 MT (13:45 ET) — Execute on afternoon signals + pairs + MR + options."""
    logger.info("=== AFTERNOON EXECUTION (13:45 ET) ===")
    _run_script("execute_longs.py", timeout=300)
    _run_script("execute_dual_mode.py", timeout=300)
    _run_script("execute_mean_reversion.py", timeout=300)
    _run_script("execute_pairs.py", timeout=300)
    _run_script("auto_options_executor.py", timeout=300)
    logger.info("=== AFTERNOON EXECUTION COMPLETE ===")


def job_preclose_screen() -> None:
    """13:30 MT (15:30 ET) — Final screen of the day, 30 min before close.

    Catches late-day momentum setups and refreshes watchlist data so the
    screener staleness alert doesn't fire during post-market hours.
    """
    logger.info("=== PRE-CLOSE SCREEN (15:30 ET) ===")
    _run_script("nx_screener_longs.py", timeout=900)
    _run_script("nx_screener_production.py", ["--mode", "all"], timeout=1800)
    _run_script("mr_screener.py", timeout=300)
    _run_script("export_tv_watchlist.py")
    logger.info("=== PRE-CLOSE SCREEN COMPLETE ===")


def job_preclose() -> None:
    """14:00 MT — Portfolio snapshot, daily report, unified positions email."""
    logger.info("=== PRE-CLOSE ===")
    _run_script("portfolio_snapshot.py", timeout=120)
    _run_script("daily_report.py", timeout=120)
    # Single unified email: stocks + options, no account overview
    _run_script("daily_options_email.py", timeout=120)
    logger.info("=== PRE-CLOSE COMPLETE ===")


def job_tax_loss_harvest() -> None:
    """Friday 13:00 MT — Weekly tax-loss harvest: scan + auto-execute qualifying positions."""
    logger.info("=== TAX-LOSS HARVEST ===")
    _run_script("tax_loss_harvester.py", args=["--execute"], timeout=300)
    logger.info("=== TAX-LOSS HARVEST COMPLETE ===")


def job_postclose() -> None:
    """14:30 MT — Adaptive learning, strategy analytics, EOD analysis."""
    logger.info("=== POST-CLOSE ===")
    _run_script("strategy_analytics.py", timeout=300)
    _run_script("adaptive_params.py", timeout=120)
    _run_script("sector_rotation.py", timeout=120)
    _run_script("sync_current_shorts.py")
    _run_script("eod_analysis.py", timeout=120)
    # End-of-day intelligence refresh with final prices
    _run_script("portfolio_greeks.py", timeout=120)
    _run_script("scenario_engine.py", timeout=60)
    _run_script("portfolio_intelligence.py", timeout=60)
    logger.info("=== POST-CLOSE COMPLETE ===")


def job_ext_hours_premarket() -> None:
    """05:30 MT (07:30 ET) — Execute any queued extended-hours pre-market orders."""
    logger.info("=== PRE-MARKET EXT-HOURS ===")
    _run_script("execute_ext_hours.py", timeout=120)
    logger.info("=== PRE-MARKET EXT-HOURS COMPLETE ===")


def job_ext_hours_afterhours() -> None:
    """16:45 MT (18:45 ET) — Execute any queued extended-hours after-hours orders."""
    logger.info("=== AFTER-HOURS EXT-HOURS ===")
    _run_script("execute_ext_hours.py", timeout=120)
    logger.info("=== AFTER-HOURS EXT-HOURS COMPLETE ===")


def job_restructure_phase1() -> None:
    """Tue 07:35 MT — Phase 1: Close decay hedges + worst energy names."""
    logger.info("=== PORTFOLIO RESTRUCTURE — PHASE 1 ===")
    _run_script("portfolio_restructure.py", ["--phase", "1", "--live"], timeout=600)
    logger.info("=== PORTFOLIO RESTRUCTURE — PHASE 1 COMPLETE ===")


def job_restructure_phase2() -> None:
    """Wed 07:35 MT — Phase 2: Close ETFs + weak discretionary names."""
    logger.info("=== PORTFOLIO RESTRUCTURE — PHASE 2 ===")
    _run_script("portfolio_restructure.py", ["--phase", "2", "--live"], timeout=600)
    logger.info("=== PORTFOLIO RESTRUCTURE — PHASE 2 COMPLETE ===")


def job_restructure_phase3() -> None:
    """Fri 07:35 MT — Phase 3: Auto-review MAYBE positions by momentum."""
    logger.info("=== PORTFOLIO RESTRUCTURE — PHASE 3 ===")
    _run_script("portfolio_restructure.py", ["--phase", "3", "--live"], timeout=600)
    logger.info("=== PORTFOLIO RESTRUCTURE — PHASE 3 COMPLETE ===")


def job_options_backtest() -> None:
    """Friday post-close — backtest options strategies and update optimal params."""
    logger.info("=== OPTIONS BACKTESTER ===")
    _run_script("options_backtester.py", ["--months", "6"], timeout=600)
    logger.info("=== OPTIONS BACKTESTER COMPLETE ===")


def _file_age_hours(path: Path) -> float:
    """Return age of file in hours, or infinity if it doesn't exist."""
    import time as _time
    if not path.exists():
        return float("inf")
    return (_time.time() - path.stat().st_mtime) / 3600


def job_sunday_catchup() -> None:
    """Sunday 18:00 MT — re-run any Friday post-close jobs that failed or were missed.

    Checks staleness of each output file before running so this is a no-op
    if everything completed successfully on Friday.
    """
    logger.info("=== SUNDAY CATCH-UP ===")
    ran_any = False

    # Options backtester — re-run if results are more than 48 h old (missed Friday run)
    backtest_age = _file_age_hours(LOGS_DIR / "backtest_results.json")
    if backtest_age > 48:
        logger.info(
            "backtest_results.json is %.0f h old — re-running options backtester", backtest_age
        )
        _run_script("options_backtester.py", ["--months", "6"], timeout=600)
        ran_any = True
    else:
        logger.info("Options backtester: up-to-date (%.0f h old) — skipping", backtest_age)

    # Pairs screener — re-run if watchlist is more than 48 h old
    pairs_age = _file_age_hours(TRADING_DIR / "watchlist_pairs.json")
    if pairs_age > 48:
        logger.info(
            "watchlist_pairs.json is %.0f h old — re-running pairs screener", pairs_age
        )
        _run_script("pairs_screener.py", timeout=300)
        ran_any = True
    else:
        logger.info("Pairs screener: up-to-date (%.0f h old) — skipping", pairs_age)

    # Tax-loss harvest — re-run if no log written this week (log file older than 7 days)
    harvest_age = _file_age_hours(LOGS_DIR / "tax_loss_harvest.log")
    if harvest_age > 72:
        logger.info(
            "tax_loss_harvest.log is %.0f h old — re-running tax-loss harvest", harvest_age
        )
        _run_script("tax_loss_harvester.py", args=["--execute"], timeout=300)
        ran_any = True
    else:
        logger.info("Tax-loss harvest: up-to-date (%.0f h old) — skipping", harvest_age)

    if not ran_any:
        logger.info("All Friday post-close jobs completed successfully — nothing to catch up.")

    logger.info("=== SUNDAY CATCH-UP COMPLETE ===")


def job_dashboard_refresh() -> None:
    """Every 5 min during market hours — refresh dashboard snapshot data."""
    _run_script("portfolio_snapshot.py", timeout=60)
    _run_script("dashboard_data_aggregator.py", timeout=120)


def job_ext_hours_refresh() -> None:
    """Extended-hours lightweight refresh — portfolio snapshot + dashboard aggregator only.

    Fires every 15 min in pre-market (3–6 AM MT / 5–8 AM ET) and
    every 10 min in after-hours (16–17 MT / 18–19 ET). Skips heavy
    analytics scripts that are only meaningful during RTH.
    """
    _run_script("portfolio_snapshot.py", timeout=60)
    _run_script("dashboard_data_aggregator.py", timeout=120)


def job_paper_snapshot() -> None:
    """Every 5 min — refresh paper-account dashboard snapshot (port 4002).

    Only runs when the paper IB Gateway is reachable. Produces
    dashboard_snapshot_paper.json so the Paper view tab in the dashboard
    shows live paper-account data. Safe to leave registered even when the
    paper gateway is not running — it silently skips if port 4002 is closed.
    """
    import socket
    try:
        with socket.create_connection(("127.0.0.1", 4002), timeout=2):
            pass
    except OSError:
        logger.debug("Paper gateway not reachable on port 4002 — skipping paper snapshot")
        return

    logger.info("Paper gateway detected — running paper snapshot aggregator")
    env_paper = TRADING_DIR / ".env.paper"
    if not env_paper.exists():
        logger.warning("Missing %s — cannot run paper snapshot", env_paper)
        return

    # Run the aggregator with paper env vars injected as overrides
    extra_env = {
        **os.environ.copy(),
        "TRADING_MODE": "paper",
        "IB_PORT": "4002",
    }
    # Load any extra vars from .env.paper that the aggregator needs
    try:
        for line in env_paper.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            # Don't let .env.paper override already-set live secrets (Telegram etc.)
            if key not in ("TRADING_MODE", "IB_PORT", "IB_HOST", "IB_CLIENT_ID"):
                continue
            extra_env[key] = val.strip()
    except OSError:
        pass

    script_path = SCRIPTS_DIR / "dashboard_data_aggregator.py"
    if not script_path.exists():
        logger.error("dashboard_data_aggregator.py not found")
        return

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            env=extra_env,
            timeout=120,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.warning("Paper snapshot failed (rc=%d): %s", result.returncode, result.stderr[:300])
        else:
            logger.info("Paper snapshot updated successfully")
    except subprocess.TimeoutExpired:
        logger.warning("Paper snapshot timed out after 120s")
    except Exception as exc:
        logger.error("Paper snapshot error: %s", exc)


def job_regime_check() -> None:
    """Twice-daily regime check: detect macro regime changes and alert via Telegram."""
    if not _is_trading_day():
        return
    try:
        import sys
        sys.path.insert(0, str(SCRIPTS_DIR))
        from regime_monitor import RegimeMonitor
        monitor = RegimeMonitor()
        result = monitor.check_and_alert()
        if result.get("alertNeeded"):
            prev = result.get("previousRegime", "UNKNOWN")
            curr = result.get("regime", "UNKNOWN")
            score = result.get("score", "?")
            try:
                from notifications import notify_critical
                notify_critical(
                    "Regime Change",
                    f"Macro regime shifted: {prev} → {curr} (score: {score})\n"
                    "Review allocations and open positions.",
                )
            except Exception:
                pass
            logger.warning("Regime change detected: %s → %s (score=%s)", prev, curr, score)
        else:
            logger.info("Regime check: %s (score=%s)", result.get("regime"), result.get("score"))

        # Persist the execution regime (Layer 1: SPY/VIX) to regime_context.json.
        # regime_monitor already wrote the macro band (Layer 2) to regime_state.json.
        # These are two independent vocabularies — do NOT mix them.
        try:
            from regime_detector import detect_market_regime, persist_regime_to_context
            execution_regime = detect_market_regime()
            persist_regime_to_context(execution_regime)
            logger.info("Execution regime persisted to context: %s", execution_regime)
        except Exception as exc:
            logger.warning("Could not persist regime to context (non-fatal): %s", exc)

    except Exception as exc:
        logger.warning("Regime check failed (non-fatal): %s", exc)


def _is_trading_day() -> bool:
    """Check if today is a US market trading day using NYSE calendar."""
    today = datetime.now().date()
    try:
        import pandas_market_calendars as mcal
        nyse = mcal.get_calendar("NYSE")
        today_str = today.strftime("%Y-%m-%d")
        schedule = nyse.schedule(start_date=today_str, end_date=today_str)
        return not schedule.empty
    except Exception:
        # Fallback to weekday check + static holiday list
        if today.weekday() >= 5:
            return False
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

    sched.add_job(job_overnight_sod, CronTrigger(
        day_of_week="mon-fri", hour=2, minute=0, timezone=TIMEZONE,
    ), id="overnight_sod", name="Overnight SOD capture (4:00 AM ET)")

    sched.add_job(job_position_integrity, CronTrigger(
        day_of_week="mon-fri", hour=6, minute=55, timezone=TIMEZONE,
    ), id="position_integrity", name="Position integrity check (6:55 AM MT, before market open)")

    sched.add_job(job_premarket, CronTrigger(
        day_of_week="mon-fri", hour=7, minute=0, timezone=TIMEZONE,
    ), id="premarket", name="Pre-market screeners")

    sched.add_job(job_pm_upgrade_check, CronTrigger(
        day_of_week="mon", hour=7, minute=1, start_date="2026-03-16", end_date="2026-03-17",
        timezone=TIMEZONE,
    ), id="pm_upgrade_check", name="Portfolio Margin activation snapshot (Mon Mar 16 only)")

    sched.add_job(job_market_open, CronTrigger(
        day_of_week="mon-fri", hour=7, minute=30, timezone=TIMEZONE,
    ), id="market_open", name="Market open execution")

    sched.add_job(job_options, CronTrigger(
        day_of_week="mon-fri", hour=8, minute=0, timezone=TIMEZONE,
    ), id="options", name="Options execution")

    sched.add_job(job_postopen_screen, CronTrigger(
        day_of_week="mon-fri", hour=8, minute=15, timezone=TIMEZONE,
    ), id="postopen_screen", name="Post-open screeners (10:15 ET)")

    sched.add_job(job_sector_rebalance, CronTrigger(
        day_of_week="mon-fri", hour=8, minute=45, timezone=TIMEZONE,
    ), id="sector_rebalance", name="Sector rebalance")
    sched.add_job(job_postopen_execute, CronTrigger(
        day_of_week="mon-fri", hour=8, minute=30, timezone=TIMEZONE,
    ), id="postopen_execute", name="Post-open execution (10:30 ET)")

    sched.add_job(job_afternoon_screen, CronTrigger(
        day_of_week="mon-fri", hour=11, minute=30, timezone=TIMEZONE,
    ), id="afternoon_screen", name="Afternoon screeners (13:30 ET)")

    sched.add_job(job_afternoon_execute, CronTrigger(
        day_of_week="mon-fri", hour=11, minute=45, timezone=TIMEZONE,
    ), id="afternoon_execute", name="Afternoon execution (13:45 ET)")

    sched.add_job(job_preclose_screen, CronTrigger(
        day_of_week="mon-fri", hour=13, minute=30, timezone=TIMEZONE,
    ), id="preclose_screen", name="Pre-close screeners (15:30 ET)")

    sched.add_job(job_preclose, CronTrigger(
        day_of_week="mon-fri", hour=14, minute=0, timezone=TIMEZONE,
    ), id="preclose", name="Pre-close snapshot")

    sched.add_job(job_postclose, CronTrigger(
        day_of_week="mon-fri", hour=14, minute=30, timezone=TIMEZONE,
    ), id="postclose", name="Post-close analytics")

    # RTH dashboard refresh — every 5 min, 7 AM–3:59 PM MT (9 AM–5:59 PM ET)
    sched.add_job(job_dashboard_refresh, CronTrigger(
        day_of_week="mon-fri", hour="7-15", minute="*/5", timezone=TIMEZONE,
    ), id="dashboard_refresh", name="Dashboard data refresh (RTH)")

    # Pre-market extended refresh — every 15 min, 3–6 AM MT (5–8 AM ET)
    sched.add_job(job_ext_hours_refresh, CronTrigger(
        day_of_week="mon-fri", hour="3-6", minute="*/15", timezone=TIMEZONE,
    ), id="ext_hours_refresh_premarket", name="Extended-hours refresh — pre-market (5–8 AM ET)")

    # After-hours extended refresh — every 10 min, 4–5:59 PM MT (6–7:59 PM ET)
    sched.add_job(job_ext_hours_refresh, CronTrigger(
        day_of_week="mon-fri", hour="16,17", minute="*/10", timezone=TIMEZONE,
    ), id="ext_hours_refresh_afterhours", name="Extended-hours refresh — after-hours (6–8 PM ET)")

    sched.add_job(job_paper_snapshot, CronTrigger(
        day_of_week="mon-fri", hour="7-15", minute="*/5", timezone=TIMEZONE,
    ), id="paper_snapshot", name="Paper account snapshot (port 4002, if running)")

    sched.add_job(job_regime_check, CronTrigger(
        day_of_week="mon-fri", hour="7,12", minute=45, timezone=TIMEZONE,
    ), id="regime_check", name="Macro regime monitoring")

    # Cash & leverage monitor — fires every 30 min 9:45–15:30 ET (7:45–13:30 MT)
    sched.add_job(job_cash_monitor, CronTrigger(
        day_of_week="mon-fri", hour="7-13", minute="15,45", timezone=TIMEZONE,
    ), id="cash_monitor", name="Cash & leverage monitor (every 30 min)")

    # Options position manager — profit-take, stop-loss, roll, expiry close
    sched.add_job(job_options_manager, CronTrigger(
        day_of_week="mon-fri", hour="8-13", minute="0,30", timezone=TIMEZONE,
    ), id="options_manager", name="Options position manager (every 30 min)")

    # Gap risk EOD check — 3:55 PM ET (13:55 MT)
    sched.add_job(job_gap_risk_eod, CronTrigger(
        day_of_week="mon-fri", hour=13, minute=55, timezone=TIMEZONE,
    ), id="gap_risk_eod", name="Gap risk EOD check (3:55 PM ET)")

    # Tax-loss harvest scan — Fridays at 1:00 PM MT (3:00 PM ET)
    sched.add_job(job_tax_loss_harvest, CronTrigger(
        day_of_week="fri", hour=13, minute=0, timezone=TIMEZONE,
    ), id="tax_loss_harvest", name="Tax-loss harvest scan (Fri 3:00 PM ET)")

    # Extended-hours executor — fires if watchlist_ext_hours.json has entries
    # Pre-market: 5:30 AM MT (7:30 ET) — before regular open
    sched.add_job(job_ext_hours_premarket, CronTrigger(
        day_of_week="mon-fri", hour=5, minute=30, timezone=TIMEZONE,
    ), id="ext_hours_premarket", name="Extended-hours pre-market orders (7:30 ET)")

    # After-hours: 4:45 PM MT (6:45 ET) — well into after-hours window
    sched.add_job(job_ext_hours_afterhours, CronTrigger(
        day_of_week="mon-fri", hour=16, minute=45, timezone=TIMEZONE,
    ), id="ext_hours_afterhours", name="Extended-hours after-hours orders (6:45 ET)")

    # Portfolio restructure — phased liquidation (one-week event, becomes no-ops after)
    sched.add_job(job_restructure_phase1, CronTrigger(
        day_of_week="tue", hour=7, minute=35, timezone=TIMEZONE,
    ), id="restructure_phase1", name="Portfolio restructure Phase 1 — hedges + energy (Tue 9:35 ET)")

    sched.add_job(job_restructure_phase2, CronTrigger(
        day_of_week="wed", hour=7, minute=35, timezone=TIMEZONE,
    ), id="restructure_phase2", name="Portfolio restructure Phase 2 — ETFs + weak (Wed 9:35 ET)")

    sched.add_job(job_restructure_phase3, CronTrigger(
        day_of_week="fri", hour=7, minute=35, timezone=TIMEZONE,
    ), id="restructure_phase3", name="Portfolio restructure Phase 3 — MAYBE review (Fri 9:35 ET)")

    # Options backtester — Fridays post-close at 3:00 PM MT (5:00 PM ET)
    sched.add_job(job_options_backtest, CronTrigger(
        day_of_week="fri", hour=15, minute=0, timezone=TIMEZONE,
    ), id="options_backtest", name="Options strategy backtester (Fri post-close)")

    # Sunday catch-up — re-run any Friday post-close jobs that failed/were missed
    sched.add_job(job_sunday_catchup, CronTrigger(
        day_of_week="sun", hour=18, minute=0, timezone=TIMEZONE,
    ), id="sunday_catchup", name="Sunday catch-up (backtest + pairs + tax-loss if stale)")

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
        ("02:00 MT", "04:00 ET", "Overnight SOD", "portfolio_snapshot → overnight_sod_capture → dashboard_data_aggregator"),
        ("03:00 MT", "05:00 ET", "Pre-Mkt Refresh", "portfolio_snapshot + dashboard_data_aggregator (every 15 min until 7 AM MT)"),
        ("05:30 MT", "07:30 ET", "Pre-Mkt Orders", "execute_ext_hours (if watchlist_ext_hours.json has entries)"),
        ("Tue 07:35", "09:35 ET", "Restructure Ph1", "portfolio_restructure --phase 1 (hedges + energy)"),
        ("Wed 07:35", "09:35 ET", "Restructure Ph2", "portfolio_restructure --phase 2 (ETFs + weak)"),
        ("Fri 07:35", "09:35 ET", "Restructure Ph3", "portfolio_restructure --phase 3 (MAYBE review)"),
        ("07:00 MT", "09:00 ET", "Pre-market", "sync_current_shorts → nx_screener_production → nx_screener_longs → mr_screener → export_tv_watchlist"),
        ("07:30 MT", "09:30 ET", "Market Open", "execute_longs → execute_dual_mode → execute_mean_reversion"),
        ("08:00 MT", "10:00 ET", "Options", "auto_options_executor"),
        ("*/30 MT", "9:45–15:30 ET", "Cash Monitor", "cash_monitor (every 30 min)"),
        ("*/30 MT", "10:00–15:30 ET", "Options Manager", "options_position_manager (profit/roll/stop)"),
        ("13:55 MT", "15:55 ET", "Gap Risk EOD", "gap_risk_eod_check"),
        ("08:15 MT", "10:15 ET", "Post-Open Screen", "nx_screener_longs → nx_screener_production → mr_screener → export_tv_watchlist"),
        ("08:30 MT", "10:30 ET", "Post-Open Execute", "execute_longs → execute_dual_mode → execute_mean_reversion"),
        ("11:30 MT", "13:30 ET", "Afternoon Screen", "nx_screener_longs → nx_screener_production → mr_screener → pairs_screener → export_tv_watchlist"),
        ("11:45 MT", "13:45 ET", "Afternoon Execute", "execute_longs → execute_dual_mode → execute_mean_reversion → execute_pairs → auto_options_executor"),
        ("13:30 MT", "15:30 ET", "Pre-Close Screen", "nx_screener_longs → nx_screener_production → mr_screener → export_tv_watchlist"),
        ("14:00 MT", "16:00 ET", "Pre-Close", "portfolio_snapshot → daily_report → daily_options_email"),
        ("14:30 MT", "16:30 ET", "Post-Close", "strategy_analytics → adaptive_params → sector_rotation → sync_current_shorts → eod_analysis"),
        ("16:00 MT", "18:00 ET", "After-Hrs Refresh", "portfolio_snapshot + dashboard_data_aggregator (every 10 min until 6 PM MT)"),
        ("16:45 MT", "18:45 ET", "After-Hrs Orders", "execute_ext_hours (if watchlist_ext_hours.json has entries)"),
        ("Sun 18:00 MT", "20:00 ET", "Sunday Catch-up", "options_backtester + pairs_screener + tax_loss_harvester (only if stale)"),
        ("Always", "      ", "Background", "risk_monitor + reconnection_agent + trade_outcome_resolver (via run_all.py)"),
        ("Always", "      ", "Webhook", "FastAPI server listening for TradingView pullback alerts"),
    ]
    print("\n  AUTOMATED TRADING SCHEDULE (Mon-Fri)")
    print("  " + "=" * 100)
    for time_mt, time_et, phase, scripts in schedule:
        print(f"  {time_mt:<12} {time_et:<10} {phase:<20} {scripts}")
    print("  " + "=" * 100)
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Automated trading scheduler")
    parser.add_argument("--dry-run", action="store_true", help="Print schedule without starting")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[logging.StreamHandler()],
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
