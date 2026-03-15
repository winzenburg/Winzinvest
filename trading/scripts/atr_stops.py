"""
ATR-based stop/take-profit calculator for swing trades.

Uses 14-period ATR to set stop and TP distances proportional to each stock's
actual volatility, replacing fixed-percentage stops that cause premature exits
on volatile names and under-protection on calm ones.

Defaults: stop = 1.5x ATR, TP = 2.5x ATR. Falls back to fixed percentages
when ATR data is unavailable.
"""

from typing import Optional, Tuple
import math
import logging

logger = logging.getLogger(__name__)

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


def fetch_atr(symbol: str, ib: Optional[object] = None) -> Optional[float]:
    """
    Fetch the 14-period daily ATR for symbol.
    Tries yfinance first to avoid IB Historical Market Data limits (Error 162);
    falls back to IB if connected and yfinance fails.
    Returns None on failure.
    """
    atr = _atr_from_yfinance(symbol)
    if atr is not None and atr > 0:
        return atr
    if ib is not None:
        atr = _atr_from_ib(symbol, ib)
        if atr is not None and atr > 0:
            return atr
    return None


def _atr_from_ib(symbol: str, ib: object) -> Optional[float]:
    try:
        from ib_insync import Stock, util
    except ImportError:
        return None
    if not getattr(ib, "isConnected", lambda: False)():
        return None
    try:
        contract = Stock(symbol, "SMART", "USD")
        bars = ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr="1 M",
            barSizeSetting="1 day",
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
        )
        if not bars or len(bars) < 15:
            return None
        import pandas as pd
        df = util.df(bars)
        col_map = {c.lower(): c for c in df.columns}
        h = df[col_map.get("high", "High")]
        l = df[col_map.get("low", "Low")]
        c = df[col_map.get("close", "Close")]
        import numpy as np
        cp = c.shift(1)
        tr = np.maximum(h - l, np.maximum((h - cp).abs(), (l - cp).abs()))
        return float(tr.rolling(14, min_periods=1).mean().iloc[-1])
    except Exception:
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
        h = df["High"]
        l = df["Low"]
        c = df["Close"]
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


TRAILING_ATR_MULT = 3.0


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
) -> int:
    """Volatility-adjusted position size scaled to account equity and conviction.

    Three caps applied (the tightest wins):
    1. Risk cap:     shares = (equity * risk_pct * conviction_mult) / stop_distance
    2. Position cap: shares = (cap_equity * max_position_pct) / entry_price
    3. Absolute cap: absolute_max_shares

    ``equity`` may be leveraged (effective equity / buying power) for risk sizing.
    ``cap_equity`` should be unleveraged NLV so that max_position_pct is measured
    against real account value, matching the backtest configuration. If not
    supplied, defaults to ``equity`` for backward compatibility.

    Conviction scaling (Druckenmiller: "go for the jugular on your best ideas"):
      High (>=0.8):  1.5x base risk
      Medium (0.5-0.8): 1.0x base risk
      Low (<0.5): 0.5x base risk

    The position cap is NOT scaled by conviction to bound maximum exposure.
    """
    if equity <= 0 or entry_price <= 0:
        return MIN_SHARES

    if atr is not None and atr > 0:
        stop_dist = atr * stop_mult
    else:
        stop_dist = entry_price * fallback_stop_pct
    if stop_dist <= 0:
        return MIN_SHARES

    tier = conviction_tier(conviction)
    conv_mult = CONVICTION_MULTIPLIERS.get(tier, 1.0)

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

    shares = min(shares_from_risk, shares_from_cap, absolute_max_shares)

    if shares > 0:
        logger.debug(
            "Position size: equity=$%s, cap_equity=$%s, price=$%.2f, atr=%s, conviction=%.2f (%s/%.1fx) "
            "→ risk=%d, cap=%d → final=%d shares ($%s notional)",
            f"{equity:,.0f}", f"{_cap_eq:,.0f}", entry_price, f"{atr:.2f}" if atr else "N/A",
            conviction if conviction is not None else 0.0, tier, conv_mult,
            shares_from_risk, shares_from_cap, shares, f"{shares * entry_price:,.0f}",
        )

    return max(MIN_SHARES, shares)
