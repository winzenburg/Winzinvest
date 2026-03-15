#!/usr/bin/env python3
"""
AMS Python Screener - Implements TradingView AMS_Pro_Screener_NX logic
Scans 2,600+ symbols daily and finds Tier 2/3 candidates
"""

import pandas as pd
import numpy as np
import yfinance as yf
from pathlib import Path
import logging
from datetime import datetime, timedelta
import json
from paths import TRADING_DIR, LOGS_DIR, WATCHLISTS_DIR

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / "ams_screener.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

WATCHLIST_DIR = WATCHLISTS_DIR
OUTPUT_FILE = TRADING_DIR / "ams_screener_results.json"

# === Screener Parameters (from TV) ===
PARAMS = {
    # Momentum
    'short_roc': 21,
    'med_roc': 63,
    'long_roc': 126,
    
    # Scoring tiers
    'min_score_t2': 0.20,
    'min_score_t3': 0.35,
    
    # Volatility normalization
    'atr_len': 14,
    'norm_base': 2.0,
    
    # HTF bias weights
    'w_weekly': 0.30,
    'w_monthly': 0.20,
    
    # RS parameters
    'rs_lookback': 252,
    'rs_long_pct': 0.60,
    'rs_short_pct': 0.40,
    
    # Volume & liquidity
    'vol_lookback': 50,
    'min_dollar_vol_m': 25.0,
    'min_price': 5.0,
    
    # RSI
    'rsi_len': 14,
    'min_rsi_long': 45,
    'max_rsi_long': 75,
    'max_abs_corr': 0.85,
}

def load_symbols():
    """Load 2,600+ symbols from CSV"""
    csv_file = WATCHLIST_DIR / "all_us_equities.csv"
    if csv_file.exists():
        df = pd.read_csv(csv_file)
        symbols = df['symbol'].tolist()
        logger.info(f"Loaded {len(symbols)} symbols from {csv_file}")
        return symbols
    else:
        logger.error(f"Symbol file not found: {csv_file}")
        return []

def fetch_data(symbol, period="1y"):
    """Fetch OHLCV data for symbol"""
    try:
        data = yf.download(symbol, period=period, progress=False, interval="1d")
        if data.empty:
            return None
        return data
    except Exception as e:
        logger.debug(f"Error fetching {symbol}: {e}")
        return None

def calculate_momentum(data, short_roc, med_roc, long_roc, use_vol_norm=True):
    """Calculate composite momentum score"""
    close = data['Close']
    
    # ROC calculations
    roc_s = close.pct_change(short_roc) * 100
    roc_m = close.pct_change(med_roc) * 100
    roc_l = close.pct_change(long_roc) * 100
    
    # Volume normalization by ATR%
    if use_vol_norm:
        atr = data['High'].rolling(14).max() - data['Low'].rolling(14).min()
        vol_pct = (atr / close) * 100
        vol_factor = np.maximum(vol_pct, 0.5)
        roc_s = roc_s / (vol_factor / PARAMS['norm_base'])
        roc_m = roc_m / (vol_factor / PARAMS['norm_base'])
        roc_l = roc_l / (vol_factor / PARAMS['norm_base'])
    
    # Composite momentum (0.2*S + 0.3*M + 0.5*L)
    comp_mom = 0.2 * roc_s + 0.3 * roc_m + 0.5 * roc_l
    
    return comp_mom.iloc[-1] if not comp_mom.isna().all() else 0.0

def calculate_rsi(close, length=14):
    """Calculate RSI"""
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=length).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=length).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not rsi.isna().all() else 50

def calculate_rvol(data, lookback=50):
    """Calculate smart RVOL"""
    volume = data['Volume']
    avg_vol = volume.rolling(lookback).mean()
    rvol = volume / avg_vol
    rvol_cap = np.minimum(rvol, 3.0)
    rvol_ema = rvol_cap.ewm(span=10).mean()
    return rvol_ema.iloc[-1] if not rvol_ema.isna().all() else 1.0

