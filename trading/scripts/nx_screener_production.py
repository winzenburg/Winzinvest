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
from typing import Any, Dict, List, Optional, Tuple

from position_filter import load_current_short_symbols
from risk_config import get_max_short_positions
from nx_metrics_helpers import (
    calculate_composite_score,
    calculate_htf_bias,
    calculate_rs_252d,
    calculate_rvol_atr,
    calculate_structure_quality,
)
from universe_builder import build_universe
from mtf_confirmation import compute_mtf_score
from earnings_catalyst import compute_earnings_boost
from sector_rotation import load_sector_momentum_multiplier
from sector_gates import SECTOR_MAP

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).resolve().parent.parent / "logs" / "nx_screener_multimode.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Paths
from paths import TRADING_DIR as WORKSPACE
WATCHLIST_DIR = WORKSPACE / "watchlists"
OUTPUT_FILE = WORKSPACE / "watchlist_multimode.json"

# Liquidity gates — match TradingView screener
MIN_PRICE = 5.0
MIN_AVG_DOLLAR_VOLUME_20D = 25_000_000  # $25M
MIN_AVG_VOLUME_20D = 500_000  # 500k shares/day

# NX Thresholds — rs_pct is raw 20-day return diff vs SPY (range ~-0.20 to +0.30)
NX_THRESHOLDS = {
    "tier_2_min": 0.08,
    "tier_3_min": 0.25,
    "rs_long_min": 0.02,
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
            'XOM', 'CVX', 'COP', 'EOG', 'MPC', 'PSX', 'VLO', 'HES',
            'OKE', 'MRO', 'BA', 'WMB', 'KMI', 'ENB', 'TRP',
            'FCX', 'RIO', 'BHP', 'VALE', 'NEM', 'HL', 'TECK', 'ICL',
            'APD', 'DD', 'LYB', 'OLN', 'CF', 'MOS', 'NUE', 'MT',
            'CF', 'MOS', 'ADM', 'BUNGE', 'GEVO', 'PLUG',
            'XLE',
        ],
        "filters": {
            "rs_long_min": 0.02,
            "rvol_min": 0.85,
            "price_above_50ma": True,
            "outperforming_spy": True,
        },
    },
    "premium_selling": {
        "name": "Premium Selling Scanner",
        "description": "Find high-IV tech for covered calls / CSPs",
        "universe": [
            'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'TSLA', 'ASML', 'NFLX',
            'ADBE', 'INTC', 'QCOM', 'AVGO', 'AMAT', 'LRCX', 'AMD', 'MRVL',
            'NXPI', 'SNPS', 'CDNS', 'INTU', 'CSCO', 'BKNG', 'CRWD', 'DDOG',
            'NET', 'OKTA', 'ZS', 'SNOW', 'SHOP', 'COIN', 'UPST', 'AFRM',
            'QQQ',
        ],
        "filters": {
            "iv_rank_min": 0.70,
            "recent_weakness": True,
            "recent_weakness_pct": -0.03,
            "identify_support": True,
        },
    },
    "short_opportunities": {
        "name": "Short Opportunities",
        "description": "Find QQQ weakness, failed bounces, downtrends",
        "universe": [
            'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'TSLA', 'AMZN', 'ASML',
            'NFLX', 'ADBE', 'INTC', 'QCOM', 'AVGO', 'AMD', 'AMAT', 'LRCX',
            'NXPI', 'SNPS', 'CDNS', 'MCHP', 'TXN', 'QCOM', 'KLA', 'KLAC',
            'CRWD', 'DDOG', 'NET', 'OKTA', 'SNOW', 'SHOP', 'UPST', 'COIN',
            'QQQ',
        ],
        "filters": {
            "price_below_100ma": True,
            "failed_bounce": True,
            "volume_confirms": True,
            "rs_short_max": 0.50,
            "composite_max": 0.35,
            "rs_252_max": 0.50,
            "rvol_atr_min": 1.0,
            "structure_max": 0.35,
            "htf_bias_max": 0.50,
        },
    },
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
    """Fetch SPY Close for relative strength calculations."""
    try:
        raw = yf.download("SPY", period=period, progress=False)
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        spy_data = raw["Close"]
        if isinstance(spy_data, pd.DataFrame):
            spy_data = spy_data.iloc[:, 0]
        return spy_data
    except Exception as e:
        logger.error(f"Failed to fetch SPY: {e}")
        return pd.Series()


