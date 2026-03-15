#!/usr/bin/env python3
"""
Send Telegram and Email alerts for regime changes.
Called by cron or manually when regime shift detected.

Requirements:
  - TELEGRAM_BOT_TOKEN: Bot token for Telegram alerts
  - TELEGRAM_CHAT_ID: Chat ID for Telegram alerts
  - RESEND_API_KEY: For email delivery (optional)
  - FROM_EMAIL: Sender email (optional)
  - TO_EMAIL: Recipient email (optional)

Environment:
  Loads from: trading/.env
  Fallback: system environment variables
"""

import os
import sys
import json
import logging
import urllib.parse
import urllib.request
from pathlib import Path

# Add scripts directory to path for email_helper import
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Import email helper
try:
    from email_helper import load_email_config, send_email
except ImportError:
    logger.warning("email_helper.py not found, email delivery will be disabled")

# Load environment - workspace first, then trading
workspace_dir = os.getenv('WORKSPACE_DIR', str(Path(__file__).resolve().parent.parent.parent))
env_files = [
    Path(workspace_dir) / '.env',
    Path(workspace_dir) / 'trading' / '.env'
]

for env_file in env_files:
    if env_file.exists():
        logger.info(f"[LOAD] Loading environment from {env_file}")
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                # Don't override existing env vars
                if key not in os.environ:
                    os.environ[key] = value

TG_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TG_CHAT = os.getenv('TELEGRAM_CHAT_ID')

def send_telegram(text):
    """Send message to Telegram."""
    if not (TG_TOKEN and TG_CHAT):
        logger.warning("Telegram not configured (missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID)")
        return False
    
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        'chat_id': TG_CHAT,
        'text': text,
        'parse_mode': 'HTML'
    }).encode()
    
    try:
        logger.info("[TG] Sending Telegram alert...")
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get('ok', False):
                logger.info("[TG] ✓ Telegram alert sent")
                return True
            else:
                logger.error(f"[TG] ✗ Telegram error: {result.get('description', 'Unknown')}")
                return False
    except Exception as e:
        logger.error(f"[TG] ✗ Error sending Telegram: {e}")
        return False


