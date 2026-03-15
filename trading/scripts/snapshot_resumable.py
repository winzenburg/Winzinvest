#!/usr/bin/env python3
"""
Resumable IBKR Snapshot Fetcher
- Saves progress after each batch
- Resumes if interrupted
- Respects IBKR rate limits
- No timeouts
"""

import os
import pandas as pd
import json
from ib_insync import IB, Stock, util
from pathlib import Path
import logging
from datetime import datetime
import asyncio
import time
from paths import TRADING_DIR, LOGS_DIR, WATCHLISTS_DIR

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
        logging.FileHandler(LOGS_DIR / "snapshot_resumable.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

WATCHLIST_DIR = WATCHLISTS_DIR
CACHE_DIR = TRADING_DIR / "screener_cache"
SNAPSHOT_FILE = CACHE_DIR / "daily_snapshot.json"
PROGRESS_FILE = CACHE_DIR / "snapshot_progress.json"

CACHE_DIR.mkdir(parents=True, exist_ok=True)

class ResumableSnapshotFetcher:
    """Fetches snapshot with resume capability"""
    
    def __init__(self, batch_size=30, rate_limit_ms=500):
        self.ib = IB()
        self.batch_size = batch_size
        self.rate_limit_ms = rate_limit_ms  # ms between requests
        self.snapshot = {}
        self.progress = self.load_progress()
        self.processed = self.progress.get('processed', 0)
        self.failed = self.progress.get('failed', 0)
    
    def load_progress(self):
        """Load previous progress"""
        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
        return {'processed': 0, 'failed': 0, 'last_batch': 0}
    
    def save_progress(self):
        """Save progress after each batch"""
        with open(PROGRESS_FILE, 'w') as f:
            json.dump({
                'processed': self.processed,
                'failed': self.failed,
                'last_batch': self.progress['last_batch'],
                'timestamp': datetime.now().isoformat(),
            }, f)
    
    def load_partial_snapshot(self):
        """Load previously fetched data"""
        if SNAPSHOT_FILE.exists():
            with open(SNAPSHOT_FILE, 'r') as f:
                data = json.load(f)
            self.snapshot = data.get('data', {})
            logger.info(f"Loaded {len(self.snapshot)} previously cached symbols")
    
    async def connect(self):
        """Connect to IBKR"""
        logger.info("Connecting to IBKR...")
        try:
            await self.ib.connectAsync(os.getenv("IB_HOST", "127.0.0.1"), int(os.getenv("IB_PORT", "4001")), clientId=103)
            logger.info("✅ Connected to IBKR")
            return True
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
    
    async def fetch_symbol_data(self, symbol):
        """Fetch data for one symbol with timeout"""
        try:
            contract = Stock(symbol, 'SMART', 'USD')
            
            # Qualify contract
            contracts = await asyncio.wait_for(
                self.ib.qualifyContractsAsync(contract),
                timeout=5.0
            )
            
            if not contracts:
                return None
            
            contract = contracts[0]
            
            # Fetch historical data
            bars = await asyncio.wait_for(
                self.ib.reqHistoricalDataAsync(
                    contract,
                    endDateTime='',
                    durationStr='1 Y',
                    barSizeSetting='1 day',
                    whatToShow='TRADES',
                    useRTH=True
                ),
                timeout=10.0
            )
            
            if not bars or len(bars) < 126:
                return None
            
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
        
        except asyncio.TimeoutError:
            logger.warning(f"Timeout: {symbol}")
            return None
        except Exception as e:
            logger.debug(f"Error fetching {symbol}: {e}")
            return None
    
    async def fetch_batch(self, symbols):
        """Fetch batch with rate limiting"""
        results = []
        
        for i, symbol in enumerate(symbols):
            result = await self.fetch_symbol_data(symbol)
            if result:
                results.append(result)
            
            # Rate limit between requests
            if i < len(symbols) - 1:
                await asyncio.sleep(self.rate_limit_ms / 1000.0)
        
        return results
    
    async def run(self, symbol_file):
        """Run resumable fetch"""
        # Load symbols
        df = pd.read_csv(symbol_file)
        symbols = df['symbol'].unique().tolist()
        
        logger.info(f"Total symbols: {len(symbols)}")
        logger.info(f"Resuming from: Symbol #{self.progress['last_batch'] * self.batch_size}")
        logger.info("=" * 60)
        
        if not await self.connect():
            return False
        
        # Load previous data
        self.load_partial_snapshot()
        
        # Resume from last batch
        start_idx = self.progress['last_batch'] * self.batch_size
        
        # Fetch remaining batches
        for i in range(start_idx, len(symbols), self.batch_size):
            batch = symbols[i:i+self.batch_size]
            batch_num = i // self.batch_size + 1
            pct = ((i + len(batch)) / len(symbols)) * 100
            
            logger.info(f"Batch {batch_num}: {i+1}-{min(i+self.batch_size, len(symbols))} ({pct:.1f}%)")
            
            results = await self.fetch_batch(batch)
            
            # Store results
            for result in results:
                self.snapshot[result['symbol']] = result
            
            self.processed += len(results)
            self.failed += len(batch) - len(results)
            self.progress['last_batch'] = batch_num
            
            # Save progress after each batch
            self.save_progress()
            
            # Save partial snapshot
            with open(SNAPSHOT_FILE, 'w') as f:
                json.dump({
                    'generated_at': datetime.now().isoformat(),
                    'symbols_count': len(self.snapshot),
                    'data': self.snapshot,
                }, f)
            
            logger.info(f"  → {len(results)} symbols cached. Total: {len(self.snapshot)}")
        
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"✅ SNAPSHOT COMPLETE")
        logger.info(f"Total processed: {self.processed}")
        logger.info(f"Total failed: {self.failed}")
        logger.info(f"Symbols cached: {len(self.snapshot)}")
        logger.info(f"Snapshot file: {SNAPSHOT_FILE}")
        logger.info("=" * 60)
        
        # Clean up progress file
        if PROGRESS_FILE.exists():
            PROGRESS_FILE.unlink()
        
        self.ib.disconnect()
        return True

async def main():
    fetcher = ResumableSnapshotFetcher(batch_size=30, rate_limit_ms=500)
    symbol_file = WATCHLIST_DIR / "balanced_800_stocks_plus_etfs.csv"
    await fetcher.run(symbol_file)

if __name__ == "__main__":
    asyncio.run(main())
