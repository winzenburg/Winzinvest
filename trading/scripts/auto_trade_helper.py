#!/usr/bin/env python3
"""
Auto-trade helper: Posts screener results to webhook listener
Runs during trading hours, auto-approves orders that pass filters
"""
import os
import json
import requests
from pathlib import Path

# Load env
ENV_PATH = Path(__file__).resolve().parents[1] / '.env'
if ENV_PATH.exists():
    for line in ENV_PATH.read_text().split('\n'):
        if '=' in line and not line.startswith('#'):
            key, val = line.split('=', 1)
            os.environ[key.strip()] = val.strip()

SECRET = os.getenv('MOLT_WEBHOOK_SECRET')
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'http://127.0.0.1:5001/webhook')
AUTO_APPROVE = os.getenv('AUTO_APPROVE', 'false').lower() == 'true'


def post_signal(ticker, signal, price, setup_type, stop_loss=None, take_profit=None, notes=''):
    """Post a trading signal to the webhook listener"""
    payload = {
        'secret': SECRET,
        'ticker': ticker,
        'timeframe': '15',
        'signal': signal,
        'price': float(price),
        'setup_type': setup_type,
        'notes': notes
    }
    if stop_loss:
        payload['stop_loss'] = float(stop_loss)
    if take_profit:
        payload['take_profit'] = float(take_profit)
    
    try:
        resp = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        print(f"✅ Signal posted: {ticker} {signal} @ {price}")
        print(f"   Status: {result.get('status')}")
        print(f"   ID: {result.get('id')}")
        
        # Auto-approve if enabled
        if AUTO_APPROVE and result.get('status') == 'pending':
            approve_intent(result.get('id'))
        
        return result
    except Exception as e:
        print(f"❌ Failed to post signal: {e}")
        return None


def approve_intent(intent_id):
    """Auto-approve a pending intent"""
    if not intent_id:
        return
    
    approve_url = 'http://127.0.0.1:5001/approve'
    payload = {'secret': SECRET, 'id': intent_id}
    
    try:
        resp = requests.post(approve_url, json=payload, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        print(f"✅ Auto-approved: {intent_id}")
        print(f"   Result: {result.get('message')}")
        return result
    except Exception as e:
        print(f"❌ Auto-approve failed: {e}")
        return None


if __name__ == '__main__':
    # Test
    import sys
    if len(sys.argv) < 4:
        print("Usage: auto_trade_helper.py TICKER SIGNAL PRICE [SETUP_TYPE] [STOP] [TARGET]")
        print("Example: auto_trade_helper.py AAPL buy 175.50 swing_fast_9_13_50 170 182")
        sys.exit(1)
    
    ticker = sys.argv[1]
    signal = sys.argv[2]
    price = sys.argv[3]
    setup = sys.argv[4] if len(sys.argv) > 4 else 'swing_fast_9_13_50'
    stop = sys.argv[5] if len(sys.argv) > 5 else None
    target = sys.argv[6] if len(sys.argv) > 6 else None
    
    result = post_signal(ticker, signal, price, setup, stop, target, 'Auto-trade test')
    print(json.dumps(result, indent=2))
