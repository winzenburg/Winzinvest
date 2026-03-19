"""
Shared notification dispatcher for critical trading events.

Supports Telegram and email (SMTP). Falls back gracefully if credentials are missing.
Used by risk_monitor (kill switch), outcome resolver, and EOD reconciliation.

Notification preferences are read from trading/config/notification_prefs.json (written by
the dashboard UI). Each send call respects the channel toggles and event filters saved there.
"""

import json
import logging
import os
import smtplib
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Load .env eagerly so credentials are available regardless of import order
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

_PREFS_PATH = Path(__file__).resolve().parent.parent / "config" / "notification_prefs.json"

_DEFAULT_PREFS: dict[str, Any] = {
    "channels":   {"telegram": True, "email": False, "browser_push": False},
    "thresholds": {"daily_loss_pct": 1.0, "drawdown_pct": 5.0,
                   "margin_utilization_pct": 80, "data_staleness_minutes": 10},
    "events":     {"trade_executed": False, "kill_switch_activated": True,
                   "drawdown_circuit_breaker": True, "assignment_risk": True,
                   "screener_complete": False, "daily_summary": True},
}


def _load_prefs() -> dict[str, Any]:
    """Read notification_prefs.json. Re-read on every call so dashboard changes take effect immediately."""
    try:
        if _PREFS_PATH.exists():
            raw = json.loads(_PREFS_PATH.read_text())
            # Deep-merge with defaults so missing keys don't break callers
            merged: dict[str, Any] = {}
            for section in ("channels", "thresholds", "events"):
                merged[section] = {**_DEFAULT_PREFS[section], **raw.get(section, {})}
            return merged
    except Exception as exc:
        logger.debug("Could not load notification prefs (%s); using defaults", exc)
    return dict(_DEFAULT_PREFS)


def is_event_enabled(event_name: str) -> bool:
    """Return True if the named event type is enabled in notification_prefs.json."""
    prefs = _load_prefs()
    return bool(prefs.get("events", {}).get(event_name, True))


def get_threshold(name: str, default: float = 0.0) -> float:
    """Return a numeric threshold from notification_prefs.json (e.g. 'daily_loss_pct')."""
    prefs = _load_prefs()
    return float(prefs.get("thresholds", {}).get(name, default))


# Read lazily via functions so env changes after import still take effect

def _tg_token() -> Optional[str]:
    return os.getenv("TELEGRAM_BOT_TOKEN")


def _tg_chat() -> Optional[str]:
    return os.getenv("TELEGRAM_CHAT_ID")


# SMTP — kept as module-level since they rarely change at runtime
SMTP_HOST: Optional[str] = os.getenv("ALERT_SMTP_HOST")
SMTP_PORT: int = int(os.getenv("ALERT_SMTP_PORT", "587"))
SMTP_USER: Optional[str] = os.getenv("ALERT_SMTP_USER")
SMTP_PASS: Optional[str] = os.getenv("ALERT_SMTP_PASS")
ALERT_EMAIL: Optional[str] = os.getenv("ALERT_EMAIL")


def send_telegram(text: str, urgent: bool = False) -> bool:
    """Send a Telegram message. Returns True on success.

    Respects the ``channels.telegram`` toggle in notification_prefs.json.
    """
    prefs = _load_prefs()
    if not prefs.get("channels", {}).get("telegram", True):
        logger.debug("Telegram channel disabled in notification prefs — skipping send")
        return False
    token = _tg_token()
    chat = _tg_chat()
    if not (token and chat):
        logger.warning("Telegram not configured (missing TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID in env)")
        return False
    try:
        import urllib.request
        import urllib.parse
        import json as _json

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = urllib.parse.urlencode({
            "chat_id": chat,
            "text": text,
            "parse_mode": "HTML",
            "disable_notification": str(not urgent).lower(),
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = _json.loads(resp.read())
            if not result.get("ok"):
                logger.warning("Telegram API error: %s", result)
                return False
            return True
    except Exception as e:
        logger.warning("Telegram send failed: %s", e)
        return False


def send_email(subject: str, body: str) -> bool:
    """Send an email alert via SMTP. Returns True on success.

    Respects the ``channels.email`` toggle in notification_prefs.json.
    """
    prefs = _load_prefs()
    if not prefs.get("channels", {}).get("email", False):
        logger.debug("Email channel disabled in notification prefs — skipping send")
        return False
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and ALERT_EMAIL):
        logger.debug("Email not configured (missing ALERT_SMTP_* / ALERT_EMAIL)")
        return False
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = ALERT_EMAIL
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, [ALERT_EMAIL], msg.as_string())
        return True
    except Exception as e:
        logger.warning("Email send failed: %s", e)
        return False


def notify_critical(subject: str, body: str) -> None:
    """Send a critical alert via all configured channels.

    Used for kill switch activation, max drawdown breach, daily loss limit, etc.
    """
    full_text = f"<b>CRITICAL: {subject}</b>\n\n{body}"
    tg_ok = send_telegram(full_text, urgent=True)
    email_ok = send_email(f"[TRADING ALERT] {subject}", body)
    if not tg_ok and not email_ok:
        logger.error("CRITICAL ALERT COULD NOT BE DELIVERED: %s — %s", subject, body)


def notify_info(text: str) -> None:
    """Send a non-critical informational alert (Telegram only)."""
    send_telegram(text)


def notify_event(event_name: str, subject: str, body: str, *, urgent: bool = False) -> None:
    """Send an alert only if ``event_name`` is enabled in notification_prefs.json.

    Use this for events the user can toggle on/off (trade_executed, daily_summary, etc.).
    Critical safety alerts (kill switch, circuit breaker) should use notify_critical directly.
    """
    if not is_event_enabled(event_name):
        logger.debug("Event '%s' disabled in notification prefs — skipping alert", event_name)
        return
    full_text = f"<b>{subject}</b>\n\n{body}" if body else f"<b>{subject}</b>"
    send_telegram(full_text, urgent=urgent)
    send_email(f"[{event_name.upper()}] {subject}", body)


def notify_executor_error(script_name: str, error: str, context: str = "") -> None:
    """Alert when an executor or scheduler job fails unexpectedly."""
    lines = [f"<b>EXECUTOR FAILURE: {script_name}</b>"]
    if context:
        lines.append(f"Context: {context}")
    lines.append(f"Error: <code>{error[:500]}</code>")
    send_telegram("\n".join(lines), urgent=True)
