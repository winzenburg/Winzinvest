#!/usr/bin/env python3
"""
TradingView Webhook Listener
Listens for alerts from TradingView Pine Script → routes to Telegram
Integrated with stop-loss manager for automatic stop placement on position entry
"""

import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from pathlib import Path
import os
import sys
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import stop-loss manager
try:
    from stop_manager import StopLossManager
    STOP_MANAGER_AVAILABLE = True
except ImportError:
    logger.warning("⚠️  stop_manager module not available - stop-loss functionality disabled")
    STOP_MANAGER_AVAILABLE = False

# Import circuit breaker and VIX monitor
try:
    from circuit_breaker import get_circuit_breaker
    from vix_monitor import get_vix_monitor
    CIRCUIT_BREAKER_AVAILABLE = True
except ImportError:
    logger.warning("⚠️  circuit_breaker/vix_monitor modules not available - VIX-based controls disabled")
    CIRCUIT_BREAKER_AVAILABLE = False

WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', 5001))
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Global stop manager instance
_stop_manager = None
_stop_manager_lock = threading.Lock()


def get_stop_manager():
    """Get or create the global stop manager instance"""
    global _stop_manager
    if _stop_manager is None and STOP_MANAGER_AVAILABLE:
        with _stop_manager_lock:
            if _stop_manager is None:
                _stop_manager = StopLossManager()
                if not _stop_manager.connect():
                    logger.warning("⚠️  Failed to connect stop manager to IB Gateway")
                    _stop_manager = None
    return _stop_manager


class TradingViewWebhookHandler(BaseHTTPRequestHandler):
    """Handle incoming TradingView webhook alerts"""

    def do_POST(self):
        """Process POST request from TradingView"""
        if self.path == '/tradingview':
            return self._handle_tradingview_alert()
        elif self.path == '/webhook':
            return self._handle_webhook()
        else:
            self.send_response(404)
            self.end_headers()
            return
    
    def _handle_tradingview_alert(self):
        """Handle TradingView Pine Script alerts"""
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            
            logger.info(f"Received TradingView alert: {body[:200]}")
            
            # For now, log the alert and send success response
            # Full execution will be done async
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'status': 'received',
                'timestamp': datetime.now().isoformat(),
                'message': 'TradingView alert received and queued for execution'
            }).encode())
            
            # Store alert for async processing
            alert_file = Path(__file__).parent.parent / 'logs' / f'tv_alert_{datetime.now().timestamp()}.txt'
            alert_file.write_text(body)
            logger.info(f"Alert stored: {alert_file}")
            
        except Exception as e:
            logger.error(f"Error handling TradingView alert: {e}")
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())
        
        return
    
    def _handle_webhook(self):
        """Handle standard webhook (old format)"""
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            
            logger.info(f"Received webhook: {body}")
            
            # Parse JSON
            alert_data = json.loads(body)
            
            # Check circuit breaker before processing entry
            circuit_breaker_status = None
            if CIRCUIT_BREAKER_AVAILABLE and is_entry_signal(alert_data):
                try:
                    breaker = get_circuit_breaker()
                    symbol = alert_data.get('symbol', 'UNKNOWN')
                    can_enter, entry_status = breaker.can_enter_position(symbol)
                    circuit_breaker_status = entry_status
                    
                    if not can_enter:
                        logger.warning(f"⚠️  Circuit breaker BLOCKED entry for {symbol}")
                        # Still format the alert but mark it as blocked
                        alert_data['circuit_breaker_blocked'] = True
                    else:
                        # Adjust position size and stops based on circuit breaker
                        base_qty = int(alert_data.get('quantity', 10))
                        adjustment = breaker.get_entry_adjustment(base_qty, symbol)
                        
                        if adjustment['adjusted_size'] != base_qty:
                            logger.info(f"📊 Circuit breaker adjusted size: {base_qty} → {adjustment['adjusted_size']}")
                            alert_data['original_quantity'] = base_qty
                            alert_data['quantity'] = adjustment['adjusted_size']
                            alert_data['circuit_breaker_adjusted'] = True
                            alert_data['size_multiplier'] = adjustment['size_multiplier']
                        
                        # Update risk_pct with circuit breaker stops
                        if adjustment['stop_percent'] != alert_data.get('risk_pct', 0) / 100:
                            logger.info(f"🛡️  Circuit breaker applied stop: {(alert_data.get('risk_pct', 2) / 100)*100:.1f}% → {adjustment['stop_percent']*100:.1f}%")
                            alert_data['original_risk_pct'] = alert_data.get('risk_pct')
                            alert_data['risk_pct'] = int(adjustment['stop_percent'] * 100)
                            alert_data['circuit_breaker_adjusted'] = True
                except Exception as e:
                    logger.error(f"❌ Circuit breaker check failed: {e}")
            
            # Check if this is a position entry signal - if so, place stop-loss
            if is_entry_signal(alert_data) and not alert_data.get('circuit_breaker_blocked', False):
                place_stop_loss(alert_data)
            
            # Format message for Telegram
            message = format_alert(alert_data, circuit_breaker_status)
            
            # Send to Telegram
            send_telegram(message)
            
            # Return success
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'status': 'received',
                'timestamp': datetime.now().isoformat()
            }).encode())
            
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

    def log_message(self, format, *args):
        """Suppress default HTTP logging"""
        logger.info(f"HTTP: {format % args}")


