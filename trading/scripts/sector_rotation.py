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

from atomic_io import atomic_write_json
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
    atomic_write_json(OUTPUT_FILE, output)
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

MACRO_EVENTS_FILE = WORKSPACE / "config" / "macro_events.json"
REGIME_STATE_FILE = WORKSPACE / "logs" / "regime_state.json"


def load_macro_event_size_adjust() -> float:
    """Sum size_multiplier_adjust across all active macro events.

    Returns an additive adjustment (e.g. -0.25 means reduce all position sizes
    by 25%).  The calling code should clamp the result and apply multiplicatively:
        effective_mult = max(0.1, 1.0 + size_adjust)
    """
    total = 0.0
    if not MACRO_EVENTS_FILE.exists():
        return total
    try:
        events = json.loads(MACRO_EVENTS_FILE.read_text(encoding="utf-8"))
        if not isinstance(events, list):
            return total
        today = datetime.now().strftime("%Y-%m-%d")
        for ev in events:
            if not isinstance(ev, dict) or not ev.get("active", False):
                continue
            start = ev.get("start_date", "")
            end = ev.get("end_date")
            if start and today < start:
                continue
            if end and today > end:
                continue
            adj = ev.get("size_multiplier_adjust", 0.0)
            if isinstance(adj, (int, float)):
                total += adj
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("Failed to load macro event size adjustments: %s", exc)
    return total


def load_macro_event_overrides() -> Dict[str, float]:
    """Read active macro event sector boosts from macro_events.json.

    Returns a dict of {GICS_sector: multiplicative_boost} merged across all
    active events.  E.g. {"Energy": 1.4, "Materials": 1.15}.
    """
    merged: Dict[str, float] = {}
    if not MACRO_EVENTS_FILE.exists():
        return merged
    try:
        events = json.loads(MACRO_EVENTS_FILE.read_text(encoding="utf-8"))
        if not isinstance(events, list):
            return merged
        today = datetime.now().strftime("%Y-%m-%d")
        for ev in events:
            if not isinstance(ev, dict):
                continue
            if not ev.get("active", False):
                continue
            start = ev.get("start_date", "")
            end = ev.get("end_date")
            if start and today < start:
                continue
            if end and today > end:
                continue
            boosts = ev.get("sector_boosts", {})
            if isinstance(boosts, dict):
                for sector, mult in boosts.items():
                    if isinstance(mult, (int, float)):
                        merged[sector] = max(merged.get(sector, 1.0), mult)
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("Failed to load macro event overrides: %s", exc)
    return merged


def load_macro_event_caps() -> Dict[str, float]:
    """Read active macro event sector_caps_override values.

    Returns a dict of {GICS_sector: cap_fraction}, e.g. {"Energy": 0.40}.
    """
    merged: Dict[str, float] = {}
    if not MACRO_EVENTS_FILE.exists():
        return merged
    try:
        events = json.loads(MACRO_EVENTS_FILE.read_text(encoding="utf-8"))
        if not isinstance(events, list):
            return merged
        today = datetime.now().strftime("%Y-%m-%d")
        for ev in events:
            if not isinstance(ev, dict):
                continue
            if not ev.get("active", False):
                continue
            start = ev.get("start_date", "")
            end = ev.get("end_date")
            if start and today < start:
                continue
            if end and today > end:
                continue
            caps = ev.get("sector_caps_override", {})
            if isinstance(caps, dict):
                for sector, cap in caps.items():
                    if isinstance(cap, (int, float)):
                        merged[sector] = max(merged.get(sector, 0.0), cap)
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("Failed to load macro event cap overrides: %s", exc)
    return merged


