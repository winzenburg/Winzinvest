#!/usr/bin/env python3
"""
End of Day Gap Risk Check
Runs at 3:55 PM ET (2:55 PM MT) to close short positions before market close
Prevents overnight gap losses on CSP and short call positions
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Add scripts dir to path for imports
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from gap_risk_manager import get_gap_risk_positions, should_close_gap_risk_positions, get_eod_checklist
    GAP_MANAGER_LOADED = True
except ImportError as e:
    logger.warning("Gap Risk Manager not loaded: %s", e)
    GAP_MANAGER_LOADED = False

# Paths
TRADING_DIR = Path(__file__).resolve().parents[1]
LOGS_DIR = TRADING_DIR / 'logs'

# IB connection settings
IB_HOST = os.getenv('IB_HOST', '127.0.0.1')
IB_PORT = int(os.getenv('IB_PORT', '4001'))
IB_CLIENT_ID = 136  # Dedicated client ID for EOD tasks

# Telegram settings
TG_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TG_CHAT = os.getenv('TELEGRAM_CHAT_ID')

LOGS_DIR.mkdir(exist_ok=True)

def get_current_positions(ib) -> list:
    """Get current portfolio positions from IB, enriched with gap-risk type labels."""
    positions = []
    try:
        for pos in ib.positions():
            c = pos.contract
            qty = int(pos.position)
            # Translate IB secType + right into gap_risk_manager type labels
            if c.secType == 'OPT' and qty < 0:
                pos_type = 'CSP' if c.right.upper() == 'P' else 'SHORT_CALL'
            else:
                pos_type = c.secType
            positions.append({
                'symbol': c.symbol,
                'quantity': qty,
                'type': pos_type,
                'entry_price': float(pos.avgCost),
                'days_to_expiration': 0,  # filled below if available
            })
    except Exception as e:
        logger.warning("Could not fetch positions: %s", e)
    return positions

def send_telegram(text):
    """Send Telegram notification"""
    if not (TG_TOKEN and TG_CHAT):
        return False
    
    import urllib.parse, urllib.request
    
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        'chat_id': TG_CHAT,
        'text': text,
        'parse_mode': 'Markdown'
    }).encode()
    
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False

def main():
    logger.info("=== GAP RISK EOD CHECK STARTED ===")
    
    if not GAP_MANAGER_LOADED:
        logger.error("Gap Risk Manager not loaded. Exiting.")
        return
    
    # Check if we should act (within 5 min of close)
    if not should_close_gap_risk_positions():
        logger.info("Not yet time to act (need to be within 5 min of close)")
        return
    
    logger.info("🚨 URGENT: Within 5 minutes of market close!")
    
    # Connect to IB
    from ib_insync import IB
    ib = IB()
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=10)
        logger.info("✅ Connected to IB Gateway")
    except Exception as e:
        logger.error(f"Failed to connect to IB: {e}")
        msg = f"❌ Gap Risk Check FAILED: Could not connect to IB Gateway\n{e}"
        send_telegram(msg)
        return
    
    try:
        # Get current positions
        positions = get_current_positions(ib)
        logger.info(f"Current positions: {len(positions)}")
        
        # Get gap risk checklist
        checklist = get_eod_checklist(positions)
        
        logger.info(f"Time to close: {checklist['time_remaining_min']:.1f} minutes")
        logger.info(f"Gap risk positions: {len(checklist['gap_risk_positions'])}")
        
        if checklist['gap_risk_positions']:
            # Report gap risk positions
            msg = f"⚠️ *Gap Risk Check*\n\n"
            msg += f"Time to close: {checklist['time_remaining_min']:.1f} min\n"
            msg += f"Gap risk positions: {len(checklist['gap_risk_positions'])}\n\n"
            
            for pos in checklist['gap_risk_positions']:
                msg += f"• {pos['symbol']} {pos['type']} (exp: {pos['days_to_expiration']}d)\n"
            
            if checklist['should_act']:
                msg += f"\n🚨 *ACTION REQUIRED NOW*\n"
                msg += f"Close these positions or reduce size\n"
            else:
                msg += f"\n⏰ Monitor closely, action needed within 5 minutes\n"
            
            logger.info(f"Sending Telegram alert...")
            send_telegram(msg)
            
            # Log checklist
            log_file = LOGS_DIR / f"gap_risk_{int(time.time())}.json"
            log_file.write_text(json.dumps({
                'timestamp': datetime.now().isoformat(),
                'time_remaining_min': checklist['time_remaining_min'],
                'should_act': checklist['should_act'],
                'positions': checklist['gap_risk_positions'],
            }, indent=2))
        else:
            logger.info("✅ No gap risk positions")
            send_telegram("✅ Gap Risk Check: No gap risk positions to manage")
        
        logger.info("=== GAP RISK EOD CHECK COMPLETE ===")
        
    except Exception as e:
        logger.error(f"Error during gap risk check: {e}")
        msg = f"❌ Gap Risk Check ERROR: {e}"
        send_telegram(msg)
    finally:
        ib.disconnect()
        logger.info("🔌 Disconnected from IB")

if __name__ == '__main__':
    main()
