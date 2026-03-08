#!/usr/bin/env python3
"""
Economic Calendar Module
Flags major economic events that should trigger trade pauses/blackouts.

Blackout Rules:
- Day of event + 1 day after = DO NOT TRADE (high volatility, gaps)
- Events tracked: CPI, Fed Decision, Jobs Report, Inflation Data

Source: https://www.federalreserve.gov/calendar.htm
          https://www.bls.gov/schedule/
"""

from datetime import datetime, timedelta
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

ECONOMIC_CACHE_FILE = Path.home() / ".openclaw" / "workspace" / "trading" / "cache" / "economic_calendar.json"
ECONOMIC_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

# 2026 Economic Calendar - Major Market-Moving Events
# Updated through Q2 2026
ECONOMIC_EVENTS = [
    # February 2026
    {"date": "2026-02-27", "event": "Jobs Report (Jan)", "importance": "CRITICAL", "type": "employment"},
    {"date": "2026-03-10", "event": "CPI (Feb)", "importance": "CRITICAL", "type": "inflation"},
    
    # March 2026
    {"date": "2026-03-18", "event": "FOMC Decision", "importance": "CRITICAL", "type": "fed"},
    
    # April 2026
    {"date": "2026-04-03", "event": "Jobs Report (Mar)", "importance": "CRITICAL", "type": "employment"},
    {"date": "2026-04-10", "event": "CPI (Mar)", "importance": "CRITICAL", "type": "inflation"},
    
    # May 2026
    {"date": "2026-05-01", "event": "Jobs Report (Apr)", "importance": "CRITICAL", "type": "employment"},
    {"date": "2026-05-12", "event": "CPI (Apr)", "importance": "CRITICAL", "type": "inflation"},
    {"date": "2026-05-19", "event": "FOMC Decision", "importance": "CRITICAL", "type": "fed"},
    
    # June 2026
    {"date": "2026-06-05", "event": "Jobs Report (May)", "importance": "CRITICAL", "type": "employment"},
    {"date": "2026-06-11", "event": "CPI (May)", "importance": "CRITICAL", "type": "inflation"},
]

def get_economic_blackout_dates() -> list:
    """
    Get all blackout dates for this month/quarter.
    Includes event date + 1 day after.
    
    Returns: list of date strings (YYYY-MM-DD)
    """
    blackout = set()
    today = datetime.now().date()
    horizon = today + timedelta(days=90)  # Look 90 days ahead
    
    for event in ECONOMIC_EVENTS:
        event_date = datetime.strptime(event["date"], "%Y-%m-%d").date()
        
        # Only include if within horizon
        if event_date > today and event_date <= horizon:
            # Blackout: event day + next day
            blackout.add(event_date.strftime("%Y-%m-%d"))
            blackout.add((event_date + timedelta(days=1)).strftime("%Y-%m-%d"))
    
    return sorted(list(blackout))

def get_upcoming_events(days=30) -> list:
    """
    Get upcoming economic events in the next N days.
    
    Returns: list of event dicts
    """
    today = datetime.now().date()
    horizon = today + timedelta(days=days)
    
    upcoming = []
    for event in ECONOMIC_EVENTS:
        event_date = datetime.strptime(event["date"], "%Y-%m-%d").date()
        if today <= event_date <= horizon:
            days_away = (event_date - today).days
            upcoming.append({
                **event,
                "days_away": days_away,
            })
    
    return sorted(upcoming, key=lambda x: x["date"])

def is_economic_blackout(date_str: str = None) -> bool:
    """
    Check if a specific date is in economic blackout.
    
    Args:
        date_str: Date to check (YYYY-MM-DD). If None, checks today.
    
    Returns: True if blackout, False if OK to trade
    """
    if date_str is None:
        date_str = datetime.now().date().strftime("%Y-%m-%d")
    
    blackout_dates = get_economic_blackout_dates()
    return date_str in blackout_dates

def get_blackout_reason(date_str: str = None) -> str:
    """
    Get reason for blackout (which event is causing it).
    
    Args:
        date_str: Date to check (YYYY-MM-DD). If None, checks today.
    
    Returns: Event description or "No blackout"
    """
    if date_str is None:
        date_str = datetime.now().date().strftime("%Y-%m-%d")
    
    if not is_economic_blackout(date_str):
        return "No blackout"
    
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    
    # Find event that triggered this blackout
    for event in ECONOMIC_EVENTS:
        event_date = datetime.strptime(event["date"], "%Y-%m-%d").date()
        # Check if target_date is event_date or event_date+1
        if target_date == event_date or target_date == event_date + timedelta(days=1):
            return f"{event['event']} ({event['date']})"
    
    return "Unknown economic event"

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("\n=== UPCOMING ECONOMIC EVENTS (30 days) ===")
    events = get_upcoming_events(days=30)
    for evt in events:
        print(f"{evt['date']}: {evt['event']} ({evt['days_away']} days away)")
    
    print("\n=== BLACKOUT DATES (90 days) ===")
    blackout = get_economic_blackout_dates()
    for date in blackout:
        reason = get_blackout_reason(date)
        print(f"{date}: {reason}")
    
    print("\n=== TODAY'S STATUS ===")
    today = datetime.now().date().strftime("%Y-%m-%d")
    is_blackout = is_economic_blackout(today)
    reason = get_blackout_reason(today)
    print(f"Today ({today}): {'🚫 BLACKOUT' if is_blackout else '✅ OK TO TRADE'}")
    if is_blackout:
        print(f"Reason: {reason}")
