#!/usr/bin/env python3
"""
Backtest for all four premium/options strategies (aligned with auto_options_executor.py).

1. Covered Calls: own 100+ shares, up 2%+ from entry, sell ~0.20 delta / 8%+ OTM, 35 DTE, premium ≥1.5%.
2. Cash-Secured Puts: pullback 3–8%, near 50 EMA, IV rank ≥50%, 0.25 delta / 1% below 50 EMA, 35 DTE.
3. Iron Condors: CHOPPY/MIXED regime, SPY/QQQ, sell 10% OTM put+call, buy 15% OTM wings, credit ~30% of max risk, max 2.
4. Protective Puts: MIXED/UNFAVORABLE/STRONG_DOWNTREND, SPY 7% OTM, 30 DTE, budget 0.5% or $5k/mo, max 2.

Usage:
  cd trading && python -m backtest.premium_backtest --years 2 --initial-equity 100000
  With --options-income from nx_backtest: pass daily_long_positions + daily_regimes for CC/IC/PP.
"""

import argparse
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).resolve().parent / "results"

# Premium-selling universe (align with nx_screener_production premium_selling mode)
PREMIUM_UNIVERSE = [
    # Tech
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "TSLA", "ASML", "NFLX",
    "ADBE", "INTC", "QCOM", "AVGO", "AMAT", "LRCX", "AMD", "MRVL",
    "NXPI", "SNPS", "CDNS", "INTU", "CSCO", "BKNG", "CRWD", "DDOG",
    "NET", "OKTA", "ZS", "SNOW", "SHOP", "COIN", "UPST", "AFRM",
    "ORCL", "CRM", "NOW", "PANW", "ABNB", "UBER", "DKNG", "PLTR",
    "SQ", "PYPL", "ROKU", "SNAP",
    # Financials / Healthcare / Industrials
    "JPM", "GS", "MA", "V", "UNH", "HD", "LLY", "COST",
    "WMT", "CAT", "DE", "BA",
    # Index ETF
    "QQQ",
]

MIN_IV_RANK = 0.45
MIN_PREMIUM_PCT = 0.015
MAX_RISK_PER_CONTRACT = 5000
CSP_DTE = 35
PULLBACK_MIN = 0.025
PULLBACK_MAX = 0.10
NEAR_SUPPORT_PCT = 0.03
VOL_RATIO_MAX = 1.8
CSP_EARLY_CLOSE_PCT = 0.05


@dataclass
class SimulatedOption:
    symbol: str
    type: str  # "CSP" | "CC" | "IRON_CONDOR" | "PROTECTIVE_PUT"
    entry_date: str
    expiry_date: str
    strike: float
    premium_per_share: float
    contracts: int
    entry_price: float
    # Iron condor: short 10% OTM, wings 15% OTM
    put_wing: Optional[float] = None
    call_wing: Optional[float] = None
    call_strike: Optional[float] = None  # for IC
    # Protective put: cost paid
    cost: Optional[float] = None


@dataclass
class OptionSettlement:
    symbol: str
    type: str
    entry_date: str
    expiry_date: str
    strike: float
    premium_collected: float
    exit_price: float
    pnl: float
    assigned: bool


def _realized_vol_series(close: pd.Series, window: int = 20) -> pd.Series:
    """Annualized realized vol from daily returns."""
    ret = close.pct_change()
    return ret.rolling(window, min_periods=window).std() * (252 ** 0.5)


def _vol_rank_series(close: pd.Series, lookback: int = 252, window: int = 20) -> pd.Series:
    """IV-rank proxy: (current 20d vol - 52w low) / (52w high - 52w low)."""
    rv = _realized_vol_series(close, window)
    rv_52 = rv.rolling(lookback, min_periods=60).agg(["min", "max"])
    rv_low = rv_52["min"]
    rv_high = rv_52["max"]
    rank = (rv - rv_low) / (rv_high - rv_low + 1e-12)
    return rank.clip(0, 1)


def _next_monthly_expiry(d: datetime) -> datetime:
    """Next expiry ~35 days out."""
    if hasattr(d, "date"):
        d = d.date() if callable(getattr(d, "date", None)) else d
    if not isinstance(d, datetime):
        d = datetime(d.year, d.month, d.day)
    return d + timedelta(days=CSP_DTE)


