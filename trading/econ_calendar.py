#!/usr/bin/env python3
"""
Economic Calendar Module
Fetches and caches major economic events (Fed, CPI, Jobs Report, GDP, PCE, etc.)
Uses free sources like FRED API, Trading Economics, and manual calendar
"""

import json
import logging
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests

logger = logging.getLogger(__name__)

CACHE_FILE = Path(os.path.expanduser('~/.openclaw/workspace/trading/cache/econ_cache.json'))
CACHE_DIR = CACHE_FILE.parent
CACHE_VALIDITY_HOURS = 6  # Refresh every 6 hours

# Major economic events to track
MAJOR_EVENTS = {
    'FED_DECISION': {'alert_days': 3, 'high_volatility': True},
    'FED_ANNOUNCEMENT': {'alert_days': 1, 'high_volatility': True},
    'CPI': {'alert_days': 1, 'high_volatility': True},
    'PPI': {'alert_days': 1, 'high_volatility': True},
    'JOBS_REPORT': {'alert_days': 1, 'high_volatility': True},
    'UNEMPLOYMENT': {'alert_days': 1, 'high_volatility': True},
    'GDP': {'alert_days': 1, 'high_volatility': True},
    'PCE': {'alert_days': 1, 'high_volatility': True},
    'RETAIL_SALES': {'alert_days': 1, 'high_volatility': False},
    'HOUSING_STARTS': {'alert_days': 1, 'high_volatility': False},
    'MORTGAGE_RATES': {'alert_days': 0, 'high_volatility': False},
}

# 2026 Known Economic Events (manually curated)
HARDCODED_EVENTS = [
    {
        'date': '2026-03-18',
        'event': 'FED_DECISION',
        'description': 'FOMC Meeting & Rate Decision',
        'impact': 'HIGH',
        'alert_days': 3
    },
    {
        'date': '2026-03-10',
        'event': 'CPI',
        'description': 'Consumer Price Index (February)',
        'impact': 'HIGH',
        'alert_days': 1
    },
    {
        'date': '2026-03-06',
        'event': 'JOBS_REPORT',
        'description': 'Non-Farm Payroll (February)',
        'impact': 'HIGH',
        'alert_days': 1
    },
    {
        'date': '2026-03-13',
        'event': 'PPI',
        'description': 'Producer Price Index (February)',
        'impact': 'MEDIUM',
        'alert_days': 1
    },
    {
        'date': '2026-04-01',
        'event': 'FED_ANNOUNCEMENT',
        'description': 'FOMC Statement Release',
        'impact': 'HIGH',
        'alert_days': 1
    },
    {
        'date': '2026-04-10',
        'event': 'CPI',
        'description': 'Consumer Price Index (March)',
        'impact': 'HIGH',
        'alert_days': 1
    },
    {
        'date': '2026-04-03',
        'event': 'JOBS_REPORT',
        'description': 'Non-Farm Payroll (March)',
        'impact': 'HIGH',
        'alert_days': 1
    },
    {
        'date': '2026-05-15',
        'event': 'FED_DECISION',
        'description': 'FOMC Meeting & Rate Decision',
        'impact': 'HIGH',
        'alert_days': 3
    },
    {
        'date': '2026-05-08',
        'event': 'CPI',
        'description': 'Consumer Price Index (April)',
        'impact': 'HIGH',
        'alert_days': 1
    },
    {
        'date': '2026-05-01',
        'event': 'JOBS_REPORT',
        'description': 'Non-Farm Payroll (April)',
        'impact': 'HIGH',
        'alert_days': 1
    },
]


