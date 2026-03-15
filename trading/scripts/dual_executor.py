#!/usr/bin/env python3
"""
Dual Executor - Auto-executes BOTH swing trades and options
Same screener output, split execution strategy
"""

import json
import os
import pandas as pd
from ib_insync import IB, Stock, Option, MarketOrder
from pathlib import Path
import logging
from datetime import datetime
import asyncio
from paths import TRADING_DIR, LOGS_DIR

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
        logging.FileHandler(LOGS_DIR / "dual_executor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

CANDIDATES_FILE = TRADING_DIR / "screener_candidates.json"
EXECUTION_LOG = LOGS_DIR / "dual_executions.json"

class DualExecutor:
    """Execute both swing trades and options from same candidates"""
    
    def __init__(self):
        self.ib = IB()
        self.executions = []
        self.account_equity = 100000.0  # Estimate
    
    async def connect(self):
        """Connect to IBKR"""
        try:
            await self.ib.connectAsync(os.getenv("IB_HOST", "127.0.0.1"), int(os.getenv("IB_PORT", "4001")), clientId=106)
            logger.info("✅ Connected to IBKR")
            return True
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
    
    def load_candidates(self):
        """Load screener candidates"""
        if not CANDIDATES_FILE.exists():
            logger.error("Candidates file not found")
            return []
        
        with open(CANDIDATES_FILE, 'r') as f:
            data = json.load(f)
        
        candidates = data.get('tier_2', []) + data.get('tier_3', [])
        logger.info(f"Loaded {len(candidates)} candidates")
        return candidates[:10]  # Execute top 10
    
    async def execute_swing_trade(self, candidate):
        """Execute swing trade (buy/sell stock or ETF)"""
        try:
            symbol = candidate['symbol']
            momentum = candidate['momentum']
            
            # Determine action
            action = 'BUY' if momentum > 0 else 'SELL'
            
            # Create contract
            contract = Stock(symbol, 'SMART', 'USD')
            contracts = await self.ib.qualifyContractsAsync(contract)
            
            if not contracts:
                logger.warning(f"  {symbol}: Contract qualification failed")
                return False
            
            contract = contracts[0]
            
            # Place order
            order = MarketOrder(action, 1)  # 1 share
            trade = self.ib.placeOrder(contract, order)
            
            logger.info(f"  ✅ SWING: {symbol} | {action} 1 share | Order ID: {trade.order.orderId}")
            
            self.executions.append({
                'type': 'SWING',
                'symbol': symbol,
                'action': action,
                'quantity': 1,
                'orderId': trade.order.orderId,
                'timestamp': datetime.now().isoformat()
            })
            
            return True
        
        except Exception as e:
            logger.error(f"  ❌ SWING {candidate['symbol']}: {e}")
            return False
    
    async def execute_options_trade(self, candidate):
        """Execute options trade (buy put/call)"""
        try:
            symbol = candidate['symbol']
            momentum = candidate['momentum']
            price = candidate['price']
            
            # Determine option strategy
            if momentum > 0:
                # Bullish: buy CALL
                right = 'CALL'
                strike = round(price * 1.02)  # 2% above current
            else:
                # Bearish: buy PUT
                right = 'PUT'
                strike = round(price * 0.98)  # 2% below current
            
            # Create contract
            option = Option(symbol, '20260313', strike, right)
            contracts = await self.ib.qualifyContractsAsync(option)
            
            if not contracts:
                logger.warning(f"  {symbol}: Option contract not found")
                return False
            
            option = contracts[0]
            
            # Place order
            order = MarketOrder('BUY', 1)  # 1 contract
            trade = self.ib.placeOrder(option, order)
            
            logger.info(f"  ✅ OPTIONS: {symbol} | BUY 1 {right} {strike} | Order ID: {trade.order.orderId}")
            
            self.executions.append({
                'type': 'OPTIONS',
                'symbol': symbol,
                'contract': right,
                'strike': strike,
                'quantity': 1,
                'orderId': trade.order.orderId,
                'timestamp': datetime.now().isoformat()
            })
            
            return True
        
        except Exception as e:
            logger.error(f"  ❌ OPTIONS {candidate['symbol']}: {e}")
            return False
    
    async def run(self):
        """Run dual executor"""
        logger.info("=" * 60)
        logger.info("DUAL EXECUTOR - SWING TRADES + OPTIONS")
        logger.info("=" * 60)
        
        if not await self.connect():
            return False
        
        candidates = self.load_candidates()
        
        if not candidates:
            logger.info("No candidates to execute")
            self.ib.disconnect()
            return True
        
        logger.info(f"Executing {len(candidates)} candidates (both swing + options)...")
        logger.info("")
        
        for candidate in candidates:
            symbol = candidate['symbol']
            logger.info(f"{symbol}:")
            
            # Execute swing trade
            await self.execute_swing_trade(candidate)
            await asyncio.sleep(0.5)
            
            # Execute options trade
            await self.execute_options_trade(candidate)
            await asyncio.sleep(0.5)
        
        # Save execution log
        with open(EXECUTION_LOG, 'a') as f:
            for exec_data in self.executions:
                f.write(json.dumps(exec_data) + '\n')
        
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"DUAL EXECUTION COMPLETE")
        logger.info(f"Swing trades: {len([e for e in self.executions if e['type'] == 'SWING'])}")
        logger.info(f"Options trades: {len([e for e in self.executions if e['type'] == 'OPTIONS'])}")
        logger.info(f"Total: {len(self.executions)}")
        logger.info("=" * 60)
        
        self.ib.disconnect()
        return True

async def main():
    executor = DualExecutor()
    await executor.run()

if __name__ == "__main__":
    asyncio.run(main())
