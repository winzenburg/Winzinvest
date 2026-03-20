#!/usr/bin/env python3
"""
Daily IBKR Snapshot Fetcher
Pulls 1 year of historical data for all 5,342 symbols
Batches requests (100 at a time) to avoid connection limits
Caches locally for screener processing
"""

import os
import pandas as pd
import numpy as np
from ib_insync import IB, Stock, util
from pathlib import Path
import logging
from datetime import datetime, timedelta
import json
import asyncio
import time
from atomic_io import atomic_write_json
from paths import TRADING_DIR, LOGS_DIR, WATCHLISTS_DIR, WORKSPACE

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
        logging.FileHandler(LOGS_DIR / "daily_snapshot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

WATCHLIST_DIR = WATCHLISTS_DIR
CACHE_DIR = TRADING_DIR / "screener_cache"
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
            await self.ib.connectAsync(os.getenv("IB_HOST", "127.0.0.1"), int(os.getenv("IB_PORT", "4001")), clientId=128)
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

        try:
            for i in range(0, len(symbols), self.batch_size):
                batch = symbols[i : i + self.batch_size]
                pct = ((i + self.batch_size) / len(symbols)) * 100
                logger.info(
                    "Batch %d: %d-%d (%.1f%%)",
                    i // self.batch_size + 1,
                    i + 1,
                    min(i + self.batch_size, len(symbols)),
                    pct,
                )

                results = await self.fetch_batch(batch)

                for result in results:
                    self.snapshot[result["symbol"]] = result
                    self.processed += 1

                self.failed += len(batch) - len(results)

                if i + self.batch_size < len(symbols):
                    await asyncio.sleep(2)

            atomic_write_json(
                SNAPSHOT_FILE,
                {
                    "generated_at": datetime.now().isoformat(),
                    "symbols_count": len(self.snapshot),
                    "data": self.snapshot,
                },
            )

            logger.info("")
            logger.info("=" * 60)
            logger.info("✅ SNAPSHOT COMPLETE")
            logger.info("Symbols processed: %s", self.processed)
            logger.info("Symbols failed: %s", self.failed)
            logger.info("Snapshot saved: %s", SNAPSHOT_FILE)
            if SNAPSHOT_FILE.exists():
                logger.info(
                    "File size: %.1f MB",
                    SNAPSHOT_FILE.stat().st_size / 1024 / 1024,
                )
            return True
        finally:
            try:
                if self.ib.isConnected():
                    self.ib.disconnect()
            except Exception as exc:
                logger.warning("IB disconnect: %s", exc)

async def main():
    fetcher = DailySnapshotFetcher(batch_size=50)
    symbol_file = WATCHLIST_DIR / "pinchy_symbols_ALL.csv"
    await fetcher.run(symbol_file)

if __name__ == "__main__":
    asyncio.run(main())
