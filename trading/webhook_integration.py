#!/usr/bin/env python3
"""
Webhook Integration Module
Patches webhook_listener.py to add pre-entry risk checks
Use: from webhook_integration import add_entry_checks
"""

import logging
import json
from entry_validator import validate_entry, format_entry_check_message
from sector_monitor import get_telegram_alert_message as get_sector_alert
from correlation_monitor import get_telegram_alert_message as get_correlation_alert

logger = logging.getLogger(__name__)

def add_entry_checks(ticker, size=1.0, send_alert_func=None):
    """
    Perform entry validation checks before position entry
    
    Args:
        ticker: Symbol to validate
        size: Position size
        send_alert_func: Function to send alerts (telegram_send_message or similar)
    
    Returns:
        {'allowed': bool, 'result': EntryValidationResult}
    """
    result = validate_entry(ticker, size)
    
    # Send alert to user
    if send_alert_func:
        message = format_entry_check_message(ticker, result, size)
        try:
            send_alert_func(message)
        except Exception as e:
            logger.error(f"Error sending alert: {e}")
    
    return {
        'allowed': result.allowed,
        'violations': result.violations,
        'warnings': result.warnings,
        'checks': result.checks,
        'result_dict': result.to_dict()
    }

def integration_instructions():
    """
    Instructions for integrating into webhook_listener.py
    """
    return """
# INTEGRATION INSTRUCTIONS FOR webhook_listener.py

1. Add import at top:
   from webhook_integration import add_entry_checks

2. Modify the handler that processes entry alerts:
   
   OLD CODE:
   ```
   # Process entry alert...
   position_size = calculate_size(...)
   send_to_broker(symbol, position_size)
   ```
   
   NEW CODE:
   ```
   # PRE-ENTRY VALIDATION
   entry_check = add_entry_checks(
       ticker=symbol,
       size=position_size,
       send_alert_func=telegram_send_message
   )
   
   if not entry_check['allowed']:
       logger.error(f"Entry blocked for {symbol}: {entry_check['violations']}")
       telegram_send_message(
           f"❌ *ENTRY BLOCKED* {symbol}\\n" + 
           "\\n".join(entry_check['violations'])
       )
       return  # Don't send order
   
   # Entry checks passed - proceed with position
   position_size = calculate_size(...)
   send_to_broker(symbol, position_size)
   ```

3. Test with:
   python -c "from webhook_integration import add_entry_checks; print(add_entry_checks('AAPL', 1.0))"

4. Monitor logs:
   - sector_concentration.json for sector tracking
   - correlation_matrix.json for correlation tracking
   - trading/logs/*.log for validation details
"""

# Example integration in webhook_listener.py context
class WebhookEnricher:
    """
    Enriches webhook alerts with pre-entry risk checks
    Can wrap the existing TradingView alert handler
    """
    
    def __init__(self, send_alert_func=None):
        self.send_alert_func = send_alert_func
    
    def process_entry_alert(self, alert_data):
        """
        Process entry alert with risk checks
        
        alert_data should contain:
        - symbol: str
        - action: 'BUY' or 'SELL'
        - size: float (optional)
        """
        symbol = alert_data.get('symbol', '').upper()
        action = alert_data.get('action', '').upper()
        size = alert_data.get('size', 1.0)
        
        if action not in ['BUY', 'SELL']:
            return {
                'status': 'invalid_action',
                'error': f"Unknown action: {action}"
            }
        
        if not symbol:
            return {
                'status': 'invalid_symbol',
                'error': "No symbol provided"
            }
        
        # Only check BUY orders (not sells)
        if action == 'BUY':
            check_result = add_entry_checks(symbol, size, self.send_alert_func)
            
            return {
                'status': 'entry_validated' if check_result['allowed'] else 'entry_blocked',
                'symbol': symbol,
                'action': action,
                'allowed': check_result['allowed'],
                'violations': check_result['violations'],
                'warnings': check_result['warnings'],
                'check_details': check_result['result_dict']
            }
        
        # SELL orders don't need pre-entry checks
        return {
            'status': 'sell_order',
            'symbol': symbol,
            'action': action,
            'allowed': True
        }

# Module-level integration helper
def install_checks_in_webhook(webhook_handler_class):
    """
    Decorator to inject entry checks into webhook handler
    
    Usage:
        @install_checks_in_webhook
        class MyWebhookHandler:
            def handle_entry_alert(self, alert):
                ...
    """
    original_handle = webhook_handler_class.handle_entry_alert
    
    def new_handle_entry_alert(self, alert):
        # Run entry checks first
        symbol = alert.get('symbol', '').upper()
        size = alert.get('size', 1.0)
        
        check = add_entry_checks(
            symbol, 
            size,
            self.send_alert if hasattr(self, 'send_alert') else None
        )
        
        if not check['allowed']:
            logger.warning(f"Entry blocked: {symbol} - {check['violations']}")
            return False  # Block the entry
        
        # Call original handler
        return original_handle(self, alert)
    
    webhook_handler_class.handle_entry_alert = new_handle_entry_alert
    return webhook_handler_class