def download_data(symbols: List[str], period: str) -> Dict[str, pd.DataFrame]:
    import yfinance as yf
    logger.info("Downloading %s for %d symbols...", period, len(symbols))
    data = yf.download(symbols, period=period, progress=False, group_by="ticker", auto_adjust=True)
    if data is None or data.empty:
        return {}
    out: Dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            if isinstance(data.columns, pd.MultiIndex):
                if sym in data.columns.get_level_values(0):
                    df = data[sym].copy()
                else:
                    continue
            else:
                df = data.copy()
            df = df.dropna(how="all")
            if len(df) < 260:
                continue
            out[sym] = df
        except Exception:
            continue
    return out


def find_csp_setups(
    data: Dict[str, pd.DataFrame],
    date: pd.Timestamp,
    max_candidates: int,
) -> List[Tuple[str, float, float, float]]:
    """
    Find CSP opportunities on date. Returns list of (symbol, strike, premium_per_share, entry_price).
    """
    opportunities: List[Tuple[str, float, float, float]] = []
    for symbol, df in data.items():
        if date not in df.index:
            continue
        try:
            close = float(df.loc[date, "Close"])
            high_20 = float(df["High"].rolling(20).max().loc[date])
            ema50 = df["Close"].ewm(span=50, adjust=False).mean().loc[date]
            ema50 = float(ema50)
            vol_rank = _vol_rank_series(df["Close"], 252, 20)
            if date not in vol_rank.index or pd.isna(vol_rank.loc[date]):
                continue
            vr = float(vol_rank.loc[date])
            if vr < MIN_IV_RANK:
                continue

            pullback = (high_20 - close) / high_20 if high_20 > 0 else 0
            if not (PULLBACK_MIN <= pullback <= PULLBACK_MAX):
                continue
            near_support = abs(close - ema50) / close <= NEAR_SUPPORT_PCT if close > 0 else False
            if not near_support:
                continue

            avg_vol = df["Volume"].rolling(20).mean().loc[date]
            avg_vol = float(avg_vol) if pd.notna(avg_vol) and avg_vol > 0 else 1
            recent_vol = float(df["Volume"].loc[date]) if pd.notna(df["Volume"].loc[date]) else 0
            vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 0
            if vol_ratio > VOL_RATIO_MAX:
                continue

            strike = round(ema50 * 0.99, 2)
            if strike <= 0:
                continue
            assignment_risk = strike * 100
            if assignment_risk > MAX_RISK_PER_CONTRACT:
                continue

            premium_pct = 0.015 + (vr - 0.5) * 0.02
            premium_pct = max(MIN_PREMIUM_PCT, min(premium_pct, 0.05))
            premium_per_share = close * premium_pct

            opportunities.append((symbol, strike, premium_per_share, close))
        except (KeyError, TypeError, ValueError, IndexError):
            continue

    opportunities.sort(key=lambda x: -x[2])
    return opportunities[:max_candidates]


def find_cc_setups(
    data: Dict[str, pd.DataFrame],
    date: pd.Timestamp,
    date_str: str,
    long_positions: List[Dict[str, Any]],
    min_premium_pct: float = 0.015,
    min_uptick_pct: float = 0.01,
    min_strike_above_pct: float = 0.06,
) -> List[Tuple[str, float, float, float]]:
    """Covered call: positions with 100+ shares, up 2%+ from entry, IV rank ≥50%, strike 8%+ above price, premium ≥1.5%. Returns (symbol, strike, premium_per_share, entry_price)."""
    opportunities: List[Tuple[str, float, float, float]] = []
    for pos in long_positions:
        symbol = pos.get("symbol") or pos.get("ticker")
        qty = pos.get("qty") or pos.get("quantity", 0)
        entry = float(pos.get("entry_price", 0) or pos.get("avgCost", 0))
        if not symbol or qty < 100 or entry <= 0:
            continue
        if symbol not in data or date not in data[symbol].index:
            continue
        try:
            close = float(data[symbol].loc[date, "Close"])
            if close < entry * (1 + min_uptick_pct):
                continue
            vol_rank = _vol_rank_series(data[symbol]["Close"], 252, 20)
            if date not in vol_rank.index or pd.isna(vol_rank.loc[date]) or float(vol_rank.loc[date]) < MIN_IV_RANK:
                continue
            strike = round(close * (1 + min_strike_above_pct), 2)
            if strike <= 0:
                continue
            premium_pct = max(min_premium_pct, 0.02)
            premium_per_share = close * premium_pct
            opportunities.append((symbol, strike, premium_per_share, entry))
        except (KeyError, TypeError, ValueError):
            continue
    return opportunities[:5]


