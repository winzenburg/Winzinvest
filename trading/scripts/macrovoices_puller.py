#!/usr/bin/env python3
"""
MacroVoices Weekly Puller
https://www.macrovoices.com

Two-phase operation:
  Phase 1 (always active — no credentials required):
    • Fetches the public PodBean RSS feed
    • Extracts episode title, guest, date, discussion topics from bullet points
    • Scores macro sentiment per episode (inflation/gold/oil/rates/credit)
    • Stores structured summaries in logs/macrovoices_insights.json
    • Merges macro themes into news_sentiment.json

  Phase 2 (activates when MACROVOICES_EMAIL + MACROVOICES_PASSWORD are in .env):
    • Logs into macrovoices.com with a requests.Session
    • Downloads the transcript PDF for the most recent episode
    • Downloads the chart book PDF for the most recent episode
    • Extracts chart/indicator titles from both PDFs
    • Appends newly-discovered indicators to logs/macrovoices_indicators.json
      (these can be manually promoted to regime_monitor.py checks)
    • Sends a Telegram digest with key macro themes + new indicators found

Scheduled: Fridays at 9:00 AM MT (11:00 AM ET) via scheduler.py
           Episodes are typically published Thursday evening.

NOTE: Ensure MACROVOICES_EMAIL and MACROVOICES_PASSWORD are in the .env file
      for Phase 2. Credentials are never logged or echoed.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from env_loader import load_env
from atomic_io import atomic_write_json
from paths import TRADING_DIR, LOGS_DIR

try:
    from notifications import notify_event
except ImportError:
    def notify_event(event: str, **kwargs: Any) -> None:  # type: ignore[misc]
        pass

load_env()

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── File paths ─────────────────────────────────────────────────────────────────
RSS_URL       = "https://feed.podbean.com/macrovoices/feed.xml"
MV_BASE       = "https://www.macrovoices.com"
LOGIN_URL     = f"{MV_BASE}/member-login"
INSIGHTS_FILE = LOGS_DIR / "macrovoices_insights.json"
INDICATORS_FILE = LOGS_DIR / "macrovoices_indicators.json"
STATE_FILE    = LOGS_DIR / "macrovoices_state.json"
SENTIMENT_FILE = LOGS_DIR / "news_sentiment.json"
PDF_CACHE_DIR = LOGS_DIR / "macrovoices_pdfs"

MAX_HISTORY = 52  # keep ~1 year of weekly episodes

# ── Macro theme extraction ─────────────────────────────────────────────────────

_THEME_PATTERNS: Dict[str, List[str]] = {
    "inflation":          ["inflation", "cpi", "ppi", "pce", "price pressure", "stagflation"],
    "gold / precious metals": ["gold", "silver", "precious metal", "gld", "slv"],
    "oil / energy":       ["oil", "wti", "crude", "energy", "opec", "natural gas", "lng"],
    "rates / bonds":      ["yield", "treasury", "bond", "rate", "fed", "fomc", "quantitative"],
    "credit / spreads":   ["credit", "spread", "high yield", "investment grade", "hy oas",
                           "private credit", "corporate bond"],
    "dollar / fx":        ["dollar", "usd", "fx", "currency", "yuan", "yen", "euro", "dxy"],
    "recession / growth": ["recession", "gdp", "growth", "slowdown", "contraction", "ism",
                           "pmi", "nfci"],
    "geopolitical":       ["war", "iran", "russia", "ukraine", "china", "tariff", "sanction",
                           "geopolitical", "conflict"],
    "commodities":        ["copper", "wheat", "fertilizer", "corn", "soybean", "commodity",
                           "agriculture", "uranium", "lithium"],
    "equity markets":     ["stock", "equity", "s&p", "spy", "nasdaq", "qqq", "market crash",
                           "bear market", "bull market"],
    "crypto":             ["bitcoin", "crypto", "stablecoin", "defi"],
    "ai / tech":          ["artificial intelligence", "ai", "data center", "semiconductor",
                           "nvidia", "technology"],
}

_BEARISH_SIGNALS = [
    "more inflation", "stagflation", "recession", "bear market", "risk-off",
    "breakdown", "credit risk", "default", "collapse", "crash", "tightening",
    "war", "conflict", "escalation", "sanctions", "tariff",
]
_BULLISH_SIGNALS = [
    "bull market", "risk-on", "growth", "recovery", "breakout", "rotation",
    "rally", "upside", "opportunity", "strong", "supercycle",
]


def _extract_themes(text: str) -> List[str]:
    lower = text.lower()
    found = []
    for theme, keywords in _THEME_PATTERNS.items():
        if any(kw in lower for kw in keywords):
            found.append(theme)
    return found


def _score_sentiment(text: str) -> float:
    lower = text.lower()
    bear = sum(1 for s in _BEARISH_SIGNALS if s in lower)
    bull = sum(1 for s in _BULLISH_SIGNALS if s in lower)
    total = bear + bull
    if total == 0:
        return 0.0
    return round(max(-1.0, min(1.0, (bull - bear) / total)), 3)


# ── HTML stripping ─────────────────────────────────────────────────────────────

class _Stripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: List[str] = []

    def handle_data(self, d: str) -> None:
        self._parts.append(d)

    def get_data(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self._parts)).strip()


def _strip_html(html: str) -> str:
    s = _Stripper()
    s.feed(html)
    return s.get_data()


# ── Bullet-point topic extraction ──────────────────────────────────────────────

def _extract_bullet_topics(page_html: str) -> List[str]:
    """
    MacroVoices episode pages list discussion bullet points in <li> tags.
    Pull them out as clean strings.
    """
    topics: List[str] = []
    for m in re.finditer(r"<li[^>]*>(.*?)</li>", page_html, re.IGNORECASE | re.DOTALL):
        item = _strip_html(m.group(1)).strip()
        if 10 < len(item) < 120 and not item.startswith("http"):
            topics.append(item)
    return topics[:15]


def _extract_guest(title: str) -> str:
    """Extract guest name from 'MacroVoices #NNN GuestName: Topic' format."""
    m = re.search(r"MacroVoices #\d+\s+(.+?):", title)
    return m.group(1).strip() if m else ""


# ── RSS parsing ────────────────────────────────────────────────────────────────

_NS_CONTENT = {"content": "http://purl.org/rss/1.0/modules/content/"}


def _fetch_rss() -> List[Dict[str, Any]]:
    try:
        req = urllib.request.Request(
            RSS_URL,
            headers={"User-Agent": "MissionControl/1.0 (trading system; rss reader)"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        logger.error("RSS fetch failed: %s", exc)
        return []

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        logger.error("RSS parse error: %s", exc)
        return []

    episodes: List[Dict[str, Any]] = []
    for item in root.findall(".//item"):
        title   = item.findtext("title", "").strip()
        link    = item.findtext("link", "").strip()
        pub_raw = item.findtext("pubDate", "").strip()
        desc_el = item.find("description")
        desc_html = desc_el.text if desc_el is not None else ""
        encoded = item.find("content:encoded", _NS_CONTENT)
        full_html = encoded.text if encoded is not None else desc_html

        pub_dt: Optional[datetime] = None
        if pub_raw:
            try:
                from email.utils import parsedate_to_datetime
                pub_dt = parsedate_to_datetime(pub_raw)
            except Exception:
                pass

        clean_desc = _strip_html(full_html or "")
        # Extract the chartbook bit.ly URL from description
        chartbook_url = None
        for m in re.finditer(r"(https?://bit\.ly/\S+)", clean_desc):
            chartbook_url = m.group(1)  # last one is usually the chartbook
            break

        episodes.append({
            "title":         title,
            "guest":         _extract_guest(title),
            "link":          link,
            "pub_dt":        pub_dt,
            "pub_raw":       pub_raw,
            "clean_desc":    clean_desc[:600],
            "chartbook_url": chartbook_url,
        })

    return episodes


# ── PDF text extraction (pdfplumber) ──────────────────────────────────────────

def _extract_pdf_text(pdf_path: Path) -> str:
    """Extract all text from a PDF using pdfplumber (best for chart book PDFs)."""
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber not installed — PDF extraction unavailable. Run: pip install pdfplumber")
        return ""
    try:
        text_parts: List[str] = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
        return "\n".join(text_parts)
    except Exception as exc:
        logger.warning("PDF extraction failed for %s: %s", pdf_path.name, exc)
        return ""


def _extract_indicators_from_pdf(text: str) -> List[str]:
    """
    From chart book PDF text, extract chart/indicator titles.
    Looks for lines that look like indicator names (capitalized, short, often with %).
    """
    indicator_patterns = [
        # yield curve patterns
        r"(?:2[Yy]|5[Yy]|10[Yy]|30[Yy])\s*[-/–]\s*(?:2[Yy]|5[Yy]|10[Yy]|30[Yy])\s+(?:yield\s+)?(?:spread|curve)?",
        r"(?:US|Treasury)\s+\d+[Ys]\s+(?:yield|note|bond)",
        # credit spreads
        r"(?:HY|IG|CDX|CDS)\s+(?:OAS|spread|index)",
        # macro indicators
        r"\b(?:NFCI|ISM|PMI|CPI|PCE|PPI|NFP|JOLTS|GDP|NFIB|NAHB|VIX|MOVE|TED|OIS|LIBOR)\b",
        # commodity patterns
        r"\b(?:WTI|Brent|Henry\s+Hub|LME\s+Copper|Wheat|Corn|Soybean|DXY|USDX)\b",
        # gold/precious
        r"\b(?:Gold|Silver|Platinum|Palladium|GLD|SLV|GDX|GDXJ)\b",
        # equity indices
        r"\b(?:S&P\s*500|NASDAQ|Russell\s*2000|Dow\s+Jones|MSCI|FTSE|Nikkei)\b",
        # credit/rate ETFs
        r"\b(?:TLT|IEF|SHY|HYG|LQD|EMB|JNK|BIL)\b",
        # energy
        r"\b(?:XLE|XOP|USO|UNG|WTIC|Brent)\b",
    ]
    found: List[str] = []
    for pat in indicator_patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            candidate = m.group(0).strip()
            if candidate not in found and len(candidate) > 2:
                found.append(candidate)
    return found[:40]


# ── MacroVoices authenticated session ─────────────────────────────────────────

def _get_credentials() -> Tuple[Optional[str], Optional[str]]:
    email    = os.environ.get("MACROVOICES_EMAIL")
    password = os.environ.get("MACROVOICES_PASSWORD")
    return email or None, password or None


def _login_session() -> Optional[Any]:
    """
    Create an authenticated requests.Session for macrovoices.com.
    Returns the session if login succeeds, None otherwise.
    Requires: pip install requests
    """
    email, password = _get_credentials()
    if not email or not password:
        return None

    try:
        import requests
    except ImportError:
        logger.warning("requests not installed — authenticated access unavailable. Run: pip install requests")
        return None

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Referer": MV_BASE,
    })

    try:
        # Step 1: GET login page to capture Joomla CSRF token
        r = session.get(LOGIN_URL, timeout=15)
        r.raise_for_status()

        # Extract Joomla form token (hidden input with value="1")
        token_match = re.search(
            r'<input[^>]+name="([0-9a-f]{32})"[^>]+value="1"', r.text
        )
        if not token_match:
            # Try alternate pattern
            token_match = re.search(
                r'"([0-9a-f]{32})"\s*:\s*1', r.text
            )
        token = token_match.group(1) if token_match else ""

        # Step 2: POST login
        payload = {
            "username":    email,
            "password":    password,
            "option":      "com_users",
            "task":        "user.login",
            "return":      "aW5kZXgucGhw",  # base64("index.php")
        }
        if token:
            payload[token] = "1"

        r2 = session.post(LOGIN_URL, data=payload, timeout=15, allow_redirects=True)
        r2.raise_for_status()

        # Check if login succeeded (look for logout link or member menu)
        if "logout" in r2.text.lower() or "my profile" in r2.text.lower():
            logger.info("MacroVoices: login successful as %s", email)
            return session
        else:
            logger.warning("MacroVoices: login POST completed but session appears unauthenticated")
            return None

    except Exception as exc:
        logger.warning("MacroVoices login failed: %s", exc)
        return None


def _download_pdf(session: Any, url: str, dest_path: Path) -> bool:
    """Download a PDF file using an authenticated session."""
    try:
        r = session.get(url, timeout=30, stream=True)
        r.raise_for_status()
        content_type = r.headers.get("content-type", "")
        if "pdf" not in content_type and "octet" not in content_type:
            logger.warning("URL did not return PDF (got %s): %s", content_type[:50], url)
            return False
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as fh:
            for chunk in r.iter_content(chunk_size=65536):
                fh.write(chunk)
        logger.info("Downloaded PDF: %s (%d KB)", dest_path.name, dest_path.stat().st_size // 1024)
        return True
    except Exception as exc:
        logger.warning("PDF download failed (%s): %s", url, exc)
        return False


def _resolve_mv_transcript_url(session: Any, episode_link: str) -> Optional[str]:
    """
    Visit the MacroVoices episode page (authenticated) and scrape the
    transcript download link.
    """
    try:
        r = session.get(episode_link, timeout=15)
        r.raise_for_status()
        # Look for transcript download link pattern
        for pat in [
            r'href="(/guest-content/list-guest-transcripts/[^"]+/file)"',
            r'href="(/[^"]*transcript[^"]*\.pdf[^"]*)"',
        ]:
            m = re.search(pat, r.text, re.IGNORECASE)
            if m:
                path = m.group(1)
                return f"{MV_BASE}{path}" if path.startswith("/") else path
    except Exception as exc:
        logger.warning("Could not resolve transcript URL for %s: %s", episode_link, exc)
    return None


def _resolve_mv_chartbook_url(session: Any, episode_link: str) -> Optional[str]:
    """Scrape chart book download URL from an authenticated episode page."""
    try:
        r = session.get(episode_link, timeout=15)
        r.raise_for_status()
        for pat in [
            r'href="(/guest-content/list-guest-publications/[^"]+/file)"',
            r'href="(/[^"]*chart[^"]*\.pdf[^"]*)"',
            r'href="(/[^"]*book[^"]*\.pdf[^"]*)"',
        ]:
            m = re.search(pat, r.text, re.IGNORECASE)
            if m:
                path = m.group(1)
                return f"{MV_BASE}{path}" if path.startswith("/") else path
    except Exception as exc:
        logger.warning("Could not resolve chart book URL for %s: %s", episode_link, exc)
    return None


# ── Indicator registry ─────────────────────────────────────────────────────────

def _load_indicators() -> Dict[str, Any]:
    if INDICATORS_FILE.exists():
        try:
            return json.loads(INDICATORS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"indicators": [], "last_updated": None}


def _merge_new_indicators(new: List[str]) -> int:
    """Add newly-discovered indicators to the registry. Returns count of truly new ones."""
    reg = _load_indicators()
    existing = {i["name"].lower() for i in reg.get("indicators", [])}
    added = 0
    for name in new:
        if name.lower() not in existing:
            reg.setdefault("indicators", []).append({
                "name":         name,
                "first_seen":   datetime.now().strftime("%Y-%m-%d"),
                "source":       "macrovoices_chartbook",
                "implemented":  False,  # set to True once added to regime_monitor.py
            })
            existing.add(name.lower())
            added += 1
    if added:
        reg["last_updated"] = datetime.now().isoformat()
        atomic_write_json(INDICATORS_FILE, reg)
        logger.info("Added %d new indicator(s) to macrovoices_indicators.json", added)
    return added


# ── State and insights management ─────────────────────────────────────────────

def _load_state() -> Dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"last_pulled_link": None, "last_pulled_at": None}


def _load_insights() -> List[Dict[str, Any]]:
    if INSIGHTS_FILE.exists():
        try:
            data = json.loads(INSIGHTS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


def _merge_into_news_sentiment(
    episode_title: str, bias_score: float, themes: List[str]
) -> None:
    """Blend MacroVoices weekly sentiment into news_sentiment.json."""
    existing: Dict[str, Any] = {}
    if SENTIMENT_FILE.exists():
        try:
            existing = json.loads(SENTIMENT_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    existing["macrovoices_bias_score"]  = bias_score
    existing["macrovoices_title"]       = episode_title
    existing["macrovoices_themes"]      = themes
    existing["macrovoices_updated_at"]  = datetime.now().isoformat()

    atomic_write_json(SENTIMENT_FILE, existing)
    logger.info("Merged MacroVoices sentiment (%.3f) into news_sentiment.json", bias_score)


# ── Main ───────────────────────────────────────────────────────────────────────

def run(force: bool = False) -> Dict[str, Any]:
    """
    Run the MacroVoices puller.
    Phase 1 (no credentials): RSS metadata extraction.
    Phase 2 (credentials available): transcript + chart book download + PDF parsing.

    Returns a summary dict.
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("=== MacroVoices Puller ===")

    state    = _load_state()
    insights = _load_insights()
    episodes = _fetch_rss()

    if not episodes:
        return {"status": "no_feed", "new_episodes": 0}

    last_link  = state.get("last_pulled_link")
    new_entries: List[Dict[str, Any]] = []

    for ep in episodes:
        link = ep["link"]
        if not force and link == last_link:
            break  # already processed this and everything older

        date_str = ep["pub_dt"].strftime("%Y-%m-%d") if ep["pub_dt"] else datetime.now().strftime("%Y-%m-%d")
        themes   = _extract_themes(ep["title"] + " " + ep["clean_desc"])
        score    = _score_sentiment(ep["title"] + " " + ep["clean_desc"])

        entry: Dict[str, Any] = {
            "date":           date_str,
            "title":          ep["title"],
            "guest":          ep["guest"],
            "url":            link,
            "chartbook_url":  ep["chartbook_url"],
            "pulled_at":      datetime.now().isoformat(),
            "themes":         themes,
            "bias_score":     score,
            "summary":        ep["clean_desc"],
            "indicators_found": [],
            "phase2_complete":  False,
        }

        new_entries.append(entry)
        logger.info(
            "New episode: %s | guest=%s | bias=%.3f | themes=%s",
            ep["title"][:60], ep["guest"], score, themes[:4],
        )

    if not new_entries:
        logger.info("No new episodes since last pull (last: %s)", last_link)
        return {"status": "no_new_episodes", "new_episodes": 0}

    # ── Phase 2: Authenticated PDF download and extraction ────────────────────
    email, password = _get_credentials()
    phase2_available = bool(email and password)
    phase2_results: Dict[str, Any] = {}
    new_indicators_total = 0

    if phase2_available:
        logger.info("Phase 2: credentials found — attempting PDF downloads")
        session = _login_session()
        if session:
            # Fetch the authenticated homepage once — transcript and chart book
            # download links are directly embedded in the episode listing.
            homepage_html = ""
            try:
                r = session.get(MV_BASE, timeout=15)
                r.raise_for_status()
                homepage_html = r.text
                logger.info("Homepage fetched (%d chars)", len(homepage_html))
            except Exception as exc:
                logger.warning("Could not fetch homepage: %s", exc)

            def _first_match(html: str, *patterns: str) -> Optional[str]:
                for pat in patterns:
                    m = re.search(pat, html)
                    if m:
                        path = m.group(1)
                        return f"{MV_BASE}{path}" if path.startswith("/") else path
                return None

            # ── Transcript ────────────────────────────────────────────────────
            transcript_url = _first_match(
                homepage_html,
                r'href="(/guest-content/list-guest-transcripts/[^"]+/file)"',
                r'href="(https?://www\.macrovoices\.com/guest-content/list-guest-transcripts/[^"]+)"',
            )
            if not transcript_url:
                # Fallback: scrape the episode page itself
                mv_ep_path = _first_match(
                    homepage_html,
                    r'href="(/\d+-macrovoices[^"]+)"',
                    r'href="(https?://www\.macrovoices\.com/\d+-macrovoices[^"]+)"',
                )
                if mv_ep_path:
                    transcript_url = _resolve_mv_transcript_url(session, mv_ep_path)

            if transcript_url:
                dest = PDF_CACHE_DIR / f"transcript_{new_entries[0]['date']}.pdf"
                if _download_pdf(session, transcript_url, dest):
                    text = _extract_pdf_text(dest)
                    if text:
                        inds = _extract_indicators_from_pdf(text)
                        n = _merge_new_indicators(inds)
                        new_entries[0]["indicators_found"].extend(inds)
                        new_indicators_total += n
                        phase2_results["transcript"] = {
                            "downloaded": True, "indicators": inds[:10]
                        }
                        logger.info("Transcript: %d indicator(s) (%d new)", len(inds), n)
            else:
                logger.warning("Could not resolve transcript URL — skipping transcript")

            # ── Chart book ────────────────────────────────────────────────────
            chartbook_url = _first_match(
                homepage_html,
                r'href="(/guest-content/list-guest-publications/[^"]+/file)"',
                r'href="(https?://www\.macrovoices\.com/guest-content/list-guest-publications/[^"]+)"',
            )
            if not chartbook_url:
                mv_ep_path = _first_match(
                    homepage_html,
                    r'href="(/\d+-macrovoices[^"]+)"',
                    r'href="(https?://www\.macrovoices\.com/\d+-macrovoices[^"]+)"',
                )
                if mv_ep_path:
                    chartbook_url = _resolve_mv_chartbook_url(session, mv_ep_path)

            if chartbook_url:
                dest = PDF_CACHE_DIR / f"chartbook_{new_entries[0]['date']}.pdf"
                if _download_pdf(session, chartbook_url, dest):
                    text = _extract_pdf_text(dest)
                    if text:
                        inds = _extract_indicators_from_pdf(text)
                        n = _merge_new_indicators(inds)
                        new_entries[0]["indicators_found"].extend(inds)
                        new_indicators_total += n
                        phase2_results["chartbook"] = {
                            "downloaded": True, "indicators": inds[:20]
                        }
                        logger.info(
                            "Chart book: %d indicator(s) (%d new)", len(inds), n
                        )
            else:
                logger.warning("Could not resolve chart book URL — skipping chart book")

            if phase2_results:
                new_entries[0]["phase2_complete"] = True
        else:
            logger.warning("Phase 2: login failed — only Phase 1 data will be saved")
    else:
        logger.info("Phase 2 inactive — set MACROVOICES_EMAIL + MACROVOICES_PASSWORD in .env to enable")

    # ── Save insights ─────────────────────────────────────────────────────────
    insights = new_entries + insights
    insights = insights[:MAX_HISTORY]
    atomic_write_json(INSIGHTS_FILE, insights)
    logger.info("Saved %d new episode(s) to macrovoices_insights.json", len(new_entries))

    # Persist state
    atomic_write_json(STATE_FILE, {
        "last_pulled_link": episodes[0]["link"],
        "last_pulled_at": datetime.now().isoformat(),
    })

    # Merge into news sentiment
    latest = new_entries[0]
    _merge_into_news_sentiment(latest["title"], latest["bias_score"], latest["themes"])

    # Notify
    _notify(latest, len(new_entries), new_indicators_total, phase2_available)

    return {
        "status":                "ok",
        "new_episodes":          len(new_entries),
        "latest_title":          latest["title"],
        "latest_guest":          latest["guest"],
        "latest_bias":           latest["bias_score"],
        "latest_themes":         latest["themes"],
        "phase2_active":         phase2_available,
        "new_indicators_found":  new_indicators_total,
        "phase2_details":        phase2_results,
    }


