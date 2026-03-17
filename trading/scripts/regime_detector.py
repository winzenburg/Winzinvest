#!/usr/bin/env python3
"""
Market regime detection and portfolio allocation.

Uses SPY vs 200 SMA and VIX to classify regime; returns short/long allocation
for use by dual-mode executor. Prefers IBKR when ib is connected; falls back to yfinance.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Literal, Optional

_TRADING_DIR = Path(__file__).resolve().parent.parent
_REGIME_CONTEXT_FILE = _TRADING_DIR / "logs" / "regime_context.json"

logger = logging.getLogger(__name__)

RegimeType = Literal["STRONG_DOWNTREND", "MIXED", "STRONG_UPTREND", "CHOPPY", "UNFAVORABLE"]


def _regime_from_spy_vix(
    current_price: float,
    sma_200: float,
    current_vix: float,
    spy_20d_std: Optional[float] = None,
) -> RegimeType:
    """Classify regime from SPY vs SMA and VIX. Caller ensures sma_200 > 0.

    UNFAVORABLE: VIX > 30 AND price within 1% of 200 SMA AND high recent volatility.
    Ed Seykota / PTJ: "know when to sit on your hands."
    """
    distance_to_sma = (current_price - sma_200) / sma_200

    if (
        current_vix > 30
        and abs(distance_to_sma) < 0.01
        and (spy_20d_std is None or spy_20d_std > 0.02)
    ):
        return "UNFAVORABLE"

    if distance_to_sma < -0.02 and current_vix > 20:
        return "STRONG_DOWNTREND"
    if distance_to_sma > 0.02 and current_vix < 15:
        return "STRONG_UPTREND"
    if distance_to_sma < -0.02 and current_vix < 20:
        return "MIXED"
    return "CHOPPY"


def _fetch_regime_from_yfinance() -> Optional[RegimeType]:
    """Fetch SPY/VIX via yfinance; return regime or None on failure."""
    try:
        import yfinance as yf
    except ImportError:
        return None
    try:
        spy = yf.download("SPY", period="1y", progress=False)
        vix = yf.download("^VIX", period="1y", progress=False)
    except Exception as e:
        logger.warning("yfinance SPY/VIX fetch failed: %s", e)
        return None
    if spy is None or spy.empty or len(spy) < 200:
        return None
    import pandas as _pd
    if isinstance(spy.columns, _pd.MultiIndex):
        spy.columns = spy.columns.get_level_values(0)
    close = spy["Close"] if "Close" in spy.columns else spy.iloc[:, 3]
    if isinstance(close, _pd.DataFrame):
        close = close.iloc[:, 0]
    current_price = float(close.iloc[-1])
    sma_200 = float(close.rolling(200).mean().iloc[-1])
    if sma_200 <= 0:
        return None
    current_vix = 20.0
    if vix is not None and not vix.empty:
        if isinstance(vix.columns, _pd.MultiIndex):
            vix.columns = vix.columns.get_level_values(0)
        vc = vix["Close"] if "Close" in vix.columns else vix.iloc[:, 3]
        if isinstance(vc, _pd.DataFrame):
            vc = vc.iloc[:, 0]
        current_vix = float(vc.iloc[-1])
    spy_20d_std = None
    if len(close) >= 20:
        spy_20d_std = float(close.pct_change().iloc[-20:].std())
    return _regime_from_spy_vix(current_price, sma_200, current_vix, spy_20d_std)


def detect_market_regime() -> RegimeType:
    """
    Classify current regime from SPY price vs 200 SMA and VIX level.

    Uses yfinance only. For IBKR fallback, use
    broker_data_helpers.regime_from_ib() in executor code.
    Defaults to CHOPPY on failure.
    """
    regime = _fetch_regime_from_yfinance()
    if regime is not None:
        return regime
    logger.warning("Regime detection failed (yfinance); defaulting to CHOPPY")
    return "CHOPPY"


_DEFAULT_ALLOCATIONS: Dict[RegimeType, Dict[str, float]] = {
    "STRONG_DOWNTREND": {"shorts": 0.00, "longs": 0.50},
    "MIXED": {"shorts": 0.25, "longs": 0.80},
    "STRONG_UPTREND": {"shorts": 0.00, "longs": 1.00},
    "CHOPPY": {"shorts": 0.35, "longs": 0.85},
    "UNFAVORABLE": {"shorts": 0.00, "longs": 0.00},
}


def _load_adaptive_allocations() -> Optional[Dict[str, Dict[str, float]]]:
    """Load regime allocations from adaptive_config.json if available."""
    try:
        from adaptive_config_loader import get_adaptive_dict
        allocs = get_adaptive_dict("regime_allocations")
        if allocs:
            return allocs
    except ImportError:
        pass
    return None


def calculate_portfolio_allocation(
    market_regime: RegimeType,
) -> Dict[str, float]:
    """
    Return target allocation (shorts, longs) as fractions that sum to 1.0.

    Checks adaptive_config.json first for learned allocations, then
    falls back to hardcoded defaults.
    """
    adaptive = _load_adaptive_allocations()
    if adaptive and market_regime in adaptive:
        alloc = adaptive[market_regime]
        if "shorts" in alloc and "longs" in alloc:
            return dict(alloc)
    return _DEFAULT_ALLOCATIONS.get(market_regime, {"shorts": 0.50, "longs": 0.50}).copy()


def persist_regime_to_context(regime: RegimeType) -> None:
    """Write current regime (and updated_at) to logs/regime_context.json, preserving existing note and catalysts."""
    data: Dict[str, Any] = {
        "regime": None,
        "note": "",
        "catalysts": [],
        "updated_at": None,
    }
    if _REGIME_CONTEXT_FILE.exists():
        try:
            raw = json.loads(_REGIME_CONTEXT_FILE.read_text())
            if isinstance(raw, dict):
                data["note"] = raw.get("note") if isinstance(raw.get("note"), str) else ""
                data["catalysts"] = raw.get("catalysts") if isinstance(raw.get("catalysts"), list) else []
        except (OSError, json.JSONDecodeError):
            pass
    data["regime"] = regime
    data["updated_at"] = datetime.now().isoformat()
    _REGIME_CONTEXT_FILE.parent.mkdir(parents=True, exist_ok=True)
    _REGIME_CONTEXT_FILE.write_text(json.dumps(data, indent=2))
    logger.debug("Persisted regime %s to regime_context.json", regime)
