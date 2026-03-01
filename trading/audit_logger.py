#!/usr/bin/env python3
"""
Comprehensive Audit Logger Module
Logs every critical event with timestamp, component, action, result, parameters
Format: JSON lines (queryable, parseable) in trading/logs/audit.jsonl
Permanent audit trail for forensic analysis
"""

import json
import logging
import os
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

# Configure logging for the audit module itself
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Audit log path
AUDIT_LOG_DIR = os.path.expanduser('~/.openclaw/workspace/trading/logs')
AUDIT_LOG_FILE = os.path.join(AUDIT_LOG_DIR, 'audit.jsonl')
AUDIT_LOCK = threading.Lock()

# Ensure log directory exists
os.makedirs(AUDIT_LOG_DIR, exist_ok=True)

# Event types supported by the audit system
SUPPORTED_EVENT_TYPES = {
    'SCREENER_RUN',
    'ENTRY_SIGNAL',
    'STOP_PLACED',
    'STOP_FILLED',
    'POSITION_CLOSED',
    'RISK_GATE_TRIGGERED',
    'CIRCUIT_BREAKER',
    'EARNINGS_ALERT',
    'OPTIONS_DECISION',
    'HEALTH_CHECK',
    'WEBHOOK_ALERT',
    'GAP_PROTECTION',
    'CORRELATION_CHECK',
    'LIQUIDATION',
    'ERROR_EVENT',
}


class AuditLogger:
    """
    Comprehensive audit logging system
    Logs all critical events in JSON lines format
    Thread-safe append-only audit trail
    """
    
    def __init__(self, log_file: str = AUDIT_LOG_FILE):
        """
        Initialize audit logger
        
        Args:
            log_file: Path to audit.jsonl file
        """
        self.log_file = log_file
        self.event_count = 0
        self._ensure_file_exists()
        
    def _ensure_file_exists(self):
        """Ensure audit log file exists"""
        try:
            if not os.path.exists(self.log_file):
                Path(self.log_file).touch()
                logger.info(f"📝 Created audit log file: {self.log_file}")
        except Exception as e:
            logger.error(f"❌ Failed to create audit log file: {e}")
    
    def _get_timestamp(self) -> str:
        """Get ISO 8601 timestamp"""
        return datetime.utcnow().isoformat() + 'Z'
    
    def _validate_event(self, event_type: str, data: Dict[str, Any]) -> bool:
        """Validate event type and required fields"""
        if event_type not in SUPPORTED_EVENT_TYPES:
            logger.warning(f"⚠️  Unknown event type: {event_type}")
            return False
        
        # Check for required fields based on event type
        required_fields = {
            'SCREENER_RUN': ['candidates_found', 'filters_passed'],
            'ENTRY_SIGNAL': ['symbol', 'entry_price', 'quantity', 'reason'],
            'STOP_PLACED': ['symbol', 'stop_price', 'order_id'],
            'STOP_FILLED': ['symbol', 'fill_price'],
            'POSITION_CLOSED': ['symbol', 'exit_price', 'reason'],
            'RISK_GATE_TRIGGERED': ['gate_name', 'reason', 'blocked'],
            'CIRCUIT_BREAKER': ['vix_level', 'regime_change', 'action'],
            'EARNINGS_ALERT': ['symbol', 'earnings_date', 'action'],
            'OPTIONS_DECISION': ['symbol', 'strike', 'decision', 'reason'],
            'HEALTH_CHECK': ['component', 'status'],
            'WEBHOOK_ALERT': ['signal_type', 'symbol'],
            'GAP_PROTECTION': ['symbol', 'action', 'gap_size'],
            'CORRELATION_CHECK': ['symbols', 'correlation'],
            'LIQUIDATION': ['symbol', 'reason', 'price'],
            'ERROR_EVENT': ['error_type', 'component', 'message'],
        }
        
        if event_type in required_fields:
            missing = [f for f in required_fields[event_type] if f not in data]
            if missing:
                logger.warning(f"⚠️  Event {event_type} missing fields: {missing}")
                # Don't fail, just warn - allow partial logging
        
        return True
    
    def log(self, event_type: str, **kwargs) -> bool:
        """
        Log an audit event
        
        Args:
            event_type: Type of event (ENTRY_SIGNAL, STOP_PLACED, etc.)
            **kwargs: Event-specific data
        
        Returns:
            True if logged successfully, False otherwise
        """
        try:
            # Validate event
            if not self._validate_event(event_type, kwargs):
                logger.debug(f"Skipping invalid event: {event_type}")
                return False
            
            # Build event record
            event = {
                'timestamp': self._get_timestamp(),
                'event_type': event_type,
                'data': kwargs
            }
            
            # Write to audit log (thread-safe append)
            with AUDIT_LOCK:
                with open(self.log_file, 'a') as f:
                    f.write(json.dumps(event) + '\n')
            
            self.event_count += 1
            logger.debug(f"✅ Logged {event_type} event #{self.event_count}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error logging audit event: {e}")
            return False
    
    def get_event_count(self) -> int:
        """Get total number of logged events"""
        return self.event_count
    
    def get_file_size(self) -> str:
        """Get audit log file size in human-readable format"""
        try:
            size = os.path.getsize(self.log_file)
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024:
                    return f"{size:.1f} {unit}"
                size /= 1024
            return f"{size:.1f} TB"
        except:
            return "Unknown"


