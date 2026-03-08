#!/usr/bin/env python3
"""
Automated Stop-Loss Order Manager
Handles placement, monitoring, and logging of stop-loss orders via IB Gateway
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, Optional, List
from ib_insync import IB, util, Order, Stock, LimitOrder
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import circuit breaker for VIX-based stop tightening
try:
    from circuit_breaker import get_circuit_breaker
    CIRCUIT_BREAKER_AVAILABLE = True
except ImportError:
    logger.warning("⚠️  circuit_breaker module not available - VIX-based stop tightening disabled")
    CIRCUIT_BREAKER_AVAILABLE = False

# Defaults
DEFAULT_RISK_PCT = 0.02  # 2%
SECTOR_RISK_OVERRIDES = {
    'TECH': 0.03,  # 3% for tech
    'FINANCE': 0.025,  # 2.5% for finance
    'ENERGY': 0.035,  # 3.5% for energy
}
STOP_LOSS_LOG = os.path.expanduser('~/.openclaw/workspace/trading/logs/stops_executed.json')
PENDING_STOPS_FILE = os.path.expanduser('~/.openclaw/workspace/trading/logs/pending_stops.json')


class StopLossManager:
    """Manages stop-loss order placement and tracking"""
    
    def __init__(self, host='127.0.0.1', port=4002, client_id=101):
        """Initialize connection to IB Gateway"""
        self.ib = IB()
        self.host = host
        self.port = port
        self.client_id = client_id
        self.connected = False
        self.pending_stops = {}  # Track pending orders by order_id
        self.load_pending_stops()
        
    def connect(self) -> bool:
        """Connect to IB Gateway"""
        try:
            logger.info(f"🔌 Connecting to IB Gateway at {self.host}:{self.port}")
            self.ib.connect(self.host, self.port, clientId=self.client_id, timeout=30)
            self.connected = True
            logger.info("✅ Connected to IB Gateway")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to IB Gateway: {e}")
            self.connected = False
            return False
            
    def disconnect(self):
        """Disconnect from IB Gateway"""
        if self.connected:
            self.ib.disconnect()
            self.connected = False
            logger.info("🔌 Disconnected from IB Gateway")
            
    def place_stop(self, symbol: str, entry_price: float, quantity: int, 
                   sector: str = None, risk_pct: float = None) -> Optional[Dict]:
        """
        Place a stop-loss order for a position
        Uses circuit breaker to tighten stops based on VIX regime
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            entry_price: Entry price of the position
            quantity: Number of shares
            sector: Sector for risk override (optional)
            risk_pct: Risk percentage override (optional)
            
        Returns:
            Order metadata dict or None if placement failed
        """
        if not self.connected:
            logger.error("❌ Not connected to IB Gateway")
            return None
            
        try:
            # Determine base risk percentage
            if risk_pct is None:
                risk_pct = SECTOR_RISK_OVERRIDES.get(sector, DEFAULT_RISK_PCT)
            
            # Apply circuit breaker stop tightening
            applied_risk_pct = risk_pct
            circuit_breaker_info = {}
            if CIRCUIT_BREAKER_AVAILABLE:
                try:
                    breaker = get_circuit_breaker()
                    cb_stop_pct, cb_details = breaker.calculate_stop_percent()
                    
                    # Use tighter stop if circuit breaker demands it
                    if cb_stop_pct < risk_pct:
                        applied_risk_pct = cb_stop_pct
                        circuit_breaker_info = cb_details
                        logger.info(f"🛡️  Circuit breaker tightened stop: {risk_pct*100:.1f}% → {applied_risk_pct*100:.1f}% (Regime: {cb_details.get('regime', 'N/A')})")
                except Exception as e:
                    logger.warning(f"⚠️  Circuit breaker error: {e}")
                
            # Calculate stop price
            stop_price = round(entry_price * (1 - applied_risk_pct), 2)
            
            # Create contract
            contract = Stock(symbol, 'SMART', 'USD')
            
            # Create STOP order (market stop)
            order = Order()
            order.action = 'SELL' if quantity > 0 else 'BUY'
            order.totalQuantity = abs(quantity)
            order.orderType = 'STP'  # Stop order
            order.auxPrice = stop_price  # Stop price
            order.timeInForce = 'GTC'  # Good-till-canceled
            
            logger.info(f"📍 Placing stop-loss for {symbol}: {abs(quantity)} @ {stop_price} (entry: {entry_price}, risk: {risk_pct*100}%)")
            
            # Place the order
            trade = self.ib.placeOrder(contract, order)
            self.ib.sleep(0.5)  # Wait for order to be registered
            
            # Build metadata
            order_metadata = {
                'order_id': trade.order.orderId,
                'symbol': symbol,
                'entry_price': entry_price,
                'stop_price': stop_price,
                'quantity': abs(quantity),
                'risk_pct': risk_pct,
                'applied_risk_pct': applied_risk_pct,
                'circuit_breaker_applied': applied_risk_pct < risk_pct,
                'circuit_breaker_info': circuit_breaker_info,
                'sector': sector or 'N/A',
                'status': 'pending',
                'order_type': 'STOP',
                'time_in_force': 'GTC',
                'placed_timestamp': datetime.now().isoformat(),
                'fill_price': None,
                'exit_timestamp': None,
                'realized_pnl': None,
                'fill_slippage': None,
            }
            
            # Track pending order
            self.pending_stops[trade.order.orderId] = order_metadata
            self.save_pending_stops()
            
            logger.info(f"✅ Stop-loss placed: Order ID {trade.order.orderId}, Stop: ${stop_price}")
            return order_metadata
            
        except Exception as e:
            logger.error(f"❌ Failed to place stop-loss: {e}")
            return None
            
    def get_order_status(self, order_id: int) -> Optional[Dict]:
        """
        Get status of a pending stop-loss order
        
        Args:
            order_id: IB order ID
            
        Returns:
            Updated order metadata dict or None
        """
        if not self.connected:
            logger.error("❌ Not connected to IB Gateway")
            return None
            
        try:
            # Query order status from IB
            orders = self.ib.openOrders()
            
            for order in orders:
                if order.orderId == order_id:
                    # Order still open
                    return self.pending_stops.get(order_id, None)
                    
            # If not in open orders, check trades (executed)
            trades = self.ib.trades()
            for trade in trades:
                if trade.order.orderId == order_id and order_id in self.pending_stops:
                    order_data = self.pending_stops[order_id]
                    
                    # Check if filled
                    if trade.orderStatus.status == 'Filled':
                        order_data['status'] = 'filled'
                        order_data['exit_timestamp'] = datetime.now().isoformat()
                        
                        # Get execution details
                        if trade.fills:
                            fill = trade.fills[0]
                            order_data['fill_price'] = fill.execution.price
                            order_data['fill_slippage'] = abs(fill.execution.price - order_data['stop_price'])
                            
                            # Calculate realized P&L
                            qty = order_data['quantity']
                            entry = order_data['entry_price']
                            fill_price = fill.execution.price
                            pnl = (fill_price - entry) * qty * -1  # Negative because exiting
                            order_data['realized_pnl'] = round(pnl, 2)
                            
                        logger.info(f"✅ Stop filled: {order_data['symbol']} @ {order_data['fill_price']} (P&L: {order_data['realized_pnl']})")
                        self.save_pending_stops()
                        return order_data
                    elif trade.orderStatus.status == 'Cancelled':
                        order_data['status'] = 'cancelled'
                        logger.warning(f"⚠️  Stop cancelled: {order_data['symbol']} (Order {order_id})")
                        self.save_pending_stops()
                        return order_data
                        
            return self.pending_stops.get(order_id, None)
            
        except Exception as e:
            logger.error(f"❌ Error checking order status: {e}")
            return None
            
    def monitor_all_stops(self) -> List[Dict]:
        """
        Monitor all pending stop-loss orders
        
        Returns:
            List of updated order metadata dicts
        """
        if not self.connected:
            logger.error("❌ Not connected to IB Gateway")
            return []
            
        updated_orders = []
        order_ids = list(self.pending_stops.keys())
        
        for order_id in order_ids:
            status = self.get_order_status(order_id)
            if status:
                updated_orders.append(status)
                
        self.save_pending_stops()
        return updated_orders
        
    def cancel_stop(self, order_id: int) -> bool:
        """Cancel a pending stop-loss order"""
        if not self.connected:
            logger.error("❌ Not connected to IB Gateway")
            return False
            
        try:
            self.ib.cancelOrder(self.ib.trades()[order_id])
            logger.info(f"✅ Cancelled order {order_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to cancel order {order_id}: {e}")
            return False
            
    def load_pending_stops(self):
        """Load pending stops from file"""
        if os.path.exists(PENDING_STOPS_FILE):
            try:
                with open(PENDING_STOPS_FILE, 'r') as f:
                    data = json.load(f)
                    self.pending_stops = data.get('pending', {})
                    # Convert string keys to int
                    self.pending_stops = {int(k): v for k, v in self.pending_stops.items()}
                    logger.info(f"📂 Loaded {len(self.pending_stops)} pending stops from file")
            except Exception as e:
                logger.error(f"❌ Error loading pending stops: {e}")
                
    def save_pending_stops(self):
        """Save pending stops to file"""
        try:
            os.makedirs(os.path.dirname(PENDING_STOPS_FILE), exist_ok=True)
            with open(PENDING_STOPS_FILE, 'w') as f:
                json.dump({'pending': self.pending_stops}, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Error saving pending stops: {e}")
            
    def log_filled_stop(self, order_data: Dict):
        """Log a filled stop-loss order to the permanent log"""
        try:
            # Load existing log
            log_data = {'stops': [], 'summary': {}}
            if os.path.exists(STOP_LOSS_LOG):
                with open(STOP_LOSS_LOG, 'r') as f:
                    log_data = json.load(f)
                    
            # Add new entry
            log_entry = {
                'symbol': order_data['symbol'],
                'entry_price': order_data['entry_price'],
                'stop_price': order_data['stop_price'],
                'fill_price': order_data.get('fill_price'),
                'realized_pnl': order_data.get('realized_pnl'),
                'entry_timestamp': order_data['placed_timestamp'],
                'exit_timestamp': order_data.get('exit_timestamp'),
                'status': order_data['status'],
                'slippage': order_data.get('fill_slippage', 0),
            }
            log_data['stops'].append(log_entry)
            
            # Update summary
            filled = [s for s in log_data['stops'] if s['status'] == 'filled']
            log_data['summary'] = {
                'total_stops_placed': len(log_data['stops']),
                'total_stops_filled': len(filled),
                'total_stops_cancelled': len([s for s in log_data['stops'] if s['status'] == 'cancelled']),
                'total_realized_loss': sum([s.get('realized_pnl', 0) for s in filled]),
                'avg_fill_slippage': round(sum([s.get('slippage', 0) for s in filled]) / len(filled), 4) if filled else 0,
            }
            
            # Save
            os.makedirs(os.path.dirname(STOP_LOSS_LOG), exist_ok=True)
            with open(STOP_LOSS_LOG, 'w') as f:
                json.dump(log_data, f, indent=2)
                
            logger.info(f"📝 Logged filled stop: {order_data['symbol']}")
        except Exception as e:
            logger.error(f"❌ Error logging stop: {e}")


def main():
    """Test the stop-loss manager"""
    manager = StopLossManager()
    
    if not manager.connect():
        sys.exit(1)
        
    # Test: Place a dummy stop (won't actually execute in paper trading)
    # In production, this would be called by webhook_listener.py
    test_symbol = "AAPL"
    test_entry = 150.00
    test_qty = 10
    
    logger.info("🧪 Testing stop-loss placement...")
    result = manager.place_stop(test_symbol, test_entry, test_qty, sector='TECH')
    
    if result:
        logger.info(f"✅ Test successful: {json.dumps(result, indent=2)}")
    else:
        logger.error("❌ Test failed")
        
    manager.disconnect()


if __name__ == '__main__':
    main()
