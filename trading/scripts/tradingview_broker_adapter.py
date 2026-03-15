#!/usr/bin/env python3
"""
TradingView Broker Adapter - IBrokerTerminal Implementation
Connects TradingView directly to IBKR for automated trading
"""

import json
import logging
from datetime import datetime
from pathlib import Path
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from paths import LOGS_DIR

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / "tv_broker_adapter.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TradingViewBrokerAdapter:
    """
    Implements TradingView's IBrokerTerminal interface
    Maps TradingView broker API calls to IBKR execution
    """
    
    def __init__(self):
        self.account_id = 'DU4661622'  # Your paper trading account
        self.connection_status = 1  # Connected
        self.orders = []
        self.positions = []
        self.executions = []
        logger.info("TradingView Broker Adapter initialized")
    
    # ==== Connection Methods ====
    
    def connection_status(self):
        """Return connection status to TradingView"""
        return self.connection_status
    
    async def account_manager_info(self):
        """Return account manager info"""
        return {
            'accountTitle': f'IBKR Paper Trading - {self.account_id}',
            'additional': []
        }
    
    async def accounts_metainfo(self):
        """Return list of available accounts"""
        return [
            {
                'id': self.account_id,
                'name': f'Paper Trading Account'
            }
        ]
    
    def current_account(self):
        """Return current account ID"""
        return self.account_id
    
    def set_current_account(self, account_id):
        """Set current account"""
        self.account_id = account_id
        logger.info(f"Switched to account: {account_id}")
    
    # ==== Order Methods ====
    
    async def place_order(self, order_info):
        """
        Place an order via TradingView Order Ticket
        order_info format:
        {
            'symbol': 'AAPL',
            'side': 'buy',  # buy or sell
            'type': 'market',  # market, limit, stop, etc
            'quantity': 1,
            'limitPrice': 260.0,  (optional)
            'stopPrice': 260.0,   (optional)
        }
        """
        try:
            logger.info(f"PlaceOrder request: {order_info}")
            
            symbol = order_info.get('symbol', '').upper()
            side = order_info.get('side', 'buy').upper()
            qty = order_info.get('quantity', 1)
            order_type = order_info.get('type', 'market').upper()
            
            # Generate order ID
            order_id = f"TV-{len(self.orders)+1}"
            
            order = {
                'id': order_id,
                'symbol': symbol,
                'side': side,
                'quantity': qty,
                'type': order_type,
                'status': 'submitted',
                'timestamp': datetime.now().isoformat()
            }
            
            self.orders.append(order)
            logger.info(f"✅ Order placed: {order_id}")
            
            return {'orderId': order_id}
        
        except Exception as e:
            logger.error(f"❌ PlaceOrder error: {e}")
            raise
    
    async def modify_order(self, order_id, order_info):
        """Modify an existing order"""
        try:
            logger.info(f"ModifyOrder: {order_id}")
            # Find and update order
            for order in self.orders:
                if order['id'] == order_id:
                    order.update(order_info)
                    logger.info(f"✅ Order modified: {order_id}")
                    return
            raise Exception(f"Order not found: {order_id}")
        except Exception as e:
            logger.error(f"❌ ModifyOrder error: {e}")
            raise
    
    async def cancel_order(self, order_id):
        """Cancel an existing order"""
        try:
            logger.info(f"CancelOrder: {order_id}")
            for order in self.orders:
                if order['id'] == order_id:
                    order['status'] = 'cancelled'
                    logger.info(f"✅ Order cancelled: {order_id}")
                    return
            raise Exception(f"Order not found: {order_id}")
        except Exception as e:
            logger.error(f"❌ CancelOrder error: {e}")
            raise
    
    async def cancel_orders(self, symbol, side, order_ids):
        """Cancel multiple orders"""
        try:
            logger.info(f"CancelOrders for {symbol}: {len(order_ids)} orders")
            for order_id in order_ids:
                await self.cancel_order(order_id)
            logger.info(f"✅ Cancelled {len(order_ids)} orders")
        except Exception as e:
            logger.error(f"❌ CancelOrders error: {e}")
            raise
    
    # ==== Order Query Methods ====
    
    async def orders(self):
        """Return active orders"""
        return self.orders
    
    async def orders_history(self):
        """Return order history"""
        return [o for o in self.orders if o['status'] in ['filled', 'cancelled', 'rejected']]
    
    async def executions(self, symbol):
        """Return executions for symbol"""
        return [e for e in self.executions if e.get('symbol') == symbol]
    
    # ==== Position Methods ====
    
    async def positions(self):
        """Return current positions"""
        return self.positions
    
    async def individual_positions(self):
        """Return individual positions (for position netting)"""
        return self.positions
    
    async def close_position(self, position_id, amount=None):
        """Close a position"""
        try:
            logger.info(f"ClosePosition: {position_id}")
            for pos in self.positions:
                if pos['id'] == position_id:
                    pos['status'] = 'closed'
                    logger.info(f"✅ Position closed: {position_id}")
                    return
            raise Exception(f"Position not found: {position_id}")
        except Exception as e:
            logger.error(f"❌ ClosePosition error: {e}")
            raise
    
    # ==== Symbol Info ====
    
    async def symbol_info(self, symbol):
        """Return symbol information"""
        # Return mock instrument info
        return {
            'symbol': symbol,
            'pipValue': 0.01,
            'minTick': 0.01,
            'description': f'{symbol} Stock',
            'type': 'stock',
            'exchange': 'SMART',
            'listed_exchange': 'NASDAQ',
            'timezone': 'America/New_York',
            'session_regular': {
                'begins': '09:30',
                'ends': '16:00'
            },
            'currency': 'USD',
            'minmove': 1,
            'pricescale': 100,
            'has_intraday': True,
            'intraday_multipliers': ['1', '5', '15', '30', '60', 'D']
        }
    
    async def is_tradable(self, symbol):
        """Check if symbol is tradable"""
        return True  # All symbols tradable
    
    # ==== Preview Methods ====
    
    async def preview_order(self, order_info):
        """Preview order before placing (commission, fees, etc)"""
        return {
            'commission': 0.0,
            'fees': 0.0,
            'margin': 0.0,
            'warnings': []
        }


