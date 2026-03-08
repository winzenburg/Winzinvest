#!/usr/bin/env python3
"""
Performance Dashboard - Track win rate, expectancy, and key metrics
"""
import os, json, sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

TRADING_DIR = Path(__file__).resolve().parents[1]
LOGS_DIR = TRADING_DIR / 'logs'

def get_all_trades():
    """Load all executed trades from logs"""
    if not LOGS_DIR.exists():
        return []
    
    trades = []
    for log_file in LOGS_DIR.glob('*.json'):
        if log_file.name.startswith('rejected-'):
            continue  # Skip rejected trades
        
        try:
            with open(log_file) as f:
                data = json.load(f)
                intent = data.get('intent', {})
                result = data.get('result', '')
                
                # Only include stock trades (not options for now)
                if not intent.get('option_type'):
                    ts = intent.get('ts', 0)
                    trade_date = datetime.fromtimestamp(ts / 1000) if ts else None
                    
                    trades.append({
                        'id': intent.get('id'),
                        'date': trade_date,
                        'ticker': intent.get('ticker'),
                        'side': intent.get('signal') or intent.get('side'),
                        'entry': float(intent.get('price') or intent.get('entry') or 0),
                        'stop': float(intent.get('stop_loss') or intent.get('stop') or 0),
                        'target': float(intent.get('take_profit') or intent.get('tp1') or 0),
                        'metrics': intent.get('metrics', {}),
                        'result': result
                    })
        except Exception:
            continue
    
    return sorted(trades, key=lambda x: x['date'] if x['date'] else datetime.min)

def calculate_r_ratio(entry, stop, exit_price, side):
    """Calculate R-ratio (reward/risk) for a trade"""
    if side.lower() in ('long', 'buy', 'entry'):
        risk = entry - stop
        reward = exit_price - entry
    else:  # short
        risk = stop - entry
        reward = entry - exit_price
    
    return reward / risk if risk > 0 else 0

def analyze_performance(trades, days=None):
    """
    Analyze trading performance
    Returns metrics dict
    """
    if days:
        cutoff = datetime.now() - timedelta(days=days)
        trades = [t for t in trades if t['date'] and t['date'] >= cutoff]
    
    if not trades:
        return None
    
    # TODO: We need to track exits to calculate actual P&L
    # For now, calculate potential metrics based on entry/stop/target
    
    total_trades = len(trades)
    
    # Calculate potential R-ratio per trade
    potential_r_ratios = []
    for t in trades:
        if t['entry'] and t['stop'] and t['target']:
            # Assume all reached target (optimistic)
            r = calculate_r_ratio(t['entry'], t['stop'], t['target'], t['side'])
            potential_r_ratios.append(r)
    
    avg_r = sum(potential_r_ratios) / len(potential_r_ratios) if potential_r_ratios else 0
    
    # Group by ticker
    by_ticker = defaultdict(int)
    for t in trades:
        by_ticker[t['ticker']] += 1
    
    # Most traded
    most_traded = sorted(by_ticker.items(), key=lambda x: x[1], reverse=True)[:5]
    
    return {
        'total_trades': total_trades,
        'period_days': days or 'all time',
        'avg_potential_r': avg_r,
        'most_traded': most_traded,
        'first_trade': trades[0]['date'].strftime('%Y-%m-%d') if trades[0]['date'] else 'Unknown',
        'last_trade': trades[-1]['date'].strftime('%Y-%m-%d') if trades[-1]['date'] else 'Unknown',
        # Placeholders until we track exits
        'win_rate': '⏳ Need closed trades',
        'avg_win': '⏳ Need closed trades',
        'avg_loss': '⏳ Need closed trades',
        'expectancy': '⏳ Need closed trades',
        'total_pnl': '⏳ Need closed trades'
    }

def print_dashboard(metrics):
    """Pretty print dashboard"""
    if not metrics:
        print("📊 No trades found")
        return
    
    print("=" * 60)
    print(" " * 18 + "PERFORMANCE DASHBOARD")
    print("=" * 60)
    print(f"\n📈 TRADING ACTIVITY")
    print(f"  Total trades: {metrics['total_trades']}")
    print(f"  Period: {metrics['period_days']}")
    print(f"  First trade: {metrics['first_trade']}")
    print(f"  Last trade: {metrics['last_trade']}")
    
    print(f"\n📊 PERFORMANCE METRICS")
    print(f"  Win rate: {metrics['win_rate']}")
    print(f"  Avg R-ratio (potential): {metrics['avg_potential_r']:.2f}")
    print(f"  Avg win: {metrics['avg_win']}")
    print(f"  Avg loss: {metrics['avg_loss']}")
    print(f"  Expectancy: {metrics['expectancy']}")
    print(f"  Total P&L: {metrics['total_pnl']}")
    
    print(f"\n🏆 MOST TRADED")
    for ticker, count in metrics['most_traded']:
        print(f"  {ticker}: {count} trades")
    
    print("\n" + "=" * 60)
    print("💡 Note: Win rate and P&L require closed position tracking")
    print("   (coming soon via IB positions API integration)")
    print("=" * 60)

def main():
    trades = get_all_trades()
    
    # Overall stats
    print_dashboard(analyze_performance(trades))
    
    # Last 30 days
    print("\n📅 LAST 30 DAYS:")
    recent_metrics = analyze_performance(trades, days=30)
    if recent_metrics:
        print(f"  Trades: {recent_metrics['total_trades']}")
        print(f"  Avg R-ratio: {recent_metrics['avg_potential_r']:.2f}")

if __name__ == '__main__':
    main()
