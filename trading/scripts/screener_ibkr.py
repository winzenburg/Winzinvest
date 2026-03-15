#!/usr/bin/env python3
"""
AMS Screener - IBKR-based
Uses IBKR real-time quotes and historical data
Scans 5,342 symbols from your TradingView export
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
        logging.FileHandler(LOGS_DIR / "screener_ibkr.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

WATCHLIST_DIR = WATCHLISTS_DIR
OUTPUT_FILE = TRADING_DIR / "screener_ibkr_results.json"

# Screener parameters (AMS-based)
PARAMS = {
    'short_roc': 21,
    'med_roc': 63,
    'long_roc': 126,
    'min_score_t2': 0.20,
    'min_score_t3': 0.35,
    'rsi_len': 14,
    'vol_lookback': 50,
    'min_dollar_vol_m': 25.0,
    'min_price': 5.0,
}

class IBKRScreener:
    """Screener using IBKR live data"""
    
    def __init__(self):
        self.ib = IB()
        self.candidates = []
        self.processed = 0
        self.failed = 0
    
    async def connect(self):
        """Connect to IBKR"""
        logger.info("Connecting to IBKR...")
        await self.ib.connectAsync(os.getenv("IB_HOST", "127.0.0.1"), int(os.getenv("IB_PORT", "4001")), clientId=99)
        logger.info("✅ Connected to IBKR")
    
    async def score_symbol(self, symbol):
        """Score a symbol using IBKR data"""
        try:
            # Create contract
            contract = Stock(symbol, 'SMART', 'USD')
            
            # Qualify contract
            contracts = await self.ib.qualifyContractsAsync(contract)
            if not contracts:
                return None
            
            contract = contracts[0]
            
            # Request historical data (1 year)
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
            
            # Convert to DataFrame
            df = util.df(bars)
            
            # Calculate momentum
            close = df['close']
            volume = df['volume']
            
            # ROC
            roc_s = close.pct_change(21) * 100
            roc_m = close.pct_change(63) * 100
            roc_l = close.pct_change(126) * 100
            momentum = 0.2 * roc_s + 0.3 * roc_m + 0.5 * roc_l
            
            # RSI
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            # RVOL
            avg_vol = volume.rolling(50).mean()
            rvol = volume / avg_vol
            
            # Liquidity
            dollar_vol = close * volume
            med_dv = dollar_vol.rolling(20).median().iloc[-1] / 1e6
            price = close.iloc[-1]
            
            if med_dv < PARAMS['min_dollar_vol_m'] or price < PARAMS['min_price']:
                return None
            
            # Score
            rsi_norm = (rsi.iloc[-1] - 50) / 25
            score = (abs(momentum.iloc[-1]) + rvol.iloc[-1] + abs(rsi_norm)) / 3.0
            
            return {
                'symbol': symbol,
                'momentum': float(momentum.iloc[-1]),
                'rsi': float(rsi.iloc[-1]),
                'rvol': float(rvol.iloc[-1]),
                'price': float(price),
                'dollar_vol_m': float(med_dv),
                'score': float(score),
            }
        
        except Exception as e:
            logger.debug(f"Error scoring {symbol}: {e}")
            return None
    
    async def scan(self, symbols):
        """Scan all symbols"""
        logger.info(f"Scanning {len(symbols)} symbols via IBKR...")
        logger.info("=" * 60)
        
        for i, symbol in enumerate(symbols):
            if (i + 1) % 100 == 0:
                pct = ((i + 1) / len(symbols)) * 100
                logger.info(f"Progress: {i+1}/{len(symbols)} ({pct:.1f}%) | Found: {len(self.candidates)} | Failed: {self.failed}")
            
            result = await self.score_symbol(symbol)
            if result:
                self.candidates.append(result)
            else:
                self.failed += 1
            
            self.processed += 1
        
        # Sort by score
        self.candidates.sort(key=lambda x: x['score'], reverse=True)
    
    async def run(self, symbol_file):
        """Run full screener"""
        # Load symbols
        df = pd.read_csv(symbol_file)
        symbols = df['symbol'].unique().tolist()
        
        logger.info(f"Loaded {len(symbols)} symbols from {symbol_file}")
        
        await self.connect()
        await self.scan(symbols)
        
        # Filter by tier
        tier2 = [c for c in self.candidates if c['score'] >= PARAMS['min_score_t2']]
        tier3 = [c for c in self.candidates if c['score'] >= PARAMS['min_score_t3']]
        
        # Report
        logger.info("")
        logger.info("=" * 60)
        logger.info("SCAN COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Symbols processed: {self.processed}")
        logger.info(f"Failed: {self.failed}")
        logger.info(f"\nTier 2 candidates (score ≥ {PARAMS['min_score_t2']}): {len(tier2)}")
        logger.info(f"Tier 3 candidates (score ≥ {PARAMS['min_score_t3']}): {len(tier3)}")
        
        if tier2:
            logger.info("\n*** TOP 10 TIER 2 ***")
            for c in tier2[:10]:
                logger.info(f"  {c['symbol']:6s} | Score: {c['score']:.3f} | Mom: {c['momentum']:+7.2f} | RSI: {c['rsi']:6.1f} | Price: ${c['price']:8.2f}")
        
        # Save results
        results = {
            'generated_at': datetime.now().isoformat(),
            'symbols_scanned': len(symbols),
            'symbols_processed': self.processed,
            'symbols_failed': self.failed,
            'tier_2_count': len(tier2),
            'tier_3_count': len(tier3),
            'tier_2': tier2,
            'tier_3': tier3,
        }
        
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"\nResults saved: {OUTPUT_FILE}")
        
        self.ib.disconnect()

async def main():
    screener = IBKRScreener()
    symbol_file = WATCHLIST_DIR / "pinchy_symbols_ALL.csv"
    await screener.run(symbol_file)

if __name__ == "__main__":
    asyncio.run(main())
