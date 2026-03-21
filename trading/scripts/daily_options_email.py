#!/usr/bin/env python3
"""
Winzinvest Daily Positions Email
==================================
Unified EOD report: stock positions (sorted by return) + all options positions.
No account overview — just the positions worth watching.

Runs daily at 2:00 PM MT via scheduler (job_pre_close).

Usage:
  python3 daily_options_email.py           # generate + send
  python3 daily_options_email.py --preview  # write HTML to /tmp, skip send
"""

import json
import logging
import os
import sys
from datetime import datetime, date
from pathlib import Path
from typing import Any, Optional

SCRIPTS_DIR = Path(__file__).resolve().parent
TRADING_DIR = SCRIPTS_DIR.parent
LOGS_DIR    = TRADING_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)
sys.path.insert(0, str(SCRIPTS_DIR))

_env_path = TRADING_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGS_DIR / "daily_options_email.log"),
    ],
)
log = logging.getLogger(__name__)

IB_HOST      = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT      = int(os.getenv("IB_PORT", "4001"))
IB_CLIENT_ID = 197  # 107 is execute_mean_reversion — use 197 to avoid concurrent Error 326

EXTRA_RECIPIENTS: list[str] = []

PENDING_FILE = TRADING_DIR / "config" / "pending_trades.json"


# ── Stop price loader ──────────────────────────────────────────────────────────

def _load_stop_prices() -> dict[str, float]:
    """Return {SYMBOL: stop_price} by reading pending_trades.json."""
    if not PENDING_FILE.exists():
        return {}
    try:
        data = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

    stops: dict[str, float] = {}
    pending = data.get("pending", [])
    for trade in pending:
        if trade.get("status") not in ("pending", None):
            continue
        for cond in trade.get("trigger", {}).get("conditions", []):
            if cond.get("type") == "price_below":
                sym = str(cond.get("symbol", "")).upper()
                price = cond.get("price")
                if sym and price is not None:
                    stops[sym] = float(price)
    return stops


# ── Data fetching ──────────────────────────────────────────────────────────────

def _fetch_stock_positions(ib: Any) -> list[dict]:
    rows: list[dict] = []
    for pos in ib.positions():
        c = pos.contract
        if c.secType != "STK" or pos.position == 0:
            continue
        rows.append({
            "symbol":   c.symbol,
            "qty":      int(pos.position),
            "avg_cost": float(pos.avgCost),
        })
    return rows


def _fetch_option_positions(ib: Any) -> list[dict]:
    rows: list[dict] = []
    for pos in ib.positions():
        c = pos.contract
        if c.secType != "OPT" or pos.position == 0:
            continue
        rows.append({
            "symbol":   c.symbol,
            "strike":   c.strike,
            "right":    c.right,
            "expiry":   c.lastTradeDateOrContractMonth,
            "qty":      int(pos.position),
            "avg_cost": float(pos.avgCost),
            "mult":     int(c.multiplier) if c.multiplier else 100,
        })
    return rows


def _fetch_prices(symbols: list[str]) -> dict[str, float]:
    import yfinance as yf
    prices: dict[str, float] = {}
    for sym in symbols:
        try:
            h = yf.download(sym, period="2d", progress=False, auto_adjust=True)
            if h.empty:
                continue
            cl = h["Close"]
            if hasattr(cl, "columns"):
                cl = cl.iloc[:, 0]
            prices[sym] = round(float(cl.iloc[-1]), 2)
        except Exception:
            pass
    return prices


# ── Enrichment ─────────────────────────────────────────────────────────────────

def _enrich_stocks(stocks: list[dict], prices: dict[str, float],
                   stops: dict[str, float]) -> list[dict]:
    enriched: list[dict] = []
    for s in stocks:
        sym       = s["symbol"]
        spot      = prices.get(sym, 0.0)
        avg_cost  = s["avg_cost"]
        qty       = s["qty"]
        notional  = round(spot * abs(qty), 2) if spot else 0.0
        unreal_pnl = round((spot - avg_cost) * qty, 2) if spot else 0.0
        ret_pct    = round((spot - avg_cost) / avg_cost * 100, 2) if avg_cost else 0.0

        stop_price  = stops.get(sym.upper())
        stop_dist   = round(spot - stop_price, 2) if (spot and stop_price) else None
        stop_dist_pct = round((spot - stop_price) / spot * 100, 2) if (spot and stop_price) else None

        enriched.append({
            **s,
            "spot": spot,
            "notional": notional,
            "unreal_pnl": unreal_pnl,
            "ret_pct": ret_pct,
            "stop_price": stop_price,
            "stop_dist": stop_dist,
            "stop_dist_pct": stop_dist_pct,
        })
    # Sort: winners first (by return % descending), shorts last
    return sorted(enriched, key=lambda x: x["ret_pct"], reverse=True)


