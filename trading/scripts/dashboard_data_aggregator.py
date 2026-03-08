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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DASHBOARD_SNAPSHOT = TRADING_DIR / "logs" / "dashboard_snapshot.json"
DAILY_LOSS_FILE = TRADING_DIR / "logs" / "daily_loss.json"
PEAK_EQUITY_FILE = TRADING_DIR / "logs" / "peak_equity.json"
SOD_EQUITY_FILE = TRADING_DIR / "logs" / "sod_equity.json"
EXECUTION_LOG = TRADING_DIR / "logs" / "executions.json"


def load_json_safe(path: Path) -> Any:
    """Load JSON file safely, return None if missing or invalid."""
    try:
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load {path}: {e}")
    return None


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
        
        if metrics["net_liquidation"] > 0:
            gross_exposure = abs(metrics["equity_with_loan"])
            metrics["leverage_ratio"] = gross_exposure / metrics["net_liquidation"]
    
    except Exception as e:
        logger.error(f"Error fetching account metrics: {e}")
    
    return metrics


def get_positions_data(ib: IB) -> Tuple[List[Dict], float, float]:
    """
    Get current positions with P&L and notional.
    Returns: (positions_list, long_notional, short_notional)
    """
    positions = []
    long_notional = 0.0
    short_notional = 0.0
    
    try:
        portfolio_items = ib.portfolio()
        
        for item in portfolio_items:
            if item.contract.secType != "STK":
                continue
            
            symbol = item.contract.symbol
            quantity = item.position
            avg_cost = item.averageCost
            market_price = item.marketPrice if item.marketPrice else avg_cost
            market_value = item.marketValue
            unrealized_pnl = item.unrealizedPNL
            realized_pnl = item.realizedPNL
            
            sector = SECTOR_MAP.get(symbol, "Unknown")
            
            position_data = {
                "symbol": symbol,
                "quantity": quantity,
                "side": "LONG" if quantity > 0 else "SHORT",
                "avg_cost": avg_cost,
                "market_price": market_price,
                "market_value": market_value,
                "unrealized_pnl": unrealized_pnl,
                "realized_pnl": realized_pnl,
                "notional": abs(market_value),
                "sector": sector,
                "return_pct": ((market_price - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0.0,
            }
            
            positions.append(position_data)
            
            if quantity > 0:
                long_notional += abs(market_value)
            else:
                short_notional += abs(market_value)
    
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
    
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


def calculate_performance_metrics(net_liq: float) -> Dict[str, Any]:
    """Calculate performance metrics from logs."""
    metrics = {
        "daily_pnl": 0.0,
        "daily_return_pct": 0.0,
        "total_pnl_30d": 0.0,
        "total_return_30d_pct": 0.0,
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
        
        executions = load_json_safe(EXECUTION_LOG)
        if executions and isinstance(executions, list):
            thirty_days_ago = datetime.now() - timedelta(days=30)
            recent_trades = [
                t for t in executions
                if "timestamp" in t and datetime.fromisoformat(t["timestamp"].replace("Z", "+00:00")) > thirty_days_ago
            ]
            
            metrics["total_trades"] = len(recent_trades)
            
            closed_trades = []
            for trade in recent_trades:
                if "pnl" in trade and trade["pnl"] is not None:
                    pnl = float(trade["pnl"])
                    closed_trades.append(pnl)
                    if pnl > 0:
                        metrics["winning_trades"] += 1
                    elif pnl < 0:
                        metrics["losing_trades"] += 1
            
            if closed_trades:
                metrics["total_pnl_30d"] = sum(closed_trades)
                
                sod_data = load_json_safe(SOD_EQUITY_FILE)
                if sod_data:
                    sod_equity_30d_ago = sod_data.get("equity", net_liq)
                    if sod_equity_30d_ago > 0:
                        metrics["total_return_30d_pct"] = (metrics["total_pnl_30d"] / sod_equity_30d_ago) * 100
                
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


def calculate_strategy_breakdown(executions: List[Dict]) -> Dict[str, Any]:
    """Break down performance by strategy."""
    strategies = {
        "momentum_long": {"trades": 0, "pnl": 0.0, "wins": 0, "losses": 0},
        "momentum_short": {"trades": 0, "pnl": 0.0, "wins": 0, "losses": 0},
        "mean_reversion": {"trades": 0, "pnl": 0.0, "wins": 0, "losses": 0},
        "pairs": {"trades": 0, "pnl": 0.0, "wins": 0, "losses": 0},
        "options": {"trades": 0, "pnl": 0.0, "wins": 0, "losses": 0},
        "webhook": {"trades": 0, "pnl": 0.0, "wins": 0, "losses": 0},
    }
    
    try:
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        for trade in executions:
            if "timestamp" not in trade:
                continue
            
            ts = datetime.fromisoformat(trade["timestamp"].replace("Z", "+00:00"))
            if ts < thirty_days_ago:
                continue
            
            strategy = trade.get("strategy", "unknown")
            pnl = trade.get("pnl")
            
            if strategy in strategies and pnl is not None:
                strategies[strategy]["trades"] += 1
                strategies[strategy]["pnl"] += float(pnl)
                if float(pnl) > 0:
                    strategies[strategy]["wins"] += 1
                else:
                    strategies[strategy]["losses"] += 1
    
    except Exception as e:
        logger.error(f"Error calculating strategy breakdown: {e}")
    
    for strat in strategies.values():
        total = strat["wins"] + strat["losses"]
        strat["win_rate"] = (strat["wins"] / total * 100) if total > 0 else 0.0
    
    return strategies


def calculate_beta_correlation(positions: List[Dict]) -> Dict[str, float]:
    """Calculate portfolio beta and correlation to SPY."""
    try:
        if not positions:
            return {"beta": 0.0, "correlation": 0.0}
        
        spy_data = yf.download("SPY", period="3mo", interval="1d", progress=False)
        if spy_data.empty:
            return {"beta": 0.0, "correlation": 0.0}
        
        spy_returns = spy_data["Close"].pct_change().dropna()
        
        portfolio_returns = []
        weights = []
        
        for pos in positions[:10]:
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
            except:
                continue
        
        if not portfolio_returns or not weights:
            return {"beta": 0.0, "correlation": 0.0}
        
        total_weight = sum(weights)
        
        min_length = min(len(spy_returns), min(len(ret) for ret in portfolio_returns))
        spy_returns_trimmed = spy_returns[:min_length]
        
        weighted_returns = np.zeros(min_length)
        for ret, weight in zip(portfolio_returns, weights):
            ret_trimmed = ret[:min_length]
            weighted_returns += ret_trimmed * (weight / total_weight)
        
        if len(weighted_returns) < 10:
            return {"beta": 0.0, "correlation": 0.0}
        
        cov_matrix = np.cov(spy_returns_trimmed, weighted_returns)
        beta = cov_matrix[0, 1] / cov_matrix[0, 0] if cov_matrix[0, 0] > 0 else 0.0
        correlation = np.corrcoef(spy_returns_trimmed, weighted_returns)[0, 1]
        
        return {"beta": beta, "correlation": correlation}
    
    except Exception as e:
        logger.error(f"Error calculating beta: {e}")
        return {"beta": 0.0, "correlation": 0.0}


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
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent = [
            t for t in executions
            if "timestamp" in t and datetime.fromisoformat(t["timestamp"].replace("Z", "+00:00")) > thirty_days_ago
        ]
        
        if not recent:
            return analytics
        
        pnls = [t.get("pnl", 0) for t in recent if t.get("pnl") is not None]
        if pnls:
            analytics["best_trade"] = max(pnls)
            analytics["worst_trade"] = min(pnls)
        
        notionals = [t.get("notional", 0) for t in recent if t.get("notional")]
        if notionals:
            analytics["largest_position"] = max(notionals)
        
        mae_values = [t.get("mae", 0) for t in recent if t.get("mae")]
        if mae_values:
            analytics["avg_mae"] = np.mean(mae_values)
        
        mfe_values = [t.get("mfe", 0) for t in recent if t.get("mfe")]
        if mfe_values:
            analytics["avg_mfe"] = np.mean(mfe_values)
        
        slippages = [t.get("slippage_bps", 0) for t in recent if t.get("slippage_bps")]
        if slippages:
            analytics["avg_slippage_bps"] = np.mean(slippages)
        
        hold_times = []
        for t in recent:
            if "entry_time" in t and "exit_time" in t:
                try:
                    entry = datetime.fromisoformat(t["entry_time"].replace("Z", "+00:00"))
                    exit = datetime.fromisoformat(t["exit_time"].replace("Z", "+00:00"))
                    hours = (exit - entry).total_seconds() / 3600
                    hold_times.append(hours)
                except:
                    pass
        
        if hold_times:
            analytics["avg_hold_time_hours"] = np.mean(hold_times)
    
    except Exception as e:
        logger.error(f"Error calculating trade analytics: {e}")
    
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
        watchlist = TRADING_DIR / "watchlist_longs.json"
        if watchlist.exists():
            data = load_json_safe(watchlist)
            if data and "generated_at" in data:
                gen_time = datetime.fromisoformat(data["generated_at"])
                health["last_screener_run"] = data["generated_at"]
                minutes_old = (datetime.now() - gen_time).total_seconds() / 60
                health["data_freshness_minutes"] = int(minutes_old)
                
                if minutes_old > 60:
                    health["issues"].append(f"Screener data is {int(minutes_old)} minutes old")
                    health["status"] = "warning"
        
        if EXECUTION_LOG.exists():
            executions = load_json_safe(EXECUTION_LOG)
            if executions and isinstance(executions, list) and executions:
                last_exec = executions[-1]
                if "timestamp" in last_exec:
                    health["last_execution"] = last_exec["timestamp"]
        
        if not health["issues"]:
            health["status"] = "healthy"
    
    except Exception as e:
        logger.error(f"Error checking system health: {e}")
        health["status"] = "error"
        health["issues"].append(str(e))
    
    return health


async def aggregate_dashboard_data() -> Dict[str, Any]:
    """Main aggregation function - collect all metrics."""
    logger.info("Starting dashboard data aggregation...")
    
    ib = IB()
    try:
        await ib.connectAsync("127.0.0.1", 4002, clientId=199)
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
        
        sector_exposure, total_notional = portfolio_sector_exposure(ib)
        
        performance = calculate_performance_metrics(net_liq)
        
        executions = load_json_safe(EXECUTION_LOG) or []
        strategy_breakdown = calculate_strategy_breakdown(executions)
        
        trade_analytics = calculate_trade_analytics(executions)
        
        beta_corr = calculate_beta_correlation(positions)
        
        system_health = get_system_health()
        
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
        
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "account": account_metrics,
            "performance": performance,
            "positions": {
                "list": positions,
                "count": len(positions),
                "long_notional": long_notional,
                "short_notional": short_notional,
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
            },
            "strategy_breakdown": strategy_breakdown,
            "trade_analytics": trade_analytics,
            "candidates": {
                "longs": long_candidates,
                "shorts": short_candidates,
            },
            "system_health": system_health,
        }
        
        with open(DASHBOARD_SNAPSHOT, "w") as f:
            json.dump(snapshot, f, indent=2)
        
        logger.info(f"Dashboard snapshot written to {DASHBOARD_SNAPSHOT}")
        return snapshot
    
    finally:
        ib.disconnect()


if __name__ == "__main__":
    asyncio.run(aggregate_dashboard_data())
