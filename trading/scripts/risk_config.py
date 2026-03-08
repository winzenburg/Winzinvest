#!/usr/bin/env python3
"""
Shared risk config loader for trading scripts.

Reads trading/risk.json for equity_shorts and options limits. Used by:
- nx_screener_production.py (trim short list to slots left)
- execute_candidates.py (max short positions, optional max new shorts per day)
- direct_premium_executor.py (max options per day/month)
- auto_options_executor.py (same options limits)

Options execution paths (direct executor and any webhook that places options orders)
must both read these limits and enforce them so caps are consistent.
"""

from pathlib import Path
from typing import Any, Optional


def _trading_dir_from_workspace(workspace: Path) -> Path:
    """Return trading directory. If workspace is already trading dir, return as-is; else assume workspace is parent."""
    if (workspace / "risk.json").exists():
        return workspace
    return workspace.parent if workspace.name == "scripts" else workspace


def _load_raw(workspace: Path) -> Any:
    path = _trading_dir_from_workspace(workspace) / "risk.json"
    if not path.exists():
        return None
    try:
        import json
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _is_valid_number(x: Any, allow_none: bool = False) -> bool:
    if allow_none and x is None:
        return True
    if x is None:
        return False
    return isinstance(x, (int, float)) and (x == int(x) if isinstance(x, float) else True)


def _safe_int(value: Any, default: int, min_val: int = 1) -> int:
    if value is None:
        return default
    try:
        n = int(value)
        return max(min_val, n) if min_val is not None else n
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: Optional[float]) -> Optional[float]:
    if value is None:
        return default
    try:
        f = float(value)
        return f if f >= 0 else default
    except (TypeError, ValueError):
        return default


def get_position_size(workspace: Path) -> int:
    """Legacy equity short position size in shares. Default 100 if missing/invalid.

    DEPRECATED: prefer calculate_position_size() in atr_stops.py which uses
    risk_per_trade_pct and max_position_pct_of_equity for proper scaling.
    Kept for backward compatibility; returns absolute_max_shares_per_order from
    the portfolio section if set, otherwise the legacy position_size field.
    """
    raw = _load_raw(workspace)
    if not isinstance(raw, dict):
        return 5000
    portfolio = raw.get("portfolio")
    if isinstance(portfolio, dict):
        v = portfolio.get("absolute_max_shares_per_order")
        if v is not None:
            return _safe_int(v, 5000, min_val=1)
    eq = raw.get("equity_shorts")
    if not isinstance(eq, dict):
        return 5000
    return _safe_int(eq.get("position_size"), 5000, min_val=1)


def get_max_short_positions(workspace: Path) -> int:
    """Max number of equity short positions. Default 20 if missing/invalid."""
    raw = _load_raw(workspace)
    if not isinstance(raw, dict):
        return 20
    eq = raw.get("equity_shorts")
    if not isinstance(eq, dict):
        return 20
    return _safe_int(eq.get("max_short_positions"), 20, min_val=1)


def get_max_long_positions(workspace: Path) -> int:
    """Max number of equity long positions. Default 25 if missing/invalid."""
    raw = _load_raw(workspace)
    if not isinstance(raw, dict):
        return 25
    eq = raw.get("equity_longs")
    if not isinstance(eq, dict):
        return 25
    return _safe_int(eq.get("max_long_positions"), 25, min_val=1)


def get_max_total_notional_pct(workspace: Path) -> float:
    """Max total notional (longs + shorts) as fraction of equity. Default 1.0 (100%)."""
    raw = _load_raw(workspace)
    if not isinstance(raw, dict):
        return 1.0
    portfolio = raw.get("portfolio")
    if not isinstance(portfolio, dict):
        return 1.0
    v = portfolio.get("max_total_notional_pct_of_equity")
    if v is None:
        return 1.0
    try:
        pct = float(v)
        return max(0.10, min(2.0, pct))
    except (TypeError, ValueError):
        return 1.0


def get_max_short_notional_dollars(workspace: Path) -> Optional[float]:
    """Max total short notional in dollars. None if not set."""
    raw = _load_raw(workspace)
    if not isinstance(raw, dict):
        return None
    eq = raw.get("equity_shorts")
    if not isinstance(eq, dict):
        return None
    return _safe_float(eq.get("max_short_notional_dollars"), None)


def get_max_short_notional_pct_of_equity(workspace: Path) -> Optional[float]:
    """Max short notional as fraction of account equity (e.g. 0.10 = 10%). None if not set."""
    raw = _load_raw(workspace)
    if not isinstance(raw, dict):
        return None
    eq = raw.get("equity_shorts")
    if not isinstance(eq, dict):
        return None
    return _safe_float(eq.get("max_short_notional_pct_of_equity"), None)


def get_max_new_shorts_per_day(workspace: Path) -> Optional[int]:
    """Max new short positions per calendar day. None if not set (no limit)."""
    raw = _load_raw(workspace)
    if not isinstance(raw, dict):
        return None
    eq = raw.get("equity_shorts")
    if not isinstance(eq, dict):
        return None
    v = eq.get("max_new_shorts_per_day")
    if v is None:
        return None
    return _safe_int(v, 999, min_val=0)


def get_max_sector_concentration_pct(workspace: Path) -> float:
    """Max sector concentration as percentage (e.g. 30). Default 30 if missing/invalid."""
    raw = _load_raw(workspace)
    if not isinstance(raw, dict):
        return 30.0
    eq = raw.get("equity_shorts")
    if not isinstance(eq, dict):
        return 30.0
    v = eq.get("max_sector_concentration_pct")
    if v is None:
        return 30.0
    try:
        pct = float(v)
        return max(1.0, min(100.0, pct))
    except (TypeError, ValueError):
        return 30.0