def _enrich_options(opts: list[dict], prices: dict[str, float]) -> list[dict]:
    today = date.today()
    enriched: list[dict] = []
    for o in opts:
        exp_date  = datetime.strptime(o["expiry"], "%Y%m%d").date()
        dte       = (exp_date - today).days
        spot      = prices.get(o["symbol"], 0.0)
        strike    = o["strike"]
        qty       = o["qty"]

        if spot > 0:
            otm_pct = ((strike - spot) / spot * 100) if o["right"] == "C" \
                      else ((spot - strike) / spot * 100)
            moneyness = f"OTM {otm_pct:.1f}%" if otm_pct >= 0 else f"ITM {abs(otm_pct):.1f}%"
        else:
            otm_pct   = None
            moneyness = "N/A"

        premium_per = abs(o["avg_cost"])
        total_prem  = premium_per * abs(qty)

        if o["right"] == "C" and qty < 0:
            otype = "Covered Call"
        elif o["right"] == "P" and qty < 0:
            otype = "CSP"
        elif o["right"] == "C" and qty > 0:
            otype = "Long Call"
        else:
            otype = "Long Put"

        assign_risk = abs(qty) * strike * 100 if (o["right"] == "P" and qty < 0) else None

        # Compliance flags
        flags: list[str] = []
        if qty < 0:
            if otm_pct is not None and otm_pct < 0:
                flags.append(f"ITM {abs(otm_pct):.1f}%")
            elif otm_pct is not None and otm_pct < 2:
                flags.append(f"Only {otm_pct:.1f}% OTM")
            if dte <= 7:
                flags.append(f"DTE {dte}")

        enriched.append({
            "symbol": o["symbol"], "type": otype, "right": o["right"],
            "strike": strike, "expiry_str": exp_date.strftime("%b %d"),
            "dte": dte, "qty": qty, "spot": spot, "moneyness": moneyness,
            "otm_pct": otm_pct, "prem_per": premium_per,
            "total_prem": total_prem, "assign_risk": assign_risk,
            "flags": flags,
        })
    return enriched


# ── Market summary ─────────────────────────────────────────────────────────────

def _fetch_index_returns() -> dict[str, dict]:
    """Fetch today's % return for key indices via yfinance."""
    import yfinance as yf
    tickers = {"SPY": "S&P 500", "QQQ": "Nasdaq", "IWM": "Russell 2K", "^VIX": "VIX"}
    results: dict[str, dict] = {}
    for sym, label in tickers.items():
        try:
            h = yf.download(sym, period="5d", progress=False, auto_adjust=True)
            if h.empty or len(h) < 2:
                continue
            cl = h["Close"]
            if hasattr(cl, "columns"):
                cl = cl.iloc[:, 0]
            prev, last = float(cl.iloc[-2]), float(cl.iloc[-1])
            chg_pct = (last - prev) / prev * 100
            results[sym] = {"label": label, "last": round(last, 2), "chg_pct": round(chg_pct, 2)}
        except Exception:
            pass
    return results


