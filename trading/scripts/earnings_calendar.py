#!/usr/bin/env python3
"""
Earnings Calendar Module
Fetches earnings dates for symbols and provides blackout periods.
Earnings ±14 days → DO NOT TRADE (high volatility, unpredictable moves)
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

EARNINGS_CACHE_FILE = Path.home() / ".openclaw" / "workspace" / "trading" / "cache" / "earnings_calendar.json"
EARNINGS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

def get_earnings_date(symbol: str, use_cache=True) -> dict:
    """
    Get earnings date for a symbol.
    Returns: { symbol, earnings_date (str YYYY-MM-DD or None), is_blackout (bool) }
    
    Blackout: ±14 days from earnings date (28 days total)
    """
    
    # Try cache first
    if use_cache and EARNINGS_CACHE_FILE.exists():
        try:
            with open(EARNINGS_CACHE_FILE) as f:
                cache = json.load(f)
                if symbol in cache:
                    cached = cache[symbol]
                    # Check if cache is fresh (< 7 days old)
                    cache_date = datetime.fromisoformat(cached.get("cached_at", "2020-01-01"))
                    if datetime.now() - cache_date < timedelta(days=7):
                        return cached
        except Exception as e:
            logger.warning(f"Cache read failed: {e}")
    
    # Fetch from yfinance
    try:
        ticker = yf.Ticker(symbol)
        earnings_date = ticker.info.get("earningsDate")
        
        if earnings_date:
            if isinstance(earnings_date, list) and len(earnings_date) > 0:
                earnings_date = earnings_date[0]
            
            # Convert to datetime if needed
            if isinstance(earnings_date, (int, float)):
                earnings_date = datetime.fromtimestamp(earnings_date).date()
            else:
                earnings_date = pd.to_datetime(earnings_date).date()
            
            earnings_str = earnings_date.strftime("%Y-%m-%d")
        else:
            earnings_str = None
    except Exception as e:
        logger.warning(f"Failed to fetch earnings for {symbol}: {e}")
        earnings_str = None
    
    # Calculate blackout
    is_blackout = False
    if earnings_str:
        try:
            earnings_dt = datetime.strptime(earnings_str, "%Y-%m-%d").date()
            today = datetime.now().date()
            days_until = (earnings_dt - today).days
            # Blackout: ±14 days (so earnings ±28 days total)
            is_blackout = -14 <= days_until <= 14
        except:
            pass
    
    result = {
        "symbol": symbol,
        "earnings_date": earnings_str,
        "is_blackout": is_blackout,
        "cached_at": datetime.now().isoformat(),
    }
    
    # Save to cache
    try:
        with open(EARNINGS_CACHE_FILE) as f:
            cache = json.load(f)
    except:
        cache = {}
    
    cache[symbol] = result
    try:
        with open(EARNINGS_CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")
    
    return result

def check_earnings_blackout(symbol: str) -> bool:
    """
    Quick check: Is this symbol in earnings blackout?
    Returns: True if blackout, False if OK to trade
    """
    earnings = get_earnings_date(symbol)
    return earnings["is_blackout"]

def get_blackout_symbols(symbols: list) -> set:
    """
    Get all symbols currently in earnings blackout.
    Returns: set of symbols to avoid
    """
    blackout = set()
    for symbol in symbols:
        if check_earnings_blackout(symbol):
            blackout.add(symbol)
    return blackout

if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    test_symbols = ["AAPL", "MSFT", "NVDA", "GS", "JPM"]
    for sym in test_symbols:
        result = get_earnings_date(sym)
        print(f"{sym}: earnings={result['earnings_date']}, blackout={result['is_blackout']}")
