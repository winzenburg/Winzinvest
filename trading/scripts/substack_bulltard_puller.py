#!/usr/bin/env python3
"""
Bulltard Substack Daily Puller
https://www.jamesbulltard.com

Fetches the latest "The Running Of The Bulltards" Substack recap,
extracts market sentiment and key themes, and:
  1. Appends a structured entry to logs/bulltard_insights.json
  2. Writes bulltard_* keys into logs/news_sentiment.json so
     regime_monitor.py can factor it into the macro regime score.
  3. Sends a Telegram notification when new content is found.

Designed to run daily at 4:30 PM ET (after market close) via scheduler.py.
"""

import json
import logging
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atomic_io import atomic_write_json
from paths import TRADING_DIR, LOGS_DIR

try:
    from notifications import notify_event
except ImportError:
    def notify_event(event: str, **kwargs: Any) -> None:  # type: ignore[misc]
        pass

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

FEED_URL        = "https://www.jamesbulltard.com/feed"
INSIGHTS_FILE   = LOGS_DIR / "bulltard_insights.json"
STATE_FILE      = LOGS_DIR / "bulltard_state.json"
SENTIMENT_FILE  = LOGS_DIR / "news_sentiment.json"

# Maximum entries to keep in insights file
MAX_HISTORY = 30

# ── Sentiment keyword lists ────────────────────────────────────────────────────

_BEARISH_PHRASES = [
    "below 200", "downtrend", "bearish", "rejection", "rejected", "avoid",
    "carnage", "ugly", "trap", "danger", "caution", "cautious", "weakness",
    "weak", "breakdown", "broke down", "selling", "pressure", "declining",
    "distribution", "don't fight", "do not fight", "cut", "be careful",
    "vix remains bid", "vix is bid", "nobody wants to hold", "not good",
    "first sign", "warning sign", "rough", "fell", "dropped", "lower",
    "bottoming is a process", "reality check", "overdue",
]

_BULLISH_PHRASES = [
    "above 200", "uptrend", "bullish", "breakout", "broke out", "reclaim",
    "reclaimed", "strong", "strength", "momentum", "buy", "accumulation",
    "going higher", "rally", "rallied", "green", "recovery", "confirming",
    "back above", "holding up", "positive", "opportunity", "best idea",
    "first step", "looking good",
]

# Known single-token stock symbols to exclude from ticker detection
_COMMON_WORDS = {
    "I", "A", "THE", "AND", "OR", "OF", "IN", "ON", "AT", "TO", "IS",
    "IT", "BE", "AS", "AN", "BY", "WE", "MY", "SO", "DO", "UP", "IF",
    "GO", "NO", "OK", "US", "PM", "ET", "EM", "MA", "EMA", "SMA", "VIX",
    "WTI", "CPI", "PPI", "GDP", "FED", "ECB", "IMF", "GDP", "USD", "EUR",
    "ALL", "ARE", "HAS", "HAD", "NOT", "BUT", "FOR", "YOU", "HIS", "HER",
    "ITS", "CAN", "MAY", "HOW", "WHO", "THEY", "THEM", "THIS", "THAT",
    "WITH", "FROM", "HAVE", "WILL", "BEEN", "WHEN", "WHAT", "WERE",
    "JUST", "OVER", "LIKE", "WELL", "BACK", "VERY", "GOOD", "EVEN",
    "SAME", "LOOK", "TAKE", "GIVE", "KNOW", "COME", "MAKE", "WANT",
    "WEEK", "DAY", "MOVE", "TIME", "LAST", "NEXT", "MONDAY", "FRIDAY",
    "SUNDAY", "RECAP", "TODAY", "OPEN", "BOOK", "LINK", "MORE", "THAT",
    "CBOE", "S&P", "SPY", "QQQ",  # keep these as themes, not ticker shorts
}

# ── HTML stripping ─────────────────────────────────────────────────────────────

class _HTMLStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.reset()
        self._parts: List[str] = []

    def handle_data(self, d: str) -> None:
        self._parts.append(d)

    def get_data(self) -> str:
        return " ".join(self._parts)


def _strip_html(html: str) -> str:
    s = _HTMLStripper()
    s.feed(html)
    text = s.get_data()
    # Collapse whitespace
    return re.sub(r"\s+", " ", text).strip()


# ── Sentiment analysis ─────────────────────────────────────────────────────────