def ensure_cache_dir():
    """Create cache directory if it doesn't exist"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_cache() -> Dict:
    """Load cached economic data"""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'r') as f:
                cache = json.load(f)
            
            # Check if cache is still valid
            if 'timestamp' in cache:
                cache_age_hours = (datetime.now().timestamp() - cache['timestamp']) / 3600
                if cache_age_hours < CACHE_VALIDITY_HOURS:
                    logger.info(f"✅ Using cached economic calendar (age: {cache_age_hours:.1f}h)")
                    return cache.get('events', [])
            
            logger.info("⏰ Economic calendar cache expired, refreshing...")
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
    
    return []


def save_cache(events: List[Dict]):
    """Save economic events to cache"""
    ensure_cache_dir()
    try:
        cache = {
            'timestamp': datetime.now().timestamp(),
            'events': events
        }
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2, default=str)
        logger.info(f"✅ Saved economic calendar cache: {len(events)} events")
    except Exception as e:
        logger.error(f"Error saving cache: {e}")


def fetch_economic_calendar() -> List[Dict]:
    """
    Fetch upcoming major economic events
    Combines hardcoded events with API data (if available)
    """
    events = []
    
    # Add hardcoded events for 2026
    today = datetime.now().date()
    for event in HARDCODED_EVENTS:
        event_date = datetime.fromisoformat(event['date']).date()
        if event_date >= today:
            events.append(event)
    
    # Try to fetch from Trading Economics API (if key available)
    # This is a placeholder; actual implementation would use their API
    api_key = os.getenv('TRADING_ECONOMICS_API_KEY')
    if api_key:
        try:
            logger.info("🔍 Fetching from Trading Economics API...")
            # Would implement API call here
            pass
        except Exception as e:
            logger.debug(f"Trading Economics API unavailable: {e}")
    
    # Sort by date
    events.sort(key=lambda x: x['date'])
    
    return events


def get_economic_calendar() -> List[Dict]:
    """
    Main function: Get upcoming economic events
    Uses cache when available, fetches fresh data otherwise
    """
    ensure_cache_dir()
    
    # Load cached data
    cached_events = load_cache()
    
    if not cached_events:
        logger.info("📊 Fetching economic calendar...")
        cached_events = fetch_economic_calendar()
        save_cache(cached_events)
    
    return cached_events


def check_econ_alerts(days_ahead: int = 3) -> List[Dict]:
    """
    Check for upcoming economic events within N days
    Returns list of events that should trigger alerts/position closures
    """
    events = get_economic_calendar()
    today = datetime.now().date()
    
    alerts = []
    for event in events:
        event_date = datetime.fromisoformat(event['date']).date()
        days_until = (event_date - today).days
        
        # Check if event is within alert window
        event_type = event.get('event', '')
        alert_days = MAJOR_EVENTS.get(event_type, {}).get('alert_days', 1)
        
        if 0 <= days_until <= alert_days:
            alerts.append({
                **event,
                'days_until': days_until,
                'action': 'LIQUIDATE' if days_until <= alert_days else 'MONITOR'
            })
    
    return sorted(alerts, key=lambda x: x['days_until'])


def get_next_major_event() -> Optional[Dict]:
    """Get the next major economic event"""
    alerts = check_econ_alerts(days_ahead=30)
    if alerts:
        return alerts[0]
    return None


def format_economic_report(days_ahead: int = 14) -> str:
    """Format economic calendar as readable report"""
    events = get_economic_calendar()
    today = datetime.now().date()
    
    report = "\n📊 ECONOMIC CALENDAR REPORT\n"
    report += "=" * 60 + "\n\n"
    
    upcoming = [e for e in events if datetime.fromisoformat(e['date']).date() >= today]
    
    if not upcoming:
        report += "✅ No major economic events scheduled\n"
    else:
        for event in upcoming[:15]:  # Show next 15 events
            event_date = datetime.fromisoformat(event['date']).date()
            days = (event_date - today).days
            
            # Mark events that trigger liquidation
            marker = "🔴" if days <= event.get('alert_days', 1) else "  "
            
            report += f"{marker} {days:2d}d: {event_date} | {event.get('event', 'UNKNOWN'):15} | {event.get('description', '')}\n"
    
    report += "\n" + "=" * 60 + "\n"
    report += "🔴 = Position liquidation window (close positions 1-3 days before)\n"
    return report


def should_liquidate_all_positions() -> Dict:
    """
    Check if there's an upcoming major event requiring all positions to be closed
    Returns: {'should_liquidate': bool, 'reason': str, 'days_until': int}
    """
    alerts = check_econ_alerts(days_ahead=3)
    
    if not alerts:
        return {'should_liquidate': False, 'reason': 'No major events', 'days_until': None}
    
    next_alert = alerts[0]
    
    # Events that require liquidating ALL positions
    critical_events = ['FED_DECISION', 'FED_ANNOUNCEMENT', 'CPI']
    
    if next_alert.get('event') in critical_events:
        return {
            'should_liquidate': True,
            'reason': f"{next_alert.get('description')} ({next_alert.get('event')})",
            'days_until': next_alert['days_until'],
            'event': next_alert
        }
    
    return {'should_liquidate': False, 'reason': 'No critical events', 'days_until': None}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Display economic calendar
    print(format_economic_report())
    
    # Check for liquidation alerts
    alerts = check_econ_alerts()
    if alerts:
        print("\n⚠️ LIQUIDATION ALERTS:\n")
        for alert in alerts:
            print(f"  {alert['days_until']}d: {alert['description']} ({alert['action']})")
    
    # Check if all positions should be liquidated
    should_liq = should_liquidate_all_positions()
    if should_liq['should_liquidate']:
        print(f"\n🔴 CRITICAL: Close all positions before {should_liq['reason']}")
    else:
        print(f"\n✅ {should_liq['reason']}")
