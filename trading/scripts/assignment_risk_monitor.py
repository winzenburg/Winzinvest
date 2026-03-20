#!/usr/bin/env python3
"""
Assignment Risk Monitor
=======================
Watches all short option positions for ITM drift and sends graduated
Telegram alerts so you can roll or close before forced assignment.

Alert levels:
  APPROACHING  — option is within 2% of being ITM (early warning)
  ITM          — option has crossed ITM (action recommended)
  DEEP_ITM     — option is > 3% ITM (urgent — high assignment risk)
  DIVIDEND     — ex-div date within DTE and option is near/ITM (early assignment likely)

Runs every 30 minutes via the scheduler alongside options_position_manager.
Tracks sent alerts in assignment_alerts_today.json to avoid spamming.

Usage:
  python3 assignment_risk_monitor.py               # live check
  python3 assignment_risk_monitor.py --dry-run      # scan + report, no alerts
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from atomic_io import atomic_write_json

SCRIPTS_DIR = Path(__file__).resolve().parent
TRADING_DIR = SCRIPTS_DIR.parent
LOGS_DIR = TRADING_DIR / "logs"
ENV_PATH = TRADING_DIR / ".env"
ALERT_STATE_PATH = LOGS_DIR / "assignment_alerts_today.json"

LOGS_DIR.mkdir(exist_ok=True)
sys.path.insert(0, str(SCRIPTS_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [assign_risk] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGS_DIR / "assignment_risk_monitor.log"),
    ],
)
log = logging.getLogger("assign_risk")

if ENV_PATH.exists():
    for line in ENV_PATH.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "4001"))
# clientId=198 (not 197). clientId=197 was previously used by a GTC combo
# roll placer; those orders persist in IB Gateway and get re-associated to
# any session connecting as 197. Using 198 keeps this read-only monitor clean.
IB_CLIENT_ID = 198

APPROACHING_THRESHOLD_PCT = 2.0
DEEP_ITM_THRESHOLD_PCT = 3.0


def _notify(msg: str, urgent: bool = False) -> None:
    """Send Telegram alert, respecting notification_prefs.json."""
    log.info(msg)
    try:
        from notifications import is_event_enabled, send_telegram
        if not is_event_enabled("assignment_risk"):
            return
        send_telegram(msg, urgent=urgent)
    except ImportError:
        # Fallback if notifications module unavailable
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat = os.getenv("TELEGRAM_CHAT_ID", "")
        if token and chat:
            try:
                import urllib.request, urllib.parse
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                data = urllib.parse.urlencode({
                    "chat_id": chat,
                    "text": msg,
                    "parse_mode": "HTML",
                    "disable_notification": str(not urgent).lower(),
                }).encode()
                urllib.request.urlopen(url, data=data, timeout=5)
            except Exception:
                pass


def _load_alert_state() -> Dict[str, Any]:
    """Load today's alert state to avoid duplicate alerts."""
    try:
        if ALERT_STATE_PATH.exists():
            data = json.loads(ALERT_STATE_PATH.read_text())
            if data.get("date") == date.today().isoformat():
                return data
    except Exception:
        pass
    return {"date": date.today().isoformat(), "alerted": {}}


def _save_alert_state(state: Dict[str, Any]) -> None:
    try:
        atomic_write_json(ALERT_STATE_PATH, state)
    except Exception as e:
        log.warning("Could not save alert state: %s", e)


def _already_alerted(state: Dict[str, Any], key: str, level: str) -> bool:
    """Check if we already sent an alert at this level or higher for this key today."""
    prev = state.get("alerted", {}).get(key)
    if prev is None:
        return False
    level_order = {"APPROACHING": 0, "ITM": 1, "DEEP_ITM": 2, "DIVIDEND": 2}
    return level_order.get(prev, -1) >= level_order.get(level, 0)


