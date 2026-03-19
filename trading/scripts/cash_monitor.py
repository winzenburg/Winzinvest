#!/usr/bin/env python3
"""
Cash & Leverage Monitor
=======================
Runs every 30 minutes during market hours.  Checks two conditions:

  1. CASH DRAG:     Cash > CASH_IDLE_THRESHOLD_PCT of NLV
                    → trigger premium selling (auto_options_executor.py)

  2. LEVERAGE GAP:  Gross Position Value < LEVERAGE_TARGET_PCT of NLV
                    → trigger equity screener + executor to deploy capital

If neither condition is met, the script exits silently (no work to do).

Configuration (all in risk.json):
  cash_monitor.cash_idle_threshold_pct      default 0.15  (fire when cash > 15% NLV)
  cash_monitor.leverage_target_pct          default 1.60  (target 1.6x gross leverage)
  cash_monitor.leverage_floor_pct           default 1.40  (alert below 1.4x)
  cash_monitor.min_premium_trigger_usd      default 50000 (only fire if >$50k idle)
  cash_monitor.cooldown_minutes             default 90    (don't re-fire within 90 min)
"""
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPTS_DIR  = Path(__file__).resolve().parent
TRADING_DIR  = SCRIPTS_DIR.parent
LOGS_DIR     = TRADING_DIR / "logs"
RISK_PATH    = TRADING_DIR / "risk.json"
STATE_PATH   = TRADING_DIR / "config" / "cash_monitor_state.json"
ENV_PATH     = TRADING_DIR / ".env"

LOGS_DIR.mkdir(exist_ok=True)
STATE_PATH.parent.mkdir(exist_ok=True)

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [cash_monitor] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGS_DIR / "cash_monitor.log"),
    ],
)
log = logging.getLogger("cash_monitor")

# ── Load .env ─────────────────────────────────────────────────────────────────
if ENV_PATH.exists():
    for line in ENV_PATH.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "4002"))
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT  = os.getenv("TELEGRAM_CHAT_ID", "")

# ── Defaults ──────────────────────────────────────────────────────────────────
CASH_IDLE_THRESHOLD_PCT  = 0.15   # trigger premium selling when cash > 15% NLV
LEVERAGE_TARGET_PCT      = 1.60   # aim for 1.6x gross leverage
LEVERAGE_FLOOR_PCT       = 1.40   # alert below 1.4x
MIN_PREMIUM_TRIGGER_USD  = 50_000 # only act if idle cash exceeds $50k
COOLDOWN_MINUTES         = 90     # don't re-trigger within 90 minutes


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cfg() -> dict:
    try:
        return json.loads(RISK_PATH.read_text()).get("cash_monitor", {})
    except Exception:
        return {}


def _threshold() -> float:
    return float(_cfg().get("cash_idle_threshold_pct", CASH_IDLE_THRESHOLD_PCT))


def _leverage_target() -> float:
    return float(_cfg().get("leverage_target_pct", LEVERAGE_TARGET_PCT))


def _leverage_floor() -> float:
    return float(_cfg().get("leverage_floor_pct", LEVERAGE_FLOOR_PCT))


def _min_trigger() -> float:
    return float(_cfg().get("min_premium_trigger_usd", MIN_PREMIUM_TRIGGER_USD))


def _cooldown_minutes() -> int:
    return int(_cfg().get("cooldown_minutes", COOLDOWN_MINUTES))


def _load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2))


def _notify(msg: str) -> None:
    log.info(msg)
    try:
        from notifications import send_telegram
        send_telegram(f"[cash_monitor] {msg}")
    except ImportError:
        if TG_TOKEN and TG_CHAT:
            try:
                import urllib.request, urllib.parse
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
                data = urllib.parse.urlencode({"chat_id": TG_CHAT, "text": f"[cash_monitor] {msg}"}).encode()
                urllib.request.urlopen(url, data=data, timeout=5)
            except Exception:
                pass


def _in_market_hours() -> bool:
    """Return True between 9:30 AM and 3:45 PM ET on weekdays."""
    import zoneinfo
    now_et = datetime.now(zoneinfo.ZoneInfo("America/New_York"))
    if now_et.weekday() >= 5:
        return False
    open_t  = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    close_t = now_et.replace(hour=15, minute=45, second=0, microsecond=0)
    return open_t <= now_et <= close_t


def _on_cooldown(action: str) -> bool:
    """True if this action was triggered within the cooldown window."""
    state = _load_state()
    last_str = state.get(f"last_{action}")
    if not last_str:
        return False
    last = datetime.fromisoformat(last_str)
    return datetime.now() - last < timedelta(minutes=_cooldown_minutes())


def _mark_triggered(action: str) -> None:
    state = _load_state()
    state[f"last_{action}"] = datetime.now().isoformat()
    _save_state(state)


