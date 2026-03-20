#!/usr/bin/env python3
"""
Portfolio Greeks Engine
=======================
Calculates Black-Scholes Greeks for every short option in the portfolio,
aggregates them at the book level, and writes portfolio_greeks.json.

Key outputs:
  net_delta       — dollar move per 1% SPY/market move (proxy)
  net_theta       — dollars earned per calendar day from time decay
  net_gamma       — how fast delta changes (negative = short gamma = risky near expiry)
  net_vega        — dollar change per 1-point VIX move
  theta_annual    — annualised projection of theta income
  decisions       — plain-English observations driven purely by the numbers
"""

import json
import logging
import math
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yfinance as yf

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

SCRIPTS_DIR = Path(__file__).resolve().parent
TRADING_DIR = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from notifications import notify_event  # noqa: E402
LOGS_DIR = TRADING_DIR / "logs"
SNAPSHOT_PATH = LOGS_DIR / "dashboard_snapshot.json"
OUTPUT_PATH = LOGS_DIR / "portfolio_greeks.json"

# ── Black-Scholes helpers ──────────────────────────────────────────────────────

def _norm_cdf(x: float) -> float:
    """Standard normal CDF via error function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def bs_greeks(
    S: float,       # underlying spot price
    K: float,       # strike
    T: float,       # time to expiry in years
    r: float,       # risk-free rate (annualised)
    sigma: float,   # implied volatility (annualised)
    right: str,     # "C" or "P"
) -> dict[str, float]:
    """Return delta, gamma, theta (per calendar day), vega (per 1-pt vol move)."""
    if T <= 0 or sigma <= 0 or S <= 0:
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}

    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    nd1 = _norm_cdf(d1)
    nd2 = _norm_cdf(d2)
    nd1_neg = _norm_cdf(-d1)
    nd2_neg = _norm_cdf(-d2)
    pdf_d1 = _norm_pdf(d1)

    if right.upper() == "C":
        delta = nd1
        theta_raw = (
            -(S * pdf_d1 * sigma) / (2 * math.sqrt(T))
            - r * K * math.exp(-r * T) * nd2
        )
    else:
        delta = nd1 - 1.0
        theta_raw = (
            -(S * pdf_d1 * sigma) / (2 * math.sqrt(T))
            + r * K * math.exp(-r * T) * nd2_neg
        )

    gamma = pdf_d1 / (S * sigma * math.sqrt(T))
    # theta per calendar day (divide by 365)
    theta = theta_raw / 365.0
    # vega per 1 percentage-point move in vol (divide by 100)
    vega = S * pdf_d1 * math.sqrt(T) / 100.0

    return {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega}


# ── Option symbol parser ───────────────────────────────────────────────────────

def parse_option_symbol(symbol: str) -> dict[str, Any] | None:
    """Parse 'ADM 75.0C 202604' → {ticker, strike, right, expiry_date}."""
    parts = symbol.strip().split()
    if len(parts) < 3:
        return None
    ticker = parts[0]
    try:
        strike_right = parts[1]   # e.g. "75.0C" or "185.0P"
        right = strike_right[-1].upper()
        strike = float(strike_right[:-1])
        expiry_str = parts[2]     # e.g. "202604"
        if len(expiry_str) == 6:
            # YYYYMM — use last trading day (third Friday) approximation: use 15th
            expiry_date = date(int(expiry_str[:4]), int(expiry_str[4:6]), 21)
        elif len(expiry_str) == 8:
            expiry_date = date(int(expiry_str[:4]), int(expiry_str[4:6]), int(expiry_str[6:8]))
        else:
            return None
        return {"ticker": ticker, "strike": strike, "right": right, "expiry_date": expiry_date}
    except (ValueError, IndexError):
        return None


# ── Implied vol estimation ─────────────────────────────────────────────────────

def estimate_iv(ticker: str, market_price: float, S: float, K: float,
                T: float, r: float, right: str) -> float:
    """Binary-search IV so that BS price matches market_price. Falls back to 30%."""
    if T <= 0 or market_price <= 0:
        return 0.30

    lo, hi = 0.01, 5.0
    for _ in range(50):
        mid = (lo + hi) / 2.0
        g = bs_greeks(S, K, T, r, mid, right)
        # Rough BS price
        d1 = (math.log(S / K) + (r + 0.5 * mid ** 2) * T) / (mid * math.sqrt(T))
        d2 = d1 - mid * math.sqrt(T)
        if right.upper() == "C":
            price = S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
        else:
            price = K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)

        if abs(price - market_price) < 0.001:
            return mid
        if price < market_price:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


# ── Spot price cache ───────────────────────────────────────────────────────────

_spot_cache: dict[str, float] = {}

def get_spot(ticker: str) -> float:
    if ticker in _spot_cache:
        return _spot_cache[ticker]
    try:
        info = yf.Ticker(ticker).fast_info
        price = float(info.last_price or info.previous_close or 0)
        _spot_cache[ticker] = price
        return price
    except Exception:
        return 0.0


# ── Main Greeks calculation ────────────────────────────────────────────────────

def calculate_portfolio_greeks(snapshot: dict[str, Any]) -> dict[str, Any]:
    positions = snapshot.get("positions", {}).get("list", [])
    nlv = snapshot["account"].get("net_liquidation", 164000.0)
    r = 0.053  # ~current Fed Funds rate

    today = date.today()
    book: list[dict] = []

    net_delta = 0.0
    net_theta = 0.0
    net_gamma = 0.0
    net_vega  = 0.0

    for pos in positions:
        if pos.get("sec_type") != "OPT":
            continue

        sym = pos.get("symbol", "")
        parsed = parse_option_symbol(sym)
        if not parsed:
            continue

        ticker      = parsed["ticker"]
        strike      = parsed["strike"]
        right       = parsed["right"]
        expiry_date = parsed["expiry_date"]
        qty         = float(pos.get("quantity", 0))
        mkt_price   = abs(float(pos.get("market_price", 0)))
        multiplier  = 100.0
        sign        = 1.0 if qty > 0 else -1.0  # +1 long, -1 short

        days_to_exp = (expiry_date - today).days
        T = max(days_to_exp, 0) / 365.0

        S = get_spot(ticker)
        if S <= 0:
            logger.warning("Could not get spot for %s — skipping", ticker)
            continue

        iv = estimate_iv(ticker, mkt_price, S, strike, T, r, right)
        g  = bs_greeks(S, strike, T, r, iv, right)

        contracts = abs(qty)
        # Dollar delta: how much the option VALUE changes per $1 move in underlying
        dollar_delta = g["delta"] * contracts * multiplier * sign
        # Dollar theta: $/day collected (positive = earning decay)
        dollar_theta = g["theta"] * contracts * multiplier * sign
        # Dollar gamma: change in dollar_delta per $1 move
        dollar_gamma = g["gamma"] * contracts * multiplier * sign
        # Dollar vega: $ change per 1pp change in IV
        dollar_vega  = g["vega"]  * contracts * multiplier * sign

        net_delta += dollar_delta
        net_theta += dollar_theta
        net_gamma += dollar_gamma
        net_vega  += dollar_vega

        book.append({
            "symbol":       sym,
            "ticker":       ticker,
            "right":        right,
            "strike":       strike,
            "expiry":       expiry_date.isoformat(),
            "days_to_exp":  days_to_exp,
            "qty":          qty,
            "side":         "SHORT" if qty < 0 else "LONG",
            "spot":         round(S, 2),
            "iv_pct":       round(iv * 100, 1),
            "delta":        round(g["delta"], 4),
            "dollar_delta": round(dollar_delta, 2),
            "dollar_theta": round(dollar_theta, 2),
            "dollar_gamma": round(dollar_gamma, 4),
            "dollar_vega":  round(dollar_vega, 2),
        })

    # Sort by absolute theta contribution
    book.sort(key=lambda x: abs(x["dollar_theta"]), reverse=True)

    # ── Decisions ─────────────────────────────────────────────────────────────
    decisions: list[dict] = []

    theta_monthly  = net_theta * 30
    theta_annual   = net_theta * 365
    theta_yield    = (theta_annual / nlv * 100) if nlv > 0 else 0

    # Delta risk: net_delta / NLV = what % of portfolio moves per $1 underlying
    delta_pct_nlv  = (net_delta / nlv * 100) if nlv > 0 else 0
    vega_pct_nlv   = (net_vega / nlv * 100)  if nlv > 0 else 0

    # Theta health
    if net_theta >= 0:
        decisions.append({
            "category": "income",
            "priority": "info",
            "title": "Theta income on track",
            "detail": (
                f"Portfolio is collecting ${abs(net_theta):.0f}/day in options decay "
                f"(${abs(theta_monthly):,.0f}/month, ${abs(theta_annual):,.0f}/year — "
                f"{abs(theta_yield):.1f}% annual yield on NLV)."
            ),
            "action": "monitor",
        })
    else:
        decisions.append({
            "category": "opportunity",
            "priority": "medium",
            "title": "Net theta is negative — portfolio is buying premium",
            "detail": (
                f"Portfolio is paying ${abs(net_theta):.0f}/day in options decay. "
                "This usually means protective puts are dominating. "
                "Consider whether the hedge cost is justified vs. current risk."
            ),
            "action": "review",
        })

    # Delta exposure
    if abs(delta_pct_nlv) > 20:
        direction = "long" if delta_pct_nlv > 0 else "short"
        decisions.append({
            "category": "risk",
            "priority": "warning",
            "title": f"Portfolio is significantly net {direction} ({delta_pct_nlv:+.1f}% delta/NLV)",
            "detail": (
                f"A 10% market move adds/subtracts ~${abs(net_delta * 10):.0f} to portfolio value. "
                + ("Consider protective puts on SPY or XOP to reduce directional risk."
                   if delta_pct_nlv > 0 else
                   "Consider trimming short positions if rally risk is elevated.")
            ),
            "action": "review",
        })

    # Gamma risk — expiring options
    expiring_soon = [b for b in book if 0 < b["days_to_exp"] <= 7]
    if expiring_soon:
        syms = ", ".join(b["symbol"] for b in expiring_soon[:5])
        decisions.append({
            "category": "risk",
            "priority": "warning",
            "title": f"{len(expiring_soon)} option(s) expire within 7 days",
            "detail": (
                f"Short options near expiry carry elevated assignment and gamma risk: {syms}. "
                "Consider rolling these forward now rather than waiting for expiry."
            ),
            "action": "review",
            "symbols": [b["symbol"] for b in expiring_soon],
        })

    # Delta drift — per-position check: short calls with |delta| > 0.50 (deep ITM / assignment risk)
    high_delta_positions = [
        b for b in book
        if b.get("side") == "SHORT" and b.get("right") == "C" and abs(b.get("delta", 0)) > 0.50
    ]
    if high_delta_positions:
        syms = ", ".join(
            f"{b['symbol']} (δ={b['delta']:+.2f}, {b['days_to_exp']}d)"
            for b in high_delta_positions[:5]
        )
        decisions.append({
            "category": "risk",
            "priority": "urgent",
            "title": f"{len(high_delta_positions)} short call(s) have delta > 0.50 — assignment risk elevated",
            "detail": (
                f"Short calls with delta above 0.50 are deep in-the-money and carry meaningful "
                f"early assignment risk, especially near ex-dividend dates: {syms}. "
                "Consider rolling up-and-out to reduce delta and extend duration."
            ),
            "action": "roll",
            "symbols": [b["symbol"] for b in high_delta_positions],
        })
        notify_event(
            "assignment_risk",
            subject=f"⚠️ Delta Drift Alert: {len(high_delta_positions)} call(s) > 0.50 delta",
            body=(
                f"{len(high_delta_positions)} short call position(s) have drifted above delta 0.50 "
                f"(deep ITM — elevated assignment risk):\n\n  {syms}\n\n"
                "Action: Roll up-and-out to reduce delta exposure and collect additional credit."
            ),
            urgent=True,
        )

    # Vega risk — high vol exposure
    if abs(vega_pct_nlv) > 1.5:
        direction = "long" if net_vega > 0 else "short"
        decisions.append({
            "category": "risk",
            "priority": "info",
            "title": f"Portfolio is net {direction} volatility (vega {vega_pct_nlv:+.1f}% of NLV)",
            "detail": (
                f"A 5-point VIX move changes portfolio value by ~${abs(net_vega * 5):.0f}. "
                + ("Short vol benefits when VIX falls but gets hurt in volatility spikes."
                   if net_vega < 0 else
                   "Long vol benefits in sell-offs but costs carry in calm markets.")
            ),
            "action": "monitor",
        })

    # Low theta warning
    if 0 <= net_theta < 50:
        decisions.append({
            "category": "opportunity",
            "priority": "medium",
            "title": "Theta income below $50/day — consider selling more premium",
            "detail": (
                f"Currently collecting only ${net_theta:.0f}/day. "
                "Check for uncovered long positions or upcoming expirations that could be rolled forward."
            ),
            "action": "review",
        })

    result = {
        "generated_at": datetime.now().isoformat(),
        "net_delta":     round(net_delta, 2),
        "net_theta":     round(net_theta, 2),
        "net_gamma":     round(net_gamma, 4),
        "net_vega":      round(net_vega, 2),
        "theta_monthly": round(theta_monthly, 2),
        "theta_annual":  round(theta_annual, 2),
        "theta_yield_pct": round(theta_yield, 2),
        "delta_pct_nlv": round(delta_pct_nlv, 2),
        "vega_pct_nlv":  round(vega_pct_nlv, 2),
        "positions":     book,
        "decisions":     decisions,
    }

    OUTPUT_PATH.write_text(json.dumps(result, indent=2))
    logger.info("Greeks written → %s", OUTPUT_PATH)
    return result


if __name__ == "__main__":
    if not SNAPSHOT_PATH.exists():
        logger.error("dashboard_snapshot.json not found — run dashboard_data_aggregator.py first")
        sys.exit(1)
    snap = json.loads(SNAPSHOT_PATH.read_text())
    result = calculate_portfolio_greeks(snap)
    print(f"\n{'='*50}")
    print(f"  NET THETA   : ${result['net_theta']:>8.2f} /day  (${result['theta_monthly']:>8,.0f}/month)")
    print(f"  NET DELTA   : ${result['net_delta']:>8.2f}        ({result['delta_pct_nlv']:+.1f}% of NLV)")
    print(f"  NET GAMMA   :  {result['net_gamma']:>8.4f}")
    print(f"  NET VEGA    : ${result['net_vega']:>8.2f}        ({result['vega_pct_nlv']:+.1f}% of NLV)")
    print(f"  THETA YIELD : {result['theta_yield_pct']:.1f}% annualised on NLV")
    print(f"{'='*50}")
    print(f"\nDecisions ({len(result['decisions'])}):")
    for d in result["decisions"]:
        icon = {"info": "ℹ️", "warning": "⚠️", "medium": "📋", "critical": "🚨"}.get(d["priority"], "•")
        print(f"  {icon}  [{d['category'].upper()}] {d['title']}")
        print(f"       {d['detail'][:120]}...")
