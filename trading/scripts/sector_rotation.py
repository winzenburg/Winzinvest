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
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

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


MAX_RETRIES = 3
RETRY_DELAY_S = 5


def _download_with_retry(tickers: List[str], retries: int = MAX_RETRIES) -> Optional[pd.DataFrame]:
    """Download yfinance data with retry and proxy cleanup."""
    # Clear proxy env vars that may redirect to a dead local tunnel
    saved_proxies: Dict[str, str] = {}
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        val = os.environ.pop(key, None)
        if val is not None:
            saved_proxies[key] = val

    try:
        for attempt in range(1, retries + 1):
            try:
                data = yf.download(tickers, period="6mo", interval="1d", progress=False, group_by="ticker")
                if data is not None and not data.empty:
                    return data
            except Exception as exc:
                logger.warning("yfinance download attempt %d/%d failed: %s", attempt, retries, exc)
            if attempt < retries:
                time.sleep(RETRY_DELAY_S * attempt)
    finally:
        os.environ.update(saved_proxies)

    return None


def _load_cached_rankings() -> List[Dict[str, object]]:
    """Return previously saved rankings from disk, or [] if unavailable."""
    if not OUTPUT_FILE.exists():
        return []
    try:
        cached = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
        rankings = list(cached.get("rankings", []))
        ts = cached.get("timestamp", "unknown")
        if rankings:
            logger.warning("Using cached sector rankings from %s (fresh download failed)", ts)
        return rankings
    except (OSError, ValueError):
        return []


def rank_sectors(top_n: int = TOP_N, lookback: int = LOOKBACK_DAYS) -> List[Dict[str, object]]:
    """Download sector ETF data, rank by lookback-day return, return top N.

    Falls back to cached sector_allocation.json if yfinance is unavailable.
    """
    data = _download_with_retry(SECTOR_ETFS)
    if data is None or data.empty:
        cached = _load_cached_rankings()
        if cached:
            # Cache hit — downgrade to warning so dashboard stays clean
            logger.warning(
                "Failed to download fresh sector ETF data after %d retries — using cached rankings",
                MAX_RETRIES,
            )
            return cached
        # No cache available — this is a genuine error
        logger.error("Failed to download sector ETF data after %d retries (no cache)", MAX_RETRIES)
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
    """Save sector allocation to JSON with lean-in multipliers."""
    selected = [r["symbol"] for r in ranked if r.get("selected")]

    total = len(ranked)
    top_cutoff = max(1, total // 3)
    bottom_cutoff = total - max(1, total // 3) + 1
    for r in ranked:
        rank = int(r.get("rank", 0))
        gics = ETF_TO_GICS.get(str(r.get("symbol", "")))
        if rank <= top_cutoff:
            r["lean_tier"] = "TOP"
            r["size_multiplier"] = LEAN_IN_BOOST
        elif rank >= bottom_cutoff:
            r["lean_tier"] = "BOTTOM"
            r["size_multiplier"] = LEAN_OUT_PENALTY
        else:
            r["lean_tier"] = "MID"
            r["size_multiplier"] = NEUTRAL_MULT
        r["gics_sector"] = gics or "Unknown"

    output = {
        "timestamp": datetime.now().isoformat(),
        "top_sectors": selected,
        "rankings": ranked,
        "config": {
            "top_n": TOP_N,
            "lookback_days": LOOKBACK_DAYS,
            "lean_in_boost": LEAN_IN_BOOST,
            "lean_out_penalty": LEAN_OUT_PENALTY,
        },
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


ETF_TO_GICS: Dict[str, str] = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLE": "Energy",
    "XLV": "Healthcare",
    "XLI": "Industrials",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLU": "Utilities",
    "XLC": "Communication Services",
    "XLRE": "Real Estate",
    "XLB": "Materials",
}

LEAN_IN_BOOST = 1.25
LEAN_OUT_PENALTY = 0.75
NEUTRAL_MULT = 1.0


def load_sector_momentum_multiplier(gics_sector: str) -> float:
    """Return a position-sizing multiplier based on sector relative strength.

    Top-ranked sectors get a LEAN_IN_BOOST (1.25x), bottom-ranked sectors get a
    LEAN_OUT_PENALTY (0.75x), and middle sectors stay at 1.0x.

    This transforms the sector gate from a pure "cap" mechanism into a
    "lean-in / lean-out" overlay that tilts capital toward momentum sectors.
    """
    if not OUTPUT_FILE.exists():
        return NEUTRAL_MULT
    try:
        data = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
        rankings: List[Dict[str, object]] = data.get("rankings", [])
        if not rankings:
            return NEUTRAL_MULT
    except (OSError, ValueError):
        return NEUTRAL_MULT

    gics_to_rank: Dict[str, int] = {}
    for entry in rankings:
        etf = entry.get("symbol", "")
        rank = entry.get("rank", 0)
        gics = ETF_TO_GICS.get(etf)
        if gics and isinstance(rank, (int, float)):
            gics_to_rank[gics] = int(rank)

    rank = gics_to_rank.get(gics_sector)
    if rank is None:
        return NEUTRAL_MULT

    total = len(gics_to_rank)
    if total == 0:
        return NEUTRAL_MULT

    top_cutoff = max(1, total // 3)
    bottom_cutoff = total - max(1, total // 3) + 1

    if rank <= top_cutoff:
        return LEAN_IN_BOOST
    if rank >= bottom_cutoff:
        return LEAN_OUT_PENALTY
    return NEUTRAL_MULT


def load_sector_rankings_detail() -> Dict[str, Dict[str, Any]]:
    """Return full sector rankings keyed by GICS sector name.

    Each value contains: rank, return_63d, multiplier, tier (TOP/MID/BOTTOM).
    """
    result: Dict[str, Dict[str, Any]] = {}
    if not OUTPUT_FILE.exists():
        return result
    try:
        data = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
        rankings = data.get("rankings", [])
    except (OSError, ValueError):
        return result

    total = len(rankings)
    top_cutoff = max(1, total // 3)
    bottom_cutoff = total - max(1, total // 3) + 1

    for entry in rankings:
        etf = entry.get("symbol", "")
        gics = ETF_TO_GICS.get(etf)
        if not gics:
            continue
        rank = int(entry.get("rank", 0))
        if rank <= top_cutoff:
            tier = "TOP"
        elif rank >= bottom_cutoff:
            tier = "BOTTOM"
        else:
            tier = "MID"
        result[gics] = {
            "rank": rank,
            "return_63d": entry.get("return_63d", 0.0),
            "etf": etf,
            "multiplier": load_sector_momentum_multiplier(gics),
            "tier": tier,
        }
    return result


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
        logger.warning("No sector data available — skipping allocation update")
        return

    # Detect if we're using cached data (no fresh price → skip re-saving)
    is_cached = OUTPUT_FILE.exists() and any(
        r == json.loads(OUTPUT_FILE.read_text(encoding="utf-8")).get("rankings", [{}])[0]
        for r in ranked[:1]
    ) if OUTPUT_FILE.exists() else False

    for r in ranked:
        marker = "*" if r.get("selected") else " "
        ret = r.get("return_63d", 0) or 0
        price = r.get("price", 0) or 0
        logger.info(
            " %s %2d. %-5s  63d ret: %+6.2f%%  price: $%.2f",
            marker, r["rank"], r["symbol"],
            ret * 100, price,
        )

    if not is_cached:
        save_allocation(ranked)
        logger.info("Done")
    else:
        logger.warning("Skipped saving — data is from cache (no fresh download)")


if __name__ == "__main__":
    main()
