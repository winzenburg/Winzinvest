#!/usr/bin/env python3
"""
Direct Premium Executor
Executes premium selling signals directly via IBKR (not through webhook).
Uses ib_insync for direct API calls.
"""

import json
from pathlib import Path
import logging
from datetime import datetime
import time

# Try to import ib_insync
try:
    from ib_insync import IB, Bag, Contract, Order, LimitOrder, MarketOrder
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False
    print("❌ ib_insync not installed. Install: pip install ib_insync")

LOG_DIR = Path.home() / ".openclaw" / "workspace" / "trading" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "direct_premium_executor.log"

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DirectPremiumExecutor:
    """Execute premium selling signals directly against IBKR."""
    
    def __init__(self):
        self.ib = None
        self.signals_file = Path.home() / ".openclaw" / "workspace" / "trading" / "premium_signals_filtered.json"
        self.execution_log = []
        
        if IB_AVAILABLE:
            self.ib = IB()
        else:
            logger.error("ib_insync not available - cannot execute")
    
    def connect(self):
        """Connect to IB Gateway."""
        try:
            if not self.ib:
                logger.error("IB instance not initialized")
                return False
            
            # Connect to IB Gateway (paper trading)
            self.ib.connect('127.0.0.1', 4002, clientId=1)
            logger.info("✓ Connected to IB Gateway")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to IB Gateway: {e}")
            return False
    
    def load_signals(self):
        """Load filtered premium signals."""
        try:
            with open(self.signals_file, "r") as f:
                data = json.load(f)
            return data.get("signals", [])
        except Exception as e:
            logger.error(f"Failed to load signals: {e}")
            return []
    
    def create_options_contract(self, signal):
        """Create an options contract from a premium signal."""
        try:
            symbol = signal["symbol"]
            strike = signal["strike"]
            dte = signal["dte"]
            option_type = "P" if signal["type"] == "SELL_PUT" else "C"
            
            # Find expiration date (approximately 45 DTE from now)
            from datetime import datetime, timedelta
            exp_date = datetime.now() + timedelta(days=dte)
            exp_str = exp_date.strftime("%Y%m%d")
            
            # Create option contract
            # Note: Use lastTradeDateOrContractMonth, not expiration
            contract = Contract(
                symbol=symbol,
                secType="OPT",
                exchange="SMART",
                strike=strike,
                right=option_type,
                lastTradeDateOrContractMonth=exp_str,
                currency="USD"
            )
            
            return contract
        except Exception as e:
            logger.error(f"Failed to create contract for {signal['symbol']}: {e}")
            return None
    
    def place_order(self, contract, signal):
        """Place a sell-to-open order."""
        try:
            if not self.ib or not self.ib.isConnected():
                logger.error("Not connected to IB Gateway")
                return False
            
            symbol = signal["symbol"]
            option_type = "PUT" if signal["type"] == "SELL_PUT" else "CALL"
            contracts = signal["contracts"]
            
            # Create market order to sell (negative quantity = sell)
            order = MarketOrder("SELL", contracts)
            
            logger.info(f"Placing order: SELL {contracts} {symbol} {option_type} ${signal['strike']} @ {signal['premium_pct']:.2f}%")
            
            # Submit order
            trade = self.ib.placeOrder(contract, order)
            
            # Wait briefly for order submission
            time.sleep(0.5)
            
            # PendingSubmit is normal - order is queued for submission
            if trade.orderStatus.status in ["PendingSubmit", "Submitted", "PreSubmitted", "Filled"]:
                logger.info(f"✓ Order submitted: {symbol} - Order ID: {trade.order.orderId} - Status: {trade.orderStatus.status}")
                self.execution_log.append({
                    "symbol": symbol,
                    "type": signal["type"],
                    "strike": signal["strike"],
                    "contracts": contracts,
                    "premium_pct": signal["premium_pct"],
                    "status": "SUBMITTED",
                    "order_id": trade.order.orderId,
                    "order_status": trade.orderStatus.status,
                    "timestamp": datetime.now().isoformat(),
                })
                return True
            else:
                logger.warning(f"✗ Order failed: {symbol} - Status: {trade.orderStatus.status}")
                self.execution_log.append({
                    "symbol": symbol,
                    "type": signal["type"],
                    "status": "FAILED",
                    "error": trade.orderStatus.status,
                    "timestamp": datetime.now().isoformat(),
                })
                return False
                
        except Exception as e:
            logger.error(f"✗ Error placing order for {signal['symbol']}: {e}")
            self.execution_log.append({
                "symbol": signal["symbol"],
                "type": signal["type"],
                "status": "ERROR",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            })
            return False
    
    def execute_all_signals(self, signals):
        """Execute all signals."""
        logger.info(f"=== EXECUTING {len(signals)} PREMIUM SIGNALS (DIRECT IBKR) ===")
        
        successful = 0
        failed = 0
        
        for signal in signals:
            contract = self.create_options_contract(signal)
            if contract:
                if self.place_order(contract, signal):
                    successful += 1
                else:
                    failed += 1
                time.sleep(0.2)  # Brief pause between orders
            else:
                failed += 1
        
        logger.info(f"Execution complete: {successful} successful, {failed} failed")
        return successful, failed
    
    def save_execution_log(self):
        """Save execution results."""
        log_file = Path.home() / ".openclaw" / "workspace" / "trading" / "direct_execution_results.json"
        
        try:
            with open(log_file, "w") as f:
                json.dump({
                    "execution_time": datetime.now().isoformat(),
                    "total": len(self.execution_log),
                    "submitted": len([e for e in self.execution_log if e["status"] == "SUBMITTED"]),
                    "failed": len([e for e in self.execution_log if e["status"] == "FAILED"]),
                    "errors": len([e for e in self.execution_log if e["status"] == "ERROR"]),
                    "executions": self.execution_log,
                }, f, indent=2)
            logger.info(f"Execution log saved to {log_file}")
        except Exception as e:
            logger.error(f"Failed to save execution log: {e}")
    
    def disconnect(self):
        """Disconnect from IB Gateway."""
        try:
            if self.ib and self.ib.isConnected():
                self.ib.disconnect()
                logger.info("Disconnected from IB Gateway")
        except Exception as e:
            logger.warning(f"Error disconnecting: {e}")
    
    def run(self):
        """Execute signals."""
        logger.info("=== DIRECT PREMIUM EXECUTOR STARTED ===")
        
        if not IB_AVAILABLE:
            logger.error("ib_insync not available - cannot execute")
            return
        
        if not self.connect():
            logger.error("Failed to connect to IB Gateway")
            return
        
        try:
            signals = self.load_signals()
            if not signals:
                logger.info("No signals to execute")
                return
            
            logger.info(f"Loaded {len(signals)} signals for execution")
            self.execute_all_signals(signals)
            self.save_execution_log()
            
        finally:
            self.disconnect()
        
        logger.info("=== DIRECT PREMIUM EXECUTOR COMPLETE ===")

def main():
    executor = DirectPremiumExecutor()
    executor.run()

if __name__ == "__main__":
    main()
