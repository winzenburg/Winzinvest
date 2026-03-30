#!/usr/bin/env python3
"""
Winzinvest Daily Positions Email
==================================
Two editions per day, styled in FT.com editorial voice:
  - Morning Brief (--morning): 08:00 MT via scheduler — market preview, overnight moves
  - Daily Close  (--evening):  14:00 MT via job_pre_close — full position rundown

Usage:
  python3 daily_options_email.py --morning   # morning edition
  python3 daily_options_email.py --evening   # evening edition (default)
  python3 daily_options_email.py --preview   # write HTML to /tmp, skip send
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


# ── Spread / condor detection ──────────────────────────────────────────────────

def _detect_spreads(
    opts: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Group matched vertical spread legs into Iron Condors / Bear Call / Bull Put.

    Algorithm:
    - Expand multi-contract positions (qty=-2 → two virtual legs of qty=-1) so
      each leg can be individually paired.
    - Bear Call Spread: SHORT lower call + LONG higher call, same symbol/expiry.
    - Bull Put Spread: SHORT higher put + LONG lower put, same symbol/expiry.
    - Iron Condor: one bear call spread + one bull put spread on same symbol/expiry
      (requires equal counts of each).

    Returns:
        spread_structures   List of identified spread/condor dicts.
        standalone_legs     Remaining enriched option dicts not consumed by a spread
                            (go to the existing CC / CSP / Long Options sections).
    """
    from collections import defaultdict

    # Expand qty into individual virtual legs so we can pair them one-to-one.
    expanded: list[dict] = []
    orig_indices: list[int] = []   # which original opt each expanded leg came from
    for orig_i, o in enumerate(opts):
        qty = int(o["qty"])
        sign = 1 if qty > 0 else -1
        for _ in range(abs(qty)):
            expanded.append(dict(o, qty=sign, _matched=False))
            orig_indices.append(orig_i)

    # Group expanded legs by (symbol, expiry)
    groups: dict[tuple, list[int]] = defaultdict(list)
    for exp_i, leg in enumerate(expanded):
        key = (leg["symbol"], leg.get("expiry_str", ""))
        groups[key].append(exp_i)

    call_spreads_by_group: dict[tuple, list[dict]] = defaultdict(list)
    put_spreads_by_group:  dict[tuple, list[dict]] = defaultdict(list)

    for (sym, exp_str), exp_indices in groups.items():
        # --- Bear Call Spreads ---
        shorts_c = sorted(
            [i for i in exp_indices if expanded[i]["right"] == "C" and expanded[i]["qty"] < 0],
            key=lambda i: expanded[i]["strike"],
        )
        longs_c = sorted(
            [i for i in exp_indices if expanded[i]["right"] == "C" and expanded[i]["qty"] > 0],
            key=lambda i: expanded[i]["strike"],
        )
        used_lc: set[int] = set()
        for sc_i in shorts_c:
            sc = expanded[sc_i]
            # nearest LONG call at a strictly higher strike (closest wing)
            best_lc: int | None = None
            for lc_i in longs_c:
                if lc_i in used_lc:
                    continue
                lc = expanded[lc_i]
                if lc["strike"] > sc["strike"]:
                    if best_lc is None or lc["strike"] < expanded[best_lc]["strike"]:
                        best_lc = lc_i
            if best_lc is not None:
                expanded[sc_i]["_matched"] = True
                expanded[best_lc]["_matched"] = True
                used_lc.add(best_lc)
                wing_strike = expanded[best_lc]["strike"]
                width = wing_strike - sc["strike"]
                # avg_cost from IB is total dollars per contract — no * 100 needed
                net_credit = round(sc["prem_per"] - expanded[best_lc]["prem_per"], 2)
                call_spreads_by_group[(sym, exp_str)].append({
                    "symbol": sym, "expiry_str": exp_str, "dte": sc["dte"],
                    "spot": sc["spot"], "right": "C",
                    "short_strike": sc["strike"], "long_strike": wing_strike,
                    "net_credit": net_credit,
                    "max_loss": round(width * 100 - net_credit, 2),
                    "moneyness": sc["moneyness"], "flags": sc.get("flags", []),
                })

        # --- Bull Put Spreads ---
        shorts_p = sorted(
            [i for i in exp_indices if expanded[i]["right"] == "P" and expanded[i]["qty"] < 0],
            key=lambda i: expanded[i]["strike"],
            reverse=True,   # highest strike short put first
        )
        longs_p = sorted(
            [i for i in exp_indices if expanded[i]["right"] == "P" and expanded[i]["qty"] > 0],
            key=lambda i: expanded[i]["strike"],
        )
        used_lp: set[int] = set()
        for sp_i in shorts_p:
            sp = expanded[sp_i]
            # nearest LONG put at a strictly lower strike (closest wing)
            best_lp: int | None = None
            for lp_i in longs_p:
                if lp_i in used_lp:
                    continue
                lp = expanded[lp_i]
                if lp["strike"] < sp["strike"]:
                    if best_lp is None or lp["strike"] > expanded[best_lp]["strike"]:
                        best_lp = lp_i
            if best_lp is not None:
                expanded[sp_i]["_matched"] = True
                expanded[best_lp]["_matched"] = True
                used_lp.add(best_lp)
                wing_strike = expanded[best_lp]["strike"]
                width = sp["strike"] - wing_strike
                # avg_cost from IB is total dollars per contract — no * 100 needed
                net_credit = round(sp["prem_per"] - expanded[best_lp]["prem_per"], 2)
                put_spreads_by_group[(sym, exp_str)].append({
                    "symbol": sym, "expiry_str": exp_str, "dte": sp["dte"],
                    "spot": sp["spot"], "right": "P",
                    "short_strike": sp["strike"], "long_strike": wing_strike,
                    "net_credit": net_credit,
                    "max_loss": round(width * 100 - net_credit, 2),
                    "moneyness": sp["moneyness"], "flags": sp.get("flags", []),
                })

    # Build final spread_structures list
    all_keys = set(call_spreads_by_group) | set(put_spreads_by_group)
    spread_structures: list[dict] = []
    for key in sorted(all_keys):
        cs = call_spreads_by_group.get(key, [])
        ps = put_spreads_by_group.get(key, [])
        n_condors = min(len(cs), len(ps))

        # Pair matching counts into Iron Condors
        for i in range(n_condors):
            c, p = cs[i], ps[i]
            spread_structures.append({
                "symbol": c["symbol"], "expiry_str": c["expiry_str"], "dte": c["dte"],
                "spot": c["spot"], "structure_type": "Iron Condor",
                "call_short": c["short_strike"], "call_long": c["long_strike"],
                "put_short":  p["short_strike"], "put_long":  p["long_strike"],
                "net_credit": round(c["net_credit"] + p["net_credit"], 2),
                "max_loss":   max(c["max_loss"], p["max_loss"]),
                "moneyness_call": c["moneyness"], "moneyness_put": p["moneyness"],
                "flags": c["flags"] + p["flags"],
            })

        # Leftover call spreads (no matching put spread)
        for c in cs[n_condors:]:
            spread_structures.append({**c, "structure_type": "Bear Call Spread"})

        # Leftover put spreads (no matching call spread)
        for p in ps[n_condors:]:
            spread_structures.append({**p, "structure_type": "Bull Put Spread"})

    # Build standalone list: any original leg whose expanded entries were not ALL matched
    from collections import Counter
    def _leg_key(leg: dict) -> tuple:
        return (leg["symbol"], leg["strike"], leg["right"],
                leg.get("expiry_str", ""), leg["qty"] > 0)

    matched_count: Counter = Counter(
        _leg_key(e) for e in expanded if e["_matched"]
    )
    standalone: list[dict] = []
    for o in opts:
        k = _leg_key(o)
        n_total   = abs(int(o["qty"]))
        n_matched = matched_count.get(k, 0)
        remaining = n_total - n_matched
        if remaining > 0:
            sign = 1 if o["qty"] > 0 else -1
            standalone.append(dict(o, qty=sign * remaining))

    return spread_structures, standalone


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