def calculate_liquidity(data):
    """Check liquidity requirements"""
    dollar_vol = data['Close'] * data['Volume']
    med_dollar_vol_m = (dollar_vol.rolling(20).median().iloc[-1]) / 1e6
    min_price = data['Close'].iloc[-1]
    
    liq_ok = (med_dollar_vol_m >= PARAMS['min_dollar_vol_m']) and (min_price >= PARAMS['min_price'])
    return liq_ok, med_dollar_vol_m

def score_candidate(symbol, data):
    """Calculate tier score for symbol"""
    try:
        momentum = calculate_momentum(data, PARAMS['short_roc'], PARAMS['med_roc'], PARAMS['long_roc'])
        rsi = calculate_rsi(data['Close'], PARAMS['rsi_len'])
        rvol = calculate_rvol(data, PARAMS['vol_lookback'])
        liq_ok, dollar_vol = calculate_liquidity(data)
        
        if not liq_ok:
            return None
        
        # Composite score (momentum + rvol + rsi_normalized)
        rsi_norm = (rsi - 50) / 25  # Normalize to ~[-1, 1]
        score = (abs(momentum) + rvol + abs(rsi_norm)) / 3.0
        
        return {
            'symbol': symbol,
            'momentum': momentum,
            'rsi': rsi,
            'rvol': rvol,
            'dollar_vol_m': dollar_vol,
            'score': score,
        }
    except Exception as e:
        logger.debug(f"Error scoring {symbol}: {e}")
        return None

def run_scan():
    """Run full market scan"""
    logger.info("=" * 60)
    logger.info("Starting AMS Screener Scan")
    logger.info("=" * 60)
    
    symbols = load_symbols()
    if not symbols:
        logger.error("No symbols loaded")
        return
    
    logger.info(f"Scanning {len(symbols)} symbols...")
    
    candidates = []
    processed = 0
    
    for i, symbol in enumerate(symbols):
        if i % 50 == 0:
            logger.info(f"Progress: {i+1}/{len(symbols)}")
        
        data = fetch_data(symbol)
        if data is None:
            continue
        
        score_data = score_candidate(symbol, data)
        if score_data:
            candidates.append(score_data)
        
        processed += 1
    
    # Tier candidates
    tier2 = [c for c in candidates if c['score'] >= PARAMS['min_score_t2']]
    tier3 = [c for c in candidates if c['score'] >= PARAMS['min_score_t3']]
    
    # Sort by score
    tier2.sort(key=lambda x: x['score'], reverse=True)
    tier3.sort(key=lambda x: x['score'], reverse=True)
    
    logger.info("")
    logger.info(f"✅ Scan complete")
    logger.info(f"Symbols processed: {processed}")
    logger.info(f"Tier 2 candidates (score ≥ {PARAMS['min_score_t2']}): {len(tier2)}")
    logger.info(f"Tier 3 candidates (score ≥ {PARAMS['min_score_t3']}): {len(tier3)}")
    logger.info("=" * 60)
    
    # Write results
    results = {
        'generated_at': datetime.now().isoformat(),
        'symbols_scanned': len(symbols),
        'symbols_processed': processed,
        'tier_2': tier2[:10],  # Top 10 per tier
        'tier_3': tier3[:10],
        'total_t2': len(tier2),
        'total_t3': len(tier3),
    }
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    logger.info(f"Results saved: {OUTPUT_FILE}")
    
    # Return top tier 2 for execution
    return tier2[:5]

if __name__ == "__main__":
    candidates = run_scan()
    if candidates:
        logger.info("\nTop 5 Tier 2 Candidates:")
        for c in candidates:
            logger.info(f"  {c['symbol']}: Score={c['score']:.3f}, Mom={c['momentum']:.2f}, RSI={c['rsi']:.1f}, RVOL={c['rvol']:.2f}")