def _score_sentiment(text: str) -> float:
    """
    Return a sentiment score in [-1.0, +1.0].
    Negative = bearish, positive = bullish.
    """
    lower = text.lower()
    bear = sum(1 for p in _BEARISH_PHRASES if p in lower)
    bull = sum(1 for p in _BULLISH_PHRASES if p in lower)
    total = bear + bull
    if total == 0:
        return 0.0
    raw = (bull - bear) / total
    # Clip to [-1, +1] and round
    return round(max(-1.0, min(1.0, raw)), 3)


def _bias_label(score: float) -> str:
    if score <= -0.6:
        return "VERY_BEARISH"
    if score <= -0.25:
        return "BEARISH"
    if score >= 0.6:
        return "VERY_BULLISH"
    if score >= 0.25:
        return "BULLISH"
    return "NEUTRAL"


# ── Key-level extraction ───────────────────────────────────────────────────────

def _extract_key_levels(text: str) -> List[str]:
    """
    Find sentences mentioning a price level near a named index/EMA/SMA.
    E.g. "660.39 is the 200 day on the SPY"
    """
    patterns = [
        r"\d{3,4}(?:\.\d{1,2})?\s+is\s+the\s+\d+\s+day",           # "660.39 is the 200 day"
        r"\d{3,4}(?:\.\d{1,2})?\s+(?:200|100|50|21|8)[- ](?:day|ema|sma|ma)",
        r"(?:200|100|50|21|8)[- ](?:day|ema|sma|ma)\s+(?:at|is|of|near)\s+[\$]?\d{3,4}(?:\.\d{1,2})?",
        r"(?:spy|qqq|spx|iwm)\s+(?:at|is|near|around|holds?|below|above)\s+[\$]?\d{3,4}(?:\.\d{1,2})?",
        r"(?:level|support|resistance|target)\s+(?:at|of|is|near)\s+[\$]?\d{3,4}(?:\.\d{1,2})?",
    ]
    sentences = re.split(r"[.!?\n]", text)
    found: List[str] = []
    for sent in sentences:
        s = sent.strip()
        for pat in patterns:
            if re.search(pat, s, re.IGNORECASE):
                cleaned = re.sub(r"\s+", " ", s)[:120]
                if cleaned not in found:
                    found.append(cleaned)
                break
    return found[:6]


def _extract_themes(text: str) -> List[str]:
    """Pull prominent recurring macro themes from the text."""
    theme_map = {
        "below 200 day":      r"\bbelow\b.{0,20}200.{0,10}day",
        "above 200 day":      r"\babove\b.{0,20}200.{0,10}day",
        "8/21 bearish cross": r"\b8\s*/\s*21\b.{0,30}cross",
        "8/21 bullish cross": r"\b8\s*/\s*21\b.{0,30}cross.{0,20}up",
        "VIX bid":            r"\bvix\b.{0,20}\bbid\b",
        "VIX falling":        r"\bvix\b.{0,20}fall|drop|declin",
        "oil above 100":      r"\boil\b.{0,20}10[0-9]",
        "tariff":             r"\btariff",
        "war":                r"\bwar\b",
        "geopolitical":       r"\bgeopolit",
        "earnings":           r"\bearning",
        "fed / rates":        r"\bfed\b|\brates?\b|\bfederal reserve",
        "SPY below 8 EMA":    r"\bspy\b.{0,30}8\s*ema|8\s*ema.{0,30}\bspy\b",
        "SPY below 21 EMA":   r"\bspy\b.{0,30}21\s*ema|21\s*ema.{0,30}\bspy\b",
        "no close above EMA": r"not.{0,30}clos.{0,20}(?:8|21)\s*ema",
        "weekly bearish candle": r"\bweekly\b.{0,20}\bcandle|hanging man",
    }
    lower = text.lower()
    found: List[str] = []
    for label, pat in theme_map.items():
        if re.search(pat, lower):
            found.append(label)
    return found


def _extract_tickers(text: str) -> List[str]:
    """
    Extract stock tickers — all-caps words 2-5 chars that don't appear in
    the common-word exclusion list and follow a $ sign or appear in context.
    """
    candidates = set()
    # $TICKER pattern
    for m in re.finditer(r"\$([A-Z]{1,5})\b", text):
        candidates.add(m.group(1))
    # ALL-CAPS 2-5 char words surrounded by spaces/punctuation
    for m in re.finditer(r"(?<![A-Z])([A-Z]{2,5})(?![A-Z])", text):
        word = m.group(1)
        if word not in _COMMON_WORDS and len(word) >= 2:
            candidates.add(word)
    # Always include known index/vol tickers if mentioned
    for known in ["SPY", "QQQ", "VIX", "IWM", "DIA", "TLT", "GLD", "USO"]:
        if known in text:
            candidates.add(known)
    return sorted(candidates)[:20]


