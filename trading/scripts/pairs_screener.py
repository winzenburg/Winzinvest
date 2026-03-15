#!/usr/bin/env python3
"""
Pairs / Relative Value Screener

Weekly sector ranking, pair selection, and spread z-score tracking.
For each sector with 3+ stocks: rank by NX composite, select top (long) vs bottom (short),
compute spread z-score over 20 days. Output: watchlist_pairs.json.
"""

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

from nx_screener_production import calculate_nx_metrics
from sector_gates import SECTOR_MAP

from paths import TRADING_DIR as WORKSPACE
WATCHLIST_PAIRS_FILE = WORKSPACE / "watchlist_pairs.json"
LOG_FILE = WORKSPACE / "logs" / "pairs_screener.log"
SPREAD_LOOKBACK = 20
MIN_STOCKS_PER_SECTOR = 3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def _build_sector_stocks() -> Dict[str, List[str]]:
    """Group symbols by sector, excluding ETF sector. Return sectors with 3+ stocks."""
    sector_to_symbols: Dict[str, List[str]] = defaultdict(list)
    for symbol, sector in SECTOR_MAP.items():
        if sector == "ETF":
            continue
        sector_to_symbols[sector].append(symbol)
    return {
        sector: symbols
        for sector, symbols in sector_to_symbols.items()
        if len(symbols) >= MIN_STOCKS_PER_SECTOR
    }


def _fetch_spy_data(period: str = "1y") -> pd.Series:
    """Fetch SPY Close for relative strength calculations."""
    try:
        df = yf.download("SPY", period=period, progress=False)
        if df is None or df.empty or len(df) < 20:
            return pd.Series(dtype=float)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df["Close"]
    except Exception as e:
        logger.error("Failed to fetch SPY: %s", e)
        return pd.Series(dtype=float)


def _download_sector_data(symbols: List[str], period: str = "3mo") -> Dict[str, pd.DataFrame]:
    """Download daily OHLCV for symbols. Returns {symbol: ohlcv_df}."""
    data_map: Dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            hist = yf.download(sym, period=period, progress=False, auto_adjust=True)
            if hist is None or hist.empty or len(hist) < 20:
                continue
            if isinstance(hist.columns, pd.MultiIndex):
                hist.columns = hist.columns.get_level_values(0)
            if "Close" not in hist.columns:
                continue
            data_map[sym] = hist
        except Exception as e:
            logger.debug("Skip %s: %s", sym, e)
    return data_map


def _spread_zscore(
    long_prices: pd.Series,
    short_prices: pd.Series,
    lookback: int = SPREAD_LOOKBACK,
) -> Optional[float]:
    """
    Compute z-score of log(long/short) ratio over lookback days.
    Returns (current - mean) / std; None if insufficient data.
    """
    if long_prices is None or short_prices is None:
        return None
    common_idx = long_prices.index.intersection(short_prices.index)
    if len(common_idx) < lookback:
        return None
    long_aligned = long_prices.reindex(common_idx).ffill().bfill()
    short_aligned = short_prices.reindex(common_idx).ffill().bfill()
    valid = long_aligned.notna() & short_aligned.notna() & (short_aligned > 0)
    if valid.sum() < lookback:
        return None
    recent_idx = valid[valid].tail(lookback).index
    long_vals = long_aligned.loc[recent_idx].values
    short_vals = short_aligned.loc[recent_idx].values
    spread = np.log(long_vals / short_vals)
    mean_s = float(np.mean(spread))
    std_s = float(np.std(spread))
    if std_s <= 0:
        return 0.0
    return float((spread[-1] - mean_s) / std_s)


def _check_stale_output() -> None:
    """Warn if watchlist_pairs.json is missing or older than 25 hours."""
    if not WATCHLIST_PAIRS_FILE.exists():
        logger.warning("watchlist_pairs.json does not exist — no pairs have been generated yet")
        return
    import time
    age_hours = (time.time() - WATCHLIST_PAIRS_FILE.stat().st_mtime) / 3600
    if age_hours > 25:
        logger.warning("watchlist_pairs.json is %.1f hours old — stale pairs data", age_hours)


