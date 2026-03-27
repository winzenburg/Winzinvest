"""
ATR-based stop/take-profit calculator for swing trades.

Uses 14-period ATR to set stop and TP distances proportional to each stock's
actual volatility, replacing fixed-percentage stops that cause premature exits
on volatile names and under-protection on calm ones.

Defaults: stop = 1.5x ATR, TP = 2.5x ATR. Falls back to fixed percentages
when ATR data is unavailable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple
import math
import logging

logger = logging.getLogger(__name__)

# Resolved once at import — used by brandt_conviction_mult to load risk.json
try:
    from paths import TRADING_DIR as _TRADING_DIR
    _RISK_JSON_PATH: Path = _TRADING_DIR / "risk.json"
except ImportError:
    _RISK_JSON_PATH = Path(__file__).parent.parent / "risk.json"

_DEFAULT_STOP_ATR_MULT = 1.5
_DEFAULT_TP_ATR_MULT = 3.5


def _load_adaptive_mult(key: str, default: float) -> float:
    try:
        from adaptive_config_loader import get_adaptive_float
        return get_adaptive_float(key, default)
    except ImportError:
        return default


STOP_ATR_MULT = _load_adaptive_mult("stop_atr_mult", _DEFAULT_STOP_ATR_MULT)
TP_ATR_MULT = _load_adaptive_mult("tp_atr_mult", _DEFAULT_TP_ATR_MULT)

FALLBACK_STOP_PCT = 0.02
FALLBACK_TP_PCT = 0.03


def fetch_atr(symbol: str) -> Optional[float]:
    """
    Fetch the 14-period daily ATR for symbol via yfinance.

    Returns None on failure. For IBKR fallback, use
    broker_data_helpers.atr_from_ib() in executor code.
    """
    atr = _atr_from_yfinance(symbol)
    if atr is not None and atr > 0:
        return atr
    return None


def _atr_from_yfinance(symbol: str) -> Optional[float]:
    try:
        import yfinance as yf
        import numpy as np
        import pandas as pd
    except ImportError:
        return None
    try:
        df = yf.download(symbol, period="1mo", progress=False)
        if df is None or df.empty or len(df) < 15:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        # Deduplicate columns that may result from MultiIndex flattening
        df = df.loc[:, ~df.columns.duplicated()]
        h = df["High"]
        l = df["Low"]
        c = df["Close"]
        # Flatten single-ticker series that may still be a DataFrame
        if hasattr(h, "columns"):
            h = h.iloc[:, 0]
        if hasattr(l, "columns"):
            l = l.iloc[:, 0]
        if hasattr(c, "columns"):
            c = c.iloc[:, 0]
        cp = c.shift(1)
        tr = np.maximum(h - l, np.maximum((h - cp).abs(), (l - cp).abs()))
        return float(tr.rolling(14, min_periods=1).mean().iloc[-1])
    except Exception:
        return None


def compute_stop_tp(
    entry_price: float,
    side: str,
    atr: Optional[float] = None,
    stop_mult: float = STOP_ATR_MULT,
    tp_mult: float = TP_ATR_MULT,
    fallback_stop_pct: float = FALLBACK_STOP_PCT,
    fallback_tp_pct: float = FALLBACK_TP_PCT,
) -> Tuple[float, float]:
    """
    Compute (stop_price, tp_price) using ATR when available, else fixed %.
    side: "SELL"/"SHORT" for shorts, "BUY"/"LONG" for longs.
    """
    is_short = side.upper() in ("SELL", "SHORT")
    if atr is not None and atr > 0:
        stop_dist = atr * stop_mult
        tp_dist = atr * tp_mult
    else:
        stop_dist = entry_price * fallback_stop_pct
        tp_dist = entry_price * fallback_tp_pct

    if is_short:
        stop_price = entry_price + stop_dist
        tp_price = entry_price - tp_dist
    else:
        stop_price = entry_price - stop_dist
        tp_price = entry_price + tp_dist
    return round(stop_price, 2), round(tp_price, 2)


# Trail multiplier loaded from adaptive_config so it can be tuned independently of TP.
# Default 2.5× (tighter than previous 3.0×) to capture more of each winner's move.
_DEFAULT_TRAILING_ATR_MULT = 2.5
TRAILING_ATR_MULT = _load_adaptive_mult("trail_atr_mult", _DEFAULT_TRAILING_ATR_MULT)


def compute_trailing_amount(
    atr: Optional[float] = None,
    entry_price: float = 0.0,
    trailing_mult: float = TRAILING_ATR_MULT,
    fallback_pct: float = 0.025,
) -> float:
    """
    Compute the trailing amount (dollar distance) for IB's TrailingStopOrder.
    Uses ATR-based distance when available, else a % of entry price.
    """
    if atr is not None and atr > 0:
        return round(atr * trailing_mult, 2)
    return round(entry_price * fallback_pct, 2)


def mfe_derived_tp_mult(strategy: Optional[str], fallback: float = TP_ATR_MULT) -> float:
    """Return the historically-calibrated TP multiplier for a given strategy.

    Lukas Fröhlich (Next Generation): TP targets should come from real MFE data,
    not fixed multiples.  attribution_gap_check.py builds mfe_targets.json daily;
    this function loads the P90 MFE (in ATR units) for the given strategy and
    returns it as the TP multiplier.

    Falls back to the configured tp_atr_mult_fallback (or the module default)
    when no historical data is available for the strategy.
    """
    try:
        import json as _json
        _risk = _json.loads(_RISK_JSON_PATH.read_text())
        stat_tp = _risk.get("statistical_tp", {})
        if not stat_tp.get("enabled", True):
            return fallback
        mfe_file_rel = stat_tp.get("mfe_file", "logs/mfe_targets.json")
        mfe_path: Path = _RISK_JSON_PATH.parent / mfe_file_rel
        if not mfe_path.exists():
            return fallback
        data = _json.loads(mfe_path.read_text())
        targets = data.get("targets", {})
        strategy_key = str(strategy or "unknown")
        entry = targets.get(strategy_key) or targets.get("unknown")
        if entry and "p90_atr" in entry:
            mult = float(entry["p90_atr"])
            n = entry.get("n", 0)
            logger.debug(
                "Fröhlich stat TP: strategy='%s' P90 MFE=%.2f ATR (n=%d)",
                strategy_key, mult, n,
            )
            return mult
    except Exception as exc:
        logger.debug("mfe_derived_tp_mult: could not load targets — %s", exc)
    return fallback


DEFAULT_RISK_PER_TRADE_PCT = 0.01
DEFAULT_MAX_POSITION_PCT = 0.05  # 5% of equity per position
MIN_SHARES = 1
ABSOLUTE_MAX_SHARES = 5000  # hard safety cap

CONVICTION_MULTIPLIERS = {
    "high": 1.5,    # conviction >= 0.8
    "medium": 1.0,  # 0.5 <= conviction < 0.8
    "low": 0.5,     # conviction < 0.5
}


def conviction_tier(conviction: Optional[float]) -> str:
    """Classify conviction score into a sizing tier."""
    if conviction is None:
        return "medium"
    if conviction >= 0.8:
        return "high"
    if conviction >= 0.5:
        return "medium"
    return "low"


def _load_brandt_tiers() -> list[dict]:
    """Load the 4-tier Brandt conviction curve from risk.json.

    Falls back to the legacy 3-tier system if risk.json is unavailable or
    the ``brandt_conviction_sizing`` key is absent.
    """
    try:
        import json as _json
        _risk = _json.loads(_RISK_JSON_PATH.read_text())
        tiers = _risk.get("brandt_conviction_sizing", {}).get("tiers", [])
        if tiers:
            return tiers
    except Exception:
        pass
    # Fallback — 3-tier curve aligned with raised conviction floor (Goedeker/Sharkness)
    # Anything below 0.55 is hard-blocked before reaching here via candidate_ranking floor
    return [
        {"min": 0.55, "max": 0.65, "mult": 0.85},
        {"min": 0.65, "max": 0.80, "mult": 1.40},
        {"min": 0.80, "max": 1.01, "mult": 2.00},
    ]


def brandt_conviction_mult(conviction: Optional[float]) -> float:
    """Return the position-size multiplier for a given conviction score.

    Peter Brandt (Unknown Market Wizards): size UP aggressively on the best
    signals; keep marginal signals small.  Uses the 4-tier curve from
    risk.json → brandt_conviction_sizing.tiers rather than the legacy 3-tier
    system, giving a steeper reward to the 0.65–0.80 and 0.80+ ranges.

    The multiplier applies only to the ATR-based risk budget (shares_from_risk).
    The NLV position cap is always enforced as a hard ceiling regardless of
    conviction, so a 2.0× multiplier cannot exceed the configured max_position_pct.
    """
    if conviction is None:
        conviction = 0.50  # neutral default
    tiers = _load_brandt_tiers()
    for tier in tiers:
        lo = float(tier.get("min", 0.0))
        hi = float(tier.get("max", 1.0))
        if lo <= conviction < hi:
            return float(tier.get("mult", 1.0))
    # Above all tiers — use the highest defined multiplier
    if tiers:
        return float(tiers[-1].get("mult", 1.5))
    return 1.0


def calculate_position_size(
    equity: float,
    entry_price: float,
    atr: Optional[float] = None,
    risk_pct: float = DEFAULT_RISK_PER_TRADE_PCT,
    max_position_pct: float = DEFAULT_MAX_POSITION_PCT,
    stop_mult: float = STOP_ATR_MULT,
    fallback_stop_pct: float = FALLBACK_STOP_PCT,
    absolute_max_shares: int = ABSOLUTE_MAX_SHARES,
    conviction: Optional[float] = None,
    cap_equity: Optional[float] = None,
    pm_max_shares: Optional[int] = None,
) -> int:
    """Volatility-adjusted position size scaled to account equity and conviction.

    Four caps applied (the tightest wins):
    1. Risk cap:     shares = (equity * risk_pct * conviction_mult) / stop_distance
    2. Position cap: shares = (cap_equity * max_position_pct) / entry_price
    3. Absolute cap: absolute_max_shares
    4. PM margin cap: pm_max_shares (from IB whatIfOrder, None = skip)

    ``equity`` may be leveraged (effective equity / buying power) for risk sizing.
    ``cap_equity`` should be unleveraged NLV so that max_position_pct is measured
    against real account value, matching the backtest configuration. If not
    supplied, defaults to ``equity`` for backward compatibility.

    ``pm_max_shares`` is the Portfolio Margin-derived maximum, computed via
    ``pm_margin.compute_pm_max_shares()``.  When provided it acts as a fourth
    cap so position sizing respects IB's actual margin requirements.  When
    None (default) this cap is skipped for backward compatibility.

    Conviction scaling (Druckenmiller: "go for the jugular on your best ideas"):
      High (>=0.8):  1.5x base risk
      Medium (0.5-0.8): 1.0x base risk
      Low (<0.5): 0.5x base risk

    The position cap and PM cap are NOT scaled by conviction to bound maximum exposure.
    """
    if equity <= 0 or entry_price <= 0:
        return MIN_SHARES

    if atr is not None and atr > 0:
        stop_dist = atr * stop_mult
    else:
        stop_dist = entry_price * fallback_stop_pct
    if stop_dist <= 0:
        return MIN_SHARES

    # Brandt 4-tier conviction curve — steeper reward for high-conviction signals
    conv_mult = brandt_conviction_mult(conviction)

    streak_mult = 1.0
    try:
        from streak_tracker import get_streak_risk_multiplier
        streak_mult = get_streak_risk_multiplier()
    except ImportError:
        pass

    vol_mult = 1.0
    try:
        from pathlib import Path
        from risk_config import compute_vol_scale
        from paths import TRADING_DIR
        vol_mult = compute_vol_scale(TRADING_DIR)
    except ImportError:
        pass

    risk_amount = equity * risk_pct * conv_mult * streak_mult * vol_mult
    shares_from_risk = int(math.floor(risk_amount / stop_dist))

    _cap_eq = cap_equity if cap_equity is not None and cap_equity > 0 else equity
    max_notional = _cap_eq * max_position_pct
    shares_from_cap = int(math.floor(max_notional / entry_price))

    candidates = [shares_from_risk, shares_from_cap, absolute_max_shares]
    if pm_max_shares is not None and pm_max_shares >= 0:
        candidates.append(pm_max_shares)

    shares = min(candidates)

    if shares > 0:
        pm_label = f", pm_cap={pm_max_shares}" if pm_max_shares is not None else ""
        logger.debug(
            "Position size: equity=$%s, cap_equity=$%s, price=$%.2f, atr=%s, conviction=%.2f (%s/%.1fx) "
            "→ risk=%d, cap=%d%s → final=%d shares ($%s notional)",
            f"{equity:,.0f}", f"{_cap_eq:,.0f}", entry_price, f"{atr:.2f}" if atr else "N/A",
            conviction if conviction is not None else 0.0, tier, conv_mult,
            shares_from_risk, shares_from_cap, pm_label, shares, f"{shares * entry_price:,.0f}",
        )

    return max(MIN_SHARES, shares)
