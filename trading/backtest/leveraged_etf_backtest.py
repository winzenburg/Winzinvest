#!/usr/bin/env python3
"""
Leveraged ETF backtest — regime-aware evaluation.

Tests each candidate ETF under three strategies:
  1. Buy-and-hold (baseline)
  2. Regime-gated: only hold during STRONG_UPTREND / CHOPPY, exit on DOWNTREND
  3. Trend-only: only hold when ETF is above its 20-day SMA

Measures: CAGR, Sharpe, max drawdown, Calmar, win-rate by regime.
Goal: identify which ETFs help reach 40%+ CAGR net of drawdown risk.

Usage:
    cd trading && python -m backtest.leveraged_etf_backtest --years 5
"""

from __future__ import annotations

import argparse
import json
import logging
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

GOAL_CAGR = 0.40  # 40% annual target

# ── Candidate universe ──────────────────────────────────────────────────────

CANDIDATES: Dict[str, Dict] = {
    # Equity index
    "TQQQ": {"group": "Equity Index",    "leverage": 3, "underlying": "QQQ",  "note": "Nasdaq 100 3x"},
    "UPRO": {"group": "Equity Index",    "leverage": 3, "underlying": "SPY",  "note": "S&P 500 3x"},
    "SPXL": {"group": "Equity Index",    "leverage": 3, "underlying": "SPY",  "note": "S&P 500 3x (Direxion)"},
    "UDOW": {"group": "Equity Index",    "leverage": 3, "underlying": "DIA",  "note": "Dow Jones 3x"},
    # International
    "KORU": {"group": "International",   "leverage": 3, "underlying": "EWY",  "note": "South Korea 3x"},
    "YINN": {"group": "International",   "leverage": 3, "underlying": "FXI",  "note": "China large-cap 3x"},
    "INDL": {"group": "International",   "leverage": 2, "underlying": "INDA", "note": "India 2x"},
    "EDC":  {"group": "International",   "leverage": 3, "underlying": "VWO",  "note": "EM 3x"},
    "EURL": {"group": "International",   "leverage": 2, "underlying": "EZU",  "note": "Europe 2x"},
    # Gold / Precious metals
    "GDXU": {"group": "Gold Miners",     "leverage": 3, "underlying": "GDX",  "note": "Gold miners 3x"},
    "NUGT": {"group": "Gold Miners",     "leverage": 2, "underlying": "GDX",  "note": "Gold miners 2x"},
    # Energy
    "ERX":  {"group": "Energy",          "leverage": 2, "underlying": "XLE",  "note": "Energy equities 2x"},
    "GUSH": {"group": "Energy",          "leverage": 2, "underlying": "XOP",  "note": "E&P 2x"},
    # Commodities
    "UCO":  {"group": "Commodities",     "leverage": 2, "underlying": "USO",  "note": "Crude oil 2x"},
    # Sectors
    "SOXL": {"group": "Semis/Tech",      "leverage": 3, "underlying": "SOXX", "note": "Semiconductors 3x"},
    "FAS":  {"group": "Financials",      "leverage": 3, "underlying": "XLF",  "note": "Financials 3x"},
    "LABU": {"group": "Biotech",         "leverage": 3, "underlying": "IBB",  "note": "Biotech 3x"},
    "TNA":  {"group": "Small Cap",       "leverage": 3, "underlying": "IWM",  "note": "Russell 2000 3x"},
}

# Benchmark
BENCHMARKS = ["SPY", "QQQ"]

# ── Regime detection ────────────────────────────────────────────────────────

def detect_regime_series(spy: pd.Series, vix: pd.Series) -> pd.Series:
    """Daily regime label matching regime_detector.py logic."""
    sma200 = spy.rolling(200).mean()
    sma200_std = spy.pct_change().rolling(20).std()
    dist = (spy - sma200) / sma200

    regimes = []
    for i in range(len(spy)):
        d = dist.iloc[i] if not pd.isna(dist.iloc[i]) else 0.0
        v = vix.iloc[i] if not pd.isna(vix.iloc[i]) else 20.0
        std = sma200_std.iloc[i] if not pd.isna(sma200_std.iloc[i]) else 0.01

        if v > 30 and abs(d) < 0.01 and std > 0.02:
            regimes.append("UNFAVORABLE")
        elif d < -0.02 and v > 20:
            regimes.append("STRONG_DOWNTREND")
        elif d > 0.02 and v < 15:
            regimes.append("STRONG_UPTREND")
        elif d < -0.02 and v <= 20:
            regimes.append("MIXED")
        else:
            regimes.append("CHOPPY")

    return pd.Series(regimes, index=spy.index)