def fetch_spy_ohlcv(period: str = "1y") -> Optional[pd.DataFrame]:
    """Fetch SPY OHLCV for ATR-based RVol (and other metrics needing High/Low)."""
    try:
        df = yf.download("SPY", period=period, progress=False)
        if df is None or df.empty or len(df) < 14:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        logger.warning(f"Failed to fetch SPY OHLCV: {e}")
        return None


def fetch_symbol_data(symbols: List[str], period: str = "1y") -> Dict:
    """Fetch OHLCV data for symbols using batch downloads for speed.

    yfinance supports multi-ticker download which is significantly faster
    than one-at-a-time for large universes. Falls back to sequential on failure.
    """
    logger.info(f"Fetching data for {len(symbols)} symbols...")
    data_map: Dict[str, pd.DataFrame] = {}

    BATCH_SIZE = 50
    for batch_start in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[batch_start : batch_start + BATCH_SIZE]
        logger.info(f"  Batch {batch_start // BATCH_SIZE + 1}: symbols {batch_start + 1}-{min(batch_start + BATCH_SIZE, len(symbols))}")
        try:
            multi = yf.download(batch, period=period, progress=False, group_by="ticker", threads=True)
            if multi is not None and not multi.empty:
                if len(batch) == 1:
                    sym = batch[0]
                    if isinstance(multi.columns, pd.MultiIndex):
                        multi.columns = multi.columns.get_level_values(0)
                    if not multi.empty and len(multi) >= 20:
                        data_map[sym] = multi
                else:
                    for sym in batch:
                        try:
                            df = multi[sym].dropna(how="all")
                            if isinstance(df.columns, pd.MultiIndex):
                                df.columns = df.columns.get_level_values(0)
                            if not df.empty and len(df) >= 20:
                                data_map[sym] = df
                        except (KeyError, TypeError):
                            pass
        except Exception:
            for sym in batch:
                try:
                    hist = yf.download(sym, period=period, progress=False)
                    if hist is not None and not hist.empty and len(hist) >= 20:
                        if isinstance(hist.columns, pd.MultiIndex):
                            hist.columns = hist.columns.get_level_values(0)
                        data_map[sym] = hist
                except Exception:
                    pass

    logger.info(f"✓ Successfully fetched data for {len(data_map)}/{len(symbols)} symbols")
    return data_map


def apply_liquidity_filter(
    data_map: Dict[str, pd.DataFrame],
    min_price: float = MIN_PRICE,
    min_avg_dollar_vol: float = MIN_AVG_DOLLAR_VOLUME_20D,
    min_avg_vol: float = MIN_AVG_VOLUME_20D,
) -> Dict[str, pd.DataFrame]:
    """Remove penny stocks and illiquid names from data_map.

    Criteria (all must pass):
    - Last close >= min_price ($5 default)
    - 20-day average daily dollar volume >= min_avg_dollar_vol ($25M default)
    - 20-day average daily share volume >= min_avg_vol (500k default)
    """
    filtered: Dict[str, pd.DataFrame] = {}
    rejected_price = 0
    rejected_dollar_vol = 0
    rejected_vol = 0

    for sym, df in data_map.items():
        try:
            close = df["Close"]
            volume = df["Volume"]

            last_price = float(close.iloc[-1])
            if last_price < min_price:
                rejected_price += 1
                continue

            avg_vol_20 = float(volume.iloc[-20:].mean()) if len(volume) >= 20 else float(volume.mean())
            if avg_vol_20 < min_avg_vol:
                rejected_vol += 1
                continue

            avg_close_20 = float(close.iloc[-20:].mean()) if len(close) >= 20 else float(close.mean())
            avg_dollar_vol = avg_vol_20 * avg_close_20
            if avg_dollar_vol < min_avg_dollar_vol:
                rejected_dollar_vol += 1
                continue

            filtered[sym] = df
        except Exception:
            pass

    logger.info(
        "Liquidity filter: %d → %d (rejected: %d price < $%.0f, %d vol < %dk, %d $vol < $%dM)",
        len(data_map),
        len(filtered),
        rejected_price,
        min_price,
        rejected_vol,
        min_avg_vol // 1000,
        rejected_dollar_vol,
        min_avg_dollar_vol // 1_000_000,
    )
    return filtered


