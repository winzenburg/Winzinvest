#!/usr/bin/env python3
"""
Market regime detection and portfolio allocation.

Uses SPY vs 200 SMA and VIX to classify regime; returns short/long allocation
for use by dual-mode executor. Prefers IBKR when ib is connected; falls back to yfinance.
"""

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Literal, Optional

_TRADING_DIR = Path(__file__).resolve().parent.parent
_REGIME_CONTEXT_FILE = _TRADING_DIR / "logs" / "regime_context.json"
_REGIME_STATE_FILE = _TRADING_DIR / "logs" / "regime_state.json"

logger = logging.getLogger(__name__)

RegimeType = Literal["STRONG_DOWNTREND", "MIXED", "STRONG_UPTREND", "CHOPPY", "UNFAVORABLE"]


def _regime_from_spy_vix(
    current_price: float,
    sma_200: float,
    current_vix: float,
    spy_20d_std: Optional[float] = None,
    ema_8: Optional[float] = None,
    ema_21: Optional[float] = None,
    days_above_200: int = 0,
) -> RegimeType:
    """Classify regime from SPY vs SMA and VIX. Caller ensures sma_200 > 0.

    UNFAVORABLE: VIX > 30 AND price within 1% of 200 SMA AND high recent volatility.
    Ed Seykota / PTJ: "know when to sit on your hands."

    STRONG_UPTREND requires confirmation to prevent false breakout signals:
      - SPY > 200 SMA by ≥ 2% for at least 3 consecutive days
      - 8 EMA and 21 EMA both above the 200 SMA (momentum confirmed)
      - VIX < 18 (relaxed from 15 — war premium means 15 is too rare)
    Downgrade signals (STRONG_DOWNTREND, UNFAVORABLE) are kept fast to react quickly
    to deterioration; upside upgrades are deliberately slow.
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

    # STRONG_UPTREND: require sustained confirmation — not just a single-day cross.
    # "Topping took months, bottoming will too. Relief rallies are bull traps."
    ema_confirmed = (
        (ema_8 is None or ema_8 > sma_200)
        and (ema_21 is None or ema_21 > sma_200)
    )
    if (
        distance_to_sma > 0.02
        and current_vix < 18           # relaxed from 15; war premium rarely dips to 15
        and days_above_200 >= 3        # must hold above 200 DMA for 3+ days
        and ema_confirmed              # short-term EMAs must confirm, not just price spike
    ):
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

    # Short-term EMAs for confirmation of genuine uptrend vs dead-cat bounce
    ema_8: Optional[float] = None
    ema_21: Optional[float] = None
    if len(close) >= 21:
        ema_8 = float(close.ewm(span=8, adjust=False).mean().iloc[-1])
        ema_21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1])

    # Count consecutive days SPY has closed above 200 SMA (capped at 10 for efficiency)
    days_above_200 = 0
    sma_series = close.rolling(200).mean()
    for i in range(1, min(11, len(close))):
        if close.iloc[-i] > sma_series.iloc[-i]:
            days_above_200 += 1
        else:
            break

    return _regime_from_spy_vix(
        current_price, sma_200, current_vix, spy_20d_std,
        ema_8=ema_8, ema_21=ema_21, days_above_200=days_above_200,
    )


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
    # STRONG_DOWNTREND: lean short — market in confirmed downtrend, short weak sectors
    # up to 30% of NLV while keeping 50% in income-generating longs (covered calls).
    "STRONG_DOWNTREND": {"shorts": 0.30, "longs": 0.50},
    # MIXED: SPY below 200 DMA but VIX under control — moderate short bias
    "MIXED": {"shorts": 0.25, "longs": 0.80},
    # STRONG_UPTREND: confirmed multi-day breakout above 200 DMA — all-in longs
    "STRONG_UPTREND": {"shorts": 0.00, "longs": 1.00},
    # CHOPPY: balanced — enough shorts to hedge, enough longs to capture upside
    # 50/50 reflects live experience: pure long bias gets killed in choppy action
    "CHOPPY": {"shorts": 0.50, "longs": 0.85},
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


def get_macro_size_multiplier() -> float:
    """Return the position-sizing multiplier from the macro regime monitor (Layer 2).

    Reads ``logs/regime_state.json`` (written by ``regime_monitor.py``) and returns
    ``parameters.sizeMultiplier``.  Falls back to 1.0 on any error so executors
    always receive a safe value.

    Macro band → multiplier mapping (mirrors regime_monitor.py defaults):
        RISK_ON    → 1.00
        NEUTRAL    → 0.75
        TIGHTENING → 0.50
        DEFENSIVE  → 0.25
    """
    try:
        if _REGIME_STATE_FILE.exists():
            raw = json.loads(_REGIME_STATE_FILE.read_text())
            multiplier = raw.get("parameters", {}).get("sizeMultiplier")
            if isinstance(multiplier, (int, float)) and 0.0 < multiplier <= 1.0:
                return float(multiplier)
    except Exception as exc:
        logger.warning("Could not read macro size multiplier from regime_state.json: %s", exc)
    return 1.0


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
    _dir = _REGIME_CONTEXT_FILE.parent
    fd, tmp = tempfile.mkstemp(dir=_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, _REGIME_CONTEXT_FILE)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    logger.debug("Persisted regime %s to regime_context.json", regime)
