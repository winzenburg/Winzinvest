#!/usr/bin/env python3
"""
Lyn Alden Monthly Newsletter Puller
https://www.lynalden.com

Lyn Alden publishes a free monthly newsletter, typically around the 22nd of each
month. The URL follows a predictable pattern:
  https://www.lynalden.com/{month-name}-{year}-newsletter/

Operation:
  - Constructs the expected URL for the current month (and previous, as a fallback)
  - Fetches the page — no authentication required, newsletter is publicly accessible
  - Parses title, body text, macro themes, indicators mentioned, and portfolio changes
  - Scores macro sentiment (same model as macrovoices_puller)
  - Appends a structured entry to logs/macrovoices_insights.json (shared insights store)
  - Merges sentiment into news_sentiment.json under the "lyn_alden_*" keys
  - Sends a Telegram digest via the notifications module

State:
  logs/lyn_alden_state.json — tracks last processed newsletter URL to prevent
  re-processing the same issue.

Scheduled: Weekly on Sundays at 10:00 AM MT via scheduler.py.
           Running weekly (rather than monthly) ensures we catch the newsletter
           promptly regardless of which day of the month it publishes.

CLI:
  python lyn_alden_puller.py               # Normal run
  python lyn_alden_puller.py --force       # Re-process even if URL already seen
  python lyn_alden_puller.py --dry-run     # Print extracted data, no writes
  python lyn_alden_puller.py --url URL     # Process a specific newsletter URL
"""

from __future__ import annotations

import json
import logging
import re
import sys
import urllib.request
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from env_loader import load_env
from atomic_io import atomic_write_json
from paths import LOGS_DIR

try:
    from notifications import notify_event
except ImportError:
    def notify_event(event: str, **kwargs: Any) -> None:  # type: ignore[misc]
        pass

load_env()

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

BASE_URL       = "https://www.lynalden.com"
ARCHIVE_URL    = f"{BASE_URL}/investment-strategy/"
INSIGHTS_FILE  = LOGS_DIR / "macrovoices_insights.json"
STATE_FILE     = LOGS_DIR / "lyn_alden_state.json"
SENTIMENT_FILE = LOGS_DIR / "news_sentiment.json"

MAX_HISTORY = 24   # keep up to 2 years of monthly newsletters
MAX_SUMMARY = 1800 # character limit for stored summary

_MONTH_NAMES = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]

# ── Theme + sentiment extraction (mirrors macrovoices_puller) ──────────────────

_THEME_PATTERNS: Dict[str, List[str]] = {
    "inflation":              ["inflation", "cpi", "ppi", "pce", "price pressure", "stagflation",
                               "inflationary", "disinflation"],
    "gold / precious metals": ["gold", "silver", "precious metal", "gld", "slv"],
    "oil / energy":           ["oil", "wti", "crude", "energy", "opec", "natural gas", "lng",
                               "strait of hormuz", "hormuz"],
    "rates / bonds":          ["yield", "treasury", "bond", "rate", "fed", "fomc", "quantitative",
                               "balance sheet", "qe", "money printing", "print"],
    "credit / spreads":       ["credit", "spread", "high yield", "investment grade", "private credit"],
    "dollar / fx":            ["dollar", "usd", "fx", "currency", "yuan", "yen", "euro", "dxy",
                               "reserve currency", "stablecoin"],
    "recession / growth":     ["recession", "gdp", "growth", "slowdown", "contraction", "ism",
                               "pmi", "employment", "jobs", "payroll", "stagflat"],
    "geopolitical":           ["war", "iran", "russia", "ukraine", "china", "tariff", "sanction",
                               "geopolitical", "conflict", "military", "strait"],
    "commodities":            ["copper", "wheat", "fertilizer", "corn", "soybean", "commodity",
                               "agriculture", "uranium", "lithium"],
    "equity markets":         ["stock", "equity", "s&p", "spy", "nasdaq", "market", "bear",
                               "bull", "valuation", "p/e", "cape"],
    "crypto":                 ["bitcoin", "crypto", "stablecoin", "defi", "btc"],
    "ai / tech":              ["artificial intelligence", "ai", "data center", "semiconductor",
                               "nvidia", "technology"],
}

