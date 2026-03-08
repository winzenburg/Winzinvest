#!/usr/bin/env python3
"""
Vectorized backtest engine for NX screener + ATR-based execution strategy.

Replays screener logic daily over historical OHLCV data, simulates entries
with ATR stops/TP/trailing, tracks equity curve and performance metrics.

Includes regime filtering (SPY vs 200 SMA + VIX), regime-based slot
allocation, and conviction-tier sizing — matching the live system's behavior.

Usage:
    python -m trading.backtest.nx_backtest --years 2 --initial-equity 1900000

Not meant for production — this is a validation tool. No IB connection needed.
"""

import argparse
import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from sector_gates import SECTOR_MAP as _SECTOR_MAP
except ImportError:
    _SECTOR_MAP = {}

RESULTS_DIR = Path(__file__).resolve().parent / "results"

RegimeType = Literal[
    "STRONG_DOWNTREND", "MIXED", "STRONG_UPTREND", "CHOPPY", "UNFAVORABLE"
]

# Long-first allocations: core portfolio is longs, shorts are a small hedge.
REGIME_ALLOCATIONS: Dict[RegimeType, Dict[str, float]] = {
    "STRONG_DOWNTREND": {"shorts": 0.00, "longs": 0.50},
    "MIXED":            {"shorts": 0.20, "longs": 0.80},
    "STRONG_UPTREND":   {"shorts": 0.00, "longs": 1.00},
    "CHOPPY":           {"shorts": 0.15, "longs": 0.85},
    "UNFAVORABLE":      {"shorts": 0.00, "longs": 0.00},
}

# Shorts are hedges — only the highest-conviction setups. None = blocked.
REGIME_SHORT_THRESHOLDS: Dict[RegimeType, Optional[Dict[str, float]]] = {
    "STRONG_DOWNTREND": None,
    "MIXED":            {"composite_max": 0.20, "structure_max": 0.20},
    "CHOPPY":           {"composite_max": 0.20, "structure_max": 0.20},
    "STRONG_UPTREND":   None,
    "UNFAVORABLE":      None,
}

REGIME_MAX_NEW_ENTRIES: Dict[RegimeType, int] = {
    "STRONG_DOWNTREND": 3,
    "MIXED":            4,
    "CHOPPY":           4,
    "STRONG_UPTREND":   5,
    "UNFAVORABLE":      1,
}


@dataclass
class BacktestConfig:
    initial_equity: float = 1_000_000.0
    risk_per_trade_pct: float = 0.01
    max_position_pct: float = 0.05
    stop_atr_mult: float = 2.0
    tp_atr_mult: float = 3.0
    trailing_atr_mult: float = 2.5
    max_positions: int = 20
    max_holding_days: int = 15
    commission_per_share: float = 0.005
    use_regime_filter: bool = True
    # Screener: "nx" | "ams" | "hybrid" (NX filter + AMS volume/HTF ranking)
    screener: str = "hybrid"
    # NX thresholds (used when screener="nx" or "hybrid")
    composite_max: float = 0.25
    rs_max: float = 0.50
    rvol_min: float = 1.0
    structure_max: float = 0.25
    composite_min_long: float = 0.45
    rs_min_long: float = 0.01
    structure_min_long: float = 0.45
    # AMS thresholds (used when screener="ams")
    ams_min_score: float = 0.05
    ams_min_rsi: float = 45.0
    ams_max_rsi: float = 75.0
    ams_corr_max: float = 0.80
    ams_short_max_score: float = 0.15
    ams_short_max_rsi: float = 40.0
    # Hybrid: AMS volume/HTF weight in ranking (0 = pure NX, 1 = heavy AMS)
    hybrid_ams_weight: float = 0.30
    # Mean reversion config
    mr_rsi_period: int = 2
    mr_rsi_entry: float = 10.0
    mr_rsi_exit: float = 70.0
    mr_max_hold: int = 5
    mr_require_above_200sma: bool = True
    mr_stop_atr_mult: float = 1.0
    mr_tp_atr_mult: float = 1.5
    # Volatility targeting config
    vol_target_enabled: bool = False
    vol_target_annual: float = 0.10
    vol_scale_cap: float = 1.5
    # Pairs trading config
    pairs_enabled: bool = False
    pairs_holding_days: int = 15
    pairs_rebalance_days: int = 5
    pairs_max_pairs: int = 5
    # Multi-TF entry optimization (simulated pullback improvement)
    mtf_entry_enabled: bool = False
    mtf_entry_improvement_atr_min: float = 0.2
    mtf_entry_improvement_atr_max: float = 0.5
    # Options overlay config
    options_overlay_enabled: bool = False
    options_condor_monthly_income_pct: float = 0.005
    options_condor_max_loss_pct: float = 0.02
    options_put_monthly_cost_pct: float = 0.003
    options_put_floor_monthly_pct: float = 0.05
    # Sector rotation config
    sector_rotation_enabled: bool = False
    sector_rotation_etfs: Tuple[str, ...] = (
        "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLC", "XLRE", "XLB",
    )
    sector_rotation_top_n: int = 3
    sector_rotation_rebalance_days: int = 21
    sector_rotation_alloc_pct: float = 0.40


def classify_regime(
    spy_close: float,
    spy_sma200: float,
    vix_close: float,
    spy_20d_std: Optional[float] = None,
) -> RegimeType:
    """Classify market regime — mirrors live regime_detector._regime_from_spy_vix."""
    if spy_sma200 <= 0:
        return "CHOPPY"
    distance_to_sma = (spy_close - spy_sma200) / spy_sma200

    if (
        vix_close > 30
        and abs(distance_to_sma) < 0.01
        and (spy_20d_std is None or spy_20d_std > 0.02)
    ):
        return "UNFAVORABLE"
    if distance_to_sma < -0.02 and vix_close > 20:
        return "STRONG_DOWNTREND"
    if distance_to_sma > 0.02 and vix_close < 15:
        return "STRONG_UPTREND"
    if distance_to_sma < -0.02 and vix_close < 20:
        return "MIXED"
    return "CHOPPY"


@dataclass
class Position:
    symbol: str
    side: str  # "SHORT" or "LONG"
    entry_price: float
    entry_date: str
    qty: int
    stop_price: float
    tp_price: float
    trailing_stop: float
    atr_at_entry: float
    initial_risk: float = 0.0
    holding_days: int = 0
    entry_regime: str = "CHOPPY"
    strategy: str = "momentum"


@dataclass
class ClosedTrade:
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    entry_date: str
    exit_date: str
    qty: int
    pnl: float
    pnl_pct: float
    r_multiple: float
    holding_days: int
    exit_reason: str
    commission: float
    regime: str = "CHOPPY"


