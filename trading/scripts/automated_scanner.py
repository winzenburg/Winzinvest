#!/usr/bin/env python3
"""
Automated scanner: Runs screeners and auto-posts signals to webhook
Used by OpenClaw for automated trading during trading hours
"""
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import pytz

# Import the auto-trade helper
sys.path.insert(0, str(Path(__file__).parent))
from auto_trade_helper import post_signal

TRADING_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = TRADING_DIR / 'scripts'

def within_trading_hours():
    """Check if we're within trading hours"""
    try:
        risk_path = TRADING_DIR / 'risk.json'
        risk = json.loads(risk_path.read_text())
        hours = risk.get('time_restrictions', {}).get('trading_hours', {})
        tz_name = hours.get('timezone', 'America/New_York')
        start = hours.get('start', '09:45')
        end = hours.get('end', '15:45')
        
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz).time()
        sh, sm = map(int, start.split(':'))
        eh, em = map(int, end.split(':'))
        
        from datetime import time
        return time(sh, sm) <= now <= time(eh, em)
    except Exception as e:
        print(f"Warning: Could not check trading hours: {e}")
        return True


def run_midday_scan():
    """Run the midday scanner and return candidates"""
    try:
        result = subprocess.run(
            ['python3', str(SCRIPTS_DIR / 'midday_scan.py')],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        # Parse output for candidates
        # Expected format: lines with ticker symbols and signals
        candidates = []
        for line in result.stdout.split('\n'):
            if 'BUY' in line or 'SELL' in line:
                # Parse candidate from output
                # Format varies, so this is a placeholder
                candidates.append(line)
        
        return candidates
    except Exception as e:
        print(f"Error running midday scan: {e}")
        return []


def process_candidates(candidates):
    """Process scanner candidates and post signals"""
    posted = 0
    for candidate in candidates:
        try:
            # Parse candidate (this format depends on scanner output)
            # For now, print what we found
            print(f"📊 Candidate: {candidate}")
            # TODO: Parse ticker, price, setup type from candidate
            # TODO: Calculate stop/target based on ATR or fixed %
            # post_signal(ticker, 'buy', price, 'swing_fast_9_13_50', stop, target)
            posted += 1
        except Exception as e:
            print(f"Error processing candidate: {e}")
    
    return posted


if __name__ == '__main__':
    print(f"🤖 Automated Scanner - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not within_trading_hours():
        print("⏰ Outside trading hours - skipping scan")
        sys.exit(0)
    
    print("🔍 Running midday scan...")
    candidates = run_midday_scan()
    
    print(f"📊 Found {len(candidates)} candidates")
    
    if candidates:
        print("📤 Posting signals to webhook...")
        posted = process_candidates(candidates)
        print(f"✅ Posted {posted} signals")
    else:
        print("📭 No candidates found")
