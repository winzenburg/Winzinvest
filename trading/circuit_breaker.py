#!/usr/bin/env python3
"""
Circuit Breaker Module
Applies VIX-based position sizing and stop-loss adjustments
Prevents trading during high volatility and panic scenarios
"""

import json
import logging
import os
import threading
from datetime import datetime
from typing import Dict, Optional, Tuple, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import VIX monitor
try:
    from vix_monitor import get_vix_monitor, VIXMonitor, REGIME_NAMES
    VIX_MONITOR_AVAILABLE = True
except ImportError:
    logger.warning("⚠️  vix_monitor not available - circuit breaker will not work")
    VIX_MONITOR_AVAILABLE = False

# Circuit breaker configuration
CIRCUIT_BREAKER_CONFIG = {
    'normal': {
        'position_size_mult': 1.0,      # 100% position size
        'stop_percent': 0.025,           # 2.5% stops
        'allow_entries': True,           # Allow new entries
        'allow_scaling': True,           # Allow scaling positions
    },
    'caution': {
        'position_size_mult': 0.8,       # 80% position size
        'stop_percent': 0.018,           # 1.8% stops
        'allow_entries': True,
        'allow_scaling': True,
    },
    'reduced': {
        'position_size_mult': 0.5,       # 50% position size
        'stop_percent': 0.010,           # 1% stops
        'allow_entries': False,          # Don't add new entries, but hold
        'allow_scaling': False,          # Don't scale
    },
    'panic': {
        'position_size_mult': 0.0,       # PAUSE new entries
        'stop_percent': 0.005,           # 0.5% emergency stops
        'allow_entries': False,          # No new entries
        'allow_scaling': False,          # No scaling
    },
    'emergency': {
        'position_size_mult': 0.0,       # LIQUIDATE
        'stop_percent': 0.005,           # Tight emergency stops
        'allow_entries': False,
        'allow_scaling': False,
    },
}

# Circuit breaker log
CIRCUIT_BREAKER_LOG = os.path.expanduser('~/.openclaw/workspace/trading/logs/circuit_breaker_events.json')


