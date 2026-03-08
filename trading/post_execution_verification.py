#!/usr/bin/env python3
"""
Post-Execution Verification Module
Verifies that trades actually executed in IB Gateway after order placement
Detects mismatches between expected portfolio state and actual IB positions
"""

import json
import logging
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from ib_insync import IB, Stock, util
import os
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
VERIFICATION_LOG = os.path.join(LOGS_DIR, 'post_execution_verification.jsonl')
MISMATCH_ALERT_LOG = os.path.join(LOGS_DIR, 'verification_mismatches.jsonl')


class PostExecutionVerifier:
    """Verifies that trades executed correctly against IB Gateway"""
    
    def __init__(self, host='127.0.0.1', port=4002, client_id=102):
        """Initialize IB connection for verification"""
        self.ib = IB()
        self.host = host
        self.port = port
        self.client_id = client_id
        self.connected = False
        self.timeout_seconds = 10
        self.max_retries = 1
        
    def connect(self, timeout_seconds=10) -> bool:
        """Connect to IB Gateway with timeout handling"""
        try:
            logger.info(f"🔍 Connecting to IB Gateway for verification at {self.host}:{self.port}")
            self.ib.connect(self.host, self.port, clientId=self.client_id, timeout=timeout_seconds)
            self.connected = True
            logger.info("✅ Verification connection established")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect for verification: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from IB Gateway"""
        if self.connected:
            self.ib.disconnect()
            self.connected = False
            logger.info("🔌 Verification connection closed")
    
    def fetch_ib_positions(self) -> Dict[str, float]:
        """
        Query IB Gateway for all actual positions
        Returns dict of {symbol: quantity}
        
        Raises TimeoutError if query takes > timeout_seconds
        """
        if not self.connected:
            raise RuntimeError("Not connected to IB Gateway")
        
        try:
            start_time = time.time()
            
            # Request account summary (includes positions)
            acctValues = self.ib.accountValues()
            positions = self.ib.positions()
            
            elapsed = time.time() - start_time
            if elapsed > self.timeout_seconds:
                logger.warning(f"⏱️  IB query took {elapsed:.1f}s (timeout: {self.timeout_seconds}s)")
            
            # Build position dict from portfolio
            position_dict = {}
            for pos in positions:
                symbol = pos.contract.symbol
                qty = pos.position
                position_dict[symbol] = qty
            
            logger.info(f"📊 Fetched {len(position_dict)} positions from IB Gateway")
            return position_dict
            
        except Exception as e:
            logger.error(f"❌ Error fetching IB positions: {e}")
            raise
    
    def fetch_portfolio_state(self) -> Dict[str, float]:
        """Load expected portfolio state from portfolio.json"""
        try:
            with open(PORTFOLIO_FILE, 'r') as f:
                data = json.load(f)
            
            position_dict = {}
            for pos in data.get('positions', []):
                symbol = pos.get('symbol')
                qty = pos.get('quantity', 0)
                
                if symbol:
                    # Sum up quantities for same symbol (may have multiple entries)
                    if symbol not in position_dict:
                        position_dict[symbol] = 0
                    position_dict[symbol] += qty
            
            logger.info(f"📋 Loaded {len(position_dict)} expected positions from portfolio.json")
            return position_dict
            
        except Exception as e:
            logger.error(f"❌ Error reading portfolio.json: {e}")
            return {}
    
    def verify_position_open(self, symbol: str, expected_qty: float, 
                             tolerance: float = 0.0) -> Tuple[bool, Dict]:
        """
        Verify that a position opened with expected quantity
        
        Args:
            symbol: Stock symbol
            expected_qty: Expected quantity
            tolerance: Allow variance (e.g., 0.0 = exact match, 1.0 = allow 1 share variance)
            
        Returns:
            (is_verified: bool, details: dict)
        """
        if not self.connected:
            return False, {'error': 'Not connected to IB Gateway'}
        
        try:
            ib_positions = self.fetch_ib_positions()
            actual_qty = ib_positions.get(symbol, 0)
            
            variance = abs(actual_qty - expected_qty)
            is_match = variance <= tolerance
            
            result = {
                'symbol': symbol,
                'expected_qty': expected_qty,
                'actual_qty': actual_qty,
                'variance': variance,
                'tolerance': tolerance,
                'verified': is_match,
                'timestamp': datetime.now().isoformat()
            }
            
            if is_match:
                logger.info(f"✅ Position verified: {symbol} {actual_qty} shares")
            else:
                logger.error(f"❌ Position mismatch: {symbol} expected {expected_qty}, got {actual_qty}")
                self._log_mismatch(result)
            
            return is_match, result
            
        except Exception as e:
            logger.error(f"❌ Error verifying position {symbol}: {e}")
            return False, {'error': str(e), 'symbol': symbol}
    
    def verify_stop_placed(self, symbol: str, order_id: Optional[str] = None) -> Tuple[bool, Dict]:
        """
        Verify that a stop-loss order was placed
        
        Args:
            symbol: Stock symbol
            order_id: Order ID to verify (optional)
            
        Returns:
            (is_verified: bool, details: dict)
        """
        if not self.connected:
            return False, {'error': 'Not connected to IB Gateway'}
        
        try:
            # Query open orders
            open_orders = self.ib.openOrders()
            
            stop_orders = [o for o in open_orders 
                          if o.contract.symbol == symbol 
                          and 'STP' in o.orderType]
            
            has_stop = len(stop_orders) > 0
            
            result = {
                'symbol': symbol,
                'order_id': order_id,
                'stop_found': has_stop,
                'open_stop_count': len(stop_orders),
                'timestamp': datetime.now().isoformat()
            }
            
            if stop_orders:
                result['stop_details'] = [
                    {
                        'order_id': o.orderId,
                        'type': o.orderType,
                        'stop_price': o.auxPrice,
                        'status': o.status
                    }
                    for o in stop_orders
                ]
            
            if has_stop:
                logger.info(f"✅ Stop verified: {symbol} (found {len(stop_orders)} stop order(s))")
            else:
                logger.error(f"❌ No stop found for {symbol}")
                self._log_mismatch(result)
            
            return has_stop, result
            
        except Exception as e:
            logger.error(f"❌ Error verifying stop for {symbol}: {e}")
            return False, {'error': str(e), 'symbol': symbol}
    
    def verify_fills_recorded(self, symbol: str) -> Tuple[List[Dict], Dict]:
        """
        Verify that fills are recorded in IB
        
        Args:
            symbol: Stock symbol
            
        Returns:
            (fills: list of fill dicts, summary: dict)
        """
        if not self.connected:
            return [], {'error': 'Not connected to IB Gateway'}
        
        try:
            # Query executions (fills)
            executions = self.ib.executions()
            
            symbol_fills = [e for e in executions 
                           if e.execution.acctNumber and 
                           e.contract.symbol == symbol]
            
            fills_list = [
                {
                    'symbol': symbol,
                    'exec_id': e.execution.execId,
                    'qty': e.execution.shares,
                    'price': e.execution.price,
                    'time': str(e.execution.time),
                    'commission': getattr(e.execution, 'commission', None)
                }
                for e in symbol_fills
            ]
            
            summary = {
                'symbol': symbol,
                'fill_count': len(fills_list),
                'total_shares': sum(f['qty'] for f in fills_list),
                'avg_price': (sum(f['qty'] * f['price'] for f in fills_list) / 
                             sum(f['qty'] for f in fills_list) if fills_list else 0),
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"📈 Found {len(fills_list)} fills for {symbol}")
            return fills_list, summary
            
        except Exception as e:
            logger.error(f"❌ Error fetching fills for {symbol}: {e}")
            return [], {'error': str(e), 'symbol': symbol}
    
    def verify_with_retry(self, symbol: str, expected_qty: float, 
                         retry_delay: float = 5.0) -> Tuple[bool, Dict]:
        """
        Verify position with retry logic (fail once, wait, retry)
        
        Args:
            symbol: Stock symbol
            expected_qty: Expected quantity
            retry_delay: Seconds to wait before retry
            
        Returns:
            (is_verified: bool, details: dict)
        """
        for attempt in range(self.max_retries + 1):
            try:
                verified, result = self.verify_position_open(symbol, expected_qty)
                if verified or attempt == self.max_retries:
                    return verified, result
                
                if attempt < self.max_retries:
                    logger.info(f"⏳ Retrying verification for {symbol} in {retry_delay}s...")
                    time.sleep(retry_delay)
                    
            except Exception as e:
                logger.error(f"❌ Verification attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries:
                    time.sleep(retry_delay)
        
        return False, {'error': 'Max retries exceeded', 'symbol': symbol}
    
    def compare_positions(self) -> List[Dict]:
        """
        Compare IB positions with portfolio.json
        
        Returns:
            List of discrepancies
        """
        try:
            ib_positions = self.fetch_ib_positions()
            portfolio_positions = self.fetch_portfolio_state()
            
            discrepancies = []
            
            # Check for mismatches
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
                        'timestamp': datetime.now().isoformat()
                    }
                    discrepancies.append(discrepancy)
                    logger.warning(f"⚠️  Mismatch {symbol}: portfolio={portfolio_qty}, IB={ib_qty}")
                    self._log_mismatch(discrepancy)
            
            return discrepancies
            
        except Exception as e:
            logger.error(f"❌ Error comparing positions: {e}")
            return []
    
    def _log_mismatch(self, mismatch_dict: Dict):
        """Log mismatch to verification_mismatches.jsonl"""
        try:
            os.makedirs(LOGS_DIR, exist_ok=True)
            with open(MISMATCH_ALERT_LOG, 'a') as f:
                f.write(json.dumps(mismatch_dict) + '\n')
        except Exception as e:
            logger.error(f"Failed to log mismatch: {e}")
    
    def log_verification(self, verification_dict: Dict):
        """Log verification result to post_execution_verification.jsonl"""
        try:
            os.makedirs(LOGS_DIR, exist_ok=True)
            with open(VERIFICATION_LOG, 'a') as f:
                f.write(json.dumps(verification_dict) + '\n')
        except Exception as e:
            logger.error(f"Failed to log verification: {e}")


# Convenience functions for direct use
def verify_position_open(symbol: str, qty: float) -> bool:
    """Quick verification function"""
    verifier = PostExecutionVerifier()
    if not verifier.connect(timeout_seconds=10):
        logger.error(f"Failed to connect to IB Gateway for verification")
        return False
    
    try:
        verified, result = verifier.verify_position_open(symbol, qty)
        verifier.log_verification(result)
        return verified
    finally:
        verifier.disconnect()


def verify_stop_placed(symbol: str, order_id: Optional[str] = None) -> bool:
    """Quick stop verification function"""
    verifier = PostExecutionVerifier()
    if not verifier.connect(timeout_seconds=10):
        logger.error(f"Failed to connect to IB Gateway for verification")
        return False
    
    try:
        verified, result = verifier.verify_stop_placed(symbol, order_id)
        verifier.log_verification(result)
        return verified
    finally:
        verifier.disconnect()


def verify_fills_recorded(symbol: str) -> List[Dict]:
    """Quick fills verification function"""
    verifier = PostExecutionVerifier()
    if not verifier.connect(timeout_seconds=10):
        logger.error(f"Failed to connect to IB Gateway for verification")
        return []
    
    try:
        fills, summary = verifier.verify_fills_recorded(symbol)
        verifier.log_verification(summary)
        return fills
    finally:
        verifier.disconnect()


if __name__ == '__main__':
    # Test
    verifier = PostExecutionVerifier()
    if verifier.connect():
        print("Testing position verification...")
        
        # Get current positions and verify
        portfolio = verifier.fetch_portfolio_state()
        print(f"\nPortfolio positions: {portfolio}")
        
        # Compare with IB
        discrepancies = verifier.compare_positions()
        if discrepancies:
            print(f"\n⚠️  Found {len(discrepancies)} discrepancies:")
            for disc in discrepancies:
                print(f"  {disc['symbol']}: portfolio={disc['portfolio_qty']}, IB={disc['ib_qty']}")
        else:
            print("\n✅ No discrepancies found!")
        
        verifier.disconnect()
