#!/usr/bin/env python3
"""
Pairs / Relative Value Screener

Weekly sector ranking, pair selection, and spread z-score tracking.
For each sector with 3+ stocks: rank by NX composite, select top (long) vs bottom (short),
compute spread z-score over 20 days. Output: watchlist_pairs.json.
"""

import json
import logging
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

# Seconds to wait between symbol downloads when rate-limited
_RATE_LIMIT_DELAY = 2.5
_RATE_LIMIT_RETRIES = 3
# Hard wall-clock timeout per chunk/symbol so a stalled connection never hangs forever.
# yfinance uses curl_cffi internally (not requests) so we enforce timeouts via
# concurrent.futures rather than session parameters.
_CHUNK_TIMEOUT_SEC = 90    # per 100-symbol chunk
_SYMBOL_TIMEOUT_SEC = 15   # per single-symbol fallback download

from nx_screener_production import calculate_nx_metrics
from sector_gates import SECTOR_MAP

from paths import TRADING_DIR as WORKSPACE
WATCHLIST_PAIRS_FILE = WORKSPACE / "watchlist_pairs.json"
LOG_FILE = WORKSPACE / "logs" / "pairs_screener.log"
# Snapshot used to derive the live portfolio universe (current stock positions only).
DASHBOARD_SNAPSHOT = WORKSPACE / "logs" / "dashboard_snapshot.json"
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


def _load_portfolio_symbols() -> Dict[str, str]:
    """
    Load current stock positions from the dashboard snapshot.
    Returns {symbol: sector} for all long/short equity positions.
    Falls back to SECTOR_MAP if the snapshot is unavailable.
    """
    try:
        if DASHBOARD_SNAPSHOT.exists():
            snap = json.loads(DASHBOARD_SNAPSHOT.read_text())
            positions = snap.get("positions", {}).get("list", [])
            portfolio: Dict[str, str] = {}
            for pos in positions:
                if pos.get("sec_type") != "STK":
                    continue
                sym = str(pos.get("symbol", "")).strip().upper()
                sector = str(pos.get("sector", "")) or SECTOR_MAP.get(sym, "")
                if sym and sector and sector not in ("ETF", "Options", ""):
                    portfolio[sym] = sector
            if portfolio:
                logger.info("Portfolio universe: %d positions from dashboard snapshot", len(portfolio))
                return portfolio
    except Exception as e:
        logger.warning("Could not load portfolio from snapshot: %s — falling back to SECTOR_MAP", e)
    logger.warning("Dashboard snapshot unavailable — using full SECTOR_MAP as fallback")
    return {sym: sec for sym, sec in SECTOR_MAP.items() if sec != "ETF"}


def _build_sector_stocks() -> Dict[str, List[str]]:
    """
    Group portfolio positions by sector for pairs ranking.
    Uses the live dashboard snapshot (current stock positions) as the universe
    so the screener only evaluates pairs we can actually trade from existing holdings.
    Returns sectors with 3+ positions.
    """
    portfolio = _load_portfolio_symbols()
    sector_to_symbols: Dict[str, List[str]] = defaultdict(list)
    for symbol, sector in portfolio.items():
        sector_to_symbols[sector].append(symbol)
    result = {
        sector: sorted(symbols)
        for sector, symbols in sector_to_symbols.items()
        if len(symbols) >= MIN_STOCKS_PER_SECTOR
    }
    total = sum(len(v) for v in result.values())
    logger.info("Pairs universe: %d positions across %d sectors", total, len(result))
    return result


def _yf_download_with_retry(sym: str, period: str = "3mo") -> Optional[pd.DataFrame]:
    """
    Download OHLCV for a single symbol with exponential backoff on rate limit errors.
    Enforces a hard wall-clock timeout via concurrent.futures so a stalled network
    request never blocks the process indefinitely.
    Returns a cleaned DataFrame or None.
    """
    delay = _RATE_LIMIT_DELAY
    for attempt in range(_RATE_LIMIT_RETRIES):
        try:
            with ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(yf.download, sym, period=period, progress=False, auto_adjust=True)
                try:
                    hist = future.result(timeout=_SYMBOL_TIMEOUT_SEC)
                except FuturesTimeout:
                    logger.debug("Timeout downloading %s — skipping", sym)
                    return None
            if hist is None or hist.empty or len(hist) < 20:
                return None
            if isinstance(hist.columns, pd.MultiIndex):
                hist.columns = hist.columns.get_level_values(0)
            if "Close" not in hist.columns:
                return None
            return hist
        except Exception as e:
            err = str(e).lower()
            if "rate" in err or "too many" in err or "429" in err:
                if attempt < _RATE_LIMIT_RETRIES - 1:
                    logger.warning("Rate limited on %s — waiting %.1fs (attempt %d/%d)",
                                   sym, delay, attempt + 1, _RATE_LIMIT_RETRIES)
                    time.sleep(delay)
                    delay *= 2  # exponential backoff
                else:
                    logger.warning("Rate limited on %s — max retries reached, skipping", sym)
            else:
                logger.debug("Skip %s: %s", sym, e)
                return None
    return None