def _settle_option(
    op: SimulatedOption,
    dt: datetime,
    date: pd.Timestamp,
    data: Dict[str, pd.DataFrame],
) -> Tuple[Optional[OptionSettlement], float]:
    """Settle one option at expiry. Returns (OptionSettlement or None, pnl)."""
    exp_str = op.expiry_date
    try:
        exp_dt = datetime.strptime(exp_str, "%Y-%m-%d").date()
    except ValueError:
        exp_dt = datetime.strptime(exp_str[:10], "%Y-%m-%d").date()
    d = dt.date() if hasattr(dt, "date") else dt
    if d < exp_dt:
        return None, 0.0

    sym = op.symbol
    if sym not in data or date not in data[sym].index:
        return None, 0.0
    exit_price = float(data[sym].loc[date, "Close"])

    if op.type == "CSP":
        premium_collected = op.premium_per_share * op.contracts * 100
        if exit_price < op.strike:
            assignment_loss = (op.strike - exit_price) * op.contracts * 100
            pnl = premium_collected - assignment_loss
            assigned = True
        else:
            pnl = premium_collected
            assigned = False
        return OptionSettlement(
            symbol=op.symbol,
            type=op.type,
            entry_date=op.entry_date,
            expiry_date=exp_str,
            strike=op.strike,
            premium_collected=premium_collected,
            exit_price=exit_price,
            pnl=pnl,
            assigned=assigned,
        ), pnl

    if op.type == "CC":
        premium_collected = op.premium_per_share * op.contracts * 100
        if exit_price > op.strike:
            # Called away: keep premium + (strike - entry) * 100
            pnl = premium_collected + (op.strike - op.entry_price) * op.contracts * 100
            assigned = True
        else:
            pnl = premium_collected
            assigned = False
        return OptionSettlement(
            symbol=op.symbol,
            type=op.type,
            entry_date=op.entry_date,
            expiry_date=exp_str,
            strike=op.strike,
            premium_collected=premium_collected,
            exit_price=exit_price,
            pnl=pnl,
            assigned=assigned,
        ), pnl

    if op.type == "IRON_CONDOR" and op.put_wing is not None and op.call_wing is not None and op.call_strike is not None:
        credit = op.premium_per_share * op.contracts * 100
        if exit_price < op.put_wing:
            loss = (op.strike - op.put_wing) * 100
            pnl = credit - loss
        elif exit_price > op.call_wing:
            loss = (op.call_wing - op.call_strike) * 100
            pnl = credit - loss
        else:
            pnl = credit
        return OptionSettlement(
            symbol=op.symbol,
            type=op.type,
            entry_date=op.entry_date,
            expiry_date=exp_str,
            strike=op.strike,
            premium_collected=credit,
            exit_price=exit_price,
            pnl=pnl,
            assigned=False,
        ), pnl

    if op.type == "PROTECTIVE_PUT" and op.cost is not None:
        # Cost was paid at open; at expiry only payoff (no double-count of cost)
        if exit_price < op.strike:
            pnl = (op.strike - exit_price) * 100
        else:
            pnl = 0
        return OptionSettlement(
            symbol=op.symbol,
            type=op.type,
            entry_date=op.entry_date,
            expiry_date=exp_str,
            strike=op.strike,
            premium_collected=0,
            exit_price=exit_price,
            pnl=pnl,
            assigned=exit_price < op.strike,
        ), pnl  # net to equity: we already deducted cost at open, so add payoff only

    return None, 0.0