def _fetch_spy_technicals() -> dict:
    """Fetch SPY 1-year history and compute key technical levels.

    Returns a dict with:
        price, sma200, sma50, ema8, ema21, pct_from_200, days_below_200,
        vix_last, vix_5d_avg, consecutive_down_closes
    All values are None on failure.
    """
    import yfinance as yf
    out: dict = {
        "price": None, "sma200": None, "sma50": None,
        "ema8": None, "ema21": None, "pct_from_200": None,
        "days_below_200": None, "consecutive_down_closes": None,
        "vix_last": None, "vix_5d_avg": None,
        "week_chg_pct": None,
    }
    try:
        spy = yf.download("SPY", period="1y", progress=False, auto_adjust=True)
        if spy.empty or len(spy) < 50:
            return out
        cl = spy["Close"]
        if hasattr(cl, "columns"):
            cl = cl.iloc[:, 0]
        price    = float(cl.iloc[-1])
        sma200   = float(cl.rolling(200).mean().iloc[-1]) if len(cl) >= 200 else None
        sma50    = float(cl.rolling(50).mean().iloc[-1])
        ema8     = float(cl.ewm(span=8, adjust=False).mean().iloc[-1])
        ema21    = float(cl.ewm(span=21, adjust=False).mean().iloc[-1])

        out["price"]   = round(price, 2)
        out["sma50"]   = round(sma50, 2)
        out["ema8"]    = round(ema8, 2)
        out["ema21"]   = round(ema21, 2)

        if sma200:
            out["sma200"]        = round(sma200, 2)
            out["pct_from_200"]  = round((price - sma200) / sma200 * 100, 2)

        # Count consecutive sessions below 200 SMA
        if sma200:
            sma200_series = cl.rolling(200).mean()
            days_below = 0
            for i in range(1, min(31, len(cl))):
                if cl.iloc[-i] < sma200_series.iloc[-i]:
                    days_below += 1
                else:
                    break
            out["days_below_200"] = days_below if days_below > 0 else None

        # Consecutive down closes
        down = 0
        for i in range(1, min(11, len(cl))):
            if cl.iloc[-i] < cl.iloc[-i - 1]:
                down += 1
            else:
                break
        out["consecutive_down_closes"] = down if down > 1 else None

        # 5-session % change
        if len(cl) >= 6:
            out["week_chg_pct"] = round((float(cl.iloc[-1]) - float(cl.iloc[-6])) / float(cl.iloc[-6]) * 100, 2)
    except Exception:
        pass

    try:
        vix = yf.download("^VIX", period="10d", progress=False, auto_adjust=True)
        if not vix.empty:
            vc = vix["Close"]
            if hasattr(vc, "columns"):
                vc = vc.iloc[:, 0]
            out["vix_last"]    = round(float(vc.iloc[-1]), 1)
            out["vix_5d_avg"]  = round(float(vc.iloc[-5:].mean()), 1) if len(vc) >= 5 else None
    except Exception:
        pass

    return out


