#!/usr/bin/env python3
"""
Options Strategy Backtester
===========================
Simulates covered call and cash-secured put strategies on historical data
to optimize strike selection, DTE, and profit-take thresholds.

Tests multiple parameter combinations and ranks them by risk-adjusted return.
Results feed into the BacktestComparison dashboard component.

Usage:
  python3 options_backtester.py                          # default backtest
  python3 options_backtester.py --symbols MPC COP OXY    # specific symbols
  python3 options_backtester.py --months 12               # longer lookback
  python3 options_backtester.py --output results.json     # custom output
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

SCRIPTS_DIR = Path(__file__).resolve().parent
TRADING_DIR = SCRIPTS_DIR.parent
LOGS_DIR = TRADING_DIR / "logs"
RESULTS_PATH = LOGS_DIR / "backtest_results.json"

LOGS_DIR.mkdir(exist_ok=True)
sys.path.insert(0, str(SCRIPTS_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [backtest] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGS_DIR / "options_backtester.log"),
    ],
)
log = logging.getLogger("backtest")


@dataclass
class BacktestParams:
    otm_pct: float = 5.0
    dte: int = 35
    profit_take_pct: float = 80.0
    stop_loss_mult: float = 2.0
    strategy: str = "covered_call"


@dataclass
class BacktestResult:
    params: Dict[str, Any] = field(default_factory=dict)
    total_premium: float = 0.0
    total_assignment_loss: float = 0.0
    net_pnl: float = 0.0
    num_cycles: int = 0
    num_assigned: int = 0
    num_profit_taken: int = 0
    num_expired_otm: int = 0
    avg_premium_pct: float = 0.0
    annualized_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate_pct: float = 0.0
    sharpe: float = 0.0


def _fetch_historical(symbol: str, months: int) -> Optional[Any]:
    """Fetch daily OHLC for a symbol."""
    try:
        import yfinance as yf
        period = f"{months}mo" if months <= 24 else f"{months // 12}y"
        data = yf.download(symbol, period=period, progress=False, auto_adjust=True)
        if data.empty:
            return None
        close = data["Close"]
        if hasattr(close, "columns"):
            close = close.iloc[:, 0]
        high = data["High"]
        if hasattr(high, "columns"):
            high = high.iloc[:, 0]
        return {"close": close, "high": high, "dates": data.index}
    except Exception as e:
        log.warning("Could not fetch %s: %s", symbol, e)
        return None


def _estimate_premium(spot: float, strike: float, dte: int, is_call: bool) -> float:
    """Simple premium estimate using Black-Scholes-like approximation.

    Uses a fixed 30% IV assumption — crude but consistent for relative
    comparison across parameter sets. Real premium would need option chain data.
    """
    iv = 0.30
    t = dte / 365.0
    if t <= 0:
        return 0.0

    otm_pct = abs(strike - spot) / spot
    time_value = spot * iv * np.sqrt(t) * 0.4
    otm_decay = np.exp(-3.0 * otm_pct)
    return max(0.01, time_value * otm_decay)


def simulate_covered_calls(
    symbol: str,
    closes: Any,
    highs: Any,
    dates: Any,
    params: BacktestParams,
) -> BacktestResult:
    """Simulate selling covered calls with given parameters on historical data."""
    result = BacktestResult(params=asdict(params))
    cycle_pnls: List[float] = []
    equity_curve: List[float] = []
    cumulative = 0.0

    i = 0
    n = len(closes)

    while i < n - params.dte:
        entry_price = float(closes.iloc[i])
        strike = entry_price * (1 + params.otm_pct / 100.0)
        premium = _estimate_premium(entry_price, strike, params.dte, is_call=True)

        expiry_idx = min(i + params.dte, n - 1)
        expiry_price = float(closes.iloc[expiry_idx])

        max_price_during = float(highs.iloc[i:expiry_idx + 1].max())

        profit_taken = False
        assigned = False

        for j in range(i + 1, expiry_idx + 1):
            current = float(closes.iloc[j])
            days_elapsed = j - i
            remaining_dte = params.dte - days_elapsed

            remaining_premium = premium * (remaining_dte / params.dte) * 0.6
            decay_pct = (premium - remaining_premium) / premium * 100 if premium > 0 else 0

            if decay_pct >= params.profit_take_pct:
                cycle_pnl = premium - remaining_premium
                result.num_profit_taken += 1
                profit_taken = True
                cycle_pnls.append(cycle_pnl)
                cumulative += cycle_pnl
                equity_curve.append(cumulative)
                i = j + 1
                break

        if not profit_taken:
            if expiry_price >= strike:
                assignment_pnl = (strike - entry_price) + premium
                cycle_pnls.append(assignment_pnl)
                cumulative += assignment_pnl
                result.num_assigned += 1
                if assignment_pnl < 0:
                    result.total_assignment_loss += abs(assignment_pnl)
            else:
                cycle_pnls.append(premium)
                cumulative += premium
                result.num_expired_otm += 1

            equity_curve.append(cumulative)
            i = expiry_idx + 1

        result.num_cycles += 1

    if not cycle_pnls:
        return result

    result.total_premium = sum(p for p in cycle_pnls if p > 0)
    result.net_pnl = sum(cycle_pnls)

    avg_entry = float(closes.mean())
    result.avg_premium_pct = (np.mean([abs(p) for p in cycle_pnls]) / avg_entry * 100) if avg_entry > 0 else 0

    trading_days = n
    years = trading_days / 252.0
    if years > 0 and avg_entry > 0:
        result.annualized_return_pct = (result.net_pnl / avg_entry) / years * 100

    if equity_curve:
        peak = equity_curve[0]
        max_dd = 0.0
        for val in equity_curve:
            if val > peak:
                peak = val
            dd = (peak - val) / max(abs(peak), 1.0) * 100
            if dd > max_dd:
                max_dd = dd
        result.max_drawdown_pct = max_dd

    wins = sum(1 for p in cycle_pnls if p > 0)
    result.win_rate_pct = (wins / len(cycle_pnls) * 100) if cycle_pnls else 0

    returns = np.array(cycle_pnls)
    if len(returns) > 2 and returns.std() > 0:
        result.sharpe = float(returns.mean() / returns.std() * np.sqrt(252 / max(params.dte, 1)))

    return result


def run_parameter_sweep(
    symbols: List[str],
    months: int = 6,
    strategies: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Test multiple parameter combinations across symbols."""
    if strategies is None:
        strategies = ["covered_call"]

    otm_options = [3.0, 5.0, 7.0, 10.0, 15.0]
    dte_options = [21, 30, 35, 45]
    pt_options = [50.0, 65.0, 80.0, 90.0]

    all_results: List[Dict[str, Any]] = []

    for symbol in symbols:
        log.info("Fetching data for %s (%d months)...", symbol, months)
        data = _fetch_historical(symbol, months)
        if data is None:
            log.warning("No data for %s — skipping", symbol)
            continue

        closes = data["close"]
        highs = data["high"]
        dates = data["dates"]
        log.info("  %s: %d data points", symbol, len(closes))

        for otm in otm_options:
            for dte in dte_options:
                for pt in pt_options:
                    params = BacktestParams(
                        otm_pct=otm,
                        dte=dte,
                        profit_take_pct=pt,
                        strategy="covered_call",
                    )
                    result = simulate_covered_calls(symbol, closes, highs, dates, params)
                    all_results.append({
                        "symbol": symbol,
                        **asdict(result),
                    })

    all_results.sort(key=lambda r: r.get("sharpe", 0), reverse=True)
    return all_results


