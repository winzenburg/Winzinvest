#!/usr/bin/env python3
"""
Options Executor with Risk Management
All trades validated against risk limits before execution.
"""

import sys
sys.path.insert(0, '/Users/pinchy/.openclaw/workspace/trading/scripts')

from risk_manager import RiskManager
from profitability_filters import ProfitabilityFilters
import json
from pathlib import Path
from ib_insync import IB, Stock, Option, MarketOrder
import logging

# Setup logging
LOG_DIR = Path.home() / ".openclaw" / "workspace" / "trading" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "executor_with_risk.log"

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ExecutorWithRisk:
    """
    Options executor that enforces risk management rules.
    """
    
    def __init__(self):
        self.rm = RiskManager()
        logger.info("Executor with Risk Management initialized")
    
    def can_execute_trade(self) -> tuple[bool, str]:
        """Check if we're allowed to execute any trade."""
        can_trade, reason = self.rm.check_can_trade()
        if not can_trade:
            logger.error(f"TRADE BLOCKED: {reason}")
        return can_trade, reason
    
    def validate_csp_trade(self, symbol: str, strike: float, qty: int = 1) -> tuple[bool, str]:
        """
        Validate cash-secured put trade before execution.
        
        Args:
            symbol: Stock symbol (e.g., 'GS')
            strike: Put strike price
            qty: Number of contracts (default 1)
        
        Returns:
            (is_valid: bool, reason: str)
        """
        # CSP requires capital = strike × 100 × qty
        capital_required = strike * 100 * qty
        
        # Risk = strike × 100 × qty (if exercised)
        is_valid, adjusted_qty, msg = self.rm.validate_position_size(
            symbol, 
            qty, 
            strike,
            strike * 0.95  # Assume 5% stop-loss below strike
        )
        
        if not is_valid:
            logger.warning(f"CSP validation failed for {symbol}: {msg}")
            return False, msg
        
        # Check if we can trade
        can_trade, reason = self.can_execute_trade()
        if not can_trade:
            return False, reason
        
        logger.info(f"✅ CSP {symbol} ${strike} validated (qty: {adjusted_qty})")
        return True, "Validated"
    
    def execute_trade(self, symbol: str, strike: float, side: str = 'SELL', order_type: str = 'PUT') -> bool:
        """
        Execute a validated trade.
        
        Returns:
            True if executed, False otherwise
        """
        try:
            # Final check before execution
            can_trade, reason = self.can_execute_trade()
            if not can_trade:
                logger.error(f"Execution blocked: {reason}")
                return False
            
            ib = IB()
            ib.connect('127.0.0.1', 4002, clientId=108)
            
            # Create option contract
            contract = Option(
                symbol=symbol,
                strike=strike,
                right=order_type.upper(),
                exchange='SMART'
            )
            
            # Create order
            order = MarketOrder(side, 1)
            
            # Place order
            trade = ib.placeOrder(contract, order)
            logger.info(f"✅ EXECUTED: {side} {symbol} ${strike} {order_type.upper()}")
            
            ib.disconnect()
            return True
            
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return False
    
    def monitor_positions(self):
        """Monitor open positions for stop-loss and profit-taking."""
        try:
            portfolio_file = Path.home() / ".openclaw" / "workspace" / "trading" / "portfolio.json"
            
            if not portfolio_file.exists():
                return
            
            with open(portfolio_file) as f:
                portfolio = json.load(f)
            
            logger.info("=== POSITION MONITORING ===")
            
            for pos in portfolio.get('positions', []):
                symbol = pos['symbol']
                qty = pos['quantity']
                entry = pos.get('avg_cost', 0)
                current = pos.get('current_price', 0)
                
                if qty == 0 or not current:
                    continue
                
                # Check profit-taking
                should_take, close_qty, reason = self.rm.check_profit_taking(symbol, entry, current, qty)
                if should_take:
                    logger.info(f"{symbol}: {reason}")
                
                # Check stop-loss
                should_stop, stop_qty, reason = self.rm.check_stop_loss(symbol, entry, current, qty)
                if should_stop:
                    logger.error(f"{symbol}: {reason}")
        
        except Exception as e:
            logger.error(f"Monitoring error: {e}")

def main():
    executor = ExecutorWithRisk()
    
    # Generate risk report
    print(executor.rm.generate_report())
    
    # Test: Can we execute a trade?
    can_execute, reason = executor.can_execute_trade()
    print(f"\nCan execute trade: {can_execute} ({reason})")
    
    # Test: Validate a CSP trade
    is_valid, msg = executor.validate_csp_trade('GS', 822, qty=1)
    print(f"CSP GS $822 valid: {is_valid} ({msg})")
    
    # Monitor positions
    executor.monitor_positions()

if __name__ == "__main__":
    main()
