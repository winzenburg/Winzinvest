#!/usr/bin/env python3
"""
IBKR Executor using ib_insync
Simpler, more reliable contract handling
"""

import json
import logging
from datetime import datetime
from ib_insync import IB, Option, MarketOrder
import asyncio

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/pinchy/.openclaw/workspace/trading/logs/ibkr_executor_insync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class IBKRExecutorInsync:
    """IBKR executor using ib_insync library"""
    
    def __init__(self, paper_trading=True):
        self.ib = IB()
        self.paper_trading = paper_trading
        self.mode = "PAPER" if paper_trading else "LIVE"
        self.results = []
        logger.info(f"🚀 IBKR Executor (ib_insync) initialized in {self.mode} mode")
    
    async def connect(self):
        """Connect to IB Gateway"""
        logger.info(f"🔌 Connecting to IB Gateway at 127.0.0.1:4002...")
        try:
            await self.ib.connectAsync(host='127.0.0.1', port=4002, clientId=0)
            logger.info(f"✅ Connected to IB Gateway")
            logger.info(f"📊 Account: {self.ib.managedAccounts()}")
            return True
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
    
    async def execute_trades(self, trades_file):
        """Execute trades from JSON file"""
        
        # Load trades
        try:
            with open(trades_file, 'r') as f:
                trades_data = json.load(f)
        except Exception as e:
            logger.error(f"❌ Failed to load trades: {e}")
            return []
        
        # Handle single or multiple trades
        if isinstance(trades_data, dict) and 'trade' in trades_data:
            trades = [trades_data]
        elif isinstance(trades_data, list):
            trades = trades_data
        else:
            logger.error("Invalid trades file format")
            return []
        
        logger.info(f"📋 Found {len(trades)} trades to execute")
        
        # Connect
        if not await self.connect():
            return []
        
        # Execute each trade
        for i, trade in enumerate(trades, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"Trade {i}/{len(trades)}")
            logger.info(f"{'='*60}")
            
            result = await self._execute_trade(trade)
            self.results.append(result)
            
            await asyncio.sleep(0.5)
        
        # Disconnect
        self.ib.disconnect()
        
        # Write report
        self._write_report()
        
        return self.results
    
    async def _execute_trade(self, trade):
        """Execute single trade"""
        try:
            # Parse trade
            symbol = trade.get('symbol') or trade.get('trade', {}).get('symbol')
            action = trade.get('type', 'BUY')
            right = trade.get('contract', 'PUT')  # CALL or PUT
            strike = float(trade.get('strike') or trade.get('trade', {}).get('strike'))
            expiry = trade.get('expiry') or trade.get('trade', {}).get('expiry')
            quantity = int(trade.get('contracts', 1) or trade.get('trade', {}).get('contracts', 1))
            reason = trade.get('reason', '')
            
            logger.info(f"Symbol: {symbol} | Action: {action} | Type: {right} {strike} | Expiry: {expiry}")
            logger.info(f"Quantity: {quantity} | Reason: {reason[:60]}")
            
            # Convert expiry format from 2026-03-12 to 20260312
            if '-' in str(expiry):
                expiry_ib = expiry.replace('-', '')
            else:
                expiry_ib = expiry
            
            # Create option contract with exchange specified
            option = Option(symbol, expiry_ib, strike, right, exchange='SMART')
            
            logger.info(f"🔍 Qualifying contract...")
            await self.ib.qualifyContractsAsync(option)
            
            if not option.conId:
                logger.error(f"❌ Failed to qualify contract")
                return {
                    'status': 'FAILED',
                    'trade': f"{action} {quantity} {symbol} {right} {strike}",
                    'reason': 'Contract qualification failed',
                    'timestamp': datetime.now().isoformat()
                }
            
            logger.info(f"✅ Contract qualified: conId={option.conId} | localSymbol={option.localSymbol}")
            
            # Create order with TIF (Time In Force)
            order = MarketOrder(action, quantity)
            order.tif = 'DAY'  # Day order
            
            logger.info(f"📝 Placing {action} order for {quantity} contract(s)...")
            logger.info(f"   Contract exchange: {option.exchange}")
            logger.info(f"   Option: {option.symbol} {right} {strike} {expiry_ib}")
            trade_obj = self.ib.placeOrder(option, order)
            
            # Wait briefly for order submission
            await asyncio.sleep(1.5)
            
            # Check order status
            order_status = trade_obj.orderStatus.status if trade_obj.orderStatus else "Unknown"
            
            if order_status in ['Submitted', 'PreSubmitted', 'Filled']:
                logger.info(f"✅ Order placed: {trade_obj.order.orderId} | Status: {order_status}")
                return {
                    'status': 'EXECUTED',
                    'mode': self.mode,
                    'trade': f"{action} {quantity} {symbol} {right} {strike}",
                    'expiry': expiry,
                    'orderId': trade_obj.order.orderId,
                    'conId': option.conId,
                    'localSymbol': option.localSymbol,
                    'orderStatus': order_status,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                logger.warning(f"⚠️  Order status: {order_status}")
                return {
                    'status': 'PENDING',
                    'trade': f"{action} {quantity} {symbol} {right} {strike}",
                    'orderId': trade_obj.order.orderId,
                    'orderStatus': order_status,
                    'timestamp': datetime.now().isoformat()
                }
        
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'status': 'ERROR',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _write_report(self):
        """Write execution report"""
        successful = sum(1 for r in self.results if r['status'] == 'EXECUTED')
        
        report = {
            'mode': self.mode,
            'execution_time': datetime.now().isoformat(),
            'total_trades': len(self.results),
            'successful': successful,
            'failed': len(self.results) - successful,
            'results': self.results
        }
        
        report_file = '/Users/pinchy/.openclaw/workspace/trading/logs/ibkr_execution_report.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ EXECUTION COMPLETE: {successful}/{len(self.results)} successful")
        logger.info(f"Report: {report_file}")
        logger.info(f"{'='*60}")


async def main():
    executor = IBKRExecutorInsync(paper_trading=True)
    trades_file = '/Users/pinchy/.openclaw/workspace/trading/logs/paper_trades.json'
    await executor.execute_trades(trades_file)


if __name__ == "__main__":
    asyncio.run(main())
