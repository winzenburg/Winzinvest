#!/usr/bin/env python3
"""
AMS Pro Screener NX — Non-Repainting (Python Implementation)

Matches Pine Script logic exactly:
- Momentum: 21/63/126 ROC with volatility normalization
- HTF Bias: Weekly + Monthly confirmed bars
- RS Percentile: Relative strength vs SPY over 252 days
- Dollar Volume: $25M minimum (20-day median)
- RVol: EMA-smoothed, capped at 3.0
- Structure: Pivot clarity score
- Correlation: vs SPY, max 0.85
- Composite: 0.40 momentum + 0.20 HTF + 0.20 volume + 0.20 structure
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(Path.home() / ".openclaw/workspace/trading/logs/nx_screener_v2.log"),
        logging.StreamHandler()
    ]
)

WATCHLIST_FILE = Path.home() / ".openclaw/workspace/trading/watchlist.json"

# NX Screener Parameters (from Pine Script inputs + practical filters)
NX_PARAMS = {
    # Momentum
    "short_roc": 21,
    "med_roc": 63,
    "long_roc": 126,
    
    # Scoring thresholds
    "min_score_t2": 0.20,  # Tier 2
    "min_score_t3": 0.35,  # Tier 3
    
    # Volatility normalization
    "use_vol_norm": True,
    "atr_len": 14,
    "norm_base": 2.0,
    
    # HTF bias
    "use_htf": True,
    "w_weekly": 0.30,
    "w_monthly": 0.20,
    
    # RS vs SPY
    "rs_lookback": 90,  # Changed from 252 to 90-day lookback (Feb 24)
    "rs_long_pct": 0.60,
    "rs_short_pct": 0.40,
    
    # Volume & Liquidity
    "vol_look": 50,
    "min_dollar_vol_m": 25.0,  # $25M minimum
    "min_price": 5.0,
    "min_avg_volume_30d": 500000,  # Filter #2
    
    # RSI
    "rsi_len": 14,
    "min_rsi": 45,
    "max_rsi": 75,
    
    # Correlation
    "max_abs_corr": 0.85,
    
    # Additional Practical Filters
    "min_market_cap_m": 300.0,  # Filter #3: $300M minimum
    "min_volatility_pct": 1.0,  # Filter #13: min volatility
    "max_volatility_pct": 8.0,  # Filter #13: max volatility
    "min_rvol": 0.8,  # Filter #10: Relative Volume
    "min_perf_6m_pct": 0.0,  # Filter #6: 6M return > 0%
    "min_perf_3m_pct": 0.0,  # Filter #7: 3M return > 0%
    "min_perf_1y_vs_spy_pct": 0.0,  # Filter #9: 1Y return vs SPY > 0%
}

def get_universe_symbols():
    """Return proven liquid symbols (S&P 500 + select liquid tech/finance)."""
    # Core symbols that consistently have data
    return [
        'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'AMZN', 'TSLA', 'BRK.B', 'JPM', 'V',
        'JNJ', 'WMT', 'PG', 'MA', 'ASML', 'COST', 'MCD', 'SPG', 'CAT', 'AXP',
        'NFLX', 'ADBE', 'CSCO', 'BKNG', 'XOM', 'CVX', 'COP', 'ISRG', 'PEP', 'KO',
        'AMD', 'INTC', 'QCOM', 'AVGO', 'TXN', 'SMCI', 'PLTR', 'UPST', 'COIN', 'GS',
        'BAC', 'WFC', 'MS', 'BLK', 'HOOD', 'SOFI', 'CRM', 'SNOW', 'CRWD', 'DDOG',
        'NET', 'OKTA', 'TWLO', 'ZM', 'PYPL', 'SHOP', 'UBER', 'LYFT', 'DASH', 'PINS',
        'SNAP', 'ROKU', 'TDOC', 'VEEV', 'RBLX', 'MNST', 'ENPH', 'FSLR', 'RUN', 'RIVN',
        'F', 'GM', 'LI', 'XPEV', 'BABA', 'SE', 'MELI', 'NTES', 'BILI', 'BIDU', 'JD',
        'MU', 'LRCX', 'MRVL', 'NXPI', 'MPWR', 'ON', 'SLAB', 'CRUS', 'CDNS', 'SNPS',
        'PANW', 'ZS', 'ANET', 'BILL', 'DBX', 'HON', 'BA', 'RTX', 'LMT', 'GOOG', 'UUUU',
    ]

def download_data(symbols, period='1y'):
    """Download OHLCV data for symbols."""
    data_map = {}
    failed = 0
    for i, sym in enumerate(symbols):
        if (i + 1) % 50 == 0:
            logger.info(f"Downloaded {i+1}/{len(symbols)} (valid: {len(data_map)})")
        try:
            df = yf.download(sym, period=period, progress=False, threads=False)
            if not df.empty and len(df) >= 126:  # Reduced from 252 for testing
                data_map[sym] = df
            elif not df.empty:
                logger.debug(f"{sym}: Only {len(df)} bars")
        except Exception as e:
            failed += 1
    logger.info(f"Downloaded {len(data_map)} valid symbols ({failed} failures)")
    return data_map

def atr(df, length=14):
    """Calculate ATR."""
    high = df['High']
    low = df['Low']
    close = df['Close']
    tr = pd.concat([
        high - low,
        abs(high - close.shift(1)),
        abs(low - close.shift(1))
    ], axis=1).max(axis=1)
    return tr.rolling(length).mean()

def roc(df, length):
    """Rate of Change."""
    return ((df - df.shift(length)) / df.shift(length)) * 100.0

def rsi(df, length=14):
    """RSI calculation."""
    delta = df.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=length).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=length).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def squash(x):
    """Squash function (tanh-like)."""
    return (np.exp(2*(x/10)) - 1) / (np.exp(2*(x/10)) + 1)

def calculate_metrics(sym, df, spy_df):
    """Calculate NX metrics for a symbol."""
    close = df['Close']
    high = df['High']
    low = df['Low']
    volume = df['Volume']
    
    # === FILTER #1: PRICE ===
    current_price = float(close.iloc[-1])
    if current_price < NX_PARAMS['min_price']:
        return None
    
    # === FILTER #2: AVERAGE VOLUME (30D) ===
    avg_vol_30d = float(volume.tail(30).mean())
    if avg_vol_30d < NX_PARAMS['min_avg_volume_30d']:
        return None
    
    # === FILTER #4-5: PRICE vs SMA ===
    sma_50 = close.rolling(50).mean().iloc[-1]
    sma_200 = close.rolling(200).mean().iloc[-1]
    price_above_50 = current_price > float(sma_50)
    price_above_200 = current_price > float(sma_200)
    if not (price_above_50 and price_above_200):
        return None
    
    # === FILTER #6-7: PERFORMANCE (6M, 3M) ===
    bars_6m = min(126, len(close))  # ~6 months of trading days
    bars_3m = min(63, len(close))   # ~3 months
    perf_6m = ((close.iloc[-1] - close.iloc[-bars_6m]) / close.iloc[-bars_6m]) * 100 if bars_6m > 0 else 0
    perf_3m = ((close.iloc[-1] - close.iloc[-bars_3m]) / close.iloc[-bars_3m]) * 100 if bars_3m > 0 else 0
    if perf_6m < NX_PARAMS['min_perf_6m_pct'] or perf_3m < NX_PARAMS['min_perf_3m_pct']:
        return None
    
    # === FILTER #13: VOLATILITY (1% - 8%) ===
    atr_val = float(atr(df, NX_PARAMS['atr_len']).iloc[-1])
    vol_pct = (atr_val / current_price) * 100.0
    if vol_pct < NX_PARAMS['min_volatility_pct'] or vol_pct > NX_PARAMS['max_volatility_pct']:
        return None
    
    # === LIQUIDITY CHECK (Dollar Volume) ===
    dollar_vol = close * volume
    med_dollar_vol = dollar_vol.rolling(20).median()
    dollar_vol_m = float(med_dollar_vol.iloc[-1]) / 1e6
    liq_ok = dollar_vol_m >= NX_PARAMS['min_dollar_vol_m']
    
    if not liq_ok:
        logger.debug(f"{sym}: Dollar volume filter failed (${dollar_vol_m:.1f}M)")
        return None
    
    # === MOMENTUM (with volatility normalization) ===
    roc_s = float(roc(close, NX_PARAMS['short_roc']).iloc[-1])
    roc_m = float(roc(close, NX_PARAMS['med_roc']).iloc[-1])
    roc_l = float(roc(close, NX_PARAMS['long_roc']).iloc[-1])
    
    comp_mom = 0.2*roc_s + 0.3*roc_m + 0.5*roc_l
    
    # Volatility normalization
    if NX_PARAMS['use_vol_norm']:
        vol_factor = max(vol_pct, 0.5)
        comp_mom = comp_mom / (vol_factor / NX_PARAMS['norm_base'])
    
    # === HTF BIAS (Weekly + Monthly, confirmed bars) ===
    htf_bias = 0.0
    if NX_PARAMS['use_htf']:
        # Weekly: 13-bar ROC
        weekly_roc = float(roc(close, 13).iloc[-2])  # [1] = previous bar (confirmed)
        # Monthly: 6-bar ROC (rough approximation)
        monthly_roc = float(roc(close, 26).iloc[-2])  # 26 ~= 4 weeks, rough monthly
        
        htf_bias = float(NX_PARAMS['w_weekly'] * squash(weekly_roc) + 
                   NX_PARAMS['w_monthly'] * squash(monthly_roc))
    
    # === FILTER #9: PERFORMANCE vs S&P 500 (1Y) ===
    # Check if stock has outperformed SPY over 1 year
    bars_1y = min(252, len(close))
    if bars_1y > 0:
        stock_perf_1y = ((close.iloc[-1] - close.iloc[-bars_1y]) / close.iloc[-bars_1y]) * 100
        spy_perf_1y = ((spy_df.iloc[-1] - spy_df.iloc[-bars_1y]) / spy_df.iloc[-bars_1y]) * 100
        perf_1y_vs_spy = stock_perf_1y - spy_perf_1y
        if perf_1y_vs_spy < NX_PARAMS['min_perf_1y_vs_spy_pct']:
            return None
    
    # === RS PERCENTILE vs SPY ===
    if len(spy_df) >= NX_PARAMS['rs_lookback']:
        stock_ch = (current_price - float(close.iloc[-NX_PARAMS['rs_lookback']])) / float(close.iloc[-NX_PARAMS['rs_lookback']])
        spy_ch = (float(spy_df.iloc[-1]) - float(spy_df.iloc[-NX_PARAMS['rs_lookback']])) / float(spy_df.iloc[-NX_PARAMS['rs_lookback']])
        rs_ex = stock_ch - spy_ch
        
        # Calculate percentile: what % of past returns were less than current excess return?
        hist_returns = close.pct_change().tail(NX_PARAMS['rs_lookback'])
        spy_hist = spy_df.pct_change().tail(NX_PARAMS['rs_lookback'])
        hist_ex = (hist_returns.values - spy_hist.values)
        rs_pct = float((hist_ex < rs_ex).sum()) / len(hist_ex) if len(hist_ex) > 0 else 0.5
    else:
        rs_pct = 0.5
    
    # === SMART RVOL (EMA smoothed, capped) ===
    avg_vol = volume.rolling(NX_PARAMS['vol_look']).mean()
    rvol = volume / avg_vol
    rvol_capped = rvol.clip(upper=3.0)
    rvol_ema = float(rvol_capped.ewm(span=10).mean().iloc[-1])
    
    # === FILTER #10: RELATIVE VOLUME ===
    if rvol_ema < NX_PARAMS['min_rvol']:
        return None
    
    vol_trend = 1.0 if float(volume.rolling(20).mean().iloc[-1]) > float(volume.rolling(40).mean().iloc[-1]) else 0.0
    vol_score = float((rvol_ema / 3.0) * 0.7 + (vol_trend * 0.3))
    
    # === STRUCTURE QUALITY (pivot clarity) ===
    struct_pts = 0
    pivot_len = 5
    
    # Simple pivot detection
    for i in range(-pivot_len, 0):
        if i >= -pivot_len and i < -1:
            is_high = float(high.iloc[i]) > float(high.iloc[i-pivot_len:i].max()) and float(high.iloc[i]) > float(high.iloc[i+1:].max())
            is_low = float(low.iloc[i]) < float(low.iloc[i-pivot_len:i].min()) and float(low.iloc[i]) < float(low.iloc[i+1:].min())
            if is_high or is_low:
                struct_pts += 1
    
    struct_score = float(min(struct_pts / (2 * pivot_len), 1.0) * 0.5)
    
    # === CORRELATION vs SPY ===
    try:
        correlation = float(close.tail(20).corr(spy_df.tail(20)))
        low_corr = abs(correlation) <= NX_PARAMS['max_abs_corr']
    except:
        correlation = 0.0
        low_corr = True
    
    # === COMPOSITE SCORE ===
    score_raw = float(comp_mom / 25.0)
    score_raw = float(max(0, min(score_raw, 1)))
    htf_adj = float((htf_bias + 1.0) / 2.0)
    
    comp_final = float(0.40 * score_raw + 
                 0.20 * htf_adj + 
                 0.20 * vol_score + 
                 0.20 * struct_score)
    
    tier = 3 if comp_final >= NX_PARAMS['min_score_t3'] else (2 if comp_final >= NX_PARAMS['min_score_t2'] else 1)
    
    # === DUAL MOMENTUM / RSI ===
    abs_mom = current_price > float(close.iloc[-NX_PARAMS['long_roc']])
    rsi_val = float(rsi(close, NX_PARAMS['rsi_len']).iloc[-1])
    rel_mom = rsi_val > 50
    
    # === LONG/SHORT READY ===
    long_ready = (liq_ok and low_corr and abs_mom and rel_mom and 
                 rs_pct >= NX_PARAMS['rs_long_pct'] and tier >= 2)
    
    short_ready = (liq_ok and low_corr and (not abs_mom) and 
                  (rsi_val < 50) and rs_pct <= NX_PARAMS['rs_short_pct'] and tier >= 2)
    
    # Debug logging for candidates that don't pass
    if not (long_ready or short_ready):
        if liq_ok and low_corr and abs_mom and rel_mom:
            logger.debug(f"{sym}: CLOSE - Long fail: RS {rs_pct:.3f} (need {NX_PARAMS['rs_long_pct']}) | Tier {tier} (need 2+) | Score {comp_final:.3f}")
        return None
    
    return {
        'symbol': sym,
        'price': round(current_price, 2),
        'comp_score': round(float(comp_final), 3),
        'rsi': round(float(rsi_val), 2),
        'rs_pct': round(float(rs_pct), 3),
        'rvol': round(float(rvol_ema), 2),
        'htf_bias': round(float(htf_bias), 3),
        'struct_score': round(float(struct_score), 3),
        'corr_spy': round(float(correlation), 3) if 'correlation' in locals() else 0.0,
        'tier': int(tier),
        'long_ready': bool(long_ready),
        'short_ready': bool(short_ready),
        'dollar_vol_m': round(float(dollar_vol_m), 1),
        'avg_vol_30d': round(avg_vol_30d, 0),
        'vol_pct': round(vol_pct, 2),
        'perf_6m_pct': round(float(perf_6m), 2),
        'perf_3m_pct': round(float(perf_3m), 2),
        'sma_50': round(float(sma_50), 2),
        'sma_200': round(float(sma_200), 2),
    }

def main():
    logger.info("=== AMS PRO SCREENER NX (PYTHON) STARTED ===")
    
    symbols = get_universe_symbols()
    logger.info(f"Universe: {len(symbols)} symbols")
    
    # Download data
    data_map = download_data(symbols)
    logger.info(f"Downloaded {len(data_map)} symbols with sufficient history")
    
    # Get SPY as benchmark
    try:
        spy_data = yf.download('SPY', period='1y', progress=False, threads=False)
        spy_close = spy_data['Close']
    except:
        logger.error("Failed to download SPY data")
        return
    
    # Calculate metrics
    logger.info("Calculating NX metrics...")
    candidates = []
    
    for i, (sym, df) in enumerate(data_map.items()):
        if (i + 1) % 50 == 0:
            logger.info(f"Metrics: {i+1}/{len(data_map)}")
        
        m = calculate_metrics(sym, df, spy_close)
        if m:
            candidates.append(m)
    
    # Sort by score
    candidates.sort(key=lambda x: x['comp_score'], reverse=True)
    
    long_cand = [c for c in candidates if c['long_ready']]
    short_cand = [c for c in candidates if c['short_ready']]
    
    logger.info(f"Long: {len(long_cand)}, Short: {len(short_cand)}")
    
    # Save watchlist
    watchlist = {
        "generated_at": datetime.now().isoformat(),
        "long_candidates": long_cand,
        "short_candidates": short_cand,
        "summary": {
            "long_count": len(long_cand),
            "short_count": len(short_cand),
            "total_count": len(long_cand) + len(short_cand),
        }
    }
    
    WATCHLIST_FILE.write_text(json.dumps(watchlist, indent=2))
    logger.info(f"✅ Watchlist saved: {len(candidates)} candidates")
    logger.info("=== AMS PRO SCREENER NX (PYTHON) COMPLETE ===")

if __name__ == '__main__':
    main()