# ── Backtest engine ─────────────────────────────────────────────────────────

@dataclass
class BacktestResult:
    symbol: str
    strategy: str
    cagr: float
    sharpe: float
    max_drawdown: float
    calmar: float
    total_return: float
    years: float
    win_rate: float
    avg_daily_return: float
    n_trading_days: int
    regime_returns: Dict[str, float] = field(default_factory=dict)
    hits_goal: bool = False


def _metrics(equity_curve: pd.Series, rf: float = 0.05) -> Tuple[float, float, float, float, float]:
    """Returns (cagr, sharpe, max_drawdown, calmar, total_return)."""
    if len(equity_curve) < 2:
        return 0.0, 0.0, 0.0, 0.0, 0.0

    total_return = float(equity_curve.iloc[-1] / equity_curve.iloc[0] - 1)
    years = len(equity_curve) / 252.0
    cagr = float((1 + total_return) ** (1 / years) - 1) if years > 0 else 0.0

    daily_rets = equity_curve.pct_change().dropna()
    excess = daily_rets - rf / 252
    sharpe = float(excess.mean() / excess.std() * np.sqrt(252)) if excess.std() > 0 else 0.0

    rolling_max = equity_curve.cummax()
    dd = (equity_curve - rolling_max) / rolling_max
    max_dd = float(dd.min())

    calmar = float(cagr / abs(max_dd)) if max_dd < 0 else 0.0

    return cagr, sharpe, max_dd, calmar, total_return


def backtest_etf(
    prices: pd.Series,
    regime_series: pd.Series,
    symbol: str,
) -> List[BacktestResult]:
    """Run three strategies on a single ETF price series."""
    results = []
    daily_rets = prices.pct_change().fillna(0)
    sma20 = prices.rolling(20).mean()
    n_days = len(prices)
    years = n_days / 252.0

    # ── Strategy 1: Buy-and-hold ──────────────────────────────────────────
    eq_bh = (1 + daily_rets).cumprod()
    cagr, sharpe, mdd, calmar, tot_ret = _metrics(eq_bh)
    win_rate = float((daily_rets > 0).sum() / max(len(daily_rets), 1))
    results.append(BacktestResult(
        symbol=symbol, strategy="buy_hold",
        cagr=cagr, sharpe=sharpe, max_drawdown=mdd, calmar=calmar,
        total_return=tot_ret, years=years, win_rate=win_rate,
        avg_daily_return=float(daily_rets.mean()),
        n_trading_days=n_days,
        hits_goal=cagr >= GOAL_CAGR,
    ))

    # ── Strategy 2: Regime-gated (hold only in non-bear regimes) ─────────
    ALLOWED = {"STRONG_UPTREND", "CHOPPY", "MIXED"}
    aligned_regime = regime_series.reindex(prices.index, method="ffill")
    mask_regime = aligned_regime.isin(ALLOWED).astype(float)
    # Exit smoothly — hold signal from prior day
    mask_regime = mask_regime.shift(1).fillna(0)
    gated_rets = daily_rets * mask_regime
    eq_rg = (1 + gated_rets).cumprod()
    cagr_r, sharpe_r, mdd_r, calmar_r, tot_r = _metrics(eq_rg)
    win_r = float((gated_rets[gated_rets != 0] > 0).mean()) if (gated_rets != 0).any() else 0.0

    # Per-regime return contribution
    regime_contribs: Dict[str, float] = {}
    for reg in ["STRONG_UPTREND", "STRONG_DOWNTREND", "CHOPPY", "MIXED", "UNFAVORABLE"]:
        mask = (aligned_regime == reg)
        if mask.any():
            r_series = daily_rets[mask]
            regime_contribs[reg] = float(r_series.mean() * 252)  # annualised avg daily return

    results.append(BacktestResult(
        symbol=symbol, strategy="regime_gated",
        cagr=cagr_r, sharpe=sharpe_r, max_drawdown=mdd_r, calmar=calmar_r,
        total_return=tot_r, years=years, win_rate=win_r,
        avg_daily_return=float(gated_rets.mean()),
        n_trading_days=int(mask_regime.sum()),
        regime_returns=regime_contribs,
        hits_goal=cagr_r >= GOAL_CAGR,
    ))

    # ── Strategy 3: Trend-only (above 20-day SMA) ─────────────────────────
    trend_mask = (prices > sma20).astype(float).shift(1).fillna(0)
    trend_rets = daily_rets * trend_mask
    eq_tr = (1 + trend_rets).cumprod()
    cagr_t, sharpe_t, mdd_t, calmar_t, tot_t = _metrics(eq_tr)
    win_t = float((trend_rets[trend_rets != 0] > 0).mean()) if (trend_rets != 0).any() else 0.0
    results.append(BacktestResult(
        symbol=symbol, strategy="trend_only_sma20",
        cagr=cagr_t, sharpe=sharpe_t, max_drawdown=mdd_t, calmar=calmar_t,
        total_return=tot_t, years=years, win_rate=win_t,
        avg_daily_return=float(trend_rets.mean()),
        n_trading_days=int(trend_mask.sum()),
        hits_goal=cagr_t >= GOAL_CAGR,
    ))

    return results