def _notify(
    entry: Dict[str, Any],
    count: int,
    new_indicators: int,
    phase2: bool,
) -> None:
    score  = entry["bias_score"]
    themes = entry.get("themes", [])
    inds   = entry.get("indicators_found", [])

    bias_emoji = "🔴" if score <= -0.3 else "🟢" if score >= 0.3 else "⚪"

    lines = [
        f"📻 MacroVoices: {entry['title']}",
        f"Guest: {entry['guest']}",
        f"Macro bias: {bias_emoji} {score:+.2f}",
    ]
    if themes:
        lines.append("Themes: " + ", ".join(themes[:6]))
    if inds:
        lines.append(f"New indicators found ({len(inds)}): " + ", ".join(inds[:8]))
    if not phase2:
        lines.append("\n💡 Add MACROVOICES_EMAIL + MACROVOICES_PASSWORD to .env for transcript/chartbook access")
    lines.append(f"\n{entry['url']}")

    try:
        notify_event(
            "macrovoices_recap",
            subject=f"📻 MacroVoices: {entry['guest']} — {entry['title'][:60]}",
            body="\n".join(lines),
            urgent=False,
        )
    except Exception as exc:
        logger.warning("Notification failed: %s", exc)


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MacroVoices RSS + PDF puller")
    parser.add_argument("--force", action="store_true", help="Re-process most recent episode")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be extracted, no writes")
    parser.add_argument("--list-indicators", action="store_true", help="Show discovered indicators registry")
    args = parser.parse_args()

    if args.list_indicators:
        reg = _load_indicators()
        inds = reg.get("indicators", [])
        print(f"Discovered indicators ({len(inds)} total):")
        for ind in inds:
            impl = "✅" if ind.get("implemented") else "  "
            print(f"  {impl} {ind['name']} (first seen {ind['first_seen']})")
        sys.exit(0)

    if args.dry_run:
        episodes = _fetch_rss()
        if episodes:
            ep = episodes[0]
            title = ep["title"]
            desc  = ep["clean_desc"]
            themes = _extract_themes(title + " " + desc)
            score  = _score_sentiment(title + " " + desc)
            print(f"Title:   {title}")
            print(f"Guest:   {_extract_guest(title)}")
            print(f"Date:    {ep['pub_raw']}")
            print(f"Themes:  {themes}")
            print(f"Score:   {score:+.3f}")
            email, _ = _get_credentials()
            print(f"Phase 2: {'ACTIVE' if email else 'INACTIVE (no credentials)'}")
            print(f"\nDescription: {desc[:400]}")
        sys.exit(0)

    result = run(force=args.force)
    print(json.dumps(result, indent=2))
