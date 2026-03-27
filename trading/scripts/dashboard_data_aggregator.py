#!/usr/bin/env python3
"""
Dashboard Data Aggregator - Institutional Grade Metrics

Connects to IBKR and aggregates:
- Real-time account values, positions, P&L
- Risk metrics: VaR, CVaR, beta, sector exposure, margin utilization
- Performance attribution by strategy
- Trade analytics: slippage, MAE/MFE, quality scores
- Audit trail: gate rejections, system health

Writes to dashboard_snapshot.json for API consumption.
"""

import asyncio
import json
import logging
import math
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf
from ib_insync import IB, Stock

from paths import TRADING_DIR
from risk_config import get_net_liquidation_and_effective_equity
from sector_gates import SECTOR_MAP, portfolio_sector_exposure

_env_path = TRADING_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "4001"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DASHBOARD_SNAPSHOT = TRADING_DIR / "logs" / "dashboard_snapshot.json"
EQUITY_BACKTEST_BENCHMARK_FILE = TRADING_DIR / "logs" / "equity_backtest_benchmark.json"
JOURNAL_SNAPSHOT   = TRADING_DIR / "logs" / "trades_journal.json"
DAILY_LOSS_FILE = TRADING_DIR / "logs" / "daily_loss.json"
PEAK_EQUITY_FILE = TRADING_DIR / "logs" / "peak_equity.json"
SOD_EQUITY_FILE = TRADING_DIR / "logs" / "sod_equity.json"
EXECUTION_LOG = TRADING_DIR / "logs" / "executions.json"

# Official system live date — portfolio_return_pct/since always uses this as the
# baseline regardless of how far back sod_equity_history.jsonl goes.
PORTFOLIO_BASELINE_DATE = "2026-03-17"


def _detect_unmapped_symbols(ib: IB) -> List[str]:
    """Return stock symbols in the portfolio that have no SECTOR_MAP entry."""
    unmapped: List[str] = []
    try:
        for item in ib.portfolio():
            contract = item.contract
            if getattr(contract, "secType", "") != "STK":
                continue
            sym = getattr(contract, "symbol", "")
            if sym and sym not in SECTOR_MAP:
                unmapped.append(sym)
    except Exception:
        pass
    return unmapped


def load_json_safe(path: Path) -> Any:
    """Load JSON file safely, return None if missing or invalid."""
    try:
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load {path}: {e}")
    return None


def load_executions(path: Path) -> List[Dict[str, Any]]:
    """Load executions from a JSONL file (one JSON object per line).

    Handles three formats:
    - JSONL (multiple objects, one per line) — normal case after multiple runs
    - Single JSON dict on one line — first-run case
    - JSON list — legacy format
    """
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return []
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        records: List[Dict[str, Any]] = []
        for line in lines:
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    records.append(obj)
                elif isinstance(obj, list):
                    records.extend(o for o in obj if isinstance(o, dict))
            except json.JSONDecodeError:
                continue
        return records
    except Exception as e:
        logger.warning("Could not load executions from %s: %s", path, e)
        return []


def _parse_ts(raw: str) -> datetime:
    """Parse an ISO timestamp to a naive datetime, stripping any timezone info."""
    cleaned = raw.replace("Z", "").split("+")[0]
    return datetime.fromisoformat(cleaned)


def get_account_metrics(ib: IB) -> Dict[str, Any]:
    """Fetch real-time account values from IBKR."""
    metrics = {
        "net_liquidation": 0.0,
        "total_cash": 0.0,
        "buying_power": 0.0,
        "equity_with_loan": 0.0,
        "maintenance_margin": 0.0,
        "excess_liquidity": 0.0,
        "leverage_ratio": 0.0,
    }
    
    try:
        for av in ib.accountValues():
            if not hasattr(av, 'currency') or av.currency != "USD":
                continue
            tag = av.tag
            try:
                value = float(av.value)
            except (ValueError, TypeError):
                continue
            
            if tag == "NetLiquidation":
                metrics["net_liquidation"] = value
            elif tag == "TotalCashValue":
                metrics["total_cash"] = value
            elif tag == "BuyingPower":
                metrics["buying_power"] = value
            elif tag == "EquityWithLoanValue":
                metrics["equity_with_loan"] = value
            elif tag == "MaintMarginReq":
                metrics["maintenance_margin"] = value
            elif tag == "ExcessLiquidity":
                metrics["excess_liquidity"] = value
        
        # leverage_ratio is computed later from gross position notional (long + short)
        # once position data is available; leave as 0.0 placeholder here
    
    except Exception as e:
        logger.error(f"Error fetching account metrics: {e}")
    
    return metrics


def _load_stop_prices() -> Dict[str, Dict]:
    """Read pending_trades.json and return a {symbol: {price, side}} map.

    Handles both long stops (price_below → SELL to exit) and short stops
    (price_above → BUY to cover), so the dashboard shows stops for all positions.
    """
    stop_map: Dict[str, Dict] = {}
    pending_file = TRADING_DIR / "config" / "pending_trades.json"
    if not pending_file.exists():
        return stop_map
    try:
        data = json.loads(pending_file.read_text(encoding="utf-8"))
        for trade in data.get("pending", []):
            if trade.get("status") in ("executed", "cancelled", "expired"):
                continue
            trade_id = trade.get("id", "")
            for cond in trade.get("trigger", {}).get("conditions", []):
                cond_type = cond.get("type", "")
                sym = cond.get("symbol", "").upper()
                price = cond.get("price")
                if not sym or not isinstance(price, (int, float)):
                    continue
                if cond_type == "price_below":
                    # Long stop — exit if price drops below threshold
                    if sym not in stop_map or price > stop_map[sym]["price"]:
                        # Keep the highest (most recently ratcheted) stop
                        stop_map[sym] = {"price": float(price), "side": "LONG"}
                elif cond_type == "price_above" and "short-stop" in trade_id:
                    # Short stop — cover if price rises above threshold
                    if sym not in stop_map or price < stop_map[sym]["price"]:
                        # Keep the lowest (tightest) cover level
                        stop_map[sym] = {"price": float(price), "side": "SHORT"}
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("Could not load stop prices from pending_trades.json: %s", exc)
    return stop_map


