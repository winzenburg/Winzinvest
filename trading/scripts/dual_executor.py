#!/usr/bin/env python3
"""
Dual Executor - Auto-executes BOTH swing trades and options
Same screener output, split execution strategy
"""

import json
import os
import time
import pandas as pd
from ib_insync import IB, Stock, Option, MarketOrder
from pathlib import Path
import logging
from datetime import datetime
import asyncio
from typing import Tuple

from paths import TRADING_DIR, LOGS_DIR
from kill_switch_guard import kill_switch_active

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

_FILL_WAIT_SEC = int(os.environ.get("IB_ORDER_FILL_WAIT_SEC", "30"))


async def _wait_order_filled(ib: IB, trade, max_sec: int = _FILL_WAIT_SEC) -> Tuple[bool, str]:
    """Poll until Filled/PartiallyFilled or timeout (async-friendly sleep)."""
    deadline = time.time() + float(max_sec)
    while time.time() < deadline:
        await asyncio.sleep(0.5)
        status = getattr(trade.orderStatus, "status", "") or ""
        if status in ("Filled", "PartiallyFilled"):
            return True, status
    status = getattr(trade.orderStatus, "status", "") or ""
    return False, status


class DualExecutor:
    """Execute both swing trades and options from same candidates"""
    
    def __init__(self):
        self.ib = IB()
        self.executions = []
        self.account_equity = 100000.0  # Estimate
    
    async def connect(self):
        """Connect to IBKR"""
        try:
            # clientId 106 is reserved for agents/risk_monitor.py — use 123 (legacy pool, see 030-ib-client-ids.mdc)
            await self.ib.connectAsync(os.getenv("IB_HOST", "127.0.0.1"), int(os.getenv("IB_PORT", "4001")), clientId=123)
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
            if kill_switch_active():
                logger.error("Kill switch active — skipping swing trade")
                return False
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
            filled, st = await _wait_order_filled(self.ib, trade)
            if not filled:
                logger.warning(
                    "  ⚠️ SWING: %s | %s 1 share | not filled within %ss (status=%s) orderId=%s",
                    symbol, action, _FILL_WAIT_SEC, st, trade.order.orderId,
                )
                return False

            logger.info(
                "  ✅ SWING: %s | %s 1 share | %s | Order ID: %s",
                symbol, action, st, trade.order.orderId,
            )

            self.executions.append({
                "type": "SWING",
                "symbol": symbol,
                "action": action,
                "quantity": 1,
                "orderId": trade.order.orderId,
                "orderStatus": st,
                "timestamp": datetime.now().isoformat(),
            })

            return True
        
        except Exception as e:
            logger.error(f"  ❌ SWING {candidate['symbol']}: {e}")
            return False
    
    async def execute_options_trade(self, candidate):
        """Execute options trade (buy put/call)"""
        try:
            if kill_switch_active():
                logger.error("Kill switch active — skipping options trade")
                return False
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
            order = MarketOrder("BUY", 1)  # 1 contract
            trade = self.ib.placeOrder(option, order)
            filled, st = await _wait_order_filled(self.ib, trade)
            if not filled:
                logger.warning(
                    "  ⚠️ OPTIONS: %s | BUY 1 %s %s | not filled within %ss (status=%s) orderId=%s",
                    symbol, right, strike, _FILL_WAIT_SEC, st, trade.order.orderId,
                )
                return False

            logger.info(
                "  ✅ OPTIONS: %s | BUY 1 %s %s | %s | Order ID: %s",
                symbol, right, strike, st, trade.order.orderId,
            )

            self.executions.append({
                "type": "OPTIONS",
                "symbol": symbol,
                "contract": right,
                "strike": strike,
                "quantity": 1,
                "orderId": trade.order.orderId,
                "orderStatus": st,
                "timestamp": datetime.now().isoformat(),
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

        try:
            candidates = self.load_candidates()

            if not candidates:
                logger.info("No candidates to execute")
                return True

            logger.info("Executing %d candidates (both swing + options)...", len(candidates))
            logger.info("")

            for candidate in candidates:
                symbol = candidate["symbol"]
                logger.info("%s:", symbol)
                await self.execute_swing_trade(candidate)
                await asyncio.sleep(0.5)
                await self.execute_options_trade(candidate)
                await asyncio.sleep(0.5)

            with open(EXECUTION_LOG, "a") as f:
                for exec_data in self.executions:
                    f.write(json.dumps(exec_data) + "\n")

            logger.info("")
            logger.info("=" * 60)
            logger.info("DUAL EXECUTION COMPLETE")
            logger.info(
                "Swing trades: %d",
                len([e for e in self.executions if e["type"] == "SWING"]),
            )
            logger.info(
                "Options trades: %d",
                len([e for e in self.executions if e["type"] == "OPTIONS"]),
            )
            logger.info("Total: %d", len(self.executions))
            logger.info("=" * 60)
            return True
        finally:
            try:
                if self.ib.isConnected():
                    self.ib.disconnect()
            except Exception as exc:
                logger.warning("IB disconnect: %s", exc)

async def main():
    executor = DualExecutor()
    await executor.run()

if __name__ == "__main__":
    asyncio.run(main())
