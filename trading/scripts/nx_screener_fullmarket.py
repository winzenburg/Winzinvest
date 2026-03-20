#!/usr/bin/env python3
"""
Full-Market Screener (2,600 Symbols)
Scans ALL symbols, applies mode-specific filters
One universe. Three filter sets. Market speaks.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime
from pathlib import Path
import logging
from paths import TRADING_DIR, LOGS_DIR

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / "screener_fullmarket.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

WORKSPACE = TRADING_DIR

def load_full_universe():
    """Load all 2,600 symbols from CSV."""
    try:
        df = pd.read_csv(WORKSPACE / "watchlists" / "full_market_2600.csv")
        symbols = df['symbol'].unique().tolist()
        logger.info(f"✓ Loaded {len(symbols)} symbols from full market")
        return symbols
    except Exception as e:
        logger.error(f"Failed to load universe: {e}")
        return []

def fetch_data(symbols, period='1y'):
    """Fetch OHLCV data for all symbols."""
    logger.info(f"Fetching data for {len(symbols)} symbols...")
    data_map = {}
    
    for i, sym in enumerate(symbols):
        if (i + 1) % 100 == 0:
            logger.info(f"Progress: {i+1}/{len(symbols)}")
        try:
            hist = yf.download(sym, period=period, progress=False)
            if not hist.empty:
                data_map[sym] = hist
        except Exception as exc:
            logger.debug("fetch skip %s: %s", sym, exc)
    
    logger.info(f"✓ Fetched {len(data_map)} symbols")
    return data_map

def calculate_metrics(sym, ohlcv, spy_data):
    """Calculate technical metrics."""
    try:
        close = ohlcv['Close'].values
        
        # Recent return
        recent_return = (close[-1] - close[-20]) / close[-20] if len(close) >= 20 else 0
        
        # Relative strength
        if len(close) >= 20 and len(spy_data) >= 20:
            sym_20d = (close[-1] - close[-20]) / close[-20]
            spy_20d = (spy_data.iloc[-1] - spy_data.iloc[-20]) / spy_data.iloc[-20]
            rs = sym_20d - spy_20d
        else:
            rs = 0
        
        # Relative volatility
        if len(close) >= 20:
            sym_vol = np.std(np.diff(np.log(close[-20:])))
            spy_vol = np.std(np.diff(np.log(spy_data.values[-20:])))
            rvol = sym_vol / spy_vol if spy_vol > 0 else 0
        else:
            rvol = 0
        
        # Moving averages
        ma50 = np.mean(close[-50:]) if len(close) >= 50 else close[-1]
        ma100 = np.mean(close[-100:]) if len(close) >= 100 else close[-1]
        price_vs_50ma = close[-1] / ma50 if ma50 > 0 else 1
        price_vs_100ma = close[-1] / ma100 if ma100 > 0 else 1
        
        return {
            "symbol": sym,
            "price": float(close[-1]),
            "rs": round(float(rs), 3),
            "rvol": round(float(rvol), 3),
            "recent_return": round(float(recent_return), 3),
            "price_vs_50ma": round(float(price_vs_50ma), 3),
            "price_vs_100ma": round(float(price_vs_100ma), 3),
            "ma50": round(float(ma50), 2),
            "ma100": round(float(ma100), 2),
        }
    except Exception as exc:
        logger.debug("calculate_metrics skip %s: %s", sym, exc)
        return None

def scan_mode_2_premium_selling(data_map, spy_data):
    """Mode 2: Find high-IV weakness across ALL 2,600 symbols."""
    logger.info("\n=== MODE 2: PREMIUM SELLING (Full Market Scan) ===")
    candidates = []
    
    for sym, ohlcv in data_map.items():
        metrics = calculate_metrics(sym, ohlcv, spy_data)
        if not metrics:
            continue
        
        # Filter: Recent weakness > 5%
        if metrics['recent_return'] < -0.05:
            candidates.append({
                **metrics,
                "reason": f"Weakness {metrics['recent_return']*100:.1f}%"
            })
    
    logger.info(f"Found {len(candidates)} candidates")
    return sorted(candidates, key=lambda x: x['recent_return'])[:10]

def scan_mode_3_short_opportunities(data_map, spy_data):
    """Mode 3: Find confirmed downtrends across ALL 2,600 symbols."""
    logger.info("\n=== MODE 3: SHORT OPPORTUNITIES (Full Market Scan) ===")
    candidates = []
    
    for sym, ohlcv in data_map.items():
        metrics = calculate_metrics(sym, ohlcv, spy_data)
        if not metrics:
            continue
        
        # Filter: Below both MAs
        if metrics['price_vs_50ma'] < 1.0 and metrics['price_vs_100ma'] < 1.0:
            candidates.append({
                **metrics,
                "reason": f"Below 50MA ({metrics['price_vs_50ma']:.3f}) & 100MA ({metrics['price_vs_100ma']:.3f})"
            })
    
    logger.info(f"Found {len(candidates)} candidates")
    return sorted(candidates, key=lambda x: x['price_vs_100ma'])[:10]

def main():
    logger.info("="*60)
    logger.info("FULL-MARKET SCREENER (2,600 Symbols)")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info("="*60)
    
    # Load all symbols
    symbols = load_full_universe()
    if not symbols:
        logger.error("Failed to load symbols")
        return
    
    # Fetch data
    spy_data = yf.download("SPY", period="1y", progress=False)['Close']
    data_map = fetch_data(symbols, period="1y")
    
    # Scan all modes
    mode2_results = scan_mode_2_premium_selling(data_map, spy_data)
    mode3_results = scan_mode_3_short_opportunities(data_map, spy_data)
    
    # Save results
    results = {
        "timestamp": datetime.now().isoformat(),
        "universe_size": len(symbols),
        "symbols_scanned": len(data_map),
        "mode_2_candidates": mode2_results,
        "mode_3_candidates": mode3_results,
    }
    
    with open(WORKSPACE / "watchlist_fullmarket.json", 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"\n✅ COMPLETE: {len(mode2_results)} Mode 2 + {len(mode3_results)} Mode 3 candidates")
    logger.info(f"Saved to: watchlist_fullmarket.json")

if __name__ == "__main__":
    main()