def get_positions_data(ib: IB) -> Tuple[List[Dict], float, float]:
    """
    Get current positions with P&L and notional.
    Returns: (positions_list, long_notional, short_notional)
    """
    positions = []
    long_notional = 0.0
    short_notional = 0.0
    stop_prices = _load_stop_prices()
    
    try:
        portfolio_items = ib.portfolio()

        for item in portfolio_items:
            sec_type = getattr(item.contract, "secType", "")
            # Include STK and OPT positions; skip futures, forex, etc.
            if sec_type not in ("STK", "OPT"):
                continue

            contract = item.contract
            quantity = float(item.position or 0)
            avg_cost = float(item.averageCost or 0)

            raw_price = item.marketPrice
            market_price_raw = (
                float(raw_price)
                if raw_price is not None
                and not (isinstance(raw_price, float) and math.isnan(raw_price))
                else None
            )
            market_price = market_price_raw if market_price_raw is not None else avg_cost

            raw_mv = item.marketValue
            market_value = (
                float(raw_mv)
                if raw_mv is not None
                and not (isinstance(raw_mv, float) and math.isnan(raw_mv))
                else 0.0
            )

            unrealized_pnl = float(item.unrealizedPNL or 0)
            realized_pnl = float(item.realizedPNL or 0)

            if sec_type == "OPT":
                # Display as "AAPL 150C 240119" style label
                right = getattr(contract, "right", "")
                strike = getattr(contract, "strike", "")
                expiry = getattr(contract, "lastTradeDateOrContractMonth", "")[:6]
                symbol = f"{contract.symbol} {strike}{right} {expiry}"
                sector = "Options"
                # Options return % relative to premium paid (avg_cost per share × 100 multiplier)
                multiplier = float(getattr(contract, "multiplier", 100) or 100)
                cost_basis = avg_cost * multiplier
                return_pct = (unrealized_pnl / cost_basis * 100) if cost_basis != 0 else 0.0
            else:
                symbol = contract.symbol
                sector = SECTOR_MAP.get(symbol, "Unknown")
                if avg_cost > 0 and market_price_raw is not None:
                    raw_return = (market_price - avg_cost) / avg_cost * 100
                    return_pct = -raw_return if quantity < 0 else raw_return
                else:
                    return_pct = 0.0

            # Attach soft-stop price from pending_trades.json (STK only; options don't need it)
            raw_symbol = contract.symbol if sec_type == "STK" else None
            stop_entry = stop_prices.get(raw_symbol) if raw_symbol else None
            stop_price: Optional[float] = stop_entry["price"] if stop_entry else None
            stop_side: Optional[str]  = stop_entry["side"]  if stop_entry else None

            position_data = {
                "symbol": symbol,
                "sec_type": sec_type,
                "quantity": quantity,
                "side": "LONG" if quantity > 0 else "SHORT",
                "avg_cost": round(avg_cost, 4),
                "market_price": round(market_price, 4) if market_price_raw is not None else None,
                "market_value": round(market_value, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "realized_pnl": round(realized_pnl, 2),
                "notional": round(abs(market_value), 2),
                "sector": sector,
                "return_pct": round(return_pct, 4),
                "stop_price": stop_price,
                "stop_side": stop_side,   # "LONG" = exit below, "SHORT" = cover above
            }

            positions.append(position_data)

            if quantity > 0:
                long_notional += abs(market_value)
            else:
                short_notional += abs(market_value)

    except Exception as e:
        logger.error("Error fetching positions: %s", e)
    
    return positions, long_notional, short_notional


def calculate_var_cvar(returns: np.ndarray, confidence: float = 0.95) -> Tuple[float, float]:
    """
    Calculate Value at Risk and Conditional Value at Risk.
    
    returns: array of daily returns (as decimals, e.g., 0.02 for 2%)
    confidence: confidence level (0.95 = 95%)
    
    Returns: (VaR, CVaR) as positive numbers representing potential loss
    """
    if len(returns) < 10:
        return 0.0, 0.0
    
    sorted_returns = np.sort(returns)
    index = int((1 - confidence) * len(sorted_returns))
    var = -sorted_returns[index] if index < len(sorted_returns) else 0.0
    cvar = -sorted_returns[:index+1].mean() if index >= 0 else 0.0
    
    return max(0.0, var), max(0.0, cvar)


def _load_closed_trades_from_db(since_days: int = 30) -> List[Dict[str, Any]]:
    """Load closed trades with P&L from trades.db via trade_log_db."""
    try:
        from trade_log_db import get_closed_trades
        return get_closed_trades(since_days=since_days)
    except Exception as e:
        logger.debug("Could not read trades.db: %s", e)
        return []


def _get_recent_trades(limit: int = 10) -> List[Dict[str, Any]]:
    """Return the most recent closed trades for the dashboard Recent Trades panel."""
    try:
        from trade_log_db import get_closed_trades
        all_closed = get_closed_trades(since_days=None)
        result = []
        for t in all_closed[:limit]:
            raw_ts = t.get("exit_timestamp") or t.get("timestamp") or ""
            date_str = str(raw_ts)[:10] if raw_ts else ""
            strategy = (t.get("strategy") or "").upper()
            side_raw = (t.get("side") or "").upper()
            # Prefer strategy field: LONG/SHORT labels position intent.
            # Side (BUY/SELL) is the execution direction — a SELL on a LONG strategy
            # is a long exit, not a short entry.
            if strategy in ("LONG", "MOMENTUM_LONG"):
                trade_type = "Long"
            elif strategy in ("SHORT", "MOMENTUM_SHORT"):
                trade_type = "Short"
            else:
                trade_type = "Long" if side_raw in ("BUY", "LONG") else "Short"
            result.append({
                "date": date_str,
                "symbol": t.get("symbol", ""),
                "type": trade_type,
                "strategy": t.get("strategy") or t.get("source_script") or "",
                "entry": float(t.get("entry_price") or t.get("price") or 0),
                "exit": float(t.get("exit_price") or 0),
                "pnl": float(t.get("realized_pnl") or 0),
                "pnl_pct": float(t.get("realized_pnl_pct") or 0) * 100,
            })
        return result
    except Exception as e:
        logger.debug("Could not load recent trades for dashboard: %s", e)
        return []


def calculate_performance_metrics(net_liq: float) -> Dict[str, Any]:
    """Calculate performance metrics from logs."""
    metrics = {
        "daily_pnl": 0.0,
        "daily_return_pct": 0.0,
        "total_pnl_30d": 0.0,
        "total_return_30d_pct": None,
        "portfolio_return_pct": None,
        "portfolio_return_since": None,
        "sharpe_ratio": 0.0,
        "sortino_ratio": 0.0,
        "max_drawdown_pct": 0.0,
        "win_rate": 0.0,
        "profit_factor": 0.0,
        "avg_win": 0.0,
        "avg_loss": 0.0,
        "total_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "var_95": 0.0,
        "cvar_95": 0.0,
        "var_99": 0.0,
        "cvar_99": 0.0,
    }
    
    try:
        daily_loss_data = load_json_safe(DAILY_LOSS_FILE)
        if daily_loss_data:
            sod_equity = daily_loss_data.get("sod_equity", net_liq)
            current_equity = daily_loss_data.get("current_equity", net_liq)
            metrics["daily_pnl"] = current_equity - sod_equity
            if sod_equity > 0:
                metrics["daily_return_pct"] = (metrics["daily_pnl"] / sod_equity) * 100
        
        peak_data = load_json_safe(PEAK_EQUITY_FILE)
        if peak_data and net_liq > 0:
            peak = peak_data.get("peak_equity", net_liq)
            drawdown = (peak - net_liq) / peak * 100
            metrics["max_drawdown_pct"] = max(0.0, drawdown)
        
        # NOTE: total_trades is set after wins/losses are counted so all three
        # metrics come from the same source (trades.db) and stay consistent.

        # P&L comes from trades.db (exit-enriched records), not executions.json
        closed_trades_db = _load_closed_trades_from_db(since_days=30)
        closed_trades: List[float] = []
        for trade in closed_trades_db:
            pnl = trade.get("realized_pnl")
            if pnl is not None:
                pnl_f = float(pnl)
                closed_trades.append(pnl_f)
                if pnl_f > 0:
                    metrics["winning_trades"] += 1
                elif pnl_f < 0:
                    metrics["losing_trades"] += 1

        if closed_trades:
            metrics["total_pnl_30d"] = sum(closed_trades)

            # Compute accurate return from SOD equity history (NLV change, not closed-trade PnL).
            # Only set total_return_30d_pct when we have a baseline from ≥20 days ago.
            # Also set portfolio_return_pct/since from the oldest available history entry.
            try:
                import json as _json
                from datetime import timedelta as _td
                history_path = TRADING_DIR / "logs" / "sod_equity_history.jsonl"
                target_30d = (datetime.now() - _td(days=30)).date().isoformat()
                min_days_required = (datetime.now() - _td(days=20)).date().isoformat()
                _current_account = ""
                try:
                    _sod = _json.loads((TRADING_DIR / "logs" / "sod_equity.json").read_text())
                    _current_account = _sod.get("account", "")
                except Exception:
                    pass
                if history_path.exists():
                    entries: List[Dict[str, Any]] = []
                    for line in history_path.read_text().splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = _json.loads(line)
                            entry_account = obj.get("account", "")
                            if _current_account and entry_account and entry_account != _current_account:
                                continue
                            if obj.get("date") and obj.get("equity"):
                                entries.append(obj)
                        except (ValueError, _json.JSONDecodeError):
                            continue

                    if entries:
                        entries.sort(key=lambda x: x["date"])
                        oldest = entries[0]
                        oldest_equity = float(oldest["equity"])
                        oldest_date = oldest["date"]

                        # Proper 30d return: only when baseline is ≥20 days old
                        if oldest_date <= min_days_required and oldest_equity > 0:
                            metrics["total_return_30d_pct"] = ((net_liq - oldest_equity) / oldest_equity) * 100

                        # Portfolio return: always measured from PORTFOLIO_BASELINE_DATE
                        # (Mar 17 2026 — official live-system start), not the oldest
                        # history entry which may predate the real system launch.
                        baseline_entries = [
                            e for e in entries if e["date"] >= PORTFOLIO_BASELINE_DATE
                        ]
                        if baseline_entries:
                            baseline = baseline_entries[0]
                            baseline_equity = float(baseline["equity"])
                            baseline_date = baseline["date"]
                        else:
                            # Fallback: no entry on or after baseline date yet — use oldest
                            baseline_equity = oldest_equity
                            baseline_date = oldest_date

                        if baseline_equity > 0 and baseline_date < datetime.now().date().isoformat():
                            metrics["portfolio_return_pct"] = ((net_liq - baseline_equity) / baseline_equity) * 100
                            metrics["portfolio_return_since"] = baseline_date
            except Exception:
                pass

            wins = [p for p in closed_trades if p > 0]
            losses = [p for p in closed_trades if p < 0]

            if wins:
                metrics["avg_win"] = np.mean(wins)
            if losses:
                metrics["avg_loss"] = abs(np.mean(losses))

            total_wins = sum(wins) if wins else 0
            total_losses = abs(sum(losses)) if losses else 0

            if len(wins) + len(losses) > 0:
                metrics["win_rate"] = (len(wins) / (len(wins) + len(losses))) * 100
            # Keep total_trades consistent with wins+losses (same DB source)
            metrics["total_trades"] = len(wins) + len(losses)

            if total_losses > 0:
                metrics["profit_factor"] = total_wins / total_losses

            returns = np.array([p / net_liq for p in closed_trades if net_liq > 0])
            if len(returns) > 10:
                sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0.0
                metrics["sharpe_ratio"] = sharpe

                downside_returns = returns[returns < 0]
                if len(downside_returns) > 0:
                    downside_std = downside_returns.std()
                    if downside_std > 0:
                        metrics["sortino_ratio"] = returns.mean() / downside_std * np.sqrt(252)
                    
                    var_95, cvar_95 = calculate_var_cvar(returns, 0.95)
                    var_99, cvar_99 = calculate_var_cvar(returns, 0.99)
                    metrics["var_95"] = var_95 * 100
                    metrics["cvar_95"] = cvar_95 * 100
                    metrics["var_99"] = var_99 * 100
                    metrics["cvar_99"] = cvar_99 * 100
    
    except Exception as e:
        logger.error(f"Error calculating performance metrics: {e}")
    
    return metrics


_SOURCE_SCRIPT_TO_STRATEGY: Dict[str, str] = {
    "execute_longs.py": "momentum_long",
    "execute_shorts.py": "momentum_short",
    "execute_dual_mode.py": "momentum_long",
    "execute_mean_reversion.py": "mean_reversion",
    "execute_pairs.py": "pairs",
    "run_combined_strategy.py": "options",
    "execute_options.py": "options",
    "webhook_receiver.py": "webhook",
}


def calculate_options_coverage(positions: List[Dict]) -> Dict[str, Any]:
    """Compute what percentage of eligible long stock positions have an active covered call.

    Eligibility: long stock (qty > 0, secType == STK) with at least 100 shares.
    Covered: there is a short call option position (qty < 0, right == 'C') for the same symbol.

    Returns a dict ready to insert into the dashboard snapshot under "options_coverage".
    """
    # Collect long stock positions with ≥100 shares
    long_stocks: Dict[str, int] = {}   # symbol → share count
    for p in positions:
        if p.get("sec_type") == "STK" and p.get("quantity", 0) >= 100:
            long_stocks[p["symbol"]] = int(p["quantity"])

    # Collect symbols with active short calls (qty < 0 OPT with 'C' in symbol name)
    covered_symbols: set[str] = set()
    for p in positions:
        if p.get("sec_type") == "OPT" and p.get("quantity", 0) < 0:
            # symbol field is formatted as "AAPL 150.0C 2026..." — extract the base ticker
            raw_sym = p.get("symbol", "")
            base = raw_sym.split()[0] if raw_sym else ""
            if base and "C" in raw_sym:  # it's a call
                covered_symbols.add(base)

    eligible = list(long_stocks.keys())
    uncovered = sorted(s for s in eligible if s not in covered_symbols)
    n_eligible = len(eligible)
    n_covered  = n_eligible - len(uncovered)
    covered_pct = round(n_covered / n_eligible * 100, 1) if n_eligible > 0 else 0.0

    return {
        "eligible_count": n_eligible,
        "covered_count":  n_covered,
        "covered_pct":    covered_pct,
        "uncovered_symbols": uncovered,
    }


def calculate_strategy_attribution(net_liq: float) -> Dict[str, Any]:
    """Compute per-strategy P&L attribution from trades.db closed trades.

    Extends the existing calculate_strategy_breakdown() with:
    - avg_r_multiple: average R-multiple across closed trades
    - pnl_pct_of_nlv: realized PnL as % of current NLV
    - contribution_pct: each strategy's share of total closed-trade PnL

    Reads the last 30 days of closed trades from trades.db.
    """
    closed = _load_closed_trades_from_db(since_days=30)

    buckets: Dict[str, Dict] = {
        "momentum_long":  {"pnl": 0.0, "wins": 0, "losses": 0, "r_multiples": []},
        "momentum_short": {"pnl": 0.0, "wins": 0, "losses": 0, "r_multiples": []},
        "mean_reversion": {"pnl": 0.0, "wins": 0, "losses": 0, "r_multiples": []},
        "pairs":          {"pnl": 0.0, "wins": 0, "losses": 0, "r_multiples": []},
        "options":        {"pnl": 0.0, "wins": 0, "losses": 0, "r_multiples": []},
        "spotlight":      {"pnl": 0.0, "wins": 0, "losses": 0, "r_multiples": []},
        "other":          {"pnl": 0.0, "wins": 0, "losses": 0, "r_multiples": []},
    }

    total_pnl = 0.0
    for trade in closed:
        bucket = _resolve_strategy(trade)
        if bucket not in buckets:
            bucket = "other"
        pnl = float(trade.get("realized_pnl") or 0)
        r   = trade.get("r_multiple")

        buckets[bucket]["pnl"] += pnl
        total_pnl += pnl
        if pnl > 0:
            buckets[bucket]["wins"] += 1
        elif pnl < 0:
            buckets[bucket]["losses"] += 1
        if r is not None:
            try:
                buckets[bucket]["r_multiples"].append(float(r))
            except (TypeError, ValueError):
                pass

    result: Dict[str, Any] = {}
    for strat, data in buckets.items():
        n_trades = data["wins"] + data["losses"]
        avg_r    = round(sum(data["r_multiples"]) / len(data["r_multiples"]), 2) if data["r_multiples"] else None
        result[strat] = {
            "realized_pnl":   round(data["pnl"], 2),
            "pnl_pct_of_nlv": round(data["pnl"] / net_liq * 100, 2) if net_liq > 0 else 0.0,
            "contribution_pct": round(data["pnl"] / total_pnl * 100, 1) if total_pnl != 0 else 0.0,
            "win_rate":       round(data["wins"] / n_trades * 100, 1) if n_trades > 0 else 0.0,
            "avg_r_multiple": avg_r,
            "closed_trades":  n_trades,
        }

    result["_total_realized_pnl"] = round(total_pnl, 2)
    result["_period_days"]        = 30
    return result


def _resolve_strategy(trade: Dict[str, Any]) -> str:
    """Map a trade dict to a strategy bucket using source_script → strategy fallback chain.

    trades.db stores generic values like 'LONG'/'SHORT' in the strategy column.
    Those are not bucket names — always prefer source_script for proper bucketing.
    """
    strategy = str(trade.get("strategy") or "").upper()
    source   = str(trade.get("source_script") or "")
    # Generic direction flags are not bucket names — route by source_script
    if strategy in ("", "LONG", "SHORT", "BUY", "SELL"):
        mapped = _SOURCE_SCRIPT_TO_STRATEGY.get(source, "unknown")
        # dual_mode SHORT positions belong to momentum_short, not momentum_long
        if source == "execute_dual_mode.py" and strategy == "SHORT":
            return "momentum_short"
        return mapped
    return _SOURCE_SCRIPT_TO_STRATEGY.get(strategy.lower(), "unknown")


def calculate_strategy_breakdown(executions: List[Dict]) -> Dict[str, Any]:
    """Break down trade counts and P&L by strategy.

    Trade counts come from executions.json (entry events).
    P&L (wins/losses) comes from trades.db exit records.
    """
    strategies: Dict[str, Dict[str, Any]] = {
        "momentum_long": {"trades": 0, "pnl": 0.0, "wins": 0, "losses": 0},
        "momentum_short": {"trades": 0, "pnl": 0.0, "wins": 0, "losses": 0},
        "mean_reversion": {"trades": 0, "pnl": 0.0, "wins": 0, "losses": 0},
        "pairs": {"trades": 0, "pnl": 0.0, "wins": 0, "losses": 0},
        "options": {"trades": 0, "pnl": 0.0, "wins": 0, "losses": 0},
        "webhook": {"trades": 0, "pnl": 0.0, "wins": 0, "losses": 0},
    }

    try:
        thirty_days_ago = datetime.now() - timedelta(days=30)

        # Trade counts from executions.json (entry events, open + closed)
        for trade in executions:
            if "timestamp" not in trade:
                continue
            try:
                ts = datetime.fromisoformat(
                    trade["timestamp"].replace("Z", "").split("+")[0]
                )
            except (ValueError, AttributeError):
                continue
            if ts < thirty_days_ago:
                continue
            strategy = _resolve_strategy(trade)
            if strategy in strategies:
                strategies[strategy]["trades"] += 1

        # P&L from trades.db (exit-enriched records)
        closed_trades_db = _load_closed_trades_from_db(since_days=30)
        for trade in closed_trades_db:
            strategy = _resolve_strategy(trade)
            if strategy not in strategies:
                continue
            pnl = trade.get("realized_pnl")
            if pnl is not None:
                pnl_f = float(pnl)
                strategies[strategy]["pnl"] += pnl_f
                if pnl_f > 0:
                    strategies[strategy]["wins"] += 1
                else:
                    strategies[strategy]["losses"] += 1

    except Exception as e:
        logger.error("Error calculating strategy breakdown: %s", e)

    for strat in strategies.values():
        total = strat["wins"] + strat["losses"]
        strat["win_rate"] = (strat["wins"] / total * 100) if total > 0 else 0.0

    return strategies


def calculate_beta_correlation(positions: List[Dict]) -> Dict[str, float]:
    """Calculate portfolio beta and correlation to SPY."""
    try:
        if not positions:
            return {"beta": 0.0, "correlation": 0.0}

        # Options have complex symbols that yfinance cannot resolve — use only stocks
        # Include both long and short positions for accurate portfolio beta
        stock_positions = [
            p for p in positions
            if p.get("sec_type") == "STK" and p.get("quantity", 0) != 0
        ]
        if not stock_positions:
            return {"beta": 0.0, "correlation": 0.0}

        spy_data = yf.download("SPY", period="3mo", interval="1d", progress=False)
        if spy_data.empty:
            return {"beta": 0.0, "correlation": 0.0}
        
        spy_returns = spy_data["Close"].pct_change().dropna()
        
        portfolio_returns = []
        weights = []
        
        for pos in stock_positions[:15]:
            symbol = pos["symbol"]
            weight = abs(pos["market_value"])
            weights.append(weight)
            
            try:
                stock_data = yf.download(symbol, period="3mo", interval="1d", progress=False)
                if not stock_data.empty:
                    stock_returns = stock_data["Close"].pct_change().dropna()
                    aligned = pd.concat([spy_returns, stock_returns], axis=1, join="inner")
                    if len(aligned) > 20:
                        portfolio_returns.append(aligned.iloc[:, 1].values)
            except Exception as exc:
                logger.debug("Beta/corr skip %s: %s", symbol, exc)
                continue
        
        if not portfolio_returns or not weights:
            return {"beta": 0.0, "correlation": 0.0}
        
        total_weight = sum(weights)
        min_length = min(len(spy_returns), min(len(np.atleast_1d(ret).ravel()) for ret in portfolio_returns))
        if min_length < 10:
            return {"beta": 0.0, "correlation": 0.0}
        
        spy_vals = np.asarray(spy_returns.iloc[:min_length].values, dtype=float).ravel()
        weighted_returns = np.zeros(min_length, dtype=float)
        for ret, weight in zip(portfolio_returns, weights):
            r = np.atleast_1d(ret).ravel()[:min_length]
            if len(r) < min_length:
                continue
            weighted_returns += r * (weight / total_weight)
        
        if spy_vals.shape != weighted_returns.shape:
            return {"beta": 0.0, "correlation": 0.0}
        
        cov_matrix = np.cov(spy_vals, weighted_returns)
        beta = cov_matrix[0, 1] / cov_matrix[0, 0] if cov_matrix[0, 0] > 0 else 0.0
        correlation = float(np.corrcoef(spy_vals, weighted_returns)[0, 1]) if min_length > 1 else 0.0
        return {"beta": float(beta), "correlation": correlation}
    
    except Exception as e:
        logger.error(f"Error calculating beta: {e}")
        return {"beta": 0.0, "correlation": 0.0}


def calculate_correlation_matrix(positions: List[Dict], lookback_days: int = 60) -> Dict[str, Any]:
    """Compute pairwise return correlations for top portfolio holdings.

    Returns a structure the frontend can render as a heat map:
      { "symbols": ["SYM1", ...], "matrix": [[1.0, 0.8, ...], ...] }
    """
    stock_positions = [
        p for p in positions
        if p.get("sec_type") == "STK" and p.get("side") == "LONG"
    ]
    stock_positions.sort(key=lambda p: abs(p.get("market_value", 0)), reverse=True)
    symbols = [p["symbol"] for p in stock_positions[:15]]

    if len(symbols) < 2:
        return {"symbols": symbols, "matrix": [[1.0]] if symbols else []}

    try:
        data = yf.download(symbols, period=f"{lookback_days}d", progress=False, auto_adjust=True)
        if data.empty:
            return {"symbols": symbols, "matrix": []}

        close = data["Close"]
        if hasattr(close, "columns"):
            close = close[symbols]
        else:
            close = close.to_frame(name=symbols[0])

        returns = close.pct_change().dropna()
        if len(returns) < 10:
            return {"symbols": symbols, "matrix": []}

        corr = returns.corr()
        valid_symbols = [s for s in symbols if s in corr.columns]
        corr = corr.loc[valid_symbols, valid_symbols]

        matrix = []
        for sym in valid_symbols:
            row = []
            for sym2 in valid_symbols:
                val = corr.loc[sym, sym2]
                row.append(round(float(val), 3) if not (isinstance(val, float) and np.isnan(val)) else 0.0)
            matrix.append(row)

        return {"symbols": valid_symbols, "matrix": matrix}

    except Exception as e:
        logger.warning("Correlation matrix calculation failed: %s", e)
        return {"symbols": symbols, "matrix": []}


def calculate_trade_analytics(executions: List[Dict]) -> Dict[str, Any]:
    """Calculate advanced trade analytics: MAE, MFE, slippage."""
    analytics = {
        "avg_mae": 0.0,
        "avg_mfe": 0.0,
        "avg_slippage_bps": 0.0,
        "avg_hold_time_hours": 0.0,
        "best_trade": 0.0,
        "worst_trade": 0.0,
        "largest_position": 0.0,
    }
    
    try:
        # Use trades.db for P&L-based analytics (MAE, MFE, best/worst trade)
        closed_db = _load_closed_trades_from_db(since_days=30)

        pnls = [float(t["realized_pnl"]) for t in closed_db if t.get("realized_pnl") is not None]
        if pnls:
            analytics["best_trade"] = max(pnls)
            analytics["worst_trade"] = min(pnls)

        mae_values = [float(t["max_adverse_excursion"]) for t in closed_db if t.get("max_adverse_excursion") is not None]
        if mae_values:
            analytics["avg_mae"] = float(np.mean(mae_values))

        mfe_values = [float(t["max_favorable_excursion"]) for t in closed_db if t.get("max_favorable_excursion") is not None]
        if mfe_values:
            analytics["avg_mfe"] = float(np.mean(mfe_values))

        hold_times = []
        for t in closed_db:
            if t.get("holding_days") is not None:
                hold_times.append(float(t["holding_days"]) * 24.0)
        if hold_times:
            analytics["avg_hold_time_hours"] = float(np.mean(hold_times))

        # Slippage and largest position from executions.json (entry-time data)
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent = [
            t for t in executions
            if "timestamp" in t
            and _parse_ts(t["timestamp"]) > thirty_days_ago
        ]

        notionals = [float(t.get("notional") or 0) for t in recent if t.get("notional")]
        if notionals:
            analytics["largest_position"] = max(notionals)

        slippages = [float(t.get("slippage_bps") or 0) for t in recent if t.get("slippage_bps")]
        if slippages:
            analytics["avg_slippage_bps"] = float(np.mean(slippages))

    except Exception as e:
        logger.error("Error calculating trade analytics: %s", e)
    
    return analytics


def get_system_health() -> Dict[str, Any]:
    """Check system health and data freshness."""
    health = {
        "status": "healthy",
        "issues": [],
        "last_screener_run": None,
        "last_execution": None,
        "data_freshness_minutes": 0,
    }
    
    try:
        # data_freshness_minutes = age of the most-recently-written snapshot file.
        # This is what the dashboard displays as "Data: Xm old".
        # Separately track screener staleness for system health alerts.
        snapshot_file = TRADING_DIR / "logs" / "dashboard_snapshot.json"
        if snapshot_file.exists():
            import os as _os
            mtime = _os.path.getmtime(snapshot_file)
            snapshot_age_min = (datetime.now().timestamp() - mtime) / 60
            health["data_freshness_minutes"] = int(snapshot_age_min)

        watchlist = TRADING_DIR / "watchlist_longs.json"
        if watchlist.exists():
            data = load_json_safe(watchlist)
            if data and "generated_at" in data:
                gen_time = _parse_ts(data["generated_at"])
                health["last_screener_run"] = data["generated_at"]
                screener_age_min = (datetime.now() - gen_time).total_seconds() / 60

                # Only alert on stale screener data during market hours (7:00–14:00 MT).
                # datetime.now() returns LOCAL machine time, which may not be MT.
                # Use zoneinfo (stdlib 3.9+) to get the true Mountain Time wall clock.
                try:
                    from zoneinfo import ZoneInfo as _ZI
                    now_mt = datetime.now(_ZI("America/Denver"))
                except Exception:
                    from datetime import timezone as _tz, timedelta as _td
                    now_mt = datetime.now(_tz(  # type: ignore[call-arg]
                        _td(hours=-6)  # MDT fallback; close enough for an alerting window
                    ))
                market_hour = now_mt.hour + now_mt.minute / 60.0
                in_market_hours = (now_mt.weekday() < 5) and (7.0 <= market_hour < 14.0)
                if screener_age_min > 90 and in_market_hours:
                    health["issues"].append(f"Screener data is {int(screener_age_min)} minutes old")
                    health["status"] = "warning"
        
        if EXECUTION_LOG.exists():
            execs = load_executions(EXECUTION_LOG)
            if execs:
                last_exec = execs[-1]
                if "timestamp" in last_exec:
                    health["last_execution"] = last_exec["timestamp"]
        
        # Check pairs screener staleness separately.
        # Allow up to 1 missed trading day (Friday → Monday = ~72 h over the weekend).
        # Count only trading hours elapsed since the file was written so weekend gaps
        # don't produce false positives.
        pairs_file = TRADING_DIR / "watchlist_pairs.json"
        if pairs_file.exists():
            import time as _time
            pairs_mtime = pairs_file.stat().st_mtime
            pairs_age_hours = (_time.time() - pairs_mtime) / 3600
            # Calculate trading hours elapsed (Mon-Fri 09:30–16:00 ET only).
            # A simple proxy: subtract 16 hours per weekend day between mtime and now.
            from datetime import datetime as _dt, timezone as _tz, timedelta as _td
            _mtime_dt  = _dt.fromtimestamp(pairs_mtime)
            _now_dt    = _dt.now()
            _weekend_hours = 0.0
            _cursor = _mtime_dt
            while _cursor < _now_dt:
                if _cursor.weekday() >= 5:  # Saturday=5, Sunday=6
                    _weekend_hours += min(24.0, (_now_dt - _cursor).total_seconds() / 3600)
                _cursor += _td(days=1)
            trading_age_hours = max(0.0, pairs_age_hours - _weekend_hours)
            # Flag only if more than ~1.5 trading days have elapsed without a refresh.
            if trading_age_hours > 36:
                health["issues"].append(
                    f"Pairs watchlist is {pairs_age_hours:.0f}h old — pairs screener may not be running"
                )
                if health["status"] == "healthy":
                    health["status"] = "warning"

        if not health["issues"]:
            health["status"] = "healthy"

    except Exception as e:
        logger.error(f"Error checking system health: {e}")
        health["status"] = "error"
        health["issues"].append(str(e))

    return health


def _compute_hedge_metrics(
    positions: List[Dict[str, Any]], long_notional: float,
) -> Dict[str, Any]:
    """Compute hedge cost-of-carry and effectiveness metrics.

    Hedge instruments (TZA, VXX, VIXY, SQQQ, SPXS, UVXY, SDOW, DRIP)
    are leveraged/inverse ETFs that decay over time. Track their unrealized
    P&L as "cost of protection" and their weight relative to the long book.
    """
    HEDGE_SYMBOLS = {"TZA", "VXX", "VIXY", "SQQQ", "SPXS", "UVXY", "SDOW", "DRIP"}

    hedge_positions: List[Dict[str, Any]] = []
    total_hedge_value = 0.0
    total_hedge_cost = 0.0
    total_hedge_pnl = 0.0

    for p in positions:
        sym = p.get("symbol", "")
        if p.get("sec_type") != "STK" or sym not in HEDGE_SYMBOLS:
            continue
        qty = abs(p.get("quantity", 0))
        avg = p.get("avg_cost", 0)
        mkt = p.get("market_price") or avg
        mv  = abs(p.get("market_value", 0))
        pnl = p.get("unrealized_pnl", 0)

        cost_basis = qty * avg
        decay_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0.0

        hedge_positions.append({
            "symbol": sym,
            "qty": int(qty),
            "cost_basis": round(cost_basis, 2),
            "market_value": round(mv, 2),
            "unrealized_pnl": round(pnl, 2),
            "decay_pct": round(decay_pct, 2),
        })
        total_hedge_value += mv
        total_hedge_cost += cost_basis
        total_hedge_pnl += pnl

    hedge_weight = (total_hedge_value / long_notional * 100) if long_notional > 0 else 0.0
    total_decay = (total_hedge_pnl / total_hedge_cost * 100) if total_hedge_cost > 0 else 0.0

    return {
        "positions": hedge_positions,
        "total_value": round(total_hedge_value, 2),
        "total_cost_basis": round(total_hedge_cost, 2),
        "total_unrealized_pnl": round(total_hedge_pnl, 2),
        "total_decay_pct": round(total_decay, 2),
        "hedge_weight_pct": round(hedge_weight, 2),
    }


def _pm_risk_metrics(account: Dict[str, Any], gross_notional: float) -> Dict[str, Any]:
    """Compute Portfolio Margin-specific risk fields for the dashboard snapshot."""
    nlv = account.get("net_liquidation", 0.0)
    el = account.get("excess_liquidity", 0.0)
    maint = account.get("maintenance_margin", 0.0)

    try:
        from risk_config import get_margin_type, get_max_leverage_hard_cap
        margin_type = get_margin_type(TRADING_DIR)
        lev_cap = get_max_leverage_hard_cap(TRADING_DIR)
    except ImportError:
        margin_type = "reg_t"
        lev_cap = 2.0

    el_pct = (el / nlv * 100) if nlv > 0 else 0.0
    leverage = (gross_notional / nlv) if nlv > 0 else 0.0

    if el_pct >= 20:
        cushion_status = "healthy"
    elif el_pct >= 10:
        cushion_status = "caution"
    else:
        cushion_status = "critical"

    return {
        "margin_type": margin_type,
        "excess_liquidity_pct": round(el_pct, 2),
        "pm_margin_cushion_status": cushion_status,
        "leverage_hard_cap": lev_cap,
        "leverage_vs_cap_pct": round(leverage / lev_cap * 100, 1) if lev_cap > 0 else 0.0,
    }


async def aggregate_dashboard_data() -> Dict[str, Any]:
    """Main aggregation function - collect all metrics."""
    logger.info("Starting dashboard data aggregation...")
    
    ib = IB()
    try:
        await ib.connectAsync(IB_HOST, IB_PORT, clientId=199)
        logger.info("Connected to IBKR")
    except Exception as e:
        logger.error(f"Could not connect to IBKR: {e}")
        return {
            "error": "IBKR connection failed",
            "timestamp": datetime.now().isoformat(),
        }
    
    try:
        account_metrics = get_account_metrics(ib)
        net_liq = account_metrics["net_liquidation"]

        positions, long_notional, short_notional = get_positions_data(ib)

        # True leverage = gross position notional / NLV (not equity_with_loan / NLV)
        if net_liq > 0:
            account_metrics["leverage_ratio"] = (long_notional + short_notional) / net_liq

        sector_exposure, total_notional = portfolio_sector_exposure(ib)

        unmapped_symbols = _detect_unmapped_symbols(ib)
        if unmapped_symbols:
            logger.warning(
                "[SECTOR] %d unmapped symbols detected: %s — add to SECTOR_MAP in sector_gates.py",
                len(unmapped_symbols), ", ".join(sorted(unmapped_symbols)),
            )

        performance = calculate_performance_metrics(net_liq)
        
        executions = load_executions(EXECUTION_LOG)
        strategy_breakdown = calculate_strategy_breakdown(executions)

        trade_analytics = calculate_trade_analytics(executions)
        
        beta_corr = calculate_beta_correlation(positions)

        correlation_matrix = calculate_correlation_matrix(positions)
        
        system_health = get_system_health()

        # Layer 1 — execution regime (SPY/VIX) from regime_context.json
        _regime_raw = load_json_safe(TRADING_DIR / "logs" / "regime_context.json") or {}
        # Guard: if regime_context.json contains a macro-band label (NEUTRAL, RISK_ON,
        # TIGHTENING, DEFENSIVE), reset it to UNKNOWN so the dashboard shows stale state
        # rather than a misleading Layer-1 label. This can happen when the scheduler
        # runs an old in-memory version and writes the Layer-2 result into the wrong file.
        _L1_EXECUTION_LABELS = {"STRONG_UPTREND", "STRONG_DOWNTREND", "CHOPPY", "MIXED", "UNFAVORABLE"}
        if _regime_raw.get("regime", "").upper() not in _L1_EXECUTION_LABELS:
            logger.warning(
                "regime_context.json contains invalid L1 label %r — likely a Layer-2 leak. "
                "Falling back to UNKNOWN. Run detect_market_regime() to refresh.",
                _regime_raw.get("regime"),
            )
            _regime_raw = {}
        # Layer 2 — macro regime band (FRED indicators) from regime_state.json
        _macro_raw = load_json_safe(TRADING_DIR / "logs" / "regime_state.json") or {}
        _macro_params = _macro_raw.get("parameters") or {}
        _commodity_triggers = _macro_raw.get("commodity_triggers") or {}

        _macro_events_raw = load_json_safe(TRADING_DIR / "config" / "macro_events.json")
        _active_macro_events: List[Dict[str, Any]] = []
        if isinstance(_macro_events_raw, list):
            _today_str = datetime.now().strftime("%Y-%m-%d")
            for _mev in _macro_events_raw:
                if not isinstance(_mev, dict) or not _mev.get("active", False):
                    continue
                _start = _mev.get("start_date", "")
                _end = _mev.get("end_date")
                if _start and _today_str < _start:
                    continue
                if _end and _today_str > _end:
                    continue
                _active_macro_events.append(_mev)

        market_regime = {
            # Layer 1: execution gating
            "regime": str(_regime_raw.get("regime", "UNKNOWN")),
            "note": str(_regime_raw.get("note", "")),
            "catalysts": list(_regime_raw.get("catalysts", [])),
            "updated_at": str(_regime_raw.get("updated_at", "")),
            # Layer 2: macro stress band
            "macro_regime": str(_macro_raw.get("regime", "UNKNOWN")),
            "macro_score": int(_macro_raw.get("currentScore", 0)),
            "macro_updated_at": str(_macro_raw.get("lastUpdate", "")),
            "macro_alerts": list(_macro_raw.get("activeAlerts", [])),
            "macro_parameters": {
                "size_multiplier": float(_macro_params.get("sizeMultiplier", 1.0)),
                "z_enter": float(_macro_params.get("zEnter", 2.0)),
                "atr_multiplier": float(_macro_params.get("atrMultiplier", 1.0)),
                "cooldown_days": int(_macro_params.get("cooldown", 3)),
            },
            "commodity_triggers": _commodity_triggers,
            "macro_events": _active_macro_events,
            "news_sentiment": load_json_safe(TRADING_DIR / "logs" / "news_sentiment.json") or {},
        }

        watchlist_longs = load_json_safe(TRADING_DIR / "watchlist_longs.json")
        long_candidates = []
        if watchlist_longs and "long_candidates" in watchlist_longs:
            long_candidates = watchlist_longs["long_candidates"][:20]
        
        watchlist_multi = load_json_safe(TRADING_DIR / "watchlist_multimode.json")
        short_candidates = []
        if watchlist_multi and "modes" in watchlist_multi:
            modes = watchlist_multi["modes"]
            if "short_opportunities" in modes and "short" in modes["short_opportunities"]:
                short_candidates = modes["short_opportunities"]["short"][:20]
        
        # Options coverage: % of eligible long stock positions with an active covered call
        options_coverage = calculate_options_coverage(positions)
        if options_coverage["uncovered_symbols"]:
            logger.info(
                "Options coverage: %d/%d eligible longs covered (%.0f%%) — uncovered: %s",
                options_coverage["covered_count"], options_coverage["eligible_count"],
                options_coverage["covered_pct"],
                ", ".join(options_coverage["uncovered_symbols"]),
            )

        # Strategy P&L attribution (30-day closed trades from trades.db)
        strategy_attribution = calculate_strategy_attribution(net_liq)

        # Hedge effectiveness — track cost-of-carry and protection value
        hedge_metrics = _compute_hedge_metrics(positions, long_notional)

        _trading_mode = os.getenv("TRADING_MODE", "paper")
        _alloc_pct = float(os.getenv("LIVE_ALLOCATION_PCT", "1.0"))

        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "trading_mode": _trading_mode,
            "live_allocation_pct": _alloc_pct,
            "account": account_metrics,
            "performance": performance,
            "positions": {
                "list": positions,
                "count": len(positions),
                "long_notional": long_notional,
                "short_notional": short_notional,
                "total_value": long_notional - short_notional,
                "total_notional": total_notional,
                "net_exposure": long_notional - short_notional,
                "gross_exposure": long_notional + short_notional,
            },
            "risk": {
                "sector_exposure": sector_exposure,
                "beta": beta_corr["beta"],
                "correlation_spy": beta_corr["correlation"],
                "margin_utilization_pct": (account_metrics["maintenance_margin"] / account_metrics["net_liquidation"] * 100) if account_metrics["net_liquidation"] > 0 else 0.0,
                "buying_power_used_pct": ((account_metrics["buying_power"] - account_metrics["excess_liquidity"]) / account_metrics["buying_power"] * 100) if account_metrics["buying_power"] > 0 else 0.0,
                **_pm_risk_metrics(account_metrics, long_notional + short_notional),
            },
            "strategy_breakdown": strategy_breakdown,
            "strategy_attribution": strategy_attribution,
            "options_coverage": options_coverage,
            "trade_analytics": trade_analytics,
            "candidates": {
                "longs": long_candidates,
                "shorts": short_candidates,
            },
            "correlation_matrix": correlation_matrix,
            "market_regime": market_regime,
            "system_health": system_health,
            "hedge_metrics": hedge_metrics,
            "summary": {
                "net_liquidation": account_metrics["net_liquidation"],
                "total_cash_value": account_metrics["total_cash"],
                "long_notional": long_notional,
                "short_notional": short_notional,
            },
            "unmapped_symbols": sorted(unmapped_symbols) if unmapped_symbols else [],
            "recent_trades": _get_recent_trades(limit=10),
            # Populated by (full path; quotes required — spaces in Google Drive path):
            # cd "/Users/ryanwinzenburg/Library/CloudStorage/GoogleDrive-ryanwinzenburg@gmail.com/My Drive/Projects/MIssion Control/trading" && python3 -m backtest.comprehensive_backtest --years 2 --enhanced-only --save
            "equity_backtest_benchmark": load_json_safe(EQUITY_BACKTEST_BENCHMARK_FILE),
        }
        
        snapshot["_source_mode"] = _trading_mode
        _snapshot_json = json.dumps(snapshot, indent=2, allow_nan=False)

        # Write mode-specific file first (canonical source for each mode)
        mode_snapshot = DASHBOARD_SNAPSHOT.parent / f"dashboard_snapshot_{_trading_mode}.json"
        tmp_fd2, tmp_path2 = tempfile.mkstemp(
            suffix=".json", dir=str(DASHBOARD_SNAPSHOT.parent)
        )
        try:
            with os.fdopen(tmp_fd2, "w") as f:
                f.write(_snapshot_json)
            os.replace(tmp_path2, str(mode_snapshot))
        except (ValueError, OSError):
            if os.path.exists(tmp_path2):
                os.unlink(tmp_path2)

        # Also write the unqualified file as a fallback (tagged with _source_mode
        # so consumers can detect mode mismatches)
        tmp_fd, tmp_path = tempfile.mkstemp(
            suffix=".json", dir=str(DASHBOARD_SNAPSHOT.parent)
        )
        try:
            with os.fdopen(tmp_fd, "w") as f:
                f.write(_snapshot_json)
            os.replace(tmp_path, str(DASHBOARD_SNAPSHOT))
        except (ValueError, OSError):
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

        logger.info("Dashboard snapshot written to %s + %s", mode_snapshot.name, DASHBOARD_SNAPSHOT.name)
        _write_journal_snapshot()
        return snapshot
    
    finally:
        ib.disconnect()


