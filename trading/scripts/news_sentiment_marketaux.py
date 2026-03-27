#!/usr/bin/env python3
"""
Marketaux News Sentiment Monitor

Fetches recent financial news from the Marketaux API, computes aggregate
sentiment for portfolio holdings and macro keywords, and saves structured
results to logs/news_sentiment.json.

Designed to run hourly during market hours via the scheduler.

API docs: https://www.marketaux.com/documentation
"""

import json
import logging
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from env_loader import load_env
from atomic_io import atomic_write_json
from paths import TRADING_DIR, LOGS_DIR

load_env()

logger = logging.getLogger(__name__)

MARKETAUX_BASE_URL = "https://api.marketaux.com/v1/news/all"
SENTIMENT_OUTPUT = LOGS_DIR / "news_sentiment.json"
SNAPSHOT_FILE = LOGS_DIR / "dashboard_snapshot.json"

MACRO_KEYWORDS = (
    '"oil" | "tariff" | "fed" | "war" | "sanctions" '
    '| "wheat" | "fertilizer" | "food prices" | "grain"'
)

MAX_ARTICLES_PER_CALL = 50


def _get_api_key() -> Optional[str]:
    return os.environ.get("MARKETAUX_API_KEY") or None


def _load_portfolio_symbols() -> List[str]:
    """Read current stock symbols from the latest dashboard snapshot."""
    if not SNAPSHOT_FILE.exists():
        return []
    try:
        snap = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
        positions = snap.get("positions", {}).get("list", [])
        symbols: List[str] = []
        for pos in positions:
            sym = pos.get("symbol")
            sec_type = pos.get("sec_type", "STK")
            if isinstance(sym, str) and sec_type == "STK" and sym not in symbols:
                symbols.append(sym)
        return symbols
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("Failed to load portfolio symbols: %s", exc)
        return []


def _fetch_marketaux(
    api_key: str,
    symbols: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = MAX_ARTICLES_PER_CALL,
) -> Optional[Dict[str, Any]]:
    """Make a single GET request to the Marketaux news endpoint."""
    params: Dict[str, str] = {
        "api_token": api_key,
        "language": "en",
        "must_have_entities": "true",
        "filter_entities": "true",
        "limit": str(limit),
        "published_after": (datetime.now(timezone.utc) - timedelta(hours=24)).strftime(
            "%Y-%m-%dT%H:%M"
        ),
    }
    if symbols:
        params["symbols"] = symbols
    if search:
        params["search"] = search

    url = f"{MARKETAUX_BASE_URL}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MissionControl/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        logger.warning("Marketaux HTTP %d: %s", exc.code, exc.reason)
        return None
    except Exception as exc:
        logger.warning("Marketaux request failed: %s", exc)
        return None


def _extract_entity_sentiments(
    data: Dict[str, Any],
) -> tuple:
    """Extract per-symbol sentiment scores and worst headlines from API response.

    Returns (symbol_scores, worst_headlines, total_sentiments) where
    symbol_scores = {SYMBOL: [score, score, ...]} and
    worst_headlines = [{title, source, sentiment, symbols, published_at, url}]
    """
    symbol_scores: Dict[str, List[float]] = {}
    worst_headlines: List[Dict[str, Any]] = []
    all_sentiments: List[float] = []

    articles = data.get("data", [])
    if not isinstance(articles, list):
        return symbol_scores, worst_headlines, all_sentiments

    for article in articles:
        if not isinstance(article, dict):
            continue
        entities = article.get("entities", [])
        if not isinstance(entities, list):
            continue

        article_sentiments: List[float] = []
        article_symbols: List[str] = []

        for entity in entities:
            if not isinstance(entity, dict):
                continue
            score = entity.get("sentiment_score")
            sym = entity.get("symbol")
            if isinstance(score, (int, float)):
                article_sentiments.append(float(score))
                all_sentiments.append(float(score))
                if isinstance(sym, str) and sym:
                    symbol_scores.setdefault(sym, []).append(float(score))
                    if sym not in article_symbols:
                        article_symbols.append(sym)

        if article_sentiments:
            avg_sent = sum(article_sentiments) / len(article_sentiments)
            if avg_sent < -0.3:
                worst_headlines.append({
                    "title": str(article.get("title", ""))[:200],
                    "source": str(article.get("source", "")),
                    "sentiment": round(avg_sent, 4),
                    "symbols": article_symbols[:5],
                    "published_at": str(article.get("published_at", "")),
                    "url": str(article.get("url", ""))[:500],
                })

    worst_headlines.sort(key=lambda h: h["sentiment"])
    return symbol_scores, worst_headlines[:10], all_sentiments


