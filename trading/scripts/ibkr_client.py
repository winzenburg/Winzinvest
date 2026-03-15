#!/usr/bin/env python3
"""
IBKR API Client
Direct integration with Interactive Brokers Gateway
Port is loaded from trading/.env (IB_PORT). Defaults to 4001 (live).
"""

import logging
import os
from pathlib import Path
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.common import BarData, TickAttrib
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.tag_value import TagValue
import threading
import time
from datetime import datetime
import json

_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IBKRWrapper(EWrapper):
    """Handles responses from IBKR API"""
    
    def __init__(self):
        self.next_order_id = None
        self.orders_placed = []
        self.errors = []
        self.is_connected = False
    
    def connectionClosed(self):
        logger.warning("❌ Connection to IB Gateway closed")
        self.is_connected = False
    
    def nextValidId(self, orderId):
        """Receive next valid order ID from IB"""
        self.next_order_id = orderId
        logger.info(f"✅ Next valid order ID: {orderId}")
    
    def orderStatus(self, orderId, status, filled, remaining, avgFillPrice, permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice):
        """Order status update"""
        logger.info(f"📊 Order {orderId}: {status} | Filled: {filled}/{filled+remaining} @ {avgFillPrice}")
    
    def execDetails(self, reqId, contract, execution):
        """Execution details"""
        logger.info(f"✅ EXECUTED: {contract.symbol} {execution.shares} @ {execution.price}")
    
    def error(self, reqId, errorCode, errorString):
        """Error callback"""
        logger.error(f"❌ Error [{errorCode}]: {errorString}")
        self.errors.append({'code': errorCode, 'msg': errorString})


class IBKRClient(EClient):
    """IBKR API Client"""
    
    def __init__(self, wrapper):
        EClient.__init__(self, wrapper)
        self.host = os.getenv("IB_HOST", "127.0.0.1")
        self.port = int(os.getenv("IB_PORT", "4001"))
        self.clientId = 0
    
    def connect_to_gateway(self):
        """Connect to IB Gateway"""
        logger.info(f"🔌 Connecting to IB Gateway at {self.host}:{self.port}")
        self.connect(self.host, self.port, self.clientId)
        
        thread = threading.Thread(target=self.run)
        thread.daemon = True
        thread.start()
        
        # Wait for connection
        time.sleep(2)
        
        if self.isConnected():
            logger.info("✅ Connected to IB Gateway")
            self.wrapper.is_connected = True
            return True
        else:
            logger.error("❌ Failed to connect to IB Gateway")
            return False
    
    def place_option_order(self, symbol, action, orderType, quantity, limit_price=None, order_type_str="LMT"):
        """
        Place an options order
        
        Args:
            symbol: Underlying symbol (e.g., "AAPL")
            action: "BUY" or "SELL"
            orderType: "PUT" or "CALL"
            quantity: Number of contracts
            limit_price: Limit price for LMT orders
            order_type_str: "LMT" or "MKT"
        """
        if not self.wrapper.next_order_id:
            logger.error("❌ Order ID not received yet. Wait for connection.")
            return False
        
        try:
            # Create contract
            contract = Contract()
            contract.symbol = symbol
            contract.secType = "OPT"
            contract.exchange = "SMART"
            contract.currency = "USD"
            
            # Note: In production, would need to query contract details
            # For now, using placeholder values - need proper implementation
            contract.lastTradeDateOrContractMonth = "20260312"  # Next Friday
            contract.strike = 250  # Placeholder
            contract.right = orderType
            contract.multiplier = "100"
            
            # Create order
            order = Order()
            order.action = action
            order.totalQuantity = quantity
            order.orderType = order_type_str
            
            if order_type_str == "LMT" and limit_price:
                order.lmtPrice = limit_price
            
            # Place order
            orderId = self.wrapper.next_order_id
            self.wrapper.next_order_id += 1
            
            logger.info(f"📝 Placing order: {action} {quantity} {symbol} {orderType} @ {limit_price or 'MKT'}")
            self.placeOrder(orderId, contract, order)
            
            self.wrapper.orders_placed.append({
                'orderId': orderId,
                'symbol': symbol,
                'action': action,
                'quantity': quantity,
                'orderType': orderType,
                'timestamp': datetime.now().isoformat()
            })
            
            return True
        
        except Exception as e:
            logger.error(f"❌ Error placing order: {e}")
            return False


def main():
    """Test IBKR connection and order placement"""
    
    wrapper = IBKRWrapper()
    client = IBKRClient(wrapper)
    
    # Connect to IB Gateway
    if not client.connect_to_gateway():
        logger.error("Failed to connect to IB Gateway")
        return
    
    # Wait for order ID
    time.sleep(1)
    
    if not wrapper.next_order_id:
        logger.error("Never received order ID")
        return
    
    # Test: Place a paper trading order
    logger.info("=" * 50)
    logger.info("Testing paper trading order placement...")
    logger.info("=" * 50)
    
    # Note: These are placeholder values - real implementation needs proper strike/expiry resolution
    # client.place_option_order("AAPL", "BUY", "PUT", 1, limit_price=2.50)
    
    logger.info("✅ IBKR Client Ready for order placement")
    logger.info(f"Connected: {wrapper.is_connected}")
    logger.info(f"Next Order ID: {wrapper.next_order_id}")
    
    # Keep running
    time.sleep(5)
    
    # Clean disconnect
    client.disconnect()


if __name__ == "__main__":
    main()