def _ams_volume_score(volume: np.ndarray) -> float:
    """Compute AMS RVol + volume trend score (0 to 1) from raw volume array."""
    if len(volume) < 50:
        return 0.0
    avg_50 = np.mean(volume[-50:])
    if avg_50 <= 0:
        return 0.0
    rvol = min(volume[-1] / avg_50, 3.0)
    avg_20 = np.mean(volume[-20:]) if len(volume) >= 40 else avg_50
    avg_40 = np.mean(volume[-40:]) if len(volume) >= 40 else avg_50
    vol_trend = 1.0 if avg_20 > avg_40 else 0.0
    return (rvol / 3.0) * 0.7 + vol_trend * 0.3


def _ams_htf_bias(close: np.ndarray) -> float:
    """Weekly (65d) + monthly (126d) ROC with sigmoid transform (0 to 1)."""
    if len(close) < 126:
        return 0.5
    weekly_roc = ((close[-1] - close[-65]) / close[-65]) * 100 if close[-65] > 0 else 0
    monthly_roc = ((close[-1] - close[-126]) / close[-126]) * 100 if close[-126] > 0 else 0

    def _sig(x: float) -> float:
        e2x = np.exp(2 * x)
        return (e2x - 1) / (e2x + 1)

    htf = 0.3 * _sig(weekly_roc / 10) + 0.2 * _sig(monthly_roc / 10)
    return (htf + 1) / 2


def _ams_rsi(close: np.ndarray, period: int = 14) -> float:
    """Simple RSI calculation from close array."""
    if len(close) < period + 1:
        return 50.0
    diffs = np.diff(close[-(period + 1):])
    gains = np.mean(diffs[diffs > 0]) if np.any(diffs > 0) else 0.0
    losses = np.mean(-diffs[diffs < 0]) if np.any(diffs < 0) else 0.0001
    rs = gains / losses if losses > 0 else 100.0
    return 100 - (100 / (1 + rs))


HYBRID_AMS_WEIGHT = 0.30


def calculate_nx_metrics(
    symbol: str,
    ohlcv: pd.DataFrame,
    spy_data: pd.Series,
    spy_ohlcv: Optional[pd.DataFrame] = None,
) -> Dict:
    """Calculate NX metrics + AMS volume/HTF signals for a symbol."""
    try:
        close = ohlcv['Close'].values
        recent_return = (close[-1] - close[-20]) / close[-20] if len(close) >= 20 else 0
        if len(close) >= 20 and len(spy_data) >= 20:
            sym_20d = (close[-1] - close[-20]) / close[-20]
            spy_20d = (spy_data.iloc[-1] - spy_data.iloc[-20]) / spy_data.iloc[-20]
            rs_pct = sym_20d - spy_20d
        else:
            rs_pct = 0
        if len(close) >= 20:
            sym_vol = np.std(np.diff(np.log(close[-20:])))
            spy_vol = np.std(np.diff(np.log(spy_data.values[-20:] if len(spy_data) >= 20 else spy_data.values)))
            rvol = sym_vol / spy_vol if spy_vol > 0 else 0
        else:
            rvol = 0
        if len(close) >= 10:
            recent_high = np.max(close[-10:])
            recent_low = np.min(close[-10:])
            hl_ratio = (close[-1] - recent_low) / (recent_high - recent_low) if recent_high > recent_low else 0
        else:
            hl_ratio = 0
        ma50 = np.mean(close[-50:]) if len(close) >= 50 else close[-1]
        ma100 = np.mean(close[-100:]) if len(close) >= 100 else close[-1]
        price_vs_50ma = close[-1] / ma50 if ma50 > 0 else 1
        price_vs_100ma = close[-1] / ma100 if ma100 > 0 else 1

        volume = ohlcv['Volume'].values if 'Volume' in ohlcv.columns else np.zeros(len(close))
        vol_score = _ams_volume_score(volume)
        htf_bias_ams = _ams_htf_bias(close)
        rsi_val = _ams_rsi(close)

        out: Dict[str, Any] = {
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
            "ams_vol_score": round(float(vol_score), 3),
            "ams_htf_bias": round(float(htf_bias_ams), 3),
            "ams_rsi": round(float(rsi_val), 1),
        }
        comp = calculate_composite_score(ohlcv)
        if comp is not None:
            out["composite"] = round(comp, 3)
        rs252 = calculate_rs_252d(ohlcv, spy_data)
        if rs252 is not None:
            out["rs_252d"] = round(rs252, 3)
        if spy_ohlcv is not None:
            rvol_a = calculate_rvol_atr(ohlcv, spy_ohlcv)
            if rvol_a is not None:
                out["rvol_atr"] = round(rvol_a, 3)
        struct = calculate_structure_quality(ohlcv)
        if struct is not None:
            out["structure"] = round(struct, 3)

        mtf = compute_mtf_score(ohlcv, side="LONG")
        if mtf is not None:
            out["mtf_score"] = mtf

        earnings = compute_earnings_boost(symbol, ohlcv, side="LONG")
        if earnings.get("is_catalyst"):
            out["earnings_boost"] = earnings["earnings_boost"]
            out["earnings_date"] = earnings["earnings_date"]

        sector = SECTOR_MAP.get(symbol)
        if sector:
            out["sector_multiplier"] = load_sector_momentum_multiplier(sector)
            out["sector"] = sector

        return out
    except Exception:
        return None