def _load_commodity_sector_multipliers() -> Dict[str, float]:
    """Read commodity triggers from regime_state.json and return per-sector multipliers.

    Chain logic (all multiplicative; strongest signal wins per sector):
      Energy:
        - Oil energy_multiplier (1.35 crisis / 1.15 surge / 0.80 collapse)
        - USD usd_multiplier (0.90 strong dollar / 1.10 weak dollar)
      Materials:
        - Copper surge → 1.10x  (industrial boom)
        - Copper collapse → 0.88x (demand warning)
        - USD surge → 0.90x (strong dollar suppresses commodity sector)
        - USD weak → 1.10x (weak dollar inflates commodity sector)
      Industrials:
        - Copper surge → 1.08x (construction/capex expansion)
        - Copper collapse → 0.92x (industrial demand warning)
      Consumer Staples:
        - food_chain_alert (oil+grain) → 0.85x (margin squeeze)
        - livestock_chain_alert (corn/soy) → 0.88x (feed cost pressure)
        - Both → 0.80x (compound squeeze)
      Consumer Discretionary:
        - livestock_chain_alert → 0.92x (food/disposable income erosion)
    """
    result: Dict[str, float] = {}
    if not REGIME_STATE_FILE.exists():
        return result
    try:
        state = json.loads(REGIME_STATE_FILE.read_text(encoding="utf-8"))
        ct = state.get("commodity_triggers", {})
        if not isinstance(ct, dict):
            return result

        # --- Energy ---
        energy_mult = float(ct.get("energy_multiplier", 1.0))
        usd_mult    = float(ct.get("usd_multiplier", 1.0))
        result["Energy"] = round(energy_mult * usd_mult, 4)

        # --- Materials (copper + USD) ---
        copper_mult = float(ct.get("copper_multiplier", 1.0))
        materials_mult = round(copper_mult * usd_mult, 4)
        if materials_mult != 1.0:
            result["Materials"] = materials_mult

        # --- Industrials (copper) ---
        copper_level = ct.get("copper_level", "NORMAL")
        if copper_level == "SURGE":
            result["Industrials"] = 1.08
        elif copper_level == "COLLAPSE":
            result["Industrials"] = 0.92

        # --- Consumer Staples (food_chain_alert + livestock_chain_alert) ---
        food_alert      = ct.get("food_chain_alert") is True
        livestock_alert = ct.get("livestock_chain_alert") is True
        if food_alert and livestock_alert:
            result["Consumer Staples"] = 0.80
        elif food_alert:
            result["Consumer Staples"] = 0.85
        elif livestock_alert:
            result["Consumer Staples"] = 0.88

        # --- Consumer Discretionary (livestock squeezes disposable income) ---
        if livestock_alert:
            result["Consumer Discretionary"] = 0.92

    except (OSError, ValueError, TypeError) as exc:
        logger.warning("Failed to load commodity sector multipliers: %s", exc)
    return result


def load_sector_momentum_multiplier(gics_sector: str) -> float:
    """Return a position-sizing multiplier based on sector relative strength,
    macro event annotations, and commodity price triggers.

    Layering:
      1. Base momentum tier (TOP → 1.25, MID → 1.0, BOTTOM → 0.75)
      2. Macro event sector boost (e.g. Energy 1.4x during Iran-Israel war)
      3. Commodity trigger energy multiplier (e.g. 1.15x for oil surge)

    All layers are multiplicative.
    """
    if not OUTPUT_FILE.exists():
        base = NEUTRAL_MULT
    else:
        try:
            data = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
            rankings: List[Dict[str, object]] = data.get("rankings", [])
            if not rankings:
                base = NEUTRAL_MULT
            else:
                gics_to_rank: Dict[str, int] = {}
                for entry in rankings:
                    etf = entry.get("symbol", "")
                    rank = entry.get("rank", 0)
                    gics = ETF_TO_GICS.get(etf)
                    if gics and isinstance(rank, (int, float)):
                        gics_to_rank[gics] = int(rank)

                rank = gics_to_rank.get(gics_sector)
                if rank is None:
                    base = NEUTRAL_MULT
                else:
                    total = len(gics_to_rank)
                    if total == 0:
                        base = NEUTRAL_MULT
                    else:
                        top_cutoff = max(1, total // 3)
                        bottom_cutoff = total - max(1, total // 3) + 1
                        if rank <= top_cutoff:
                            base = LEAN_IN_BOOST
                        elif rank >= bottom_cutoff:
                            base = LEAN_OUT_PENALTY
                        else:
                            base = NEUTRAL_MULT
        except (OSError, ValueError):
            base = NEUTRAL_MULT

    macro_boosts = load_macro_event_overrides()
    macro_mult = macro_boosts.get(gics_sector, 1.0)

    commodity_mults = _load_commodity_sector_multipliers()
    commodity_mult = commodity_mults.get(gics_sector, 1.0)

    size_adj = load_macro_event_size_adjust()
    global_mult = max(0.10, 1.0 + size_adj)

    return base * macro_mult * commodity_mult * global_mult


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
