#!/usr/bin/env python3
"""
AMS Screener - Real run on 5,342 symbols from TradingView export
No BS. Just actual results.
"""

import pandas as pd
import numpy as np
import yfinance as yf
from pathlib import Path
import logging
from datetime import datetime
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

WORKSPACE = Path.home() / ".openclaw" / "workspace"
WATCHLIST_DIR = WORKSPACE / "trading" / "watchlists"
OUTPUT_FILE = WORKSPACE / "trading" / "screener_results_real.json"

# Load symbols
csv_file = WATCHLIST_DIR / "pinchy_symbols_ALL.csv"
logger.info(f"Loading symbols from {csv_file}")

df = pd.read_csv(csv_file)
symbols = df['symbol'].unique().tolist()
logger.info(f"✅ Loaded {len(symbols)} unique symbols")

# Screener parameters (AMS-based)
PARAMS = {
    'short_roc': 21,
    'med_roc': 63,
    'long_roc': 126,
    'min_score_t2': 0.20,
    'min_score_t3': 0.35,
    'atr_len': 14,
    'rsi_len': 14,
    'vol_lookback': 50,
    'min_dollar_vol_m': 25.0,
    'min_price': 5.0,
}

def score_symbol(symbol):
    """Score a single symbol. Return None if invalid."""
    try:
        # Fetch 1 year of data
        data = yf.download(symbol, period='1y', progress=False, interval='1d')
        
        if data.empty or len(data) < 126:
            return None
        
        close = data['Close']
        volume = data['Volume']
        
        # Momentum (ROC)
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
            'momentum': momentum.iloc[-1],
            'rsi': rsi.iloc[-1],
            'rvol': rvol.iloc[-1],
            'price': price,
            'dollar_vol_m': med_dv,
            'score': score,
        }
    
    except Exception as e:
        return None

# Run scan
logger.info(f"\nScanning {len(symbols)} symbols...")
logger.info("This will take 15-20 minutes...")
logger.info("=" * 60)

candidates = []
processed = 0
failed = 0

for i, symbol in enumerate(symbols):
    if (i + 1) % 100 == 0:
        pct = ((i + 1) / len(symbols)) * 100
        logger.info(f"Progress: {i+1}/{len(symbols)} ({pct:.1f}%) | Found: {len(candidates)} | Failed: {failed}")
    
    result = score_symbol(symbol)
    if result:
        candidates.append(result)
    else:
        failed += 1
    
    processed += 1

# Filter by tier
tier2 = [c for c in candidates if c['score'] >= PARAMS['min_score_t2']]
tier3 = [c for c in candidates if c['score'] >= PARAMS['min_score_t3']]

tier2.sort(key=lambda x: x['score'], reverse=True)
tier3.sort(key=lambda x: x['score'], reverse=True)

# Report
logger.info("\n" + "=" * 60)
logger.info(f"SCAN COMPLETE")
logger.info("=" * 60)
logger.info(f"Symbols scanned: {len(symbols)}")
logger.info(f"Successfully processed: {processed}")
logger.info(f"Failed: {failed}")
logger.info(f"\nTier 2 candidates (score ≥ {PARAMS['min_score_t2']}): {len(tier2)}")
logger.info(f"Tier 3 candidates (score ≥ {PARAMS['min_score_t3']}): {len(tier3)}")

if tier2:
    logger.info("\n*** TOP 10 TIER 2 ***")
    for c in tier2[:10]:
        logger.info(f"  {c['symbol']:6s} | Score: {c['score']:.3f} | Mom: {c['momentum']:+7.2f} | RSI: {c['rsi']:6.1f} | Price: ${c['price']:8.2f} | Vol: ${c['dollar_vol_m']:.1f}M")

if tier3:
    logger.info("\n*** TOP 10 TIER 3 ***")
    for c in tier3[:10]:
        logger.info(f"  {c['symbol']:6s} | Score: {c['score']:.3f} | Mom: {c['momentum']:+7.2f} | RSI: {c['rsi']:6.1f} | Price: ${c['price']:8.2f} | Vol: ${c['dollar_vol_m']:.1f}M")

# Save results
results = {
    'generated_at': datetime.now().isoformat(),
    'symbols_scanned': len(symbols),
    'symbols_processed': processed,
    'symbols_failed': failed,
    'tier_2_count': len(tier2),
    'tier_3_count': len(tier3),
    'tier_2_top_10': tier2[:10],
    'tier_3_top_10': tier3[:10],
}

with open(OUTPUT_FILE, 'w') as f:
    json.dump(results, f, indent=2, default=str)

logger.info(f"\nResults saved: {OUTPUT_FILE}")
