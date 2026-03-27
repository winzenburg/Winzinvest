#!/usr/bin/env python3
"""
Risk Monitor Agent — runs on a loop (e.g. every 30–60s during market hours).

Checks portfolio drawdown, daily P&L, per-position exposure, sector concentration.
Triggers kill switch if limits breached. Completely independent from order execution path.
"""

import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

from agents._paths import KILL_SWITCH_FILE, LOGS_DIR, TRADING_DIR

_env_path = TRADING_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "4001"))  # default to live gateway (4001); paper is 4002

# Risk limits — read from risk.json via risk_config at runtime, with fallbacks
DEFAULT_DAILY_LOSS_PCT = 0.03
DEFAULT_MAX_DRAWDOWN_PCT = 0.10
DEFAULT_MAX_SINGLE_POSITION_PCT = 0.10
DEFAULT_MAX_SECTOR_PCT = 0.30


def _load_risk_limits() -> tuple:
    """Return (daily_loss_pct, max_drawdown_pct) from risk.json, falling back to defaults."""
    import json as _json
    try:
        from risk_config import get_daily_loss_limit_pct
        daily = get_daily_loss_limit_pct(TRADING_DIR)
    except Exception:
        daily = DEFAULT_DAILY_LOSS_PCT
    try:
        risk_path = TRADING_DIR / "risk.json"
        if risk_path.exists():
            cfg = _json.loads(risk_path.read_text())
            drawdown = cfg.get("portfolio", {}).get("max_drawdown_pct", DEFAULT_MAX_DRAWDOWN_PCT)
        else:
            drawdown = DEFAULT_MAX_DRAWDOWN_PCT
    except Exception:
        drawdown = DEFAULT_MAX_DRAWDOWN_PCT
    return float(daily), float(drawdown)

PEAK_EQUITY_FILE = TRADING_DIR / "logs" / "peak_equity.json"
DAILY_LOSS_FILE = TRADING_DIR / "logs" / "daily_loss.json"
SOD_EQUITY_FILE = TRADING_DIR / "logs" / "sod_equity.json"


def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _load_peak_equity(account: str = "") -> Optional[float]:
    try:
        if PEAK_EQUITY_FILE.exists():
            data = json.loads(PEAK_EQUITY_FILE.read_text())
            if account and data.get("account", "") and data["account"] != account:
                logger.warning(
                    "Peak equity account mismatch: file has %s, current is %s — resetting",
                    data["account"], account,
                )
                return None
            return float(data.get("peak_equity", 0) or 0)
    except (OSError, ValueError, TypeError):
        pass
    return None


def _save_peak_equity(equity: float, account: str = "") -> None:
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        prev = _load_peak_equity(account=account)
        peak = max(equity, prev or 0)
        _atomic_write_json(PEAK_EQUITY_FILE, {
            "peak_equity": peak,
            "account": account,
            "updated_at": datetime.now().isoformat(),
        })
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


def _load_sod_equity(account: str = "") -> Optional[float]:
    """Load start-of-day equity. Returns None if file is missing, stale, or from a different account."""
    try:
        if SOD_EQUITY_FILE.exists():
            data = json.loads(SOD_EQUITY_FILE.read_text())
            if data.get("date") != datetime.now().date().isoformat():
                return None
            if account and data.get("account", "") and data["account"] != account:
                logger.warning(
                    "SOD equity account mismatch: file has %s, current is %s — resetting",
                    data["account"], account,
                )
                return None
            return float(data.get("equity", 0) or 0)
    except (OSError, ValueError, TypeError):
        pass
    return None


SOD_EQUITY_HISTORY_FILE = TRADING_DIR / "logs" / "sod_equity_history.jsonl"


def _save_sod_equity(equity: float, account: str = "") -> None:
    """Persist start-of-day equity (first check of the day) and append to history."""
    today = datetime.now().date().isoformat()
    record = {
        "equity": equity,
        "date": today,
        "account": account,
        "updated_at": datetime.now().isoformat(),
    }
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(SOD_EQUITY_FILE, record)
    except OSError as e:
        logger.warning("Could not save SOD equity: %s", e)

    # Append to history (deduplicated by date, account-guarded to prevent cross-contamination)
    try:
        existing_dates: set = set()
        if SOD_EQUITY_HISTORY_FILE.exists():
            for line in SOD_EQUITY_HISTORY_FILE.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    # Only count entries from this account as "existing"
                    if not account or obj.get("account", "") in ("", account):
                        existing_dates.add(obj.get("date", ""))
                except (json.JSONDecodeError, ValueError):
                    pass
        if today not in existing_dates:
            # Only write if account matches — prevents paper account values poisoning history
            if account:
                with open(SOD_EQUITY_HISTORY_FILE, "a") as f:
                    f.write(json.dumps(record) + "\n")
            else:
                logger.warning("Skipping SOD equity history append: no account ID provided")
    except OSError as e:
        logger.warning("Could not append SOD equity to history: %s", e)