# Global audit logger instance
_global_audit_logger: Optional[AuditLogger] = None
_audit_logger_lock = threading.Lock()


def get_audit_logger() -> AuditLogger:
    """Get or create global audit logger instance (singleton)"""
    global _global_audit_logger
    
    if _global_audit_logger is None:
        with _audit_logger_lock:
            if _global_audit_logger is None:
                _global_audit_logger = AuditLogger()
    
    return _global_audit_logger


def log_event(event_type: str, **kwargs) -> bool:
    """
    Convenience function to log an event using global audit logger
    
    Usage:
        from audit_logger import log_event
        log_event('ENTRY_SIGNAL', symbol='AAPL', entry_price=150.00, quantity=10, reason='breakout')
    
    Args:
        event_type: Type of event
        **kwargs: Event-specific data
    
    Returns:
        True if logged successfully
    """
    return get_audit_logger().log(event_type, **kwargs)


# Convenience logging functions for specific event types
def log_screener_run(candidates_found: int, symbols: List[str], filters_passed: Dict[str, int]) -> bool:
    """Log a screener run result"""
    return log_event('SCREENER_RUN', 
                     candidates_found=candidates_found,
                     symbols=symbols,
                     filters_passed=filters_passed)


def log_entry_signal(symbol: str, entry_price: float, quantity: int, reason: str, **kwargs) -> bool:
    """Log an entry signal"""
    return log_event('ENTRY_SIGNAL',
                     symbol=symbol,
                     entry_price=entry_price,
                     quantity=quantity,
                     reason=reason,
                     **kwargs)


def log_stop_placed(symbol: str, stop_price: float, order_id: str, **kwargs) -> bool:
    """Log a stop-loss order placement"""
    return log_event('STOP_PLACED',
                     symbol=symbol,
                     stop_price=stop_price,
                     order_id=order_id,
                     **kwargs)


def log_stop_filled(symbol: str, fill_price: float, slippage: Optional[float] = None, 
                    pnl: Optional[float] = None, **kwargs) -> bool:
    """Log a stop-loss fill"""
    return log_event('STOP_FILLED',
                     symbol=symbol,
                     fill_price=fill_price,
                     slippage=slippage,
                     pnl=pnl,
                     **kwargs)


def log_position_closed(symbol: str, exit_price: float, reason: str, **kwargs) -> bool:
    """Log a position closure"""
    return log_event('POSITION_CLOSED',
                     symbol=symbol,
                     exit_price=exit_price,
                     reason=reason,
                     **kwargs)


