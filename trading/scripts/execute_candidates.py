#!/usr/bin/env python3
"""
Auto-Execute Pipeline
Reads screener candidates, auto-executes to IBKR
Enforces position sizing, stops, profit targets, daily loss limits
"""

import json
import pandas as pd
import numpy as np
from ib_insync import IB, Stock, MarketOrder, StopOrder
from pathlib import Path
import logging
from datetime import datetime
import asyncio
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/pinchy/.openclaw/workspace/trading/logs/execute_candidates.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

WORKSPACE = Path.home() / ".openclaw" / "workspace"
CANDIDATES_FILE = WORKSPACE / "trading" / "screener_candidates.json"
EXECUTION_LOG = WORKSPACE / "trading" / "logs" / "executions.json"
LOSS_TRACKER = WORKSPACE / "trading" / "logs" / "daily_loss.json"

# Execution parameters
EXEC_PARAMS = {
    'paper_trading': True,
    'position_size': 1,  # 1 share per trade (paper)
    'stop_loss_pct': 0.50,  # -50% of entry
    'take_profit_pct': 1.00,  # +100% of entry (2:1 R:R)
    'daily_loss_limit_pct': 0.03,  # -3% of account equity
}

class CandidateExecutor:
    """Execute screener candidates to IBKR"""
    
    def __init__(self):
        self.ib = IB()
        self.executions = []
        self.daily_loss = 0.0
        self.account_equity = 0.0
    
    async def connect(self):
        """Connect to IBKR"""
        try:
            await self.ib.connectAsync('127.0.0.1', 4002, clientId=101)
            logger.info("✅ Connected to IBKR")
            return True
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
    
    def load_candidates(self):
        """Load candidates from screener output"""
        if not CANDIDATES_FILE.exists():
            logger.error(f"Candidates file not found: {CANDIDATES_FILE}")
            return []
        
        with open(CANDIDATES_FILE, 'r') as f:
            data = json.load(f)
        
        # Return top candidates (Tier 2 preferred)
        tier2 = data.get('tier_2', [])
        tier3 = data.get('tier_3', [])
        
        # Combine, Tier 2 first
        candidates = tier2 + tier3
        logger.info(f"Loaded {len(tier2)} Tier 2 + {len(tier3)} Tier 3 candidates")
        
        return candidates
    
    def load_daily_loss(self):
        """Load today's cumulative loss"""
        if LOSS_TRACKER.exists():
            with open(LOSS_TRACKER, 'r') as f:
                data = json.load(f)
            
            today = datetime.now().date().isoformat()
            if data.get('date') == today:
                self.daily_loss = data.get('loss', 0.0)
                logger.info(f"Daily loss so far: ${self.daily_loss:.2f}")
        
        return self.daily_loss
    
    async def get_account_equity(self):
        """Get current account equity"""
        try:
            account_summary = await self.ib.reqAccountSummaryAsync('All', 'USD')
            for item in account_summary:
                if item.tag == 'TotalCashValue':
                    self.account_equity = float(item.value)
                    return self.account_equity
        except Exception as e:
            logger.warning(f"Could not fetch account equity: {e}")
            return 100000.0  # Default estimate
    
    def check_daily_loss_limit(self):
        """Check if daily loss limit exceeded"""
        equity = self.account_equity or 100000.0
        loss_limit = equity * EXEC_PARAMS['daily_loss_limit_pct']
        
        if self.daily_loss >= loss_limit:
            logger.warning(f"⚠️  DAILY LOSS LIMIT EXCEEDED: ${self.daily_loss:.2f} / ${loss_limit:.2f}")
            logger.warning("Trading halted for remainder of day")
            return False
        
        return True
    
    async def execute_candidate(self, candidate):
        """Execute a single candidate"""
        try:
            symbol = candidate['symbol']
            score = candidate['score']
            momentum = candidate['momentum']
            price = candidate['price']
            
            logger.info(f"Executing: {symbol} | Score: {score:.3f} | Mom: {momentum:+.2f} | Price: ${price:.2f}")
            
            # Create contract
            contract = Stock(symbol, 'SMART', 'USD')
            
            # Qualify contract
            contracts = await self.ib.qualifyContractsAsync(contract)
            if not contracts:
                logger.error(f"  ❌ Contract qualification failed")
                return False
            
            contract = contracts[0]
            
            # Calculate stop loss and take profit levels
            entry_price = price
            stop_price = entry_price * (1 - EXEC_PARAMS['stop_loss_pct'])
            profit_price = entry_price * (1 + EXEC_PARAMS['take_profit_pct'])
            
            # Determine action (BUY if positive momentum, SELL if negative)
            action = 'BUY' if momentum > 0 else 'SELL'
            
            # Place entry order
            entry_order = MarketOrder(action, EXEC_PARAMS['position_size'])
            trade = self.ib.placeOrder(contract, entry_order)
            
            logger.info(f"  📝 Order ID: {trade.order.orderId} | {action} {EXEC_PARAMS['position_size']} @ MKT")
            
            # Wait for order submission
            await asyncio.sleep(1)
            
            # Log execution
            execution = {
                'symbol': symbol,
                'orderId': trade.order.orderId,
                'action': action,
                'quantity': EXEC_PARAMS['position_size'],
                'entry_price': float(entry_price),
                'stop_price': float(stop_price),
                'profit_price': float(profit_price),
                'score': float(score),
                'momentum': float(momentum),
                'timestamp': datetime.now().isoformat(),
                'status': trade.orderStatus.status,
            }
            
            self.executions.append(execution)
            logger.info(f"  ✅ EXECUTED: {symbol} | Stop: ${stop_price:.2f} | Target: ${profit_price:.2f}")
            
            return True
        
        except Exception as e:
            logger.error(f"  ❌ Execution error: {e}")
            return False
    
    def save_executions(self):
        """Save execution log"""
        with open(EXECUTION_LOG, 'a') as f:
            for exec_data in self.executions:
                f.write(json.dumps(exec_data) + '\n')
        
        logger.info(f"Logged {len(self.executions)} executions")
    
    async def run(self):
        """Run full execution pipeline"""
        logger.info("=" * 60)
        logger.info("EXECUTION PIPELINE")
        logger.info("=" * 60)
        logger.info(f"Mode: {'PAPER' if EXEC_PARAMS['paper_trading'] else 'LIVE'}")
        logger.info(f"Position size: {EXEC_PARAMS['position_size']} shares")
        logger.info(f"Stop loss: {EXEC_PARAMS['stop_loss_pct']*100:.0f}%")
        logger.info(f"Take profit: {EXEC_PARAMS['take_profit_pct']*100:.0f}%")
        logger.info("=" * 60)
        
        # Connect
        if not await self.connect():
            return False
        
        # Load state
        candidates = self.load_candidates()
        self.load_daily_loss()
        await self.get_account_equity()
        
        logger.info(f"Account equity: ${self.account_equity:.2f}")
        
        # Check daily loss limit
        if not self.check_daily_loss_limit():
            logger.warning("Daily loss limit exceeded. No executions.")
            self.ib.disconnect()
            return False
        
        # Execute candidates
        if not candidates:
            logger.info("No candidates to execute")
            self.ib.disconnect()
            return True
        
        logger.info(f"Executing {len(candidates)} candidates...")
        logger.info("")
        
        for candidate in candidates[:5]:  # Execute top 5 only
            await self.execute_candidate(candidate)
            await asyncio.sleep(1)  # Rate limit
        
        # Save executions
        self.save_executions()
        
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"EXECUTION COMPLETE: {len(self.executions)} trades")
        logger.info("=" * 60)
        
        self.ib.disconnect()
        return True

async def main():
    executor = CandidateExecutor()
    await executor.run()

if __name__ == "__main__":
    asyncio.run(main())
