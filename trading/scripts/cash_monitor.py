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

Configuration (all in risk.json → cash_monitor):
  cash_idle_threshold_pct      0.15   (fire when cash > 15% NLV)
  leverage_target_pct          2.50   (PM target: 2.5x gross leverage)
  leverage_floor_pct           2.00   (alert below 2.0x)
  min_premium_trigger_usd      20000  (only fire if >$20k idle)
  cooldown_minutes             90     (don't re-fire within 90 min)
"""
import json
import logging
import os
import tempfile
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
LEVERAGE_TARGET_PCT      = 2.50   # PM target: 2.5x gross leverage
LEVERAGE_FLOOR_PCT       = 2.00   # alert below 2.0x
MIN_PREMIUM_TRIGGER_USD  = 20_000 # only act if idle cash exceeds $20k (matches risk.json)
COOLDOWN_MINUTES         = 90     # don't re-trigger within 90 minutes


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cfg() -> dict:
    try:
        return json.loads(RISK_PATH.read_text()).get("cash_monitor", {})
    except Exception:
        return {}


def _macro_defensive_mode() -> bool:
    """Return True if any active macro event has a negative size_multiplier_adjust."""
    try:
        macro_file = TRADING_DIR / "config" / "macro_events.json"
        events = json.loads(macro_file.read_text(encoding="utf-8"))
        return any(
            e.get("active") and float(e.get("size_multiplier_adjust", 0)) < 0
            for e in events
        )
    except Exception:
        return False


def _threshold() -> float:
    cfg = _cfg()
    if _macro_defensive_mode():
        defensive = cfg.get("defensive_cash_threshold_pct", 0.50)
        log.debug("Macro defensive mode active — using %.0f%% cash threshold", defensive * 100)
        return float(defensive)
    return float(cfg.get("cash_idle_threshold_pct", CASH_IDLE_THRESHOLD_PCT))


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
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=STATE_PATH.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
        os.replace(tmp, STATE_PATH)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


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


def _screener_is_running() -> bool:
    """Return True if any nx_screener process is already running.

    Prevents cash_monitor from spawning a second screener instance when the
    scheduler's screener job is still in-flight, which causes yfinance
    rate-limiting and makes both runs take 10x longer.
    """
    import psutil
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            cmd_str = " ".join(cmdline)
            if "nx_screener_production" in cmd_str or "nx_screener_longs" in cmd_str:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


def _run(
    script: str,
    label: str,
    wait: bool = True,
    timeout: int = 300,
    extra_args: list | None = None,
) -> bool:
    """Run a script in the scripts directory.

    Args:
        script:     filename relative to SCRIPTS_DIR (no CLI flags — use extra_args)
        label:      human-readable name for logging
        wait:       if True (default) block until the subprocess exits.
        timeout:    max seconds to wait when wait=True (ignored when wait=False)
        extra_args: additional CLI arguments passed after the script path

    Returns True on success (always True when wait=False).
    """
    path = SCRIPTS_DIR / script
    if not path.exists():
        log.error(f"Script not found: {path}")
        return False
    cmd = [sys.executable, str(path)] + (extra_args or [])
    log.info(f"Launching: {script}{' ' + ' '.join(extra_args) if extra_args else ''}"
             f"{'' if wait else ' (background)'}")

    if not wait:
        subprocess.Popen(
            cmd,
            cwd=str(SCRIPTS_DIR),
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log.info(f"{label} launched in background")
        return True

    try:
        result = subprocess.run(
            cmd,
            cwd=str(SCRIPTS_DIR),
            capture_output=False,
            timeout=timeout,
        )
        success = result.returncode == 0
        log.info(f"{label} finished — returncode={result.returncode}")
        return success
    except subprocess.TimeoutExpired:
        log.error(f"{label} timed out after {timeout}s")
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    _mode = os.getenv("TRADING_MODE", "paper")
    if _mode == "live":
        log.warning("🔴 LIVE TRADING MODE — real money at risk")
    log.info("Cash Monitor [%s]", _mode.upper())

    # SAFETY: Respect the kill switch before spawning any subprocesses
    try:
        sys.path.insert(0, str(SCRIPTS_DIR))
        from kill_switch_guard import kill_switch_active
        if kill_switch_active():
            log.warning("Kill switch is ACTIVE — cash monitor will not trigger any actions.")
            return
    except ImportError:
        log.warning("kill_switch_guard not importable — assuming active (fail-closed)")
        return

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
            "AvailableFunds", "BuyingPower", "ExcessLiquidity",
            "MaintMarginReq",
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
        # Screener runs in background (fire-and-forget) — it takes 20-40 min.
        # Guard: if a screener is already running (spawned by the scheduler),
        # skip launching a second instance to avoid yfinance rate-limiting.
        if _screener_is_running():
            log.info("Screener already running — skipping duplicate launch")
        else:
            _run("nx_screener_production.py", "Production screener", wait=False)
        _run("auto_options_executor.py", "Options executor", wait=True, timeout=120)
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
        # Guard: skip screener if already running (see premium branch comment).
        if _screener_is_running():
            log.info("Screener already running — skipping duplicate launch")
        else:
            _run("nx_screener_longs.py",      "Longs screener",      wait=False)
            _run("nx_screener_production.py", "Production screener", wait=False)
        _run("execute_longs.py",          "Longs executor",      wait=True, timeout=300)
        _run("execute_dual_mode.py",      "Dual-mode executor",  wait=True, timeout=300)
    else:
        if not lev_trigger and leverage_used >= _leverage_floor():
            log.info(f"Leverage trigger: NO (leverage {leverage_used:.2f}x ≥ floor {_leverage_floor():.2f}x)")

    # ── Condition 3: Overleveraged → trim positions ─────────────────────────
    DELEVER_TRIGGER_PCT = 3.00
    delever_trigger = (
        leverage_used > DELEVER_TRIGGER_PCT
        and not _on_cooldown("delever")
    )
    if delever_trigger:
        excess_notional = gpv - (nlv * _leverage_target())
        _notify(
            f"⚠️ Over-Leveraged: {leverage_used:.2f}x vs {_leverage_target():.1f}x target "
            f"(trigger at {DELEVER_TRIGGER_PCT:.1f}x).\n"
            f"~${excess_notional:,.0f} excess notional. Running portfolio restructure (Phase 3)..."
        )
        _mark_triggered("delever")
        _run("trim_oversized_positions.py", "Trim oversized")
        # Pass CLI flags as separate list items — _run() builds the path from the
        # first token only, so "--phase auto --live" must NOT be part of the filename.
        _run("portfolio_restructure.py", "Portfolio restructure",
             extra_args=["--phase", "auto", "--live"])
    elif leverage_used > _leverage_target():
        log.info(
            f"Delever watch: leverage {leverage_used:.2f}x above target "
            f"{_leverage_target():.1f}x but below trigger {DELEVER_TRIGGER_PCT:.1f}x"
        )

    # ── Condition 4: PM margin cushion thin → emergency delever ─────────────
    excess_liq = vals.get("ExcessLiquidity", vals.get("AvailableFunds", 0))
    el_ratio = excess_liq / nlv if nlv > 0 else 1.0

    if el_ratio < 0.05 and not _on_cooldown("margin_emergency"):
        _notify(
            f"🚨 PM MARGIN CRITICAL: ExcessLiquidity ${excess_liq:,.0f} "
            f"({el_ratio:.1%} of NLV) — emergency deleveraging!"
        )
        _mark_triggered("margin_emergency")
        _run("trim_oversized_positions.py", "Emergency trim")
    elif el_ratio < 0.10:
        _notify(
            f"⚠️ PM margin cushion thin: ExcessLiquidity ${excess_liq:,.0f} "
            f"({el_ratio:.1%} of NLV). Monitor closely."
        )
    elif el_ratio < 0.20:
        log.info(
            f"PM margin watch: ExcessLiquidity ${excess_liq:,.0f} ({el_ratio:.1%} of NLV)"
        )

    # ── Summary ───────────────────────────────────────────────────────────────
    log.info(
        f"Done. cash_trigger={cash_trigger}  lev_trigger={lev_trigger}  "
        f"delever_trigger={delever_trigger}  leverage={leverage_used:.2f}x  "
        f"cash={cash_pct:.1%}  EL_ratio={el_ratio:.1%}"
    )


if __name__ == "__main__":
    main()
