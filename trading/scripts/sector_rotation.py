#!/usr/bin/env python3
"""
Systematic Sector Rotation — monthly ranking of sector ETFs by momentum.

Ranks 11 SPDR sector ETFs by 63-day return, selects top N, outputs
sector_allocation.json for use by screeners and executors.

Run monthly (or on demand):
    python sector_rotation.py
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import yfinance as yf
import numpy as np

logger = logging.getLogger(__name__)

from paths import TRADING_DIR as WORKSPACE
OUTPUT_FILE = WORKSPACE / "sector_allocation.json"
LOG_FILE = WORKSPACE / "logs" / "sector_rotation.log"

SECTOR_ETFS = [
    "XLK",   # Technology
    "XLF",   # Financials
    "XLE",   # Energy
    "XLV",   # Healthcare
    "XLI",   # Industrials
    "XLY",   # Consumer Discretionary
    "XLP",   # Consumer Staples
    "XLU",   # Utilities
    "XLC",   # Communication Services
    "XLRE",  # Real Estate
    "XLB",   # Materials
]

TOP_N = 3
LOOKBACK_DAYS = 63


def rank_sectors(top_n: int = TOP_N, lookback: int = LOOKBACK_DAYS) -> List[Dict[str, object]]:
    """Download sector ETF data, rank by lookback-day return, return top N."""
    try:
        data = yf.download(SECTOR_ETFS, period="6mo", interval="1d", progress=False, group_by="ticker")
    except Exception as e:
        logger.error("Failed to download sector ETF data: %s", e)
        return []
    
    results: List[Tuple[str, float, float]] = []
    
    for etf in SECTOR_ETFS:
        try:
            if etf in data.columns.get_level_values(0):
                close = data[etf]["Close"].dropna()
            else:
                continue
            if len(close) < lookback:
                continue
            current = float(close.iloc[-1])
            past = float(close.iloc[-lookback])
            if past <= 0:
                continue
            ret = (current - past) / past
            results.append((etf, ret, current))
        except (KeyError, TypeError, ValueError, IndexError):
            continue
    
    results.sort(key=lambda x: x[1], reverse=True)
    
    ranked = []
    for rank_idx, (etf, ret, price) in enumerate(results, 1):
        ranked.append({
            "symbol": etf,
            "rank": rank_idx,
            "return_63d": round(ret, 4),
            "price": round(price, 2),
            "selected": rank_idx <= top_n,
        })
    
    return ranked


def save_allocation(ranked: List[Dict[str, object]]) -> None:
    """Save sector allocation to JSON."""
    selected = [r["symbol"] for r in ranked if r.get("selected")]
    output = {
        "timestamp": datetime.now().isoformat(),
        "top_sectors": selected,
        "rankings": ranked,
        "config": {"top_n": TOP_N, "lookback_days": LOOKBACK_DAYS},
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2), encoding="utf-8")
    logger.info("Saved sector allocation: top=%s to %s", selected, OUTPUT_FILE)


def load_top_sectors() -> List[str]:
    """Load previously saved top sector ETFs. Returns empty list if unavailable."""
    if not OUTPUT_FILE.exists():
        return []
    try:
        data = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
        return list(data.get("top_sectors", []))
    except (OSError, ValueError):
        return []


def main() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
    )
    logger.info("=== SECTOR ROTATION ===")
    ranked = rank_sectors()
    if not ranked:
        logger.warning("No sector data available")
        return
    
    for r in ranked:
        marker = "*" if r.get("selected") else " "
        logger.info(
            " %s %2d. %-5s  63d ret: %+6.2f%%  price: $%.2f",
            marker, r["rank"], r["symbol"],
            r["return_63d"] * 100, r["price"],
        )
    
    save_allocation(ranked)
    logger.info("Done")


if __name__ == "__main__":
    main()