def _write_journal_snapshot() -> None:
    """Write trades_journal.json with all closed + open trades from trades.db.

    Called at the end of every dashboard refresh so the journal page always
    reflects the latest state without needing a direct DB connection from Next.js.
    """
    try:
        from trade_log_db import get_closed_trades, get_open_trades

        closed = get_closed_trades(since_days=None)
        open_trades = get_open_trades()

        def _row_to_journal(t: dict, status: str) -> dict:
            strategy = (t.get("strategy") or "").upper()
            side_raw = (t.get("side") or "").upper()
            if strategy in ("LONG", "MOMENTUM_LONG"):
                trade_type = "LONG"
            elif strategy in ("SHORT", "MOMENTUM_SHORT"):
                trade_type = "SHORT"
            else:
                trade_type = "LONG" if side_raw in ("BUY", "LONG") else "SHORT"

            entry_price = float(t.get("entry_price") or t.get("price") or 0)
            exit_price = t.get("exit_price")
            realized_pnl = t.get("realized_pnl")
            realized_pnl_pct = t.get("realized_pnl_pct")

            pnl = float(realized_pnl) if realized_pnl is not None else None
            pnl_pct = float(realized_pnl_pct) * 100 if realized_pnl_pct is not None else None

            return {
                "id": t.get("id"),
                "symbol": t.get("symbol", ""),
                "side": trade_type,
                "status": status,
                "strategy": t.get("strategy") or t.get("source_script") or "",
                "entry_timestamp": t.get("timestamp") or "",
                "exit_timestamp": t.get("exit_timestamp") or None,
                "entry_price": entry_price,
                "exit_price": float(exit_price) if exit_price is not None else None,
                "qty": int(t.get("qty") or 0),
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "r_multiple": float(t.get("r_multiple")) if t.get("r_multiple") is not None else None,
                "holding_days": int(t.get("holding_days") or 0) or None,
                "exit_reason": t.get("exit_reason") or None,
                "reason": t.get("reason") or None,
                "regime": t.get("regime_at_entry") or None,
                "conviction": float(t.get("conviction_score")) if t.get("conviction_score") is not None else None,
            }

        journal = {
            "generated_at": datetime.now().isoformat(),
            "closed": [_row_to_journal(t, "CLOSED") for t in closed],
            "open": [_row_to_journal(t, "OPEN") for t in open_trades],
            "total_closed": len(closed),
            "total_open": len(open_trades),
        }

        journal_json = json.dumps(journal, indent=2, allow_nan=False)
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".json", dir=str(JOURNAL_SNAPSHOT.parent))
        try:
            with os.fdopen(tmp_fd, "w") as f:
                f.write(journal_json)
            os.replace(tmp_path, str(JOURNAL_SNAPSHOT))
            logger.info("Journal snapshot written to %s", JOURNAL_SNAPSHOT.name)
        except (ValueError, OSError):
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    except Exception as e:
        logger.warning("Could not write journal snapshot: %s", e)


if __name__ == "__main__":
    asyncio.run(aggregate_dashboard_data())
