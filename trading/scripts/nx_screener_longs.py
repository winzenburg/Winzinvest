#!/usr/bin/env python3
"""
NX Long Screener — inverse NX criteria for uptrend/long entry.

Screens for strong uptrend: RS above SPY, price above MAs, positive momentum,
and structure (hl_ratio) in upper range. Output: watchlist_longs.json for
execute_longs or execute_dual_mode.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from nx_screener_production import (
    apply_liquidity_filter,
    calculate_nx_metrics,
    fetch_spy_data,
    fetch_symbol_data,
    MIN_AVG_DOLLAR_VOLUME_20D,
    MIN_AVG_VOLUME_20D,
    MIN_PRICE,
)
from universe_builder import build_universe
from mtf_confirmation import compute_mtf_score
from earnings_catalyst import compute_earnings_boost
from sector_rotation import load_sector_momentum_multiplier
from sector_gates import SECTOR_MAP

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(
            Path(__file__).resolve().parent.parent / "logs" / "nx_screener_longs.log"
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

from paths import TRADING_DIR as WORKSPACE
OUTPUT_FILE = WORKSPACE / "watchlist_longs.json"

# Long thresholds — rs_pct is the raw 20-day return difference vs SPY
# (typically ranges -0.20 to +0.30), so 0.01 = just beating SPY.
# Longs are the core portfolio; bar is moderate to build a wide book.
LONG_THRESHOLDS = {
    "rs_min": 0.01,
    "recent_return_min": 0.02,
    "rvol_min": 0.85,
    "price_above_50ma": True,
    "price_above_100ma": True,
    "hl_ratio_min": 0.45,
}

LONG_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "TSLA", "AMZN", "ASML", "NFLX",
    "ADBE", "INTC", "QCOM", "AVGO", "AMD", "AMAT", "LRCX", "NXPI", "SNPS", "CDNS",
    "CRWD", "DDOG", "NET", "OKTA", "SNOW", "SHOP", "COIN", "UPST",
    "XOM", "CVX", "COP", "EOG", "FCX", "RIO", "BHP", "XLE", "QQQ", "SPY",
]


from nx_screener_production import HYBRID_AMS_WEIGHT


def _hybrid_score(metrics: Dict[str, Any]) -> float:
    """Combine NX quality score with AMS volume/HTF boost, MTF alignment,
    earnings catalyst, and sector rotation multiplier for ranking."""
    nx_score = (
        metrics.get("composite", 0.5) * 0.4 +
        metrics.get("rs_pct", 0) * 0.3 +
        metrics.get("structure", 0.5) * 0.3
    )
    ams_boost = (
        metrics.get("ams_vol_score", 0) * 0.5 +
        metrics.get("ams_htf_bias", 0.5) * 0.5
    )
    w = HYBRID_AMS_WEIGHT
    base_score = nx_score * (1 - w) + ams_boost * w

    mtf = metrics.get("mtf_score", 0.5)
    mtf_mult = 0.8 + 0.4 * mtf

    earnings_add = metrics.get("earnings_boost", 0.0)

    sector_mult = metrics.get("sector_multiplier", 1.0)

    return base_score * mtf_mult * sector_mult + earnings_add


def screen_for_longs(
    data_map: Dict[str, Any],
    spy_data: Any,
) -> List[Dict[str, Any]]:
    """Build long candidates using NX quality filter + AMS-boosted ranking.

    NX thresholds act as quality gates; AMS volume score and HTF bias
    improve candidate ordering so the best momentum + volume confluence
    setups rank highest.
    """
    long_candidates = []
    for symbol in data_map:
        metrics = calculate_nx_metrics(symbol, data_map[symbol], spy_data)
        if not metrics:
            continue
        if metrics.get("rs_pct", 0) < LONG_THRESHOLDS["rs_min"]:
            continue
        if metrics.get("recent_return", 0) < LONG_THRESHOLDS["recent_return_min"]:
            continue
        if metrics.get("rvol", 0) < LONG_THRESHOLDS["rvol_min"]:
            continue
        if LONG_THRESHOLDS.get("price_above_50ma") and metrics.get("price_vs_50ma", 0) < 1.0:
            continue
        if LONG_THRESHOLDS.get("price_above_100ma") and metrics.get("price_vs_100ma", 0) < 1.0:
            continue
        if metrics.get("hl_ratio", 0) < LONG_THRESHOLDS.get("hl_ratio_min", 0):
            continue
        rsi_val = metrics.get("ams_rsi", 50)
        if not (45 <= rsi_val <= 75):
            continue
        mtf = compute_mtf_score(data_map[symbol], side="LONG")
        if mtf is not None:
            metrics["mtf_score"] = mtf

        earnings = compute_earnings_boost(symbol, data_map[symbol], side="LONG")
        if earnings.get("is_catalyst"):
            metrics["earnings_boost"] = earnings["earnings_boost"]
            metrics["earnings_date"] = earnings["earnings_date"]

        sector = SECTOR_MAP.get(symbol)
        if sector:
            metrics["sector_multiplier"] = load_sector_momentum_multiplier(sector)
            metrics["sector"] = sector

        metrics["hybrid_score"] = round(_hybrid_score(metrics), 4)
        long_candidates.append({
            **metrics,
            "reason": (
                f"Uptrend: RS={metrics.get('rs_pct', 0):.3f}, "
                f"vol={metrics.get('ams_vol_score', 0):.2f}, "
                f"mtf={metrics.get('mtf_score', 0.5):.2f}, "
                f"earn={metrics.get('earnings_boost', 0):.2f}, "
                f"score={metrics.get('hybrid_score', 0):.3f}"
            ),
        })
    long_candidates.sort(key=lambda x: x.get("hybrid_score", 0), reverse=True)
    return long_candidates


def main() -> None:
    logger.info("=== NX LONG SCREENER ===")

    all_symbols = build_universe(include_etfs=True)
    logger.info("Universe: %d symbols", len(all_symbols))

    spy_data = fetch_spy_data()
    data_map = fetch_symbol_data(all_symbols)

    data_map = apply_liquidity_filter(data_map)
    logger.info("Post-liquidity: %d symbols", len(data_map))

    long_candidates = screen_for_longs(data_map, spy_data)
    logger.info("Long candidates: %d", len(long_candidates))

    payload = {
        "generated_at": datetime.now().isoformat(),
        "long_candidates": long_candidates,
        "total": len(long_candidates),
    }
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(payload, indent=2))
    logger.info("Wrote %s", OUTPUT_FILE)

    try:
        from export_tv_watchlist import export_tv_watchlist
        export_tv_watchlist()
        logger.info("TradingView pullback candidates exported")
    except Exception as exc:
        logger.warning("TV watchlist export failed (non-fatal): %s", exc)


if __name__ == "__main__":
    main()