def _mark_alerted(state: Dict[str, Any], key: str, level: str) -> None:
    state.setdefault("alerted", {})[key] = level


def _fetch_prices(symbols: list[str]) -> Dict[str, float]:
    """Fetch current spot prices via yfinance."""
    import yfinance as yf
    prices: Dict[str, float] = {}
    if not symbols:
        return prices
    for sym in symbols:
        try:
            h = yf.download(sym, period="2d", progress=False, auto_adjust=True)
            if h.empty:
                continue
            cl = h["Close"]
            if hasattr(cl, "columns"):
                cl = cl.iloc[:, 0]
            prices[sym] = round(float(cl.iloc[-1]), 2)
        except Exception:
            pass
    return prices


def _check_dividend_risk(symbol: str, expiry_str: str) -> Optional[Dict[str, Any]]:
    """Check if an upcoming dividend creates early assignment risk."""
    try:
        from dividend_calendar import get_ex_dividend_info
        info = get_ex_dividend_info(symbol)
        ex_date_str = info.get("ex_date")
        div_amount = info.get("dividend_amount", 0)
        if not ex_date_str or div_amount <= 0:
            return None

        ex_date = date.fromisoformat(ex_date_str)
        expiry_date = datetime.strptime(expiry_str[:8], "%Y%m%d").date()
        today = date.today()

        if today <= ex_date <= expiry_date:
            days_to_ex = (ex_date - today).days
            return {
                "ex_date": ex_date_str,
                "days_to_ex": days_to_ex,
                "dividend_amount": div_amount,
            }
    except ImportError:
        pass
    except Exception:
        pass
    return None


