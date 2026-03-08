#!/usr/bin/env python3
"""
Slippage Analysis Module
Tracks slippage on stop-loss fills
Provides weekly and aggregated slippage reports
"""

import json
import logging
import os
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import statistics

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

WORKSPACE = os.path.expanduser('~/.openclaw/workspace')
TRADING_DIR = os.path.join(WORKSPACE, 'trading')
LOGS_DIR = os.path.join(TRADING_DIR, 'logs')
SLIPPAGE_LOG = os.path.join(LOGS_DIR, 'slippage_tracker.jsonl')


class SlippageTracker:
    """Tracks slippage on stop-loss fills"""
    
    def __init__(self, log_file: str = SLIPPAGE_LOG):
        """Initialize slippage tracker"""
        self.log_file = log_file
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    def record_stop_fill(self, symbol: str, stop_price: float, fill_price: float,
                        qty: float, timestamp: Optional[str] = None) -> Dict:
        """
        Record a stop-loss fill with slippage
        
        Args:
            symbol: Stock symbol
            stop_price: Stop order price
            fill_price: Actual fill price
            qty: Quantity filled
            timestamp: Fill timestamp (auto-generated if None)
            
        Returns:
            Slippage record
        """
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        # Calculate slippage
        slippage = fill_price - stop_price
        slippage_pct = (slippage / stop_price * 100) if stop_price != 0 else 0
        loss_impact = slippage * qty  # Dollar impact
        
        record = {
            'timestamp': timestamp,
            'symbol': symbol,
            'stop_price': stop_price,
            'fill_price': fill_price,
            'qty': qty,
            'slippage': slippage,
            'slippage_pct': slippage_pct,
            'loss_impact': loss_impact,
            'favorable': slippage < 0  # True if fill is better than stop price
        }
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(record) + '\n')
            
            favorable_str = "favorable" if record['favorable'] else "adverse"
            logger.info(f"✅ Recorded stop fill: {symbol} {qty}@${fill_price} "
                       f"(stop: ${stop_price}, slippage: ${slippage:.2f} ({favorable_str}))")
            return record
            
        except Exception as e:
            logger.error(f"❌ Error recording stop fill: {e}")
            return record
    
    def get_all_fills(self) -> List[Dict]:
        """Get all recorded stop fills"""
        fills = []
        
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            fills.append(json.loads(line))
        except Exception as e:
            logger.error(f"Error reading slippage log: {e}")
        
        return fills
    
    def total_slippage(self) -> float:
        """Get total slippage (sum of all loss impacts)"""
        fills = self.get_all_fills()
        return sum(f.get('loss_impact', 0) for f in fills)
    
    def avg_slippage(self) -> float:
        """Get average slippage per fill"""
        fills = self.get_all_fills()
        
        if not fills:
            return 0.0
        
        slippages = [f.get('slippage', 0) for f in fills]
        return statistics.mean(slippages)
    
    def avg_slippage_pct(self) -> float:
        """Get average slippage as percentage"""
        fills = self.get_all_fills()
        
        if not fills:
            return 0.0
        
        slippage_pcts = [f.get('slippage_pct', 0) for f in fills]
        return statistics.mean(slippage_pcts)
    
    def max_slippage(self) -> float:
        """Get maximum slippage"""
        fills = self.get_all_fills()
        
        if not fills:
            return 0.0
        
        slippages = [abs(f.get('slippage', 0)) for f in fills]
        return max(slippages)
    
    def min_slippage(self) -> float:
        """Get minimum slippage (best fill)"""
        fills = self.get_all_fills()
        
        if not fills:
            return 0.0
        
        slippages = [f.get('slippage', 0) for f in fills]
        return min(slippages)
    
    def favorable_fills_count(self) -> int:
        """Count fills better than stop price"""
        fills = self.get_all_fills()
        return sum(1 for f in fills if f.get('favorable', False))
    
    def slippage_by_symbol(self) -> Dict[str, Dict]:
        """Get slippage breakdown by symbol"""
        fills = self.get_all_fills()
        breakdown = {}
        
        for fill in fills:
            symbol = fill.get('symbol')
            slippage = fill.get('slippage', 0)
            
            if symbol not in breakdown:
                breakdown[symbol] = {
                    'symbol': symbol,
                    'fill_count': 0,
                    'total_slippage': 0,
                    'avg_slippage': 0,
                    'max_slippage': 0,
                    'favorable_count': 0
                }
            
            breakdown[symbol]['fill_count'] += 1
            breakdown[symbol]['total_slippage'] += slippage
            breakdown[symbol]['max_slippage'] = max(
                breakdown[symbol]['max_slippage'], 
                abs(slippage)
            )
            
            if fill.get('favorable', False):
                breakdown[symbol]['favorable_count'] += 1
        
        # Calculate averages
        for symbol in breakdown:
            count = breakdown[symbol]['fill_count']
            breakdown[symbol]['avg_slippage'] = (
                breakdown[symbol]['total_slippage'] / count if count > 0 else 0
            )
        
        return breakdown
    
    def weekly_summary(self, days_back: int = 7) -> Dict:
        """Get weekly slippage summary"""
        fills = self.get_all_fills()
        cutoff_time = datetime.now() - timedelta(days=days_back)
        
        weekly_fills = [
            f for f in fills
            if datetime.fromisoformat(f.get('timestamp', '')) >= cutoff_time
        ]
        
        if not weekly_fills:
            return {
                'period_days': days_back,
                'fill_count': 0,
                'total_slippage': 0,
                'avg_slippage': 0,
                'note': 'No fills in period'
            }
        
        slippages = [f.get('slippage', 0) for f in weekly_fills]
        
        return {
            'period_days': days_back,
            'period_end': datetime.now().isoformat(),
            'fill_count': len(weekly_fills),
            'total_slippage': sum(f.get('loss_impact', 0) for f in weekly_fills),
            'avg_slippage': statistics.mean(slippages),
            'avg_slippage_pct': statistics.mean([f.get('slippage_pct', 0) for f in weekly_fills]),
            'max_slippage': max(slippages),
            'min_slippage': min(slippages),
            'favorable_count': sum(1 for f in weekly_fills if f.get('favorable', False))
        }
    
    def print_summary(self):
        """Print slippage summary"""
        fills = self.get_all_fills()
        fill_count = len(fills)
        
        print("\n" + "="*70)
        print("SLIPPAGE SUMMARY")
        print("="*70)
        print(f"Total stop fills: {fill_count}")
        
        if fill_count > 0:
            print(f"Total slippage impact: ${self.total_slippage():.2f}")
            print(f"Avg slippage per fill: ${self.avg_slippage():.2f} ({self.avg_slippage_pct():.4f}%)")
            print(f"Max slippage: ${self.max_slippage():.2f}")
            print(f"Min slippage: ${self.min_slippage():.2f}")
            print(f"Favorable fills: {self.favorable_fills_count()} ({self.favorable_fills_count()/fill_count*100:.1f}%)")
        
        # Weekly summary
        weekly = self.weekly_summary(days_back=7)
        if weekly.get('fill_count', 0) > 0:
            print(f"\nLast 7 days:")
            print(f"  Fills: {weekly['fill_count']}")
            print(f"  Total slippage: ${weekly['total_slippage']:.2f}")
            print(f"  Avg slippage: ${weekly['avg_slippage']:.2f} ({weekly['avg_slippage_pct']:.4f}%)")
            print(f"  Favorable: {weekly['favorable_count']}/{weekly['fill_count']}")
        
        # By symbol
        by_symbol = self.slippage_by_symbol()
        if by_symbol:
            print(f"\nBy symbol (top 10 by total slippage):")
            print("-"*70)
            sorted_symbols = sorted(by_symbol.items(), 
                                   key=lambda x: abs(x[1]['total_slippage']), 
                                   reverse=True)[:10]
            
            for symbol, data in sorted_symbols:
                print(f"  {symbol:6s} | Fills: {data['fill_count']:3d} | "
                      f"Total: ${data['total_slippage']:8.2f} | "
                      f"Avg: ${data['avg_slippage']:7.2f} | "
                      f"Favorable: {data['favorable_count']}")
        
        print("="*70 + "\n")


if __name__ == '__main__':
    tracker = SlippageTracker()
    
    # Test recording a fill
    # tracker.record_stop_fill('AAPL', 145.00, 144.95, 100)  # Favorable
    # tracker.record_stop_fill('TSLA', 250.00, 250.50, 50)   # Adverse
    
    # Print summary
    tracker.print_summary()
