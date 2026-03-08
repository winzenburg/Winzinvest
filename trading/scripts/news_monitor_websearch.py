#!/usr/bin/env python3
"""
Web-search based news monitoring for market-moving events
Uses OpenClaw's web_search capability to monitor Trump, Fed, and economic news
"""
import json
import sys
import time
from pathlib import Path
from datetime import datetime

# This will be called by OpenClaw AI which has web_search capability
# When run standalone, it provides structure for OpenClaw to follow

TRADING_DIR = Path(__file__).resolve().parents[1]
NEWS_LOG = TRADING_DIR / 'logs' / 'news_events.json'
ALERT_DIR = TRADING_DIR / 'notifications'
NEWS_LOG.parent.mkdir(exist_ok=True)
ALERT_DIR.mkdir(exist_ok=True)

# Search queries to monitor
SEARCHES = {
    'trump_tariff': {
        'query': 'Trump tariff trade war site:twitter.com OR site:x.com',
        'keywords': ['tariff', 'trade war', 'china', 'imports', 'exports'],
        'impact': 'HIGH',
        'action': 'DEFENSIVE'
    },
    'trump_fed': {
        'query': 'Trump Federal Reserve Powell site:twitter.com OR site:x.com',
        'keywords': ['fed', 'powell', 'interest rate', 'inflation'],
        'impact': 'HIGH',
        'action': 'MONITOR'
    },
    'fed_announcement': {
        'query': 'Federal Reserve FOMC announcement rate decision',
        'keywords': ['rate', 'hike', 'cut', 'decision', 'fomc'],
        'impact': 'HIGH',
        'action': 'PAUSE_ENTRIES'
    },
    'economic_data': {
        'query': 'CPI inflation jobs report unemployment GDP surprise',
        'keywords': ['cpi', 'inflation', 'jobs', 'unemployment', 'gdp'],
        'impact': 'MEDIUM',
        'action': 'MONITOR'
    }
}

def load_news_history():
    """Load previous news events"""
    if NEWS_LOG.exists():
        try:
            return json.loads(NEWS_LOG.read_text())
        except:
            return {'events': [], 'last_check': None}
    return {'events': [], 'last_check': None}


def save_news_event(event):
    """Save a news event"""
    history = load_news_history()
    
    # Check if we've already logged this (dedupe)
    existing = [e for e in history['events'] if e.get('text', '') == event.get('text', '')]
    if existing:
        return False  # Already logged
    
    history['events'].append({
        **event,
        'timestamp': datetime.now().isoformat(),
        'processed': False
    })
    history['last_check'] = datetime.now().isoformat()
    
    # Keep only last 100 events
    history['events'] = history['events'][-100:]
    
    NEWS_LOG.write_text(json.dumps(history, indent=2))
    return True


def create_alert(event):
    """Create an alert file for OpenClaw to notify user"""
    alert_file = ALERT_DIR / f'news_alert_{int(time.time())}.json'
    
    alert = {
        'type': 'NEWS_ALERT',
        'source': event['source'],
        'impact': event['impact'],
        'action': event['action'],
        'text': event['text'][:300],
        'keywords': event['keywords'],
        'timestamp': datetime.now().isoformat(),
        'recommendation': generate_recommendation(event)
    }
    
    alert_file.write_text(json.dumps(alert, indent=2))
    return alert


def generate_recommendation(event):
    """Generate trading recommendation based on news"""
    action = event.get('action', 'MONITOR')
    impact = event.get('impact', 'MEDIUM')
    text = event.get('text', '').lower()
    
    if action == 'DEFENSIVE':
        return {
            'action': 'Tighten stops by 25%, pause new entries for 15 minutes',
            'reason': 'High-impact bearish news detected'
        }
    elif action == 'PAUSE_ENTRIES':
        return {
            'action': 'Pause all new entries for 30 minutes',
            'reason': 'Major announcement - wait for volatility to settle'
        }
    elif 'rate cut' in text or 'stimulus' in text:
        return {
            'action': 'Watch for breakout entries in next 1-2 hours',
            'reason': 'Bullish catalyst detected'
        }
    else:
        return {
            'action': 'Monitor closely, no immediate action needed',
            'reason': 'News noted but not immediately actionable'
        }


def analyze_search_results(search_name, results_text):
    """
    Analyze search results for market-relevant content
    This is a placeholder - OpenClaw AI will do the actual analysis
    """
    search_config = SEARCHES[search_name]
    keywords_found = []
    
    # Check for keywords
    text_lower = results_text.lower()
    for keyword in search_config['keywords']:
        if keyword in text_lower:
            keywords_found.append(keyword)
    
    if not keywords_found:
        return None
    
    # Found relevant news
    event = {
        'source': search_name,
        'text': results_text[:500],  # First 500 chars
        'keywords': keywords_found,
        'impact': search_config['impact'],
        'action': search_config['action']
    }
    
    return event


def get_monitoring_instructions():
    """
    Return instructions for OpenClaw AI to follow during monitoring
    """
    return {
        'schedule': 'Every 5 minutes during trading hours (7:45 AM - 1:45 PM MT)',
        'searches': SEARCHES,
        'process': [
            '1. Run web_search for each query with freshness="pd" (past day)',
            '2. Analyze results for market-moving keywords',
            '3. If keywords found, save event to news log',
            '4. Create alert file in notifications/',
            '5. Notify user via Telegram/chat',
            '6. Take recommended defensive action if needed'
        ],
        'defensive_actions': {
            'HIGH_IMPACT_BEARISH': 'Tighten stops by 25%, pause new entries 15 min',
            'HIGH_IMPACT_BULLISH': 'Watch for breakout setups, increase position size',
            'MAJOR_ANNOUNCEMENT': 'Pause all entries 30 min, monitor volatility',
            'MODERATE_NEWS': 'Note in report, no immediate action'
        }
    }


def check_if_trading_hours():
    """Check if we're in trading hours"""
    from datetime import datetime
    import pytz
    
    mt_tz = pytz.timezone('America/Denver')
    now = datetime.now(mt_tz)
    current_time = now.time()
    
    from datetime import time
    start = time(7, 45)
    end = time(13, 45)
    
    return start <= current_time <= end


if __name__ == '__main__':
    print("""
    ========================================
    News Monitor - Web Search Edition
    ========================================
    
    This script provides the framework for OpenClaw AI
    to monitor market-moving news using web_search.
    
    OpenClaw will:
    1. Run searches every 5 minutes during trading hours
    2. Analyze results for keywords
    3. Create alerts when found
    4. Take defensive actions automatically
    
    Monitoring Instructions:
    """)
    
    instructions = get_monitoring_instructions()
    print(json.dumps(instructions, indent=2))
    
    print("\n✅ Framework ready for OpenClaw to use")
    print("📡 News monitoring will start tomorrow at 7:45 AM MT")
