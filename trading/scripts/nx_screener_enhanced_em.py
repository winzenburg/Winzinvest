#!/usr/bin/env python3
"""
NX Enhanced Screener with Emerging Market ETFs
Runs in PARALLEL with nx_screener_production.py
Evaluates regional EM ETFs (SA, Brazil, China, Korea, Mexico) using same NX criteria
No bias, no weighting—just expanded universe for technical analysis

CHANGE LOG:
- Feb 28, 2026: Created to include EM regional tickers
- Loads from emerging_markets_regional.json
- Outputs separate watchlist for comparison
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
from pathlib import Path
import logging
import time
import sys

# Add scripts dir to path for imports
SCRIPTS_DIR = Path.home() / ".openclaw" / "workspace" / "trading" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from earnings_calendar import get_blackout_symbols as get_earnings_blackout
    from economic_calendar import is_economic_blackout, get_blackout_reason
    from regime_detector import RegimeDetector
    CALENDAR_MODULES_LOADED = True
    REGIME_DETECTOR_LOADED = True
except ImportError as e:
    print(f"Warning: Some modules not loaded: {e}")
    CALENDAR_MODULES_LOADED = False
    REGIME_DETECTOR_LOADED = False

# Setup logging
LOG_DIR = Path.home() / ".openclaw" / "workspace" / "trading" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "nx_screener_enhanced_em.log"

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

WATCHLIST_DIR = Path.home() / ".openclaw" / "workspace" / "trading" / "watchlists"
EM_WATCHLIST_FILE = WATCHLIST_DIR / "emerging_markets_regional.json"
OUTPUT_WATCHLIST = Path.home() / ".openclaw" / "workspace" / "trading" / "watchlist_enhanced_em.json"

# NX Criteria (LOWERED THRESHOLDS for better candidate flow in EM universe)
NX = {
    "tier_2_min": 0.05,      # Lowered from 0.10
    "tier_3_min": 0.20,      # Lowered from 0.30
    "rs_long_min": 0.40,     # Lowered from 0.50
    "rs_short_max": 0.60,    # Raised from 0.50
    "rvol_min": 0.80,        # Lowered from 1.00
    "struct_q_min": 0.25,    # Lowered from 0.35
    "htf_bias_long_min": 0.35,  # Lowered from 0.45
    "htf_bias_short_max": 0.65, # Raised from 0.55
}

def load_em_tickers():
    """Load emerging market regional tickers from JSON."""
    try:
        with open(EM_WATCHLIST_FILE, 'r') as f:
            data = json.load(f)
            tickers = data.get('all_tickers', [])
            logger.info(f"Loaded {len(tickers)} EM tickers from {EM_WATCHLIST_FILE}")
            return tickers
    except Exception as e:
        logger.error(f"Failed to load EM tickers: {e}")
        return []

def fetch_spy_data():
    """Fetch SPY data for relative strength calculations."""
    try:
        logger.info("Fetching SPY data...")
        spy = yf.download("SPY", period="1y", progress=False)
        logger.info("SPY data fetched")
        return spy
    except Exception as e:
        logger.error(f"Failed to fetch SPY: {e}")
        return None

def fetch_data(symbols, retries=2):
    """Fetch OHLCV data for symbols."""
    logger.info(f"Fetching data for {len(symbols)} EM ETFs...")
    
    data_map = {}
    
    for i, symbol in enumerate(symbols):
        if (i + 1) % 5 == 0:
            logger.info(f"Progress: {i+1}/{len(symbols)}")
        
        for attempt in range(retries):
            try:
                df = yf.download(symbol, period="1y", progress=False)
                if df is not None and len(df) > 100:
                    data_map[symbol] = df
                    break
                time.sleep(0.1)
            except Exception as e:
                if attempt == retries - 1:
                    logger.warning(f"Failed {symbol}: {str(e)[:50]}")
                time.sleep(0.5)
    
    logger.info(f"Successfully fetched data for {len(data_map)} EM ETFs")
    return data_map

def calculate_metrics(symbol, df, spy_df=None):
    """Calculate NX metrics for a symbol. Identical to production screener."""
    try:
        close = df['Close'].values
        volume = df['Volume'].values
        high = df['High'].values
        low = df['Low'].values
        
        if len(close) < 126 or close[-1] <= 0:
            return None
        
        # Momentum (ROC)
        roc_21 = ((close[-1] - close[-22]) / close[-22] * 100) if len(close) > 22 else 0
        roc_63 = ((close[-1] - close[-64]) / close[-64] * 100) if len(close) > 64 else 0
        roc_126 = ((close[-1] - close[-127]) / close[-127] * 100) if len(close) > 127 else 0
        
        momentum = (roc_21 + roc_63 + roc_126) / 3.0
        
        # ATR % (volatility)
        tr_list = []
        for i in range(1, min(len(close), 15)):
            tr = max(
                high[i] - low[i],
                abs(high[i] - close[i-1]),
                abs(low[i] - close[i-1])
            )
            tr_list.append(tr)
        
        atr = np.mean(tr_list) if tr_list else 0
        atr_pct = (atr / close[-1] * 100) if close[-1] > 0 else 0
        
        # CompScore
        if atr_pct > 0:
            comp_score = (momentum / (atr_pct / 2.0) * 100 + 100) / 200.0
        else:
            comp_score = (momentum + 100) / 200.0
        comp_score = max(0, min(1, comp_score))
        
        # Relative Strength vs SPY
        if spy_df is not None and len(spy_df) >= 252:
            try:
                sym_dates = df.index
                spy_dates = spy_df.index
                common_idx = sym_dates.intersection(spy_dates)[-252:]
                
                sym_close_rs = df.loc[common_idx, 'Close'].values
                spy_close_rs = spy_df.loc[common_idx, 'Close'].values
                
                sym_return = sym_close_rs[-1] / sym_close_rs[0] if sym_close_rs[0] > 0 else 1.0
                spy_return = spy_close_rs[-1] / spy_close_rs[0] if spy_close_rs[0] > 0 else 1.0
                
                rs_ratio = sym_return / spy_return if spy_return > 0 else 1.0
                rs_pct = max(0, min(1, (rs_ratio - 0.5) * 0.5 + 0.5))
            except Exception:
                rs_pct = 0.5
        else:
            rs_pct = max(0, min(1, (momentum + 50) / 100.0))
        
        # Relative Volume
        if len(volume) >= 50:
            recent_vol = np.mean(volume[-21:-1])
            prior_vol = np.mean(volume[-51:-21])
            rvol = recent_vol / prior_vol if prior_vol > 0 else 1.0
        else:
            rvol = 1.0
        
        # Structure Quality
        if len(close) >= 20:
            returns = np.diff(close[-21:])
            positive = np.sum(returns > 0)
            struct_q = positive / len(returns)
        else:
            struct_q = 0.5
        
        # HTF Bias (weekly/monthly)
        if len(close) >= 252:
            weekly_ret = (close[-1] - close[-5]) / close[-5] if close[-5] > 0 else 0
            monthly_ret = (close[-1] - close[-21]) / close[-21] if close[-21] > 0 else 0
            htf_bias = (weekly_ret + monthly_ret) / 2.0
            htf_bias_pct = max(0, min(1, (htf_bias + 0.05) / 0.1))
        else:
            htf_bias_pct = 0.5
        
        # Tier Classification
        if comp_score >= 0.70:
            tier = 1
        elif comp_score >= 0.50:
            tier = 2
        else:
            tier = 3
        
        return {
            "symbol": symbol,
            "comp_score": float(round(float(comp_score), 4)),
            "rs_pct": float(round(float(rs_pct), 4)),
            "rvol": float(round(float(rvol), 4)),
            "struct_q": float(round(float(struct_q), 4)),
            "htf_bias": float(round(float(htf_bias_pct), 4)),
            "momentum": float(round(float(momentum), 2)),
            "atr_pct": float(round(float(atr_pct), 2)),
            "price": float(round(float(close[-1]), 2)),
            "tier": int(tier)
        }
    except Exception as e:
        logger.warning(f"Error calculating metrics for {symbol}: {str(e)[:50]}")
        return None

def evaluate_candidates(metrics_list, spy_df=None):
    """Evaluate candidates against NX criteria."""
    long_candidates = []
    short_candidates = []
    
    for m in metrics_list:
        if m is None:
            continue
        
        symbol = m['symbol']
        tier = m['tier']
        
        # Determine tier minimum
        if tier == 1:
            tier_min = 0.0  # Tier 1 always qualifies
        elif tier == 2:
            tier_min = NX['tier_2_min']
        else:
            tier_min = NX['tier_3_min']
        
        # Long logic
        if m['comp_score'] >= tier_min:
            rs_ok = m['rs_pct'] >= NX['rs_long_min']
            rvol_ok = m['rvol'] >= NX['rvol_min']
            struct_ok = m['struct_q'] >= NX['struct_q_min']
            htf_ok = m['htf_bias'] >= NX['htf_bias_long_min']
            
            if rs_ok and rvol_ok and struct_ok and htf_ok:
                long_candidates.append({
                    "symbol": symbol,
                    "comp_score": m['comp_score'],
                    "rs": m['rs_pct'],
                    "rvol": m['rvol'],
                    "struct_q": m['struct_q'],
                    "htf_bias": m['htf_bias'],
                    "price": m['price'],
                    "tier": tier,
                    "entry_signal": "NX Long"
                })
        
        # Short logic
        if m['comp_score'] < (1 - tier_min):
            rs_ok = m['rs_pct'] <= NX['rs_short_max']
            rvol_ok = m['rvol'] >= NX['rvol_min']
            struct_ok = m['struct_q'] <= (1 - NX['struct_q_min'])
            htf_ok = m['htf_bias'] <= NX['htf_bias_short_max']
            
            if rs_ok and rvol_ok and struct_ok and htf_ok:
                short_candidates.append({
                    "symbol": symbol,
                    "comp_score": m['comp_score'],
                    "rs": m['rs_pct'],
                    "rvol": m['rvol'],
                    "struct_q": m['struct_q'],
                    "htf_bias": m['htf_bias'],
                    "price": m['price'],
                    "tier": tier,
                    "entry_signal": "NX Short"
                })
    
    return long_candidates, short_candidates

def run_enhanced_em_screener():
    """Main screener function."""
    logger.info("=" * 80)
    logger.info("NX ENHANCED SCREENER - EMERGING MARKETS")
    logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    
    # Load EM tickers
    em_tickers = load_em_tickers()
    if not em_tickers:
        logger.error("No EM tickers loaded. Exiting.")
        return
    
    # Fetch SPY data
    spy_df = fetch_spy_data()
    
    # Fetch EM data
    data_map = fetch_data(em_tickers)
    
    # Calculate metrics
    logger.info("Calculating NX metrics...")
    metrics_list = []
    for symbol, df in data_map.items():
        m = calculate_metrics(symbol, df, spy_df)
        if m:
            metrics_list.append(m)
    
    logger.info(f"Calculated metrics for {len(metrics_list)} symbols")
    
    # Evaluate
    logger.info("Evaluating against NX criteria...")
    long_cands, short_cands = evaluate_candidates(metrics_list, spy_df)
    
    # Sort by comp_score
    long_cands.sort(key=lambda x: x['comp_score'], reverse=True)
    short_cands.sort(key=lambda x: x['comp_score'])
    
    # Log results (only passing candidates)
    if long_cands:
        logger.info(f"LONG candidates: {len(long_cands)}")
        for c in long_cands:
            logger.info(f"  {c['symbol']}: comp={c['comp_score']}, rs={c['rs']}, rvol={c['rvol']}, struct={c['struct_q']}, htf={c['htf_bias']}")
    else:
        logger.info("LONG candidates: 0")
    
    if short_cands:
        logger.info(f"SHORT candidates: {len(short_cands)}")
        for c in short_cands:
            logger.info(f"  {c['symbol']}: comp={c['comp_score']}, rs={c['rs']}, rvol={c['rvol']}, struct={c['struct_q']}, htf={c['htf_bias']}")
    else:
        logger.info("SHORT candidates: 0")
    
    # Write output
    output_data = {
        "generated_at": datetime.now().isoformat(),
        "screener": "nx_screener_enhanced_em",
        "long_candidates": long_cands,
        "short_candidates": short_cands,
        "regime": None,
        "summary": {
            "long_count": len(long_cands),
            "short_count": len(short_cands),
            "total_count": len(long_cands) + len(short_cands),
            "symbols_scanned": len(metrics_list)
        }
    }
    
    with open(OUTPUT_WATCHLIST, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    logger.info(f"Output written to {OUTPUT_WATCHLIST}")
    logger.info("=" * 80)
    logger.info("SCREENER COMPLETE")
    logger.info("=" * 80)
    
    # Auto-execute passing candidates via EM Signal Executor
    logger.info("=" * 80)
    logger.info("Triggering EM Signal Executor for auto-execution...")
    logger.info("=" * 80)
    try:
        import subprocess
        executor_path = SCRIPTS_DIR / "em_signal_executor.py"
        result = subprocess.run(
            ['python3', str(executor_path)],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            logger.info("✅ EM Signal Executor completed successfully")
            if result.stdout:
                logger.info(f"Executor output:\n{result.stdout}")
        else:
            logger.error(f"❌ EM Signal Executor failed with code {result.returncode}")
            if result.stderr:
                logger.error(f"Executor error:\n{result.stderr}")
    except Exception as e:
        logger.error(f"Failed to trigger EM Signal Executor: {e}")
    
    return output_data

if __name__ == "__main__":
    run_enhanced_em_screener()
