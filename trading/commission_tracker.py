#!/usr/bin/env python3
"""
Commission Tracking Module
Tracks commissions paid on all fills
Provides weekly and aggregated commission reports
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
COMMISSION_LOG = os.path.join(LOGS_DIR, 'commission_tracker.jsonl')


class CommissionTracker:
    """Tracks trading commissions"""
    
    def __init__(self, log_file: str = COMMISSION_LOG):
        """Initialize commission tracker"""
        self.log_file = log_file
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    def record_fill(self, symbol: str, qty: float, price: float, 
                   commission: float, timestamp: Optional[str] = None) -> Dict:
        """
        Record a fill with commission
        
        Args:
            symbol: Stock symbol
            qty: Quantity filled
            price: Fill price
            commission: Commission paid
            timestamp: Fill timestamp (auto-generated if None)
            
        Returns:
            Fill record
        """
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        record = {
            'timestamp': timestamp,
            'symbol': symbol,
            'qty': qty,
            'price': price,
            'commission': commission,
            'notional_value': qty * price
        }
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(record) + '\n')
            
            logger.info(f"✅ Recorded fill: {symbol} {qty}@${price} (commission: ${commission:.2f})")
            return record
            
        except Exception as e:
            logger.error(f"❌ Error recording fill: {e}")
            return record
    
    def get_all_fills(self) -> List[Dict]:
        """Get all recorded fills"""
        fills = []
        
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            fills.append(json.loads(line))
        except Exception as e:
            logger.error(f"Error reading commission log: {e}")
        
        return fills
    
    def total_commissions(self) -> float:
        """Get total commissions paid"""
        fills = self.get_all_fills()
        return sum(f.get('commission', 0) for f in fills)
    
    def avg_commission_per_trade(self) -> float:
        """Get average commission per fill"""
        fills = self.get_all_fills()
        
        if not fills:
            return 0.0
        
        commissions = [f.get('commission', 0) for f in fills]
        return statistics.mean(commissions)
    
    def commission_by_symbol(self) -> Dict[str, Dict]:
        """Get commission breakdown by symbol"""
        fills = self.get_all_fills()
        breakdown = {}
        
        for fill in fills:
            symbol = fill.get('symbol')
            commission = fill.get('commission', 0)
            
            if symbol not in breakdown:
                breakdown[symbol] = {
                    'symbol': symbol,
                    'fill_count': 0,
                    'total_commission': 0,
                    'avg_commission': 0,
                    'total_notional': 0
                }
            
            breakdown[symbol]['fill_count'] += 1
            breakdown[symbol]['total_commission'] += commission
            breakdown[symbol]['total_notional'] += fill.get('notional_value', 0)
        
        # Calculate averages
        for symbol in breakdown:
            count = breakdown[symbol]['fill_count']
            breakdown[symbol]['avg_commission'] = (
                breakdown[symbol]['total_commission'] / count if count > 0 else 0
            )
        
        return breakdown
    
    def commission_as_pct_of_notional(self) -> float:
        """Get average commission as percentage of notional value"""
        fills = self.get_all_fills()
        
        if not fills:
            return 0.0
        
        total_commission = sum(f.get('commission', 0) for f in fills)
        total_notional = sum(f.get('notional_value', 0) for f in fills)
        
        if total_notional == 0:
            return 0.0
        
        return (total_commission / total_notional) * 100
    
    def weekly_summary(self, days_back: int = 7) -> Dict:
        """Get weekly commission summary"""
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
                'total_commission': 0,
                'avg_commission': 0,
                'note': 'No fills in period'
            }
        
        commissions = [f.get('commission', 0) for f in weekly_fills]
        
        return {
            'period_days': days_back,
            'period_end': datetime.now().isoformat(),
            'fill_count': len(weekly_fills),
            'total_commission': sum(commissions),
            'avg_commission': statistics.mean(commissions),
            'min_commission': min(commissions),
            'max_commission': max(commissions),
            'median_commission': statistics.median(commissions),
            'total_notional': sum(f.get('notional_value', 0) for f in weekly_fills),
            'commission_pct': (sum(commissions) / 
                             sum(f.get('notional_value', 0) for f in weekly_fills) * 100
                             if sum(f.get('notional_value', 0) for f in weekly_fills) > 0 
                             else 0)
        }
    
    def print_summary(self):
        """Print commission summary"""
        total_commission = self.total_commissions()
        avg_commission = self.avg_commission_per_trade()
        
        fills = self.get_all_fills()
        fill_count = len(fills)
        
        print("\n" + "="*70)
        print("COMMISSION SUMMARY")
        print("="*70)
        print(f"Total fills: {fill_count}")
        print(f"Total commissions: ${total_commission:.2f}")
        
        if fill_count > 0:
            print(f"Avg commission per fill: ${avg_commission:.2f}")
            print(f"Commission as % of notional: {self.commission_as_pct_of_notional():.4f}%")
        
        # Weekly summary
        weekly = self.weekly_summary(days_back=7)
        if weekly.get('fill_count', 0) > 0:
            print(f"\nLast 7 days:")
            print(f"  Fills: {weekly['fill_count']}")
            print(f"  Total: ${weekly['total_commission']:.2f}")
            print(f"  Avg: ${weekly['avg_commission']:.2f}")
        
        # By symbol
        by_symbol = self.commission_by_symbol()
        if by_symbol:
            print(f"\nBy symbol (top 10 by commission):")
            print("-"*70)
            sorted_symbols = sorted(by_symbol.items(), 
                                   key=lambda x: x[1]['total_commission'], 
                                   reverse=True)[:10]
            
            for symbol, data in sorted_symbols:
                print(f"  {symbol:6s} | Fills: {data['fill_count']:3d} | "
                      f"Total: ${data['total_commission']:8.2f} | "
                      f"Avg: ${data['avg_commission']:.2f}")
        
        print("="*70 + "\n")


if __name__ == '__main__':
    tracker = CommissionTracker()
    
    # Test recording a fill
    # tracker.record_fill('AAPL', 100, 150.50, 2.50)
    
    # Print summary
    tracker.print_summary()