def run_mode_sector_strength(data_map: Dict, spy_data: pd.Series, mode_cfg: Dict) -> Tuple[List, List]:
    """Mode 1: Find energy/materials breaking out.

    Scans all symbols in data_map (full universe, post-liquidity filter).
    The mode_cfg 'sectors' key limits to relevant GICS sectors when available.
    """
    logger.info(f"\n=== {mode_cfg['name']} ===")
    universe = list(data_map.keys())
    long_candidates = []
    short_candidates = []
    filters = mode_cfg['filters']
    for symbol in universe:
        if symbol not in data_map:
            continue
        metrics = calculate_nx_metrics(symbol, data_map[symbol], spy_data)
        if not metrics:
            continue
        if metrics['rs_pct'] < filters['rs_long_min']:
            continue
        if metrics['rvol'] < filters['rvol_min']:
            continue
        if metrics['price_vs_50ma'] < 1.0:
            continue
        if metrics['rs_pct'] <= 0:
            continue
        nx_score = metrics.get("composite", 0.5) * 0.4 + metrics["rs_pct"] * 0.3 + metrics.get("structure", 0.5) * 0.3
        ams_boost = metrics.get("ams_vol_score", 0) * 0.5 + metrics.get("ams_htf_bias", 0.5) * 0.5
        w = HYBRID_AMS_WEIGHT
        base_score = nx_score * (1 - w) + ams_boost * w

        mtf = metrics.get("mtf_score", 0.5)
        mtf_mult = 0.8 + 0.4 * mtf

        earnings_add = metrics.get("earnings_boost", 0.0)

        sector_mult = metrics.get("sector_multiplier", 1.0)

        metrics["hybrid_score"] = round(base_score * mtf_mult * sector_mult + earnings_add, 4)
        long_candidates.append({
            **metrics,
            "reason": (
                f"Sector breakout: RS={metrics['rs_pct']}, "
                f"vol={metrics.get('ams_vol_score', 0):.2f}, "
                f"mtf={mtf:.2f}, "
                f"score={metrics['hybrid_score']:.3f}"
            ),
        })
    long_candidates.sort(key=lambda x: x.get("hybrid_score", 0), reverse=True)
    logger.info(f"Long candidates: {len(long_candidates)}")
    logger.info(f"Short candidates: {len(short_candidates)}")
    return long_candidates, short_candidates


