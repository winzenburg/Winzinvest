#!/usr/bin/env python3
"""
Stop-Loss Order Monitor
Monitors pending stops for execution, updates logs, and alerts on fills
Designed to run as a cron job (8:30 AM, 11:30 AM, 2:30 PM, 4:00 PM)
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import List, Dict
import sys
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import our stop manager
try:
    from stop_manager import StopLossManager, STOP_LOSS_LOG, PENDING_STOPS_FILE
except ImportError:
    # Fallback if module not installed properly
    STOP_LOSS_LOG = os.path.expanduser('~/.openclaw/workspace/trading/logs/stops_executed.json')
    PENDING_STOPS_FILE = os.path.expanduser('~/.openclaw/workspace/trading/logs/pending_stops.json')


class StopMonitor:
    """Monitors stop-loss orders and handles alerts"""
    
    def __init__(self, telegram_bot_token=None, telegram_chat_id=None):
        """
        Initialize the monitor
        
        Args:
            telegram_bot_token: Telegram bot token for alerts (optional)
            telegram_chat_id: Telegram chat ID for alerts (optional)
        """
        self.telegram_bot_token = telegram_bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = telegram_chat_id or os.getenv('TELEGRAM_CHAT_ID')
        self.stop_manager = StopLossManager()
        self.filled_stops = set()  # Track which stops we've already alerted on
        
    def run(self) -> Dict:
        """
        Main monitoring cycle
        
        Returns:
            Summary dict with results
        """
        logger.info("🔍 Starting stop-loss monitoring cycle...")
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'stops_monitored': 0,
            'stops_filled': [],
            'stops_cancelled': [],
            'stops_pending': [],
            'errors': [],
        }
        
        # Connect to IB Gateway
        if not self.stop_manager.connect():
            summary['errors'].append("Failed to connect to IB Gateway")
            logger.error("❌ Could not connect to IB Gateway")
            return summary
            
        try:
            # Monitor all pending stops
            updates = self.stop_manager.monitor_all_stops()
            summary['stops_monitored'] = len(updates)
            
            # Process each update
            for order_data in updates:
                symbol = order_data['symbol']
                order_id = order_data['order_id']
                status = order_data['status']
                
                if status == 'filled':
                    # Log the fill
                    self.stop_manager.log_filled_stop(order_data)
                    summary['stops_filled'].append({
                        'symbol': symbol,
                        'fill_price': order_data.get('fill_price'),
                        'realized_pnl': order_data.get('realized_pnl'),
                    })
                    
                    # Alert the user
                    self.send_alert(order_data)
                    
                    # Remove from pending
                    if order_id in self.stop_manager.pending_stops:
                        del self.stop_manager.pending_stops[order_id]
                        
                elif status == 'cancelled':
                    summary['stops_cancelled'].append({
                        'symbol': symbol,
                        'cancel_reason': 'Manual or system cancelled',
                    })
                    
                    # Remove from pending
                    if order_id in self.stop_manager.pending_stops:
                        del self.stop_manager.pending_stops[order_id]
                        
                else:
                    # Still pending
                    summary['stops_pending'].append({
                        'symbol': symbol,
                        'stop_price': order_data['stop_price'],
                        'entry_price': order_data['entry_price'],
                    })
                    
            # Save updated state
            self.stop_manager.save_pending_stops()
            
            logger.info(f"✅ Monitoring cycle complete: {summary['stops_monitored']} stops checked")
            logger.info(f"   Filled: {len(summary['stops_filled'])}, Cancelled: {len(summary['stops_cancelled'])}, Pending: {len(summary['stops_pending'])}")
            
        except Exception as e:
            summary['errors'].append(str(e))
            logger.error(f"❌ Error during monitoring: {e}")
            
        finally:
            self.stop_manager.disconnect()
            
        return summary
        
    def send_alert(self, order_data: Dict) -> bool:
        """
        Send alert when stop-loss is filled
        
        Args:
            order_data: Order data dict with fill info
            
        Returns:
            True if alert sent successfully
        """
        try:
            symbol = order_data['symbol']
            fill_price = order_data.get('fill_price', 'N/A')
            entry_price = order_data['entry_price']
            pnl = order_data.get('realized_pnl', 0)
            pnl_pct = (pnl / (entry_price * order_data['quantity'])) * 100 if order_data['quantity'] else 0
            
            # Format message
            alert_msg = f"""
⛔ *STOP-LOSS FILLED*

*Symbol:* `{symbol}`
*Entry Price:* ${entry_price:.2f}
*Exit Price:* ${fill_price}
*Loss:* ${pnl:.2f} ({pnl_pct:.2f}%)
*Quantity:* {order_data['quantity']}

_Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_
"""
            
            # Send to Telegram if configured
            if self.telegram_bot_token and self.telegram_chat_id:
                self._send_telegram(alert_msg)
                logger.info(f"✅ Alert sent to Telegram: {symbol}")
            else:
                logger.warning("⚠️  Telegram not configured - skipping alert")
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Error sending alert: {e}")
            return False
            
    def _send_telegram(self, message: str) -> bool:
        """Send message via Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            payload = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'Markdown',
            }
            response = requests.post(url, json=payload, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"❌ Telegram send failed: {e}")
            return False
            
    def get_summary(self) -> Dict:
        """Get summary of all stops (filled + pending)"""
        try:
            summary = {
                'timestamp': datetime.now().isoformat(),
                'pending': {},
                'filled': {},
            }
            
            # Load pending stops
            if os.path.exists(PENDING_STOPS_FILE):
                with open(PENDING_STOPS_FILE, 'r') as f:
                    pending_data = json.load(f)
                    for order_id, order_data in pending_data.get('pending', {}).items():
                        symbol = order_data.get('symbol')
                        if symbol:
                            summary['pending'][symbol] = {
                                'stop_price': order_data.get('stop_price'),
                                'entry_price': order_data.get('entry_price'),
                                'status': order_data.get('status'),
                            }
                            
            # Load filled stops
            if os.path.exists(STOP_LOSS_LOG):
                with open(STOP_LOSS_LOG, 'r') as f:
                    log_data = json.load(f)
                    for entry in log_data.get('stops', []):
                        symbol = entry.get('symbol')
                        if entry.get('status') == 'filled':
                            summary['filled'][symbol] = {
                                'fill_price': entry.get('fill_price'),
                                'realized_pnl': entry.get('realized_pnl'),
                            }
                            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Error getting summary: {e}")
            return {'error': str(e)}


def main():
    """Main entry point - designed for cron execution"""
    
    # Check if we're in market hours (rough check)
    now = datetime.now()
    hour = now.hour
    
    # Market hours roughly 9:30 AM - 4:00 PM EST (adjust for timezone)
    if hour < 9 or hour >= 17:
        logger.info("⏰ Outside market hours - skipping monitoring")
        return
        
    monitor = StopMonitor()
    result = monitor.run()
    
    # Log results
    logger.info(f"📊 Monitoring summary:")
    logger.info(f"   Stops monitored: {result['stops_monitored']}")
    logger.info(f"   Stops filled: {len(result['stops_filled'])}")
    logger.info(f"   Stops cancelled: {len(result['stops_cancelled'])}")
    logger.info(f"   Still pending: {len(result['stops_pending'])}")
    
    if result['errors']:
        logger.error(f"   Errors: {result['errors']}")
        
    # Print summary for logging
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
