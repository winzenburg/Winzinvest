#!/usr/bin/env python3
"""
TradingView Alert Executor
Receives alerts from Pine Script, parses them, and executes trades
"""

import json
import logging
from datetime import datetime
from pathlib import Path
import sys
import asyncio

sys.path.insert(0, '/Users/pinchy/.openclaw/workspace/trading/scripts')
from ibkr_executor_insync import IBKRExecutorInsync

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/pinchy/.openclaw/workspace/trading/logs/tradingview_executor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TradingViewAlertParser:
    """Parse TradingView Pine Script alerts"""
    
    @staticmethod
    def parse_alert(alert_text):
        """
        Parse TradingView alert format:
        action: BUY/SELL
        symbol: AAPL
        price: 260.50
        message: [signal details]
        """
        try:
            lines = alert_text.strip().split('\n')
            data = {}
            
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    data[key.strip().lower()] = value.strip()
            
            logger.info(f"Parsed alert: {data}")
            return data
        except Exception as e:
            logger.error(f"Failed to parse alert: {e}")
            return None
    
    @staticmethod
    def alert_to_trade(alert_data):
        """Convert parsed alert to trade signal"""
        try:
            symbol = alert_data.get('symbol', '').upper()
            action = alert_data.get('action', '').upper()
            price = float(alert_data.get('price', 0))
            message = alert_data.get('message', '')
            
            # Determine contract type and strike
            # For now: assume PUT for SELL, CALL for BUY
            contract_type = 'PUT' if action == 'SELL' else 'CALL'
            
            # Strike calculation: near current price
            strike = round(price / 5) * 5  # Round to nearest $5
            
            trade = {
                'symbol': symbol,
                'type': action,
                'contract': contract_type,
                'strike': strike,
                'contracts': 1,
                'expiry': '2026-03-13',  # Next Friday
                'reason': message[:100]
            }
            
            logger.info(f"Converted to trade: {trade}")
            return trade
        except Exception as e:
            logger.error(f"Failed to convert alert to trade: {e}")
            return None


async def execute_tradingview_alert(alert_text):
    """Execute trade from TradingView alert"""
    
    logger.info("=" * 60)
    logger.info("Processing TradingView Alert")
    logger.info("=" * 60)
    
    # Parse alert
    parser = TradingViewAlertParser()
    alert_data = parser.parse_alert(alert_text)
    
    if not alert_data:
        logger.error("Failed to parse alert")
        return False
    
    # Convert to trade
    trade = parser.alert_to_trade(alert_data)
    
    if not trade:
        logger.error("Failed to convert alert to trade")
        return False
    
    # Execute trade
    logger.info(f"Executing: {trade['type']} {trade['symbol']} {trade['contract']} {trade['strike']}")
    
    executor = IBKRExecutorInsync(paper_trading=True, extended_hours=True)
    
    # Create temp file with trade
    trades_file = '/tmp/tv_alert_trade.json'
    with open(trades_file, 'w') as f:
        json.dump([trade], f)
    
    # Execute
    results = await executor.execute_trades(trades_file)
    
    # Log results
    success = any(r['status'] == 'EXECUTED' for r in results)
    
    if success:
        logger.info("✅ Trade executed successfully")
    else:
        logger.error("❌ Trade execution failed")
    
    return success


if __name__ == "__main__":
    if len(sys.argv) > 1:
        alert_text = ' '.join(sys.argv[1:])
        asyncio.run(execute_tradingview_alert(alert_text))
    else:
        print("Usage: tradingview_executor.py '<alert_text>'")