class NewsSentimentMonitor:
    """Fetches and aggregates news sentiment from Marketaux."""

    def __init__(self) -> None:
        self.api_key = _get_api_key()
        self.api_calls_made = 0

    def run(self) -> Dict[str, Any]:
        """Execute the full sentiment scan and save results."""
        if not self.api_key:
            logger.warning("MARKETAUX_API_KEY not set — skipping news sentiment")
            return {"error": "no_api_key"}

        portfolio_symbols = _load_portfolio_symbols()
        all_symbol_scores: Dict[str, List[float]] = {}
        all_worst_headlines: List[Dict[str, Any]] = []
        all_portfolio_sentiments: List[float] = []
        all_macro_sentiments: List[float] = []

        # Call 1: portfolio symbols (batch up to 20 at a time for API limits)
        portfolio_data = None
        if portfolio_symbols:
            batch = ",".join(portfolio_symbols[:20])
            logger.info("Fetching portfolio sentiment for %d symbols", min(len(portfolio_symbols), 20))
            portfolio_data = _fetch_marketaux(self.api_key, symbols=batch)
            self.api_calls_made += 1
            if portfolio_data:
                scores, headlines, sents = _extract_entity_sentiments(portfolio_data)
                for sym, vals in scores.items():
                    all_symbol_scores.setdefault(sym, []).extend(vals)
                all_worst_headlines.extend(headlines)
                all_portfolio_sentiments.extend(sents)

        # Call 2: macro keyword search
        logger.info("Fetching macro keyword sentiment")
        macro_data = _fetch_marketaux(self.api_key, search=MACRO_KEYWORDS)
        self.api_calls_made += 1
        if macro_data:
            scores, headlines, sents = _extract_entity_sentiments(macro_data)
            for sym, vals in scores.items():
                all_symbol_scores.setdefault(sym, []).extend(vals)
            all_worst_headlines.extend(headlines)
            all_macro_sentiments.extend(sents)

        # Compute aggregates
        portfolio_sentiment = (
            round(sum(all_portfolio_sentiments) / len(all_portfolio_sentiments), 4)
            if all_portfolio_sentiments
            else 0.0
        )
        macro_sentiment = (
            round(sum(all_macro_sentiments) / len(all_macro_sentiments), 4)
            if all_macro_sentiments
            else 0.0
        )

        # Per-symbol summary (only portfolio symbols)
        held_set = set(portfolio_symbols)
        symbol_sentiments: Dict[str, Dict[str, Any]] = {}
        for sym, vals in all_symbol_scores.items():
            if sym in held_set and vals:
                symbol_sentiments[sym] = {
                    "score": round(sum(vals) / len(vals), 4),
                    "article_count": len(vals),
                }

        # Deduplicate and sort worst headlines
        seen_titles: set = set()
        unique_headlines: List[Dict[str, Any]] = []
        for h in sorted(all_worst_headlines, key=lambda x: x["sentiment"]):
            if h["title"] not in seen_titles:
                seen_titles.add(h["title"])
                unique_headlines.append(h)
            if len(unique_headlines) >= 10:
                break

        total_articles = 0
        if portfolio_data:
            total_articles += portfolio_data.get("meta", {}).get("returned", 0)
        if macro_data:
            total_articles += macro_data.get("meta", {}).get("returned", 0)

        # Merge into existing file — preserve Bulltard, MacroVoices, and Lyn Alden
        # keys written by their own pullers. Marketaux only owns its own namespace.
        existing: Dict[str, Any] = {}
        if SENTIMENT_OUTPUT.exists():
            try:
                existing = json.loads(SENTIMENT_OUTPUT.read_text(encoding="utf-8"))
            except Exception:
                existing = {}

        # Preserve third-party source keys that Marketaux does not own
        _PRESERVED_PREFIXES = ("bulltard_", "macrovoices_", "lyn_alden_")
        for key, val in existing.items():
            if any(key.startswith(p) for p in _PRESERVED_PREFIXES):
                pass  # keep below

        marketaux_score = round(sum(all_macro_sentiments) / len(all_macro_sentiments), 4) \
            if all_macro_sentiments else None

        # Blend macro_sentiment: Marketaux (50%) + Bulltard (30%) + MacroVoices/LynAlden (20%)
        # Falls back gracefully if any source is missing.
        bt_score  = existing.get("bulltard_bias_score")
        mv_score  = existing.get("macrovoices_bias_score")
        la_score  = existing.get("lyn_alden_bias_score")
        scores: list[tuple[float, float]] = []  # (weight, score)
        if marketaux_score is not None:
            scores.append((0.50, marketaux_score))
        if bt_score is not None:
            scores.append((0.30, float(bt_score)))
        secondary = [s for s in [mv_score, la_score] if s is not None]
        if secondary:
            scores.append((0.20, sum(float(s) for s in secondary) / len(secondary)))

        if scores:
            total_weight = sum(w for w, _ in scores)
            blended = sum(w * s for w, s in scores) / total_weight
            blended_macro = round(blended, 4)
        else:
            blended_macro = macro_sentiment  # raw Marketaux only

        result: Dict[str, Any] = {
            **{k: v for k, v in existing.items()
               if any(k.startswith(p) for p in _PRESERVED_PREFIXES)},
            "marketaux_score":     marketaux_score,
            "timestamp":           datetime.now().isoformat(),
            "portfolio_sentiment": portfolio_sentiment,
            "macro_sentiment":     blended_macro,
            "symbol_sentiments":   symbol_sentiments,
            "worst_headlines":     unique_headlines,
            "articles_analyzed":   total_articles,
            "api_calls_made":      self.api_calls_made,
        }

        atomic_write_json(SENTIMENT_OUTPUT, result)
        logger.info(
            "News sentiment saved: portfolio=%.3f, macro=%.3f (blended), articles=%d",
            portfolio_sentiment,
            blended_macro,
            total_articles,
        )
        return result


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    monitor = NewsSentimentMonitor()
    result = monitor.run()
    if "error" in result:
        logger.error("News sentiment scan failed: %s", result["error"])
    else:
        logger.info("Done — %d API calls used", result.get("api_calls_made", 0))


if __name__ == "__main__":
    main()
