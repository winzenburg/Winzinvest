#!/usr/bin/env python3
"""
Execute High-IV CSP Candidates
Reads high_iv_candidates.json and executes qualifying trades via IB.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from ib_insync import IB, Stock, Option, MarketOrder
import logging

# Setup logging
LOG_DIR = Path.home() / ".openclaw" / "workspace" / "trading" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "high_iv_execution.log"

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Paths
CANDIDATES_FILE = Path.home() / ".openclaw" / "workspace" / "trading" / "high_iv_candidates.json"
IB_HOST = os.getenv('IB_HOST', '127.0.0.1')
IB_PORT = int(os.getenv('IB_PORT', 4002))

def load_candidates():
    """Load high-IV CSP candidates."""
    try:
        if CANDIDATES_FILE.exists():
            with open(CANDIDATES_FILE) as f:
                data = json.load(f)
            return data.get('candidates', [])
        return []
    except Exception as e:
        logger.error(f"Failed to load candidates: {e}")
        return []

def execute_csp_trade(ib, symbol, strike, dte):
    """Execute a cash-secured put trade."""
    try:
        # Create put contract
        contract = Option(
            symbol=symbol,
            lastTradeDateOrContractMonth=None,  # IB will find appropriate expiry
            strike=strike,
            right='P',
            exchange='SMART'
        )
        
        # Qualify contract
        ib.qualifyContracts(contract)
        
        # Get current market data
        ib.reqMktData(contract, '', False, False)
        ib.sleep(0.5)
        
        # Create sell order (we're SELLING puts)
        order = MarketOrder('SELL', 1)  # 1 contract
        
        # Place order
        trade = ib.placeOrder(contract, order)
        logger.info(f"Order placed: {symbol} ${strike} Put")
        logger.info(f"Trade: {trade}")
        
        return trade
        
    except Exception as e:
        logger.error(f"Failed to execute {symbol} ${strike} put: {e}")
        return None

def main():
    logger.info("=== HIGH-IV CSP EXECUTOR STARTED ===")
    
    # Load candidates
    candidates = load_candidates()
    if not candidates:
        logger.info("No high-IV candidates to execute")
        return
    
    logger.info(f"Found {len(candidates)} candidates to execute")
    
    # Connect to IB
    try:
        ib = IB()
        ib.connect(IB_HOST, IB_PORT, clientId=104)  # Dedicated client ID for high-IV execution
        logger.info("✅ Connected to IB Gateway")
    except Exception as e:
        logger.error(f"Failed to connect to IB: {e}")
        return
    
    # Execute each candidate
    executed = 0
    for candidate in candidates:
        symbol = candidate.get('symbol')
        strike = candidate.get('strike')
        premium = candidate.get('premium_pct')
        
        logger.info(f"Executing: {symbol} ${strike} Put @ {premium}% premium")
        
        trade = execute_csp_trade(ib, symbol, strike, 40)
        if trade:
            executed += 1
    
    logger.info(f"Executed {executed}/{len(candidates)} trades")
    
    # Disconnect
    ib.disconnect()
    logger.info("=== HIGH-IV CSP EXECUTOR COMPLETE ===")

if __name__ == "__main__":
    main()