def scan_assignment_risk(dry_run: bool = False) -> List[Dict[str, Any]]:
    """Connect to IB, scan short options, and alert on ITM risk."""
    from ib_insync import IB

    ib = IB()
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=10)
        log.info("Connected to IB")
    except Exception as e:
        log.error("IB connect failed: %s", e)
        return []

    alerts_sent: List[Dict[str, Any]] = []
    state = _load_alert_state()

    try:
        short_options = []
        for pos in ib.positions():
            c = pos.contract
            if c.secType != "OPT" or int(pos.position) >= 0:
                continue
            short_options.append({
                "symbol": c.symbol,
                "strike": c.strike,
                "right": c.right,
                "expiry": c.lastTradeDateOrContractMonth,
                "qty": int(pos.position),
                "avg_cost": float(pos.avgCost),
            })

        if not short_options:
            log.info("No short option positions to monitor.")
            return []

        log.info("Monitoring %d short option positions", len(short_options))

        symbols = list({p["symbol"] for p in short_options})
        prices = _fetch_prices(symbols)

        for pos in short_options:
            spot = prices.get(pos["symbol"])
            if spot is None or spot <= 0:
                continue

            strike = pos["strike"]
            right = pos["right"]
            expiry = pos["expiry"]
            today = date.today()
            exp_date = datetime.strptime(expiry, "%Y%m%d").date()
            dte = (exp_date - today).days

            if right == "C":
                otm_pct = (strike - spot) / spot * 100
            else:
                otm_pct = (spot - strike) / spot * 100

            is_itm = otm_pct < 0
            label = f"{pos['symbol']} {right}{strike} exp {expiry}"
            alert_key = f"{pos['symbol']}_{right}_{strike}_{expiry}"

            level = None
            msg = None
            urgent = False

            if otm_pct < -DEEP_ITM_THRESHOLD_PCT:
                level = "DEEP_ITM"
                urgent = True
                msg = (
                    f"🚨 <b>DEEP ITM — ASSIGNMENT RISK</b>\n"
                    f"<b>{label}</b>\n"
                    f"Spot: ${spot:.2f} | Strike: ${strike:.2f}\n"
                    f"ITM by {abs(otm_pct):.1f}% | DTE: {dte}\n"
                    f"Contracts: {abs(pos['qty'])}\n\n"
                    f"⚡ Roll or close ASAP to avoid assignment"
                )
            elif is_itm:
                level = "ITM"
                urgent = True
                msg = (
                    f"⚠️ <b>ITM ALERT</b>\n"
                    f"<b>{label}</b>\n"
                    f"Spot: ${spot:.2f} | Strike: ${strike:.2f}\n"
                    f"ITM by {abs(otm_pct):.1f}% | DTE: {dte}\n"
                    f"Contracts: {abs(pos['qty'])}\n\n"
                    f"Consider rolling up/out before assignment"
                )
            elif otm_pct < APPROACHING_THRESHOLD_PCT:
                level = "APPROACHING"
                msg = (
                    f"📋 <b>Approaching ITM</b>\n"
                    f"<b>{label}</b>\n"
                    f"Spot: ${spot:.2f} | Strike: ${strike:.2f}\n"
                    f"Only {otm_pct:.1f}% OTM | DTE: {dte}\n"
                    f"Contracts: {abs(pos['qty'])}\n\n"
                    f"Monitor closely — may need to roll"
                )

            div_risk = None
            if right == "C" and is_itm:
                div_risk = _check_dividend_risk(pos["symbol"], expiry)
                if div_risk and not _already_alerted(state, alert_key, "DIVIDEND"):
                    div_msg = (
                        f"💰 <b>DIVIDEND + ITM — EARLY ASSIGNMENT LIKELY</b>\n"
                        f"<b>{label}</b>\n"
                        f"Ex-div: {div_risk['ex_date']} ({div_risk['days_to_ex']}d away)\n"
                        f"Dividend: ${div_risk['dividend_amount']:.2f}/sh\n"
                        f"Spot: ${spot:.2f} | Strike: ${strike:.2f} (ITM {abs(otm_pct):.1f}%)\n\n"
                        f"⚡ Holders will likely exercise to capture dividend"
                    )
                    if not dry_run:
                        _notify(div_msg, urgent=True)
                    _mark_alerted(state, alert_key, "DIVIDEND")
                    alerts_sent.append({
                        "symbol": pos["symbol"], "level": "DIVIDEND",
                        "label": label, "otm_pct": round(otm_pct, 2),
                    })

            if level and msg and not _already_alerted(state, alert_key, level):
                log.info("[%s] %s — %.1f%% OTM (DTE %d)", level, label, otm_pct, dte)
                if not dry_run:
                    _notify(msg, urgent=urgent)
                _mark_alerted(state, alert_key, level)
                alerts_sent.append({
                    "symbol": pos["symbol"], "level": level,
                    "label": label, "otm_pct": round(otm_pct, 2),
                    "dte": dte,
                })

        all_hold = [
            p for p in short_options
            if prices.get(p["symbol"])
            and (
                (p["right"] == "C" and (p["strike"] - prices[p["symbol"]]) / prices[p["symbol"]] * 100 >= APPROACHING_THRESHOLD_PCT)
                or (p["right"] == "P" and (prices[p["symbol"]] - p["strike"]) / prices[p["symbol"]] * 100 >= APPROACHING_THRESHOLD_PCT)
            )
        ]

        log.info("\nSummary: %d alerts, %d positions safe, %d total short options",
                 len(alerts_sent), len(all_hold), len(short_options))

    finally:
        try:
            _save_alert_state(state)
        except Exception as exc:
            log.warning("Could not persist alert state: %s", exc)
        try:
            ib.disconnect()
        except Exception:
            pass
        log.info("Disconnected from IB")

    return alerts_sent


def main() -> None:
    parser = argparse.ArgumentParser(description="Assignment Risk Monitor")
    parser.add_argument("--dry-run", action="store_true", help="Scan only, no alerts")
    args = parser.parse_args()

    log.info("Assignment Risk Monitor [%s]", "DRY RUN" if args.dry_run else "LIVE")
    scan_assignment_risk(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
