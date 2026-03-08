#!/usr/bin/env python3
"""
Track trading performance and adjust position sizing dynamically
"""
import json
from pathlib import Path
from datetime import datetime, timedelta

TRADING_DIR = Path(__file__).resolve().parents[1]
LOGS_DIR = TRADING_DIR / 'logs'
PERF_FILE = TRADING_DIR / 'performance.json'


def load_performance():
    """Load performance history"""
    if PERF_FILE.exists():
        return json.loads(PERF_FILE.read_text())
    return {
        'trades': [],
        'win_rate': 0.0,
        'avg_rr': 0.0,
        'total_pnl': 0.0,
        'current_position_size': 1,  # Start with 1 share
        'last_updated': None
    }


def save_performance(perf):
    """Save performance data"""
    perf['last_updated'] = datetime.now().isoformat()
    PERF_FILE.write_text(json.dumps(perf, indent=2))


def analyze_recent_trades(days=7):
    """Analyze trades from the last N days"""
    if not LOGS_DIR.exists():
        return []
    
    cutoff = datetime.now() - timedelta(days=days)
    trades = []
    
    for log_file in LOGS_DIR.glob('*.json'):
        try:
            log_data = json.loads(log_file.read_text())
            # Parse trade data from logs
            # This is a placeholder - actual parsing depends on log format
            trades.append(log_data)
        except Exception:
            continue
    
    return trades


def calculate_win_rate(trades):
    """Calculate win rate from trades"""
    if not trades:
        return 0.0
    
    wins = sum(1 for t in trades if t.get('pnl', 0) > 0)
    return (wins / len(trades)) * 100


def calculate_avg_rr(trades):
    """Calculate average reward:risk ratio"""
    if not trades:
        return 0.0
    
    rr_ratios = [t.get('rr_ratio', 0) for t in trades if 'rr_ratio' in t]
    return sum(rr_ratios) / len(rr_ratios) if rr_ratios else 0.0


def determine_position_size(win_rate, avg_rr, total_trades):
    """Dynamically determine position size based on performance"""
    
    # Start conservative
    if total_trades < 10:
        return 1  # Canary mode until we have data
    
    # Scale based on performance
    if win_rate >= 75 and avg_rr >= 2.5:
        return 50  # Crushing it
    elif win_rate >= 65 and avg_rr >= 2.0:
        return 25  # Doing well
    elif win_rate >= 55 and avg_rr >= 1.5:
        return 10  # Profitable
    elif win_rate >= 45:
        return 5   # Slightly profitable
    else:
        return 1   # Back to canary mode


def generate_performance_report():
    """Generate a performance report"""
    perf = load_performance()
    trades = analyze_recent_trades(days=7)
    
    if not trades:
        return "📊 No trades yet - starting fresh!"
    
    total_trades = len(trades)
    win_rate = calculate_win_rate(trades)
    avg_rr = calculate_avg_rr(trades)
    
    report = f"""
📊 **Trading Performance Report**
Period: Last 7 days

**Metrics:**
• Total trades: {total_trades}
• Win rate: {win_rate:.1f}%
• Avg R:R: {avg_rr:.2f}
• Total P&L: ${perf.get('total_pnl', 0):.2f}

**Position Sizing:**
• Current: {perf.get('current_position_size', 1)} shares
• Next level: {determine_position_size(win_rate, avg_rr, total_trades)} shares

**Performance Targets:**
• 55%+ win rate → 10 shares
• 65%+ win rate → 25 shares  
• 75%+ win rate → 50 shares

**Status:** {'🚀 Scaling up!' if win_rate > 55 else '📊 Building track record...'}
"""
    
    return report


if __name__ == '__main__':
    print(generate_performance_report())