# ── Data fetch ──────────────────────────────────────────────────────────────

def fetch_prices(symbols: List[str], years: int) -> pd.DataFrame:
    """Download adjusted close prices via yfinance."""
    import yfinance as yf

    end = datetime.today()
    start = end - timedelta(days=int(years * 365.25) + 30)
    log.info("Downloading %d symbols (%d years)...", len(symbols), years)

    raw = yf.download(
        symbols,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        auto_adjust=True,
        progress=False,
        threads=True,
    )

    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"]
    else:
        close = raw[["Close"]].rename(columns={"Close": symbols[0]})

    # Drop columns with >30% missing
    threshold = 0.70 * len(close)
    close = close.dropna(thresh=int(threshold), axis=1)
    close = close.ffill().bfill()
    return close


# ── Main ────────────────────────────────────────────────────────────────────

def run(years: int = 5) -> None:
    all_syms = list(CANDIDATES.keys()) + BENCHMARKS + ["^VIX"]
    prices_all = fetch_prices(all_syms, years)

    spy = prices_all.get("SPY", prices_all.get("spy"))
    vix = prices_all.get("^VIX", prices_all.get("VIX"))

    if spy is None:
        log.error("SPY data missing — cannot compute regimes")
        return

    if vix is None:
        log.warning("VIX data missing — using constant 20")
        vix = pd.Series(20.0, index=spy.index)

    spy = spy.dropna()
    vix = vix.reindex(spy.index).ffill().fillna(20.0)

    regime_series = detect_regime_series(spy, vix)
    log.info("Regime distribution:\n%s", regime_series.value_counts().to_string())

    all_results: List[BacktestResult] = []

    # Benchmark
    for bench in BENCHMARKS:
        if bench in prices_all.columns:
            bres = backtest_etf(prices_all[bench].dropna(), regime_series, bench)
            all_results.extend(bres)

    # ETF candidates
    available = [s for s in CANDIDATES if s in prices_all.columns]
    missing = [s for s in CANDIDATES if s not in prices_all.columns]
    if missing:
        log.warning("Missing data for: %s", ", ".join(missing))

    for sym in available:
        prices = prices_all[sym].dropna()
        if len(prices) < 120:
            log.warning("Skipping %s — insufficient history (%d days)", sym, len(prices))
            continue
        res = backtest_etf(prices, regime_series, sym)
        all_results.extend(res)
        bh = next(r for r in res if r.strategy == "buy_hold")
        rg = next(r for r in res if r.strategy == "regime_gated")
        log.info(
            "%-6s  BH CAGR=%+6.1f%%  RG CAGR=%+6.1f%%  MDD=%5.1f%%  Calmar=%.2f  %s",
            sym,
            bh.cagr * 100, rg.cagr * 100,
            rg.max_drawdown * 100,
            rg.calmar,
            "✅ GOAL" if rg.hits_goal else "",
        )

    # ── Build output ─────────────────────────────────────────────────────────
    output = _build_report(all_results, regime_series, years)

    out_path = RESULTS_DIR / "leveraged_etf_backtest.json"
    out_path.write_text(json.dumps(output, indent=2))
    log.info("Results saved → %s", out_path)
    _print_summary(output)