def run_mode_premium_selling(data_map: Dict, spy_data: pd.Series, mode_cfg: Dict) -> Tuple[List, List]:
    """Mode 2: Find high-IV tech for premium selling.

    Scans all symbols in data_map (full universe, post-liquidity filter).
    """
    logger.info(f"\n=== {mode_cfg['name']} ===")
    universe = list(data_map.keys())
    long_candidates = []
    short_candidates = []
    filters = mode_cfg['filters']
    for symbol in universe:
        if symbol not in data_map:
            continue
        metrics = calculate_nx_metrics(symbol, data_map[symbol], spy_data)
        if not metrics:
            continue
        weakness_threshold = filters.get("recent_weakness_pct", -0.05)
        if metrics['recent_return'] < weakness_threshold:
            short_candidates.append({
                **metrics,
                "reason": f"High-IV weakness: Recent {metrics['recent_return']*100:.1f}%, elevated IV"
            })
    exclude = load_current_short_symbols(WORKSPACE)
    before = len(short_candidates)
    short_candidates = [c for c in short_candidates if c["symbol"] not in exclude]
    if before > len(short_candidates):
        logger.info(f"Excluded {before - len(short_candidates)} symbols already in current shorts (premium_selling).")
    current_short_count = len(exclude)
    max_short = get_max_short_positions(WORKSPACE)
    slots_left = max(0, max_short - current_short_count)
    if len(short_candidates) > slots_left:
        short_candidates = short_candidates[:slots_left]
        logger.info(f"Trimmed short list to slots left: {slots_left} (max_short_positions={max_short}, current={current_short_count}).")
    logger.info(f"Long candidates (CSP): {len(long_candidates)}")
    logger.info(f"Short candidates (Call): {len(short_candidates)}")
    return long_candidates, short_candidates


def run_mode_short_opportunities(
    data_map: Dict,
    spy_data: pd.Series,
    mode_cfg: Dict,
    spy_ohlcv: Optional[pd.DataFrame] = None,
) -> Tuple[List, List]:
    """Mode 3: Find QQQ weakness, failed bounces, downtrends.

    Scans all symbols in data_map (full universe, post-liquidity filter).
    spy_ohlcv optional for rvol_atr.
    """
    logger.info(f"\n=== {mode_cfg['name']} ===")
    universe = list(data_map.keys())
    long_candidates = []
    short_candidates = []
    filters = mode_cfg['filters']
    for symbol in universe:
        if symbol not in data_map:
            continue
        metrics = calculate_nx_metrics(symbol, data_map[symbol], spy_data, spy_ohlcv)
        if not metrics:
            continue
        if metrics['price_vs_100ma'] >= 1.0:
            continue
        if metrics['price_vs_50ma'] >= 1.0:
            continue
        if metrics['rs_pct'] > filters['rs_short_max']:
            continue
        if 'composite' in metrics and metrics['composite'] > filters.get('composite_max', 0.35):
            continue
        if 'rs_252d' in metrics and metrics['rs_252d'] > filters.get('rs_252_max', 0.50):
            continue
        if 'rvol_atr' in metrics and metrics['rvol_atr'] < filters.get('rvol_atr_min', 1.0):
            continue
        if 'structure' in metrics and metrics['structure'] > filters.get('structure_max', 0.35):
            continue
        mtf_short = compute_mtf_score(data_map[symbol], side="SHORT")
        if mtf_short is not None:
            metrics["mtf_score"] = mtf_short

        short_candidates.append({
            **metrics,
            "reason": (
                f"Downtrend confirmed: Below 50MA/100MA, RS {metrics['rs_pct']}, "
                f"mtf={metrics.get('mtf_score', 0.5):.2f}"
            ),
        })
    htf_max = filters.get("htf_bias_max", 0.50)
    if htf_max is not None:
        passed = []
        for c in short_candidates:
            htf = calculate_htf_bias(c["symbol"])
            if htf is not None:
                c["htf_bias"] = round(htf, 3)
                if htf > htf_max:
                    continue
            passed.append(c)
        short_candidates = passed
    exclude = load_current_short_symbols(WORKSPACE)
    before = len(short_candidates)
    short_candidates = [c for c in short_candidates if c["symbol"] not in exclude]
    if before > len(short_candidates):
        logger.info(f"Excluded {before - len(short_candidates)} symbols already in current shorts (short_opportunities).")
    current_short_count = len(exclude)
    max_short = get_max_short_positions(WORKSPACE)
    slots_left = max(0, max_short - current_short_count)
    if len(short_candidates) > slots_left:
        short_candidates = short_candidates[:slots_left]
        logger.info(f"Trimmed short list to slots left: {slots_left} (max_short_positions={max_short}, current={current_short_count}).")
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


