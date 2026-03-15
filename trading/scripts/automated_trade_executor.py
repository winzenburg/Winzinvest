#!/usr/bin/env python3
"""
Automated Trade Executor
Executes trades automatically based on screener modes (strategy-driven)

Modes:
  Mode 2 (Premium Selling): Sell CSPs on high-IV weakness
  Mode 3 (Short Opportunities): Buy puts on downtrend confirmation

Execution Rules:
  - CSP: Sell at support levels, collect premium
  - Put: Buy ATM or 1-strike down, hedge downtrend
  - Expiry: Next Friday (7 days out)
  - Quantity: Conservative (1-2 contracts per trade)
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
import logging
from paths import TRADING_DIR, LOGS_DIR

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / "automated_executor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Paths
WORKSPACE = TRADING_DIR
SCREENER_OUTPUT = WORKSPACE / "watchlist_multimode.json"
EXECUTION_LOG = WORKSPACE / "logs" / "execution_log.json"

# Automation Rules
AUTOMATION_RULES = {
    "mode_2_premium_selling": {
        "name": "Premium Selling (High-IV Weakness)",
        "enabled": True,
        "trade_type": "sell_csp",
        "candidates": ["AAPL", "MSFT", "NVDA", "GOOGL", "TSLA"],
        "strike_offset": -1,  # 1 strike below current price
        "expiry_days": 7,  # Next Friday
        "max_contracts_per_trade": 1,
        "condition": "recent_weakness > 5%",
    },
    
    "mode_3_short_opportunities": {
        "name": "Short Opportunities (Downtrend)",
        "enabled": True,
        "trade_type": "buy_put",
        "candidates": ["AAPL", "MSFT", "NVDA", "GOOGL", "TSLA", "QQQ"],
        "strike_offset": 0,  # ATM
        "expiry_days": 7,  # Next Friday
        "max_contracts_per_trade": 1,
        "condition": "price < 100ma AND price < 50ma",
    }
}

def load_screener_output():
    """Load latest screener results."""
    try:
        with open(SCREENER_OUTPUT, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load screener output: {e}")
        return {}

def calculate_strike(symbol, current_price, offset, trade_type):
    """
    Calculate strike price based on offset.
    
    offset = -2 → 2 strikes down (cheaper puts, lower probability)
    offset = -1 → 1 strike down
    offset = 0 → ATM (at-the-money)
    """
    # Standard option strike spacing
    strike_spacing = {
        "low": 0.5,      # Under $25
        "mid": 1.0,      # $25-$100
        "high": 5.0,     # $100+
    }
    
    if current_price < 25:
        spacing = strike_spacing["low"]
    elif current_price < 100:
        spacing = strike_spacing["mid"]
    else:
        spacing = strike_spacing["high"]
    
    strike = current_price + (offset * spacing)
    
    # Round to nearest valid strike
    if strike < 10:
        strike = round(strike * 2) / 2  # $0.50 increments
    else:
        strike = round(strike)
    
    return max(strike, 1.0)  # Prevent invalid strikes

def generate_trades(screener_data):
    """Generate trades based on screener output and rules."""
    trades = []
    
    try:
        # Mode 2: Premium Selling (Sell CSPs on weakness)
        if "modes" in screener_data and "premium_selling" in screener_data["modes"]:
            mode2_data = screener_data["modes"]["premium_selling"]
            
            if mode2_data.get("short") and AUTOMATION_RULES["mode_2_premium_selling"]["enabled"]:
                logger.info(f"Processing Mode 2 (Premium Selling): {len(mode2_data['short'])} candidates")
                
                for candidate in mode2_data["short"][:2]:  # Limit to top 2
                    symbol = candidate["symbol"]
                    price = candidate["price"]
                    recent_return = candidate["recent_return"]
                    
                    # Check condition: weakness > 5%
                    if recent_return < -0.05:
                        strike = calculate_strike(symbol, price, offset=-1, trade_type="csp")
                        
                        trade = {
                            "timestamp": datetime.now().isoformat(),
                            "mode": "Premium Selling",
                            "type": "Sell CSP",
                            "symbol": symbol,
                            "current_price": round(price, 2),
                            "strike": strike,
                            "contracts": 1,
                            "expiry": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
                            "reason": f"Weakness {recent_return*100:.1f}%, elevated IV",
                            "status": "READY_TO_EXECUTE"
                        }
                        trades.append(trade)
                        logger.info(f"✅ CSP Trade: {symbol} ${strike} x1")
        
        # Mode 3: Short Opportunities (Buy Puts)
        if "modes" in screener_data and "short_opportunities" in screener_data["modes"]:
            mode3_data = screener_data["modes"]["short_opportunities"]
            
            if mode3_data.get("short") and AUTOMATION_RULES["mode_3_short_opportunities"]["enabled"]:
                logger.info(f"Processing Mode 3 (Short Opportunities): {len(mode3_data['short'])} candidates")
                
                for candidate in mode3_data["short"][:1]:  # Limit to top 1
                    symbol = candidate["symbol"]
                    price = candidate["price"]
                    price_vs_50ma = candidate["price_vs_50ma"]
                    price_vs_100ma = candidate["price_vs_100ma"]
                    
                    # Check condition: below both MAs
                    if price_vs_50ma < 1.0 and price_vs_100ma < 1.0:
                        strike = calculate_strike(symbol, price, offset=0, trade_type="put")
                        
                        trade = {
                            "timestamp": datetime.now().isoformat(),
                            "mode": "Short Opportunities",
                            "type": "Buy Put",
                            "symbol": symbol,
                            "current_price": round(price, 2),
                            "strike": strike,
                            "contracts": 1,
                            "expiry": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
                            "reason": f"Below 50MA ({price_vs_50ma:.3f}) & 100MA ({price_vs_100ma:.3f})",
                            "status": "READY_TO_EXECUTE"
                        }
                        trades.append(trade)
                        logger.info(f"✅ Put Trade: {symbol} ${strike} x1")
    
    except Exception as e:
        logger.error(f"Error generating trades: {e}")
    
    return trades

def log_execution(trades):
    """Log generated trades for execution."""
    try:
        log_data = {
            "generated_at": datetime.now().isoformat(),
            "total_trades": len(trades),
            "trades": trades
        }
        
        with open(EXECUTION_LOG, 'w') as f:
            json.dump(log_data, f, indent=2)
        
        logger.info(f"📋 Logged {len(trades)} trades for execution")
        return log_data
    
    except Exception as e:
        logger.error(f"Failed to log execution: {e}")
        return {}

def main():
    """Main execution flow."""
    logger.info("=== AUTOMATED TRADE EXECUTOR ===")
    logger.info(f"Paper Trading Mode: ENABLED")
    
    # Load screener output
    screener_data = load_screener_output()
    
    if not screener_data:
        logger.error("No screener output available")
        return
    
    # Generate trades based on rules
    trades = generate_trades(screener_data)
    
    if not trades:
        logger.info("No trades match criteria")
        return
    
    # Log for execution
    execution_log = log_execution(trades)
    
    logger.info(f"=== {len(trades)} TRADES READY ===")
    logger.info("Status: PAPER_TRADING")
    logger.info("Next: Manual execution in paper account or live IB Gateway")

if __name__ == "__main__":
    main()