def _fetch_spy_data(period: str = "1y") -> pd.Series:
    """Fetch SPY Close for relative strength calculations."""
    df = _yf_download_with_retry("SPY", period=period)
    if df is None:
        logger.error("Failed to fetch SPY data — pairs screener cannot run")
        return pd.Series(dtype=float)
    return df["Close"]


def _download_sector_data(symbols: List[str], period: str = "3mo") -> Dict[str, pd.DataFrame]:
    """
    Download daily OHLCV for symbols via yfinance chunked batch API.

    Downloads in chunks of 100 with ``threads=False`` to avoid the ThreadPoolExecutor
    hang that occurs when ``threads=True`` and a single request stalls indefinitely.
    Falls back to one-by-one sequential download if a chunk fails.
    Returns {symbol: ohlcv_df}.
    """
    data_map: Dict[str, pd.DataFrame] = {}
    chunk_size = 100

    for chunk_start in range(0, len(symbols), chunk_size):
        chunk = symbols[chunk_start: chunk_start + chunk_size]
        try:
            with ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(
                    yf.download, chunk,
                    period=period, progress=False, auto_adjust=True,
                    threads=False, group_by="ticker",
                )
                try:
                    batch = future.result(timeout=_CHUNK_TIMEOUT_SEC)
                except FuturesTimeout:
                    logger.warning(
                        "Chunk %d-%d timed out after %ds — falling back to per-symbol",
                        chunk_start, chunk_start + len(chunk), _CHUNK_TIMEOUT_SEC,
                    )
                    batch = None
            chunk_succeeded = False
            if batch is not None and not batch.empty:
                for sym in chunk:
                    try:
                        df = batch if len(chunk) == 1 else batch[sym].dropna(how="all")
                        if isinstance(df.columns, pd.MultiIndex):
                            df.columns = df.columns.get_level_values(0)
                        if df is not None and not df.empty and len(df) >= 20 and "Close" in df.columns:
                            data_map[sym] = df
                            chunk_succeeded = True
                    except (KeyError, TypeError):
                        pass
            if not chunk_succeeded:
                # Batch timed out or returned empty — fall back to per-symbol with timeout
                logger.info("Chunk %d-%d: batch failed, trying per-symbol fallback", chunk_start, chunk_start + len(chunk))
                for sym in chunk:
                    hist = _yf_download_with_retry(sym, period=period)
                    if hist is not None:
                        data_map[sym] = hist
            logger.info(
                "Chunk %d-%d done (total fetched: %d)",
                chunk_start, chunk_start + len(chunk), len(data_map),
            )
        except Exception as e:
            logger.warning("Chunk %d-%d failed, falling back to sequential: %s", chunk_start, chunk_start + len(chunk), e)
            for sym in chunk:
                hist = _yf_download_with_retry(sym, period=period)
                if hist is not None:
                    data_map[sym] = hist

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

    # Pre-fetch all symbols + SPY in a single batch call for speed
    all_symbols = sorted({sym for syms in sector_stocks.values() for sym in syms})
    if "SPY" not in all_symbols:
        all_symbols.insert(0, "SPY")
    logger.info("Downloading %d symbols in batch...", len(all_symbols))
    all_data = _download_sector_data(all_symbols)
    logger.info("Downloaded data for %d/%d symbols", len(all_data), len(all_symbols))

    spy_df = all_data.get("SPY")
    if spy_df is None or spy_df.empty:
        spy_series = _fetch_spy_data()
    else:
        spy_series = spy_df["Close"]

    if spy_series.empty or len(spy_series) < 20:
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
        data_map = {sym: all_data[sym] for sym in symbols if sym in all_data}
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
                metrics = calculate_nx_metrics(sym, ohlcv, spy_series)
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