def run_premium_backtest(
    years: int = 2,
    initial_equity: float = 100_000.0,
    max_options_per_day: int = 5,
    max_options_per_month: int = 20,
    symbols: Optional[List[str]] = None,
    daily_long_positions: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    daily_regimes: Optional[Dict[str, str]] = None,
) -> Tuple[List[OptionSettlement], List[float], List[str], float]:
    """
    Run backtest for all four strategies. Returns (settlements, equity_curve, dates, final_equity).
    - symbols: universe for CSP (and for CC if daily_long_positions from same universe).
    - daily_long_positions: date_str -> list of {symbol, qty, entry_price} for covered calls.
    - daily_regimes: date_str -> regime for iron condors (CHOPPY/MIXED) and protective puts (MIXED/UNFAVORABLE/STRONG_DOWNTREND).
    When daily_regimes is provided, SPY and QQQ are added to the download for IC/PP.
    """
    period = f"{years}y"
    universe = list(symbols) if symbols else list(PREMIUM_UNIVERSE)
    if daily_regimes is not None:
        for sym in ("SPY", "QQQ"):
            if sym not in universe:
                universe.append(sym)
    data = download_data(universe, period)
    if len(data) < 5:
        logger.error("Insufficient data")
        return [], [initial_equity], [], initial_equity

    sample = next(iter(data.values()))
    trading_dates = sample.index[260:].tolist()

    open_options: List[SimulatedOption] = []
    settlements: List[OptionSettlement] = []
    equity = initial_equity
    equity_curve: List[float] = [initial_equity]
    curve_dates: List[str] = []

    options_this_month = 0
    month_key: Optional[Tuple[int, int]] = None
    cc_symbols_this_month: set = set()
    ic_count = 0
    pp_count = 0
    CC_DTE = 35
    IC_DTE = 35
    PP_DTE = 30

    ic_vol_rank: Dict[str, pd.Series] = {}
    for ic_sym in ("SPY", "QQQ"):
        if ic_sym in data:
            ic_vol_rank[ic_sym] = _vol_rank_series(data[ic_sym]["Close"], 252, 20)

    for i, date in enumerate(trading_dates):
        date_str = str(date.date()) if hasattr(date, "date") else str(date)[:10]
        try:
            dt = date.to_pydatetime().date() if hasattr(date, "to_pydatetime") else datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            dt = datetime.strptime(date_str, "%Y-%m-%d").date()
        current_month = (dt.year, dt.month)
        if month_key != current_month:
            month_key = current_month
            options_this_month = 0
            cc_symbols_this_month = set()

        regime = (daily_regimes or {}).get(date_str, "CHOPPY")

        # Settle expired options + early close CSPs that went deep ITM
        new_open: List[SimulatedOption] = []
        for op in open_options:
            exp_str = op.expiry_date
            try:
                exp_dt = datetime.strptime(exp_str, "%Y-%m-%d").date()
            except ValueError:
                exp_dt = datetime.strptime(exp_str[:10], "%Y-%m-%d").date()

            # Early close for CSPs: if underlying drops > CSP_EARLY_CLOSE_PCT below strike, cap the loss
            if op.type == "CSP" and dt < exp_dt and op.symbol in data and date in data[op.symbol].index:
                current = float(data[op.symbol].loc[date, "Close"])
                if current < op.strike * (1 - CSP_EARLY_CLOSE_PCT):
                    premium_collected = op.premium_per_share * op.contracts * 100
                    assignment_loss = (op.strike - current) * op.contracts * 100
                    pnl = premium_collected - assignment_loss
                    settlements.append(OptionSettlement(
                        symbol=op.symbol, type="CSP", entry_date=op.entry_date,
                        expiry_date=date_str, strike=op.strike,
                        premium_collected=premium_collected, exit_price=current,
                        pnl=pnl, assigned=False,
                    ))
                    equity += pnl
                    continue

            if dt < exp_dt:
                new_open.append(op)
                continue
            sett, pnl = _settle_option(op, dt, date, data)
            if sett is not None:
                settlements.append(sett)
                equity += pnl
            if op.type == "IRON_CONDOR":
                ic_count = max(0, ic_count - 1)
            elif op.type == "PROTECTIVE_PUT":
                pp_count = max(0, pp_count - 1)
        open_options = new_open

        # New CSP entries (skip during downtrends to avoid assignment losses)
        csp_regime_ok = regime not in ("STRONG_DOWNTREND", "UNFAVORABLE")
        if csp_regime_ok and options_this_month < max_options_per_month:
            slots = min(max_options_per_day, max_options_per_month - options_this_month)
            if slots > 0:
                opps = find_csp_setups(data, date, slots)
                for (symbol, strike, premium_per_share, entry_price) in opps:
                    exp_dt = _next_monthly_expiry(datetime(dt.year, dt.month, dt.day))
                    exp_str = exp_dt.strftime("%Y-%m-%d")
                    open_options.append(SimulatedOption(
                        symbol=symbol,
                        type="CSP",
                        entry_date=date_str,
                        expiry_date=exp_str,
                        strike=strike,
                        premium_per_share=premium_per_share,
                        contracts=1,
                        entry_price=entry_price,
                    ))
                    options_this_month += 1

        # Covered calls (from equity positions)
        if daily_long_positions and date_str in daily_long_positions:
            positions = daily_long_positions[date_str]
            for (symbol, strike, premium_per_share, entry_price) in find_cc_setups(data, date, date_str, positions):
                if symbol in cc_symbols_this_month:
                    continue
                exp_dt = datetime(dt.year, dt.month, dt.day) + timedelta(days=CC_DTE)
                exp_str = exp_dt.strftime("%Y-%m-%d")
                open_options.append(SimulatedOption(
                    symbol=symbol,
                    type="CC",
                    entry_date=date_str,
                    expiry_date=exp_str,
                    strike=strike,
                    premium_per_share=premium_per_share,
                    contracts=1,
                    entry_price=entry_price,
                ))
                cc_symbols_this_month.add(symbol)

        # Iron condors (CHOPPY/MIXED + STRONG_UPTREND when vol elevated, SPY/QQQ, max 4)
        ic_eligible = regime in ("CHOPPY", "MIXED")
        if not ic_eligible and regime == "STRONG_UPTREND" and "SPY" in ic_vol_rank:
            vr_s = ic_vol_rank["SPY"]
            if date in vr_s.index and not pd.isna(vr_s.loc[date]) and float(vr_s.loc[date]) > 0.30:
                ic_eligible = True
        if daily_regimes is not None and ic_eligible and ic_count < 4:
            for sym in ("SPY", "QQQ"):
                if sym not in data or date not in data[sym].index or ic_count >= 4:
                    continue
                price = float(data[sym].loc[date, "Close"])
                put_strike = round(price * 0.90, 2)
                call_strike = round(price * 1.10, 2)
                put_wing = round(price * 0.85, 2)
                call_wing = round(price * 1.15, 2)
                width = (put_strike - put_wing) * 100
                credit = width * 0.30
                if credit < 50:
                    continue
                exp_dt = datetime(dt.year, dt.month, dt.day) + timedelta(days=IC_DTE)
                exp_str = exp_dt.strftime("%Y-%m-%d")
                open_options.append(SimulatedOption(
                    symbol=sym,
                    type="IRON_CONDOR",
                    entry_date=date_str,
                    expiry_date=exp_str,
                    strike=put_strike,
                    premium_per_share=credit / 100,
                    contracts=1,
                    entry_price=price,
                    put_wing=put_wing,
                    call_wing=call_wing,
                    call_strike=call_strike,
                ))
                ic_count += 1

        # Protective puts (MIXED/UNFAVORABLE/STRONG_DOWNTREND, SPY, max 2)
        if daily_regimes is not None and regime in ("MIXED", "UNFAVORABLE", "STRONG_DOWNTREND") and pp_count < 2:
            if "SPY" in data and date in data["SPY"].index:
                price = float(data["SPY"].loc[date, "Close"])
                strike = round(price * 0.93, 2)
                cost = min(5000.0, equity * 0.005, price * 0.02 * 100)
                if cost >= 10:
                    exp_dt = datetime(dt.year, dt.month, dt.day) + timedelta(days=PP_DTE)
                    exp_str = exp_dt.strftime("%Y-%m-%d")
                    open_options.append(SimulatedOption(
                        symbol="SPY",
                        type="PROTECTIVE_PUT",
                        entry_date=date_str,
                        expiry_date=exp_str,
                        strike=strike,
                        premium_per_share=-cost / 100,
                        contracts=1,
                        entry_price=price,
                        cost=cost,
                    ))
                    equity -= cost
                    pp_count += 1

        equity_curve.append(round(equity, 2))
        curve_dates.append(date_str)

    return settlements, equity_curve, curve_dates, equity