def log_risk_gate_triggered(gate_name: str, position: str, reason: str, blocked: bool, **kwargs) -> bool:
    """Log a risk gate trigger"""
    return log_event('RISK_GATE_TRIGGERED',
                     gate_name=gate_name,
                     position=position,
                     reason=reason,
                     blocked=blocked,
                     **kwargs)


def log_circuit_breaker(vix_level: float, regime_change: str, action: str, **kwargs) -> bool:
    """Log a circuit breaker event"""
    return log_event('CIRCUIT_BREAKER',
                     vix_level=vix_level,
                     regime_change=regime_change,
                     action=action,
                     **kwargs)


def log_earnings_alert(symbol: str, earnings_date: str, action: str, **kwargs) -> bool:
    """Log an earnings alert"""
    return log_event('EARNINGS_ALERT',
                     symbol=symbol,
                     earnings_date=earnings_date,
                     action=action,
                     **kwargs)


def log_options_decision(symbol: str, strike: float, decision: str, reason: str, **kwargs) -> bool:
    """Log an options decision"""
    return log_event('OPTIONS_DECISION',
                     symbol=symbol,
                     strike=strike,
                     decision=decision,
                     reason=reason,
                     **kwargs)


def log_health_check(component: str, status: str, response_time_ms: Optional[int] = None,
                     error: Optional[str] = None, **kwargs) -> bool:
    """Log a health check result"""
    return log_event('HEALTH_CHECK',
                     component=component,
                     status=status,
                     response_time_ms=response_time_ms,
                     error=error,
                     **kwargs)


def log_webhook_alert(signal_type: str, symbol: str, price: Optional[float] = None, **kwargs) -> bool:
    """Log a webhook alert"""
    return log_event('WEBHOOK_ALERT',
                     signal_type=signal_type,
                     symbol=symbol,
                     price=price,
                     **kwargs)


def log_gap_protection(symbol: str, action: str, gap_size: float, **kwargs) -> bool:
    """Log a gap protection event"""
    return log_event('GAP_PROTECTION',
                     symbol=symbol,
                     action=action,
                     gap_size=gap_size,
                     **kwargs)


def log_correlation_check(symbols: List[str], correlation: float, action: str, **kwargs) -> bool:
    """Log a correlation check result"""
    return log_event('CORRELATION_CHECK',
                     symbols=symbols,
                     correlation=correlation,
                     action=action,
                     **kwargs)


def log_liquidation(symbol: str, reason: str, price: float, **kwargs) -> bool:
    """Log a position liquidation"""
    return log_event('LIQUIDATION',
                     symbol=symbol,
                     reason=reason,
                     price=price,
                     **kwargs)


def log_error(error_type: str, component: str, message: str, **kwargs) -> bool:
    """Log an error event"""
    return log_event('ERROR_EVENT',
                     error_type=error_type,
                     component=component,
                     message=message,
                     **kwargs)


if __name__ == '__main__':
    # Test the audit logger
    print("🧪 Testing Audit Logger...")
    
    logger_instance = get_audit_logger()
    
    # Test various event types
    log_screener_run(
        candidates_found=5,
        symbols=['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'AMZN'],
        filters_passed={'price_filter': 5, 'volume_filter': 4, 'trend_filter': 3}
    )
    
    log_entry_signal(
        symbol='AAPL',
        entry_price=150.25,
        quantity=10,
        reason='breakout above 200MA',
        confidence=0.95
    )
    
    log_stop_placed(
        symbol='AAPL',
        stop_price=145.00,
        order_id='123456',
        risk_pct=0.035
    )
    
    log_circuit_breaker(
        vix_level=22.5,
        regime_change='normal→caution',
        action='reduce_position_size'
    )
    
    log_health_check(
        component='ib_gateway',
        status='ok',
        response_time_ms=42
    )
    
    print(f"✅ Logged {logger_instance.get_event_count()} events")
    print(f"📊 Audit log size: {logger_instance.get_file_size()}")
    print(f"📁 Audit log location: {AUDIT_LOG_FILE}")