# ── RSS parsing ────────────────────────────────────────────────────────────────

_NS = {"content": "http://purl.org/rss/1.0/modules/content/"}


def _fetch_feed() -> List[Dict[str, Any]]:
    """Fetch and parse the RSS feed. Returns a list of post dicts."""
    try:
        req = urllib.request.Request(
            FEED_URL,
            headers={"User-Agent": "MissionControl/1.0 (trading system; rss reader)"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        logger.error("Failed to fetch Bulltard RSS: %s", exc)
        return []

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        logger.error("RSS XML parse error: %s", exc)
        return []

    posts: List[Dict[str, Any]] = []
    for item in root.findall(".//item"):
        title   = item.findtext("title", "").strip()
        link    = item.findtext("link", "").strip()
        pub_raw = item.findtext("pubDate", "").strip()
        encoded = item.find("content:encoded", _NS)
        html_content = encoded.text if encoded is not None else item.findtext("description", "")

        # Parse publish date
        pub_dt: Optional[datetime] = None
        if pub_raw:
            try:
                # RFC 2822 date
                from email.utils import parsedate_to_datetime
                pub_dt = parsedate_to_datetime(pub_raw)
            except Exception:
                pass

        clean_text = _strip_html(html_content or "")

        posts.append({
            "title":      title,
            "link":       link,
            "pub_dt":     pub_dt,
            "pub_raw":    pub_raw,
            "clean_text": clean_text,
        })

    return posts


# ── State management ───────────────────────────────────────────────────────────

def _load_state() -> Dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"last_pulled_link": None, "last_pulled_at": None}


def _save_state(link: str) -> None:
    atomic_write_json(STATE_FILE, {
        "last_pulled_link": link,
        "last_pulled_at": datetime.now().isoformat(),
    })


def _load_insights() -> List[Dict[str, Any]]:
    if INSIGHTS_FILE.exists():
        try:
            data = json.loads(INSIGHTS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


# ── news_sentiment.json integration ───────────────────────────────────────────

def _merge_into_news_sentiment(bias_score: float, bias_label: str, title: str) -> None:
    """
    Write bulltard_* keys into news_sentiment.json so regime_monitor.py
    picks up the daily directional signal.
    """
    existing: Dict[str, Any] = {}
    if SENTIMENT_FILE.exists():
        try:
            existing = json.loads(SENTIMENT_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    existing["bulltard_bias_score"]  = bias_score
    existing["bulltard_bias_label"]  = bias_label
    existing["bulltard_title"]       = title
    existing["bulltard_updated_at"]  = datetime.now().isoformat()

    # If no Marketaux data exists yet, seed a macro_sentiment from Bulltard
    if "macro_sentiment" not in existing or existing.get("macro_sentiment") is None:
        existing["macro_sentiment"]      = bias_score
        existing["portfolio_sentiment"]  = 0.0
        existing["articles_analyzed"]    = 1
        existing["timestamp"]            = datetime.now().isoformat()
        existing["source"]               = "bulltard_only"
    else:
        # Blend: 40% Bulltard, 60% Marketaux
        existing["macro_sentiment"] = round(
            0.6 * float(existing.get("macro_sentiment", 0.0)) + 0.4 * bias_score, 3
        )
        existing["source"] = "blended"

    atomic_write_json(SENTIMENT_FILE, existing)
    logger.info("Merged Bulltard bias (%s / %.3f) into news_sentiment.json", bias_label, bias_score)


# ── Main ───────────────────────────────────────────────────────────────────────

def run(force: bool = False) -> Dict[str, Any]:
    """
    Pull latest Bulltard recap and process it.

    Args:
        force: If True, reprocess the most recent post even if already seen.

    Returns:
        dict with status, new_posts_count, latest_bias, latest_title.
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("=== Bulltard Substack Puller ===")

    state    = _load_state()
    insights = _load_insights()
    posts    = _fetch_feed()

    if not posts:
        logger.warning("No posts returned from feed")
        return {"status": "no_feed", "new_posts_count": 0}

    last_link = state.get("last_pulled_link")
    new_entries: List[Dict[str, Any]] = []

    for post in posts:
        link = post["link"]
        if not force and link == last_link:
            break  # already processed this and everything older

        clean = post["clean_text"]
        if len(clean) < 100:
            logger.debug("Skipping short post: %s (%d chars)", post["title"], len(clean))
            continue

        score  = _score_sentiment(clean)
        label  = _bias_label(score)
        levels = _extract_key_levels(clean)
        themes = _extract_themes(clean)
        tickers = _extract_tickers(clean)

        pub_date = post["pub_dt"]
        date_str = pub_date.strftime("%Y-%m-%d") if pub_date else datetime.now().strftime("%Y-%m-%d")

        entry: Dict[str, Any] = {
            "date":              date_str,
            "title":             post["title"],
            "url":               link,
            "pulled_at":         datetime.now().isoformat(),
            "bias_score":        score,
            "bias_label":        label,
            "key_levels":        levels,
            "themes":            themes,
            "tickers_mentioned": tickers,
            "summary":           clean[:600],
        }

        new_entries.append(entry)
        logger.info(
            "New post: %s | bias=%s (%.3f) | themes=%s",
            post["title"], label, score, themes[:4],
        )

    if not new_entries:
        logger.info("No new posts since last pull (last: %s)", last_link)
        return {"status": "no_new_posts", "new_posts_count": 0}

    # Prepend new entries (newest first) and trim to MAX_HISTORY
    insights = new_entries + insights
    insights = insights[:MAX_HISTORY]
    atomic_write_json(INSIGHTS_FILE, insights)
    logger.info("Saved %d new entry/entries to bulltard_insights.json", len(new_entries))

    # Use the most recent post for downstream sentiment
    latest = new_entries[0]
    _merge_into_news_sentiment(latest["bias_score"], latest["bias_label"], latest["title"])

    # Persist state — mark the newest post as processed
    _save_state(posts[0]["link"])

    # Telegram notification with daily digest
    _notify(latest, len(new_entries))

    return {
        "status":         "ok",
        "new_posts_count": len(new_entries),
        "latest_title":   latest["title"],
        "latest_bias":    latest["bias_label"],
        "latest_score":   latest["bias_score"],
        "latest_themes":  latest["themes"],
    }


def _notify(entry: Dict[str, Any], count: int) -> None:
    """Send Telegram notification for the new Bulltard recap."""
    bias   = entry["bias_label"]
    score  = entry["bias_score"]
    themes = entry.get("themes", [])
    levels = entry.get("key_levels", [])
    title  = entry["title"]
    url    = entry.get("url", "")

    bias_emoji = {
        "VERY_BEARISH": "🔴",
        "BEARISH":      "🟠",
        "NEUTRAL":      "⚪",
        "BULLISH":      "🟢",
        "VERY_BULLISH": "💚",
    }.get(bias, "⚪")

    lines = [
        f"{bias_emoji} Bulltard Recap: {title}",
        f"Bias: {bias} (score {score:+.2f})",
    ]
    if themes:
        lines.append("Themes: " + ", ".join(themes[:5]))
    if levels:
        lines.append("Key levels:")
        for lvl in levels[:3]:
            lines.append(f"  • {lvl}")
    lines.append(f"\n{url}")

    urgent = bias in ("VERY_BEARISH", "VERY_BULLISH")
    try:
        notify_event(
            "bulltard_recap",
            subject=f"{bias_emoji} Bulltard: {title} — {bias}",
            body="\n".join(lines),
            urgent=urgent,
        )
    except Exception as exc:
        logger.warning("Notification failed: %s", exc)


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Bulltard Substack Puller")
    parser.add_argument("--force", action="store_true", help="Re-process most recent post")
    parser.add_argument("--dry-run", action="store_true", help="Parse but don't write files")
    args = parser.parse_args()

    if args.dry_run:
        posts = _fetch_feed()
        if posts:
            p = posts[0]
            score = _score_sentiment(p["clean_text"])
            print(f"Title:   {p['title']}")
            print(f"Score:   {score} ({_bias_label(score)})")
            print(f"Levels:  {_extract_key_levels(p['clean_text'])}")
            print(f"Themes:  {_extract_themes(p['clean_text'])}")
            print(f"Summary: {p['clean_text'][:400]}")
        sys.exit(0)

    result = run(force=args.force)
    print(json.dumps(result, indent=2))
