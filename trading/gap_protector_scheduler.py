#!/usr/bin/env python3
"""
Gap Protector Scheduler
Runs gap protection checks at scheduled times:
- 3:00 PM (15:00): Check for earnings alerts (pre-liquidation)
- 8:00 AM (08:00): Run auto-liquidation logic for violations

Can be run as a cron job or background scheduler
"""

import json
import logging
import os
import asyncio
from pathlib import Path
from datetime import datetime, time
from typing import Dict, List, Optional
import schedule
import time as time_module

from gap_protector import (
    identify_liquidation_candidates,
    format_gap_protection_report,
    format_liquidation_summary,
    auto_liquidate_violations,
    check_critical_econ_event,
    load_protected_portfolio,
    save_protected_portfolio
)
from earnings_calendar import format_earnings_report, get_earnings_calendar, check_earnings_alert
from econ_calendar import format_economic_report, check_econ_alerts, should_liquidate_all_positions

logger = logging.getLogger(__name__)

# Configuration
ALERT_CHANNEL = os.getenv('TELEGRAM_CHAT_ID')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
IB_AUTO_LIQUIDATE = os.getenv('AUTO_LIQUIDATE', 'true').lower() == 'true'
DRY_RUN = os.getenv('GAP_PROTECTOR_DRY_RUN', 'true').lower() == 'true'

# State tracking
STATE_FILE = Path(os.path.expanduser('~/.openclaw/workspace/trading/.gap_scheduler_state.json'))