def _run(script: str, label: str) -> bool:
    """Run a script in the scripts directory, return True on success."""
    path = SCRIPTS_DIR / script
    if not path.exists():
        log.error(f"Script not found: {path}")
        return False
    log.info(f"Launching: {script}")
    result = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(SCRIPTS_DIR),
        capture_output=False,
        timeout=600,
    )
    success = result.returncode == 0
    log.info(f"{label} finished — returncode={result.returncode}")
    return success


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    _mode = os.getenv("TRADING_MODE", "paper")
    if _mode == "live":
        log.warning("🔴 LIVE TRADING MODE — real money at risk")
    log.info("Cash Monitor [%s]", _mode.upper())

    if not _in_market_hours():
        log.info("Outside market hours — nothing to do.")
        return

    # ── Connect & fetch account snapshot ─────────────────────────────────────
    try:
        from ib_insync import IB
    except ImportError:
        log.error("ib_insync not installed")
        return

    ib = IB()
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=193, timeout=10)
    except Exception as e:
        log.error(f"IB connect failed: {e}")
        return

    try:
        tags = {
            "NetLiquidation", "TotalCashValue", "GrossPositionValue",
            "AvailableFunds", "BuyingPower",
        }
        vals: dict[str, float] = {}
        for v in ib.accountSummary():
            if v.tag in tags and v.currency == "USD":
                vals[v.tag] = float(v.value)
    finally:
        ib.disconnect()

    nlv  = vals.get("NetLiquidation", 0)
    cash = vals.get("TotalCashValue", 0)
    gpv  = vals.get("GrossPositionValue", 0)
    avail = vals.get("AvailableFunds", 0)

    if nlv <= 0:
        log.warning("Could not read NLV — aborting.")
        return

    cash_pct      = cash / nlv
    leverage_used = gpv / nlv
    leverage_gap  = _leverage_target() - leverage_used
    idle_usd      = cash - (nlv * _threshold())   # cash above the idle threshold

    log.info(
        f"Account snapshot: NLV=${nlv:,.0f}  cash=${cash:,.0f} ({cash_pct:.1%})  "
        f"GPV=${gpv:,.0f}  leverage={leverage_used:.2f}x"
    )

    # ── Condition 1: Too much idle cash → sell premium ───────────────────────
    cash_trigger = (
        cash_pct > _threshold()
        and idle_usd >= _min_trigger()
        and not _on_cooldown("premium")
    )
    if cash_trigger:
        _notify(
            f"💰 Cash Drag Alert: ${cash:,.0f} cash ({cash_pct:.1%} of NLV) "
            f"exceeds {_threshold():.0%} threshold.\n"
            f"~${idle_usd:,.0f} idle above floor. Triggering premium selling..."
        )
        _mark_triggered("premium")
        # Re-run screeners first so we have fresh candidates, then execute
        _run("nx_screener_production.py", "Production screener")
        _run("auto_options_executor.py", "Options executor")
    else:
        reasons = []
        if cash_pct <= _threshold():
            reasons.append(f"cash {cash_pct:.1%} ≤ threshold {_threshold():.0%}")
        if idle_usd < _min_trigger():
            reasons.append(f"idle ${idle_usd:,.0f} < min ${_min_trigger():,.0f}")
        if _on_cooldown("premium"):
            reasons.append("on cooldown")
        log.info(f"Premium trigger: NO ({', '.join(reasons)})")

    # ── Condition 2: Leverage below target → deploy equity capital ───────────
    lev_trigger = (
        leverage_used < _leverage_floor()
        and leverage_gap > 0.10        # at least 10% leverage gap
        and avail > 50_000             # have available funds
        and not _on_cooldown("equity")
    )
    if lev_trigger:
        deploy_target = (nlv * _leverage_target()) - gpv
        _notify(
            f"📉 Leverage Gap Alert: {leverage_used:.2f}x used vs {_leverage_target():.1f}x target.\n"
            f"~${deploy_target:,.0f} could be deployed. Running screeners + executors..."
        )
        _mark_triggered("equity")
        _run("nx_screener_longs.py",     "Longs screener")
        _run("nx_screener_production.py","Production screener")
        _run("execute_longs.py",          "Longs executor")
        _run("execute_dual_mode.py",      "Dual-mode executor")
    else:
        if not lev_trigger and leverage_used >= _leverage_floor():
            log.info(f"Leverage trigger: NO (leverage {leverage_used:.2f}x ≥ floor {_leverage_floor():.2f}x)")

    # ── Summary ───────────────────────────────────────────────────────────────
    log.info(
        f"Done. cash_trigger={cash_trigger}  lev_trigger={lev_trigger}  "
        f"leverage={leverage_used:.2f}x  cash={cash_pct:.1%}"
    )


if __name__ == "__main__":
    main()
