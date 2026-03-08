#!/usr/bin/env python3
"""
Daily Reconciliation Module
Runs daily @ 8:00 PM to compare IB Gateway positions with portfolio.json
Logs discrepancies and generates reconciliation reports
"""

import json
import logging
import os
from typing import Dict, List, Tuple
from datetime import datetime
from ib_insync import IB, util
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

WORKSPACE = os.path.expanduser('~/.openclaw/workspace')
TRADING_DIR = os.path.join(WORKSPACE, 'trading')
PORTFOLIO_FILE = os.path.join(TRADING_DIR, 'portfolio.json')
LOGS_DIR = os.path.join(TRADING_DIR, 'logs')
RECONCILIATION_LOG = os.path.join(LOGS_DIR, 'reconciliation.jsonl')


class DailyReconciler:
    """Performs daily reconciliation of portfolio vs IB positions"""
    
    def __init__(self, host='127.0.0.1', port=4002, client_id=103):
        """Initialize IB connection for reconciliation"""
        self.ib = IB()
        self.host = host
        self.port = port
        self.client_id = client_id
        self.connected = False
        self.timeout_seconds = 15
        
    def connect(self) -> bool:
        """Connect to IB Gateway"""
        try:
            logger.info(f"🔍 Connecting to IB Gateway for daily reconciliation")
            self.ib.connect(self.host, self.port, clientId=self.client_id, timeout=self.timeout_seconds)
            self.connected = True
            logger.info("✅ Reconciliation connection established")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect for reconciliation: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from IB Gateway"""
        if self.connected:
            self.ib.disconnect()
            self.connected = False
            logger.info("🔌 Reconciliation connection closed")
    
    def fetch_ib_positions(self) -> Dict[str, float]:
        """
        Query IB Gateway for all actual positions
        Returns dict of {symbol: quantity}
        """
        if not self.connected:
            raise RuntimeError("Not connected to IB Gateway")
        
        try:
            positions = self.ib.positions()
            
            position_dict = {}
            for pos in positions:
                symbol = pos.contract.symbol
                qty = pos.position
                
                if symbol not in position_dict:
                    position_dict[symbol] = 0
                position_dict[symbol] += qty
            
            logger.info(f"📊 Fetched {len(position_dict)} positions from IB Gateway")
            return position_dict
            
        except Exception as e:
            logger.error(f"❌ Error fetching IB positions: {e}")
            raise
    
    def fetch_portfolio_state(self) -> Dict[str, float]:
        """Load current portfolio state from portfolio.json"""
        try:
            with open(PORTFOLIO_FILE, 'r') as f:
                data = json.load(f)
            
            position_dict = {}
            for pos in data.get('positions', []):
                symbol = pos.get('symbol')
                qty = pos.get('quantity', 0)
                
                if symbol:
                    if symbol not in position_dict:
                        position_dict[symbol] = 0
                    position_dict[symbol] += qty
            
            logger.info(f"📋 Loaded {len(position_dict)} positions from portfolio.json")
            return position_dict
            
        except Exception as e:
            logger.error(f"❌ Error reading portfolio.json: {e}")
            return {}
    
    def compare_positions(self, ib_positions: Dict[str, float], 
                         portfolio_positions: Dict[str, float]) -> List[Dict]:
        """
        Compare IB positions with portfolio positions
        
        Returns:
            List of discrepancies
        """
        discrepancies = []
        all_symbols = set(ib_positions.keys()) | set(portfolio_positions.keys())
        
        for symbol in all_symbols:
            ib_qty = ib_positions.get(symbol, 0)
            portfolio_qty = portfolio_positions.get(symbol, 0)
            
            if ib_qty != portfolio_qty:
                discrepancy = {
                    'symbol': symbol,
                    'portfolio_qty': portfolio_qty,
                    'ib_qty': ib_qty,
                    'variance': ib_qty - portfolio_qty,
                    'variance_pct': ((ib_qty - portfolio_qty) / portfolio_qty * 100 
                                    if portfolio_qty != 0 else float('inf')),
                    'discrepancy_type': 'missing' if ib_qty < portfolio_qty else 'extra'
                }
                discrepancies.append(discrepancy)
                
                logger.warning(f"⚠️  Mismatch {symbol}: portfolio={portfolio_qty}, IB={ib_qty} "
                             f"(variance={discrepancy['variance']})")
        
        return discrepancies
    
    def generate_reconciliation_report(self, 
                                      ib_positions: Dict[str, float],
                                      portfolio_positions: Dict[str, float],
                                      discrepancies: List[Dict]) -> Dict:
        """Generate reconciliation report summary"""
        
        timestamp = datetime.now()
        
        report = {
            'timestamp': timestamp.isoformat(),
            'date': timestamp.strftime('%Y-%m-%d'),
            'time': timestamp.strftime('%H:%M:%S'),
            'reconciliation_type': 'DAILY_8PM',
            'portfolio_symbol_count': len(portfolio_positions),
            'ib_symbol_count': len(ib_positions),
            'total_symbols': len(set(ib_positions.keys()) | set(portfolio_positions.keys())),
            'portfolio_net_shares': sum(portfolio_positions.values()),
            'ib_net_shares': sum(ib_positions.values()),
            'discrepancy_count': len(discrepancies),
            'status': 'OK' if len(discrepancies) == 0 else 'MISMATCH_DETECTED',
            'discrepancies': discrepancies
        }
        
        if len(discrepancies) > 0:
            report['action_required'] = 'Investigate position mismatches'
            report['recommendation'] = 'Review discrepancies and consider refreshing from IB'
        
        return report
    
    def run_daily_reconciliation(self) -> Dict:
        """
        Run complete daily reconciliation
        
        Returns:
            Reconciliation report
        """
        try:
            if not self.connect():
                logger.error("❌ Cannot run reconciliation - IB Gateway unavailable")
                return {
                    'status': 'FAILED',
                    'error': 'IB Gateway connection failed',
                    'timestamp': datetime.now().isoformat()
                }
            
            # Fetch both position sources
            logger.info("📋 Fetching positions from IB Gateway...")
            ib_positions = self.fetch_ib_positions()
            
            logger.info("📋 Fetching positions from portfolio.json...")
            portfolio_positions = self.fetch_portfolio_state()
            
            # Compare
            logger.info("🔍 Comparing positions...")
            discrepancies = self.compare_positions(ib_positions, portfolio_positions)
            
            # Generate report
            report = self.generate_reconciliation_report(
                ib_positions, portfolio_positions, discrepancies
            )
            
            # Log report
            self._log_reconciliation(report)
            
            # Print summary
            self._print_summary(report)
            
            return report
            
        finally:
            self.disconnect()
    
    def _log_reconciliation(self, report: Dict):
        """Log reconciliation report to reconciliation.jsonl"""
        try:
            os.makedirs(LOGS_DIR, exist_ok=True)
            with open(RECONCILIATION_LOG, 'a') as f:
                f.write(json.dumps(report) + '\n')
            logger.info(f"📝 Reconciliation logged to {RECONCILIATION_LOG}")
        except Exception as e:
            logger.error(f"Failed to log reconciliation: {e}")
    
    def _print_summary(self, report: Dict):
        """Print reconciliation summary to console"""
        print("\n" + "="*70)
        print("DAILY RECONCILIATION REPORT")
        print("="*70)
        print(f"Date: {report.get('date')} {report.get('time')}")
        print(f"Status: {report.get('status')}")
        print(f"Portfolio symbols: {report.get('portfolio_symbol_count')}")
        print(f"IB symbols: {report.get('ib_symbol_count')}")
        print(f"Portfolio net shares: {report.get('portfolio_net_shares')}")
        print(f"IB net shares: {report.get('ib_net_shares')}")
        
        if report.get('discrepancies'):
            print(f"\n⚠️  Found {len(report['discrepancies'])} discrepancies:")
            print("-" * 70)
            for disc in report['discrepancies']:
                print(f"  {disc['symbol']:8s} | Portfolio: {disc['portfolio_qty']:8.0f} | "
                      f"IB: {disc['ib_qty']:8.0f} | Variance: {disc['variance']:+8.0f}")
            
            if report.get('recommendation'):
                print(f"\n💡 Recommendation: {report['recommendation']}")
        else:
            print("\n✅ No discrepancies found - positions match perfectly!")
        
        print("="*70 + "\n")


def run_reconciliation() -> Dict:
    """Convenience function to run reconciliation"""
    reconciler = DailyReconciler()
    return reconciler.run_daily_reconciliation()


if __name__ == '__main__':
    # Run daily reconciliation
    report = run_reconciliation()
    
    # Exit with error code if mismatches found
    if report.get('status') == 'MISMATCH_DETECTED':
        sys.exit(1)
    elif report.get('status') == 'FAILED':
        sys.exit(2)
    else:
        sys.exit(0)