class CircuitBreaker:
    """
    VIX-based circuit breaker for position sizing and risk management
    Dynamically adjusts position size, stops, and entry rules based on volatility
    """
    
    def __init__(self, vix_monitor: VIXMonitor = None):
        """
        Initialize circuit breaker
        
        Args:
            vix_monitor: VIXMonitor instance (optional, will use global if not provided)
        """
        self.vix_monitor = vix_monitor or (get_vix_monitor() if VIX_MONITOR_AVAILABLE else None)
        self.last_check = None
        self.event_log = []
        self.load_event_log()
        
    def load_event_log(self):
        """Load circuit breaker events from file"""
        try:
            if os.path.exists(CIRCUIT_BREAKER_LOG):
                with open(CIRCUIT_BREAKER_LOG, 'r') as f:
                    data = json.load(f)
                    self.event_log = data.get('events', [])[-100:]  # Keep last 100
                    logger.info(f"📂 Loaded {len(self.event_log)} circuit breaker events")
        except Exception as e:
            logger.error(f"❌ Error loading event log: {e}")
            
    def save_event_log(self):
        """Save circuit breaker events to file"""
        try:
            os.makedirs(os.path.dirname(CIRCUIT_BREAKER_LOG), exist_ok=True)
            data = {
                'events': self.event_log[-100:],  # Keep last 100
                'count': len(self.event_log),
                'last_updated': datetime.now().isoformat(),
            }
            with open(CIRCUIT_BREAKER_LOG, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Error saving event log: {e}")
            
    def get_current_regime(self) -> Optional[str]:
        """Get current VIX regime"""
        if self.vix_monitor is None:
            logger.error("❌ VIX monitor not available")
            return None
            
        return self.vix_monitor.current_regime
        
    def get_current_vix(self) -> Optional[float]:
        """Get current VIX value"""
        if self.vix_monitor is None:
            return None
        return self.vix_monitor.current_vix
        
    def calculate_position_size_multiplier(self, base_size: float, vix: Optional[float] = None) -> Tuple[float, Dict]:
        """
        Calculate position size multiplier based on current VIX
        
        Args:
            base_size: Base position size (in shares or contracts)
            vix: Optional VIX override (uses current if not provided)
            
        Returns:
            Tuple of (adjusted_size, details_dict)
        """
        if vix is None:
            vix = self.get_current_vix()
            
        if vix is None:
            logger.warning("⚠️  VIX not available, using 100% sizing")
            return (base_size, {
                'reason': 'no_vix_data',
                'base_size': base_size,
                'multiplier': 1.0,
                'adjusted_size': base_size,
                'vix': None,
            })
            
        # Dynamic reduction if VIX > 18
        multiplier = 1.0
        if vix > 18:
            # Reduce by (VIX - 18) * 5% per point above 18
            reduction = (vix - 18) * 0.05
            multiplier = max(0, 1.0 - reduction)
            
        adjusted_size = int(base_size * multiplier)
        
        return (adjusted_size, {
            'reason': 'vix_adjustment',
            'base_size': base_size,
            'vix': vix,
            'multiplier': multiplier,
            'adjusted_size': adjusted_size,
            'reduction_pct': (1 - multiplier) * 100,
        })
        
    def calculate_stop_percent(self, vix: Optional[float] = None) -> Tuple[float, Dict]:
        """
        Calculate stop-loss percentage based on VIX regime
        
        Args:
            vix: Optional VIX override (uses current if not provided)
            
        Returns:
            Tuple of (stop_percent, details_dict)
        """
        regime = self.get_current_regime()
        if regime is None:
            logger.warning("⚠️  Regime not available, using 2.5% stops")
            return (0.025, {'reason': 'no_regime_data', 'stop_percent': 0.025})
            
        config = CIRCUIT_BREAKER_CONFIG.get(regime, CIRCUIT_BREAKER_CONFIG['normal'])
        stop_percent = config['stop_percent']
        
        return (stop_percent, {
            'regime': regime,
            'stop_percent': stop_percent,
            'vix': self.get_current_vix(),
        })
        
    def can_enter_position(self, symbol: str = None) -> Tuple[bool, Dict]:
        """
        Check if trading system should enter new positions
        
        Args:
            symbol: Optional symbol for logging
            
        Returns:
            Tuple of (allowed, reason_dict)
        """
        regime = self.get_current_regime()
        vix = self.get_current_vix()
        
        if regime is None:
            logger.warning("⚠️  Regime not available, allowing entries with caution")
            return (True, {
                'allowed': True,
                'reason': 'no_regime_data',
                'symbol': symbol,
                'vix': vix,
            })
            
        config = CIRCUIT_BREAKER_CONFIG.get(regime, CIRCUIT_BREAKER_CONFIG['normal'])
        allowed = config['allow_entries']
        
        if not allowed:
            alert = f"[ALERT] Circuit breaker BLOCKED entry for {symbol or 'NEW_POSITION'}: {REGIME_NAMES.get(regime, regime)} (VIX={vix})"
            logger.warning(alert)
            self.log_event('entry_blocked', {
                'symbol': symbol,
                'regime': regime,
                'vix': vix,
                'reason': 'circuit_breaker',
            })
            
        return (allowed, {
            'allowed': allowed,
            'regime': regime,
            'vix': vix,
            'symbol': symbol,
            'reason': 'circuit_breaker' if not allowed else 'ok',
        })
        
    def should_close_weak_positions(self) -> Tuple[bool, Dict]:
        """
        Check if system should close weak/losing positions
        Typically triggered in VIX 18-20 (reduced mode)
        
        Returns:
            Tuple of (should_close, reason_dict)
        """
        regime = self.get_current_regime()
        vix = self.get_current_vix()
        
        if regime in ['reduced', 'panic', 'emergency']:
            alert = f"[ALERT] Circuit breaker triggered: {REGIME_NAMES.get(regime, regime)} (VIX={vix}) → closing weak positions"
            logger.warning(alert)
            self.log_event('weak_position_closeout', {
                'regime': regime,
                'vix': vix,
                'reason': 'high_volatility',
            })
            return (True, {
                'should_close': True,
                'regime': regime,
                'vix': vix,
                'reason': 'weak_position_closeout',
                'close_losers': True,
                'close_percent': 0.5 if regime == 'panic' else 0.25,
            })
            
        return (False, {
            'should_close': False,
            'regime': regime,
            'vix': vix,
            'reason': 'normal_trading',
        })
        
    def should_liquidate_all(self) -> Tuple[bool, Dict]:
        """
        Check if emergency liquidation is needed
        Triggered when VIX > 25
        
        Returns:
            Tuple of (should_liquidate, reason_dict)
        """
        regime = self.get_current_regime()
        vix = self.get_current_vix()
        
        if regime == 'emergency':
            alert = f"[ALERT] EMERGENCY LIQUIDATION TRIGGERED: VIX={vix} (> 25) → liquidating all positions"
            logger.critical(alert)
            self.log_event('emergency_liquidation', {
                'regime': regime,
                'vix': vix,
                'reason': 'panic_mode',
            })
            return (True, {
                'should_liquidate': True,
                'regime': regime,
                'vix': vix,
                'reason': 'emergency_liquidation',
                'message': 'VIX exceeded 25 - closing all positions immediately',
            })
            
        return (False, {
            'should_liquidate': False,
            'regime': regime,
            'vix': vix,
        })
        
    def get_entry_adjustment(self, base_size: int, symbol: str = None) -> Dict:
        """
        Get full entry adjustment based on circuit breaker
        Combines position sizing, stop adjustments, and entry permission
        
        Args:
            base_size: Base position size
            symbol: Optional symbol
            
        Returns:
            Dict with full adjustment details
        """
        can_enter, entry_status = self.can_enter_position(symbol)
        adjusted_size, size_details = self.calculate_position_size_multiplier(base_size)
        stop_pct, stop_details = self.calculate_stop_percent()
        
        return {
            'symbol': symbol,
            'allowed': can_enter,
            'base_size': base_size,
            'adjusted_size': adjusted_size if can_enter else 0,
            'size_multiplier': size_details['multiplier'] if 'multiplier' in size_details else 1.0,
            'stop_percent': stop_pct,
            'regime': self.get_current_regime(),
            'vix': self.get_current_vix(),
            'regime_info': REGIME_NAMES.get(self.get_current_regime(), 'Unknown'),
            'size_details': size_details,
            'stop_details': stop_details,
            'entry_status': entry_status,
            'timestamp': datetime.now().isoformat(),
        }
        
    def check_circuit_breaker(self) -> Dict:
        """
        Comprehensive circuit breaker check
        Returns status of all checks
        
        Returns:
            Dict with all circuit breaker checks
        """
        return {
            'regime': self.get_current_regime(),
            'vix': self.get_current_vix(),
            'can_enter': self.can_enter_position()[0],
            'should_close_weak': self.should_close_weak_positions()[0],
            'should_liquidate': self.should_liquidate_all()[0],
            'position_size_mult': CIRCUIT_BREAKER_CONFIG.get(
                self.get_current_regime(),
                CIRCUIT_BREAKER_CONFIG['normal']
            )['position_size_mult'],
            'stop_percent': self.calculate_stop_percent()[0],
            'timestamp': datetime.now().isoformat(),
        }
        
    def log_event(self, event_type: str, details: Dict):
        """Log a circuit breaker event"""
        event = {
            'event_type': event_type,
            'details': details,
            'timestamp': datetime.now().isoformat(),
        }
        self.event_log.append(event)
        self.save_event_log()
        logger.info(f"📝 Circuit breaker event logged: {event_type}")


# Global circuit breaker instance
_circuit_breaker = None
_breaker_lock = threading.Lock()


def get_circuit_breaker(vix_monitor: VIXMonitor = None) -> CircuitBreaker:
    """Get or create global circuit breaker instance"""
    global _circuit_breaker
    if _circuit_breaker is None:
        with _breaker_lock:
            if _circuit_breaker is None:
                _circuit_breaker = CircuitBreaker(vix_monitor)
    return _circuit_breaker


def main():
    """Test circuit breaker"""
    logger.info("🦞 Circuit Breaker Test")
    
    # Create monitor and breaker
    from vix_monitor import VIXMonitor
    monitor = VIXMonitor()
    
    # Update VIX
    vix_update = monitor.update()
    if not vix_update:
        logger.error("❌ Failed to fetch VIX")
        return
        
    logger.info(f"✅ VIX Update: {json.dumps(vix_update, indent=2)}")
    
    # Create circuit breaker
    breaker = CircuitBreaker(monitor)
    
    # Test various checks
    logger.info(f"📊 Can enter position: {breaker.can_enter_position('TEST')[0]}")
    logger.info(f"📊 Should close weak: {breaker.should_close_weak_positions()[0]}")
    logger.info(f"📊 Should liquidate: {breaker.should_liquidate_all()[0]}")
    
    # Test position sizing
    adjustment = breaker.get_entry_adjustment(100, 'AAPL')
    logger.info(f"📊 Entry adjustment: {json.dumps(adjustment, indent=2)}")
    
    # Test circuit breaker status
    status = breaker.check_circuit_breaker()
    logger.info(f"📊 Circuit breaker status: {json.dumps(status, indent=2)}")


if __name__ == '__main__':
    main()
