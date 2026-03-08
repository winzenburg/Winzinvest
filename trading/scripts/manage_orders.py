#!/usr/bin/env python3
"""
Order management CLI - for OpenClaw to approve/reject pending orders
"""
import os
import json
import requests
import sys
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parents[1] / '.env'
if ENV_PATH.exists():
    for line in ENV_PATH.read_text().split('\n'):
        if '=' in line and not line.startswith('#'):
            key, val = line.split('=', 1)
            os.environ[key.strip()] = val.strip()

SECRET = os.getenv('MOLT_WEBHOOK_SECRET')
PENDING_DIR = Path(__file__).resolve().parents[1] / 'pending'


def list_pending():
    """List all pending orders"""
    if not PENDING_DIR.exists():
        print("No pending orders")
        return []
    
    pending = []
    for f in PENDING_DIR.glob('*.json'):
        try:
            intent = json.loads(f.read_text())
            pending.append(intent)
        except Exception:
            continue
    
    return pending


def approve_order(intent_id):
    """Approve a pending order"""
    url = 'http://127.0.0.1:5001/approve'
    payload = {'secret': SECRET, 'id': intent_id}
    
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        print(f"✅ Approved: {result.get('message')}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


def reject_order(intent_id):
    """Reject a pending order"""
    url = 'http://127.0.0.1:5001/reject'
    payload = {'secret': SECRET, 'id': intent_id}
    
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        print(f"✅ Rejected: {result.get('message')}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  manage_orders.py list                 - Show pending orders")
        print("  manage_orders.py approve <intent_id>  - Approve order")
        print("  manage_orders.py reject <intent_id>   - Reject order")
        print("  manage_orders.py approve-all          - Approve all pending")
        sys.exit(1)
    
    action = sys.argv[1]
    
    if action == 'list':
        pending = list_pending()
        if not pending:
            print("📭 No pending orders")
        else:
            print(f"📊 {len(pending)} pending orders:\n")
            for intent in pending:
                print(f"  ID: {intent.get('id')}")
                print(f"  Ticker: {intent.get('ticker')}")
                print(f"  Signal: {intent.get('signal')}")
                print(f"  Price: {intent.get('price')}")
                print(f"  Setup: {intent.get('setup')}")
                print(f"  Qty: {intent.get('qty')}")
                print()
    
    elif action == 'approve' and len(sys.argv) > 2:
        intent_id = sys.argv[2]
        approve_order(intent_id)
    
    elif action == 'reject' and len(sys.argv) > 2:
        intent_id = sys.argv[2]
        reject_order(intent_id)
    
    elif action == 'approve-all':
        pending = list_pending()
        print(f"Approving {len(pending)} orders...")
        for intent in pending:
            approve_order(intent.get('id'))
    
    else:
        print("Unknown action")
        sys.exit(1)