@dataclass
class BacktestResult:
    config: BacktestConfig
    equity_curve: List[float] = field(default_factory=list)
    dates: List[str] = field(default_factory=list)
    closed_trades: List[ClosedTrade] = field(default_factory=list)
    daily_returns: List[float] = field(default_factory=list)
    regime_day_counts: Dict[str, int] = field(default_factory=dict)


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Compute ATR from OHLC dataframe."""
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    cp = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - cp).abs(),
        (low - cp).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=1).mean()


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period, min_periods=1).mean()
    loss = (-delta.clip(upper=0)).rolling(period, min_periods=1).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def compute_composite(df: pd.DataFrame) -> pd.Series:
    close = df["Close"]
    momentum_raw = close.pct_change(20)
    momentum_norm = momentum_raw.clip(-0.15, 0.15) / 0.15
    momentum_01 = (momentum_norm + 1) / 2

    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    bb_upper = sma20 + 2 * std20
    bb_lower = sma20 - 2 * std20
    bb_range = bb_upper - bb_lower
    bb_pos = ((close - bb_lower) / bb_range.replace(0, np.nan)).clip(0, 1).fillna(0.5)

    rsi = compute_rsi(close, 14)
    rsi_norm = ((rsi - 30) / 40).clip(0, 1)

    return momentum_01 * 0.4 + bb_pos * 0.3 + rsi_norm * 0.3


# =========================================================================
#  AMS v2 Pro Scoring — mirrors TradingView AMS screener logic
# =========================================================================

def compute_ams_roc_composite(close: pd.Series, atr: pd.Series) -> pd.Series:
    """Multi-timeframe ROC with volatility normalization (AMS v2 Pro)."""
    roc_21 = close.pct_change(21) * 100
    roc_63 = close.pct_change(63) * 100
    roc_126 = close.pct_change(126) * 100

    vol_pct = (atr / close.replace(0, np.nan)) * 100
    vol_factor = vol_pct.clip(lower=0.5)
    norm_base = 2.0
    roc_s = roc_21 / (vol_factor / norm_base)
    roc_m = roc_63 / (vol_factor / norm_base)
    roc_l = roc_126 / (vol_factor / norm_base)

    raw = 0.2 * roc_s + 0.3 * roc_m + 0.5 * roc_l
    return (raw / 25.0).clip(0, 1)


def _sigmoid(x: pd.Series) -> pd.Series:
    """tanh-like sigmoid: (exp(2x)-1)/(exp(2x)+1)."""
    e2x = np.exp(2 * x)
    return (e2x - 1) / (e2x + 1)


def compute_ams_htf_bias(close: pd.Series) -> pd.Series:
    """Weekly (13w≈65d) + monthly (6m≈126d) ROC with sigmoid transform."""
    weekly_roc = close.pct_change(65) * 100
    monthly_roc = close.pct_change(126) * 100
    htf = 0.3 * _sigmoid(weekly_roc / 10) + 0.2 * _sigmoid(monthly_roc / 10)
    return (htf + 1) / 2  # map -1..1 → 0..1


def compute_ams_volume_score(volume: pd.Series) -> pd.Series:
    """RVol + volume trend score (0 to 1)."""
    avg_50 = volume.rolling(50, min_periods=1).mean()
    rvol = (volume / avg_50.replace(0, np.nan)).fillna(1.0).clip(upper=3.0)
    vol_trend = (volume.rolling(20).mean() > volume.rolling(40).mean()).astype(float)
    return (rvol / 3.0) * 0.7 + vol_trend * 0.3


def compute_ams_structure(high: pd.Series, low: pd.Series) -> pd.Series:
    """Pivot-based structure quality (0 to 1)."""
    pivot_len = 5
    ph = high.rolling(2 * pivot_len + 1, center=True).max()
    pl = low.rolling(2 * pivot_len + 1, center=True).min()
    is_ph = (high == ph).astype(float)
    is_pl = (low == pl).astype(float)
    pivot_pts = is_ph + is_pl
    return (pivot_pts.rolling(50, min_periods=1).mean() / 2).clip(0, 1)


def compute_ams_final(
    df: pd.DataFrame, atr: pd.Series,
) -> Dict[str, pd.Series]:
    """Compute the full AMS v2 Pro score suite for one stock."""
    close = df["Close"]
    volume = df["Volume"] if "Volume" in df.columns else pd.Series(0, index=df.index)

    score_raw = compute_ams_roc_composite(close, atr)
    htf_adj = compute_ams_htf_bias(close)
    vol_score = compute_ams_volume_score(volume)
    struct_score = compute_ams_structure(df["High"], df["Low"])

    comp_final = (
        0.40 * score_raw +
        0.20 * htf_adj +
        0.20 * vol_score +
        0.20 * struct_score
    )

    rsi = compute_rsi(close, 14)
    abs_mom = (close > close.shift(126)).astype(float)
    rel_mom = (rsi > 50).astype(float)

    return {
        "comp_final": comp_final,
        "rsi": rsi,
        "abs_mom": abs_mom,
        "rel_mom": rel_mom,
        "score_raw": score_raw,
        "htf_adj": htf_adj,
        "vol_score": vol_score,
        "struct_score": struct_score,
    }


def compute_relative_strength(stock_returns: pd.Series, spy_returns: pd.Series) -> pd.Series:
    """20-day cumulative return difference."""
    stock_cum = stock_returns.rolling(20).sum()
    spy_cum = spy_returns.rolling(20).sum()
    return stock_cum - spy_cum


def compute_relative_vol(stock_atr: pd.Series, spy_atr: pd.Series,
                          stock_close: pd.Series, spy_close: pd.Series) -> pd.Series:
    """ATR-normalized volatility ratio."""
    stock_norm = stock_atr / stock_close.replace(0, np.nan)
    spy_norm = spy_atr / spy_close.replace(0, np.nan)
    return (stock_norm / spy_norm.replace(0, np.nan)).fillna(1.0)


def compute_structure_quality(df: pd.DataFrame) -> pd.Series:
    close = df["Close"]
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()

    sma20_std = close.rolling(20).std()
    bb_upper = sma20 + 2 * sma20_std
    bb_lower = sma20 - 2 * sma20_std
    bb_range = bb_upper - bb_lower
    bb_pos = ((close - bb_lower) / bb_range.replace(0, np.nan)).clip(0, 1).fillna(0.5)

    sma_aligned_bull = ((sma20 > sma50) & (sma50 > sma200)).astype(float)
    sma_aligned_bear = ((sma20 < sma50) & (sma50 < sma200)).astype(float)
    sma_score = sma_aligned_bull * 1.0 + (1 - sma_aligned_bull - sma_aligned_bear) * 0.5

    rsi = compute_rsi(close, 14) / 100.0

    return bb_pos * 0.4 + sma_score * 0.3 + rsi * 0.3


def _download_stock_data(
    symbols: List[str], period: str
) -> Dict[str, pd.DataFrame]:
    """Download OHLCV data for all symbols + SPY + ^VIX via yfinance."""
    import yfinance as yf

    all_symbols = list(set(symbols + ["SPY"]))
    logger.info("Downloading data for %d symbols over %s...", len(all_symbols), period)
    data = yf.download(all_symbols, period=period, progress=False, group_by="ticker")

    if data is None or data.empty:
        return {}

    stock_data: Dict[str, pd.DataFrame] = {}
    for sym in all_symbols:
        try:
            if isinstance(data.columns, pd.MultiIndex):
                if sym in data.columns.get_level_values(0):
                    df = data[sym].dropna(how="all")
                else:
                    continue
            else:
                df = data.copy()
            if df is not None and not df.empty and len(df) >= 200:
                stock_data[sym] = df
        except Exception:
            continue

    logger.info("Downloading VIX data...")
    try:
        vix_raw = yf.download("^VIX", period=period, progress=False)
        if vix_raw is not None and not vix_raw.empty and len(vix_raw) >= 50:
            stock_data["^VIX"] = vix_raw
    except Exception as e:
        logger.warning("VIX download failed (will default to 18): %s", e)

    return stock_data


def _extract_close_series(df: pd.DataFrame) -> pd.Series:
    """Safely extract a 1-D Close series from a possibly MultiIndex DataFrame."""
    if isinstance(df.columns, pd.MultiIndex):
        if "Close" in df.columns.get_level_values(0):
            s = df["Close"]
        else:
            s = df.iloc[:, 0]
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0]
        return s
    if "Close" in df.columns:
        return df["Close"]
    return df.iloc[:, 3]


def _compute_daily_regime(
    spy_df: pd.DataFrame, vix_df: Optional[pd.DataFrame]
) -> pd.Series:
    """Return a Series of RegimeType indexed by date for every trading day."""
    spy_close = _extract_close_series(spy_df)
    spy_sma200 = spy_close.rolling(200).mean()
    spy_returns = spy_close.pct_change()
    spy_20d_std = spy_returns.rolling(20).std()

    if vix_df is not None and not vix_df.empty:
        vix_raw = _extract_close_series(vix_df)
        vix_close = vix_raw.reindex(spy_df.index, method="ffill").fillna(18.0)
    else:
        vix_close = pd.Series(18.0, index=spy_df.index)

    regimes: List[RegimeType] = []
    for i in range(len(spy_df.index)):
        try:
            sc = float(spy_close.iloc[i])
        except (TypeError, ValueError):
            sc = 0
        try:
            s200_val = spy_sma200.iloc[i]
            s200 = float(s200_val) if pd.notna(s200_val) else 0
        except (TypeError, ValueError):
            s200 = 0
        try:
            vc_val = vix_close.iloc[i]
            vc = float(vc_val) if pd.notna(vc_val) else 18.0
        except (TypeError, ValueError):
            vc = 18.0
        try:
            sd_val = spy_20d_std.iloc[i]
            sd: Optional[float] = float(sd_val) if pd.notna(sd_val) else None
        except (TypeError, ValueError):
            sd = None
        regimes.append(classify_regime(sc, s200, vc, sd))

    return pd.Series(regimes, index=spy_df.index)


def run_backtest(
    symbols: List[str],
    config: BacktestConfig,
    years: int = 2,
) -> BacktestResult:
    """Run a vectorized backtest on the given symbols.

    Downloads historical data via yfinance, computes daily regime from
    SPY/VIX, runs either NX or AMS v2 Pro screener daily with
    regime-gated allocation, and simulates order execution with ATR stops.
    """
    period = f"{years}y"

    # Ensure sector ETFs are included in download if rotation enabled
    all_symbols = list(symbols)
    if config.sector_rotation_enabled:
        for etf in config.sector_rotation_etfs:
            if etf not in all_symbols:
                all_symbols.append(etf)

    stock_data = _download_stock_data(all_symbols, period)

    if "SPY" not in stock_data:
        logger.error("SPY data not available")
        return BacktestResult(config=config)

    spy_df = stock_data["SPY"]
    spy_close_series = _extract_close_series(spy_df)
    spy_returns = spy_close_series.pct_change()
    spy_atr = compute_atr(spy_df)

    vix_df = stock_data.get("^VIX")
    daily_regime = _compute_daily_regime(spy_df, vix_df)

    # Pre-compute SPY correlation series for AMS correlation guard
    spy_corr_close = spy_close_series.copy()

    # SPY realized vol series for vol-targeting
    spy_daily_ret = spy_close_series.pct_change()
    spy_realized_vol = spy_daily_ret.rolling(20).std() * np.sqrt(252)

    metrics: Dict[str, Dict[str, pd.Series]] = {}
    ams_metrics: Dict[str, Dict[str, pd.Series]] = {}
    mr_metrics: Dict[str, Dict[str, pd.Series]] = {}

    need_nx = config.screener in ("nx", "hybrid", "hybrid_mr")
    need_ams = config.screener in ("ams", "hybrid", "hybrid_mr")
    need_mr = config.screener in ("mean_reversion", "hybrid_mr")

    for sym, df in stock_data.items():
        if sym in ("SPY", "^VIX"):
            continue
        try:
            atr = compute_atr(df)

            if need_mr:
                close = df["Close"]
                rsi_fast = compute_rsi(close, config.mr_rsi_period)
                sma_200 = close.rolling(200, min_periods=200).mean()
                mr_metrics[sym] = {
                    "rsi_fast": rsi_fast,
                    "sma_200": sma_200,
                    "atr": atr,
                }

            if need_nx:
                stock_returns = df["Close"].pct_change()
                composite = compute_composite(df)
                rs = compute_relative_strength(stock_returns, spy_returns.reindex(df.index))
                rvol = compute_relative_vol(atr, spy_atr.reindex(df.index), df["Close"], spy_close_series.reindex(df.index))
                structure = compute_structure_quality(df)
                metrics[sym] = {
                    "atr": atr,
                    "composite": composite,
                    "rs": rs,
                    "rvol": rvol,
                    "structure": structure,
                }
            if need_ams:
                ams = compute_ams_final(df, atr)
                spy_aligned = spy_corr_close.reindex(df.index)
                corr = df["Close"].rolling(20).corr(spy_aligned).fillna(0)
                ams["corr"] = corr
                ams["atr"] = atr
                ams_metrics[sym] = ams
        except Exception as e:
            logger.debug("Skipping %s metrics: %s", sym, e)

    trading_dates = spy_df.index[200:]
    equity = config.initial_equity
    positions: List[Position] = []
    result = BacktestResult(config=config)

    regime_day_counts: Dict[str, int] = {}

    # Sector rotation state
    sr_top_etfs: List[str] = []
    sr_days_since_rebalance = 999

    for date in trading_dates:
        date_str = str(date.date()) if hasattr(date, "date") else str(date)[:10]

        regime: RegimeType = "CHOPPY"
        if config.use_regime_filter and date in daily_regime.index:
            regime = daily_regime.loc[date]
        regime_day_counts[regime] = regime_day_counts.get(regime, 0) + 1

        alloc = REGIME_ALLOCATIONS.get(regime, {"shorts": 0.50, "longs": 0.50})

        # ---- Manage existing positions ----
        new_positions: List[Position] = []
        for pos in positions:
            sym = pos.symbol
            if sym not in stock_data:
                new_positions.append(pos)
                continue
            df = stock_data[sym]
            if date not in df.index:
                new_positions.append(pos)
                continue

            high = float(df.loc[date, "High"])
            low = float(df.loc[date, "Low"])
            close_price = float(df.loc[date, "Close"])
            pos.holding_days += 1
            exit_price: Optional[float] = None
            exit_reason = ""

            if pos.side == "SHORT":
                if high >= pos.stop_price:
                    exit_price = pos.stop_price
                    exit_reason = "STOP_HIT"
                elif low <= pos.tp_price:
                    exit_price = pos.tp_price
                    exit_reason = "TP_HIT"
                elif high >= pos.trailing_stop:
                    exit_price = pos.trailing_stop
                    exit_reason = "TRAIL_HIT"
                else:
                    new_trail = close_price + pos.atr_at_entry * config.trailing_atr_mult
                    pos.trailing_stop = min(pos.trailing_stop, new_trail)
            else:
                if low <= pos.stop_price:
                    exit_price = pos.stop_price
                    exit_reason = "STOP_HIT"
                elif high >= pos.tp_price:
                    exit_price = pos.tp_price
                    exit_reason = "TP_HIT"
                elif low <= pos.trailing_stop:
                    exit_price = pos.trailing_stop
                    exit_reason = "TRAIL_HIT"
                else:
                    new_trail = close_price - pos.atr_at_entry * config.trailing_atr_mult
                    pos.trailing_stop = max(pos.trailing_stop, new_trail)

            # MR-specific RSI exit: close when RSI recovers
            if exit_price is None and pos.strategy == "mean_reversion" and sym in mr_metrics:
                try:
                    rsi_now = float(mr_metrics[sym]["rsi_fast"].loc[date])
                    if rsi_now >= config.mr_rsi_exit:
                        exit_price = close_price
                        exit_reason = "RSI_EXIT"
                except (KeyError, TypeError, ValueError):
                    pass
                mr_hold_limit = config.mr_max_hold
                if exit_price is None and pos.holding_days >= mr_hold_limit:
                    exit_price = close_price
                    exit_reason = "MR_TIME_STOP"

            if exit_price is None and pos.strategy != "mean_reversion" and pos.holding_days >= config.max_holding_days:
                exit_price = close_price
                exit_reason = "TIME_STOP"

            if exit_price is not None:
                if pos.side == "SHORT":
                    pnl = (pos.entry_price - exit_price) * pos.qty
                else:
                    pnl = (exit_price - pos.entry_price) * pos.qty
                commission = pos.qty * config.commission_per_share * 2
                pnl -= commission
                pnl_pct = pnl / (pos.entry_price * pos.qty) if pos.entry_price * pos.qty > 0 else 0
                r_mult = pnl / pos.initial_risk if pos.initial_risk > 0 else 0

                result.closed_trades.append(ClosedTrade(
                    symbol=pos.symbol, side=pos.side,
                    entry_price=pos.entry_price, exit_price=exit_price,
                    entry_date=pos.entry_date, exit_date=date_str,
                    qty=pos.qty, pnl=round(pnl, 2), pnl_pct=round(pnl_pct, 4),
                    r_multiple=round(r_mult, 2), holding_days=pos.holding_days,
                    exit_reason=exit_reason, commission=round(commission, 2),
                    regime=pos.entry_regime,
                ))
                equity += pnl
            else:
                new_positions.append(pos)

        positions = new_positions

        # ---- Sector Rotation Rebalance ----
        if config.sector_rotation_enabled:
            sr_days_since_rebalance += 1
            if sr_days_since_rebalance >= config.sector_rotation_rebalance_days:
                sr_days_since_rebalance = 0
                etf_returns: List[Tuple[str, float]] = []
                for etf in config.sector_rotation_etfs:
                    if etf not in stock_data:
                        continue
                    edf = stock_data[etf]
                    if date not in edf.index:
                        continue
                    try:
                        cur = float(edf.loc[date, "Close"])
                        idx63 = edf.index.get_loc(date)
                        if idx63 < 63:
                            continue
                        prev = float(edf.iloc[idx63 - 63]["Close"])
                        ret63 = (cur - prev) / prev if prev > 0 else 0
                        etf_returns.append((etf, ret63))
                    except (KeyError, TypeError, ValueError, IndexError):
                        continue
                etf_returns.sort(key=lambda x: x[1], reverse=True)
                new_top = [e[0] for e in etf_returns[:config.sector_rotation_top_n]]

                # Close ETF positions no longer in top
                for pos in list(positions):
                    if pos.strategy == "sector_rotation" and pos.symbol not in new_top:
                        close_price = float(stock_data[pos.symbol].loc[date, "Close"]) if date in stock_data[pos.symbol].index else pos.entry_price
                        pnl = (close_price - pos.entry_price) * pos.qty
                        commission = pos.qty * config.commission_per_share * 2
                        pnl -= commission
                        pnl_pct = pnl / (pos.entry_price * pos.qty) if pos.entry_price * pos.qty > 0 else 0
                        r_mult = pnl / pos.initial_risk if pos.initial_risk > 0 else 0
                        result.closed_trades.append(ClosedTrade(
                            symbol=pos.symbol, side="LONG",
                            entry_price=pos.entry_price, exit_price=close_price,
                            entry_date=pos.entry_date, exit_date=date_str,
                            qty=pos.qty, pnl=round(pnl, 2), pnl_pct=round(pnl_pct, 4),
                            r_multiple=round(r_mult, 2), holding_days=pos.holding_days,
                            exit_reason="SR_ROTATION", commission=round(commission, 2),
                            regime=pos.entry_regime,
                        ))
                        equity += pnl
                        positions.remove(pos)

                sr_top_etfs = new_top

        # ---- Screen for new entries ----
        if len(positions) < config.max_positions:
            short_candidates: List[Tuple[str, float, float]] = []
            long_candidates: List[Tuple[str, float, float]] = []

            # Resolve regime-aware short thresholds
            short_thresh = REGIME_SHORT_THRESHOLDS.get(regime) if config.use_regime_filter else {
                "composite_max": config.composite_max,
                "structure_max": config.structure_max,
            }
            shorts_allowed = short_thresh is not None

            # Mean reversion candidates (used by "mean_reversion" and "hybrid_mr")
            mr_candidates: List[Tuple[str, float, float]] = []
            if config.screener in ("mean_reversion", "hybrid_mr"):
                for sym, m in mr_metrics.items():
                    if sym not in stock_data:
                        continue
                    df = stock_data[sym]
                    if date not in df.index:
                        continue
                    try:
                        rsi_val = float(m["rsi_fast"].loc[date])
                        sma200 = float(m["sma_200"].loc[date])
                        atr_val = float(m["atr"].loc[date])
                        close_px = float(df.loc[date, "Close"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    if any(math.isnan(v) for v in [rsi_val, sma200, atr_val, close_px]):
                        continue
                    already_in = any(p.symbol == sym for p in positions)
                    if already_in:
                        continue
                    if config.mr_require_above_200sma and close_px <= sma200:
                        continue
                    if rsi_val < config.mr_rsi_entry:
                        score = (config.mr_rsi_entry - rsi_val) / config.mr_rsi_entry
                        mr_candidates.append((sym, score, atr_val))

            if config.screener == "mean_reversion":
                long_candidates = mr_candidates

            elif config.screener == "ams":
                # --- AMS v2 Pro screening ---
                for sym, m in ams_metrics.items():
                    if sym not in stock_data:
                        continue
                    df = stock_data[sym]
                    if date not in df.index:
                        continue

                    try:
                        comp_f = float(m["comp_final"].loc[date])
                        rsi_v = float(m["rsi"].loc[date])
                        abs_m = float(m["abs_mom"].loc[date])
                        rel_m = float(m["rel_mom"].loc[date])
                        corr_v = float(m["corr"].loc[date])
                        atr_val = float(m["atr"].loc[date])
                    except (KeyError, TypeError, ValueError):
                        continue

                    if any(math.isnan(v) for v in [comp_f, rsi_v, atr_val]):
                        continue

                    already_in = any(p.symbol == sym for p in positions)
                    if already_in:
                        continue

                    pass_score = comp_f > config.ams_min_score
                    pass_rsi = config.ams_min_rsi <= rsi_v <= config.ams_max_rsi
                    pass_abs = abs_m > 0.5
                    pass_rel = rel_m > 0.5
                    pass_corr = abs(corr_v) < config.ams_corr_max

                    if pass_score and pass_rsi and pass_abs and pass_rel and pass_corr:
                        tier = 3 if comp_f >= 0.8 else (2 if comp_f >= 0.6 else 1)
                        long_candidates.append((sym, comp_f * tier, atr_val))

                    if shorts_allowed and short_thresh is not None:
                        if (comp_f < config.ams_short_max_score and
                                rsi_v < config.ams_short_max_rsi and
                                abs_m < 0.5 and
                                abs(corr_v) < config.ams_corr_max):
                            short_candidates.append((sym, (1 - comp_f), atr_val))

            elif config.screener == "hybrid":
                # --- Hybrid: NX quality filter + AMS volume/HTF ranking ---
                w = config.hybrid_ams_weight
                for sym in metrics:
                    if sym not in stock_data or sym not in ams_metrics:
                        continue
                    df = stock_data[sym]
                    if date not in df.index:
                        continue

                    m = metrics[sym]
                    a = ams_metrics[sym]
                    try:
                        comp_val = float(m["composite"].loc[date])
                        rs_val = float(m["rs"].loc[date])
                        rvol_val = float(m["rvol"].loc[date])
                        struct_val = float(m["structure"].loc[date])
                        atr_val = float(m["atr"].loc[date])
                        vol_score = float(a["vol_score"].loc[date])
                        htf_adj = float(a["htf_adj"].loc[date])
                        ams_rsi = float(a["rsi"].loc[date])
                    except (KeyError, TypeError, ValueError):
                        continue

                    if any(math.isnan(v) for v in [comp_val, rs_val, rvol_val, struct_val, atr_val, vol_score, htf_adj]):
                        continue

                    already_in = any(p.symbol == sym for p in positions)
                    if already_in:
                        continue

                    # NX filter for shorts (unchanged)
                    if shorts_allowed and short_thresh is not None:
                        s_comp_max = short_thresh.get("composite_max", config.composite_max)
                        s_struct_max = short_thresh.get("structure_max", config.structure_max)
                        if (comp_val < s_comp_max and
                                rs_val < config.rs_max and
                                rvol_val >= config.rvol_min and
                                struct_val < s_struct_max):
                            nx_score = (1 - comp_val) * 0.4 + (1 - rs_val) * 0.3 + (1 - struct_val) * 0.3
                            short_candidates.append((sym, nx_score, atr_val))

                    # NX quality gate + RSI band from AMS
                    rsi_ok = config.ams_min_rsi <= ams_rsi <= config.ams_max_rsi
                    if (comp_val >= config.composite_min_long and
                            rs_val >= config.rs_min_long and
                            rvol_val >= config.rvol_min and
                            struct_val >= config.structure_min_long and
                            rsi_ok):
                        nx_score = comp_val * 0.4 + rs_val * 0.3 + struct_val * 0.3
                        ams_boost = vol_score * 0.5 + htf_adj * 0.5
                        combined = nx_score * (1 - w) + ams_boost * w
                        long_candidates.append((sym, combined, atr_val))

            else:
                # --- Original NX screening ---
                for sym, m in metrics.items():
                    if sym not in stock_data:
                        continue
                    df = stock_data[sym]
                    if date not in df.index:
                        continue

                    try:
                        comp_val = float(m["composite"].loc[date])
                        rs_val = float(m["rs"].loc[date])
                        rvol_val = float(m["rvol"].loc[date])
                        struct_val = float(m["structure"].loc[date])
                        atr_val = float(m["atr"].loc[date])
                    except (KeyError, TypeError, ValueError):
                        continue

                    if any(math.isnan(v) for v in [comp_val, rs_val, rvol_val, struct_val, atr_val]):
                        continue

                    already_in = any(p.symbol == sym for p in positions)
                    if already_in:
                        continue

                    if shorts_allowed and short_thresh is not None:
                        s_comp_max = short_thresh.get("composite_max", config.composite_max)
                        s_struct_max = short_thresh.get("structure_max", config.structure_max)
                        if (comp_val < s_comp_max and
                                rs_val < config.rs_max and
                                rvol_val >= config.rvol_min and
                                struct_val < s_struct_max):
                            score = (1 - comp_val) * 0.4 + (1 - rs_val) * 0.3 + (1 - struct_val) * 0.3
                            short_candidates.append((sym, score, atr_val))

                    if (comp_val >= config.composite_min_long and
                            rs_val >= config.rs_min_long and
                            rvol_val >= config.rvol_min and
                            struct_val >= config.structure_min_long):
                        score = comp_val * 0.4 + rs_val * 0.3 + struct_val * 0.3
                        long_candidates.append((sym, score, atr_val))

            short_candidates.sort(key=lambda x: x[1], reverse=True)
            long_candidates.sort(key=lambda x: x[1], reverse=True)

            total_slots = config.max_positions - len(positions)
            short_alloc_pct = alloc["shorts"]
            long_alloc_pct = alloc["longs"]

            short_slots = max(0, min(
                int(total_slots * short_alloc_pct),
                len(short_candidates),
            ))
            long_slots = max(0, min(
                int(total_slots * long_alloc_pct),
                len(long_candidates),
            ))

            max_new = REGIME_MAX_NEW_ENTRIES.get(regime, 3) if config.use_regime_filter else total_slots
            short_slots = min(short_slots, max_new)
            remaining_new = max(0, max_new - short_slots)
            long_slots = min(long_slots, remaining_new)

            # Vol-targeting scale factor
            vol_scale = 1.0
            if config.vol_target_enabled and date in spy_realized_vol.index:
                rv = float(spy_realized_vol.loc[date])
                if rv > 0 and not math.isnan(rv):
                    vol_scale = min(config.vol_target_annual / rv, config.vol_scale_cap)

            def _open_position(sym: str, atr_val: float, side: str, strategy: str = "momentum") -> Optional[Position]:
                df = stock_data[sym]
                price = float(df.loc[date, "Close"])
                # Multi-TF entry improvement: simulate intraday pullback entry
                if config.mtf_entry_enabled and side == "LONG" and atr_val > 0:
                    import random
                    improvement = random.uniform(
                        config.mtf_entry_improvement_atr_min,
                        config.mtf_entry_improvement_atr_max,
                    ) * atr_val
                    price = max(price - improvement, price * 0.99)
                if strategy == "mean_reversion":
                    s_mult = config.mr_stop_atr_mult
                    t_mult = config.mr_tp_atr_mult
                else:
                    s_mult = config.stop_atr_mult
                    t_mult = config.tp_atr_mult
                stop_dist = atr_val * s_mult
                if stop_dist <= 0 or price <= 0:
                    return None
                risk_amount = equity * config.risk_per_trade_pct * vol_scale
                qty_from_risk = int(risk_amount / stop_dist)
                max_qty = int((equity * config.max_position_pct) / price)
                qty = max(1, min(qty_from_risk, max_qty))

                if side == "SHORT":
                    stop_price = price + stop_dist
                    tp_price = price - atr_val * t_mult
                    trail = price + atr_val * config.trailing_atr_mult
                else:
                    stop_price = price - stop_dist
                    tp_price = price + atr_val * t_mult
                    trail = price - atr_val * config.trailing_atr_mult

                return Position(
                    symbol=sym, side=side, entry_price=price,
                    entry_date=date_str, qty=qty,
                    stop_price=round(stop_price, 2),
                    tp_price=round(tp_price, 2),
                    trailing_stop=round(trail, 2),
                    atr_at_entry=atr_val,
                    initial_risk=stop_dist * qty,
                    entry_regime=regime,
                    strategy=strategy,
                )

            for sym, score, atr_val in short_candidates[:short_slots]:
                pos = _open_position(sym, atr_val, "SHORT")
                if pos:
                    positions.append(pos)

            for sym, score, atr_val in long_candidates[:long_slots]:
                strat = "momentum"
                pos = _open_position(sym, atr_val, "LONG", strategy=strat)
                if pos:
                    positions.append(pos)

            # MR entries get remaining slots
            if config.screener == "hybrid_mr" and mr_candidates:
                mr_candidates.sort(key=lambda x: x[1], reverse=True)
                mr_slots = max(0, config.max_positions - len(positions))
                mr_slots = min(mr_slots, 3, len(mr_candidates))
                for sym, score, atr_val in mr_candidates[:mr_slots]:
                    if any(p.symbol == sym for p in positions):
                        continue
                    pos = _open_position(sym, atr_val, "LONG", strategy="mean_reversion")
                    if pos:
                        positions.append(pos)

            # Sector rotation ETF entries
            if config.sector_rotation_enabled and sr_top_etfs:
                existing_sr = {p.symbol for p in positions if p.strategy == "sector_rotation"}
                sr_budget = equity * config.sector_rotation_alloc_pct
                sr_per_etf = sr_budget / max(1, config.sector_rotation_top_n)
                for etf in sr_top_etfs:
                    if etf in existing_sr:
                        continue
                    if etf not in stock_data or date not in stock_data[etf].index:
                        continue
                    try:
                        price = float(stock_data[etf].loc[date, "Close"])
                        atr_val = float(compute_atr(stock_data[etf]).loc[date]) if date in compute_atr(stock_data[etf]).index else price * 0.015
                        if price <= 0:
                            continue
                        qty = max(1, int(sr_per_etf / price))
                        stop_dist = atr_val * config.stop_atr_mult
                        stop_price = price - stop_dist
                        tp_price = price + atr_val * config.tp_atr_mult
                        trail = price - atr_val * config.trailing_atr_mult
                        positions.append(Position(
                            symbol=etf, side="LONG", entry_price=price,
                            entry_date=date_str, qty=qty,
                            stop_price=round(stop_price, 2),
                            tp_price=round(tp_price, 2),
                            trailing_stop=round(trail, 2),
                            atr_at_entry=atr_val,
                            initial_risk=stop_dist * qty,
                            entry_regime=regime,
                            strategy="sector_rotation",
                        ))
                    except (KeyError, TypeError, ValueError):
                        continue

        # ---- Pairs Trading ----
        if config.pairs_enabled and _SECTOR_MAP and need_nx:
            pairs_positions = [p for p in positions if p.strategy == "pairs_long" or p.strategy == "pairs_short"]
            if len(pairs_positions) < config.pairs_max_pairs * 2:
                # Group symbols by sector
                sector_groups: Dict[str, List[Tuple[str, float]]] = {}
                for sym, m in metrics.items():
                    if sym not in stock_data or date not in stock_data[sym].index:
                        continue
                    sector = _SECTOR_MAP.get(sym, "Unknown")
                    if sector == "Unknown":
                        continue
                    try:
                        comp = float(m["composite"].loc[date])
                        if math.isnan(comp):
                            continue
                    except (KeyError, TypeError, ValueError):
                        continue
                    if sector not in sector_groups:
                        sector_groups[sector] = []
                    sector_groups[sector].append((sym, comp))

                for sector, group in sector_groups.items():
                    if len(group) < 3:
                        continue
                    group.sort(key=lambda x: x[1], reverse=True)
                    long_sym = group[0][0]
                    short_sym = group[-1][0]

                    already_paired = any(p.symbol in (long_sym, short_sym) for p in positions)
                    if already_paired:
                        continue

                    try:
                        long_price = float(stock_data[long_sym].loc[date, "Close"])
                        short_price = float(stock_data[short_sym].loc[date, "Close"])
                        long_atr = float(compute_atr(stock_data[long_sym]).loc[date]) if date in compute_atr(stock_data[long_sym]).index else long_price * 0.015
                        short_atr = float(compute_atr(stock_data[short_sym]).loc[date]) if date in compute_atr(stock_data[short_sym]).index else short_price * 0.015
                    except (KeyError, TypeError, ValueError):
                        continue

                    pair_notional = equity * 0.02
                    long_qty = max(1, int(pair_notional / long_price))
                    short_qty = max(1, int(pair_notional / short_price))

                    # Long leg
                    positions.append(Position(
                        symbol=long_sym, side="LONG", entry_price=long_price,
                        entry_date=date_str, qty=long_qty,
                        stop_price=round(long_price - long_atr * 2.0, 2),
                        tp_price=round(long_price + long_atr * 3.0, 2),
                        trailing_stop=round(long_price - long_atr * 2.5, 2),
                        atr_at_entry=long_atr,
                        initial_risk=long_atr * 2.0 * long_qty,
                        entry_regime=regime, strategy="pairs_long",
                    ))
                    # Short leg
                    positions.append(Position(
                        symbol=short_sym, side="SHORT", entry_price=short_price,
                        entry_date=date_str, qty=short_qty,
                        stop_price=round(short_price + short_atr * 2.0, 2),
                        tp_price=round(short_price - short_atr * 3.0, 2),
                        trailing_stop=round(short_price + short_atr * 2.5, 2),
                        atr_at_entry=short_atr,
                        initial_risk=short_atr * 2.0 * short_qty,
                        entry_regime=regime, strategy="pairs_short",
                    ))

                    if len([p for p in positions if p.strategy in ("pairs_long", "pairs_short")]) >= config.pairs_max_pairs * 2:
                        break

        # ---- Options overlay (simplified daily P&L adjustments) ----
        if config.options_overlay_enabled:
            trading_days_per_month = 21
            daily_condor = config.options_condor_monthly_income_pct / trading_days_per_month
            daily_put_cost = config.options_put_monthly_cost_pct / trading_days_per_month

            # Iron condors: income in CHOPPY, loss when big moves happen
            if regime == "CHOPPY":
                spy_daily_move = abs(float(spy_returns.loc[date])) if date in spy_returns.index else 0
                if spy_daily_move < 0.015:
                    equity += equity * daily_condor
                else:
                    equity -= equity * (config.options_condor_max_loss_pct / trading_days_per_month)

            # Protective puts: constant cost, floor on monthly loss
            equity -= equity * daily_put_cost

        prev_equity = result.equity_curve[-1] if result.equity_curve else config.initial_equity

        # Protective put floor: if monthly loss exceeds floor, clamp
        if config.options_overlay_enabled and len(result.equity_curve) >= trading_days_per_month:
            month_start = result.equity_curve[-trading_days_per_month]
            month_loss = (equity - month_start) / month_start if month_start > 0 else 0
            if month_loss < -config.options_put_floor_monthly_pct:
                equity = month_start * (1 - config.options_put_floor_monthly_pct)

        daily_ret = (equity - prev_equity) / prev_equity if prev_equity > 0 else 0
        result.equity_curve.append(round(equity, 2))
        result.dates.append(date_str)
        result.daily_returns.append(round(daily_ret, 6))

    result.regime_day_counts = regime_day_counts
    return result


def _slice_metrics(trades: List[ClosedTrade]) -> Dict[str, Any]:
    """Compute win rate, P&L, and avg R for a trade slice."""
    n = len(trades)
    if n == 0:
        return {"count": 0, "pnl": 0, "win_rate": 0, "avg_r": 0, "avg_pnl": 0}
    wins = [t for t in trades if t.pnl > 0]
    total_pnl = sum(t.pnl for t in trades)
    return {
        "count": n,
        "pnl": round(total_pnl, 2),
        "win_rate": round(len(wins) / n, 4),
        "avg_r": round(float(np.mean([t.r_multiple for t in trades])), 2),
        "avg_pnl": round(total_pnl / n, 2),
    }


def compute_summary(result: BacktestResult) -> Dict[str, Any]:
    """Compute performance summary from backtest results."""
    trades = result.closed_trades
    n = len(trades)
    if n == 0:
        return {"error": "No trades generated"}

    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]
    total_pnl = sum(t.pnl for t in trades)
    total_commission = sum(t.commission for t in trades)

    win_rate = len(wins) / n
    avg_win = float(np.mean([t.pnl for t in wins])) if wins else 0
    avg_loss = float(np.mean([abs(t.pnl) for t in losses])) if losses else 0
    profit_factor = sum(t.pnl for t in wins) / sum(abs(t.pnl) for t in losses) if losses else float("inf")
    avg_r = float(np.mean([t.r_multiple for t in trades]))

    rets = np.array(result.daily_returns)
    rets_clean = rets[~np.isnan(rets)]
    ann_return = (result.equity_curve[-1] / result.config.initial_equity) ** (252 / max(len(rets_clean), 1)) - 1 if result.equity_curve else 0
    ann_vol = float(np.std(rets_clean) * np.sqrt(252)) if len(rets_clean) > 1 else 0
    sharpe = ann_return / ann_vol if ann_vol > 0 else 0

    peak = result.config.initial_equity
    max_dd = 0.0
    for eq in result.equity_curve:
        peak = max(peak, eq)
        dd = (peak - eq) / peak
        max_dd = max(max_dd, dd)

    short_trades = [t for t in trades if t.side == "SHORT"]
    long_trades = [t for t in trades if t.side == "LONG"]
    short_win_rate = len([t for t in short_trades if t.pnl > 0]) / len(short_trades) if short_trades else 0
    long_win_rate = len([t for t in long_trades if t.pnl > 0]) / len(long_trades) if long_trades else 0

    avg_holding = float(np.mean([t.holding_days for t in trades]))

    exit_reasons: Dict[str, int] = {}
    for t in trades:
        exit_reasons[t.exit_reason] = exit_reasons.get(t.exit_reason, 0) + 1

    regime_breakdown: Dict[str, Any] = {}
    for regime in set(t.regime for t in trades):
        regime_trades = [t for t in trades if t.regime == regime]
        regime_breakdown[regime] = _slice_metrics(regime_trades)

    side_by_regime: Dict[str, Any] = {}
    for regime in set(t.regime for t in trades):
        side_by_regime[regime] = {
            "shorts": _slice_metrics([t for t in trades if t.regime == regime and t.side == "SHORT"]),
            "longs": _slice_metrics([t for t in trades if t.regime == regime and t.side == "LONG"]),
        }

    exit_by_side: Dict[str, Dict[str, int]] = {"SHORT": {}, "LONG": {}}
    for t in trades:
        exit_by_side[t.side][t.exit_reason] = exit_by_side[t.side].get(t.exit_reason, 0) + 1

    return {
        "total_trades": n,
        "short_trades": len(short_trades),
        "long_trades": len(long_trades),
        "win_rate": round(win_rate, 4),
        "short_win_rate": round(short_win_rate, 4),
        "long_win_rate": round(long_win_rate, 4),
        "total_pnl": round(total_pnl, 2),
        "total_commission": round(total_commission, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(min(profit_factor, 999.0), 2),
        "avg_r_multiple": round(avg_r, 2),
        "annualized_return": round(ann_return, 4),
        "annualized_volatility": round(ann_vol, 4),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown": round(max_dd, 4),
        "avg_holding_days": round(avg_holding, 1),
        "starting_equity": result.config.initial_equity,
        "ending_equity": result.equity_curve[-1] if result.equity_curve else result.config.initial_equity,
        "exit_reasons": exit_reasons,
        "exit_by_side": exit_by_side,
        "regime_breakdown": regime_breakdown,
        "side_by_regime": side_by_regime,
        "regime_day_counts": result.regime_day_counts,
    }


def save_results(result: BacktestResult, summary: Dict[str, Any]) -> Path:
    """Save backtest results to JSON."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"backtest_{ts}.json"

    cfg = result.config
    config_dict: Dict[str, Any] = {
        "screener": cfg.screener,
        "initial_equity": cfg.initial_equity,
        "risk_per_trade_pct": cfg.risk_per_trade_pct,
        "max_position_pct": cfg.max_position_pct,
        "stop_atr_mult": cfg.stop_atr_mult,
        "tp_atr_mult": cfg.tp_atr_mult,
        "trailing_atr_mult": cfg.trailing_atr_mult,
        "max_positions": cfg.max_positions,
        "max_holding_days": cfg.max_holding_days,
        "use_regime_filter": cfg.use_regime_filter,
    }
    if cfg.screener == "nx":
        config_dict.update({
            "composite_max": cfg.composite_max,
            "rs_max": cfg.rs_max,
            "composite_min_long": cfg.composite_min_long,
            "rs_min_long": cfg.rs_min_long,
            "structure_min_long": cfg.structure_min_long,
        })
    else:
        config_dict.update({
            "ams_min_score": cfg.ams_min_score,
            "ams_min_rsi": cfg.ams_min_rsi,
            "ams_max_rsi": cfg.ams_max_rsi,
            "ams_corr_max": cfg.ams_corr_max,
            "ams_short_max_score": cfg.ams_short_max_score,
            "ams_short_max_rsi": cfg.ams_short_max_rsi,
        })

    output = {
        "timestamp": datetime.now().isoformat(),
        "config": config_dict,
        "summary": summary,
        "equity_curve_length": len(result.equity_curve),
        "equity_start": result.equity_curve[0] if result.equity_curve else None,
        "equity_end": result.equity_curve[-1] if result.equity_curve else None,
        "all_trades": [
            {
                "symbol": t.symbol, "side": t.side,
                "entry": t.entry_price, "exit": t.exit_price,
                "entry_date": t.entry_date, "exit_date": t.exit_date,
                "pnl": t.pnl, "r_mult": t.r_multiple,
                "days": t.holding_days, "reason": t.exit_reason,
                "regime": t.regime,
            }
            for t in result.closed_trades
        ],
    }

    out_path.write_text(json.dumps(output, indent=2))
    logger.info("Results saved to %s", out_path)
    return out_path


