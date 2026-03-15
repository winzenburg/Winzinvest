#!/usr/bin/env python3
"""
Live Pre-Flight Validation
===========================
Run before starting the scheduler in live mode.
Validates every critical condition is met before real money is at risk.

Usage:
    python3 live_preflight.py          # all checks must pass
    python3 live_preflight.py --skip-ib  # skip IB connectivity (for CI)

Exit code 0 = all clear.  Non-zero = DO NOT start live trading.
"""

import json
import os
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
TRADING_DIR = SCRIPTS_DIR.parent
ENV_PATH = TRADING_DIR / ".env"

sys.path.insert(0, str(SCRIPTS_DIR))

if ENV_PATH.exists():
    for _line in ENV_PATH.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())


class PreflightResult:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[str] = []

    def ok(self, msg: str) -> None:
        self.passed.append(msg)
        print(f"  ✅  {msg}")

    def fail(self, msg: str) -> None:
        self.failed.append(msg)
        print(f"  ❌  {msg}")

    @property
    def all_passed(self) -> bool:
        return len(self.failed) == 0


def check_env(r: PreflightResult) -> None:
    mode = os.getenv("TRADING_MODE", "paper")
    if mode == "live":
        r.ok(f"TRADING_MODE = {mode}")
    else:
        r.fail(f"TRADING_MODE = {mode!r} (expected 'live')")

    port = os.getenv("IB_PORT", "4001")
    if port == "4001":
        r.ok(f"IB_PORT = {port}")
    else:
        r.fail(f"IB_PORT = {port!r} (expected '4001' for live)")

    alloc = os.getenv("LIVE_ALLOCATION_PCT", "")
    if alloc:
        try:
            pct = float(alloc)
            if 0 < pct <= 1.0:
                r.ok(f"LIVE_ALLOCATION_PCT = {pct} ({pct*100:.0f}%)")
            else:
                r.fail(f"LIVE_ALLOCATION_PCT = {pct} (out of range 0-1)")
        except ValueError:
            r.fail(f"LIVE_ALLOCATION_PCT = {alloc!r} (not a number)")
    else:
        r.fail("LIVE_ALLOCATION_PCT is not set")

    api_key = os.getenv("DASHBOARD_API_KEY", "")
    if api_key and len(api_key) >= 16:
        r.ok("DASHBOARD_API_KEY is set")
    else:
        r.fail("DASHBOARD_API_KEY is missing or too short")

    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    tg_chat = os.getenv("TELEGRAM_CHAT_ID", "")
    if tg_token and tg_chat:
        r.ok("Telegram credentials configured")
    else:
        r.fail("Telegram credentials missing (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)")


def check_risk_files(r: PreflightResult) -> None:
    risk_path = TRADING_DIR / "risk.json"
    if risk_path.exists():
        r.ok("risk.json exists")
    else:
        r.fail("risk.json not found")

    live_risk_path = TRADING_DIR / "risk.live.json"
    if live_risk_path.exists():
        try:
            data = json.loads(live_risk_path.read_text())
            portfolio = data.get("portfolio", {})
            loss_pct = portfolio.get("daily_loss_limit_pct", 0)
            dd_pct = portfolio.get("max_drawdown_pct", 0)
            if loss_pct <= 0.02 and dd_pct <= 0.06:
                r.ok(f"risk.live.json: loss={loss_pct:.1%}, drawdown={dd_pct:.1%}")
            else:
                r.fail(f"risk.live.json limits too loose: loss={loss_pct:.1%}, drawdown={dd_pct:.1%}")
        except (OSError, ValueError, KeyError) as e:
            r.fail(f"risk.live.json parse error: {e}")
    else:
        r.fail("risk.live.json not found")


def check_kill_switch(r: PreflightResult) -> None:
    ks_path = TRADING_DIR / "kill_switch.json"
    if not ks_path.exists():
        r.ok("Kill switch file absent (clear)")
        return
    try:
        data = json.loads(ks_path.read_text())
        if data.get("active"):
            r.fail("Kill switch is ACTIVE — clear it before going live")
        else:
            r.ok("Kill switch exists but is inactive (clear)")
    except (OSError, ValueError):
        r.fail("Kill switch file exists but is unreadable")


def check_ib_connectivity(r: PreflightResult) -> None:
    host = os.getenv("IB_HOST", "127.0.0.1")
    port = int(os.getenv("IB_PORT", "4001"))
    try:
        from ib_insync import IB
        ib = IB()
        ib.connect(host, port, clientId=200, timeout=10)
        nlv = 0.0
        for item in ib.accountSummary():
            if item.tag == "NetLiquidation" and item.currency == "USD":
                nlv = float(item.value)
                break
        ib.disconnect()
        if nlv > 0:
            r.ok(f"IB Gateway reachable at {host}:{port} — NLV ${nlv:,.0f}")
        else:
            r.fail(f"Connected to IB at {host}:{port} but NLV returned 0")
    except Exception as e:
        r.fail(f"IB Gateway connection failed ({host}:{port}): {e}")


def send_preflight_telegram(r: PreflightResult) -> None:
    try:
        from notifications import send_telegram
    except ImportError:
        print("  ⚠️  Could not import notifications.send_telegram")
        return

    if r.all_passed:
        msg = (
            "🟢 <b>LIVE PRE-FLIGHT PASSED</b>\n\n"
            f"All {len(r.passed)} checks passed.\n"
            f"Allocation: {os.getenv('LIVE_ALLOCATION_PCT', '?')} "
            f"({float(os.getenv('LIVE_ALLOCATION_PCT', '0')) * 100:.0f}%)\n"
            f"Port: {os.getenv('IB_PORT', '?')}\n\n"
            "Scheduler is cleared for live trading."
        )
    else:
        failures = "\n".join(f"• {f}" for f in r.failed)
        msg = (
            "🔴 <b>LIVE PRE-FLIGHT FAILED</b>\n\n"
            f"{len(r.failed)} check(s) failed:\n{failures}\n\n"
            "DO NOT start the scheduler until all issues are resolved."
        )
    send_telegram(msg)


def main() -> None:
    skip_ib = "--skip-ib" in sys.argv

    print("\n╔══════════════════════════════════════════╗")
    print("║       LIVE PRE-FLIGHT VALIDATION         ║")
    print("╚══════════════════════════════════════════╝\n")

    r = PreflightResult()

    print("[1/4] Environment variables")
    check_env(r)

    print("\n[2/4] Risk configuration")
    check_risk_files(r)

    print("\n[3/4] Kill switch")
    check_kill_switch(r)

    if skip_ib:
        print("\n[4/4] IB Connectivity — SKIPPED (--skip-ib)")
    else:
        print("\n[4/4] IB Connectivity")
        check_ib_connectivity(r)

    print("\n" + "─" * 44)
    if r.all_passed:
        print("  🟢  ALL CHECKS PASSED — cleared for live trading")
    else:
        print(f"  🔴  {len(r.failed)} CHECK(S) FAILED — do NOT start scheduler")
        for f in r.failed:
            print(f"       • {f}")

    print("─" * 44 + "\n")

    send_preflight_telegram(r)

    sys.exit(0 if r.all_passed else 1)


if __name__ == "__main__":
    main()