def _load_return_summary() -> dict:
    """Load portfolio_return_summary.json written by portfolio_return_tracker.py.

    Returns an empty dict if the file doesn't exist yet (first run before tracker fires).
    """
    from paths import LOGS_DIR
    path = LOGS_DIR / "portfolio_return_summary.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_json_safe(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except Exception:
        return None


def _build_market_summary(edition: str = "evening") -> str:
    """
    Builds an HTML market-summary block for the top of the email.

    edition: "morning" (8 AM — setup/plan focus) or "evening" (2 PM — recap focus).

    Narrative is driven by actual calculated technicals and synthesized macro
    themes — not attributed quotes from individual sources.  The goal is one
    tight paragraph that reads like a trader wrote it after looking at the tape.
    """
    # ── Load all sources ──────────────────────────────────────────────────────
    indices        = _fetch_index_returns()
    tech           = _fetch_spy_technicals()
    regime_ctx     = _load_json_safe(LOGS_DIR / "regime_context.json") or {}
    sentiment_data = _load_json_safe(LOGS_DIR / "news_sentiment.json") or {}
    macro_raw      = _load_json_safe(LOGS_DIR.parent / "config" / "macro_events.json")

    macro_events: list[dict] = []
    if isinstance(macro_raw, list):
        macro_events = [e for e in macro_raw if e.get("active", True) and not e.get("end_date")]
    elif isinstance(macro_raw, dict):
        macro_events = [e for e in macro_raw.get("events", []) if e.get("active", True)]

    # ── Sentiment data (synthesized, no source attribution) ───────────────────
    symbol_sentiments: dict = sentiment_data.get("symbol_sentiments") or {}
    marketaux_macro   = sentiment_data.get("macro_sentiment")
    articles_count    = sentiment_data.get("articles_analyzed", 0)

    # Stocks in our portfolio with meaningfully negative news flow
    bearish_holdings: list[tuple[str, float]] = sorted(
        [
            (sym, info["score"])
            for sym, info in symbol_sentiments.items()
            if isinstance(info, dict) and info.get("score", 0) < -0.25
        ],
        key=lambda x: x[1],
    )[:3]

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
        if score is None:    return "Neutral",      "#555"
        if score <= -0.7:    return "Very Bearish",  "#c62828"
        if score <= -0.3:    return "Bearish",        "#e65100"
        if score <   0.3:    return "Neutral",        "#555"
        if score <   0.7:    return "Bullish",        "#2e7d32"
        return                      "Very Bullish",   "#2e7d32"

    sent_label, sent_color = _sent_label(macro_sent)
    sentiment_badge = (
        f'<span style="background:#f5f5f5;color:{sent_color};padding:3px 10px;border-radius:10px;'
        f'font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.5px">'
        f'{sent_label}</span>'
    )

    # ── Active geopolitical/macro events ──────────────────────────────────────
    geo_events = [
        e.get("event") or e.get("name", "")
        for e in macro_events
        if any(w in (e.get("event") or e.get("name") or "").lower()
               for w in ["war", "iran", "israel", "oil", "ceasefire", "supply"])
    ]

    # ── Pull index values ─────────────────────────────────────────────────────
    spy = indices.get("SPY")
    qqq = indices.get("QQQ")
    vix = indices.get("^VIX")
    iwm = indices.get("IWM")

    pct_200    = tech.get("pct_from_200")
    days_below = tech.get("days_below_200")
    ema8       = tech.get("ema8")
    price      = tech.get("price") or (spy["last"] if spy else None)
    sma200     = tech.get("sma200")
    week_chg   = tech.get("week_chg_pct")
    vix_level  = tech.get("vix_last") or (vix["last"] if vix else None)

    # ── Build the narrative ───────────────────────────────────────────────────
    sentences: list[str] = []
    is_morning = edition == "morning"

    # ── Ordinal helper ────────────────────────────────────────────────────────
    def _ordinal(n: int) -> str:
        if 11 <= (n % 100) <= 13:
            return f"{n}th"
        return f"{n}{['th','st','nd','rd','th','th','th','th','th','th'][n % 10 if n % 10 < 10 else 0]}"

    # 1. Index movements — precise and direct, no slang
    if spy:
        spy_chg  = spy["chg_pct"]
        qqq_chg  = qqq["chg_pct"] if qqq else None
        iwm_chg  = iwm["chg_pct"] if iwm else None

        def _verb(chg: float) -> str:
            if chg <= -1.5: return "fell sharply"
            if chg < -0.3:  return "declined"
            if chg < 0:     return "edged lower"
            if chg < 0.3:   return "was little changed"
            if chg < 1.5:   return "advanced"
            return "rose sharply"

        parts: list[str] = [f"The S&P 500 {_verb(spy_chg)} {spy_chg:+.1f}%"]

        if qqq_chg is not None and abs(qqq_chg - spy_chg) > 0.4:
            tech_rel = "outperforming" if qqq_chg > spy_chg else "underperforming"
            parts.append(f"with technology stocks {tech_rel} ({qqq_chg:+.1f}%)")
        elif qqq_chg is not None:
            parts.append(f"alongside a {qqq_chg:+.1f}% move in technology")

        if iwm_chg is not None and abs(iwm_chg - spy_chg) > 0.5:
            sm_desc = "outperformed" if iwm_chg > spy_chg else "underperformed"
            parts.append(f"small-cap stocks {sm_desc} ({iwm_chg:+.1f}%)")

        if vix:
            vix_chg = vix["chg_pct"]
            if abs(vix_chg) > 3:
                parts.append(
                    f"volatility {'rose sharply' if vix_chg > 0 else 'fell sharply'}, "
                    f"with the Vix at {vix['last']:.1f}"
                )
            elif abs(vix_chg) > 1:
                parts.append(
                    f"the Vix {'edged higher to' if vix_chg > 0 else 'eased to'} {vix['last']:.1f}"
                )

        sentences.append(". ".join(p[0].upper() + p[1:] if i > 0 else p for i, p in enumerate(parts)) + ".")

    # 2. Technical structure — where the index stands
    if pct_200 is not None and sma200:
        if pct_200 < 0:
            below_clause = (
                f", a {_ordinal(days_below)} consecutive close below that level"
                if days_below and days_below > 1
                else ""
            )
            sentences.append(
                f"The S&P 500 is trading {abs(pct_200):.1f}% below its 200-day moving average "
                f"of ${sma200:,.0f}{below_clause}."
            )
        else:
            sentences.append(
                f"The S&P 500 remains {pct_200:.1f}% above its 200-day moving average of ${sma200:,.0f}."
            )

    if ema8 and price:
        if price < ema8:
            sentences.append(
                f"Short-term momentum indicators are negative — the index remains below "
                f"its eight-day exponential average of ${ema8:,.0f}."
            )
        else:
            sentences.append(
                f"The index has reclaimed its eight-day exponential average at ${ema8:,.0f}, "
                f"a modest improvement in short-term momentum."
            )

    if week_chg is not None and abs(week_chg) > 1.5:
        dir_str = f"declined {abs(week_chg):.1f}%" if week_chg < 0 else f"advanced {week_chg:.1f}%"
        sentences.append(f"On a weekly basis the S&P 500 has {dir_str}.")

    # 3. What is driving markets — synthesized from all news sources, no attribution
    if marketaux_macro is not None and marketaux_macro < -0.3 and articles_count >= 5:
        # Synthesize bearish news flow without citing specific sources
        geo_context = " Geopolitical risk continues to weigh on sentiment." if geo_events else ""
        vix_context = (
            f" The options market is pricing in an elevated risk premium, with the Vix at {vix_level:.0f}."
            if vix_level and vix_level > 25
            else ""
        )
        sentences.append(
            f"News flow has contributed to the cautious tone, "
            f"with market participants digesting concerns around policy uncertainty and earnings visibility.{geo_context}{vix_context}"
        )
    elif marketaux_macro is not None and marketaux_macro > 0.3 and articles_count >= 5:
        # Synthesize bullish news flow
        sentences.append(
            f"News flow has been constructive, "
            f"with improving sentiment around growth expectations and corporate earnings."
        )
    elif geo_events:
        vix_context = (
            f" The options market is pricing in an elevated risk premium, "
            f"with the Vix at {vix_level:.0f}."
            if vix_level and vix_level > 25
            else ""
        )
        sentences.append(f"Geopolitical developments continue to influence market positioning.{vix_context}")

    # 4. Portfolio holdings under news pressure
    if bearish_holdings:
        syms_html = ", ".join(f"<strong>{sym}</strong>" for sym, _ in bearish_holdings)
        sentences.append(
            f"News sentiment for {syms_html} — holdings in the current portfolio — "
            f"is notably negative. Stop placement on those positions warrants a review."
        )

    # 5. Regime assessment — institutional language, morning vs evening distinction
    regime_morning: dict[str, str] = {
        "STRONG_UPTREND": (
            "The technical regime is constructive. "
            "The portfolio is positioned to benefit from continued equity strength, "
            "with premium income providing a secondary return stream."
        ),
        "MIXED": (
            "The technical regime is mixed — no decisive directional signal. "
            "Against this backdrop, the strategy limits new directional exposure "
            "and relies on premium income as the primary return driver."
        ),
        "CHOPPY": (
            "The regime is indeterminate. "
            "In the absence of a clear directional signal, the strategy is weighted towards "
            "premium collection rather than new positional risk."
        ),
        "STRONG_DOWNTREND": (
            "The regime is in a confirmed downtrend. "
            "Short exposure is the primary driver of returns in this environment; "
            "no new long positions are warranted until conditions improve."
        ),
        "UNFAVORABLE": (
            "The technical regime is unfavourable for new risk-taking. "
            "Preserving capital and tightening existing stop levels takes precedence "
            "over deploying additional exposure."
        ),
    }
    regime_evening: dict[str, str] = {
        "STRONG_UPTREND": (
            "The technical regime remained constructive through the session. "
            "Long positions contributed positively; covered calls continue to add "
            "incremental income without meaningfully capping upside."
        ),
        "MIXED": (
            "The mixed regime was reflected in today's price action — "
            "a lack of directional conviction on both sides. "
            "Premium income remained the primary contributor to portfolio returns."
        ),
        "CHOPPY": (
            "The indeterminate regime persisted through the close. "
            "Short premium positions performed as expected in a range-bound session — "
            "time decay accrued without directional risk materialising."
        ),
        "STRONG_DOWNTREND": (
            "The downtrend held through the session. "
            "Short exposure continued to contribute positively; "
            "long positions with covered calls partially offset broader equity weakness."
        ),
        "UNFAVORABLE": (
            "The unfavourable regime was unchanged through the close. "
            "Cash preserved capital in today's environment. "
            "No new exposure is warranted until the regime improves."
        ),
    }
    regime_voices = regime_morning if is_morning else regime_evening
    regime_read = regime_voices.get(regime_l1)
    if regime_read:
        sentences.append(regime_read)

    # 6. Forward-looking close — morning: key levels to watch; evening: overnight factors
    watch_items: list[str] = []
    if days_below and days_below >= 3 and pct_200 is not None and pct_200 < 0:
        level_str = f"${sma200:,.0f}" if sma200 else "the 200-day moving average"
        watch_items.append(
            f"whether the S&P 500 can sustain a move back above the 200-day at {level_str}"
            if is_morning
            else f"whether the 200-day moving average at {level_str} reasserts itself as resistance"
        )
    if vix_level and vix_level > 22:
        vix_target = round(vix_level * 0.85, 0)
        watch_items.append(
            f"any compression in the Vix toward {vix_target:.0f}, which would signal easing risk appetite"
            if is_morning
            else f"whether the Vix holds above {vix_target:.0f} or begins to moderate"
        )
    if geo_events:
        watch_items.append(
            "geopolitical developments ahead of the open" if is_morning
            else "any geopolitical developments that could affect sentiment at the next open"
        )
    if bearish_holdings and not watch_items:
        syms = " and ".join(s for s, _ in bearish_holdings[:2])
        watch_items.append(
            f"early price action in {syms}, where news flow has been adverse"
            if is_morning
            else f"any after-hours developments in {syms}"
        )

    if watch_items:
        label = "Investors will be focused on" if is_morning else "Key factors to monitor overnight include"
        watch_sentence = f"{label} {watch_items[0]}"
        if len(watch_items) > 1:
            watch_sentence += f", as well as {watch_items[1]}"
        sentences.append(watch_sentence + ".")

    narrative_html = " ".join(sentences)

    # ── No headline cards or theme pills — pure synthesis only ────────────────

    return f"""
    <div style="background:#f8f9fb;border:1px solid #e9ecef;border-radius:10px;padding:20px 22px;margin-bottom:28px">
      <div style="font-size:11px;font-weight:700;color:#6c757d;text-transform:uppercase;letter-spacing:.6px;margin-bottom:14px">
        Market Summary — {date.today().strftime('%A, %B %d')}
        &nbsp;{regime_badge}&nbsp;{sentiment_badge}
      </div>

      <div class="summary-bar" style="margin-bottom:16px">{index_bar}</div>

      <p style="font-size:13px;color:#1a1a2e;line-height:1.75;margin:0">{narrative_html}</p>
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
.spread-type { display: inline-block; padding: 2px 9px; border-radius: 10px;
               font-size: 11px; font-weight: 700; letter-spacing: .3px; white-space: nowrap; }
.spread-condor  { background: #e8eaf6; color: #283593; }
.spread-bcall   { background: #fce4ec; color: #880e4f; }
.spread-bput    { background: #e8f5e9; color: #1b5e20; }
.spread-legs    { font-size: 12px; color: #495057; }
.spread-legs small { color: #868e96; }
.credit-pos  { color: #2e7d32; font-weight: 600; }
.credit-neg  { color: #c62828; font-weight: 600; }
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

def _build_pace_line() -> str:
    """Return an HTML snippet showing YTD return and pace vs 40% annual target.

    Reads logs/portfolio_return_summary.json produced by portfolio_return_tracker.py.
    Returns empty string gracefully if the file is unavailable.
    """
    data = _load_return_summary()
    line = data.get("email_summary_line", "")
    if not line:
        return ""
    pace = data.get("pace", {})
    on_pace = pace.get("on_pace", True)
    color = "#a5d6a7" if on_pace else "#ffcc80"   # muted green / amber on dark header
    return (
        f'<p style="margin:6px 0 0; opacity:0.85; font-size:13px; color:{color};">'
        f"&#x1F4C8; {line}"
        f"</p>"
    )


def build_html(stocks: list[dict], options: list[dict], edition: str = "evening", recipient_email: str = "") -> str:
    now_str = datetime.now().strftime("%A, %B %d, %Y &middot; %I:%M %p MT")
    market_summary_html = _build_market_summary(edition=edition)
    pace_line_html = _build_pace_line()

    # Detect spreads first; remaining standalone legs feed the CC/CSP/Long tables
    spreads, standalone_opts = _detect_spreads(options)

    cc    = sorted([r for r in standalone_opts if r["type"] == "Covered Call"], key=lambda x: x["symbol"])
    csps  = sorted([r for r in standalone_opts if r["type"] == "CSP"],          key=lambda x: x["symbol"])
    longs = sorted([r for r in standalone_opts if r["qty"] > 0],                key=lambda x: (x["dte"], x["symbol"]))

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

    # ── Spreads & Condors table ───────────────────────────────────────────────
    def _spread_type_pill(stype: str) -> str:
        cls = {"Iron Condor": "spread-condor",
               "Bear Call Spread": "spread-bcall",
               "Bull Put Spread":  "spread-bput"}.get(stype, "pill-ok")
        return f'<span class="spread-type {cls}">{stype}</span>'

    def _spread_legs_cell(s: dict) -> str:
        stype = s["structure_type"]
        spot  = s.get("spot", 0)
        if stype == "Iron Condor":
            cs = f"${s['call_short']:.0f}C / ${s['call_long']:.0f}C"
            ps = f"${s['put_long']:.0f}P / ${s['put_short']:.0f}P"
            return (
                f"<td class='spread-legs'>"
                f"Short: ${s['call_short']:.0f}C &amp; ${s['put_short']:.0f}P<br>"
                f"<small>Wings: ${s['call_long']:.0f}C &amp; ${s['put_long']:.0f}P</small>"
                f"</td>"
            )
        else:
            return (
                f"<td class='spread-legs'>"
                f"Short: ${s['short_strike']:.0f}{s['right']}<br>"
                f"<small>Wing: ${s['long_strike']:.0f}{s['right']}</small>"
                f"</td>"
            )

    def _spread_moneyness_cell(s: dict) -> str:
        stype = s["structure_type"]
        if stype == "Iron Condor":
            mc = s.get("moneyness_call", "")
            mp = s.get("moneyness_put", "")
            return f"<td><small>{mc}<br>{mp}</small></td>"
        return f"<td>{s.get('moneyness', '—')}</td>"

    def _spread_credit_cell(net: float) -> str:
        cls = "credit-pos" if net >= 0 else "credit-neg"
        sign = "+" if net >= 0 else ""
        return f'<td class="r {cls}">{sign}${net:,.0f}</td>'

    def _spreads_html(spread_list: list[dict]) -> str:
        import math as _math
        if not spread_list:
            return "<p class='muted'>No spreads detected.</p>"
        hdr = (
            "<tr><th>Symbol</th><th>Structure</th><th>Legs</th>"
            "<th class='r'>DTE</th><th class='r'>Spot</th><th>Moneyness</th>"
            "<th class='r'>Net Credit</th><th class='r'>Max Risk</th>"
            "<th>Status</th></tr>"
        )
        rows = ""
        for s in spread_list:
            spot = s.get("spot", 0)
            spot_str = f"${spot:,.2f}" if spot and not _math.isnan(spot) else "—"
            rows += (
                f"<tr>"
                f"<td><strong>{s['symbol']}</strong></td>"
                f"<td>{_spread_type_pill(s['structure_type'])}</td>"
                + _spread_legs_cell(s)
                + f"<td class='r'>{s['dte']}d</td>"
                f"<td class='r'>{spot_str}</td>"
                + _spread_moneyness_cell(s)
                + _spread_credit_cell(s['net_credit'])
                + f"<td class='r'>${s['max_loss']:,.0f}</td>"
                + f"<td>{_pill_status(s.get('flags', []))}</td>"
                + "</tr>"
            )
        return f"<table>{hdr}{rows}</table>"

    total_spread_credit = sum(s["net_credit"] for s in spreads)
    n_condors    = sum(1 for s in spreads if s["structure_type"] == "Iron Condor")
    n_bcall      = sum(1 for s in spreads if s["structure_type"] == "Bear Call Spread")
    n_bput       = sum(1 for s in spreads if s["structure_type"] == "Bull Put Spread")
    spread_label_parts = []
    if n_condors: spread_label_parts.append(f"{n_condors} Iron Condor{'s' if n_condors>1 else ''}")
    if n_bcall:   spread_label_parts.append(f"{n_bcall} Bear Call Spread{'s' if n_bcall>1 else ''}")
    if n_bput:    spread_label_parts.append(f"{n_bput} Bull Put Spread{'s' if n_bput>1 else ''}")
    spread_section_title = " &middot; ".join(spread_label_parts) if spread_label_parts else "Spreads"
    spreads_html_block = _spreads_html(spreads)

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
    <h1>Winzinvest — {'Morning Brief' if edition == 'morning' else 'Daily Close'}</h1>
    <p>{now_str}</p>
    {pace_line_html}
  </div>
  <div class="body">

    {market_summary_html}
    {summary_bar}
    {alert_html}

    <h2>Long Stocks ({len(long_stocks)} positions &middot; sorted by return)</h2>
    {long_stock_html}

    {short_section}

    {'<h2>Spreads &amp; Condors (' + spread_section_title + ' &middot; ' + _money(total_spread_credit) + ' net credit)</h2>' + spreads_html_block if spreads else ''}

    <h2>Covered Calls ({len(cc)} positions &middot; {_money(sum(r['total_prem'] for r in cc))} premium)</h2>
    {cc_html}

    <h2>Cash-Secured Puts ({len(csps)} positions &middot; {_money(sum(r['total_prem'] for r in csps))} premium &middot; {_money(total_assign)} obligation)</h2>
    {csp_html}

    {longs_html}

  </div>
  <div class="ft">
    Winzinvest &middot; Live data from Interactive Brokers &middot; Prices via yfinance &middot; {datetime.now().strftime('%Y-%m-%d %H:%M MT')}
    {'<br><br><a href="https://winzinvest.com/api/unsubscribe?email=' + recipient_email + '" style="color: #adb5bd; font-size: 10px; text-decoration: underline;">Unsubscribe</a>' if recipient_email else ''}
  </div>
</div>
</body></html>"""
    return html


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Winzinvest Daily Positions Email")
    parser.add_argument("--preview",  action="store_true", help="Write HTML to /tmp, skip send")
    parser.add_argument("--morning",  action="store_true", help="Morning Brief edition (8 AM)")
    parser.add_argument("--evening",  action="store_true", help="Daily Close edition (2 PM, default)")
    args = parser.parse_args()
    edition = "morning" if args.morning else "evening"

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

    # Load recipient for unsubscribe link
    from email_helper import load_email_config
    email_config = load_email_config()
    recipient_email = email_config.get('to_email', '')

    html      = build_html(enriched_stocks, enriched_options, edition=edition, recipient_email=recipient_email)
    today_str = date.today().strftime("%b %d, %Y")
    edition_label = "Morning Brief" if edition == "morning" else "Daily Close"
    subject   = f"Winzinvest {edition_label} — {today_str}"

    if args.preview:
        preview_path = Path(f"/tmp/positions_email_{edition}_preview.html")
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
