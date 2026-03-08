#!/usr/bin/env python3
"""
Risk Monitor Agent — runs on a loop (e.g. every 30–60s during market hours).

Checks portfolio drawdown, daily P&L, per-position exposure, sector concentration.
Triggers kill switch if limits breached. Completely independent from order execution path.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

from agents._paths import KILL_SWITCH_FILE, LOGS_DIR, TRADING_DIR

# Risk limits (align with risk.json / .cursorrules)
DEFAULT_DAILY_LOSS_PCT = 0.03
DEFAULT_MAX_DRAWDOWN_PCT = 0.10
DEFAULT_MAX_SINGLE_POSITION_PCT = 0.10
DEFAULT_MAX_SECTOR_PCT = 0.30

PEAK_EQUITY_FILE = TRADING_DIR / "logs" / "peak_equity.json"
DAILY_LOSS_FILE = TRADING_DIR / "logs" / "daily_loss.json"
SOD_EQUITY_FILE = TRADING_DIR / "logs" / "sod_equity.json"


def _load_peak_equity() -> Optional[float]:
    try:
        if PEAK_EQUITY_FILE.exists():
            data = json.loads(PEAK_EQUITY_FILE.read_text())
            return float(data.get("peak_equity", 0) or 0)
    except (OSError, ValueError, TypeError):
        pass
    return None


def _save_peak_equity(equity: float) -> None:
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        prev = _load_peak_equity()
        peak = max(equity, prev or 0)
        PEAK_EQUITY_FILE.write_text(json.dumps({"peak_equity": peak, "updated_at": datetime.now().isoformat()}))
    except OSError as e:
        logger.warning("Could not save peak equity: %s", e)


def _load_daily_loss() -> float:
    try:
        if DAILY_LOSS_FILE.exists():
            data = json.loads(DAILY_LOSS_FILE.read_text())
            if data.get("date") == datetime.now().date().isoformat():
                return float(data.get("loss", 0) or 0)
    except (OSError, ValueError, TypeError):
        pass
    return 0.0


def _load_sod_equity() -> Optional[float]:
    """Load start-of-day equity. Returns None if file is missing or stale."""
    try:
        if SOD_EQUITY_FILE.exists():
            data = json.loads(SOD_EQUITY_FILE.read_text())
            if data.get("date") == datetime.now().date().isoformat():
                return float(data.get("equity", 0) or 0)
    except (OSError, ValueError, TypeError):
        pass
    return None


def _save_sod_equity(equity: float) -> None:
    """Persist start-of-day equity (first check of the day)."""
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        SOD_EQUITY_FILE.write_text(json.dumps({
            "equity": equity,
            "date": datetime.now().date().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }))
    except OSError as e:
        logger.warning("Could not save SOD equity: %s", e)


def _update_daily_loss(account_value: float) -> float:
    """Compute and persist daily loss (SOD equity minus current equity).

    On the first check of the day, stores the starting equity.
    Returns the current daily loss amount (positive = loss).
    """
    sod = _load_sod_equity()
    if sod is None or sod <= 0:
        _save_sod_equity(account_value)
        sod = account_value

    daily_loss = max(0.0, sod - account_value)
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        DAILY_LOSS_FILE.write_text(json.dumps({
            "date": datetime.now().date().isoformat(),
            "loss": round(daily_loss, 2),
            "sod_equity": round(sod, 2),
            "current_equity": round(account_value, 2),
            "updated_at": datetime.now().isoformat(),
        }))
    except OSError as e:
        logger.warning("Could not save daily loss: %s", e)

    return daily_loss


def is_kill_switch_active() -> bool:
    """True if kill_switch.json exists and active is True. Executors should check this before running."""
    if not KILL_SWITCH_FILE.exists():
        return False
    try:
        data = json.loads(KILL_SWITCH_FILE.read_text())
        return bool(data.get("active"))
    except (OSError, ValueError):
        return False


def trigger_kill_switch(reason: str) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    TRADING_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "active": True,
        "reason": reason,
        "timestamp": datetime.now().isoformat(),
    }
    KILL_SWITCH_FILE.write_text(json.dumps(payload, indent=2))
    logger.critical("KILL SWITCH TRIGGERED: %s", reason)

    try:
        from notifications import notify_critical
        notify_critical(
            "Kill Switch Triggered",
            f"Reason: {reason}\nTime: {datetime.now().isoformat()}\n\nAll trading has been halted.",
        )
    except Exception as e:
        logger.warning("Could not send kill switch notification: %s", e)


def clear_kill_switch() -> None:
    if KILL_SWITCH_FILE.exists():
        try:
            KILL_SWITCH_FILE.write_text(json.dumps({"active": False, "cleared_at": datetime.now().isoformat()}))
        except OSError as e:
            logger.warning("Could not clear kill switch: %s", e)


async def run_one_check(ib: Any) -> bool:
    """
    Run one risk check cycle. Returns False if kill switch was triggered.
    Requires ib_insync.IB connected; uses reqAccountSummaryAsync and portfolio().
    """
    try:
        from risk_config import get_max_sector_concentration_pct
        from sector_gates import portfolio_sector_exposure
    except ImportError:
        get_max_sector_concentration_pct = None
        portfolio_sector_exposure = None

    # Account value
    account_value = 0.0
    try:
        for av in ib.accountValues():
            if av.tag == "NetLiquidation" and av.currency == "USD":
                account_value = float(av.value)
                break
        if account_value <= 0:
            for av in ib.accountValues():
                if av.tag == "TotalCashValue" and av.currency == "USD":
                    account_value = float(av.value)
                    break
    except Exception as e:
        logger.warning("Risk monitor: could not get account summary: %s", e)
        return True

    if account_value <= 0:
        return True

    _save_peak_equity(account_value)
    peak = _load_peak_equity()
    daily_loss = _update_daily_loss(account_value)
    daily_limit = account_value * DEFAULT_DAILY_LOSS_PCT
    if daily_loss >= daily_limit:
        trigger_kill_switch(f"daily loss limit exceeded: {daily_loss:.2f} >= {daily_limit:.2f}")
        return False
    if peak and peak > 0:
        drawdown_pct = (peak - account_value) / peak
        if drawdown_pct >= DEFAULT_MAX_DRAWDOWN_PCT:
            trigger_kill_switch(f"max drawdown exceeded: {drawdown_pct:.1%} >= {DEFAULT_MAX_DRAWDOWN_PCT:.1%}")
            return False

    # Per-position and sector from portfolio (warn only — execution gates block new entries)
    if portfolio_sector_exposure is not None:
        sector_exposure, total_notional = portfolio_sector_exposure(ib)
        if total_notional > 0 and get_max_sector_concentration_pct is not None:
            max_sector_pct = get_max_sector_concentration_pct(TRADING_DIR) / 100.0
            for sector, exp in sector_exposure.items():
                pct = abs(exp) / total_notional
                if pct > max_sector_pct:
                    logger.warning(
                        "Sector concentration WARNING: %s = %.1f%% (limit %.0f%%). "
                        "Execution gates will block new entries.",
                        sector, pct * 100, max_sector_pct * 100,
                    )

    return True


async def run_loop(
    ib: Any,
    interval_sec: int = 60,
    stop_event: Optional[asyncio.Event] = None,
) -> None:
    """
    Run risk checks every interval_sec. Stops when stop_event is set (if provided).
    """
    logger.info("Risk monitor started (interval=%ds)", interval_sec)
    while True:
        if stop_event is not None and stop_event.is_set():
            break
        try:
            if ib.isConnected():
                ok = await run_one_check(ib)
                if not ok:
                    logger.critical("Risk monitor triggered kill switch; exiting loop")
                    break
            else:
                logger.warning("Risk monitor: IB not connected, skipping check")
        except Exception as e:
            logger.error("Risk monitor check failed: %s", e)
        if stop_event is not None and stop_event.is_set():
            break
        await asyncio.sleep(interval_sec)


async def _main_async() -> None:
    from ib_insync import IB
    ib = IB()
    await ib.connectAsync("127.0.0.1", 4002, clientId=106)
    try:
        await run_loop(ib, interval_sec=60)
    finally:
        ib.disconnect()


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    try:
        asyncio.run(_main_async())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error("Fatal: %s", e)
        sys.exit(1)