def screen_for_shorts(
    ticker: str,
    spy_data: pd.Series,
    thresholds: Dict[str, Any],
    spy_ohlcv: Optional[pd.DataFrame] = None,
    include_htf: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Single-ticker short screen: fetch 1y daily, compute full NX metrics, apply thresholds.
    Returns candidate dict (symbol, composite, rs_252d, rvol_atr, structure, htf_bias, price, reason)
    if all gates pass; otherwise None. Useful for testing and for webhook-triggered single-symbol checks.
    """
    try:
        ohlcv = yf.download(ticker, period="1y", progress=False, auto_adjust=True)
        if ohlcv is None or ohlcv.empty or len(ohlcv) < 20:
            return None
        if isinstance(ohlcv.columns, pd.MultiIndex):
            ohlcv.columns = ohlcv.columns.get_level_values(0)
        metrics = calculate_nx_metrics(ticker, ohlcv, spy_data, spy_ohlcv)
        if not metrics:
            return None
        th = thresholds
        if metrics.get("price_vs_100ma", 1.0) >= 1.0:
            return None
        if metrics.get("price_vs_50ma", 1.0) >= 1.0:
            return None
        if metrics.get("rs_pct", 1.0) > th.get("rs_short_max", 0.50):
            return None
        if "composite" in metrics and metrics["composite"] > th.get("composite_max", 0.35):
            return None
        if "rs_252d" in metrics and metrics["rs_252d"] > th.get("rs_252_max", 0.50):
            return None
        if "rvol_atr" in metrics and metrics["rvol_atr"] < th.get("rvol_atr_min", 1.0):
            return None
        if "structure" in metrics and metrics["structure"] > th.get("structure_max", 0.35):
            return None
        if include_htf and th.get("htf_bias_max") is not None:
            htf = calculate_htf_bias(ticker)
            if htf is not None:
                metrics["htf_bias"] = round(htf, 3)
                if htf > th.get("htf_bias_max", 0.50):
                    return None
        metrics["reason"] = (
            f"Short setup: composite={metrics.get('composite')}, rs_252d={metrics.get('rs_252d')}, "
            f"structure={metrics.get('structure')}, price_vs_100ma={metrics.get('price_vs_100ma')}"
        )
        return metrics
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="NX Multi-Mode Screener")
    parser.add_argument("--mode", choices=["all", "sector_strength", "premium_selling", "short_opportunities"],
                        default="all", help="Screener mode to run")
    parser.add_argument("--universe", choices=["full", "legacy"], default="full",
                        help="Universe size: 'full' (~1500 symbols) or 'legacy' (original ~75)")
    parser.add_argument("--min-price", type=float, default=MIN_PRICE,
                        help=f"Min stock price filter (default ${MIN_PRICE})")
    parser.add_argument("--min-dollar-vol", type=float, default=MIN_AVG_DOLLAR_VOLUME_20D,
                        help=f"Min 20d avg dollar volume (default ${MIN_AVG_DOLLAR_VOLUME_20D:,.0f})")
    args = parser.parse_args()
    logger.info(f"=== NX MULTI-MODE SCREENER ===")
    logger.info(f"Mode: {args.mode} | Universe: {args.universe}")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")

    if args.universe == "full":
        csv_path = WATCHLIST_DIR / "full_market_2600.csv"
        all_symbols = build_universe(
            csv_path=csv_path if csv_path.exists() else None,
            include_etfs=True,
        )
    else:
        all_symbols_set: set[str] = set()
        for mode_cfg in MODE_CONFIG.values():
            all_symbols_set.update(mode_cfg["universe"])
        all_symbols = sorted(all_symbols_set)

    spy_data = fetch_spy_data()
    logger.info(f"Fetching data for {len(all_symbols)} symbols...")
    data_map = fetch_symbol_data(all_symbols)

    data_map = apply_liquidity_filter(
        data_map,
        min_price=args.min_price,
        min_avg_dollar_vol=args.min_dollar_vol,
    )
    results = {
        "generated_at": datetime.now().isoformat(),
        "universe_stats": {
            "universe_mode": args.universe,
            "symbols_requested": len(all_symbols),
            "symbols_fetched": len(data_map),
            "min_price": args.min_price,
            "min_avg_dollar_vol": args.min_dollar_vol,
        },
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
        spy_ohlcv = fetch_spy_ohlcv()
        long, short = run_mode_short_opportunities(
            data_map, spy_data, MODE_CONFIG["short_opportunities"], spy_ohlcv
        )
        results["modes"]["short_opportunities"] = {
            "long": long[:25],
            "short": short[:25],
            "total": {"long": len(long), "short": len(short)}
        }
    save_results(results, OUTPUT_FILE)
    logger.info(f"\n=== SCREENING COMPLETE ===")


if __name__ == "__main__":
    main()