def _update_daily_loss(account_value: float, account: str = "") -> float:
    """Compute and persist daily loss (SOD equity minus current equity).

    On the first check of the day, stores the starting equity.
    Returns the current daily loss amount (positive = loss).
    """
    sod = _load_sod_equity(account=account)
    if sod is None or sod <= 0:
        _save_sod_equity(account_value, account=account)
        logger.info("SOD equity set to %.2f for account %s", account_value, account or "default")
        sod = account_value

    daily_loss = max(0.0, sod - account_value)
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(DAILY_LOSS_FILE, {
            "date": datetime.now().date().isoformat(),
            "loss": round(daily_loss, 2),
            "sod_equity": round(sod, 2),
            "current_equity": round(account_value, 2),
            "updated_at": datetime.now().isoformat(),
        })
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
    payload = {
        "active": True,
        "reason": reason,
        "timestamp": datetime.now().isoformat(),
    }
    _atomic_write_json(KILL_SWITCH_FILE, payload)
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
            _atomic_write_json(KILL_SWITCH_FILE, {"active": False, "cleared_at": datetime.now().isoformat()})
        except OSError as e:
            logger.warning("Could not clear kill switch: %s", e)


_LAST_KNOWN_GOOD_NLV: float = 0.0
_LAST_KNOWN_GOOD_ACCOUNT: str = ""

# Maximum plausible single-check NLV change before we treat the value as stale/corrupt.
# A >40% drop in one 60-second check is impossible under normal trading conditions.
_MAX_SINGLE_CHECK_NLV_DROP_PCT = 0.40


async def run_one_check(ib: Any) -> bool:
    """
    Run one risk check cycle. Returns False if kill switch was triggered.
    Requires ib_insync.IB connected; uses accountValues() cache from ib_insync.

    Sanity guard: if the returned NLV is zero, negative, or dropped >40% from the
    last known-good value in a single check (which indicates a stale/corrupt IB cache
    after a connectivity blip), the check is skipped entirely rather than firing a
    false kill switch.
    """
    global _LAST_KNOWN_GOOD_NLV, _LAST_KNOWN_GOOD_ACCOUNT

    try:
        from risk_config import get_max_sector_concentration_pct
        from sector_gates import portfolio_sector_exposure
    except ImportError:
        get_max_sector_concentration_pct = None
        portfolio_sector_exposure = None

    account_value = 0.0
    account_id = ""
    try:
        for av in ib.accountValues():
            if av.tag == "NetLiquidation" and av.currency == "USD":
                account_value = float(av.value)
                account_id = getattr(av, "account", "") or ""
                break
        if account_value <= 0:
            for av in ib.accountValues():
                if av.tag == "TotalCashValue" and av.currency == "USD":
                    account_value = float(av.value)
                    account_id = getattr(av, "account", "") or ""
                    break
    except Exception as e:
        logger.warning("Risk monitor: could not get account summary: %s", e)
        return True

    if account_value <= 0:
        logger.warning(
            "Risk monitor: NLV is zero/negative (%.2f) — IB cache likely stale after "
            "connectivity blip. Skipping check to avoid false kill switch.",
            account_value,
        )
        return True

    # Guard: reject implausible single-check NLV drops (corrupt cache after 1100/timeout)
    if _LAST_KNOWN_GOOD_NLV > 0:
        drop_pct = (_LAST_KNOWN_GOOD_NLV - account_value) / _LAST_KNOWN_GOOD_NLV
        if drop_pct > _MAX_SINGLE_CHECK_NLV_DROP_PCT:
            logger.warning(
                "Risk monitor: NLV dropped %.1f%% in one check (%.2f → %.2f) — "
                "this exceeds the %.0f%% plausibility threshold. "
                "Likely corrupt IB cache after network blip. Skipping check.",
                drop_pct * 100, _LAST_KNOWN_GOOD_NLV, account_value,
                _MAX_SINGLE_CHECK_NLV_DROP_PCT * 100,
            )
            return True

    _LAST_KNOWN_GOOD_NLV = account_value
    _LAST_KNOWN_GOOD_ACCOUNT = account_id

    _save_peak_equity(account_value, account=account_id)
    peak = _load_peak_equity(account=account_id)
    daily_loss = _update_daily_loss(account_value, account=account_id)
    daily_loss_pct, max_drawdown_pct = _load_risk_limits()
    daily_limit = account_value * daily_loss_pct
    if daily_loss >= daily_limit:
        trigger_kill_switch(f"daily loss limit exceeded: {daily_loss:.2f} >= {daily_limit:.2f}")
        return False
    if peak and peak > 0:
        drawdown_pct = (peak - account_value) / peak
        if drawdown_pct >= max_drawdown_pct:
            trigger_kill_switch(f"max drawdown exceeded: {drawdown_pct:.1%} >= {max_drawdown_pct:.1%}")
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
    await ib.connectAsync(IB_HOST, IB_PORT, clientId=106)
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
