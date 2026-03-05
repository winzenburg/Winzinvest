#!/usr/bin/env python3
"""
Contract Resolver - Maps trade signals to IBKR contract details
Queries IB Gateway to get proper contract IDs for options
"""

import logging
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
import threading
import time
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ContractResolverWrapper(EWrapper):
    """Handles contract details responses"""
    
    def __init__(self):
        self.contract_details = None
        self.request_id = None
        self.error_msg = None
    
    def contractDetails(self, reqId, contractDetails):
        """Receive contract details"""
        logger.info(f"✅ Contract found: {contractDetails.contract.symbol} {contractDetails.contract.localSymbol}")
        self.contract_details = contractDetails
    
    def contractDetailsEnd(self, reqId):
        """Contract details query complete"""
        logger.info("✅ Contract details received")
    
    def error(self, reqId, errorCode, errorString):
        """Error from contract query"""
        logger.error(f"❌ Contract lookup error [{errorCode}]: {errorString}")
        self.error_msg = errorString


class ContractResolver(EClient):
    """Resolves trade signals to IBKR contracts"""
    
    def __init__(self, wrapper, host="127.0.0.1", port=4002):
        EClient.__init__(self, wrapper)
        self.host = host
        self.port = port
        self.clientId = 1
        self._request_counter = 1
    
    def connect(self):
        """Connect to IB Gateway"""
        logger.info(f"Connecting to IB Gateway at {self.host}:{self.port}")
        super().connect(self.host, self.port, self.clientId)
        
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
        time.sleep(1)
        
        return self.isConnected()
    
    def resolve_option_contract(self, symbol, strike, right, expiry_yyyymmdd):
        """
        Query IB for option contract details
        
        Args:
            symbol: Underlying (e.g., "AAPL")
            strike: Strike price (e.g., 259)
            right: "CALL" or "PUT"
            expiry_yyyymmdd: Expiry date as YYYYMMDD (e.g., "20260312")
        
        Returns:
            Contract object if found, None otherwise
        """
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "OPT"
        contract.exchange = "SMART"
        contract.currency = "USD"
        contract.lastTradeDateOrContractMonth = expiry_yyyymmdd
        contract.strike = float(strike)
        contract.right = right
        # Note: Removed explicit multiplier - let IB infer it
        
        logger.info(f"🔍 Looking up: {symbol} {right} {strike} expiry {expiry_yyyymmdd}")
        
        # Request contract details
        self.wrapper.contract_details = None
        self.wrapper.error_msg = None
        
        reqId = self._request_counter
        self._request_counter += 1
        
        try:
            self.reqContractDetails(reqId, contract)
        except Exception as e:
            logger.error(f"Error requesting contract: {e}")
            return None
        
        # Wait for response (up to 3 seconds)
        start = time.time()
        while time.time() - start < 3:
            if self.wrapper.contract_details:
                logger.info(f"✅ Found contract: {self.wrapper.contract_details.contract.localSymbol}")
                return self.wrapper.contract_details.contract
            if self.wrapper.error_msg:
                logger.error(f"Contract lookup failed: {self.wrapper.error_msg}")
                return None
            time.sleep(0.1)
        
        logger.warning("⏱️  Contract lookup timed out")
        return None


def test_contract_resolution():
    """Test contract resolver"""
    wrapper = ContractResolverWrapper()
    resolver = ContractResolver(wrapper)
    
    if not resolver.connect():
        logger.error("❌ Failed to connect to IB Gateway")
        return
    
    logger.info("=" * 50)
    logger.info("Testing contract resolution...")
    logger.info("=" * 50)
    
    # Test: Resolve AAPL PUT 259 expiry 2026-03-12
    contract = resolver.resolve_option_contract("AAPL", 259, "PUT", "20260312")
    
    if contract:
        logger.info(f"✅ Successfully resolved: {contract.symbol} {contract.right} {contract.strike}")
    else:
        logger.error("❌ Failed to resolve contract")
    
    resolver.disconnect()


if __name__ == "__main__":
    test_contract_resolution()
