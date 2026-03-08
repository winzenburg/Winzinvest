#!/usr/bin/env python3
"""
Earnings Calendar Module
Fetches and caches earnings dates for holdings using yfinance and alternative sources
"""

import json
import logging
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import yfinance as yf
import requests

logger = logging.getLogger(__name__)

CACHE_FILE = Path(os.path.expanduser('~/.openclaw/workspace/trading/cache/earnings_cache.json'))
CACHE_DIR = CACHE_FILE.parent
CACHE_VALIDITY_HOURS = 24  # Refresh cache daily


def ensure_cache_dir():
    """Create cache directory if it doesn't exist"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_cache() -> Dict:
    """Load cached earnings data"""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'r') as f:
                cache = json.load(f)
            
            # Check if cache is still valid
            if 'timestamp' in cache:
                cache_age_hours = (datetime.now().timestamp() - cache['timestamp']) / 3600
                if cache_age_hours < CACHE_VALIDITY_HOURS:
                    logger.info(f"✅ Using cached earnings data (age: {cache_age_hours:.1f}h)")
                    return cache.get('data', {})
            
            logger.info("⏰ Earnings cache expired, refreshing...")
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
    
    return {}


def save_cache(data: Dict):
    """Save earnings data to cache"""
    ensure_cache_dir()
    try:
        cache = {
            'timestamp': datetime.now().timestamp(),
            'data': data
        }
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2, default=str)
        logger.info(f"✅ Saved earnings cache: {len(data)} symbols")
    except Exception as e:
        logger.error(f"Error saving cache: {e}")


def get_earnings_date_yfinance(symbol: str) -> Optional[datetime]:
    """
    Fetch earnings date from yfinance
    Returns next earnings date or None
    """
    try:
        ticker = yf.Ticker(symbol)
        
        # Try to get earnings dates from calendar
        earnings_dates = ticker.calendar
        if earnings_dates is not None and len(earnings_dates) > 0:
            next_earnings = earnings_dates[0]
            if isinstance(next_earnings, datetime):
                return next_earnings
            # If it's a timestamp, convert it
            return pd.Timestamp(next_earnings).to_pydatetime()
        
        return None
    except Exception as e:
        logger.debug(f"Could not fetch earnings for {symbol}: {e}")
        return None


def get_earnings_date_alternative(symbol: str) -> Optional[datetime]:
    """
    Fetch earnings date from alternative source (e.g., Finnhub, if API available)
    Falls back to None if no API key or rate limited
    """
    try:
        # Check for Finnhub API key (free tier available)
        api_key = os.getenv('FINNHUB_API_KEY')
        if not api_key:
            return None
        
        url = f"https://finnhub.io/api/v1/calendar/earnings?symbol={symbol}&token={api_key}"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if 'earningsCalendar' in data and len(data['earningsCalendar']) > 0:
                earnings_date_str = data['earningsCalendar'][0]['date']
                return datetime.strptime(earnings_date_str, '%Y-%m-%d')
        
        return None
    except Exception as e:
        logger.debug(f"Alternative earnings fetch failed for {symbol}: {e}")
        return None


def fetch_earnings_for_symbols(symbols: List[str]) -> Dict[str, Optional[datetime]]:
    """
    Fetch earnings dates for a list of symbols
    Returns dict: {symbol: earnings_date}
    """
    earnings_data = {}
    
    for symbol in symbols:
        logger.info(f"🔍 Fetching earnings for {symbol}...")
        
        # Try yfinance first
        earnings_date = get_earnings_date_yfinance(symbol)
        
        # Try alternative source if yfinance fails
        if not earnings_date:
            earnings_date = get_earnings_date_alternative(symbol)
        
        if earnings_date:
            earnings_data[symbol] = earnings_date.isoformat()
            logger.info(f"  └─ Next earnings: {earnings_date.strftime('%Y-%m-%d')}")
        else:
            logger.warning(f"  └─ No earnings date found")
            earnings_data[symbol] = None
    
    return earnings_data


def get_earnings_calendar(symbols: List[str]) -> Dict[str, Optional[str]]:
    """
    Main function: Get earnings dates for symbols
    Uses cache when available, fetches fresh data otherwise
    """
    ensure_cache_dir()
    
    # Load cached data first
    cached_earnings = load_cache()
    
    # Identify which symbols need fetching (not in cache or cache expired)
    symbols_to_fetch = [s for s in symbols if s not in cached_earnings]
    
    if symbols_to_fetch:
        logger.info(f"📅 Fetching earnings for {len(symbols_to_fetch)} new symbols")
        new_earnings = fetch_earnings_for_symbols(symbols_to_fetch)
        cached_earnings.update(new_earnings)
        save_cache(cached_earnings)
    
    # Return only requested symbols
    return {s: cached_earnings.get(s) for s in symbols}


def check_earnings_alert(symbol: str, earnings_date: Optional[str], days_ahead: int = 2) -> bool:
    """
    Check if symbol has earnings within N days
    Returns True if earnings are approaching (should liquidate)
    """
    if not earnings_date:
        return False
    
    try:
        ed = datetime.fromisoformat(earnings_date).date()
        today = datetime.now().date()
        days_until_earnings = (ed - today).days
        
        return 0 <= days_until_earnings <= days_ahead
    except Exception as e:
        logger.error(f"Error parsing earnings date for {symbol}: {e}")
        return False


def format_earnings_report(earnings_data: Dict[str, Optional[str]]) -> str:
    """Format earnings data as readable report"""
    today = datetime.now().date()
    
    report = "\n📅 EARNINGS CALENDAR REPORT\n"
    report += "=" * 50 + "\n\n"
    
    # Group by days away
    upcoming = {}
    for symbol, earnings_str in earnings_data.items():
        if earnings_str:
            ed = datetime.fromisoformat(earnings_str).date()
            days = (ed - today).days
            if days >= 0:
                if days not in upcoming:
                    upcoming[days] = []
                upcoming[days].append((symbol, ed))
    
    if not upcoming:
        report += "✅ No upcoming earnings in the next 30 days\n"
    else:
        for days in sorted(upcoming.keys())[:10]:  # Show next 10 events
            symbols = [s for s, _ in upcoming[days]]
            date_str = upcoming[days][0][1].strftime('%Y-%m-%d')
            report += f"{days}d: {date_str} - {', '.join(symbols)}\n"
    
    report += "\n" + "=" * 50 + "\n"
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Example usage
    test_symbols = ['AAPL', 'MSFT', 'TSLA', 'NVDA', 'GOOGL']
    earnings = get_earnings_calendar(test_symbols)
    print(format_earnings_report(earnings))
    
    # Test alert logic
    for symbol, date in earnings.items():
        if check_earnings_alert(symbol, date):
            print(f"⚠️ ALERT: {symbol} has earnings within 2 days!")