def _fmt_pct(val: float) -> str:
    return f"{val:.2%}"


def main() -> None:
    parser = argparse.ArgumentParser(description="NX Strategy Backtest")
    parser.add_argument("--years", type=int, default=2, help="Lookback years (default 2)")
    parser.add_argument("--initial-equity", type=float, default=1_900_000, help="Starting equity")
    parser.add_argument("--max-positions", type=int, default=25)
    parser.add_argument("--risk-pct", type=float, default=0.01)
    parser.add_argument("--no-regime", action="store_true", help="Disable regime filter")
    parser.add_argument("--symbols", type=int, default=200, help="Max symbols from universe")
    parser.add_argument(
        "--screener",
        choices=["nx", "ams", "hybrid", "mean_reversion", "hybrid_mr"],
        default="hybrid",
        help="Screener mode",
    )
    parser.add_argument("--vol-target", action="store_true", help="Enable volatility targeting")
    parser.add_argument("--sector-rotation", action="store_true", help="Enable sector rotation overlay")
    parser.add_argument("--options-overlay", action="store_true", help="Enable simplified options P&L overlay")
    parser.add_argument("--mtf-entry", action="store_true", help="Enable multi-TF entry improvement simulation")
    parser.add_argument("--pairs", action="store_true", help="Enable pairs trading overlay")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    config = BacktestConfig(
        initial_equity=args.initial_equity,
        max_positions=args.max_positions,
        risk_per_trade_pct=args.risk_pct,
        use_regime_filter=not args.no_regime,
        screener=args.screener,
        vol_target_enabled=getattr(args, "vol_target", False),
        sector_rotation_enabled=getattr(args, "sector_rotation", False),
        options_overlay_enabled=getattr(args, "options_overlay", False),
        mtf_entry_enabled=getattr(args, "mtf_entry", False),
        pairs_enabled=getattr(args, "pairs", False),
    )

    try:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from universe_builder import get_full_universe
        symbols = get_full_universe()[:args.symbols]
    except ImportError:
        symbols = [
            "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
            "JPM", "V", "MA", "UNH", "HD", "PG", "JNJ", "XOM",
            "CVX", "BAC", "WFC", "ABBV", "KO", "PEP", "MRK", "LLY",
            "COST", "WMT", "DIS", "NFLX", "CRM", "AMD", "INTC",
            "QCOM", "TXN", "AVGO", "ADBE", "ORCL", "CSCO", "IBM",
            "GS", "MS", "BLK", "AXP", "CAT", "DE", "RTX", "BA",
            "GE", "MMM", "HON", "UPS", "FDX",
        ]
        logger.info("Using default universe of %d symbols", len(symbols))

    regime_label = "ON" if config.use_regime_filter else "OFF"
    logger.info(
        "Starting backtest: %d symbols, %d years, $%s equity, regime=%s, screener=%s",
        len(symbols), args.years, f"{args.initial_equity:,.0f}", regime_label, config.screener,
    )

    result = run_backtest(symbols, config, years=args.years)
    summary = compute_summary(result)

    screener_label = config.screener.upper()
    print("\n" + "=" * 70)
    print(f"BACKTEST RESULTS — {screener_label} Screener" +
          (" (with regime filter)" if config.use_regime_filter else " (NO regime filter)"))
    print("=" * 70)

    simple_keys = [
        "total_trades", "short_trades", "long_trades",
        "total_pnl", "total_commission",
        "avg_win", "avg_loss", "profit_factor", "avg_r_multiple",
    ]
    pct_keys = [
        "win_rate", "short_win_rate", "long_win_rate",
        "annualized_return", "annualized_volatility",
        "sharpe_ratio", "max_drawdown",
    ]
    for k in simple_keys:
        v = summary.get(k)
        if isinstance(v, float):
            print(f"  {k:>25s}: {v:>12,.2f}")
        else:
            print(f"  {k:>25s}: {v}")
    for k in pct_keys:
        v = summary.get(k)
        if isinstance(v, float):
            if k == "sharpe_ratio":
                print(f"  {k:>25s}: {v:>12.2f}")
            else:
                print(f"  {k:>25s}: {_fmt_pct(v):>12s}")
        else:
            print(f"  {k:>25s}: {v}")

    print(f"  {'avg_holding_days':>25s}: {summary.get('avg_holding_days', 0):>12.1f}")
    print(f"  {'starting_equity':>25s}: {summary.get('starting_equity', 0):>12,.2f}")
    print(f"  {'ending_equity':>25s}: {summary.get('ending_equity', 0):>12,.2f}")

    print(f"\n  Exit reasons:")
    for reason, count in summary.get("exit_reasons", {}).items():
        print(f"    {reason:>12s}: {count}")

    ebs = summary.get("exit_by_side", {})
    for side_name in ("SHORT", "LONG"):
        side_exits = ebs.get(side_name, {})
        if side_exits:
            print(f"\n  Exit reasons ({side_name}):")
            for reason, count in side_exits.items():
                print(f"    {reason:>12s}: {count}")

    rb = summary.get("regime_breakdown", {})
    if rb:
        print(f"\n  Regime breakdown:")
        for regime, stats in sorted(rb.items()):
            print(
                f"    {regime:>18s}: {stats['count']:>4d} trades, "
                f"pnl=${stats['pnl']:>10,.2f}, "
                f"win_rate={_fmt_pct(stats['win_rate'])}, "
                f"avg_r={stats['avg_r']:>5.2f}"
            )

    sbr = summary.get("side_by_regime", {})
    if sbr:
        print(f"\n  Side-by-regime detail:")
        for regime, sides in sorted(sbr.items()):
            for side_name in ("shorts", "longs"):
                s = sides.get(side_name, {})
                if s.get("count", 0) > 0:
                    print(
                        f"    {regime:>18s} {side_name:>6s}: {s['count']:>4d} trades, "
                        f"pnl=${s['pnl']:>10,.2f}, "
                        f"win={_fmt_pct(s['win_rate'])}, "
                        f"avg_r={s['avg_r']:>5.2f}"
                    )

    rdc = summary.get("regime_day_counts", {})
    if rdc:
        total_days = sum(rdc.values())
        print(f"\n  Regime days ({total_days} total):")
        for regime, count in sorted(rdc.items()):
            print(f"    {regime:>18s}: {count:>4d} days ({count/total_days:.0%})")

    print("=" * 70)

    out_path = save_results(result, summary)
    print(f"\nFull results: {out_path}")


if __name__ == "__main__":
    main()
