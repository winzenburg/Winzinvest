#!/usr/bin/env python3
"""
VIX Monitor Module
Fetches VIX data every 30 minutes during market hours (9:30 AM - 4:00 PM ET)
Tracks VIX trend (rising/falling/stable) and volatility regime
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import requests
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# File paths
VIX_LOG = os.path.expanduser('~/.openclaw/workspace/trading/logs/vix_history.json')
VIX_STATE = os.path.expanduser('~/.openclaw/workspace/trading/logs/vix_state.json')

# VIX Thresholds
VIX_THRESHOLDS = {
    'normal': (0, 15),      # VIX < 15
    'caution': (15, 18),    # 15 <= VIX < 18
    'reduced': (18, 20),    # 18 <= VIX < 20
    'panic': (20, 25),      # 20 <= VIX < 25
    'emergency': (25, 100), # VIX >= 25
}

# Regime names for alerts
REGIME_NAMES = {
    'normal': 'Normal Mode (100% sizing)',
    'caution': 'Caution Mode (80% sizing)',
    'reduced': 'Reduced Mode (50% sizing)',
    'panic': 'Panic Mode (PAUSE entries)',
    'emergency': 'Emergency Mode (liquidate)',
}


class VIXMonitor:
    """Monitors VIX data and tracks volatility regime"""
    
    def __init__(self):
        """Initialize VIX monitor"""
        self.current_vix = None
        self.previous_vix = None
        self.current_regime = None
        self.previous_regime = None
        self.last_fetch_time = None
        self.vix_history = []
        self.regime_history = []
        self.load_state()
        
    def load_state(self):
        """Load VIX state from file"""
        try:
            if os.path.exists(VIX_STATE):
                with open(VIX_STATE, 'r') as f:
                    data = json.load(f)
                    self.current_vix = data.get('current_vix')
                    self.previous_vix = data.get('previous_vix')
                    self.current_regime = data.get('current_regime')
                    self.previous_regime = data.get('previous_regime')
                    self.last_fetch_time = data.get('last_fetch_time')
                    logger.info(f"📂 Loaded VIX state: Current={self.current_vix}, Regime={self.current_regime}")
            
            if os.path.exists(VIX_LOG):
                with open(VIX_LOG, 'r') as f:
                    data = json.load(f)
                    self.vix_history = data.get('history', [])[-100:]  # Keep last 100 readings
                    logger.info(f"📂 Loaded {len(self.vix_history)} historical VIX readings")
        except Exception as e:
            logger.error(f"❌ Error loading state: {e}")
            
    def save_state(self):
        """Save current VIX state to file"""
        try:
            os.makedirs(os.path.dirname(VIX_STATE), exist_ok=True)
            state = {
                'current_vix': self.current_vix,
                'previous_vix': self.previous_vix,
                'current_regime': self.current_regime,
                'previous_regime': self.previous_regime,
                'last_fetch_time': self.last_fetch_time,
                'updated_at': datetime.now().isoformat(),
            }
            with open(VIX_STATE, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Error saving state: {e}")
            
    def save_history(self):
        """Save VIX history to file"""
        try:
            os.makedirs(os.path.dirname(VIX_LOG), exist_ok=True)
            data = {
                'history': self.vix_history,
                'count': len(self.vix_history),
                'last_updated': datetime.now().isoformat(),
            }
            with open(VIX_LOG, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Error saving history: {e}")
            
    def fetch_vix_yfinance(self) -> Optional[float]:
        """
        Fetch VIX from yfinance
        Fallback method if direct API fails
        """
        try:
            import yfinance as yf
            vix_data = yf.Ticker("^VIX")
            hist = vix_data.history(period="1d")
            if not hist.empty:
                vix_price = float(hist['Close'].iloc[-1])
                return round(vix_price, 2)
        except Exception as e:
            logger.error(f"❌ yfinance error: {e}")
            
        return None
        
    def fetch_vix_api(self) -> Optional[float]:
        """
        Fetch VIX from API (Alpha Vantage or similar)
        """
        try:
            # Try using yfinance first (most reliable)
            import yfinance as yf
            vix_data = yf.Ticker("^VIX")
            current = vix_data.info.get('currentPrice')
            if current:
                return round(float(current), 2)
            
            # Fallback to history
            hist = vix_data.history(period="1d")
            if not hist.empty:
                return round(float(hist['Close'].iloc[-1]), 2)
                
        except ImportError:
            logger.warning("⚠️  yfinance not installed, trying HTTP fallback")
            
        # HTTP fallback: CBOE data (public, no auth required)
        try:
            # Use CBOE's public endpoint
            response = requests.get(
                'https://www.cboe.com/us/equities/market_statistics/historical_data/VIX/json/',
                timeout=10,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            
            if response.status_code == 200:
                data = response.json()
                # Extract most recent VIX value
                if data and 'data' in data and len(data['data']) > 0:
                    vix_value = float(data['data'][0]['close'])
                    return round(vix_value, 2)
        except Exception as e:
            logger.error(f"❌ CBOE API error: {e}")
            
        return None
        
    def fetch_vix(self) -> Optional[float]:
        """
        Fetch current VIX value
        
        Returns:
            VIX value or None if fetch failed
        """
        try:
            vix = self.fetch_vix_api()
            if vix is None:
                vix = self.fetch_vix_yfinance()
                
            if vix is not None:
                logger.info(f"📊 VIX fetched: {vix}")
                return vix
            else:
                logger.error("❌ Failed to fetch VIX from all sources")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error fetching VIX: {e}")
            return None
            
    def get_regime(self, vix_value: float) -> str:
        """
        Determine volatility regime based on VIX level
        
        Args:
            vix_value: Current VIX value
            
        Returns:
            Regime name: 'normal', 'caution', 'reduced', 'panic', 'emergency'
        """
        for regime, (min_vix, max_vix) in VIX_THRESHOLDS.items():
            if min_vix <= vix_value < max_vix:
                return regime
        return 'emergency'  # VIX >= 25
        
    def get_trend(self) -> str:
        """
        Determine if VIX is rising, falling, or stable
        
        Returns:
            'rising', 'falling', or 'stable'
        """
        if self.current_vix is None or self.previous_vix is None:
            return 'unknown'
            
        diff = self.current_vix - self.previous_vix
        
        if diff > 0.5:  # Rising if change > 0.5 points
            return 'rising'
        elif diff < -0.5:  # Falling if change < -0.5 points
            return 'falling'
        else:
            return 'stable'
            
    def update(self) -> Dict:
        """
        Update VIX data and regime
        
        Returns:
            Dict with update info: {
                'vix': float,
                'previous_vix': float,
                'regime': str,
                'previous_regime': str,
                'trend': str,
                'regime_changed': bool,
                'timestamp': str,
                'alert_messages': [str, ...]
            }
        """
        vix = self.fetch_vix()
        if vix is None:
            return None
            
        # Update values
        self.previous_vix = self.current_vix
        self.current_vix = vix
        self.previous_regime = self.current_regime
        self.current_regime = self.get_regime(vix)
        self.last_fetch_time = datetime.now().isoformat()
        
        # Record in history
        history_entry = {
            'vix': vix,
            'regime': self.current_regime,
            'timestamp': self.last_fetch_time,
        }
        self.vix_history.append(history_entry)
        
        # Keep last 100 readings
        if len(self.vix_history) > 100:
            self.vix_history = self.vix_history[-100:]
            
        # Save state
        self.save_state()
        self.save_history()
        
        # Build alert messages
        alerts = []
        regime_changed = self.previous_regime != self.current_regime
        
        if regime_changed and self.previous_regime is not None:
            alerts.append(
                f"[ALERT] VIX regime changed: {REGIME_NAMES.get(self.previous_regime, self.previous_regime)} "
                f"→ {REGIME_NAMES.get(self.current_regime, self.current_regime)}"
            )
            
        trend = self.get_trend()
        if trend == 'rising':
            alerts.append(f"[WARN] VIX rising: {self.previous_vix} → {self.current_vix}")
        elif trend == 'falling':
            alerts.append(f"[INFO] VIX falling: {self.previous_vix} → {self.current_vix}")
            
        return {
            'vix': vix,
            'previous_vix': self.previous_vix,
            'regime': self.current_regime,
            'previous_regime': self.previous_regime,
            'trend': trend,
            'regime_changed': regime_changed,
            'timestamp': self.last_fetch_time,
            'alert_messages': alerts,
        }
        
    def is_market_hours(self) -> bool:
        """
        Check if current time is within market hours
        Market hours: 9:30 AM - 4:00 PM ET, Monday-Friday
        """
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
        
    def get_status(self) -> Dict:
        """Get current VIX status"""
        return {
            'current_vix': self.current_vix,
            'previous_vix': self.previous_vix,
            'regime': self.current_regime,
            'trend': self.get_trend() if self.current_vix and self.previous_vix else 'unknown',
            'last_fetch': self.last_fetch_time,
            'history_count': len(self.vix_history),
            'regime_info': REGIME_NAMES.get(self.current_regime, 'Unknown'),
        }


# Global monitor instance
_vix_monitor = None
_monitor_lock = threading.Lock()


def get_vix_monitor() -> VIXMonitor:
    """Get or create global VIX monitor instance"""
    global _vix_monitor
    if _vix_monitor is None:
        with _monitor_lock:
            if _vix_monitor is None:
                _vix_monitor = VIXMonitor()
    return _vix_monitor


def main():
    """Test VIX monitor"""
    monitor = VIXMonitor()
    
    logger.info("🦞 VIX Monitor Test")
    
    result = monitor.update()
    if result:
        logger.info(f"✅ VIX Update: {json.dumps(result, indent=2)}")
        logger.info(f"📊 Status: {json.dumps(monitor.get_status(), indent=2)}")
    else:
        logger.error("❌ Failed to fetch VIX")


if __name__ == '__main__':
    main()