def _load_json_safe(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except Exception:
        return None


def _build_market_summary() -> str:
    """
    Builds an HTML market-summary block for the top of the email.
    All sources are woven into a single cohesive narrative rather than
    separate cards — keeps the voice tight and trader-focused.
    """
    # ── Load all sources ──────────────────────────────────────────────────────
    indices        = _fetch_index_returns()
    regime_ctx     = _load_json_safe(LOGS_DIR / "regime_context.json") or {}
    sentiment_data = _load_json_safe(LOGS_DIR / "news_sentiment.json") or {}
    bulltard_data  = _load_json_safe(LOGS_DIR / "bulltard_insights.json")
    mv_data        = _load_json_safe(LOGS_DIR / "macrovoices_insights.json")
    macro_raw      = _load_json_safe(LOGS_DIR.parent / "config" / "macro_events.json")

    bulltard_entry = (bulltard_data or [None])[0] or {}
    mv_entry       = (mv_data or [None])[0] or {}

    macro_events: list[dict] = []
    if isinstance(macro_raw, list):
        macro_events = [e for e in macro_raw if e.get("active", True) and not e.get("end_date")]
    elif isinstance(macro_raw, dict):
        macro_events = [e for e in macro_raw.get("events", []) if e.get("active", True)]

    # ── Index bar ─────────────────────────────────────────────────────────────
    def _idx_cell(sym: str) -> str:
        d = indices.get(sym)
        if not d:
            return ""
        chg    = d["chg_pct"]
        is_vix = sym == "^VIX"
        color  = "#c62828" if (chg >= 0) == is_vix else "#2e7d32"
        arrow  = "▲" if chg >= 0 else "▼"
        return (
            f'<div class="sb">'
            f'<div class="val" style="color:{color}">{arrow} {abs(chg):.1f}%</div>'
            f'<div class="lbl">{d["label"]} ({d["last"]:,.0f})</div>'
            f'</div>'
        )

    index_bar = "".join(_idx_cell(s) for s in ["SPY", "QQQ", "IWM", "^VIX"])

    # ── Regime badge ──────────────────────────────────────────────────────────
    regime_l1 = regime_ctx.get("regime", "UNKNOWN")
    regime_colors = {
        "STRONG_UPTREND":   ("#2e7d32", "#e8f5e9"),
        "MIXED":            ("#1565c0", "#e3f2fd"),
        "CHOPPY":           ("#e65100", "#fff3e0"),
        "STRONG_DOWNTREND": ("#c62828", "#ffebee"),
        "UNFAVORABLE":      ("#6a1b9a", "#f3e5f5"),
    }
    r_fg, r_bg = regime_colors.get(regime_l1, ("#555", "#f5f5f5"))
    regime_badge = (
        f'<span style="background:{r_bg};color:{r_fg};padding:3px 10px;border-radius:10px;'
        f'font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.5px">'
        f'{regime_l1.replace("_"," ")}</span>'
    )

    # ── Sentiment badge ───────────────────────────────────────────────────────
    macro_sent = sentiment_data.get("macro_sentiment")

    def _sent_label(score: Optional[float]) -> tuple[str, str]:
        if score is None:          return "Neutral",     "#555"
        if score <= -0.7:          return "Very Bearish", "#c62828"
        if score <= -0.3:          return "Bearish",      "#e65100"
        if score <   0.3:          return "Neutral",      "#555"
        if score <   0.7:          return "Bullish",      "#2e7d32"
        return                            "Very Bullish", "#2e7d32"

    sent_label, sent_color = _sent_label(macro_sent)
    sentiment_badge = (
        f'<span style="background:#f5f5f5;color:{sent_color};padding:3px 10px;border-radius:10px;'
        f'font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.5px">'
        f'{sent_label}</span>'
    )

    # ── Raw data for narrative ────────────────────────────────────────────────
    spy = indices.get("SPY")
    qqq = indices.get("QQQ")
    vix = indices.get("^VIX")
    iwm = indices.get("IWM")

    bt_summary = (bulltard_entry.get("summary") or "").strip()
    bt_themes  = bulltard_entry.get("themes") or []
    bt_levels  = bulltard_entry.get("key_levels") or []
    bt_bias    = (sentiment_data.get("bulltard_bias_label") or "").upper()

    mv_title  = (mv_entry.get("title") or "").replace("MacroVoices #", "#").strip()
    mv_guest  = (mv_entry.get("guest") or "").strip()
    mv_themes = mv_entry.get("themes") or []

    # ── Build the unified narrative ───────────────────────────────────────────
    sentences: list[str] = []

    # 1. Lead with what the tape did
    if spy:
        spy_dir  = "shed" if spy["chg_pct"] < 0 else "added"
        spy_move = f"{abs(spy['chg_pct']):.1f}%"
        qqq_str  = (f", Nasdaq {'+' if qqq['chg_pct'] >= 0 else ''}{qqq['chg_pct']:.1f}%"
                    if qqq else "")
        iwm_str  = (f", small-caps {'+' if iwm['chg_pct'] >= 0 else ''}{iwm['chg_pct']:.1f}%"
                    if iwm else "")
        if vix:
            vix_dir  = "ripped" if vix["chg_pct"] > 5 else ("ticked up" if vix["chg_pct"] > 0 else "eased")
            vix_str  = f" — VIX {vix_dir} {abs(vix['chg_pct']):.1f}% to <strong>{vix['last']:.1f}</strong>"
        else:
            vix_str = ""
        sentences.append(
            f"SPY {spy_dir} <strong>{spy_move}</strong>{qqq_str}{iwm_str}{vix_str}."
        )

    # 2. Weave in active macro events as the "why"
    event_names = [e.get("event") or e.get("name", "") for e in macro_events if e.get("event") or e.get("name")]
    # Pull the richest event description (longest one is usually the SPY/market-structure note)
    rich_event = max(macro_events, key=lambda e: len(e.get("event") or e.get("name") or ""), default=None)
    rich_desc  = (rich_event.get("event") or rich_event.get("name") or "") if rich_event else ""

    if event_names:
        # Separate structural market events from geopolitical ones
        geo_events  = [n for n in event_names if any(w in n.lower() for w in ["war", "iran", "israel", "oil", "food", "supply"])]
        mkt_events  = [n for n in event_names if n not in geo_events]

        if geo_events and mkt_events:
            sentences.append(
                f"{geo_events[0]} continues to keep risk premium elevated, "
                f"and {mkt_events[0].lower()}."
            )
        elif geo_events:
            sentences.append(f"{geo_events[0]} is keeping risk premium elevated.")
        elif mkt_events:
            sentences.append(f"{mkt_events[0]}.")

    # 3. Bulltard's take — pull the most actionable line from the summary
    if bt_summary:
        trimmed = bt_summary.strip()
        # Strip housekeeping/apology openers and find where market content starts
        is_data_issue = any(w in trimmed.lower() for w in ["sorry", "data feed", "cboe knows"])
        if is_data_issue:
            # Scan for the first substantive market marker
            for marker in ["as for levels", "the spy", "spy is", "the market", "levels to watch"]:
                cut = trimmed.lower().find(marker)
                if cut > 0:
                    trimmed = trimmed[cut:]
                    trimmed = trimmed[0].upper() + trimmed[1:]
                    break
            else:
                # No market content found — fall back to themes only
                trimmed = ""
        # Cap at ~400 chars, ending on a clean sentence break
        if trimmed:
            cap = 420
            if len(trimmed) > cap:
                # Prefer ending on a period
                last_period = trimmed[:cap].rfind(".")
                if last_period > 80:
                    trimmed = trimmed[: last_period + 1]
                else:
                    # Fall back to last comma before cap
                    last_comma = trimmed[:cap].rfind(",")
                    trimmed = trimmed[: last_comma] + "…" if last_comma > 80 else trimmed[:cap] + "…"
        if trimmed and len(trimmed) > 40:
            # If the text ends mid-word (no trailing punctuation), add ellipsis
            if trimmed[-1] not in ".!?,…":
                trimmed += "…"
            sentences.append(f'Bulltard: <em>"{trimmed}"</em>')
        elif bt_themes:
            sentences.append(
                f"Bulltard flagged {', '.join(bt_themes[:3])} as the key themes — bias is {bt_bias.lower()}."
            )

    # 4. MacroVoices framing
    if mv_guest and mv_themes:
        theme_str = " and ".join(mv_themes[:2])
        sentences.append(
            f"MacroVoices this week, <strong>{mv_guest}</strong> lays out the case: "
            f"{mv_title.split(':', 1)[-1].strip() if ':' in mv_title else mv_title} — "
            f"themes of {theme_str} line up with what the tape is telling us right now."
        )
    elif mv_guest:
        sentences.append(
            f"MacroVoices this week, <strong>{mv_guest}</strong> — {mv_title.split(':', 1)[-1].strip() if ':' in mv_title else mv_title}."
        )

    # 5. Regime + positioning implication (closing line)
    regime_implications = {
        "STRONG_UPTREND":   "Regime is green — size up, let winners run.",
        "MIXED":            f"Regime is Mixed — stay selective, size cautiously ({sent_label} tape).",
        "CHOPPY":           f"Regime is Choppy — no new exposure until the tape proves itself. Let your stops work and collect premium.",
        "STRONG_DOWNTREND": "Regime is in full downtrend — defensive posture, hedges on, short side is live.",
        "UNFAVORABLE":      "Regime is Unfavorable — cash is a position.",
    }
    implication = regime_implications.get(regime_l1, f"Regime: {regime_l1}.")
    if macro_sent is not None:
        implication += f" Combined sentiment reads <strong>{sent_label}</strong> ({macro_sent:+.2f})."
    sentences.append(implication)

    # 6. Key levels as a quick line (if any)
    if bt_levels:
        sentences.append(f"Key levels to watch: {' | '.join(bt_levels[:3])}.")

    # Join all sentences into one flowing paragraph
    narrative_html = " ".join(sentences)

    # ── Theme pills (visual quick-ref) ────────────────────────────────────────
    all_themes = list(dict.fromkeys(bt_themes + mv_themes))
    theme_pills = "".join(
        f'<span style="display:inline-block;padding:2px 9px;border-radius:10px;'
        f'font-size:11px;font-weight:600;background:#e3f2fd;color:#1565c0;margin:2px 2px 0 0">{t}</span>'
        for t in all_themes[:8]
    )

    return f"""
    <div style="background:#f8f9fb;border:1px solid #e9ecef;border-radius:10px;padding:20px 22px;margin-bottom:28px">
      <div style="font-size:11px;font-weight:700;color:#6c757d;text-transform:uppercase;letter-spacing:.6px;margin-bottom:14px">
        Market Summary — {date.today().strftime('%A, %B %d')}
        &nbsp;{regime_badge}&nbsp;{sentiment_badge}
      </div>

      <div class="summary-bar" style="margin-bottom:16px">{index_bar}</div>

      <p style="font-size:13px;color:#1a1a2e;line-height:1.75;margin:0{' 0 10px' if all_themes else ''}">{narrative_html}</p>

      {f'<div style="margin-top:12px">{theme_pills}</div>' if all_themes else ''}
    </div>"""


# ── HTML helpers ───────────────────────────────────────────────────────────────

_CSS = """
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       color: #1a1a2e; background: #f0f2f5; margin: 0; padding: 20px; }
.wrap { max-width: 920px; margin: 0 auto; background: #fff; border-radius: 14px;
        box-shadow: 0 4px 20px rgba(0,0,0,.10); overflow: hidden; }
.hdr  { background: linear-gradient(135deg, #0f2027 0%, #1a3a4a 50%, #2c5364 100%);
        color: #fff; padding: 28px 36px 22px; }
.hdr h1 { margin: 0 0 4px; font-size: 22px; font-weight: 700; letter-spacing: -.3px; }
.hdr p  { margin: 0; opacity: .65; font-size: 13px; }
.body   { padding: 28px 36px 36px; }
.summary-bar { display: flex; gap: 10px; margin-bottom: 28px; flex-wrap: wrap; }
.sb { flex: 1; min-width: 110px; background: #f8f9fb; border-radius: 8px;
      padding: 12px 14px; text-align: center; border: 1px solid #eaecef; }
.sb .val { font-size: 18px; font-weight: 700; color: #0f2027; }
.sb .lbl { font-size: 10px; color: #6c757d; text-transform: uppercase;
           letter-spacing: .6px; margin-top: 3px; }
h2 { font-size: 14px; color: #2c5364; margin: 28px 0 10px;
     border-bottom: 2px solid #e9ecef; padding-bottom: 6px; text-transform: uppercase;
     letter-spacing: .4px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { background: #f1f3f5; padding: 8px 10px; text-align: left; font-weight: 600;
     color: #495057; border-bottom: 2px solid #dee2e6;
     font-size: 11px; text-transform: uppercase; letter-spacing: .4px; }
td { padding: 7px 10px; border-bottom: 1px solid #f4f5f7; vertical-align: middle; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #f8f9fa; }
.r  { text-align: right; }
.green { color: #2e7d32; font-weight: 600; }
.red   { color: #c62828; font-weight: 600; }
.muted { color: #868e96; }
.pill { display: inline-block; padding: 2px 8px; border-radius: 10px;
        font-size: 11px; font-weight: 600; white-space: nowrap; }
.pill-ok   { background: #e8f5e9; color: #2e7d32; }
.pill-warn { background: #fff3e0; color: #e65100; }
.pill-bad  { background: #ffebee; color: #c62828; }
.alert-box { background: #fff8e1; border-left: 4px solid #f59e0b;
             border-radius: 6px; padding: 14px 16px; margin-bottom: 20px; }
.alert-box h3 { margin: 0 0 8px; font-size: 13px; color: #92400e; text-transform: uppercase; letter-spacing: .4px; }
.alert-item { font-size: 13px; color: #78350f; margin: 4px 0; }
.ft { padding: 16px 36px; background: #f8f9fb; color: #adb5bd;
      font-size: 11px; text-align: center; border-top: 1px solid #eaecef; }
"""


def _money(v: float) -> str:
    return f"${v:,.0f}"


def _pnl_cell(v: float) -> str:
    cls = "green" if v >= 0 else "red"
    sign = "+" if v >= 0 else ""
    return f'<td class="r {cls}">{sign}${v:,.0f}</td>'


def _pct_cell(v: float) -> str:
    cls = "green" if v >= 0 else "red"
    sign = "+" if v >= 0 else ""
    return f'<td class="r {cls}">{sign}{v:.1f}%</td>'


def _pill_status(flags: list[str]) -> str:
    if not flags:
        return '<span class="pill pill-ok">OK</span>'
    worst = flags[0]
    cls = "pill-bad" if "ITM" in worst else "pill-warn"
    return f'<span class="pill {cls}">{worst}</span>'


# ── HTML builder ───────────────────────────────────────────────────────────────

def build_html(stocks: list[dict], options: list[dict]) -> str:
    now_str = datetime.now().strftime("%A, %B %d, %Y &middot; %I:%M %p MT")
    market_summary_html = _build_market_summary()

    cc    = sorted([r for r in options if r["type"] == "Covered Call"], key=lambda x: x["symbol"])
    csps  = sorted([r for r in options if r["type"] == "CSP"],          key=lambda x: x["symbol"])
    longs = sorted([r for r in options if r["qty"] > 0],                key=lambda x: (x["dte"], x["symbol"]))

    total_prem   = sum(r["total_prem"] for r in cc + csps)
    n_short_opts = sum(abs(r["qty"]) for r in cc + csps)
    avg_dte      = sum(r["dte"] for r in cc + csps) / len(cc + csps) if cc + csps else 0
    total_assign = sum(r["assign_risk"] for r in csps if r["assign_risk"])

    # Stocks summary
    long_stocks  = [s for s in stocks if s["qty"] > 0]
    short_stocks = [s for s in stocks if s["qty"] < 0]
    total_unreal = sum(s["unreal_pnl"] for s in stocks)

    # Alerts
    alerts: list[str] = []
    for r in options:
        for f in r["flags"]:
            right_lbl = "C" if r["right"] == "C" else "P"
            alerts.append(f"{r['symbol']} ${r['strike']:.0f}{right_lbl} exp {r['expiry_str']}: {f}")
    for s in stocks:
        if s["qty"] < 0 and s["ret_pct"] < -5:
            alerts.append(f"{s['symbol']} short position down {s['ret_pct']:.1f}% — review stop")
        dist_pct = s.get("stop_dist_pct")
        if dist_pct is not None and dist_pct <= 2 and s["qty"] > 0:
            alerts.append(
                f"{s['symbol']} within {dist_pct:.1f}% of stop ${s['stop_price']:,.2f} "
                f"(spot ${s['spot']:,.2f}) — near trigger"
            )
        if s.get("stop_price") is None and s["qty"] > 0:
            alerts.append(f"{s['symbol']} has no stop set — add one")

    # ── Summary bar ──────────────────────────────────────────────────────────
    pnl_color = "green" if total_unreal >= 0 else "red"
    pnl_sign  = "+" if total_unreal >= 0 else ""
    summary_bar = f"""
    <div class="summary-bar">
      <div class="sb"><div class="val">{len(long_stocks)}</div><div class="lbl">Long Stocks</div></div>
      <div class="sb"><div class="val" style="color:{'#2e7d32' if total_unreal>=0 else '#c62828'}">{pnl_sign}{_money(total_unreal)}</div><div class="lbl">Unrealized P&L</div></div>
      <div class="sb"><div class="val">{len(cc)}</div><div class="lbl">Covered Calls</div></div>
      <div class="sb"><div class="val">{len(csps)}</div><div class="lbl">CSPs</div></div>
      <div class="sb"><div class="val">{_money(total_prem)}</div><div class="lbl">Premium On Book</div></div>
      <div class="sb"><div class="val">{avg_dte:.0f}d</div><div class="lbl">Avg DTE</div></div>
      <div class="sb"><div class="val">{'🔴 ' + str(len(alerts)) if alerts else '✅ 0'}</div><div class="lbl">Alerts</div></div>
    </div>"""

    # ── Alerts box ───────────────────────────────────────────────────────────
    alert_html = ""
    if alerts:
        items = "".join(f'<div class="alert-item">⚠️ {a}</div>' for a in alerts)
        alert_html = f'<div class="alert-box"><h3>Action Items ({len(alerts)})</h3>{items}</div>'

    # ── Stock positions table ─────────────────────────────────────────────────
    def _stop_cell(s: dict) -> str:
        stop = s.get("stop_price")
        dist_pct = s.get("stop_dist_pct")
        if stop is None:
            return "<td class='r muted'>—</td>"
        stop_str = f"${stop:,.2f}"
        if dist_pct is None:
            return f"<td class='r'>{stop_str}</td>"
        # Colour: red ≤2%, orange ≤5%, green >5%
        if dist_pct <= 2:
            cls  = "red"
            dist = f"({dist_pct:.1f}%)"
        elif dist_pct <= 5:
            cls  = "pill-warn"
            dist = f"({dist_pct:.1f}%)"
        else:
            cls  = "muted"
            dist = f"({dist_pct:.1f}%)"
        return f"<td class='r'><span style='font-weight:600'>{stop_str}</span><br><small class='{cls}'>{dist}</small></td>"

    def _stock_rows(rows: list[dict]) -> str:
        out = ""
        for s in rows:
            spot_str = f"${s['spot']:,.2f}" if s["spot"] else "—"
            notional = f"${s['notional']:,.0f}" if s["notional"] else "—"
            out += (
                f"<tr>"
                f"<td><strong>{s['symbol']}</strong></td>"
                f"<td class='r'>{s['qty']:,}</td>"
                f"<td class='r'>${s['avg_cost']:.2f}</td>"
                f"<td class='r'>{spot_str}</td>"
                f"<td class='r'>{notional}</td>"
                + _pnl_cell(s["unreal_pnl"])
                + _pct_cell(s["ret_pct"])
                + _stop_cell(s)
                + "</tr>"
            )
        return out

    stock_header = (
        "<tr><th>Symbol</th><th class='r'>Qty</th><th class='r'>Avg Cost</th>"
        "<th class='r'>Spot</th><th class='r'>Notional</th>"
        "<th class='r'>Unreal P&L</th><th class='r'>Return</th>"
        "<th class='r'>Stop</th></tr>"
    )

    long_stock_html = f"<table>{stock_header}{_stock_rows(long_stocks)}</table>" if long_stocks else "<p class='muted'>No long stock positions.</p>"
    short_stock_html = f"<table>{stock_header}{_stock_rows(short_stocks)}</table>" if short_stocks else ""

    # ── Options table ─────────────────────────────────────────────────────────
    def _opt_rows(rows: list[dict], show_assign: bool = False) -> str:
        out = ""
        for r in rows:
            right_lbl = "C" if r["right"] == "C" else "P"
            out += (
                f"<tr>"
                f"<td><strong>{r['symbol']}</strong></td>"
                f"<td>${r['strike']:.0f} {right_lbl}</td>"
                f"<td>{r['expiry_str']}</td>"
                f"<td class='r'>{r['dte']}d</td>"
                f"<td class='r'>${r['spot']:,.2f}</td>"
                f"<td>{r['moneyness']}</td>"
                f"<td class='r'>&times;{abs(r['qty'])}</td>"
                f"<td class='r'>{_money(r['total_prem'])}</td>"
            )
            if show_assign:
                out += f"<td class='r'>{_money(r['assign_risk']) if r['assign_risk'] else '—'}</td>"
            out += f"<td>{_pill_status(r['flags'])}</td></tr>"
        return out

    def _opt_table(rows: list[dict], show_assign: bool = False) -> str:
        cols = (
            "<tr><th>Symbol</th><th>Strike</th><th>Expiry</th><th class='r'>DTE</th>"
            "<th class='r'>Spot</th><th>Moneyness</th><th class='r'>Qty</th>"
            "<th class='r'>Premium</th>"
        )
        if show_assign:
            cols += "<th class='r'>Assign Risk</th>"
        cols += "<th>Status</th></tr>"
        return f"<table>{cols}{_opt_rows(rows, show_assign)}</table>"

    cc_html  = _opt_table(cc)  if cc  else "<p class='muted'>No covered calls.</p>"
    csp_html = _opt_table(csps, show_assign=True) if csps else "<p class='muted'>No CSPs.</p>"

    longs_html = ""
    if longs:
        longs_html = f"<h2>Long Options ({len(longs)})</h2><table>"
        longs_html += "<tr><th>Symbol</th><th>Strike</th><th>Expiry</th><th class='r'>DTE</th><th class='r'>Spot</th><th>Moneyness</th><th class='r'>Qty</th></tr>"
        for r in longs:
            right_lbl = "C" if r["right"] == "C" else "P"
            longs_html += (
                f"<tr><td><strong>{r['symbol']}</strong></td>"
                f"<td>${r['strike']:.0f} {right_lbl}</td>"
                f"<td>{r['expiry_str']}</td>"
                f"<td class='r'>{r['dte']}d</td>"
                f"<td class='r'>${r['spot']:,.2f}</td>"
                f"<td>{r['moneyness']}</td>"
                f"<td class='r'>&times;{r['qty']}</td></tr>"
            )
        longs_html += "</table>"

    short_section = f"<h2>Short Positions ({len(short_stocks)})</h2>{short_stock_html}" if short_stocks else ""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{_CSS}</style></head>
<body>
<div class="wrap">
  <div class="hdr">
    <h1>Winzinvest — Daily Positions</h1>
    <p>{now_str}</p>
  </div>
  <div class="body">

    {market_summary_html}
    {summary_bar}
    {alert_html}

    <h2>Long Stocks ({len(long_stocks)} positions &middot; sorted by return)</h2>
    {long_stock_html}

    {short_section}

    <h2>Covered Calls ({len(cc)} positions &middot; {_money(sum(r['total_prem'] for r in cc))} premium)</h2>
    {cc_html}

    <h2>Cash-Secured Puts ({len(csps)} positions &middot; {_money(sum(r['total_prem'] for r in csps))} premium &middot; {_money(total_assign)} obligation)</h2>
    {csp_html}

    {longs_html}

  </div>
  <div class="ft">
    Winzinvest &middot; Live data from Interactive Brokers &middot; Prices via yfinance &middot; {datetime.now().strftime('%Y-%m-%d %H:%M MT')}
  </div>
</div>
</body></html>"""
    return html


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Winzinvest Daily Positions Email")
    parser.add_argument("--preview", action="store_true", help="Write HTML to /tmp, skip send")
    args = parser.parse_args()

    from ib_insync import IB
    ib = IB()
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=10)
        log.info("Connected to IB")
    except Exception as e:
        log.error(f"IB connect failed: {e}")
        return

    try:
        stock_positions  = _fetch_stock_positions(ib)
        option_positions = _fetch_option_positions(ib)
    finally:
        ib.disconnect()
        log.info("Disconnected from IB")

    all_symbols = list({p["symbol"] for p in stock_positions + option_positions})
    prices      = _fetch_prices(all_symbols)
    stops       = _load_stop_prices()

    enriched_stocks  = _enrich_stocks(stock_positions, prices, stops)
    enriched_options = _enrich_options(option_positions, prices)

    html      = build_html(enriched_stocks, enriched_options)
    today_str = date.today().strftime("%b %d, %Y")
    subject   = f"Winzinvest Positions — {today_str}"

    if args.preview:
        preview_path = Path("/tmp/positions_email_preview.html")
        preview_path.write_text(html)
        log.info(f"Preview written to {preview_path}")
        return

    try:
        from email_helper import load_email_config, send_email, validate_email_config
        config = load_email_config()
        is_valid, err = validate_email_config(config)
        if not is_valid:
            log.error(f"Email config invalid: {err}")
            _send_telegram_fallback(enriched_stocks, enriched_options)
            return

        all_recipients = [config.get("to_email", "")] + EXTRA_RECIPIENTS
        all_recipients = [r for r in all_recipients if r]

        for recipient in all_recipients:
            ok = send_email(subject, html, to_email=recipient, config=config)
            log.info(f"Email {'sent' if ok else 'FAILED'} → {recipient}")

    except ImportError:
        log.error("email_helper not found — falling back to Telegram")
        _send_telegram_fallback(enriched_stocks, enriched_options)


def _send_telegram_fallback(stocks: list[dict], options: list[dict]) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat  = os.getenv("TELEGRAM_CHAT_ID", "")
    if not (token and chat):
        log.warning("Telegram not configured — no delivery channel available")
        return

    cc   = [r for r in options if r["type"] == "Covered Call"]
    csps = [r for r in options if r["type"] == "CSP"]
    alerts = [f for r in options for f in r["flags"]]
    total_prem = sum(r["total_prem"] for r in cc + csps)
    total_unreal = sum(s["unreal_pnl"] for s in stocks)

    top_stocks = sorted(stocks, key=lambda x: x["ret_pct"], reverse=True)[:5]
    top_lines  = "\n".join(
        f"  {s['symbol']}: {'+' if s['ret_pct']>=0 else ''}{s['ret_pct']:.1f}%"
        for s in top_stocks
    )

    lines = [
        "<b>Winzinvest Daily Positions</b>",
        f"Long stocks: {len([s for s in stocks if s['qty']>0])} | Unrealized P&L: {'+'if total_unreal>=0 else ''}{total_unreal:,.0f}",
        f"CC: {len(cc)} | CSP: {len(csps)} | Premium: ${total_prem:,.0f}",
        f"Alerts: {len(alerts)}",
        f"\nTop performers:\n{top_lines}",
    ]

    import urllib.request, urllib.parse
    url  = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode(
        {"chat_id": chat, "text": "\n".join(lines), "parse_mode": "HTML"}
    ).encode()
    try:
        urllib.request.urlopen(url, data=data, timeout=5)
        log.info("Telegram fallback sent")
    except Exception as e:
        log.error(f"Telegram fallback also failed: {e}")


if __name__ == "__main__":
    main()