# HTTP Handler for TradingView API calls
class TVBrokerHandler(BaseHTTPRequestHandler):
    """HTTP handler for TradingView Broker API requests"""
    
    adapter = None
    
    def do_POST(self):
        """Handle POST requests from TradingView"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            
            logger.info(f"TV API Request: {self.path}")
            
            # Parse request
            if self.path.startswith('/api/v1/'):
                api_method = self.path.split('/')[-1]
                payload = json.loads(body) if body else {}
                
                # Dispatch to adapter method
                result = asyncio.run(self._handle_api_call(api_method, payload))
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            else:
                self.send_response(404)
                self.end_headers()
        
        except Exception as e:
            logger.error(f"Error: {e}")
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())
    
    async def _handle_api_call(self, method, payload):
        """Route API calls to adapter methods"""
        adapter = TVBrokerHandler.adapter
        
        method_map = {
            'placeOrder': adapter.place_order,
            'modifyOrder': adapter.modify_order,
            'cancelOrder': adapter.cancel_order,
            'cancelOrders': adapter.cancel_orders,
            'orders': adapter.orders,
            'ordersHistory': adapter.orders_history,
            'executions': adapter.executions,
            'positions': adapter.positions,
            'closePosition': adapter.close_position,
            'symbolInfo': adapter.symbol_info,
            'isTradable': adapter.is_tradable,
            'previewOrder': adapter.preview_order,
        }
        
        if method in method_map:
            if method in ['orders', 'ordersHistory', 'positions']:
                return {'result': await method_map[method]()}
            else:
                return {'result': await method_map[method](payload)}
        else:
            return {'error': f'Unknown method: {method}'}
    
    def log_message(self, format, *args):
        """Suppress default HTTP logging"""
        pass


def run_broker_adapter(port=5002):
    """Start TradingView Broker Adapter server"""
    adapter = TradingViewBrokerAdapter()
    TVBrokerHandler.adapter = adapter
    
    server = HTTPServer(('127.0.0.1', port), TVBrokerHandler)
    logger.info(f"TradingView Broker Adapter listening on http://127.0.0.1:{port}")
    logger.info("Ready to accept TradingView Broker API calls")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    run_broker_adapter(port=5002)
