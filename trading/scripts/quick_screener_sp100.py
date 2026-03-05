#!/usr/bin/env python3
"""
Quick SP100 Screener - Proof of Concept
Tests on 100 most liquid stocks
"""

import pandas as pd
import numpy as np
from ib_insync import IB, Stock, util
from pathlib import Path
import logging
from datetime import datetime
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/pinchy/.openclaw/workspace/trading/logs/sp100_screener.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Top 100 liquid stocks (S&P 100)
SP100 = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'BRK.B', 'AVGO', 'ASML',
         'AMAT', 'LRCX', 'AMD', 'QCOM', 'COST', 'ADBE', 'NFLX', 'INTC', 'CSCO', 'INTU',
         'SNPS', 'CADENCE', 'ABBV', 'JNJ', 'UNH', 'PFE', 'VRTX', 'MRNA', 'REGN', 'GILD',
         'AMGN', 'BIIB', 'BAC', 'WFC', 'JPM', 'GS', 'MS', 'BLK', 'SCHW', 'AXP',
         'BX', 'KKR', 'APO', 'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'MPC', 'DHI',
         'LEN', 'PHM', 'NKE', 'LULU', 'VFC', 'DECK', 'RH', 'CPRI', 'MCD', 'SBUX',
         'DIS', 'CMCSA', 'CHTR', 'PARA', 'WBD', 'ROKU', 'BA', 'GD', 'RTX', 'LMT',
         'NXST', 'TXT', 'HON', 'ETN', 'ROK', 'ITRI', 'IR', 'EMR', 'LVS', 'MGM',
         'WYNN', 'CZR', 'UBER', 'LYFT', 'DASH', 'PYPL', 'SQ', 'COIN', 'GDDY', 'MNST',
         'KO', 'PEP', 'MO', 'PM', 'KMB', 'CL', 'WMT', 'TGT', 'LOW', 'HD']

WORKSPACE = Path.home() / ".openclaw" / "workspace"
OUTPUT_FILE = WORKSPACE / "trading" / "sp100_candidates.json"

class SP100Screener:
    def __init__(self, symbols=None):
        self.ib = IB()
        self.candidates = []
        self.processed = 0
        self.SP100 = symbols or []
    
    async def connect(self):
        await self.ib.connectAsync('127.0.0.1', 4002, clientId=104)
        logger.info("✅ Connected to IBKR")
    
    async def fetch_and_score(self, symbol):
        try:
            contract = Stock(symbol, 'SMART', 'USD')
            contracts = await self.ib.qualifyContractsAsync(contract)
            if not contracts:
                return None
            
            contract = contracts[0]
            bars = await self.ib.reqHistoricalDataAsync(
                contract, '', '1 Y', '1 day', 'TRADES', True
            )
            
            if not bars or len(bars) < 126:
                return None
            
            df = util.df(bars)
            close = df['close'].values
            volume = df['volume'].values
            
            # Momentum
            roc_s = (close[-1] - close[-21]) / close[-21] * 100
            roc_m = (close[-1] - close[-63]) / close[-63] * 100
            roc_l = (close[-1] - close[-126]) / close[-126] * 100
            momentum = 0.2*roc_s + 0.3*roc_m + 0.5*roc_l
            
            # RSI
            delta = np.diff(close)
            avg_gain = np.mean([d for d in delta[-14:] if d > 0]) or 0.001
            avg_loss = np.mean([-d for d in delta[-14:] if d < 0]) or 0.001
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            # RVOL
            rvol = volume[-1] / np.mean(volume[-50:])
            
            # Dollar volume
            dollar_vol = (close[-1] * np.mean(volume[-20:])) / 1e6
            
            if dollar_vol < 25 or close[-1] < 5:
                return None
            
            score = (abs(momentum) + min(rvol, 3.0) + abs((rsi-50)/25)) / 3.0
            
            return {
                'symbol': symbol,
                'momentum': float(momentum),
                'rsi': float(rsi),
                'rvol': float(rvol),
                'price': float(close[-1]),
                'dollar_vol_m': float(dollar_vol),
                'score': float(score),
            }
        except Exception as e:
            logger.debug(f"{symbol}: {e}")
            return None
    
    async def run(self):
        logger.info(f"Screening {len(self.SP100)} stocks...")
        await self.connect()
        
        for i, symbol in enumerate(self.SP100):
            result = await self.fetch_and_score(symbol)
            if result:
                self.candidates.append(result)
            self.processed += 1
            
            if (i+1) % 50 == 0:
                logger.info(f"  Progress: {i+1}/{len(self.SP100)} | Found: {len(self.candidates)}")
        
        # Sort & save
        self.candidates.sort(key=lambda x: x['score'], reverse=True)
        
        tier2 = [c for c in self.candidates if c['score'] >= 0.20]
        
        with open(OUTPUT_FILE, 'w') as f:
            json.dump({
                'generated_at': datetime.now().isoformat(),
                'symbols_scanned': len(SP100),
                'candidates': self.candidates,
                'tier_2': tier2[:10],
            }, f, indent=2, default=str)
        
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"✅ SCREENING COMPLETE")
        logger.info(f"Total: {len(self.candidates)} candidates")
        logger.info(f"Tier 2 (top): {len(tier2)}")
        
        if tier2:
            logger.info("\n*** TOP 10 CANDIDATES ***")
            for c in tier2[:10]:
                logger.info(f"  {c['symbol']:6s} | Score: {c['score']:.3f} | Mom: {c['momentum']:+7.2f} | RSI: {c['rsi']:6.1f}")
        
        self.ib.disconnect()

async def main():
    import asyncio
    
    # Load 800 complete universe (S&P 500 + Nasdaq + Russell)
    df = pd.read_csv('/Users/pinchy/.openclaw/workspace/trading/watchlists/top_800_final.csv')
    symbols = df['symbol'].tolist()
    
    screener = SP100Screener(symbols=symbols)
    await screener.run()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
