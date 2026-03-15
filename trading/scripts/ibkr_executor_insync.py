#!/usr/bin/env python3
"""
IBKR Executor using ib_insync
Simpler, more reliable contract handling
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from ib_insync import IB, Option, MarketOrder, LimitOrder
import asyncio
from paths import LOGS_DIR, TRADING_DIR

_env_path = TRADING_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / "ibkr_executor_insync.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class IBKRExecutorInsync:
    """IBKR executor using ib_insync library"""
    
    def __init__(self, paper_trading=True, extended_hours=False):
        self.ib = IB()
        self.paper_trading = paper_trading
        self.extended_hours = extended_hours
        self.mode = "PAPER" if paper_trading else "LIVE"
        self.hours_mode = "EXT" if extended_hours else "RTH"
        self.results = []
        logger.info(f"🚀 IBKR Executor (ib_insync) initialized in {self.mode} mode | Hours: {self.hours_mode}")
    
    async def connect(self):
        """Connect to IB Gateway"""
        _ib_host = os.getenv("IB_HOST", "127.0.0.1")
        _ib_port = int(os.getenv("IB_PORT", "4001"))
        logger.info(f"🔌 Connecting to IB Gateway at {_ib_host}:{_ib_port}...")
        try:
            await self.ib.connectAsync(host=_ib_host, port=_ib_port, clientId=0)
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
            
            # Create order based on hours mode
            if self.extended_hours:
                # Extended hours requires limit orders
                # Use mid-price estimate (simplified)
                limit_price = strike * 0.5 if action == 'BUY' else strike * 1.5
                order = LimitOrder(action, quantity, limit_price)
                order.tif = 'EXT'  # Extended hours
                order_type_str = f"LMT @ ${limit_price:.2f}"
            else:
                # Regular hours: market orders are fine
                order = MarketOrder(action, quantity)
                order.tif = 'DAY'  # Day order
                order_type_str = "MKT"
            
            logger.info(f"📝 Placing {action} order for {quantity} contract(s) ({order_type_str})...")
            logger.info(f"   Hours mode: {self.hours_mode} | TIF: {order.tif}")
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
        
        report_file = str(LOGS_DIR / "ibkr_execution_report.json")
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ EXECUTION COMPLETE: {successful}/{len(self.results)} successful")
        logger.info(f"Report: {report_file}")
        logger.info(f"{'='*60}")


async def main():
    import sys
    extended_hours = '--ext' in sys.argv or '--extended' in sys.argv
    executor = IBKRExecutorInsync(paper_trading=True, extended_hours=extended_hours)
    trades_file = str(LOGS_DIR / "ready_to_execute.json")
    await executor.execute_trades(trades_file)


if __name__ == "__main__":
    asyncio.run(main())