def get_risk_per_trade_pct(workspace: Path) -> float:
    """Risk per trade as fraction of equity (e.g. 0.01 = 1%).

    Checks adaptive_config.json first, then risk.json, then default 0.01.
    """
    try:
        from adaptive_config_loader import get_adaptive_float
        adaptive_val = get_adaptive_float("risk_per_trade_pct", 0.0)
        if 0.001 <= adaptive_val <= 0.05:
            return adaptive_val
    except ImportError:
        pass

    raw = _load_raw(workspace)
    if not isinstance(raw, dict):
        return 0.01
    eq = raw.get("equity_shorts")
    if not isinstance(eq, dict):
        return 0.01
    v = eq.get("risk_per_trade_pct")
    if v is None:
        return 0.01
    try:
        pct = float(v)
        return max(0.001, min(0.05, pct))
    except (TypeError, ValueError):
        return 0.01


def get_max_options_per_day(workspace: Path) -> int:
    """Max options orders per day. Default 2 if missing/invalid."""
    raw = _load_raw(workspace)
    if not isinstance(raw, dict):
        return 2
    opt = raw.get("options")
    if not isinstance(opt, dict):
        return 2
    return _safe_int(opt.get("max_options_per_day"), 2, min_val=0)


def get_max_options_per_month(workspace: Path) -> int:
    """Max options orders per month. Default 20 if missing/invalid."""
    raw = _load_raw(workspace)
    if not isinstance(raw, dict):
        return 20
    opt = raw.get("options")
    if not isinstance(opt, dict):
        return 20
    return _safe_int(opt.get("max_options_per_month"), 20, min_val=0)


def get_max_position_pct_of_equity(workspace: Path, side: str = "short") -> float:
    """Max single position as fraction of equity (e.g. 0.05 = 5%).

    Reads from equity_shorts or equity_longs depending on side.
    Default 0.05 (5%) if missing.
    """
    raw = _load_raw(workspace)
    if not isinstance(raw, dict):
        return 0.05
    section_key = "equity_longs" if side.upper() in ("LONG", "BUY") else "equity_shorts"
    section = raw.get(section_key)
    if not isinstance(section, dict):
        return 0.05
    v = section.get("max_position_pct_of_equity")
    if v is None:
        return 0.05
    try:
        pct = float(v)
        return max(0.005, min(0.20, pct))
    except (TypeError, ValueError):
        return 0.05


def get_max_short_notional_pct(workspace: Path) -> float:
    """Max total short notional as fraction of equity. Default 0.50 (50%)."""
    raw = _load_raw(workspace)
    if not isinstance(raw, dict):
        return 0.50
    eq = raw.get("equity_shorts")
    if not isinstance(eq, dict):
        return 0.50
    v = eq.get("max_short_notional_pct_of_equity")
    if v is None:
        return 0.50
    try:
        pct = float(v)
        return max(0.05, min(1.0, pct))
    except (TypeError, ValueError):
        return 0.50


def get_daily_loss_limit_pct(workspace: Path) -> float:
    """Daily loss limit as fraction of equity. Default 0.03 (3%)."""
    raw = _load_raw(workspace)
    if not isinstance(raw, dict):
        return 0.03
    portfolio = raw.get("portfolio")
    if not isinstance(portfolio, dict):
        return 0.03
    v = portfolio.get("daily_loss_limit_pct")
    if v is None:
        return 0.03
    try:
        pct = float(v)
        return max(0.005, min(0.10, pct))
    except (TypeError, ValueError):
        return 0.03


def get_absolute_max_shares(workspace: Path) -> int:
    """Hard safety cap on shares per order. Default 5000."""
    raw = _load_raw(workspace)
    if not isinstance(raw, dict):
        return 5000
    portfolio = raw.get("portfolio")
    if not isinstance(portfolio, dict):
        return 5000
    return _safe_int(portfolio.get("absolute_max_shares_per_order"), 5000, min_val=1)


def compute_vol_scale(workspace: Path) -> float:
    """Compute position-size scale factor based on SPY realized vol vs target.

    When realized vol > target, positions shrink (scale < 1.0).
    When realized vol < target, positions grow (scale > 1.0, capped).
    Returns 1.0 if disabled or data unavailable.
    """
    raw = _load_raw(workspace)
    if not isinstance(raw, dict):
        return 1.0
    vt = raw.get("vol_targeting")
    if not isinstance(vt, dict) or not vt.get("enabled", False):
        return 1.0

    target = float(vt.get("target_annual_vol", 0.15))
    cap = float(vt.get("scale_cap", 1.5))
    lookback = int(vt.get("lookback_days", 20))
    if target <= 0:
        return 1.0

    try:
        import numpy as np
        import yfinance as yf
        spy = yf.download("SPY", period="60d", interval="1d", progress=False)
        if spy.empty or len(spy) < lookback:
            return 1.0
        close = spy["Close"]
        if hasattr(close, "columns"):
            close = close.iloc[:, 0]
        returns = close.pct_change().dropna()
        realized = float(returns.tail(lookback).std() * np.sqrt(252))
        if realized <= 0:
            return 1.0
        scale = min(target / realized, cap)
        return max(0.25, scale)
    except Exception:
        return 1.0