def is_entry_signal(alert_data) -> bool:
    """
    Detect if this is a position entry signal
    Expected fields: action='BUY' or 'LONG', and price field present
    """
    try:
        action = alert_data.get('action', '').upper()
        has_price = alert_data.get('price') is not None
        return action in ['BUY', 'LONG'] and has_price
    except:
        return False


def place_stop_loss(alert_data: dict) -> bool:
    """
    Place a companion stop-loss order when position enters
    Expects: symbol, action, price, quantity (optional), sector (optional), risk_pct (optional)
    """
    try:
        symbol = alert_data.get('symbol', '').upper()
        entry_price = float(alert_data.get('price', 0))
        quantity = int(alert_data.get('quantity', 10))
        sector = alert_data.get('sector', None)
        risk_pct = float(alert_data.get('risk_pct', 0)) / 100 if alert_data.get('risk_pct') else None
        
        if not symbol or entry_price <= 0 or quantity <= 0:
            logger.warning(f"⚠️  Invalid stop-loss parameters: {alert_data}")
            return False
            
        # Get or create stop manager
        manager = get_stop_manager()
        if manager is None:
            logger.error("❌ Stop manager not available")
            return False
            
        # Place the stop
        result = manager.place_stop(symbol, entry_price, quantity, sector=sector, risk_pct=risk_pct)
        
        if result:
            logger.info(f"✅ Stop-loss placed for {symbol}: {result['stop_price']}")
            return True
        else:
            logger.error(f"❌ Failed to place stop-loss for {symbol}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error placing stop-loss: {e}")
        return False


def format_alert(alert_data, circuit_breaker_status=None):
    """Format TradingView alert for Telegram"""
    try:
        symbol = alert_data.get('symbol', 'UNKNOWN')
        action = alert_data.get('action', 'ALERT')
        price = alert_data.get('price', 'N/A')
        message_text = alert_data.get('message', '')
        
        # Build base Telegram message
        telegram_msg = f"""
📊 *TradingView Alert*

*Symbol:* `{symbol}`
*Action:* {action}
*Price:* {price}

{message_text}
"""
        
        # Add circuit breaker status
        if alert_data.get('circuit_breaker_blocked'):
            telegram_msg += f"\n⛔ *CIRCUIT BREAKER:* Entry BLOCKED - Volatility regime prevents new entries"
            if circuit_breaker_status:
                regime = circuit_breaker_status.get('regime', 'Unknown')
                vix = circuit_breaker_status.get('vix', 'Unknown')
                telegram_msg += f"\n   Regime: {regime} (VIX: {vix})"
        elif alert_data.get('circuit_breaker_adjusted'):
            original_qty = alert_data.get('original_quantity', alert_data.get('quantity', 'N/A'))
            adjusted_qty = alert_data.get('quantity', 'N/A')
            mult = alert_data.get('size_multiplier', 1.0)
            telegram_msg += f"\n🛡️  *CIRCUIT BREAKER:* Position size reduced"
            telegram_msg += f"\n   Size: {original_qty} → {adjusted_qty} ({mult*100:.0f}%)"
            if circuit_breaker_status:
                regime = circuit_breaker_status.get('regime', 'Unknown')
                vix = circuit_breaker_status.get('vix', 'Unknown')
                telegram_msg += f"\n   Regime: {regime} (VIX: {vix})"
        
        # Add stop-loss info if this was an entry
        if is_entry_signal(alert_data):
            try:
                entry = float(alert_data.get('price', 0))
                risk = float(alert_data.get('risk_pct', 2)) / 100
                stop_price = entry * (1 - risk)
                telegram_msg += f"\n🛑 *Stop-Loss:* ${stop_price:.2f} ({risk*100:.1f}% risk)"
            except:
                pass
        
        telegram_msg += f"\n_Time: {datetime.now().strftime('%H:%M:%S')}_"
        return telegram_msg.strip()
    except Exception as e:
        logger.error(f"Error formatting alert: {e}")
        return f"Alert received: {json.dumps(alert_data)}"


def send_telegram(message):
    """Send message to Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials not set (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)")
        return
    
    try:
        import requests
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        }
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            logger.info("Message sent to Telegram")
        else:
            logger.error(f"Telegram error: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Error sending to Telegram: {e}")


def start_server():
    """Start webhook listener"""
    server_address = ('127.0.0.1', WEBHOOK_PORT)
    httpd = HTTPServer(server_address, TradingViewWebhookHandler)
    logger.info(f"🦞 TradingView Webhook Listener started on http://127.0.0.1:{WEBHOOK_PORT}/tradingview")
    logger.info("Waiting for alerts...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        httpd.shutdown()


if __name__ == '__main__':
    start_server()
