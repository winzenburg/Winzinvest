#!/usr/bin/env python3
"""
VIX Monitoring Daemon
Fetches VIX every 30 minutes during market hours
Updates circuit breaker status continuously
"""

import json
import logging
import os
import time
import signal
import sys
from datetime import datetime
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import modules
try:
    from vix_monitor import get_vix_monitor, VIXMonitor
    from circuit_breaker import get_circuit_breaker
    MODULES_AVAILABLE = True
except ImportError as e:
    logger.error(f"❌ Failed to import required modules: {e}")
    MODULES_AVAILABLE = False
    sys.exit(1)

# Configuration
MARKET_HOURS_START = 9  # 9 AM ET
MARKET_HOURS_END = 16   # 4 PM ET
FETCH_INTERVAL = 1800   # 30 minutes (1800 seconds)
MONITORING_LOG = os.path.expanduser('~/.openclaw/workspace/trading/logs/vix_daemon.log')

# Telegram integration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Global state
_running = True
_monitor = None
_breaker = None


def send_telegram_alert(message: str):
    """Send alert to Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    
    try:
        import requests
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown',
        }
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            logger.info("✅ Alert sent to Telegram")
        else:
            logger.warning(f"⚠️  Telegram error: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Error sending Telegram alert: {e}")


def check_vix():
    """Fetch and check VIX, update circuit breaker"""
    global _monitor, _breaker
    
    try:
        if _monitor is None:
            _monitor = get_vix_monitor()
        if _breaker is None:
            _breaker = get_circuit_breaker(_monitor)
        
        # Update VIX
        vix_update = _monitor.update()
        
        if vix_update is None:
            logger.warning("⚠️  Failed to update VIX")
            return
        
        # Log update
        logger.info(f"📊 VIX Update: {vix_update['vix']} (Regime: {vix_update['regime']}, Trend: {vix_update['trend']})")
        
        # Send alerts if regime changed
        if vix_update.get('alert_messages'):
            for alert in vix_update['alert_messages']:
                logger.warning(alert)
                send_telegram_alert(alert)
        
        # Check circuit breaker status
        cb_status = _breaker.check_circuit_breaker()
        
        # Log circuit breaker status
        logger.info(
            f"🛡️  Circuit Breaker: "
            f"Can enter: {cb_status['can_enter']}, "
            f"Close weak: {cb_status['should_close_weak']}, "
            f"Liquidate: {cb_status['should_liquidate']}, "
            f"Size mult: {cb_status['position_size_mult']:.0%}"
        )
        
        # Alert if circuit breaker triggered
        if cb_status['should_liquidate']:
            alert = f"⚠️  EMERGENCY LIQUIDATION: VIX={cb_status['vix']} (>25)"
            logger.critical(alert)
            send_telegram_alert(alert)
        elif cb_status['should_close_weak']:
            alert = f"⚠️  CLOSE WEAK POSITIONS: Regime {cb_status['regime']} (VIX={cb_status['vix']})"
            logger.warning(alert)
            send_telegram_alert(alert)
        
    except Exception as e:
        logger.error(f"❌ Error in check_vix: {e}")


def is_market_hours() -> bool:
    """Check if current time is within market hours (9:30 AM - 4:00 PM ET)"""
    try:
        from datetime import datetime
        import pytz
        
        et = pytz.timezone('US/Eastern')
        now = datetime.now(et)
        
        # Check if weekday (0=Monday, 4=Friday)
        if now.weekday() >= 5:  # Weekend
            return False
        
        # Check if within market hours
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        
        return market_open <= now <= market_close
    except Exception as e:
        logger.error(f"❌ Error checking market hours: {e}")
        return False


def monitor_loop():
    """Main monitoring loop"""
    global _running
    
    logger.info("🦞 VIX Monitoring Daemon started")
    logger.info(f"Fetch interval: {FETCH_INTERVAL} seconds ({FETCH_INTERVAL//60} minutes)")
    
    while _running:
        try:
            if is_market_hours():
                check_vix()
            else:
                logger.debug("⏸️  Outside market hours, skipping VIX fetch")
            
            # Sleep for interval
            for _ in range(FETCH_INTERVAL):
                if not _running:
                    break
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            _running = False
        except Exception as e:
            logger.error(f"❌ Error in monitoring loop: {e}")
            time.sleep(10)  # Retry after error


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global _running
    logger.info("📍 Received shutdown signal")
    _running = False


def main():
    """Main entry point"""
    global _running
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create logs directory
    os.makedirs(os.path.dirname(MONITORING_LOG), exist_ok=True)
    
    # Add file handler for logging
    fh = logging.FileHandler(MONITORING_LOG)
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logging.getLogger().addHandler(fh)
    
    # Start monitoring
    try:
        monitor_loop()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
    
    logger.info("✅ VIX Monitoring Daemon stopped")


if __name__ == '__main__':
    main()