_BEARISH_SIGNALS = [
    "stagflation", "recession", "bear market", "risk-off", "breakdown",
    "credit risk", "default", "collapse", "crash", "tightening",
    "war", "conflict", "escalation", "sanctions", "tariff", "shortage",
    "above baseline", "big print", "toxic combo",
]
_BULLISH_SIGNALS = [
    "bull market", "risk-on", "growth", "recovery", "breakout", "rally",
    "upside", "strong", "supercycle", "gradual print", "scarce assets",
    "profitable equities",
]

_INDICATOR_PATTERNS = [
    r"\b(?:MOVE|VIX|TED|DXY|USDX)\b",
    r"\b(?:CPI|PCE|PPI|NFP|PMI|ISM|GDP|JOLTS|NFIB|NAHB)\b",
    r"\b(?:WTI|Brent|Henry\s+Hub)\b",
    r"\b(?:Gold|Silver|GLD|SLV|GDX|GDXJ)\b",
    r"\b(?:S&P\s*500|NASDAQ|Russell\s*2000|SPY|QQQ|IWM)\b",
    r"\b(?:TLT|IEF|SHY|HYG|LQD|JNK|BIL|TIPS)\b",
    r"(?:2[Yy]|5[Yy]|10[Yy]|30[Yy])\s*[-/–]\s*(?:2[Yy]|5[Yy]|10[Yy]|30[Yy])\s+(?:yield\s+)?(?:spread|curve)?",
    r"\b(?:Fed\s+(?:balance\s+sheet|repo|swap\s+lines?|funds?\s+rate))\b",
    r"\b(?:treasury\s+yields?|10[- ]year\s+yield)\b",
    r"\b(?:Brent\s+crude|crude\s+oil)\b",
    r"\b(?:payrolls?|nonfarm\s+payrolls?)\b",
]


def _extract_themes(text: str) -> List[str]:
    lower = text.lower()
    return [theme for theme, kws in _THEME_PATTERNS.items() if any(kw in lower for kw in kws)]


def _score_sentiment(text: str) -> float:
    lower = text.lower()
    bear = sum(1 for s in _BEARISH_SIGNALS if s in lower)
    bull = sum(1 for s in _BULLISH_SIGNALS if s in lower)
    total = bear + bull
    if total == 0:
        return 0.0
    return round(max(-1.0, min(1.0, (bull - bear) / total)), 3)


def _extract_indicators(text: str) -> List[str]:
    found: List[str] = []
    seen: set[str] = set()
    for pat in _INDICATOR_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            val = m.group(0).strip()
            if val.lower() not in seen and len(val) > 1:
                found.append(val)
                seen.add(val.lower())
    return found[:30]


# ── HTML parsing ───────────────────────────────────────────────────────────────

class _TextExtractor(HTMLParser):
    """
    Extracts clean text from an HTML page, skipping nav/footer/script/style blocks.
    Preserves paragraph boundaries for better summary extraction.
    """
    _SKIP_TAGS = {"script", "style", "nav", "footer", "head", "noscript", "form", "button"}

    def __init__(self) -> None:
        super().__init__()
        self._parts: List[str] = []
        self._skip_depth = 0
        self._current_skip: Optional[str] = None

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        if tag in ("p", "h1", "h2", "h3", "li", "blockquote"):
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, d: str) -> None:
        if self._skip_depth == 0:
            cleaned = d.strip()
            if cleaned:
                self._parts.append(cleaned)

    def get_text(self) -> str:
        raw = " ".join(self._parts)
        raw = re.sub(r"\n\s*\n+", "\n\n", raw)
        return re.sub(r"[ \t]+", " ", raw).strip()


