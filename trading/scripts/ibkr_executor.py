#!/usr/bin/env python3
"""
IBKR Executor - End-to-end trade execution
Reads trade signals → Resolves contracts → Places orders → Logs results
"""

import json
import logging
import time
from datetime import datetime
from ibkr_client import IBKRClient, IBKRWrapper
from ibkr_contract_resolver import ContractResolver, ContractResolverWrapper
from paths import TRADING_DIR, LOGS_DIR

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / "ibkr_executor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class IBKRExecutor:
    """End-to-end IBKR trade executor"""
    
    def __init__(self, paper_trading=True):
        self.paper_trading = paper_trading
        self.mode = "PAPER" if paper_trading else "LIVE"
        logger.info(f"🚀 IBKR Executor initialized in {self.mode} mode")
    
    def execute_trades_from_file(self, trades_file):
        """
        Read trade signals from JSON and execute them
        
        Args:
            trades_file: Path to paper_trades.json
        
        Returns:
            List of execution results
        """
        # Load trade signals
        try:
            with open(trades_file, 'r') as f:
                trades_data = json.load(f)
        except Exception as e:
            logger.error(f"❌ Failed to load trades file: {e}")
            return []
        
        # Handle single trade or list of trades
        if isinstance(trades_data, dict) and 'trade' in trades_data:
            trades = [trades_data]
        elif isinstance(trades_data, list):
            trades = trades_data
        else:
            logger.error("Invalid trades file format")
            return []
        
        logger.info(f"📋 Found {len(trades)} trades to execute")
        
        # Connect to IB Gateway
        logger.info("🔌 Connecting to IB Gateway...")
        wrapper = IBKRWrapper()
        client = IBKRClient(wrapper)
        
        if not client.connect_to_gateway():
            logger.error("❌ Failed to connect to IB Gateway")
            return []
        
        # Wait for order ID
        time.sleep(2)
        if not wrapper.next_order_id:
            logger.error("❌ Never received order ID")
            return []
        
        # Connect contract resolver
        logger.info("🔍 Initializing contract resolver...")
        resolver_wrapper = ContractResolverWrapper()
        resolver = ContractResolver(resolver_wrapper)
        
        if not resolver.connect():
            logger.error("❌ Failed to connect contract resolver")
            return []
        
        # Execute trades
        results = []
        for i, trade in enumerate(trades, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"Trade {i}/{len(trades)}")
            logger.info(f"{'='*60}")
            
            result = self._execute_single_trade(trade, client, wrapper, resolver)
            results.append(result)
            
            # Delay between orders
            if i < len(trades):
                time.sleep(1)
        
        # Cleanup
        resolver.disconnect()
        client.disconnect()
        
        # Write execution report
        self._write_execution_report(results)
        
        return results
    
    def _execute_single_trade(self, trade, client, wrapper, resolver):
        """Execute a single trade signal"""
        
        try:
            # Parse trade details
            symbol = trade.get('symbol') or trade.get('trade', {}).get('symbol')
            action = trade.get('type') or 'BUY'
            contract_type = trade.get('contract', 'PUT')
            strike = trade.get('strike') or trade.get('trade', {}).get('strike')
            expiry = trade.get('expiry') or trade.get('trade', {}).get('expiry')
            quantity = trade.get('contracts', 1) or trade.get('trade', {}).get('contracts', 1)
            reason = trade.get('reason', 'No reason provided')
            
            logger.info(f"Symbol: {symbol} | Action: {action} | Type: {contract_type} | Strike: {strike} | Expiry: {expiry}")
            logger.info(f"Quantity: {quantity} | Reason: {reason}")
            
            # Resolve contract
            logger.info(f"🔍 Resolving contract...")
            contract = resolver.resolve_option_contract(symbol, strike, contract_type, expiry)
            
            if not contract:
                logger.error(f"❌ Failed to resolve contract for {symbol} {contract_type} {strike}")
                return {
                    'status': 'FAILED',
                    'trade': f"{action} {symbol} {contract_type} {strike}",
                    'reason': 'Contract resolution failed',
                    'timestamp': datetime.now().isoformat()
                }
            
            # Place order
            logger.info(f"📝 Placing {action} order for {quantity} contracts...")
            success = client.place_option_order(
                symbol=symbol,
                action=action,
                orderType=contract_type,
                quantity=quantity,
                limit_price=None,
                order_type_str="MKT"
            )
            
            if not success:
                logger.error(f"❌ Order placement failed")
                return {
                    'status': 'FAILED',
                    'trade': f"{action} {symbol} {contract_type} {strike}",
                    'reason': 'Order placement failed',
                    'timestamp': datetime.now().isoformat()
                }
            
            logger.info(f"✅ Order placed successfully")
            
            return {
                'status': 'EXECUTED',
                'mode': self.mode,
                'trade': f"{action} {quantity} {symbol} {contract_type} {strike}",
                'expiry': expiry,
                'orderId': wrapper.next_order_id - 1,
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"❌ Error executing trade: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                'status': 'ERROR',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _write_execution_report(self, results):
        """Write execution report"""
        report = {
            'mode': self.mode,
            'execution_time': datetime.now().isoformat(),
            'total_trades': len(results),
            'successful': sum(1 for r in results if r['status'] == 'EXECUTED'),
            'failed': sum(1 for r in results if r['status'] in ['FAILED', 'ERROR']),
            'results': results
        }
        
        report_file = str(LOGS_DIR / "ibkr_execution_report.json")
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"EXECUTION REPORT: {report['successful']}/{report['total_trades']} successful")
        logger.info(f"Report written to: {report_file}")
        logger.info(f"{'='*60}")


if __name__ == "__main__":
    import sys
    
    paper_mode = "--live" not in sys.argv
    executor = IBKRExecutor(paper_trading=paper_mode)
    
    trades_file = str(LOGS_DIR / "paper_trades.json")
    executor.execute_trades_from_file(trades_file)
