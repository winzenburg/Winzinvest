#!/usr/bin/env python3
"""
Comprehensive Strategy Backtest — Baseline vs Enhanced.

Validates all strategy changes against the 40%+ annual return target.

Baseline: nx_backtest defaults
  - stop 1.5x ATR, tp 3.5x ATR, trail 3.0x ATR
  - Flat 1% risk per trade, max_hold 20 days
  - No conviction scaling, no daily budget, no pyramid

Enhanced: all new changes applied
  - R:R fix: tp 3.0x ATR, trail 2.5x ATR (aligns with adaptive_config.json)
  - Brandt 4-tier conviction sizing (0.5x/0.85x/1.40x/2.0x)
  - Brandt daily budget: max 4 longs / 3 shorts per day
  - Dhaliwal pyramid: +50% shares at +1R within 2 days, stop → breakeven
  - Phillips trend runner: stop 2.0x + max_hold 45d in STRONG_UPTREND
  - Benedict daily loss tiers: 50% size at 1% daily loss, 25% at 2%
  - Shapiro put/call overlay: ±0.05 conviction from ^VIX-derived P/C proxy (^PCCE removed from Yahoo)

Usage:
    cd trading
    python -m backtest.comprehensive_backtest --years 2 3 --initial-equity 1900000
    python -m backtest.comprehensive_backtest --years 2 --baseline-only
    python -m backtest.comprehensive_backtest --years 2 --enhanced-only --save
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ── path setup so we can import from nx_backtest ──────────────────────────────
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "scripts"))

from nx_backtest import (
    ClosedTrade,
    Position,
    RegimeType,
    classify_regime,
    compute_atr,
    compute_composite,
    compute_rsi,
    compute_relative_strength,
    compute_relative_vol,
    compute_structure_quality,
    compute_ams_final,
    REGIME_ALLOCATIONS,
    REGIME_MAX_NEW_ENTRIES,
    REGIME_SHORT_THRESHOLDS,
)

logger = logging.getLogger(__name__)
RESULTS_DIR = _HERE / "results"
# Canonical file consumed by dashboard_data_aggregator → Performance tab "Live vs Backtest"
EQUITY_BACKTEST_BENCHMARK_PATH = _HERE.parent / "logs" / "equity_backtest_benchmark.json"

# ── Universe (same as nx_backtest default) ─────────────────────────────────────
UNIVERSE = [
    "AAPL","MSFT","NVDA","GOOGL","META","TSLA","ASML","NFLX","ADBE","INTC",
    "QCOM","AVGO","AMAT","LRCX","AMD","MRVL","SNPS","CDNS","INTU","CSCO",
    "BKNG","CRWD","DDOG","NET","ZS","SNOW","SHOP","COIN","ORCL","CRM","NOW",
    "PANW","ABNB","UBER","DKNG","PLTR","SQ","PYPL","ROKU","SNAP","JPM","GS",
    "MA","V","UNH","HD","LLY","COST","WMT","CAT","DE","BA","XOM","CVX","COP",
    "EOG","SLB","DVN","MPC","VLO","PSX","NEE","DUK","SO","D","AEP","EXC",
    "PLD","AMT","EQIX","SPG","O","DLR","WPC","SBAC","CCI","KRE","XLF","KO",
    "PEP","PG","JNJ","MRK","ABBV","BMY","AMGN","GILD","BIIB","REGN","VRTX",
    "SPY","QQQ","IWM","XLK","XLF","XLE","XLV","XLI","XLY","XLP","XLU","XLC",
]

# ── Conviction tier helpers ────────────────────────────────────────────────────
_BRANDT_TIERS: List[Tuple[float, float, float]] = [
    # Goedeker/Sharkness hard-block: trades below 0.55 are excluded at screening
    # Only trades that pass the 0.55 floor reach the sizing tiers
    (0.55, 0.65, 0.85),   # acceptable
    (0.65, 0.80, 1.40),   # strong
    (0.80, 1.01, 2.00),   # exceptional
]


def brandt_conviction_mult(score: float) -> float:
    """Return position-size multiplier for a conviction score.

    Peter Brandt: concentrate capital on the highest-conviction setups.
    Uses the 4-tier curve from risk.json → brandt_conviction_sizing.
    """
    for lo, hi, mult in _BRANDT_TIERS:
        if lo <= score < hi:
            return mult
    return 2.00  # above all tiers → exceptional


def benedict_size_scale(daily_pnl: float, nlv: float) -> float:
    """Larry Benedict intraday drawdown scale factor.

    Approximated at the daily level (we don't have intraday granularity):
      daily_loss < 1% NLV : 1.00x (full size)
      daily_loss >= 1% NLV: 0.50x
      daily_loss >= 2% NLV: 0.25x
    """
    if nlv <= 0 or daily_pnl >= 0:
        return 1.0
    loss_pct = abs(daily_pnl) / nlv
    if loss_pct >= 0.02:
        return 0.25
    if loss_pct >= 0.01:
        return 0.50
    return 1.0


# ── Extended Position dataclass ────────────────────────────────────────────────

@dataclass
class EnhancedPosition(Position):
    """Position extended with pyramid-add tracking fields."""
    conviction_score: float = 0.50
    pyramid_added: bool = False
    original_qty: int = 0   # qty at entry (before any pyramid add; always set at construction)


# ── Config dataclass ───────────────────────────────────────────────────────────

@dataclass
class ComprehensiveConfig:
    """Parameters for both baseline and enhanced runs."""
    initial_equity: float = 1_900_000.0
    risk_per_trade_pct: float = 0.0063       # from adaptive_config.json
    max_position_pct: float = 0.05
    max_positions: int = 25
    commission_per_share: float = 0.005
    use_regime_filter: bool = True
    screener: str = "hybrid"
    min_combined_score: float = 0.55         # Goedeker/Sharkness hard block (raised from 0.40)

    # Baseline exit params
    baseline_stop_atr_mult: float = 1.5
    baseline_tp_atr_mult: float = 3.5
    baseline_trail_atr_mult: float = 3.0
    baseline_max_hold: int = 20

    # Enhanced exit params (R:R fix + Phillips)
    enhanced_stop_atr_mult: float = 1.5
    enhanced_tp_atr_mult: float = 3.0        # fixed from 1.575 → 3.0
    enhanced_trail_atr_mult: float = 2.5     # from adaptive_config.json
    enhanced_max_hold: int = 20
    enhanced_stop_uptrend: float = 2.0       # Phillips wider trail
    enhanced_max_hold_uptrend: int = 45      # Phillips longer hold

    # Brandt
    brandt_daily_longs: int = 4
    brandt_daily_shorts: int = 3

    # Dhaliwal
    dhaliwal_pyramid_enabled: bool = True
    dhaliwal_r_threshold: float = 1.0        # up ≥ 1R before pyramiding
    dhaliwal_days_window: int = 2            # must be within first 2 days
    dhaliwal_add_fraction: float = 0.50     # add 50% of original qty

    # Kullamägi open-profit pyramid (Next Generation)
    kullamagi_pyramid_enabled: bool = True
    kullamagi_min_profit_atr: float = 2.0   # open profit must be ≥ 2× ATR
    kullamagi_add_pct: float = 0.30          # fund add from 30% of open profit
    kullamagi_max_pct_nlv: float = 0.08     # cap at 8% of NLV

    # Bobblehead exit (Breitstein/Goedeker, Next Generation)
    bobblehead_enabled: bool = True
    bobblehead_days: int = 2                 # still below entry after N days
    bobblehead_min_loss_atr: float = 0.35   # drift must be ≥ 0.35× ATR

    # Fröhlich stat TP — modelled as a multiplier shift vs baseline
    stat_tp_enabled: bool = True
    stat_tp_atr_mult: float = 3.5           # P90 MFE proxy (slightly higher than fixed 3.0)

    # Brandt tier adjustment (raised floor removes marginal trades)
    brandt_min_conviction: float = 0.55     # hard block below this

    # Options income layer
    options_enabled: bool = True
    options_csp_income_pct_monthly: float = 0.005   # 0.5% monthly from CSP
    options_cc_income_pct_monthly: float = 0.004    # 0.4% monthly from CC


# ── Metrics container ──────────────────────────────────────────────────────────

@dataclass
class RunMetrics:
    label: str
    years: int
    initial_equity: float
    final_equity: float
    final_equity_with_options: float
    equity_curve: List[float]
    closed_trades: List[ClosedTrade]
    dates: List[str]
    pyramid_adds: int = 0
    budget_gated: int = 0
    brandt_avg_mult: float = 1.0
    options_income_total: float = 0.0

    @property
    def total_trades(self) -> int:
        return len(self.closed_trades)

    @property
    def cagr_equity(self) -> float:
        n_years = len(self.equity_curve) / 252.0
        if n_years <= 0 or self.initial_equity <= 0:
            return 0.0
        return (self.final_equity / self.initial_equity) ** (1 / n_years) - 1

    @property
    def cagr_with_options(self) -> float:
        n_years = len(self.equity_curve) / 252.0
        if n_years <= 0 or self.initial_equity <= 0:
            return 0.0
        return (self.final_equity_with_options / self.initial_equity) ** (1 / n_years) - 1

    @property
    def max_drawdown(self) -> float:
        arr = np.array(self.equity_curve)
        peak = np.maximum.accumulate(arr)
        dd = (peak - arr) / (peak + 1e-12)
        return float(np.max(dd))

    @property
    def sharpe(self) -> float:
        if len(self.equity_curve) < 2:
            return 0.0
        rets = np.diff(self.equity_curve) / (np.array(self.equity_curve[:-1]) + 1e-12)
        ann_vol = float(np.std(rets) * np.sqrt(252))
        if ann_vol <= 0:
            return 0.0
        return float(np.mean(rets) * 252 / ann_vol)

    @property
    def win_rate(self) -> float:
        if not self.closed_trades:
            return 0.0
        wins = sum(1 for t in self.closed_trades if t.pnl > 0)
        return wins / len(self.closed_trades)

    @property
    def avg_r(self) -> float:
        if not self.closed_trades:
            return 0.0
        return float(np.mean([t.r_multiple for t in self.closed_trades]))

    @property
    def avg_hold(self) -> float:
        if not self.closed_trades:
            return 0.0
        return float(np.mean([t.holding_days for t in self.closed_trades]))

    def per_calendar_year(self) -> Dict[str, float]:
        """CAGR broken down by calendar year."""
        if len(self.dates) != len(self.equity_curve) - 1:
            return {}
        years_map: Dict[str, List[Tuple[float, float]]] = {}
        prev = self.equity_curve[0]
        for i, d in enumerate(self.dates):
            yr = d[:4]
            curr = self.equity_curve[i + 1]
            years_map.setdefault(yr, []).append((prev, curr))
            prev = curr
        result: Dict[str, float] = {}
        for yr, snapshots in sorted(years_map.items()):
            start_eq = snapshots[0][0]
            end_eq = snapshots[-1][1]
            result[yr] = (end_eq - start_eq) / start_eq if start_eq > 0 else 0.0
        return result


# ── Data download ──────────────────────────────────────────────────────────────

def _download_all(years: int) -> Tuple[Dict[str, pd.DataFrame], pd.DataFrame, pd.Series, Optional[pd.Series]]:
    """Download OHLCV for universe + SPY + ^VIX (+ ^PCCE if still on Yahoo) via yfinance.

    Returns (stock_data, spy_df, vix_series, pcce_series_or_None).
    pcce_series is derived from VIX when ^PCCE is unavailable (removed from Yahoo Finance).
    """
    import yfinance as yf

    period = f"{years + 1}y"   # extra year for warm-up indicators
    # ^PCCE removed from Yahoo Finance — excluded from batch download; P/C is derived from VIX below
    all_syms = list(dict.fromkeys(UNIVERSE + ["SPY", "^VIX"]))
    logger.info("Downloading %dy data for %d symbols (including SPY/VIX)...", years + 1, len(all_syms))

    raw = yf.download(all_syms, period=period, progress=False, group_by="ticker")

    def _extract(sym: str) -> Optional[pd.DataFrame]:
        try:
            if isinstance(raw.columns, pd.MultiIndex):
                if sym in raw.columns.get_level_values(0):
                    df = raw[sym].dropna(how="all")
                else:
                    return None
            else:
                df = raw.copy()
            if df is not None and not df.empty and len(df) >= 50:
                return df
        except Exception:
            pass
        return None

    stock_data: Dict[str, pd.DataFrame] = {}
    for sym in all_syms:
        df = _extract(sym)
        if df is not None:
            stock_data[sym] = df

    # Download SPY and VIX individually if the multi-ticker batch missed them
    for sym in ("SPY", "^VIX"):
        if sym not in stock_data:
            try:
                df = yf.download(sym, period=period, progress=False)
                if df is not None and not df.empty:
                    stock_data[sym] = df
            except Exception as exc:
                logger.warning("Single-symbol download failed for %s: %s", sym, exc)

    spy_df = stock_data.get("SPY", pd.DataFrame())
    vix_raw = stock_data.get("^VIX", pd.DataFrame())
    vix_series: pd.Series = (
        vix_raw["Close"] if not vix_raw.empty and "Close" in vix_raw.columns
        else pd.Series(dtype=float)
    )
    pcce_raw = stock_data.get("^PCCE", pd.DataFrame())
    pcce_series: Optional[pd.Series]
    if not pcce_raw.empty and "Close" in pcce_raw.columns:
        pcce_series = pcce_raw["Close"].rolling(5, min_periods=1).mean()
    elif not vix_series.empty:
        # ^PCCE was removed from Yahoo Finance. Derive a P/C proxy from VIX.
        # Empirical mapping: VIX=12→0.58 (complacency), VIX=20→0.77 (neutral),
        # VIX=30→1.01 (fear), VIX=40→1.25 (extreme fear). Capped [0.40, 1.50].
        logger.info("^PCCE unavailable — using VIX-derived P/C proxy for Shapiro overlay")
        proxy = (vix_series - 15.0) / 25.0 * 0.6 + 0.65
        pcce_series = proxy.clip(0.40, 1.50).rolling(5, min_periods=1).mean()
    else:
        logger.warning("^PCCE and ^VIX both unavailable — Shapiro P/C overlay disabled")
        pcce_series = None

    # Remove market/index data from the trading universe
    for k in ("SPY", "^VIX"):
        stock_data.pop(k, None)

    logger.info("Data ready: %d tradeable symbols, SPY rows=%d", len(stock_data), len(spy_df))
    return stock_data, spy_df, vix_series, pcce_series


# ── Core simulation ────────────────────────────────────────────────────────────

def _run_one(
    label: str,
    cfg: ComprehensiveConfig,
    enhanced: bool,
    stock_data: Dict[str, pd.DataFrame],
    spy_df: pd.DataFrame,
    vix_series: pd.Series,
    pcce_series: Optional[pd.Series],
    years: int,
) -> RunMetrics:
    """Run one simulation (baseline or enhanced) on pre-loaded data."""
    logger.info("--- %s run (%dy) ---", label, years)

    if spy_df.empty:
        raise RuntimeError("SPY data unavailable")

    spy_close = spy_df["Close"]
    spy_sma200 = spy_close.rolling(200, min_periods=200).mean()
    spy_std20 = spy_close.pct_change().rolling(20).std()
    spy_returns = spy_close.pct_change()
    spy_atr = compute_atr(spy_df)

    # Pre-compute screener metrics for all symbols
    stock_metrics: Dict[str, Dict[str, pd.Series]] = {}
    for sym, df in stock_data.items():
        if sym in ("SPY", "^VIX"):
            continue
        try:
            atr = compute_atr(df)
            composite = compute_composite(df)
            rs = compute_relative_strength(
                df["Close"].pct_change(),
                spy_returns.reindex(df.index),
            )
            rvol = compute_relative_vol(atr, spy_atr.reindex(df.index), df["Close"], spy_close.reindex(df.index))
            structure = compute_structure_quality(df)
            ams = compute_ams_final(df, atr)
            stock_metrics[sym] = {
                "atr": atr, "composite": composite, "rs": rs,
                "rvol": rvol, "structure": structure,
                "ams_vol": ams["vol_score"], "ams_htf": ams["htf_adj"],
                "ams_rsi": ams["rsi"],
            }
        except Exception as exc:
            logger.debug("Skipping %s metrics: %s", sym, exc)

    # Clip the trading window to `years`
    cutoff_start = spy_df.index[-years * 252 - 200] if len(spy_df) > years * 252 + 200 else spy_df.index[200]
    trading_dates = spy_df.index[spy_df.index >= cutoff_start][200:]

    equity = cfg.initial_equity
    equity_curve: List[float] = [equity]
    positions: List[EnhancedPosition] = []
    closed_trades: List[ClosedTrade] = []
    dates: List[str] = []

    # Tracking stats for enhanced-only features
    pyramid_adds = 0
    budget_gated = 0
    brandt_mults: List[float] = []
    daily_pnl_cumulative = 0.0   # Benedict: resets each day

    # Leverage-adjusted params
    stop_mult_base = cfg.enhanced_stop_atr_mult if enhanced else cfg.baseline_stop_atr_mult
    tp_mult = cfg.enhanced_tp_atr_mult if enhanced else cfg.baseline_tp_atr_mult
    trail_mult = cfg.enhanced_trail_atr_mult if enhanced else cfg.baseline_trail_atr_mult
    max_hold = cfg.enhanced_max_hold if enhanced else cfg.baseline_max_hold

    for date in trading_dates:
        date_str = str(date.date()) if hasattr(date, "date") else str(date)[:10]

        # Detect regime
        regime: RegimeType = "CHOPPY"
        if cfg.use_regime_filter and date in spy_sma200.index:
            try:
                regime = classify_regime(
                    float(spy_close.loc[date]),
                    float(spy_sma200.loc[date]),
                    float(vix_series.loc[date]) if date in vix_series.index else 20.0,
                    float(spy_std20.loc[date]) if date in spy_std20.index else None,
                )
            except (KeyError, TypeError, ValueError):
                pass

        # Phillips: regime-aware stop and max hold
        if enhanced and regime == "STRONG_UPTREND":
            eff_stop_mult = cfg.enhanced_stop_uptrend
            eff_max_hold = cfg.enhanced_max_hold_uptrend
        else:
            eff_stop_mult = stop_mult_base
            eff_max_hold = max_hold

        # Shapiro: daily P/C adjustment to conviction
        pc_long_adj = 0.0
        pc_short_adj = 0.0
        if enhanced and pcce_series is not None and date in pcce_series.index:
            try:
                pc = float(pcce_series.loc[date])
                if not math.isnan(pc):
                    if pc >= 0.90:
                        pc_long_adj, pc_short_adj = +0.05, -0.05
                    elif pc <= 0.60:
                        pc_long_adj, pc_short_adj = -0.05, +0.05
            except (KeyError, TypeError, ValueError):
                pass

        # Benedict: reset daily P&L tracking at start of each day
        day_start_equity = equity
        daily_pnl_today = 0.0

        # ── Exit management ────────────────────────────────────────────────────
        new_positions: List[EnhancedPosition] = []
        for pos in positions:
            sym = pos.symbol
            if sym not in stock_data or date not in stock_data[sym].index:
                new_positions.append(pos)
                continue
            df = stock_data[sym]
            high = float(df.loc[date, "High"])
            low = float(df.loc[date, "Low"])
            close_px = float(df.loc[date, "Close"])
            pos.holding_days += 1
            exit_price: Optional[float] = None
            exit_reason = ""

            if pos.side == "SHORT":
                unrealized = (pos.entry_price - close_px) * pos.qty
                trail_active = unrealized >= pos.initial_risk
                if high >= pos.stop_price:
                    exit_price = pos.stop_price
                    exit_reason = "STOP_HIT"
                elif low <= pos.tp_price:
                    exit_price = pos.tp_price
                    exit_reason = "TP_HIT"
                elif trail_active and high >= pos.trailing_stop:
                    exit_price = pos.trailing_stop
                    exit_reason = "TRAIL_HIT"
                elif trail_active:
                    new_trail = close_px + pos.atr_at_entry * trail_mult
                    pos.trailing_stop = min(pos.trailing_stop, new_trail)
            else:
                unrealized = (close_px - pos.entry_price) * pos.qty
                trail_active = unrealized >= pos.initial_risk
                if low <= pos.stop_price:
                    exit_price = pos.stop_price
                    exit_reason = "STOP_HIT"
                elif high >= pos.tp_price:
                    exit_price = pos.tp_price
                    exit_reason = "TP_HIT"
                elif trail_active and low <= pos.trailing_stop:
                    exit_price = pos.trailing_stop
                    exit_reason = "TRAIL_HIT"
                elif trail_active:
                    new_trail = close_px - pos.atr_at_entry * trail_mult
                    pos.trailing_stop = max(pos.trailing_stop, new_trail)

            # Time stop (regime-aware for Phillips)
            if exit_price is None:
                hold_limit = eff_max_hold if (enhanced and pos.entry_regime == "STRONG_UPTREND") else max_hold
                if pos.holding_days >= hold_limit:
                    exit_price = close_px
                    exit_reason = "TIME_STOP"

            if exit_price is not None:
                if pos.side == "SHORT":
                    pnl = (pos.entry_price - exit_price) * pos.qty
                else:
                    pnl = (exit_price - pos.entry_price) * pos.qty
                commission = pos.qty * cfg.commission_per_share * 2
                pnl -= commission
                pnl_pct = pnl / (pos.entry_price * pos.qty) if pos.entry_price * pos.qty > 0 else 0
                r_mult = pnl / pos.initial_risk if pos.initial_risk > 0 else 0
                closed_trades.append(ClosedTrade(
                    symbol=sym, side=pos.side,
                    entry_price=pos.entry_price, exit_price=exit_price,
                    entry_date=pos.entry_date, exit_date=date_str,
                    qty=pos.qty, pnl=round(pnl, 2),
                    pnl_pct=round(pnl_pct, 4),
                    r_multiple=round(r_mult, 2),
                    holding_days=pos.holding_days,
                    exit_reason=exit_reason,
                    commission=round(commission, 2),
                    regime=pos.entry_regime,
                    strategy="momentum",
                ))
                equity += pnl
                daily_pnl_today += pnl
            else:
                new_positions.append(pos)

        positions = new_positions

        # ── Dhaliwal pyramid (enhanced only) ───────────────────────────────────
        if enhanced and cfg.dhaliwal_pyramid_enabled:
            for pos in positions:
                if pos.side != "LONG" or pos.pyramid_added:
                    continue
                if pos.holding_days > cfg.dhaliwal_days_window:
                    continue
                if pos.initial_risk <= 0:
                    continue
                if pos.symbol not in stock_data or date not in stock_data[pos.symbol].index:
                    continue
                try:
                    close_px = float(stock_data[pos.symbol].loc[date, "Close"])
                    unrealized = (close_px - pos.entry_price) * pos.original_qty
                    if unrealized >= pos.initial_risk * cfg.dhaliwal_r_threshold:
                        add_qty = max(1, round(pos.original_qty * cfg.dhaliwal_add_fraction))
                        pos.qty += add_qty
                        pos.stop_price = pos.entry_price  # move stop to breakeven
                        pos.pyramid_added = True
                        pyramid_adds += 1
                except (KeyError, TypeError, ValueError):
                    pass

        # ── Kullamägi open-profit pyramid (Next Gen, enhanced only) ────────────
        if enhanced and cfg.kullamagi_pyramid_enabled:
            for pos in positions:
                if pos.side != "LONG" or not pos.pyramid_added:
                    continue   # Layer 2 runs after Dhaliwal confirms the trade
                if pos.symbol not in stock_data or date not in stock_data[pos.symbol].index:
                    continue
                try:
                    close_px = float(stock_data[pos.symbol].loc[date, "Close"])
                    atr_val = float(pos.atr_at_entry) if pos.atr_at_entry > 0 else pos.entry_price * 0.02
                    open_profit = (close_px - pos.entry_price) * pos.qty
                    if open_profit < atr_val * cfg.kullamagi_min_profit_atr * pos.qty:
                        continue
                    add_dollars = open_profit * cfg.kullamagi_add_pct
                    max_dollars = equity * cfg.kullamagi_max_pct_nlv
                    add_dollars = min(add_dollars, max_dollars)
                    add_qty = max(1, int(add_dollars // close_px))
                    if add_qty >= 1:
                        pos.qty += add_qty
                        pyramid_adds += 1
                except (KeyError, TypeError, ValueError):
                    pass

        # ── Bobblehead early exit (Next Gen, enhanced only) ─────────────────────
        if enhanced and cfg.bobblehead_enabled:
            post_bobble: List[EnhancedPosition] = []
            for pos in positions:
                if pos.side != "LONG":
                    post_bobble.append(pos)
                    continue
                if pos.holding_days < cfg.bobblehead_days:
                    post_bobble.append(pos)
                    continue
                if pos.symbol not in stock_data or date not in stock_data[pos.symbol].index:
                    post_bobble.append(pos)
                    continue
                try:
                    close_px = float(stock_data[pos.symbol].loc[date, "Close"])
                    atr_val = float(pos.atr_at_entry) if pos.atr_at_entry > 0 else pos.entry_price * 0.02
                    if close_px >= pos.entry_price:
                        post_bobble.append(pos)
                        continue
                    drift = pos.entry_price - close_px
                    if drift >= atr_val * cfg.bobblehead_min_loss_atr:
                        # Exit the failed setup
                        pnl = (close_px - pos.entry_price) * pos.qty - (pos.qty * cfg.commission_per_share * 2)
                        pnl_pct = pnl / (pos.entry_price * pos.qty)
                        r_mult = pnl / pos.initial_risk if pos.initial_risk > 0 else 0
                        closed_trades.append(ClosedTrade(
                            symbol=pos.symbol, side=pos.side,
                            entry_price=pos.entry_price, exit_price=close_px,
                            entry_date=pos.entry_date, exit_date=date_str,
                            qty=pos.qty, pnl=round(pnl, 2),
                            pnl_pct=round(pnl_pct, 4),
                            r_multiple=round(r_mult, 2),
                            holding_days=pos.holding_days,
                            exit_reason="BOBBLEHEAD_EXIT",
                            commission=round(pos.qty * cfg.commission_per_share * 2, 2),
                            regime=pos.entry_regime,
                            strategy="momentum",
                        ))
                        equity += pnl
                        daily_pnl_today += pnl
                    else:
                        post_bobble.append(pos)
                except (KeyError, TypeError, ValueError):
                    post_bobble.append(pos)
            positions = post_bobble

        # ── Benedict: compute scale factor from today's realized P&L ──────────
        benedict_scale = 1.0
        if enhanced:
            # Approximate using cumulative closed-trade P&L since day start
            benedict_scale = benedict_size_scale(daily_pnl_today, equity)

        # ── Entry screening ────────────────────────────────────────────────────
        alloc = REGIME_ALLOCATIONS.get(regime, {"shorts": 0.08, "longs": 0.92})
        max_new = REGIME_MAX_NEW_ENTRIES.get(regime, 3) if cfg.use_regime_filter else 5
        short_thresh = REGIME_SHORT_THRESHOLDS.get(regime) if cfg.use_regime_filter else {
            "composite_max": 0.25, "structure_max": 0.25,
        }
        shorts_allowed = short_thresh is not None

        total_slots = cfg.max_positions - len(positions)
        short_slots = max(0, min(int(total_slots * alloc["shorts"]), max_new))
        long_slots = max(0, min(int(total_slots * alloc["longs"]), max(0, max_new - short_slots)))

        # Brandt daily budget (enhanced only)
        longs_today = 0
        shorts_today = 0

        short_cands: List[Tuple[str, float, float]] = []
        long_cands: List[Tuple[str, float, float]] = []

        w = 0.30  # hybrid AMS weight — same as nx_backtest default
        for sym, m in stock_metrics.items():
            if sym not in stock_data or date not in stock_data[sym].index:
                continue
            try:
                comp_val = float(m["composite"].loc[date])
                rs_val = float(m["rs"].loc[date])
                rvol_val = float(m["rvol"].loc[date])
                struct_val = float(m["structure"].loc[date])
                atr_val = float(m["atr"].loc[date])
                vol_score = float(m["ams_vol"].loc[date])
                htf_adj = float(m["ams_htf"].loc[date])
                ams_rsi = float(m["ams_rsi"].loc[date])
            except (KeyError, TypeError, ValueError):
                continue
            if any(math.isnan(v) for v in [comp_val, rs_val, rvol_val, struct_val, atr_val]):
                continue
            if any(p.symbol == sym for p in positions):
                continue

            # Shorts
            if shorts_allowed and short_thresh is not None:
                s_comp_max = short_thresh.get("composite_max", 0.25)
                s_struct_max = short_thresh.get("structure_max", 0.25)
                if (comp_val < s_comp_max and rs_val < 0.50 and
                        rvol_val >= 1.0 and struct_val < s_struct_max):
                    score = (1 - comp_val) * 0.4 + (1 - rs_val) * 0.3 + (1 - struct_val) * 0.3
                    adj_score = max(0.0, min(1.0, score + pc_short_adj))
                    short_cands.append((sym, adj_score, atr_val))

            # Longs (hybrid score)
            rsi_ok = 45 <= ams_rsi <= 75
            if (comp_val >= 0.45 and rs_val >= 0.01 and rvol_val >= 1.0 and
                    struct_val >= 0.45 and rsi_ok):
                nx_score = comp_val * 0.4 + rs_val * 0.3 + struct_val * 0.3
                ams_boost = vol_score * 0.5 + htf_adj * 0.5
                combined = nx_score * (1 - w) + ams_boost * w
                adj_score = max(0.0, min(1.0, combined + pc_long_adj))
                long_cands.append((sym, adj_score, atr_val))

        short_cands.sort(key=lambda x: -x[1])
        long_cands = [c for c in long_cands if c[1] >= cfg.min_combined_score]
        long_cands.sort(key=lambda x: -x[1])

        def _open(sym: str, score: float, atr_val: float, side: str) -> Optional[EnhancedPosition]:
            nonlocal longs_today, shorts_today, budget_gated
            df = stock_data[sym]
            if date not in df.index:
                return None
            price = float(df.loc[date, "Close"])
            if price <= 0 or atr_val <= 0:
                return None

            # Brandt daily budget (enhanced only)
            if enhanced:
                if side == "LONG" and longs_today >= cfg.brandt_daily_longs:
                    budget_gated += 1
                    return None
                if side == "SHORT" and shorts_today >= cfg.brandt_daily_shorts:
                    budget_gated += 1
                    return None

            # Conviction multiplier (Brandt 4-tier, enhanced only)
            conv_mult = brandt_conviction_mult(score) if enhanced else 1.0
            if enhanced:
                brandt_mults.append(conv_mult)

            # Position sizing
            eff_risk_pct = cfg.risk_per_trade_pct * conv_mult * benedict_scale
            risk_amount = equity * eff_risk_pct
            stop_dist = atr_val * eff_stop_mult
            if stop_dist <= 0:
                return None
            qty_from_risk = int(risk_amount / stop_dist)
            max_qty = int((equity * cfg.max_position_pct) / price)
            qty = max(1, min(qty_from_risk, max_qty))

            if side == "SHORT":
                stop_price = price + stop_dist
                tp_price = price - atr_val * tp_mult
                trail = price + atr_val * trail_mult
            else:
                stop_price = price - stop_dist
                tp_price = price + atr_val * tp_mult
                trail = price - atr_val * trail_mult

            if side == "LONG":
                longs_today += 1
            else:
                shorts_today += 1

            pos = EnhancedPosition(
                symbol=sym, side=side, entry_price=price,
                entry_date=date_str, qty=qty,
                stop_price=round(stop_price, 2),
                tp_price=round(tp_price, 2),
                trailing_stop=round(trail, 2),
                atr_at_entry=atr_val,
                initial_risk=stop_dist * qty,
                entry_regime=regime,
                strategy="momentum",
                conviction_score=score,
                pyramid_added=False,
                original_qty=qty,
            )
            return pos

        entered = 0
        for sym, score, atr_val in short_cands[:short_slots]:
            if entered >= max_new:
                break
            pos = _open(sym, score, atr_val, "SHORT")
            if pos:
                positions.append(pos)
                entered += 1

        for sym, score, atr_val in long_cands[:long_slots]:
            if entered >= max_new:
                break
            pos = _open(sym, score, atr_val, "LONG")
            if pos:
                positions.append(pos)
                entered += 1

        equity_curve.append(round(equity, 2))
        dates.append(date_str)

    # Approximate monthly options income (simplified model)
    # Options layer: CSP + CC income as % of NLV per month across the period
    options_income = 0.0
    if cfg.options_enabled:
        n_months = len(dates) / 21.0   # ~21 trading days/month
        monthly_rate = cfg.options_csp_income_pct_monthly + cfg.options_cc_income_pct_monthly
        # Compound month by month starting from initial equity
        eq = cfg.initial_equity
        for _ in range(int(n_months)):
            income = eq * monthly_rate
            eq += income
            options_income += income
        # In CHOPPY/UNFAVORABLE months, income is lower (regime penalty ~30%)
        # Rough adjustment: take 85% of computed value for realism
        options_income *= 0.85

    avg_brandt = float(np.mean(brandt_mults)) if brandt_mults else 1.0
    return RunMetrics(
        label=label,
        years=years,
        initial_equity=cfg.initial_equity,
        final_equity=equity,
        final_equity_with_options=equity + options_income,
        equity_curve=equity_curve,
        closed_trades=closed_trades,
        dates=dates,
        pyramid_adds=pyramid_adds,
        budget_gated=budget_gated,
        brandt_avg_mult=avg_brandt,
        options_income_total=options_income,
    )


# ── Output ─────────────────────────────────────────────────────────────────────

def _fmt_pct(v: float, decimals: int = 1) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v * 100:.{decimals}f}%"


def print_comparison(baseline: RunMetrics, enhanced: RunMetrics, pm_leverage: float = 2.5) -> None:
    """Print a side-by-side comparison table."""
    print(f"\n{'=' * 74}")
    print(f"  COMPREHENSIVE BACKTEST — {baseline.years}Y WINDOW")
    print(f"  Baseline vs Enhanced  |  Initial equity: ${baseline.initial_equity:,.0f}")
    print(f"{'=' * 74}")

    def row(label: str, b: str, e: str, delta: str = "") -> None:
        print(f"  {label:<32s}  {b:>10s}  {e:>10s}  {delta:>10s}")

    row("Metric", "Baseline", "Enhanced", "Delta")
    print(f"  {'-' * 70}")

    # CAGR rows
    b_eq  = baseline.cagr_equity
    e_eq  = enhanced.cagr_equity
    row("CAGR (equity only)", _fmt_pct(b_eq), _fmt_pct(e_eq), _fmt_pct(e_eq - b_eq))

    b_opt = baseline.cagr_with_options
    e_opt = enhanced.cagr_with_options
    row("CAGR + options income", _fmt_pct(b_opt), _fmt_pct(e_opt), _fmt_pct(e_opt - b_opt))

    b_lev = (1 + b_opt) ** (1 / baseline.years) - 1 if False else b_opt * pm_leverage
    e_lev = e_opt * pm_leverage
    # Approx leveraged: (1+unlev)^2.5 - 1 is too aggressive; use (unlev × leverage) as a first-order estimate
    row(f"CAGR × {pm_leverage:.1f}x PM leverage", _fmt_pct(b_lev), _fmt_pct(e_lev), _fmt_pct(e_lev - b_lev))

    target_label = f"40% target ({_fmt_pct(0.40 / pm_leverage)} unlev)"
    b_vs_tgt = b_opt - (0.40 / pm_leverage)
    e_vs_tgt = e_opt - (0.40 / pm_leverage)
    row(target_label, _fmt_pct(b_vs_tgt), _fmt_pct(e_vs_tgt), "")

    print(f"  {'-' * 70}")
    row("Max Drawdown", _fmt_pct(-baseline.max_drawdown), _fmt_pct(-enhanced.max_drawdown),
        _fmt_pct(baseline.max_drawdown - enhanced.max_drawdown))
    row("Sharpe Ratio",
        f"{baseline.sharpe:.2f}", f"{enhanced.sharpe:.2f}",
        f"{enhanced.sharpe - baseline.sharpe:+.2f}")
    row("Win Rate",
        f"{baseline.win_rate * 100:.0f}%", f"{enhanced.win_rate * 100:.0f}%",
        f"{(enhanced.win_rate - baseline.win_rate) * 100:+.0f}pp")
    row("Avg R-Multiple",
        f"{baseline.avg_r:.2f}R", f"{enhanced.avg_r:.2f}R",
        f"{enhanced.avg_r - baseline.avg_r:+.2f}R")
    row("Avg Hold (days)",
        f"{baseline.avg_hold:.1f}d", f"{enhanced.avg_hold:.1f}d",
        f"{enhanced.avg_hold - baseline.avg_hold:+.1f}d")
    row("Total Trades",
        str(baseline.total_trades), str(enhanced.total_trades),
        f"{enhanced.total_trades - baseline.total_trades:+d}")
    print(f"  {'-' * 70}")

    row("Pyramid Adds (Dhaliwal)", "0", str(enhanced.pyramid_adds), f"+{enhanced.pyramid_adds}")
    row("Budget-Gated (Brandt)", "0", str(enhanced.budget_gated), f"+{enhanced.budget_gated}")
    row("Brandt Avg Sizing Mult",
        "1.00x", f"{enhanced.brandt_avg_mult:.2f}x",
        f"{enhanced.brandt_avg_mult - 1.0:+.2f}x")
    opt_income_pct = enhanced.options_income_total / enhanced.initial_equity
    row("Options Income (total)",
        f"${baseline.options_income_total:,.0f}", f"${enhanced.options_income_total:,.0f}",
        f"+${enhanced.options_income_total - baseline.options_income_total:,.0f}")
    print(f"  {'-' * 70}")

    row("Starting Equity",
        f"${baseline.initial_equity:,.0f}", f"${enhanced.initial_equity:,.0f}", "")
    row("Final Equity (equity)",
        f"${baseline.final_equity:,.0f}", f"${enhanced.final_equity:,.0f}",
        f"${enhanced.final_equity - baseline.final_equity:+,.0f}")
    row("Final Equity + Options",
        f"${baseline.final_equity_with_options:,.0f}",
        f"${enhanced.final_equity_with_options:,.0f}",
        f"${enhanced.final_equity_with_options - baseline.final_equity_with_options:+,.0f}")

    # Per-calendar-year breakdown
    b_yr = baseline.per_calendar_year()
    e_yr = enhanced.per_calendar_year()
    all_yrs = sorted(set(b_yr) | set(e_yr))
    if all_yrs:
        print(f"\n  Per-calendar-year return:")
        print(f"  {'Year':<8s}  {'Baseline':>10s}  {'Enhanced':>10s}  {'Delta':>10s}  {'vs 40% target':>14s}")
        print(f"  {'-' * 58}")
        target_unlev = 0.40 / pm_leverage
        for yr in all_yrs:
            b = b_yr.get(yr, 0.0)
            e = e_yr.get(yr, 0.0)
            vs_tgt = _fmt_pct(e - target_unlev)
            suffix = " ✓" if e >= target_unlev else " ✗"
            print(f"  {yr:<8s}  {_fmt_pct(b):>10s}  {_fmt_pct(e):>10s}  {_fmt_pct(e - b):>10s}  {vs_tgt + suffix:>14s}")

    print(f"\n  Note: Leveraged CAGR uses first-order approximation: unlev × {pm_leverage}×")
    print(f"  Actual leveraged returns vary with drawdown path and margin costs.")
    print(f"  40% target = {_fmt_pct(0.40 / pm_leverage)} unleveraged CAGR + options income.")
    print(f"{'=' * 74}\n")


def write_equity_backtest_benchmark(enhanced: RunMetrics) -> None:
    """Write metrics for the institutional dashboard Performance tab (Backtest column).

    Uses ENHANCED run only — same curve as production logic.     Re-run (from repo `trading/` — use quotes if the path contains spaces):
      cd "/Users/ryanwinzenburg/Library/CloudStorage/GoogleDrive-ryanwinzenburg@gmail.com/My Drive/Projects/MIssion Control/trading" && python3 -m backtest.comprehensive_backtest --years 2 --enhanced-only --save
    """
    n = len(enhanced.closed_trades)
    total_pnl = sum(t.pnl for t in enhanced.closed_trades)
    avg_pnl = (total_pnl / n) if n else 0.0
    payload = {
        "_note": "Auto-written by comprehensive_backtest --save. Do not hand-edit numbers.",
        "generated_at": datetime.now().isoformat(),
        "source": "comprehensive_backtest_enhanced",
        "years": enhanced.years,
        "initial_equity": enhanced.initial_equity,
        "sharpe": round(enhanced.sharpe, 3),
        "win_rate_pct": round(enhanced.win_rate * 100, 2),
        "max_drawdown_pct": round(enhanced.max_drawdown * 100, 2),
        "avg_pnl_per_trade_usd": round(avg_pnl, 2),
        "total_trades": enhanced.total_trades,
    }
    EQUITY_BACKTEST_BENCHMARK_PATH.parent.mkdir(parents=True, exist_ok=True)
    EQUITY_BACKTEST_BENCHMARK_PATH.write_text(json.dumps(payload, indent=2))
    logger.info("Wrote equity backtest benchmark for dashboard: %s", EQUITY_BACKTEST_BENCHMARK_PATH)


def save_comprehensive_results(baseline: RunMetrics, enhanced: RunMetrics) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = RESULTS_DIR / f"comprehensive_backtest_{baseline.years}y_{ts}.json"

    def _metrics_dict(m: RunMetrics) -> dict:
        return {
            "label": m.label,
            "years": m.years,
            "initial_equity": m.initial_equity,
            "final_equity": m.final_equity,
            "final_equity_with_options": m.final_equity_with_options,
            "cagr_equity": round(m.cagr_equity, 4),
            "cagr_with_options": round(m.cagr_with_options, 4),
            "max_drawdown": round(m.max_drawdown, 4),
            "sharpe": round(m.sharpe, 3),
            "win_rate": round(m.win_rate, 3),
            "avg_r": round(m.avg_r, 3),
            "avg_hold": round(m.avg_hold, 1),
            "total_trades": m.total_trades,
            "pyramid_adds": m.pyramid_adds,
            "budget_gated": m.budget_gated,
            "brandt_avg_mult": round(m.brandt_avg_mult, 3),
            "options_income_total": round(m.options_income_total, 2),
            "per_calendar_year": {yr: round(r, 4) for yr, r in m.per_calendar_year().items()},
        }

    payload = {
        "generated_at": datetime.now().isoformat(),
        "baseline": _metrics_dict(baseline),
        "enhanced": _metrics_dict(enhanced),
    }
    out.write_text(json.dumps(payload, indent=2))
    try:
        write_equity_backtest_benchmark(enhanced)
    except OSError as exc:
        logger.warning("Could not write equity_backtest_benchmark.json: %s", exc)
    return out


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Comprehensive strategy backtest — baseline vs enhanced")
    parser.add_argument("--years", type=int, nargs="+", default=[2, 3],
                        help="One or more year windows to backtest (default: 2 3)")
    parser.add_argument("--initial-equity", type=float, default=1_900_000.0,
                        help="Starting equity (default: 1,900,000 — approximate current NLV)")
    parser.add_argument("--baseline-only", action="store_true")
    parser.add_argument("--enhanced-only", action="store_true")
    parser.add_argument("--save", action="store_true", help="Save results JSON to backtest/results/")
    parser.add_argument("--pm-leverage", type=float, default=2.5,
                        help="PM leverage multiplier for projected return (default: 2.5)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    cfg = ComprehensiveConfig(initial_equity=args.initial_equity)

    run_both = not args.baseline_only and not args.enhanced_only
    run_base = run_both or args.baseline_only
    run_enh  = run_both or args.enhanced_only

    for years in args.years:
        logger.info("===== %d-YEAR WINDOW =====", years)

        # Download data once for this window
        stock_data, spy_df, vix_series, pcce_series = _download_all(years)
        if spy_df.empty:
            logger.error("SPY data unavailable — aborting")
            return

        baseline_metrics: Optional[RunMetrics] = None
        enhanced_metrics: Optional[RunMetrics] = None

        if run_base:
            baseline_metrics = _run_one(
                "BASELINE", cfg, enhanced=False,
                stock_data=stock_data, spy_df=spy_df, vix_series=vix_series,
                pcce_series=pcce_series, years=years,
            )

        if run_enh:
            enhanced_metrics = _run_one(
                "ENHANCED", cfg, enhanced=True,
                stock_data=stock_data, spy_df=spy_df, vix_series=vix_series,
                pcce_series=pcce_series, years=years,
            )

        if baseline_metrics is not None and enhanced_metrics is not None:
            print_comparison(baseline_metrics, enhanced_metrics, pm_leverage=args.pm_leverage)
            if args.save:
                out = save_comprehensive_results(baseline_metrics, enhanced_metrics)
                print(f"  Results saved: {out}\n")
        elif baseline_metrics is not None:
            # Single run output
            print(f"\n{'=' * 60}")
            print(f"  BASELINE — {years}Y")
            print(f"  CAGR: {_fmt_pct(baseline_metrics.cagr_equity)}  "
                  f"Sharpe: {baseline_metrics.sharpe:.2f}  "
                  f"MaxDD: {_fmt_pct(-baseline_metrics.max_drawdown)}")
            print(f"  Trades: {baseline_metrics.total_trades}  "
                  f"Win%: {baseline_metrics.win_rate*100:.0f}%  "
                  f"AvgR: {baseline_metrics.avg_r:.2f}")
            print(f"{'=' * 60}\n")
        elif enhanced_metrics is not None:
            print(f"\n{'=' * 60}")
            print(f"  ENHANCED — {years}Y")
            print(f"  CAGR (equity): {_fmt_pct(enhanced_metrics.cagr_equity)}")
            print(f"  CAGR + options: {_fmt_pct(enhanced_metrics.cagr_with_options)}")
            print(f"  CAGR × {args.pm_leverage}x: {_fmt_pct(enhanced_metrics.cagr_with_options * args.pm_leverage)}")
            print(f"  Sharpe: {enhanced_metrics.sharpe:.2f}  "
                  f"MaxDD: {_fmt_pct(-enhanced_metrics.max_drawdown)}")
            print(f"  Trades: {enhanced_metrics.total_trades}  "
                  f"Win%: {enhanced_metrics.win_rate*100:.0f}%  "
                  f"AvgR: {enhanced_metrics.avg_r:.2f}")
            print(f"  Pyramid adds: {enhanced_metrics.pyramid_adds}  "
                  f"Budget-gated: {enhanced_metrics.budget_gated}")
            print(f"{'=' * 60}\n")

            yr_tbl = enhanced_metrics.per_calendar_year()
            if yr_tbl:
                target_u = 0.40 / args.pm_leverage
                print("  Per-year:")
                for yr, r in sorted(yr_tbl.items()):
                    mark = "✓" if r >= target_u else "✗"
                    print(f"    {yr}: {_fmt_pct(r)}  {mark}")
                print()

            if args.save:
                out = save_comprehensive_results(
                    RunMetrics("BASELINE", years, cfg.initial_equity, cfg.initial_equity, cfg.initial_equity, [cfg.initial_equity], [], []),
                    enhanced_metrics,
                )
                print(f"  Results saved: {out}\n")


if __name__ == "__main__":
    main()