def _fetch_page(url: str) -> Optional[str]:
    """Fetch a URL and return raw HTML, or None on failure."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "MissionControl/1.0 (trading research; newsletter tracker)",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            if resp.status != 200:
                return None
            return resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        logger.debug("Fetch failed for %s: %s", url, exc)
        return None


def _extract_title(html: str) -> str:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
    if m:
        title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        return title
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        return re.sub(r"<[^>]+>", "", m.group(1)).strip().split("|")[0].strip()
    return "Lyn Alden Newsletter"


def _extract_meta_description(html: str) -> str:
    m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)', html, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return ""


def _build_summary(full_text: str) -> str:
    """
    Extract a focused summary from the newsletter body text.
    Prioritises the thesis update, current view, and investment implications sections.
    """
    section_headers = [
        "gradual print", "current view", "investment implication",
        "adding war", "toxic combo", "portfolio update", "flywheel",
        "final thought",
    ]
    lines = [l.strip() for l in full_text.split("\n") if l.strip()]
    summary_lines: List[str] = []
    capturing = False

    for line in lines:
        lower = line.lower()
        # Start capturing at key section headings
        if any(h in lower for h in section_headers):
            capturing = True
        if capturing and len(line) > 40:
            summary_lines.append(line)
        if len(" ".join(summary_lines)) > MAX_SUMMARY:
            break

    if not summary_lines:
        # Fallback: first 1800 chars of meaningful body text
        body_lines = [l for l in lines if len(l) > 60]
        joined = " ".join(body_lines)
        return joined[:MAX_SUMMARY]

    return " ".join(summary_lines)[:MAX_SUMMARY]


def _extract_portfolio_changes(full_text: str) -> List[str]:
    """
    Pull out M1 / portfolio changes from the 'Changes since the previous issue' section.
    Scopes extraction to the portfolio update block to avoid false positives in body text.
    Ticker symbols are 1–5 uppercase letters, not common English stop-words.
    """
    _STOP_WORDS = {
        "A", "AN", "THE", "AND", "OR", "BUT", "IN", "ON", "AT", "TO", "OF",
        "FOR", "BY", "WITH", "FROM", "IS", "ARE", "WAS", "WERE", "BE", "BEEN",
        "THEIR", "HOLD", "LOSS", "THEM", "THEY", "THIS", "THAT", "MORE",
    }

    # Narrow to the portfolio changes block if present
    scope = full_text
    block_m = re.search(
        r"Changes since the previous issue[:\s]*(.*?)(?:\n{3,}|$)",
        full_text,
        re.IGNORECASE | re.DOTALL,
    )
    if block_m:
        scope = block_m.group(1)[:600]

    changes: List[str] = []
    for m in re.finditer(
        r"\b(Buy|Sell|Trim|Add|Reduce|Remove|Initiate)\s+([A-Z]{2,5})\b",
        scope,
    ):
        ticker = m.group(2).upper()
        if ticker in _STOP_WORDS:
            continue
        change = f"{m.group(1).capitalize()} {ticker}"
        if change not in changes:
            changes.append(change)
    return changes[:10]


# ── URL construction ───────────────────────────────────────────────────────────

def _newsletter_url(year: int, month: int) -> str:
    """Build the expected Lyn Alden newsletter URL for the given year/month."""
    month_name = _MONTH_NAMES[month - 1]
    return f"{BASE_URL}/{month_name}-{year}-newsletter/"


def _candidate_urls() -> List[Tuple[str, int, int]]:
    """
    Return candidate newsletter URLs to try, newest first.
    Checks current month and the two prior months as a safety net.
    """
    now = datetime.now()
    candidates: List[Tuple[str, int, int]] = []
    for delta in range(3):
        dt = now - timedelta(days=30 * delta)
        candidates.append((_newsletter_url(dt.year, dt.month), dt.year, dt.month))
    return candidates


# ── State management ───────────────────────────────────────────────────────────

def _load_state() -> Dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"last_url": None, "last_pulled_at": None}


def _load_insights() -> List[Dict[str, Any]]:
    if INSIGHTS_FILE.exists():
        try:
            data = json.loads(INSIGHTS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


def _merge_into_news_sentiment(title: str, bias_score: float, themes: List[str]) -> None:
    existing: Dict[str, Any] = {}
    if SENTIMENT_FILE.exists():
        try:
            existing = json.loads(SENTIMENT_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    existing["lyn_alden_bias_score"]  = bias_score
    existing["lyn_alden_title"]       = title
    existing["lyn_alden_themes"]      = themes
    existing["lyn_alden_updated_at"]  = datetime.now().isoformat()
    atomic_write_json(SENTIMENT_FILE, existing)
    logger.info("Merged Lyn Alden sentiment (%.3f) into news_sentiment.json", bias_score)


# ── Main processing ────────────────────────────────────────────────────────────

def _process_newsletter(url: str, year: int, month: int) -> Optional[Dict[str, Any]]:
    """
    Fetch and parse a single newsletter URL.
    Returns a structured insight dict, or None if the page couldn't be fetched.
    """
    logger.info("Fetching Lyn Alden newsletter: %s", url)
    html = _fetch_page(url)
    if not html:
        logger.debug("Newsletter not available at %s", url)
        return None

    extractor = _TextExtractor()
    extractor.feed(html)
    full_text = extractor.get_text()

    title       = _extract_title(html)
    summary     = _build_summary(full_text)
    themes      = _extract_themes(full_text)
    score       = _score_sentiment(full_text)
    indicators  = _extract_indicators(full_text)
    port_chg    = _extract_portfolio_changes(full_text)
    date_str    = f"{year}-{month:02d}-01"

    # Try to get a more precise publish date from the page
    date_m = re.search(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{1,2}),?\s+(20\d{2})\b",
        full_text[:500],
        re.IGNORECASE,
    )
    if date_m:
        try:
            parsed = datetime.strptime(f"{date_m.group(1)} {date_m.group(2)} {date_m.group(3)}", "%B %d %Y")
            date_str = parsed.strftime("%Y-%m-%d")
        except ValueError:
            pass

    logger.info(
        "Parsed: title=%s | bias=%.3f | themes=%s | indicators=%d | portfolio_changes=%s",
        title[:60], score, themes[:4], len(indicators), port_chg,
    )

    return {
        "date":              date_str,
        "title":             title,
        "guest":             "Lyn Alden",
        "url":               url,
        "chartbook_url":     "",
        "source_type":       "newsletter",
        "pulled_at":         datetime.now().isoformat(),
        "themes":            themes,
        "bias_score":        score,
        "summary":           summary,
        "indicators_found":  indicators,
        "portfolio_changes": port_chg,
        "phase2_complete":   True,
    }


def _notify(entry: Dict[str, Any]) -> None:
    score  = entry["bias_score"]
    themes = entry.get("themes", [])
    inds   = entry.get("indicators_found", [])
    chgs   = entry.get("portfolio_changes", [])

    bias_emoji = "🔴" if score <= -0.3 else "🟢" if score >= 0.3 else "⚪"

    lines = [
        f"📰 Lyn Alden Newsletter: {entry['title']}",
        f"Macro bias: {bias_emoji} {score:+.2f}",
    ]
    if themes:
        lines.append("Themes: " + ", ".join(themes[:6]))
    if inds:
        lines.append("Indicators: " + ", ".join(inds[:8]))
    if chgs:
        lines.append("Portfolio changes: " + ", ".join(chgs))
    lines.append(f"\n{entry['url']}")

    try:
        notify_event(
            "lyn_alden_newsletter",
            subject=f"📰 Lyn Alden: {entry['title'][:70]}",
            body="\n".join(lines),
            urgent=False,
        )
    except Exception as exc:
        logger.warning("Notification failed: %s", exc)


# ── Public entry point ─────────────────────────────────────────────────────────

def run(force: bool = False, specific_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Run the Lyn Alden newsletter puller.

    Args:
        force: Re-process even if we've already seen this URL.
        specific_url: Skip URL detection and process this URL directly.

    Returns a summary dict.
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("=== Lyn Alden Newsletter Puller ===")

    state    = _load_state()
    insights = _load_insights()
    last_url = state.get("last_url")

    # Build the list of URLs to try
    if specific_url:
        # Infer year/month from URL or default to now
        m = re.search(r"(\w+)-(\d{4})-newsletter", specific_url)
        if m:
            month_name = m.group(1).lower()
            year = int(m.group(2))
            month = _MONTH_NAMES.index(month_name) + 1 if month_name in _MONTH_NAMES else datetime.now().month
        else:
            year, month = datetime.now().year, datetime.now().month
        candidates = [(specific_url, year, month)]
    else:
        candidates = _candidate_urls()

    entry: Optional[Dict[str, Any]] = None

    for url, year, month in candidates:
        if not force and url == last_url:
            logger.info("Already processed: %s — skipping (use --force to reprocess)", url)
            return {"status": "already_current", "url": url}

        result = _process_newsletter(url, year, month)
        if result:
            entry = result
            break

    if not entry:
        logger.info("No new newsletter found (checked %d URL(s))", len(candidates))
        return {"status": "not_yet_published", "checked_urls": [u for u, _, _ in candidates]}

    # Prepend to shared insights store
    # Avoid duplicates by URL
    existing_urls = {e.get("url") for e in insights}
    if entry["url"] in existing_urls and not force:
        logger.info("Entry for %s already exists in insights — skipping write", entry["url"])
        return {"status": "already_in_insights", "url": entry["url"]}

    insights = [entry] + [e for e in insights if e.get("url") != entry["url"]]
    insights = insights[:MAX_HISTORY + 52]  # cap combined store
    atomic_write_json(INSIGHTS_FILE, insights)
    logger.info("Saved Lyn Alden newsletter to macrovoices_insights.json")

    # Update state
    atomic_write_json(STATE_FILE, {
        "last_url":        entry["url"],
        "last_pulled_at":  datetime.now().isoformat(),
        "last_title":      entry["title"],
    })

    # Merge sentiment
    _merge_into_news_sentiment(entry["title"], entry["bias_score"], entry["themes"])

    # Notify
    _notify(entry)

    return {
        "status":          "ok",
        "title":           entry["title"],
        "url":             entry["url"],
        "bias_score":      entry["bias_score"],
        "themes":          entry["themes"],
        "indicators":      entry["indicators_found"],
        "portfolio_chg":   entry.get("portfolio_changes", []),
    }


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Lyn Alden monthly newsletter puller")
    parser.add_argument("--force",   action="store_true", help="Re-process even if URL already seen")
    parser.add_argument("--dry-run", action="store_true", help="Print extracted data, no writes")
    parser.add_argument("--url",     metavar="URL",       help="Process a specific newsletter URL")
    args = parser.parse_args()

    if args.dry_run:
        candidates = [args.url] if args.url else [u for u, _, _ in _candidate_urls()[:2]]
        for url in candidates:
            m = re.search(r"(\w+)-(\d{4})-newsletter", url)
            year  = int(m.group(2)) if m else datetime.now().year
            month = (_MONTH_NAMES.index(m.group(1).lower()) + 1) if m and m.group(1).lower() in _MONTH_NAMES else datetime.now().month
            result = _process_newsletter(url, year, month)
            if result:
                print(f"\nTitle:      {result['title']}")
                print(f"Date:       {result['date']}")
                print(f"Bias:       {result['bias_score']:+.3f}")
                print(f"Themes:     {', '.join(result['themes'])}")
                print(f"Indicators: {', '.join(result['indicators_found'][:10])}")
                print(f"Portfolio:  {', '.join(result.get('portfolio_changes', []))}")
                print(f"\nSummary:\n{result['summary'][:600]}")
                break
            else:
                print(f"Not available: {url}")
        sys.exit(0)

    result = run(force=args.force, specific_url=args.url or None)
    print(json.dumps(result, indent=2))
