#!/usr/bin/env python3
"""
Close Final 3 Positions via IB Gateway API
Closes: REM (5), AAPL (1), FXI (5)
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import List, Dict
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from kill_switch_guard import kill_switch_active

try:
    from ib_insync import IB, Stock, MarketOrder, util
except ImportError:
    print("ERROR: ib_insync not installed. Run: pip install ib_insync")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
IB_HOST = os.getenv('IB_HOST', '127.0.0.1')
IB_PORT = int(os.getenv('IB_PORT', 4001))
CLIENT_ID = int(os.getenv('IB_CLIENT_ID', 101))
ACCOUNT = os.getenv('IB_ACCOUNT', 'DU4661622')

# Positions to close
POSITIONS_TO_CLOSE = {
    'REM': 5,
    'AAPL': 1,
    'FXI': 5
}

class PositionCloser:
    def __init__(self):
        self.ib = IB()
        self.results = []
        self.errors = []
        
    async def connect(self) -> bool:
        """Connect to IB Gateway"""
        try:
            logger.info(f"🔌 Connecting to IB Gateway at {IB_HOST}:{IB_PORT} (ClientID {CLIENT_ID})")
            await self.ib.connectAsync(IB_HOST, IB_PORT, clientId=CLIENT_ID, timeout=30)
            logger.info("✅ Connected to IB Gateway")
            await asyncio.sleep(1)
            return True
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            self.errors.append(f"Connection failed: {e}")
            return False
    
    async def get_current_position(self, symbol: str) -> Dict:
        """Get current position details for a symbol"""
        try:
            positions = self.ib.portfolio()
            for pos in positions:
                if pos.contract.symbol == symbol:
                    return {
                        'symbol': symbol,
                        'qty': pos.position,
                        'avg_cost': pos.averageCost,
                        'market_price': pos.marketPrice,
                        'market_value': pos.marketValue,
                        'unrealized_pnl': pos.unrealizedPNL
                    }
            logger.warning(f"⚠️  Position not found for {symbol}")
            return None
        except Exception as e:
            logger.error(f"❌ Error fetching position for {symbol}: {e}")
            self.errors.append(f"Error fetching {symbol}: {e}")
            return None
    
    async def close_position(self, symbol: str, qty: int) -> Dict:
        """Close a position at market price"""
        try:
            logger.info(f"\n📊 Closing {symbol}: {qty} shares")
            
            # Get current position
            position = await self.get_current_position(symbol)
            if not position:
                return None
            
            logger.info(f"   Current position: {position['qty']} shares @ ${position['avg_cost']:.2f} avg cost")
            logger.info(f"   Market price: ${position['market_price']:.2f}")
            
            # Determine action (BUY if short, SELL if long)
            if position['qty'] < 0:
                # Short position - BUY to close
                action = 'BUY'
                order_qty = abs(int(position['qty']))
            else:
                # Long position - SELL to close
                action = 'SELL'
                order_qty = int(position['qty'])
            
            logger.info(f"   Action: {action} {order_qty} shares")
            
            # Create market order
            contract = Stock(symbol, 'SMART', 'USD')
            order = MarketOrder(action, order_qty)
            order.timeInForce = 'DAY'
            
            # Place order
            trade = self.ib.placeOrder(contract, order)
            logger.info(f"   Order placed. ID: {trade.order.orderId}")
            
            # Wait for execution
            logger.info("   ⏳ Waiting for execution...")
            start_time = datetime.now()
            timeout = 30  # 30 second timeout
            
            while trade.isDone() == False:
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > timeout:
                    logger.error(f"   ❌ Order timeout after {timeout}s")
                    self.errors.append(f"{symbol} order timeout")
                    return None
                await asyncio.sleep(0.5)
            
            # Get execution details
            fills = trade.fills
            if not fills:
                logger.error(f"   ❌ No fills for {symbol}")
                self.errors.append(f"{symbol}: no fills")
                return None
            
            # Calculate average execution price and P&L
            total_shares = sum(fill.execution.shares for fill in fills)
            total_cost = sum(fill.execution.shares * fill.execution.price for fill in fills)
            avg_execution_price = total_cost / total_shares if total_shares > 0 else 0
            
            # Calculate P&L
            if action == 'SELL':
                pnl = (avg_execution_price - position['avg_cost']) * total_shares
            else:
                # For short covers, profit = (avg_cost - execution_price) * qty
                pnl = (position['avg_cost'] - avg_execution_price) * total_shares
            
            result = {
                'symbol': symbol,
                'qty': order_qty,
                'action': action,
                'close_price': avg_execution_price,
                'execution_time': datetime.now().isoformat(),
                'pnl': pnl,
                'status': 'closed'
            }
            
            logger.info(f"   ✅ Executed {action} {order_qty} @ ${avg_execution_price:.2f}")
            logger.info(f"   💰 P&L: ${pnl:,.2f}")
            
            self.results.append(result)
            return result
            
        except Exception as e:
            logger.error(f"❌ Error closing {symbol}: {e}")
            self.errors.append(f"{symbol}: {e}")
            return None
    
    async def close_all_positions(self):
        """Close all positions in sequence"""
        logger.info(f"\n{'='*60}")
        logger.info("CLOSING FINAL 3 POSITIONS")
        logger.info(f"{'='*60}")
        
        for symbol, qty in POSITIONS_TO_CLOSE.items():
            await self.close_position(symbol, qty)
            await asyncio.sleep(1)  # Brief delay between orders
        
        return self.results
    
    async def disconnect(self):
        """Safely disconnect"""
        if self.ib.isConnected():
            logger.info("\n🔌 Disconnecting from IB Gateway...")
            self.ib.disconnect()
            logger.info("✅ Disconnected")
    
    def generate_report(self) -> Dict:
        """Generate final report"""
        total_pnl = sum(r['pnl'] for r in self.results)
        
        report = {
            'status': 'completed' if len(self.results) == len(POSITIONS_TO_CLOSE) else 'partial',
            'timestamp': datetime.now().isoformat(),
            'positions_closed': len(self.results),
            'execution_results': self.results,
            'total_realized_pnl': total_pnl,
            'errors': self.errors
        }
        
        return report


async def main():
    """Main execution"""
    if kill_switch_active():
        logger.error("Kill switch is ACTIVE — close_final_positions aborted.")
        sys.exit(1)

    closer = PositionCloser()
    
    try:
        # Connect
        if not await closer.connect():
            sys.exit(1)
        
        # Close all positions
        results = await closer.close_all_positions()
        
        # Generate report
        report = closer.generate_report()
        
        # Print summary
        logger.info(f"\n{'='*60}")
        logger.info("EXECUTION SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Positions closed: {report['positions_closed']}/{len(POSITIONS_TO_CLOSE)}")
        logger.info(f"Total realized P&L: ${report['total_realized_pnl']:,.2f}")
        
        if report['errors']:
            logger.warning(f"\nErrors encountered: {len(report['errors'])}")
            for error in report['errors']:
                logger.warning(f"  - {error}")
        
        logger.info(f"{'='*60}\n")
        
        # Save report
        report_file = Path(__file__).resolve().parent.parent / "logs" / "close_positions_report.json"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        logger.info(f"📄 Report saved to {report_file}")
        
        # Output JSON for programmatic use
        print(json.dumps(report, indent=2))
        
        return report
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
    finally:
        await closer.disconnect()


if __name__ == '__main__':
    report = asyncio.run(main())
    sys.exit(0 if report['status'] == 'completed' else 1)