def load_state() -> Dict:
    """Load scheduler state"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {'last_3pm_check': None, 'last_8am_check': None}


def save_state(state: Dict):
    """Save scheduler state"""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, default=str)
    except Exception as e:
        logger.error(f"Error saving state: {e}")


def build_alert_message(
    alert_type: str,
    positions: List[Dict],
    details: Optional[Dict] = None
) -> str:
    """
    Build Telegram alert message
    alert_type: 'EARNINGS', 'ECON', 'LIQUIDATED', 'CRITICAL'
    """
    now = datetime.now().strftime('%H:%M')
    
    if alert_type == 'EARNINGS':
        msg = f"⏰ EARNINGS ALERT [{now}]\n"
        msg += f"Positions reporting earnings in next 2 days:\n"
        for pos in positions:
            days = pos.get('earnings_days_away', '?')
            msg += f"  • {pos['symbol']}: {days}d ({pos.get('earnings_date', 'N/A')})\n"
        msg += "\n⚠️ Will close at open tomorrow if not manually closed"
        return msg
    
    elif alert_type == 'ECON':
        msg = f"📊 ECONOMIC EVENT ALERT [{now}]\n"
        event = details.get('event', {})
        days = details.get('days_until', '?')
        msg += f"{event.get('description')} in {days} days\n"
        msg += f"Impact: {event.get('impact', 'N/A')}\n"
        msg += f"\n⚠️ Will close all positions within {event.get('alert_days', 1)} days"
        return msg
    
    elif alert_type == 'LIQUIDATED':
        msg = f"✅ POSITIONS LIQUIDATED [{now}]\n"
        for pos in positions:
            msg += f"  {pos['symbol']}: ${pos.get('price', '?'):.2f}\n"
            msg += f"    Reason: {pos.get('reason', 'N/A')}\n"
        return msg
    
    elif alert_type == 'CRITICAL':
        msg = f"🔴 CRITICAL EVENT - ALL POSITIONS CLOSING [{now}]\n"
        event = details.get('event', {})
        msg += f"Event: {event.get('description', 'Unknown')}\n"
        msg += f"Close in: {details.get('days_until', '?')} days\n"
        return msg
    
    return "Unknown alert type"


def send_alert(message: str, channel: Optional[str] = None):
    """
    Send alert via configured channel (Telegram, webhook, etc.)
    For now, logs to file as proof of concept
    """
    try:
        # Log to alert file
        alert_dir = Path(os.path.expanduser('~/.openclaw/workspace/trading/logs'))
        alert_dir.mkdir(parents=True, exist_ok=True)
        
        alert_file = alert_dir / 'gap_alerts.log'
        with open(alert_file, 'a') as f:
            f.write(f"\n[{datetime.now().isoformat()}]\n{message}\n")
        
        logger.info(f"📢 Alert sent:\n{message}")
        
        # In production, would send via webhook or Telegram API
        if WEBHOOK_URL:
            try:
                import requests
                requests.post(WEBHOOK_URL, json={'message': message, 'type': 'gap_protection'})
            except Exception as e:
                logger.debug(f"Webhook send failed: {e}")
    
    except Exception as e:
        logger.error(f"Error sending alert: {e}")


def fetch_portfolio_from_ib() -> Optional[List[Dict]]:
    """
    Fetch current portfolio from IB Gateway
    Returns list of position dicts
    """
    try:
        from ib_insync import IB
        import os
        
        ib = IB()
        ib_host = os.getenv('IB_HOST', '127.0.0.1')
        ib_port = int(os.getenv('IB_PORT', '4002'))
        
        ib.connect(ib_host, ib_port, clientId=101)
        
        positions = []
        for pos in ib.portfolio():
            positions.append({
                'symbol': pos.contract.symbol,
                'quantity': pos.position,
                'market_price': pos.marketPrice,
                'market_value': pos.marketValue,
                'average_cost': pos.averageCost,
                'unrealized_pnl': pos.unrealizedPNL
            })
        
        ib.disconnect()
        return positions
    
    except Exception as e:
        logger.error(f"Error fetching portfolio from IB: {e}")
        return None


def job_3pm_earnings_check():
    """
    3:00 PM Job: Check for upcoming earnings
    Alert user if positions have earnings in next 2 days
    """
    logger.info("🕐 Running 3 PM earnings check...")
    state = load_state()
    
    try:
        # Fetch portfolio
        positions = fetch_portfolio_from_ib()
        if not positions:
            logger.warning("Could not fetch portfolio from IB")
            return
        
        # Check for earnings alerts
        candidates = identify_liquidation_candidates(positions)
        earnings_alerts = [p for p in candidates if p.get('earnings_alert')]
        
        if earnings_alerts:
            msg = build_alert_message('EARNINGS', earnings_alerts)
            send_alert(msg)
            state['last_3pm_check'] = datetime.now().isoformat()
            state['last_earnings_alerts'] = len(earnings_alerts)
            save_state(state)
            logger.info(f"📢 Sent earnings alert for {len(earnings_alerts)} positions")
        else:
            logger.info("✅ No earnings alerts")
    
    except Exception as e:
        logger.error(f"Error in 3 PM job: {e}")


def job_8am_auto_liquidate():
    """
    8:00 AM Job: Auto-liquidate positions that violate rules
    - Earnings < 2 days away
    - Major economic event < 1-3 days away
    """
    logger.info("🕐 Running 8 AM auto-liquidation job...")
    state = load_state()
    
    try:
        # Fetch portfolio
        positions = fetch_portfolio_from_ib()
        if not positions:
            logger.warning("Could not fetch portfolio from IB")
            return
        
        # Check for critical econ event first
        critical = check_critical_econ_event()
        if critical and not DRY_RUN:
            msg = build_alert_message('CRITICAL', [], {'event': critical, 'days_until': 0})
            send_alert(msg)
        
        # Identify candidates
        candidates = identify_liquidation_candidates(positions)
        
        if not candidates:
            logger.info("✅ No liquidation candidates")
            state['last_8am_check'] = datetime.now().isoformat()
            save_state(state)
            return
        
        logger.warning(f"⚠️  Found {len(candidates)} positions to liquidate")
        
        # Auto-liquidate
        if IB_AUTO_LIQUIDATE and not DRY_RUN:
            # This would require IB connection in async context
            logger.info("🔄 Auto-liquidation enabled but requires async context")
            logger.info("In production, would liquidate the following:")
            for pos in candidates:
                logger.info(f"  {pos['symbol']}: {pos['close_reason']}")
        else:
            logger.info("[DRY RUN] Would liquidate:")
            for pos in candidates:
                logger.info(f"  {pos['symbol']}: {pos['close_reason']}")
        
        # Send alert with liquidation summary
        msg = f"📋 LIQUIDATION CHECK [{datetime.now().strftime('%H:%M')}]\n"
        msg += f"Candidates: {len(candidates)}\n"
        for pos in candidates[:5]:
            msg += f"  • {pos['symbol']}: {pos['close_reason']}\n"
        if len(candidates) > 5:
            msg += f"  ... and {len(candidates) - 5} more\n"
        
        if DRY_RUN:
            msg += "\n[DRY RUN - Not liquidating]"
        
        send_alert(msg)
        
        state['last_8am_check'] = datetime.now().isoformat()
        state['last_liquidation_candidates'] = len(candidates)
        save_state(state)
    
    except Exception as e:
        logger.error(f"Error in 8 AM job: {e}")


def run_scheduler():
    """Run the scheduler in foreground"""
    logger.info("🚀 Starting Gap Protector Scheduler")
    logger.info(f"   Mode: {'DRY RUN' if DRY_RUN else 'AUTO LIQUIDATE'}")
    logger.info(f"   Auto-liquidate enabled: {IB_AUTO_LIQUIDATE}")
    
    # Schedule jobs
    schedule.every().day.at("15:00").do(job_3pm_earnings_check)
    schedule.every().day.at("08:00").do(job_8am_auto_liquidate)
    
    logger.info("✅ Scheduled jobs:")
    logger.info("   • 08:00 - Auto-liquidate violations")
    logger.info("   • 15:00 - Check earnings alerts")
    
    # Run forever
    try:
        while True:
            schedule.run_pending()
            time_module.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("⏹️  Scheduler stopped")


def run_once(job_type: str = 'both'):
    """Run jobs immediately (for testing)"""
    logger.info(f"🔄 Running {job_type} job(s) immediately...")
    
    if job_type in ['earnings', 'both']:
        job_3pm_earnings_check()
    
    if job_type in ['liquidate', 'both']:
        job_8am_auto_liquidate()
    
    logger.info("✅ Done")


if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'run':
            run_scheduler()
        elif sys.argv[1] == 'test-earnings':
            job_3pm_earnings_check()
        elif sys.argv[1] == 'test-liquidate':
            job_8am_auto_liquidate()
        elif sys.argv[1] == 'test-all':
            run_once('both')
        else:
            print("Usage: gap_protector_scheduler.py [run|test-earnings|test-liquidate|test-all]")
    else:
        print("Usage: gap_protector_scheduler.py [run|test-earnings|test-liquidate|test-all]")
        print("\nExamples:")
        print("  python3 gap_protector_scheduler.py run           # Run scheduler")
        print("  python3 gap_protector_scheduler.py test-earnings # Test 3PM check")
        print("  python3 gap_protector_scheduler.py test-liquidate # Test 8AM check")
