#!/usr/bin/env python3
"""
Daily Risk Monitor - Scheduler
Runs sector and correlation checks at scheduled times
- 8:00 AM: Sector concentration check
- 3:00 PM: Correlation matrix update
- Sends Telegram alerts on violations
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
import threading
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TRADING_DIR = Path(__file__).resolve().parents[0]
LOGS_DIR = TRADING_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

# Import monitoring modules
try:
    from sector_monitor import (
        generate_daily_report as generate_sector_report,
        save_daily_report,
        get_telegram_alert_message as get_sector_alert_msg
    )
    SECTOR_MONITOR_AVAILABLE = True
except ImportError:
    SECTOR_MONITOR_AVAILABLE = False
    logger.warning("sector_monitor not available")

try:
    from correlation_monitor import (
        generate_correlation_report,
        save_correlation_report,
        get_telegram_alert_message as get_corr_alert_msg
    )
    CORRELATION_MONITOR_AVAILABLE = True
except ImportError:
    CORRELATION_MONITOR_AVAILABLE = False
    logger.warning("correlation_monitor not available")

# Telegram integration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def send_telegram_alert(message, alert_type='info'):
    """Send alert to Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials not configured")
        return False
    
    try:
        import requests
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"Telegram alert sent ({alert_type})")
            return True
        else:
            logger.error(f"Telegram error: {response.status_code}")
            return False
    
    except Exception as e:
        logger.error(f"Error sending Telegram: {e}")
        return False

def run_sector_check():
    """Run 8 AM sector concentration check"""
    if not SECTOR_MONITOR_AVAILABLE:
        logger.warning("Sector monitor not available")
        return
    
    logger.info("=" * 60)
    logger.info("SECTOR CONCENTRATION CHECK (8:00 AM)")
    logger.info("=" * 60)
    
    try:
        report = generate_sector_report()
        save_daily_report(report)
        
        # Log results
        violations = report.get('violations', [])
        warnings = report.get('warnings', [])
        
        if violations:
            logger.warning(f"⚠️ {len(violations)} VIOLATIONS:")
            for v in violations:
                logger.warning(f"   {v['sector']}: {v['allocation']*100:.1f}% (limit 20%)")
        
        if warnings:
            logger.warning(f"⚠️ {len(warnings)} WARNINGS:")
            for w in warnings:
                logger.warning(f"   {w['sector']}: {w['allocation']*100:.1f}%")
        
        # Send alert if violations
        if violations:
            message = get_sector_alert_msg(report)
            if message:
                send_telegram_alert(message, 'violation')
    
    except Exception as e:
        logger.error(f"Error in sector check: {e}")

def run_correlation_check():
    """Run 3 PM correlation matrix update"""
    if not CORRELATION_MONITOR_AVAILABLE:
        logger.warning("Correlation monitor not available")
        return
    
    logger.info("=" * 60)
    logger.info("CORRELATION MATRIX UPDATE (3:00 PM)")
    logger.info("=" * 60)
    
    try:
        report = generate_correlation_report()
        save_correlation_report(report)
        
        # Log results
        pairs = report.get('correlated_pairs', [])
        alerts = report.get('alerts', [])
        
        if pairs:
            logger.warning(f"⚠️ {len(pairs)} CORRELATED PAIRS:")
            for p in pairs[:5]:
                logger.warning(f"   {p['ticker1']}-{p['ticker2']}: {p['correlation']:.2f}")
        
        # Send alert if issues
        if alerts:
            message = get_corr_alert_msg(report)
            if message:
                send_telegram_alert(message, 'alert')
    
    except Exception as e:
        logger.error(f"Error in correlation check: {e}")

class DailyRiskMonitor:
    """Manages scheduled risk monitoring"""
    
    def __init__(self):
        self.running = False
        self.threads = {}
    
    def should_run_at_8am(self):
        """Check if it's 8:00 AM"""
        now = datetime.now()
        return now.hour == 8 and now.minute == 0
    
    def should_run_at_3pm(self):
        """Check if it's 3:00 PM (15:00)"""
        now = datetime.now()
        return now.hour == 15 and now.minute == 0
    
    def monitor_loop(self):
        """Main monitoring loop"""
        logger.info("Daily Risk Monitor started")
        
        last_8am_run = None
        last_3pm_run = None
        
        while self.running:
            try:
                now = datetime.now().date()
                
                # Check for 8 AM run
                if self.should_run_at_8am():
                    if last_8am_run != now:
                        logger.info("🔔 Running 8 AM sector check...")
                        run_sector_check()
                        last_8am_run = now
                
                # Check for 3 PM run
                if self.should_run_at_3pm():
                    if last_3pm_run != now:
                        logger.info("🔔 Running 3 PM correlation check...")
                        run_correlation_check()
                        last_3pm_run = now
                
                # Sleep to avoid busy loop (check every 30 seconds)
                time.sleep(30)
            
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                time.sleep(60)
    
    def start(self, daemon=True):
        """Start monitoring in background thread"""
        if self.running:
            logger.warning("Monitor already running")
            return
        
        self.running = True
        
        thread = threading.Thread(target=self.monitor_loop, daemon=daemon)
        thread.start()
        self.threads['main'] = thread
        
        logger.info("Daily risk monitor started (background)")
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        logger.info("Daily risk monitor stopped")
    
    def manual_sector_check(self):
        """Run sector check manually (for testing)"""
        logger.info("📊 Running manual sector check...")
        run_sector_check()
    
    def manual_correlation_check(self):
        """Run correlation check manually (for testing)"""
        logger.info("📊 Running manual correlation check...")
        run_correlation_check()

# Global monitor instance
_monitor = None

def get_monitor():
    """Get or create global monitor instance"""
    global _monitor
    if _monitor is None:
        _monitor = DailyRiskMonitor()
    return _monitor

def start_daily_monitor():
    """Start the daily risk monitor"""
    monitor = get_monitor()
    monitor.start(daemon=True)

def stop_daily_monitor():
    """Stop the daily risk monitor"""
    monitor = get_monitor()
    monitor.stop()

def run_checks_now():
    """Run both checks immediately (for testing)"""
    logger.info("Running all checks NOW...")
    run_sector_check()
    run_correlation_check()

# CLI
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Daily Risk Monitor')
    parser.add_argument('--action', choices=['start', 'stop', 'sector', 'correlation', 'all'], 
                       default='start', help='Action to perform')
    args = parser.parse_args()
    
    monitor = get_monitor()
    
    if args.action == 'start':
        monitor.start(daemon=False)
        try:
            while monitor.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            monitor.stop()
    
    elif args.action == 'stop':
        monitor.stop()
    
    elif args.action == 'sector':
        monitor.manual_sector_check()
    
    elif args.action == 'correlation':
        monitor.manual_correlation_check()
    
    elif args.action == 'all':
        run_checks_now()