def main() -> None:
    parser = argparse.ArgumentParser(description="Options Strategy Backtester")
    parser.add_argument("--symbols", nargs="+", default=None, help="Symbols to backtest")
    parser.add_argument("--months", type=int, default=6, help="Lookback months")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")
    args = parser.parse_args()

    symbols = args.symbols
    if not symbols:
        try:
            from sector_gates import SECTOR_MAP
            snapshot_path = LOGS_DIR / "dashboard_snapshot.json"
            if snapshot_path.exists():
                snap = json.loads(snapshot_path.read_text())
                positions = snap.get("positions", {}).get("list", [])
                stock_positions = [
                    p for p in positions
                    if p.get("sec_type") == "STK" and p.get("side") == "LONG"
                    and abs(p.get("quantity", 0)) >= 100
                ]
                stock_positions.sort(key=lambda p: abs(p.get("market_value", 0)), reverse=True)
                symbols = [p["symbol"] for p in stock_positions[:10]]
        except Exception:
            pass

    if not symbols:
        symbols = ["SPY", "QQQ", "MPC", "COP", "OXY"]

    log.info("Backtesting %d symbols over %d months", len(symbols), args.months)
    log.info("Symbols: %s", ", ".join(symbols))

    results = run_parameter_sweep(symbols, months=args.months)

    log.info(f"\n{'='*80}")
    log.info(f"BACKTEST RESULTS: {len(results)} parameter combinations tested")
    log.info(f"{'='*80}")

    top_by_symbol: Dict[str, Dict] = {}
    for r in results:
        sym = r["symbol"]
        if sym not in top_by_symbol or r.get("sharpe", 0) > top_by_symbol[sym].get("sharpe", 0):
            top_by_symbol[sym] = r

    log.info("\nBest parameters by symbol:")
    for sym, r in sorted(top_by_symbol.items()):
        p = r.get("params", {})
        log.info(f"  {sym:6s}  OTM={p.get('otm_pct', 0):.0f}%  DTE={p.get('dte', 0)}  "
                 f"PT={p.get('profit_take_pct', 0):.0f}%  "
                 f"Sharpe={r.get('sharpe', 0):.2f}  "
                 f"Ann.Return={r.get('annualized_return_pct', 0):.1f}%  "
                 f"WinRate={r.get('win_rate_pct', 0):.0f}%  "
                 f"MaxDD={r.get('max_drawdown_pct', 0):.1f}%")

    top10 = results[:10]
    log.info("\nTop 10 parameter sets (by Sharpe):")
    for i, r in enumerate(top10, 1):
        p = r.get("params", {})
        log.info(f"  #{i}: {r['symbol']} OTM={p.get('otm_pct',0):.0f}% DTE={p.get('dte',0)} "
                 f"PT={p.get('profit_take_pct',0):.0f}% → "
                 f"Sharpe={r.get('sharpe',0):.2f} Ann={r.get('annualized_return_pct',0):.1f}% "
                 f"Win={r.get('win_rate_pct',0):.0f}%")

    output_path = Path(args.output) if args.output else RESULTS_PATH
    summary = {
        "timestamp": datetime.now().isoformat(),
        "symbols_tested": list(top_by_symbol.keys()),
        "months": args.months,
        "total_combinations": len(results),
        "best_by_symbol": top_by_symbol,
        "top_10": top10,
        "current_params": {
            "otm_pct": 10.0,
            "dte": 35,
            "profit_take_pct": 80.0,
        },
    }
    output_path.write_text(json.dumps(summary, indent=2, default=str))
    log.info(f"\nResults written to {output_path}")


if __name__ == "__main__":
    main()
