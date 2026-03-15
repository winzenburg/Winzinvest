#!/usr/bin/env python3
"""
Regime-Aware Screener (Mar 5, 2026)
Market: DOWNTREND + SECTOR ROTATION
- Mode 1: Find energy/materials LONG (outperformers in downtrend)
- Mode 2: Identify tech weakness for CALL SELLING (not puts)
- Mode 3: Strict shorts (both 50MA AND 100MA below)
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
        logging.FileHandler(LOGS_DIR / "screener_regime.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

WORKSPACE = TRADING_DIR

def load_universe():
    """Load full 2,600 symbols."""
    try:
        df = pd.read_csv(WORKSPACE / "watchlists" / "full_market_2600.csv")
        return df['symbol'].unique().tolist()
    except:
        return []

def fetch_data(symbols, period='1y'):
    """Fetch OHLCV data."""
    logger.info(f"Fetching {len(symbols)} symbols...")
    data_map = {}
    for i, sym in enumerate(symbols):
        if (i + 1) % 100 == 0:
            logger.info(f"Progress: {i+1}/{len(symbols)}")
        try:
            hist = yf.download(sym, period=period, progress=False)
            if not hist.empty:
                data_map[sym] = hist
        except:
            pass
    logger.info(f"✓ Fetched {len(data_map)} symbols")
    return data_map

def calculate_metrics(sym, ohlcv, spy_data):
    """Calculate metrics."""
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
    except:
        return None

def is_energy_materials(sym):
    """Check if symbol is energy/materials sector."""
    energy = {'XLE', 'OKE', 'MPC', 'PSX', 'VLO', 'HES', 'COP', 'EOG', 'XOM', 'CVX'}
    materials = {'FCX', 'RIO', 'BHP', 'VALE', 'NEM', 'TECK', 'CF', 'MOS', 'APD', 'DD'}
    return sym in energy or sym in materials

def is_tech(sym):
    """Check if symbol is tech sector."""
    tech_list = {'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'TSLA', 'INTC', 'AMD', 'QCOM', 'AVGO',
                 'ADBE', 'CRM', 'SNOW', 'CRWD', 'DDOG', 'NET', 'OKTA', 'ZS', 'SHOP', 'UPST'}
    return sym in tech_list or 'QQQ' in sym

def mode_1_sector_long(data_map, spy_data):
    """Mode 1: Energy/Materials LONG (outperformers in downtrend)."""
    logger.info("\n=== MODE 1: SECTOR LONG (Energy/Materials Breaking Out) ===")
    candidates = []
    
    for sym, ohlcv in data_map.items():
        if not is_energy_materials(sym):
            continue
        
        metrics = calculate_metrics(sym, ohlcv, spy_data)
        if not metrics:
            continue
        
        # Filter: RS > 0 (outperforming SPY) + Price > 50MA (uptrend)
        if metrics['rs'] > 0 and metrics['price_vs_50ma'] > 1.0:
            candidates.append({
                **metrics,
                "reason": f"Energy/Materials outperforming (RS {metrics['rs']:.3f}), above 50MA"
            })
    
    logger.info(f"Found {len(candidates)} candidates")
    return sorted(candidates, key=lambda x: x['rs'], reverse=True)[:5]

def mode_2_call_selling(data_map, spy_data):
    """Mode 2: Identify tech weakness for CALL SELLING (premium collection)."""
    logger.info("\n=== MODE 2: CALL SELLING (Tech Weakness) ===")
    candidates = []
    
    for sym, ohlcv in data_map.items():
        if not is_tech(sym):
            continue
        
        metrics = calculate_metrics(sym, ohlcv, spy_data)
        if not metrics:
            continue
        
        # Filter: Recent weakness > 2% (pullback for selling calls)
        if metrics['recent_return'] < -0.02:
            candidates.append({
                **metrics,
                "reason": f"Tech weakness {metrics['recent_return']*100:.1f}%, opportunity to sell calls",
                "trade_type": "sell_call"
            })
    
    logger.info(f"Found {len(candidates)} candidates")
    return sorted(candidates, key=lambda x: x['recent_return'])[:5]

def mode_3_strict_shorts(data_map, spy_data):
    """Mode 3: Strict shorts (both 50MA AND 100MA)."""
    logger.info("\n=== MODE 3: SHORT (Confirmed Downtrends) ===")
    candidates = []
    
    for sym, ohlcv in data_map.items():
        metrics = calculate_metrics(sym, ohlcv, spy_data)
        if not metrics:
            continue
        
        # Strict filter: Below BOTH MAs
        if metrics['price_vs_50ma'] < 1.0 and metrics['price_vs_100ma'] < 1.0:
            # Exclude penny stocks (price < $5)
            if metrics['price'] >= 5.0:
                candidates.append({
                    **metrics,
                    "reason": f"Confirmed downtrend (below 50MA & 100MA)"
                })
    
    logger.info(f"Found {len(candidates)} candidates")
    return sorted(candidates, key=lambda x: x['price_vs_100ma'])[:5]

def main():
    logger.info("="*60)
    logger.info("REGIME-AWARE SCREENER (Downtrend + Sector Rotation)")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info("="*60)
    
    symbols = load_universe()
    if not symbols:
        return
    
    spy_data = yf.download("SPY", period="1y", progress=False)['Close']
    data_map = fetch_data(symbols)
    
    mode1 = mode_1_sector_long(data_map, spy_data)
    mode2 = mode_2_call_selling(data_map, spy_data)
    mode3 = mode_3_strict_shorts(data_map, spy_data)
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "regime": "Downtrend + Sector Rotation",
        "mode_1_sector_long": mode1,
        "mode_2_call_selling": mode2,
        "mode_3_strict_shorts": mode3,
    }
    
    with open(WORKSPACE / "watchlist_regime.json", 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"\n✅ COMPLETE")
    logger.info(f"Mode 1 (Long): {len(mode1)} candidates")
    logger.info(f"Mode 2 (Calls): {len(mode2)} candidates")
    logger.info(f"Mode 3 (Shorts): {len(mode3)} candidates")

if __name__ == "__main__":
    main()