def _build_report(results: List[BacktestResult], regime_series: pd.Series, years: int) -> dict:
    regime_dist = regime_series.value_counts(normalize=True).to_dict()

    def _res_to_dict(r: BacktestResult) -> dict:
        return {
            "symbol": r.symbol,
            "strategy": r.strategy,
            "cagr_pct": round(r.cagr * 100, 2),
            "sharpe": round(r.sharpe, 3),
            "max_drawdown_pct": round(r.max_drawdown * 100, 2),
            "calmar": round(r.calmar, 3),
            "total_return_pct": round(r.total_return * 100, 2),
            "years": round(r.years, 2),
            "win_rate_pct": round(r.win_rate * 100, 1),
            "n_trading_days": r.n_trading_days,
            "hits_40pct_goal": r.hits_goal,
            "regime_annual_returns": {k: round(v * 100, 2) for k, v in r.regime_returns.items()},
        }

    all_dicts = [_res_to_dict(r) for r in results]

    # Filter to regime_gated strategy for ranking
    rg_results = [r for r in results if r.strategy == "regime_gated"]
    rg_results.sort(key=lambda r: r.cagr, reverse=True)

    # Top candidates that hit goal
    goal_hitters = [_res_to_dict(r) for r in rg_results if r.hits_goal]
    # Top 10 by CAGR regardless
    top10 = [_res_to_dict(r) for r in rg_results[:10]]

    # Score each: weighted combo of CAGR, Sharpe, Calmar, MDD
    def _score(r: BacktestResult) -> float:
        if r.cagr < -0.5 or r.sharpe < -2:
            return -999.0
        cagr_score  = min(r.cagr / GOAL_CAGR, 2.0) * 40          # 40 pts max
        sharpe_score = min(max(r.sharpe, 0), 3) / 3 * 30           # 30 pts max
        mdd_penalty  = max(r.max_drawdown * 100, -80) / 80 * 20    # 20 pts max (less negative = better)
        calmar_score = min(max(r.calmar, 0), 2) / 2 * 10           # 10 pts max
        return round(cagr_score + sharpe_score - mdd_penalty + calmar_score, 2)

    rg_scored = sorted(rg_results, key=_score, reverse=True)
    scored_list = [
        {**_res_to_dict(r), "composite_score": _score(r), "group": CANDIDATES.get(r.symbol, {}).get("group", "Benchmark")}
        for r in rg_scored
    ]

    return {
        "generated_at": datetime.now().isoformat(),
        "backtest_years": years,
        "goal_cagr_pct": GOAL_CAGR * 100,
        "regime_distribution_pct": {k: round(v * 100, 1) for k, v in regime_dist.items()},
        "candidates_tested": len([r for r in rg_results if r.symbol in CANDIDATES]),
        "candidates_hit_goal": len(goal_hitters),
        "all_strategies": all_dicts,
        "ranked_by_composite_score": scored_list,
        "goal_hitters_regime_gated": goal_hitters,
        "top10_by_cagr": top10,
    }


def _print_summary(output: dict) -> None:
    print("\n" + "=" * 72)
    print(f"  LEVERAGED ETF BACKTEST — {output['backtest_years']}yr  |  Goal: {output['goal_cagr_pct']:.0f}% CAGR")
    print("=" * 72)
    print(f"  Regime distribution: {output['regime_distribution_pct']}")
    print(f"  Candidates tested:   {output['candidates_tested']}")
    print(f"  Hit 40%+ goal:       {output['candidates_hit_goal']}\n")

    print(f"  {'SYMBOL':<7} {'GROUP':<18} {'CAGR%':>7} {'SHARPE':>7} {'MDD%':>7} {'CALMAR':>7} {'SCORE':>7}  GOAL?")
    print("  " + "-" * 68)
    for r in output["ranked_by_composite_score"]:
        if r["symbol"] in ("SPY", "QQQ"):
            continue
        goal = "✅" if r["hits_40pct_goal"] else "  "
        print(
            f"  {r['symbol']:<7} {r.get('group',''):<18} "
            f"{r['cagr_pct']:>6.1f}% "
            f"{r['sharpe']:>7.2f} "
            f"{r['max_drawdown_pct']:>6.1f}% "
            f"{r['calmar']:>7.2f} "
            f"{r['composite_score']:>7.1f}  {goal}"
        )
    print()
    print("  BENCHMARKS:")
    for r in output["ranked_by_composite_score"]:
        if r["symbol"] in ("SPY", "QQQ"):
            print(f"    {r['symbol']}: CAGR={r['cagr_pct']:.1f}%  Sharpe={r['sharpe']:.2f}  MDD={r['max_drawdown_pct']:.1f}%")
    print("=" * 72)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Leveraged ETF regime-aware backtest")
    parser.add_argument("--years", type=int, default=5, help="Years of history to test")
    args = parser.parse_args()
    run(years=args.years)
