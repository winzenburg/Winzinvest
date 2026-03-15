#!/usr/bin/env python3
"""
Scenario Engine — Stress-Test the Portfolio
============================================
Answers the question: "What happens to my portfolio if X occurs?"

Scenarios modelled:
  1. Energy sector  -15%  (moderate pullback)
  2. Energy sector  -30%  (severe drawdown / oil crash)
  3. Broad market   -10%  (correction)
  4. VIX spikes to  +40   (volatility shock)
  5. Energy sector  +10%  (covered calls get called away)

For each scenario the engine computes:
  • P&L from stock positions (beta * price change)
  • P&L from options (delta * price change + theta credit)
  • Net portfolio impact in dollars and % of NLV
  • Plain-English explanation and recommended action

Output: logs/scenario_results.json
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import yfinance as yf

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

SCRIPTS_DIR = Path(__file__).resolve().parent
TRADING_DIR  = SCRIPTS_DIR.parent
LOGS_DIR     = TRADING_DIR / "logs"
SNAPSHOT_PATH = LOGS_DIR / "dashboard_snapshot.json"
GREEKS_PATH   = LOGS_DIR / "portfolio_greeks.json"
OUTPUT_PATH   = LOGS_DIR / "scenario_results.json"

# ── Sector → scenario shock mapping ──────────────────────────────────────────

# Each scenario is {id, label, shocks: {sector: pct_change, ...}, vix_change}
SCENARIOS = [
    {
        "id":    "energy_down_15",
        "label": "Energy -15% (moderate pullback)",
        "shocks": {"Energy": -0.15, "ETF": -0.05, "Hedge": +0.08},
        "vix_change": +8,
        "color": "orange",
    },
    {
        "id":    "energy_down_30",
        "label": "Energy -30% (oil crash / severe)",
        "shocks": {"Energy": -0.30, "ETF": -0.12, "Hedge": +0.20},
        "vix_change": +20,
        "color": "red",
    },
    {
        "id":    "market_down_10",
        "label": "Market -10% (broad correction)",
        "shocks": {"Energy": -0.10, "ETF": -0.08, "Consumer Staples": -0.05,
                   "Technology": -0.12, "Healthcare": -0.06, "Materials": -0.09,
                   "Industrials": -0.09, "Consumer Discretionary": -0.11,
                   "Hedge": +0.25},
        "vix_change": +15,
        "color": "red",
    },
    {
        "id":    "vix_spike",
        "label": "VIX spikes to 40 (volatility shock)",
        "shocks": {"Energy": -0.08, "ETF": -0.05, "Hedge": +0.30},
        "vix_change": +20,
        "color": "orange",
    },
    {
        "id":    "energy_up_10",
        "label": "Energy +10% (covered calls capped)",
        "shocks": {"Energy": +0.10, "ETF": +0.04, "Hedge": -0.10},
        "vix_change": -3,
        "color": "green",
    },
    {
        "id":    "energy_up_20",
        "label": "Energy +20% (strong rally)",
        "shocks": {"Energy": +0.20, "ETF": +0.08, "Hedge": -0.15},
        "vix_change": -5,
        "color": "green",
    },
]

# ── Spot price cache ──────────────────────────────────────────────────────────

_spot_cache: dict[str, float] = {}

def get_spot(ticker: str) -> float:
    if ticker in _spot_cache:
        return _spot_cache[ticker]
    try:
        price = float(yf.Ticker(ticker).fast_info.last_price or 0)
        _spot_cache[ticker] = price
        return price
    except Exception:
        return 0.0


# ── Stock P&L under a shock ──────────────────────────────────────────────────

def _stock_pnl(pos: dict, shocks: dict[str, float]) -> float:
    sector = pos.get("sector", "Unknown")
    shock  = shocks.get(sector, 0.0)
    mkt    = float(pos.get("market_value", 0))
    return mkt * shock


# ── Option P&L under a shock ─────────────────────────────────────────────────

def _option_pnl(
    pos: dict,
    greeks_by_symbol: dict[str, dict],
    shocks: dict[str, float],
    vix_change: float,
) -> float:
    sym    = pos.get("symbol", "")
    g_data = greeks_by_symbol.get(sym)
    if not g_data:
        return 0.0

    ticker = sym.split(" ")[0]
    sector = pos.get("sector", "Options")

    # Map option underlying to a sector
    # (options sector is "Options" — derive from underlying ticker's sector)
    # We use the "Energy" shock for energy underlyings, etc.
    # Simple approach: use the same sector as the underlying stock position
    underlying_shock = shocks.get("Energy", 0.0)  # default to energy (most common here)
    for s, shock in shocks.items():
        if s in ("Energy", "Technology", "Consumer Staples", "Materials",
                 "Healthcare", "Industrials", "Consumer Discretionary", "ETF"):
            underlying_shock = shock
            break

    S = g_data.get("spot", 100.0)
    price_change = S * underlying_shock

    dollar_delta = g_data.get("dollar_delta", 0.0)
    dollar_gamma = g_data.get("dollar_gamma", 0.0)
    dollar_vega  = g_data.get("dollar_vega", 0.0)

    # Taylor expansion: dP ≈ delta*dS + 0.5*gamma*dS² + vega*dVol
    pnl = (
        dollar_delta * price_change
        + 0.5 * dollar_gamma * price_change ** 2
        + dollar_vega * vix_change
    )
    return pnl


# ── Run one scenario ──────────────────────────────────────────────────────────

def run_scenario(
    scenario: dict,
    positions: list[dict],
    greeks_by_symbol: dict[str, dict],
    nlv: float,
) -> dict[str, Any]:
    shocks     = scenario["shocks"]
    vix_change = scenario.get("vix_change", 0)

    stock_pnl  = 0.0
    option_pnl = 0.0
    breakdown: list[dict] = []

    for pos in positions:
        sec = pos.get("sec_type", "")
        sym = pos.get("symbol", "")

        if sec == "STK":
            pnl = _stock_pnl(pos, shocks)
            stock_pnl += pnl
            if abs(pnl) > 200:
                breakdown.append({
                    "symbol": sym,
                    "type": "stock",
                    "pnl": round(pnl, 2),
                })
        elif sec == "OPT":
            # Find the underlying sector from the stock position with same ticker
            base_ticker = sym.split(" ")[0]
            underlying_sector = "Energy"
            for p in positions:
                if p.get("symbol") == base_ticker and p.get("sec_type") == "STK":
                    underlying_sector = p.get("sector", "Energy")
                    break
            shock = shocks.get(underlying_sector, shocks.get("Energy", 0.0))
            adjusted_shocks = dict(shocks)
            adjusted_shocks["_underlying"] = shock

            pnl = _option_pnl(pos, greeks_by_symbol, adjusted_shocks, vix_change)
            option_pnl += pnl
            if abs(pnl) > 100:
                breakdown.append({
                    "symbol": sym,
                    "type": "option",
                    "pnl": round(pnl, 2),
                })

    total_pnl = stock_pnl + option_pnl
    pnl_pct   = (total_pnl / nlv * 100) if nlv > 0 else 0

    breakdown.sort(key=lambda x: x["pnl"])

    # ── Plain-English recommendation ──────────────────────────────────────────
    if total_pnl < -nlv * 0.10:
        severity  = "critical"
        action    = (
            "This scenario causes a loss exceeding your 10% max-drawdown limit. "
            "Consider buying protective puts on XOP or reducing Energy exposure by ~30%."
        )
    elif total_pnl < -nlv * 0.05:
        severity  = "warning"
        action    = (
            "This loss would trigger your Tier 2 drawdown breaker. "
            "Hedging with XOP puts or trimming the largest energy position (MPC) could reduce this by ~40%."
        )
    elif total_pnl < 0:
        severity  = "info"
        action    = "Loss is within acceptable risk parameters. No immediate action required."
    else:
        severity  = "positive"
        action    = (
            "Portfolio benefits from this scenario. "
            "Note: covered calls will cap upside on energy stocks that move above their strike."
        )

    return {
        "scenario_id":    scenario["id"],
        "label":          scenario["label"],
        "color":          scenario["color"],
        "stock_pnl":      round(stock_pnl, 2),
        "option_pnl":     round(option_pnl, 2),
        "total_pnl":      round(total_pnl, 2),
        "pnl_pct":        round(pnl_pct, 2),
        "severity":       severity,
        "action":         action,
        "top_losers":     breakdown[:5],
        "top_gainers":    list(reversed(breakdown[-3:])),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def run_all_scenarios() -> dict[str, Any]:
    if not SNAPSHOT_PATH.exists():
        logger.error("dashboard_snapshot.json not found")
        return {}

    snap       = json.loads(SNAPSHOT_PATH.read_text())
    positions  = snap.get("positions", {}).get("list", [])
    nlv        = snap["account"].get("net_liquidation", 164000.0)

    # Load Greeks by symbol for option P&L calculation
    greeks_by_symbol: dict[str, dict] = {}
    if GREEKS_PATH.exists():
        greeks_data = json.loads(GREEKS_PATH.read_text())
        for g in greeks_data.get("positions", []):
            greeks_by_symbol[g["symbol"]] = g
    else:
        logger.warning("portfolio_greeks.json not found — option P&L estimates will be rough")

    results = []
    for scenario in SCENARIOS:
        r = run_scenario(scenario, positions, greeks_by_symbol, nlv)
        results.append(r)
        logger.info("%-35s  %+8.0f  (%+.1f%%)", scenario["label"], r["total_pnl"], r["pnl_pct"])

    # Summary: worst case
    worst = min(results, key=lambda x: x["total_pnl"])
    best  = max(results, key=lambda x: x["total_pnl"])

    output = {
        "generated_at": datetime.now().isoformat(),
        "nlv":          nlv,
        "scenarios":    results,
        "worst_case":   {"label": worst["label"], "pnl": worst["total_pnl"], "pnl_pct": worst["pnl_pct"]},
        "best_case":    {"label": best["label"],  "pnl": best["total_pnl"],  "pnl_pct": best["pnl_pct"]},
    }

    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    logger.info("Scenarios written → %s", OUTPUT_PATH)
    return output


if __name__ == "__main__":
    result = run_all_scenarios()
    if result:
        print(f"\n{'='*65}")
        print(f"  {'SCENARIO':<40} {'P&L':>10}  {'% NLV':>8}  SEVERITY")
        print(f"  {'-'*60}")
        for s in result["scenarios"]:
            icon = {"critical": "🚨", "warning": "⚠️", "info": "ℹ️", "positive": "✅"}.get(s["severity"], "•")
            print(f"  {s['label']:<40} ${s['total_pnl']:>9,.0f}  {s['pnl_pct']:>+7.1f}%  {icon}")
        print(f"{'='*65}")
        print(f"\n  Worst case: {result['worst_case']['label']}")
        print(f"    → ${result['worst_case']['pnl']:,.0f} ({result['worst_case']['pnl_pct']:+.1f}% of NLV)")