def send_regime_email(regime_data):
    """Send regime alert via email."""
    try:
        from email_helper import load_email_config, send_email
    except ImportError:
        logger.debug("[EMAIL] email_helper not available, skipping email")
        return False
    
    config = load_email_config()
    if not config or not config.get('resend_api_key'):
        logger.debug("[EMAIL] Email not configured, skipping")
        return False
    
    regime = regime_data.get('regime', 'UNKNOWN')
    prev_regime = regime_data.get('previousRegime', 'UNKNOWN')
    emoji = regime_data.get('emoji', '📊')
    
    subject = f"🚨 REGIME ALERT: {prev_regime} → {emoji} {regime}"
    
    # Format as HTML email
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #e74c3c;">📊 REGIME ALERT</h2>
        
        <div style="background: #f5f5f5; padding: 15px; border-radius: 6px; margin: 20px 0;">
          <p style="margin: 5px 0;">
            <strong>Regime Shift:</strong> {prev_regime} → {emoji} <strong>{regime}</strong>
          </p>
          <p style="margin: 5px 0;">
            <strong>Score:</strong> {regime_data.get('score', 0)}/10
          </p>
        </div>
        
        <h3>Active Alerts</h3>
        <ul>
    """
    
    # Add active alerts
    for alert in regime_data.get('activeAlerts', [])[:5]:
        priority = alert.get('priority', '?')
        name = alert.get('name', 'Unknown')
        value = alert.get('value', '')
        weight = alert.get('weight', 0)
        html_body += f"  <li>#{priority} {name}: {value} (+{weight})</li>\n"
    
    html_body += """
        </ul>
        
        <h3>AMS Adjustments</h3>
        <ul>
    """
    
    # Add AMS parameters
    params = regime_data.get('parameters', {})
    html_body += f"  <li>Z-score threshold: {params.get('zEnter', 'N/A')}</li>\n"
    html_body += f"  <li>Position size: {params.get('sizeMultiplier', 0)*100:.0f}%</li>\n"
    html_body += f"  <li>ATR multiplier: {params.get('atrMultiplier', 1.0):.1f}x</li>\n"
    html_body += f"  <li>Cooldown: {params.get('cooldown', 'N/A')} bars</li>\n"
    
    html_body += """
        </ul>
        
        <hr style="margin: 30px 0;">
        <p style="color: #999; font-size: 12px;">
          Regime alert from OpenClaw Trading System
        </p>
      </body>
    </html>
    """
    
    success = send_email(subject, html_body, config=config)
    return success


def format_regime_alert(regime_data):
    """Format regime data as Telegram message."""
    
    emoji = regime_data.get('emoji', '')
    regime = regime_data.get('regime', 'UNKNOWN')
    score = regime_data.get('score', 0)
    prev_regime = regime_data.get('previousRegime', 'UNKNOWN')
    
    msg = f"🚨 <b>REGIME ALERT</b>\n"
    msg += f"{prev_regime} → {emoji} <b>{regime}</b>\n"
    msg += f"Score: {score}/10\n\n"
    
    # Active alerts
    active = regime_data.get('activeAlerts', [])
    if active:
        msg += "<b>Active Alerts:</b>\n"
        for alert in active[:3]:  # Top 3
            priority = alert.get('priority', '?')
            name = alert.get('name', 'Unknown')
            value = alert.get('value', '')
            weight = alert.get('weight', 0)
            msg += f"#{priority} {name}: {value} (+{weight})\n"
        msg += "\n"
    
    # AMS parameters
    params = regime_data.get('parameters', {})
    msg += "<b>AMS Adjustments:</b>\n"
    msg += f"• Z-score threshold: {params.get('zEnter', 'N/A')}\n"
    msg += f"• Position size: {params.get('sizeMultiplier', 0)*100:.0f}%\n"
    msg += f"• ATR multiplier: {params.get('atrMultiplier', 1.0):.1f}x\n"
    msg += f"• Cooldown: {params.get('cooldown', 'N/A')} bars\n"
    
    return msg


def main():
    """Send regime alert based on current state."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Send regime alerts via Telegram and Email")
    parser.add_argument('--force', action='store_true', help="Send alert even if no change")
    args = parser.parse_args()
    
    logger.info("[MAIN] Starting regime alert system...")
    
    # Load regime state
    state_file = Path(__file__).parent.parent / 'logs' / 'regime_state.json'
    if not state_file.exists():
        logger.error(f"No regime state found at {state_file}")
        sys.exit(1)
    
    try:
        with open(state_file) as f:
            regime_data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load regime state: {e}")
        sys.exit(1)
    
    # Check if regime changed
    current = regime_data.get('regime')
    previous = regime_data.get('previousRegime')
    
    if not args.force and current == previous:
        logger.info(f"[MAIN] No regime change (current: {current})")
        sys.exit(0)
    
    logger.info(f"[MAIN] Regime changed: {previous} → {current}")
    
    # Format and send alerts
    telegram_message = format_regime_alert(regime_data)
    
    # Send via Telegram
    telegram_success = send_telegram(telegram_message)
    
    # Send via Email
    email_success = send_regime_email(regime_data)
    
    # Report results
    if telegram_success or email_success:
        if telegram_success and email_success:
            logger.info("[MAIN] ✓ Alert sent via Telegram and Email")
            sys.exit(0)
        elif telegram_success:
            logger.warning("[MAIN] ⚠️ Alert sent via Telegram only (Email failed)")
            sys.exit(0)
        else:
            logger.warning("[MAIN] ⚠️ Alert sent via Email only (Telegram failed)")
            sys.exit(0)
    else:
        logger.error("[MAIN] ✗ Failed to send alert via any channel")
        sys.exit(1)


if __name__ == "__main__":
    main()