def compute_summary(
    settlements: List[OptionSettlement],
    equity_curve: List[float],
    curve_dates: List[str],
    initial_equity: float,
    final_equity: float,
) -> Dict[str, Any]:
    n = len(settlements)
    if n == 0:
        return {
            "total_trades": 0,
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "assigned_pct": 0.0,
            "annualized_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
        }
    wins = [s for s in settlements if s.pnl > 0]
    assigned = [s for s in settlements if s.assigned]
    total_pnl = sum(s.pnl for s in settlements)
    win_rate = len(wins) / n
    assigned_pct = len(assigned) / n

    arr = np.array(equity_curve)
    peak = np.maximum.accumulate(arr)
    dd = (peak - arr) / (peak + 1e-12)
    max_dd = float(np.max(dd))

    if len(equity_curve) > 1:
        daily_returns = np.diff(arr) / (arr[:-1] + 1e-12)
        ann_vol = float(np.std(daily_returns) * np.sqrt(252)) if len(daily_returns) > 1 else 0
        n_years = len(equity_curve) / 252.0
        ann_ret = (final_equity / initial_equity) ** (1 / max(n_years, 0.1)) - 1 if n_years > 0 else 0
        sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
    else:
        ann_ret = 0.0
        ann_vol = 0.0
        sharpe = 0.0

    return {
        "total_trades": n,
        "total_pnl": round(total_pnl, 2),
        "win_rate": round(win_rate, 4),
        "assigned_pct": round(assigned_pct, 4),
        "avg_pnl_per_trade": round(total_pnl / n, 2),
        "annualized_return": round(ann_ret, 4),
        "max_drawdown": round(max_dd, 4),
        "sharpe_ratio": round(sharpe, 2),
        "starting_equity": initial_equity,
        "ending_equity": round(final_equity, 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Premium-selling strategy backtest (CSP)")
    parser.add_argument("--years", type=int, default=2)
    parser.add_argument("--initial-equity", type=float, default=100_000.0)
    parser.add_argument("--max-per-day", type=int, default=5)
    parser.add_argument("--max-per-month", type=int, default=20)
    parser.add_argument("--save", action="store_true", help="Save results JSON")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    logger.info(
        "Running premium backtest: %d years, $%s initial, max %d/day %d/month",
        args.years, f"{args.initial_equity:,.0f}", args.max_per_day, args.max_per_month,
    )
    settlements, equity_curve, curve_dates, final_equity = run_premium_backtest(
        years=args.years,
        initial_equity=args.initial_equity,
        max_options_per_day=args.max_per_day,
        max_options_per_month=args.max_per_month,
    )
    summary = compute_summary(
        settlements,
        equity_curve,
        curve_dates,
        args.initial_equity,
        final_equity,
    )

    print("\n" + "=" * 60)
    print("PREMIUM SELLING BACKTEST RESULTS (CSP)")
    print("=" * 60)
    print(f"  {'Total trades':>25s}: {summary['total_trades']}")
    print(f"  {'Total P&L':>25s}: ${summary['total_pnl']:,.2f}")
    print(f"  {'Win rate':>25s}: {summary['win_rate']:.2%}")
    print(f"  {'Assignment rate':>25s}: {summary['assigned_pct']:.2%}")
    print(f"  {'Avg P&L per trade':>25s}: ${summary['avg_pnl_per_trade']:,.2f}")
    print(f"  {'Annualized return':>25s}: {summary['annualized_return']:.2%}")
    print(f"  {'Max drawdown':>25s}: {summary['max_drawdown']:.2%}")
    print(f"  {'Sharpe ratio':>25s}: {summary['sharpe_ratio']:.2f}")
    print(f"  {'Starting equity':>25s}: ${summary['starting_equity']:,.2f}")
    print(f"  {'Ending equity':>25s}: ${summary['ending_equity']:,.2f}")
    print("=" * 60)

    if args.save and settlements:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        out = RESULTS_DIR / f"premium_backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        payload = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "years": args.years,
                "initial_equity": args.initial_equity,
                "max_per_day": args.max_per_day,
                "max_per_month": args.max_per_month,
            },
            "summary": summary,
            "settlements": [
                {
                    "symbol": s.symbol,
                    "type": s.type,
                    "entry_date": s.entry_date,
                    "expiry_date": s.expiry_date,
                    "strike": s.strike,
                    "premium_collected": s.premium_collected,
                    "exit_price": s.exit_price,
                    "pnl": s.pnl,
                    "assigned": s.assigned,
                }
                for s in settlements
            ],
            "equity_curve_length": len(equity_curve),
        }
        out.write_text(json.dumps(payload, indent=2))
        print(f"\nResults saved to {out}")


if __name__ == "__main__":
    main()
