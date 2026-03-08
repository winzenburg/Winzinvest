#!/usr/bin/env python3
"""
Mean Reversion (RSI-2) Screener.

Screens universe for RSI(2) pullback entries on quality uptrend stocks.
Criteria: close > 200 SMA, RSI(2) < 10, close > $5.
Output: watchlist_mean_reversion.json for the MR executor.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from nx_screener_production import (
    MIN_AVG_DOLLAR_VOLUME_20D,
    MIN_AVG_VOLUME_20D,
    MIN_PRICE,
    apply_liquidity_filter,
    fetch_symbol_data,
)
from universe_builder import build_universe

from paths import TRADING_DIR as WORKSPACE
WATCHLIST_FILE = WORKSPACE / "watchlist_mean_reversion.json"
LOG_FILE = WORKSPACE / "logs" / "mr_screener.log"

# Ensure log directory exists before configuring handler
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# RSI(2) oversold threshold; rank by how oversold (lower RSI = higher score)
RSI2_OVERSOLD_THRESHOLD = 10
SMA200_PERIOD = 200

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def _compute_rsi(close: np.ndarray, period: int = 2) -> float:
    """Compute RSI from close array. Returns 50.0 if insufficient data."""
    if len(close) < period + 1:
        return 50.0
    diffs = np.diff(close[-(period + 1) :])
    gains = np.mean(diffs[diffs > 0]) if np.any(diffs > 0) else 0.0
    losses = np.mean(-diffs[diffs < 0]) if np.any(diffs < 0) else 0.0001
    rs = gains / losses if losses > 0 else 100.0
    return float(100 - (100 / (1 + rs)))


def _compute_sma200(close: np.ndarray) -> Optional[float]:
    """Compute 200-day SMA. Returns None if insufficient data."""
    if len(close) < SMA200_PERIOD:
        return None
    return float(np.mean(close[-SMA200_PERIOD:]))


def screen_mr_candidates(
    data_map: Dict[str, pd.DataFrame],
    min_price: float = MIN_PRICE,
    rsi_threshold: float = RSI2_OVERSOLD_THRESHOLD,
) -> List[Dict[str, object]]:
    """
    Screen data_map for RSI(2) pullback entries on uptrend stocks.

    Filter: close > 200 SMA AND RSI(2) < rsi_threshold AND close > min_price.
    Rank by oversold score (lower RSI = higher score).
    """
    candidates: List[Dict[str, object]] = []

    for symbol, df in data_map.items():
        try:
            close = df["Close"].values
            if len(close) < SMA200_PERIOD + 2:
                continue

            price = float(close[-1])
            if price < min_price:
                continue

            rsi2 = _compute_rsi(close, period=2)
            sma200 = _compute_sma200(close)
            if sma200 is None or sma200 <= 0:
                continue

            if price <= sma200:
                continue
            if rsi2 >= rsi_threshold:
                continue

            # Score: lower RSI = higher score (more oversold = better)
            score = max(0.0, rsi_threshold - rsi2)
            reason = (
                f"RSI(2)={rsi2:.1f} oversold, price ${price:.2f} above SMA200 ${sma200:.2f}"
            )
            candidates.append({
                "symbol": symbol.strip().upper(),
                "price": round(price, 2),
                "rsi2": round(rsi2, 2),
                "sma200": round(sma200, 2),
                "score": round(score, 2),
                "reason": reason,
            })
        except (KeyError, IndexError, TypeError, ValueError) as e:
            logger.debug("Skipping %s: %s", symbol, e)
            continue

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates


def main() -> None:
    """Build universe, fetch data, apply liquidity filter, screen for MR candidates."""
    logger.info("=== MEAN REVERSION (RSI-2) SCREENER ===")
    logger.info("Timestamp: %s", datetime.now().isoformat())

    all_symbols = build_universe(csv_path=None, include_etfs=True)
    if not all_symbols:
        logger.warning("Empty universe")
        _write_empty_watchlist()
        return

    data_map = fetch_symbol_data(all_symbols)
    data_map = apply_liquidity_filter(
        data_map,
        min_price=MIN_PRICE,
        min_avg_dollar_vol=MIN_AVG_DOLLAR_VOLUME_20D,
        min_avg_vol=MIN_AVG_VOLUME_20D,
    )

    candidates = screen_mr_candidates(data_map)
    logger.info("MR candidates: %d", len(candidates))

    result = {
        "generated_at": datetime.now().isoformat(),
        "candidates": candidates,
    }

    WORKSPACE.mkdir(parents=True, exist_ok=True)
    WATCHLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        WATCHLIST_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")
        logger.info("Saved watchlist to %s", WATCHLIST_FILE)
    except OSError as e:
        logger.error("Failed to write watchlist: %s", e)

    logger.info("=== SCREENING COMPLETE ===")


def _write_empty_watchlist() -> None:
    """Write empty watchlist when no candidates or universe."""
    result = {"generated_at": datetime.now().isoformat(), "candidates": []}
    try:
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        WATCHLIST_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")
    except OSError as e:
        logger.error("Failed to write empty watchlist: %s", e)


if __name__ == "__main__":
    main()
