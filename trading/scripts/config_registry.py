#!/usr/bin/env python3
"""
Config Registry — single source of truth for JSON config file locations and owners.

Every JSON config file in the trading system is listed here with its path,
purpose, primary writer, and which module reads it. This prevents config
sprawl and makes it easy to audit who writes/reads each file.

Usage:
    from config_registry import REGISTRY, get_config_path, list_configs

    path = get_config_path("risk")
    for entry in list_configs():
        print(entry["name"], entry["path"])
"""

from __future__ import annotations

from pathlib import Path

try:
    from paths import TRADING_DIR
except ImportError:
    TRADING_DIR = Path(__file__).resolve().parent.parent


REGISTRY: list[dict[str, str]] = [
    # ── Risk & Limits ───────────────────────────────────────────────
    {
        "name": "risk",
        "path": str(TRADING_DIR / "risk.json"),
        "purpose": "Primary risk limits: position sizing, daily loss, sector caps, options caps",
        "writer": "manual edit",
        "readers": "risk_config.py, execution_gates.py, cash_monitor.py, auto_options_executor.py",
    },
    {
        "name": "risk_live",
        "path": str(TRADING_DIR / "risk.live.json"),
        "purpose": "Live-mode overrides merged into risk.json when TRADING_MODE=live",
        "writer": "manual edit",
        "readers": "risk_config.py",
    },
    {
        "name": "adaptive_config",
        "path": str(TRADING_DIR / "adaptive_config.json"),
        "purpose": "Learned parameters: ATR multipliers, risk_per_trade, regime allocations, ranking weights",
        "writer": "adaptive_params.py",
        "readers": "adaptive_config_loader.py, regime_detector.py, risk_config.py",
    },
    {
        "name": "kill_switch",
        "path": str(TRADING_DIR / "kill_switch.json"),
        "purpose": "Global trading halt: {active: true/false, reason, timestamp}",
        "writer": "dashboard API, risk_monitor.py, drawdown_circuit_breaker.py",
        "readers": "kill_switch_guard.py, execution_gates.py, base_executor.py",
    },
    {
        "name": "drawdown_breaker_state",
        "path": str(TRADING_DIR / "logs" / "drawdown_breaker_state.json"),
        "purpose": "Current drawdown tier (0-3) and scaling factor",
        "writer": "drawdown_circuit_breaker.py",
        "readers": "base_executor.py, dashboard API",
    },
    # ── Sector & Allocation ─────────────────────────────────────────
    {
        "name": "sector_allocation",
        "path": str(TRADING_DIR / "sector_allocation.json"),
        "purpose": "Ranked sectors by 63-day return with size multipliers",
        "writer": "sector_rotation.py",
        "readers": "nx_screener_longs.py, nx_screener_production.py",
    },
    {
        "name": "macro_events",
        "path": str(TRADING_DIR / "config" / "macro_events.json"),
        "purpose": "Active macro events with size adjustments and sector overrides",
        "writer": "manual edit",
        "readers": "cash_monitor.py, sector_rebalancer.py, regime_detector.py",
    },
    # ── Watchlists & Candidates ─────────────────────────────────────
    {
        "name": "watchlist_longs",
        "path": str(TRADING_DIR / "watchlist_longs.json"),
        "purpose": "Long candidates from nx_screener_longs",
        "writer": "nx_screener_longs.py",
        "readers": "execute_longs.py, execute_dual_mode.py",
    },
    {
        "name": "watchlist_shorts",
        "path": str(TRADING_DIR / "watchlist_shorts.json"),
        "purpose": "Short candidates from nx_screener_shorts (bearish regime)",
        "writer": "nx_screener_shorts.py",
        "readers": "execute_dual_mode.py",
    },
    {
        "name": "watchlist_multimode",
        "path": str(TRADING_DIR / "watchlist_multimode.json"),
        "purpose": "Multi-mode candidates: sector_strength, premium_selling, short_opportunities",
        "writer": "nx_screener_production.py",
        "readers": "execute_dual_mode.py",
    },
    {
        "name": "watchlist_pairs",
        "path": str(TRADING_DIR / "watchlist_pairs.json"),
        "purpose": "Pairs candidates with spread z-scores",
        "writer": "pairs_screener.py",
        "readers": "execute_pairs.py",
    },
    {
        "name": "watchlist_spotlight",
        "path": str(TRADING_DIR / "watchlist_spotlight.json"),
        "purpose": "Manually curated high-conviction watchlist with alert/execution config",
        "writer": "manual edit",
        "readers": "spotlight_monitor.py",
    },
    {
        "name": "watchlist_mean_reversion",
        "path": str(TRADING_DIR / "watchlist_mean_reversion.json"),
        "purpose": "Mean-reversion candidates from mr_screener",
        "writer": "mr_screener.py",
        "readers": "execute_mean_reversion.py",
    },
    # ── Pending Trades (two distinct files) ─────────────────────────
    {
        "name": "pending_trades_config",
        "path": str(TRADING_DIR / "config" / "pending_trades.json"),
        "purpose": "Manually queued trades: stops, TPs, conditional entries",
        "writer": "manual edit / dashboard",
        "readers": "execute_pending_trades.py",
    },
    {
        "name": "pending_trades_logs",
        "path": str(TRADING_DIR / "logs" / "pending_trades.json"),
        "purpose": "Auto-generated pending trades from alert monitors",
        "writer": "auto_options_executor.py",
        "readers": "auto_options_executor.py (process_pending_trades)",
    },
    # ── State & Snapshots ───────────────────────────────────────────
    {
        "name": "portfolio",
        "path": str(TRADING_DIR / "portfolio.json"),
        "purpose": "Live portfolio snapshot from IBKR (positions + account values)",
        "writer": "portfolio_snapshot.py",
        "readers": "daily_report.py, dashboard_data_aggregator.py",
    },
    {
        "name": "dashboard_snapshot",
        "path": str(TRADING_DIR / "logs" / "dashboard_snapshot.json"),
        "purpose": "Aggregated dashboard data (positions, risk, performance, health)",
        "writer": "dashboard_data_aggregator.py",
        "readers": "Next.js API /api/dashboard, execute_pending_trades.py (prices)",
    },
    {
        "name": "regime_context",
        "path": str(TRADING_DIR / "logs" / "regime_context.json"),
        "purpose": "Current execution regime (L1: SPY/VIX) for dashboard display",
        "writer": "regime_detector.py, scheduler job_regime_check",
        "readers": "Dashboard Regime card, screeners",
    },
    {
        "name": "regime_state",
        "path": str(TRADING_DIR / "logs" / "regime_state.json"),
        "purpose": "Macro regime (L2: regime_monitor) with size multiplier",
        "writer": "regime_monitor.py",
        "readers": "regime_detector.get_macro_size_multiplier()",
    },
    {
        "name": "cash_monitor_state",
        "path": str(TRADING_DIR / "config" / "cash_monitor_state.json"),
        "purpose": "Last trigger timestamps for cash/leverage/delever actions",
        "writer": "cash_monitor.py",
        "readers": "cash_monitor.py",
    },
    {
        "name": "trades_db",
        "path": str(TRADING_DIR / "logs" / "trades.db"),
        "purpose": "SQLite trade log — all open/closed positions",
        "writer": "trade_log_db.py (via executors)",
        "readers": "trade_outcome_resolver.py, execution_gates.py (heat), dashboard",
    },
]

_REGISTRY_BY_NAME = {entry["name"]: entry for entry in REGISTRY}


def get_config_path(name: str) -> Path:
    """Return the Path for a registered config by name. Raises KeyError if unknown."""
    entry = _REGISTRY_BY_NAME.get(name)
    if entry is None:
        raise KeyError(f"Unknown config name: {name!r}. Known: {sorted(_REGISTRY_BY_NAME)}")
    return Path(entry["path"])


def list_configs() -> list[dict[str, str]]:
    """Return all registered configs."""
    return list(REGISTRY)
