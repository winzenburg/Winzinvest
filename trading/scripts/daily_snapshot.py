#!/usr/bin/env python3
"""
Daily IBKR Snapshot Fetcher
Pulls 1 year of historical data for all 5,342 symbols
Batches requests (100 at a time) to avoid connection limits
Caches locally for screener processing
"""

import pandas as pd
import numpy as np
from ib_insync import IB, Stock, util
from pathlib import Path
import logging
from datetime import datetime, timedelta
import json
import asyncio
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/pinchy/.openclaw/workspace/trading/logs/daily_snapshot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

WORKSPACE = Path.home() / ".openclaw" / "workspace"
WATCHLIST_DIR = WORKSPACE / "trading" / "watchlists"
CACHE_DIR = WORKSPACE / "trading" / "screener_cache"
SNAPSHOT_FILE = CACHE_DIR / "daily_snapshot.json"

CACHE_DIR.mkdir(parents=True, exist_ok=True)

class DailySnapshotFetcher:
    """Fetch daily IBKR snapshot with batching"""
    
    def __init__(self, batch_size=50):
        self.ib = IB()
        self.batch_size = batch_size
        self.snapshot = {}
        self.processed = 0
        self.failed = 0
    
    async def connect(self):
        """Connect to IBKR"""
        logger.info("Connecting to IBKR...")
        try:
            await self.ib.connectAsync('127.0.0.1', 4002, clientId=100)
            logger.info("✅ Connected to IBKR")
            return True
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
    
    async def fetch_symbol_data(self, symbol):
        """Fetch historical data for one symbol"""
        try:
            contract = Stock(symbol, 'SMART', 'USD')
            
            # Qualify contract
            contracts = await self.ib.qualifyContractsAsync(contract)
            if not contracts:
                return None
            
            contract = contracts[0]
            
            # Request 1 year of daily data
            bars = await self.ib.reqHistoricalDataAsync(
                contract,
                endDateTime='',
                durationStr='1 Y',
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=True
            )
            
            if not bars or len(bars) < 126:
                return None
            
            # Convert to simple format
            df = util.df(bars)
            
            return {
                'symbol': symbol,
                'close': df['close'].tolist(),
                'volume': df['volume'].tolist(),
                'high': df['high'].tolist(),
                'low': df['low'].tolist(),
                'price': float(df['close'].iloc[-1]),
                'dollar_vol_m': float((df['close'].iloc[-1] * df['volume'].iloc[-20:].mean()) / 1e6),
            }
        
        except Exception as e:
            logger.debug(f"Error fetching {symbol}: {e}")
            return None
    
    async def fetch_batch(self, symbols):
        """Fetch data for a batch of symbols"""
        tasks = [self.fetch_symbol_data(s) for s in symbols]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]
    
    async def run(self, symbol_file):
        """Run full daily snapshot"""
        # Load symbols
        df = pd.read_csv(symbol_file)
        symbols = df['symbol'].unique().tolist()
        
        logger.info(f"Loaded {len(symbols)} symbols")
        logger.info(f"Fetching batches of {self.batch_size} symbols...")
        logger.info("=" * 60)
        
        if not await self.connect():
            return False
        
        # Fetch in batches
        for i in range(0, len(symbols), self.batch_size):
            batch = symbols[i:i+self.batch_size]
            pct = ((i + self.batch_size) / len(symbols)) * 100
            logger.info(f"Batch {i//self.batch_size + 1}: {i+1}-{min(i+self.batch_size, len(symbols))} ({pct:.1f}%)")
            
            results = await self.fetch_batch(batch)
            
            for result in results:
                self.snapshot[result['symbol']] = result
                self.processed += 1
            
            self.failed += len(batch) - len(results)
            
            # Rate limit: small delay between batches
            if i + self.batch_size < len(symbols):
                await asyncio.sleep(2)
        
        # Save snapshot
        with open(SNAPSHOT_FILE, 'w') as f:
            json.dump({
                'generated_at': datetime.now().isoformat(),
                'symbols_count': len(self.snapshot),
                'data': self.snapshot,
            }, f)
        
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"✅ SNAPSHOT COMPLETE")
        logger.info(f"Symbols processed: {self.processed}")
        logger.info(f"Symbols failed: {self.failed}")
        logger.info(f"Snapshot saved: {SNAPSHOT_FILE}")
        logger.info(f"File size: {SNAPSHOT_FILE.stat().st_size / 1024 / 1024:.1f} MB")
        
        self.ib.disconnect()
        return True

async def main():
    fetcher = DailySnapshotFetcher(batch_size=50)
    symbol_file = WATCHLIST_DIR / "pinchy_symbols_ALL.csv"
    await fetcher.run(symbol_file)

if __name__ == "__main__":
    asyncio.run(main())
