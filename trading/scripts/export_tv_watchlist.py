#!/usr/bin/env python3
"""
Export daily screener candidates for TradingView pullback monitoring.

Reads watchlist_longs.json (from nx_screener_longs.py) and outputs:
  1. A TradingView-importable .txt watchlist (one EXCHANGE:SYMBOL per line)
  2. A JSON endpoint-ready file for the webhook server

Run after the daily screener completes (e.g. via cron or scheduler).
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

from paths import TRADING_DIR as WORKSPACE
WATCHLIST_LONGS = WORKSPACE / "watchlist_longs.json"
WATCHLIST_SHORTS = WORKSPACE / "watchlist_multimode.json"

TV_WATCHLIST_DIR = WORKSPACE / "tradingview_exports"
TV_PULLBACK_CANDIDATES = TV_WATCHLIST_DIR / "mtf_pullback_candidates.txt"
TV_PULLBACK_JSON = TV_WATCHLIST_DIR / "mtf_pullback_candidates.json"


def _is_valid_candidate(c: object) -> bool:
    return (
        isinstance(c, dict)
        and isinstance(c.get("symbol"), str)
        and len(c["symbol"].strip()) > 0
    )


def _load_long_candidates() -> List[Dict[str, Any]]:
    if not WATCHLIST_LONGS.exists():
        logger.warning("watchlist_longs.json not found")
        return []
    try:
        data = json.loads(WATCHLIST_LONGS.read_text())
        candidates = data.get("long_candidates", [])
        return [c for c in candidates if _is_valid_candidate(c)]
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to load longs: %s", exc)
        return []


def _load_short_candidates() -> List[Dict[str, Any]]:
    if not WATCHLIST_SHORTS.exists():
        return []
    try:
        data = json.loads(WATCHLIST_SHORTS.read_text())
        shorts = data.get("short_opportunities", {}).get("short", [])
        return [c for c in shorts if _is_valid_candidate(c)]
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to load shorts: %s", exc)
        return []


def export_tv_watchlist(max_symbols: int = 40) -> None:
    """Export top screener candidates to TradingView-compatible formats."""
    longs = _load_long_candidates()
    shorts = _load_short_candidates()

    combined: List[Dict[str, Any]] = []
    for c in longs:
        c["side"] = "LONG"
        combined.append(c)
    for c in shorts[:10]:
        c["side"] = "SHORT"
        combined.append(c)

    symbols_seen: set[str] = set()
    deduped: List[Dict[str, Any]] = []
    for c in combined:
        sym = c["symbol"].strip().upper()
        if sym not in symbols_seen:
            symbols_seen.add(sym)
            deduped.append(c)

    top = deduped[:max_symbols]

    TV_WATCHLIST_DIR.mkdir(parents=True, exist_ok=True)

    tv_lines = []
    for c in top:
        sym = c["symbol"].strip().upper()
        exchange = "NASDAQ" if sym in _NASDAQ_COMMON else "NYSE"
        tv_lines.append(f"{exchange}:{sym}")

    TV_PULLBACK_CANDIDATES.write_text("\n".join(tv_lines) + "\n")
    logger.info("TradingView watchlist: %d symbols → %s", len(tv_lines), TV_PULLBACK_CANDIDATES)

    json_payload = {
        "generated_at": datetime.now().isoformat(),
        "total": len(top),
        "candidates": [
            {
                "symbol": c["symbol"].strip().upper(),
                "side": c.get("side", "LONG"),
                "price": c.get("price", 0),
                "hybrid_score": c.get("hybrid_score", 0),
                "composite_score": c.get("composite", 0),
                "rs_pct": c.get("rs_pct", 0),
            }
            for c in top
        ],
    }
    TV_PULLBACK_JSON.write_text(json.dumps(json_payload, indent=2))
    logger.info("JSON candidates: %d → %s", len(top), TV_PULLBACK_JSON)


_NASDAQ_COMMON = {
    "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "META", "TSLA", "AMZN", "NFLX",
    "ADBE", "INTC", "QCOM", "AVGO", "AMD", "AMAT", "LRCX", "NXPI", "SNPS",
    "CDNS", "CRWD", "DDOG", "NET", "OKTA", "SNOW", "COIN", "UPST", "SHOP",
    "MRVL", "MU", "PANW", "ABNB", "FTNT", "ZS", "TEAM", "TTD", "MELI",
    "ISRG", "REGN", "MRNA", "AMGN", "GILD", "BKNG", "PYPL", "SQ",
    "QQQ", "TQQQ", "SQQQ",
}


if __name__ == "__main__":
    export_tv_watchlist()
