#!/usr/bin/env python3
"""
AMS Screener - Uses cached IBKR snapshot
Fast local processing on cached data
No API calls during screening
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
from datetime import datetime
import json
import asyncio

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/pinchy/.openclaw/workspace/trading/logs/screener_from_snapshot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

WORKSPACE = Path.home() / ".openclaw" / "workspace"
CACHE_DIR = WORKSPACE / "trading" / "screener_cache"
SNAPSHOT_FILE = CACHE_DIR / "daily_snapshot.json"
CANDIDATES_FILE = WORKSPACE / "trading" / "screener_candidates.json"
EXECUTE_FILE = WORKSPACE / "trading" / "ready_to_execute.json"

# AMS Parameters
AMS_PARAMS = {
    'min_score_t2': 0.20,
    'min_score_t3': 0.35,
    'rsi_len': 14,
    'vol_lookback': 50,
    'min_dollar_vol_m': 25.0,
    'min_price': 5.0,
}

class SnapshotScreener:
    """Screen using cached snapshot data"""
    
    def __init__(self):
        self.snapshot = {}
        self.candidates = []
        self.processed = 0
        self.failed = 0
    
    def load_snapshot(self):
        """Load cached snapshot"""
        if not SNAPSHOT_FILE.exists():
            logger.error(f"Snapshot not found: {SNAPSHOT_FILE}")
            logger.error("Run daily_snapshot.py first to generate snapshot")
            return False
        
        with open(SNAPSHOT_FILE, 'r') as f:
            data = json.load(f)
        
        self.snapshot = data.get('data', {})
        logger.info(f"Loaded snapshot: {len(self.snapshot)} symbols")
        logger.info(f"Generated at: {data.get('generated_at')}")
        return True
    
    def score_symbol(self, symbol_data):
        """Score a symbol by AMS criteria"""
        try:
            close = np.array(symbol_data['close'])
            volume = np.array(symbol_data['volume'])
            
            if len(close) < 126:
                return None
            
            # Momentum (ROC 21/63/126)
            roc_s = (close[-1] - close[-21]) / close[-21] * 100
            roc_m = (close[-1] - close[-63]) / close[-63] * 100
            roc_l = (close[-1] - close[-126]) / close[-126] * 100
            momentum = 0.2 * roc_s + 0.3 * roc_m + 0.5 * roc_l
            
            # RSI
            delta = np.diff(close)
            gains = [d for d in delta[-14:] if d > 0]
            losses = [-d for d in delta[-14:] if d < 0]
            
            avg_gain = np.mean(gains) if gains else 0.001
            avg_loss = np.mean(losses) if losses else 0.001
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            # RVOL
            avg_vol = np.mean(volume[-50:])
            rvol = volume[-1] / avg_vol if avg_vol > 0 else 1.0
            rvol = min(rvol, 3.0)  # Cap at 3x
            
            # Liquidity check
            if symbol_data['dollar_vol_m'] < AMS_PARAMS['min_dollar_vol_m']:
                return None
            if symbol_data['price'] < AMS_PARAMS['min_price']:
                return None
            
            # Composite score
            rsi_norm = (rsi - 50) / 25
            score = (abs(momentum) + rvol + abs(rsi_norm)) / 3.0
            
            return {
                'symbol': symbol_data['symbol'],
                'momentum': float(momentum),
                'rsi': float(rsi),
                'rvol': float(rvol),
                'price': float(symbol_data['price']),
                'dollar_vol_m': float(symbol_data['dollar_vol_m']),
                'score': float(score),
            }
        
        except Exception as e:
            logger.debug(f"Error scoring {symbol_data.get('symbol')}: {e}")
            return None
    
    def run_screen(self):
        """Screen all cached symbols"""
        logger.info(f"Screening {len(self.snapshot)} symbols...")
        logger.info("=" * 60)
        
        for i, (symbol, data) in enumerate(self.snapshot.items()):
            if (i + 1) % 500 == 0:
                pct = ((i + 1) / len(self.snapshot)) * 100
                logger.info(f"Progress: {i+1}/{len(self.snapshot)} ({pct:.1f}%) | Found: {len(self.candidates)}")
            
            result = self.score_symbol(data)
            if result:
                self.candidates.append(result)
            
            self.processed += 1
        
        # Sort by score
        self.candidates.sort(key=lambda x: x['score'], reverse=True)
    
    def save_results(self):
        """Save candidate results"""
        tier2 = [c for c in self.candidates if c['score'] >= AMS_PARAMS['min_score_t2']]
        tier3 = [c for c in self.candidates if c['score'] >= AMS_PARAMS['min_score_t3']]
        
        results = {
            'generated_at': datetime.now().isoformat(),
            'symbols_scanned': self.processed,
            'tier_2_count': len(tier2),
            'tier_3_count': len(tier3),
            'tier_2': tier2[:20],  # Top 20
            'tier_3': tier3[:20],
        }
        
        with open(CANDIDATES_FILE, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"✅ SCREENING COMPLETE")
        logger.info(f"Symbols processed: {self.processed}")
        logger.info(f"Tier 2 candidates: {len(tier2)}")
        logger.info(f"Tier 3 candidates: {len(tier3)}")
        
        if tier2:
            logger.info("\n*** TOP 10 TIER 2 ***")
            for c in tier2[:10]:
                logger.info(f"  {c['symbol']:6s} | Score: {c['score']:.3f} | Mom: {c['momentum']:+7.2f} | RSI: {c['rsi']:6.1f} | ${c['price']:7.2f}")
        
        logger.info(f"\nResults saved: {CANDIDATES_FILE}")
        
        return tier2, tier3
    
    async def run(self):
        """Run full screening"""
        logger.info(f"Starting AMS screener at {datetime.now().isoformat()}")
        
        if not self.load_snapshot():
            return False
        
        self.run_screen()
        tier2, tier3 = self.save_results()
        
        return True

async def main():
    screener = SnapshotScreener()
    await screener.run()

if __name__ == "__main__":
    asyncio.run(main())