def run_pairs_screener() -> None:
    """
    Run weekly sector ranking, pair selection, and spread z-score calculation.
    Writes watchlist_pairs.json with pairs: [{long_sym, short_sym, sector, long_score, short_score, spread_zscore}].
    """
    logger.info("=== PAIRS SCREENER ===")
    sector_stocks = _build_sector_stocks()
    logger.info("Sectors with 3+ stocks: %d", len(sector_stocks))

    spy_data = _fetch_spy_data()
    if spy_data.empty or len(spy_data) < 20:
        logger.error("Insufficient SPY data — pairs screener aborted. Check yfinance network access.")
        _check_stale_output()
        return

    pairs: List[Dict[str, Any]] = []
    sectors_attempted = 0
    sectors_with_data = 0

    for sector, symbols in sector_stocks.items():
        if len(symbols) < MIN_STOCKS_PER_SECTOR:
            continue
        sectors_attempted += 1
        data_map = _download_sector_data(symbols)
        if len(data_map) < MIN_STOCKS_PER_SECTOR:
            logger.warning(
                "Sector %s: only %d/%d symbols downloaded — skipping",
                sector, len(data_map), len(symbols),
            )
            continue
        sectors_with_data += 1

        scored: List[Tuple[str, float, Dict[str, Any]]] = []
        for sym, ohlcv in data_map.items():
            try:
                metrics = calculate_nx_metrics(sym, ohlcv, spy_data)
            except Exception as e:
                logger.warning("nx_metrics failed for %s: %s", sym, e)
                continue
            if not metrics:
                continue
            comp = metrics.get("composite")
            if comp is None:
                continue
            scored.append((sym, comp, metrics))

        if len(scored) < MIN_STOCKS_PER_SECTOR:
            logger.info("Sector %s: only %d scored symbols — skipping pair", sector, len(scored))
            continue

        scored.sort(key=lambda x: x[1], reverse=True)
        long_sym, long_score, long_metrics = scored[0]
        short_sym, short_score, short_metrics = scored[-1]

        if long_sym == short_sym:
            continue

        long_prices = data_map[long_sym]["Close"]
        short_prices = data_map[short_sym]["Close"]
        spread_z = _spread_zscore(long_prices, short_prices)

        pairs.append({
            "long_sym": long_sym,
            "short_sym": short_sym,
            "sector": sector,
            "long_score": round(long_score, 4),
            "short_score": round(short_score, 4),
            "spread_zscore": round(spread_z, 4) if spread_z is not None else None,
            "long_price": long_metrics.get("price"),
            "short_price": short_metrics.get("price"),
        })
        logger.info(
            "Pair %s: %s (%.3f) vs %s (%.3f) | spread_z=%.2f",
            sector, long_sym, long_score, short_sym, short_score,
            spread_z if spread_z is not None else float("nan"),
        )

    logger.info(
        "Pairs screener complete: %d sectors attempted, %d with data, %d pairs found",
        sectors_attempted, sectors_with_data, len(pairs),
    )

    if not pairs:
        logger.warning(
            "No pairs generated. sectors_attempted=%d, sectors_with_data=%d. "
            "Possible causes: yfinance data gaps, all sectors < %d scored symbols.",
            sectors_attempted, sectors_with_data, MIN_STOCKS_PER_SECTOR,
        )

    output = {
        "pairs": pairs,
        "updated_at": pd.Timestamp.now().isoformat(),
        "sectors_attempted": sectors_attempted,
        "sectors_with_data": sectors_with_data,
    }
    WATCHLIST_PAIRS_FILE.parent.mkdir(parents=True, exist_ok=True)
    WATCHLIST_PAIRS_FILE.write_text(json.dumps(output, indent=2), encoding="utf-8")
    logger.info("Wrote %d pairs to %s", len(pairs), WATCHLIST_PAIRS_FILE)


if __name__ == "__main__":
    run_pairs_screener()
