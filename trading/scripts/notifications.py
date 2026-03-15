"""
Shared notification dispatcher for critical trading events.

Supports Telegram and email (SMTP). Falls back gracefully if credentials are missing.
Used by risk_monitor (kill switch), outcome resolver, and EOD reconciliation.
"""

import logging
import os
import smtplib
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Load .env eagerly so credentials are available regardless of import order
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

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


def send_telegram(text: str) -> bool:
    """Send a Telegram message. Returns True on success."""
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
    """Send an email alert via SMTP. Returns True on success."""
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
    tg_ok = send_telegram(full_text)
    email_ok = send_email(f"[TRADING ALERT] {subject}", body)
    if not tg_ok and not email_ok:
        logger.error("CRITICAL ALERT COULD NOT BE DELIVERED: %s — %s", subject, body)


def notify_info(text: str) -> None:
    """Send a non-critical informational alert (Telegram only)."""
    send_telegram(text)


def notify_executor_error(script_name: str, error: str, context: str = "") -> None:
    """Alert when an executor or scheduler job fails unexpectedly."""
    lines = [f"<b>EXECUTOR FAILURE: {script_name}</b>"]
    if context:
        lines.append(f"Context: {context}")
    lines.append(f"Error: <code>{error[:500]}</code>")
    send_telegram("\n".join(lines))
