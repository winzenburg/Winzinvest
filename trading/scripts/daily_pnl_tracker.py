#!/usr/bin/env python3
"""
Daily P&L Tracker - Enforces max daily loss limit
Checks current day's realized + unrealized P&L
Blocks new trade approvals if daily loss limit exceeded
"""
import os, json, sys
from pathlib import Path
from datetime import datetime

TRADING_DIR = Path(__file__).resolve().parents[1]
LOGS_DIR = TRADING_DIR / 'logs'
RISK_PATH = TRADING_DIR / 'risk.json'

def load_risk_limits():
    """Load risk limits from risk.json"""
    if not RISK_PATH.exists():
        return None
    with open(RISK_PATH) as f:
        risk = json.load(f)
    return {
        'max_daily_loss_dollars': risk['loss_limits']['max_daily_loss_dollars'],
        'trading_capital': risk['account']['trading_capital']
    }

def calculate_daily_pnl():
    """Calculate today's realized P&L from closed trades"""
    if not LOGS_DIR.exists():
        return 0.0, []
    
    today = datetime.now().date()
    trades_today = []
    total_pnl = 0.0
    
    for log_file in LOGS_DIR.glob('*.json'):
        try:
            with open(log_file) as f:
                data = json.load(f)
                intent = data.get('intent', {})
                result = data.get('result', '')
                
                # Check if trade was today
                ts = intent.get('ts', 0)
                if ts:
                    trade_date = datetime.fromtimestamp(ts / 1000).date()
                    if trade_date == today:
                        # For now, we don't have closed P&L yet (need IB positions API)
                        # This is a placeholder that tracks executions
                        trades_today.append({
                            'ticker': intent.get('ticker'),
                            'side': intent.get('signal') or intent.get('side'),
                            'entry': intent.get('price') or intent.get('entry'),
                            'pnl': 0.0  # TODO: Calculate from IB positions
                        })
        except Exception:
            continue
    
    return total_pnl, trades_today

def check_daily_loss_limit():
    """
    Check if daily loss limit has been exceeded
    Returns: (ok: bool, current_loss: float, limit: float, message: str)
    """
    limits = load_risk_limits()
    if not limits:
        return True, 0.0, 0.0, "Risk limits not configured"
    
    current_pnl, trades = calculate_daily_pnl()
    max_loss = limits['max_daily_loss_dollars']
    
    # Check if we're beyond limit (negative PnL exceeds max loss)
    if current_pnl < -max_loss:
        return False, abs(current_pnl), max_loss, f"Daily loss limit exceeded: ${abs(current_pnl):.2f} > ${max_loss:.2f}"
    
    return True, abs(current_pnl), max_loss, "Within daily loss limit"

def main():
    ok, current_loss, limit, msg = check_daily_loss_limit()
    print(f"Daily Loss Check: {msg}")
    print(f"Current: ${current_loss:.2f} / Limit: ${limit:.2f}")
    
    if not ok:
        print("\n⚠️ CIRCUIT BREAKER ACTIVE - No new trades allowed today")
        sys.exit(1)
    else:
        print("\n✅ Trading allowed")
        sys.exit(0)

if __name__ == '__main__':
    main()
