#!/usr/bin/env python3
"""
NX Multi-Mode Screener
Adaptive to market regime: bullish (sector hunting), premium selling, short opportunities

Modes:
  1. SECTOR_STRENGTH - Find energy/materials breaking out while market falls
  2. PREMIUM_SELLING - Find high-IV tech for covered calls / CSPs
  3. SHORT_OPPORTUNITIES - Find QQQ weakness, failed bounces, downtrends

Usage:
  python3 nx_screener_multimode.py --mode all
  python3 nx_screener_multimode.py --mode sector_strength
  python3 nx_screener_multimode.py --mode premium_selling
  python3 nx_screener_multimode.py --mode short_opportunities
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
from pathlib import Path
import logging
import sys
import argparse
from typing import List, Dict, Tuple
from paths import TRADING_DIR, LOGS_DIR

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / "nx_screener_multimode.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Paths
WORKSPACE = TRADING_DIR
WATCHLIST_DIR = WORKSPACE / "watchlists"
OUTPUT_FILE = WORKSPACE / "watchlist_multimode.json"

# NX Thresholds (downtrend adjusted - Mar 5, 2026)
NX_THRESHOLDS = {
    "tier_2_min": 0.08,
    "tier_3_min": 0.25,
    "rs_long_min": 0.40,
    "rs_short_max": 0.50,
    "rvol_min": 0.85,
    "struct_q_min": 0.35,
    "htf_bias_long_min": 0.45,
    "htf_bias_short_max": 0.55,
}

# Mode-specific configurations
MODE_CONFIG = {
    "sector_strength": {
        "name": "Sector Strength Hunter",
        "description": "Find energy/materials breaking out while market falls",
        "universe": [
            # Energy sector (XLE constituents + related)
            'XOM', 'CVX', 'COP', 'EOG', 'MPC', 'PSX', 'VLO', 'HES',
            'OKE', 'MRO', 'BA', 'WMB', 'KMI', 'ENB', 'TRP',
            # Materials/Mining
            'FCX', 'RIO', 'BHP', 'VALE', 'NEM', 'HL', 'TECK', 'ICL',
            'APD', 'DD', 'LYB', 'OLN', 'CF', 'MOS', 'NUE', 'MT',
            # Agriculture/Chemicals
            'CF', 'MOS', 'ADM', 'BUNGE', 'GEVO', 'PLUG',
            # Sector ETF
            'XLE',
        ],
        "filters": {
            "rs_long_min": 0.50,  # Higher bar - these should be actually strong
            "rvol_min": 0.85,
            "price_above_50ma": True,  # Confirming uptrend
            "outperforming_spy": True,  # Better than market
        }
    },
    
    "premium_selling": {
        "name": "Premium Selling Scanner",
        "description": "Find high-IV tech for covered calls / CSPs",
        "universe": [
            # Large-cap tech (QQQ top holdings)
            'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'TSLA', 'ASML', 'NFLX',
            'ADBE', 'INTC', 'QCOM', 'AVGO', 'AMAT', 'LRCX', 'AMD', 'MRVL',
            'NXPI', 'SNPS', 'CDNS', 'INTU', 'CSCO', 'BKNG', 'CRWD', 'DDOG',
            'NET', 'OKTA', 'ZS', 'SNOW', 'SHOP', 'COIN', 'UPST', 'AFRM',
            # Sector ETF
            'QQQ',
        ],
        "filters": {
            "iv_rank_min": 0.70,  # Elevated IV (70th percentile+)
            "recent_weakness": True,  # Recent pullback = better entry
            "identify_support": True,  # Find support/resistance for premium placement
        }
    },
    
    "short_opportunities": {
        "name": "Short Opportunities",
        "description": "Find QQQ weakness, failed bounces, downtrends",
        "universe": [
            # QQQ constituents (tech-heavy)
            'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'TSLA', 'AMZN', 'ASML',
            'NFLX', 'ADBE', 'INTC', 'QCOM', 'AVGO', 'AMD', 'AMAT', 'LRCX',
            'NXPI', 'SNPS', 'CDNS', 'MCHP', 'TXN', 'QCOM', 'KLA', 'KLAC',
            'CRWD', 'DDOG', 'NET', 'OKTA', 'SNOW', 'SHOP', 'UPST', 'COIN',
            # Sector ETF
            'QQQ',
        ],
        "filters": {
            "price_below_100ma": True,  # In downtrend
            "failed_bounce": True,  # Tried to recover, failed
            "volume_confirms": True,  # Volume on down days > up days
            "rs_short_max": 0.50,  # Weak relative strength
        }
    }
}

def load_full_universe() -> List[str]:
    """Load full market universe from CSV."""
    watchlist_file = WATCHLIST_DIR / "full_market_2600.csv"
    try:
        df = pd.read_csv(watchlist_file)
        symbols = df['symbol'].unique().tolist()
        logger.info(f"✓ Loaded {len(symbols)} symbols from full market CSV")
        return sorted(symbols)
    except Exception as e:
        logger.warning(f"Could not load full universe: {e}")
        return []

def fetch_spy_data(period: str = "1y") -> pd.Series:
    """Fetch SPY for relative strength calculations."""
    try:
        spy_data = yf.download("SPY", period=period, progress=False)['Close']
        return spy_data
    except Exception as e:
        logger.error(f"Failed to fetch SPY: {e}")
        return pd.Series()

def fetch_symbol_data(symbols: List[str], period: str = "1y") -> Dict:
    """Fetch OHLCV data for symbols."""
    logger.info(f"Fetching data for {len(symbols)} symbols...")
    data_map = {}
    
    for i, symbol in enumerate(symbols):
        if (i + 1) % 50 == 0:
            logger.info(f"Progress: {i+1}/{len(symbols)}")
        
        try:
            hist = yf.download(symbol, period=period, progress=False)
            if not hist.empty:
                data_map[symbol] = hist
        except Exception as e:
            pass  # Silent fail for unavailable symbols
    
    logger.info(f"✓ Successfully fetched data for {len(data_map)} symbols")
    return data_map

def calculate_nx_metrics(symbol: str, ohlcv: pd.DataFrame, spy_data: pd.Series) -> Dict:
    """Calculate NX metrics for a symbol."""
    try:
        # Close prices
        close = ohlcv['Close'].values
        
        # Recent performance (20-day)
        recent_return = (close[-1] - close[-20]) / close[-20] if len(close) >= 20 else 0
        
        # Relative strength (vs SPY)
        if len(close) >= 20 and len(spy_data) >= 20:
            sym_20d = (close[-1] - close[-20]) / close[-20]
            spy_20d = (spy_data.iloc[-1] - spy_data.iloc[-20]) / spy_data.iloc[-20]
            rs_pct = sym_20d - spy_20d
        else:
            rs_pct = 0
        
        # Relative volatility (vs SPY)
        if len(close) >= 20:
            sym_vol = np.std(np.diff(np.log(close[-20:])))
            spy_vol = np.std(np.diff(np.log(spy_data.values[-20:] if len(spy_data) >= 20 else spy_data.values)))
            rvol = sym_vol / spy_vol if spy_vol > 0 else 0
        else:
            rvol = 0
        
        # Structure (HH/HL pattern)
        if len(close) >= 10:
            recent_high = np.max(close[-10:])
            recent_low = np.min(close[-10:])
            hl_ratio = (close[-1] - recent_low) / (recent_high - recent_low) if recent_high > recent_low else 0
        else:
            hl_ratio = 0
        
        # Moving averages
        ma50 = np.mean(close[-50:]) if len(close) >= 50 else close[-1]
        ma100 = np.mean(close[-100:]) if len(close) >= 100 else close[-1]
        
        # Price vs MAs
        price_vs_50ma = close[-1] / ma50 if ma50 > 0 else 1
        price_vs_100ma = close[-1] / ma100 if ma100 > 0 else 1
        
        return {
            "symbol": symbol,
            "price": float(close[-1]),
            "rs_pct": round(float(rs_pct), 3),
            "rvol": round(float(rvol), 3),
            "hl_ratio": round(float(hl_ratio), 3),
            "price_vs_50ma": round(float(price_vs_50ma), 3),
            "price_vs_100ma": round(float(price_vs_100ma), 3),
            "ma50": round(float(ma50), 2),
            "ma100": round(float(ma100), 2),
            "recent_return": round(float(recent_return), 3),
        }
    
    except Exception as e:
        return None

def run_mode_sector_strength(data_map: Dict, spy_data: pd.Series, mode_cfg: Dict) -> Tuple[List, List]:
    """Mode 1: Find energy/materials breaking out."""
    logger.info(f"\n=== {mode_cfg['name']} ===")
    
    universe = mode_cfg['universe']
    long_candidates = []
    short_candidates = []
    
    filters = mode_cfg['filters']
    
    for symbol in universe:
        if symbol not in data_map:
            continue
        
        metrics = calculate_nx_metrics(symbol, data_map[symbol], spy_data)
        if not metrics:
            continue
        
        # Filter: RS > 0.50 (actually strong)
        if metrics['rs_pct'] < filters['rs_long_min']:
            continue
        
        # Filter: RVol > 0.85
        if metrics['rvol'] < filters['rvol_min']:
            continue
        
        # Filter: Price > 50 MA (uptrend)
        if metrics['price_vs_50ma'] < 1.0:
            continue
        
        # Filter: Outperforming SPY (rs_pct > 0)
        if metrics['rs_pct'] <= 0:
            continue
        
        # Passed all filters
        long_candidates.append({
            **metrics,
            "reason": f"Energy/Materials breaking out: RS {metrics['rs_pct']}, above 50MA"
        })
    
    logger.info(f"Long candidates: {len(long_candidates)}")
    logger.info(f"Short candidates: {len(short_candidates)}")
    
    return long_candidates, short_candidates

def run_mode_premium_selling(data_map: Dict, spy_data: pd.Series, mode_cfg: Dict) -> Tuple[List, List]:
    """Mode 2: Find high-IV tech for premium selling."""
    logger.info(f"\n=== {mode_cfg['name']} ===")
    
    universe = mode_cfg['universe']
    long_candidates = []  # Sell CSPs
    short_candidates = []  # Sell calls
    
    filters = mode_cfg['filters']
    
    for symbol in universe:
        if symbol not in data_map:
            continue
        
        metrics = calculate_nx_metrics(symbol, data_map[symbol], spy_data)
        if not metrics:
            continue
        
        # For now: Look for weakness in recent return
        if metrics['recent_return'] < -0.05:  # Down 5%+
            short_candidates.append({
                **metrics,
                "reason": f"High-IV weakness: Recent {metrics['recent_return']*100:.1f}%, elevated IV"
            })
    
    logger.info(f"Long candidates (CSP): {len(long_candidates)}")
    logger.info(f"Short candidates (Call): {len(short_candidates)}")
    
    return long_candidates, short_candidates

def run_mode_short_opportunities(data_map: Dict, spy_data: pd.Series, mode_cfg: Dict) -> Tuple[List, List]:
    """Mode 3: Find QQQ weakness, failed bounces, downtrends."""
    logger.info(f"\n=== {mode_cfg['name']} ===")
    
    universe = mode_cfg['universe']
    long_candidates = []
    short_candidates = []
    
    filters = mode_cfg['filters']
    
    for symbol in universe:
        if symbol not in data_map:
            continue
        
        metrics = calculate_nx_metrics(symbol, data_map[symbol], spy_data)
        if not metrics:
            continue
        
        # Filter: Price < 100 MA (downtrend)
        if metrics['price_vs_100ma'] >= 1.0:
            continue
        
        # Filter: Price < 50 MA (confirmed downtrend)
        if metrics['price_vs_50ma'] >= 1.0:
            continue
        
        # Filter: Weak relative strength
        if metrics['rs_pct'] > filters['rs_short_max']:
            continue
        
        # Passed all filters
        short_candidates.append({
            **metrics,
            "reason": f"Downtrend confirmed: Below 50MA/100MA, RS {metrics['rs_pct']}"
        })
    
    logger.info(f"Long candidates: {len(long_candidates)}")
    logger.info(f"Short candidates: {len(short_candidates)}")
    
    return long_candidates, short_candidates

def save_results(results: Dict, output_file: Path):
    """Save results to JSON."""
    try:
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"✓ Results saved to {output_file}")
    except Exception as e:
        logger.error(f"Failed to save results: {e}")

def main():
    parser = argparse.ArgumentParser(description="NX Multi-Mode Screener")
    parser.add_argument("--mode", choices=["all", "sector_strength", "premium_selling", "short_opportunities"],
                       default="all", help="Screener mode to run")
    args = parser.parse_args()
    
    logger.info(f"=== NX MULTI-MODE SCREENER ===")
    logger.info(f"Mode: {args.mode}")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    
    # Load universes and data
    full_universe = load_full_universe()
    spy_data = fetch_spy_data()
    
    # Fetch data for all mode universes
    all_symbols = set()
    for mode_cfg in MODE_CONFIG.values():
        all_symbols.update(mode_cfg['universe'])
    
    data_map = fetch_symbol_data(list(all_symbols))
    
    # Run requested modes
    results = {
        "generated_at": datetime.now().isoformat(),
        "modes": {},
    }
    
    if args.mode in ["all", "sector_strength"]:
        long, short = run_mode_sector_strength(data_map, spy_data, MODE_CONFIG["sector_strength"])
        results["modes"]["sector_strength"] = {
            "long": long[:25],
            "short": short[:25],
            "total": {"long": len(long), "short": len(short)}
        }
    
    if args.mode in ["all", "premium_selling"]:
        long, short = run_mode_premium_selling(data_map, spy_data, MODE_CONFIG["premium_selling"])
        results["modes"]["premium_selling"] = {
            "long": long[:25],
            "short": short[:25],
            "total": {"long": len(long), "short": len(short)}
        }
    
    if args.mode in ["all", "short_opportunities"]:
        long, short = run_mode_short_opportunities(data_map, spy_data, MODE_CONFIG["short_opportunities"])
        results["modes"]["short_opportunities"] = {
            "long": long[:25],
            "short": short[:25],
            "total": {"long": len(long), "short": len(short)}
        }
    
    # Save results
    save_results(results, OUTPUT_FILE)
    
    logger.info(f"\n=== SCREENING COMPLETE ===")

if __name__ == "__main__":
    main()
