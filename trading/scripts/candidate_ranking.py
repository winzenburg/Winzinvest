"""
Candidate ranking by conviction score.

For shorts: lower RS + more negative momentum + lower structure = stronger conviction.
For longs: higher RS + more positive momentum = stronger conviction.
Scores are normalized to [0, 1] where 1 = highest conviction.

Conviction is boosted by:
  - MTF alignment (multi-timeframe confirmation)
  - Earnings catalyst (post-earnings drift)
  - Sector rotation (overweight top-RS sectors)
  - Shapiro sentiment overlay: put/call ratio correction (fades crowd extremes)
  - Fröhlich profit-factor overlay: sectors/regimes with strong historical PF get a boost

Weights and minimum conviction thresholds are loaded from adaptive_config.json
when available, falling back to hardcoded defaults.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_DEFAULT_WEIGHTS: Dict[str, float] = {"rs": 0.40, "momentum": 0.35, "structure": 0.25}

# ---------------------------------------------------------------------------
# Shapiro put/call sentiment overlay
# ---------------------------------------------------------------------------
_PC_CACHE: Dict[str, Any] = {}   # date → {"pc_5d": float, "long_adj": float, "short_adj": float}


_PF_CACHE: Dict[str, Any] = {}   # date → {(sector, regime): pf_adj}


def _fetch_profit_factor_adjustment(sector: Optional[str], regime: Optional[str]) -> float:
    """Return a conviction adjustment based on historical profit factor for this sector/regime.

    Lukas Fröhlich (Next Generation): size into setups with historically proven
    profit factors.  A sector × regime combination with PF ≥ 2.5 gets a +0.04 boost;
    with PF ≤ 0.8 (more losers than winners in value) gets a -0.04 penalty.

    The profit factor is computed from closed trades in trades.db grouped by
    strategy/sector × regime.  Results are cached once per day.
    """
    import datetime as _dt

    today = _dt.date.today().isoformat()
    cache_key = (str(sector or ""), str(regime or ""))

    if _PF_CACHE.get("date") == today and cache_key in _PF_CACHE:
        return float(_PF_CACHE[cache_key])

    adj = 0.0
    try:
        import sqlite3
        from pathlib import Path as _Path
        _tdir = _Path(__file__).parent.parent
        db_path = _tdir / "logs" / "trades.db"
        if not db_path.exists():
            _PF_CACHE["date"] = today
            _PF_CACHE[cache_key] = adj
            return adj

        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT entry_price, exit_price, side, strategy
                FROM trades
                WHERE exit_price IS NOT NULL
                  AND entry_price IS NOT NULL
                  AND entry_price > 0
                  AND exit_price > 0
                  AND strategy IS NOT NULL
                """
            ).fetchall()

        # Compute profit factor for trades from this sector's strategies
        # (proxy: look for strategy names containing the sector name)
        sector_lower = (sector or "").lower()
        gross_profit = 0.0
        gross_loss = 0.0
        for entry_price, exit_price, side, strategy in rows:
            if sector_lower and sector_lower not in (strategy or "").lower():
                continue
            ep, xp = float(entry_price), float(exit_price)
            if side and side.upper() in ("BUY", "LONG"):
                pnl = xp - ep
            else:
                pnl = ep - xp
            if pnl > 0:
                gross_profit += pnl
            else:
                gross_loss += abs(pnl)

        if gross_loss > 0:
            pf = gross_profit / gross_loss
            if pf >= 2.5:
                adj = +0.04
            elif pf <= 0.8:
                adj = -0.04
            logger.debug(
                "Fröhlich PF overlay: sector='%s' regime='%s' PF=%.2f → adj=%+.2f",
                sector, regime, pf, adj,
            )
    except Exception as exc:
        logger.debug("Fröhlich PF overlay failed (non-fatal): %s", exc)

    if _PF_CACHE.get("date") != today:
        _PF_CACHE.clear()
        _PF_CACHE["date"] = today
    _PF_CACHE[cache_key] = adj
    return adj


def _fetch_put_call_adjustment() -> tuple[float, float]:
    """Return (long_adj, short_adj) conviction multipliers from the CBOE equity P/C ratio.

    Jason Shapiro (Unknown Market Wizards): fade the crowd at sentiment extremes.
    - High P/C (≥ 0.90) = crowd is fearful → contrarian LONG boost (market likely to bounce)
    - Low P/C  (≤ 0.60) = crowd is complacent → contrarian SHORT boost (market overextended)
    - Neutral zone (0.60–0.90): no adjustment

    Returns (long_adj, short_adj) where each is ±0.05 applied to base conviction.
    Cache is refreshed once per calendar day to avoid repeated yfinance calls.
    """
    today = __import__("datetime").date.today().isoformat()
    if _PC_CACHE.get("date") == today and "long_adj" in _PC_CACHE:
        return float(_PC_CACHE["long_adj"]), float(_PC_CACHE["short_adj"])

    long_adj, short_adj = 0.0, 0.0
    try:
        import yfinance as yf
        import pandas as pd

        def _extract_close(df: pd.DataFrame) -> pd.Series:
            if isinstance(df.columns, pd.MultiIndex):
                df = df.copy()
                df.columns = df.columns.get_level_values(0)
            col = df["Close"] if "Close" in df.columns else df.iloc[:, 3]
            if isinstance(col, pd.DataFrame):
                col = col.iloc[:, 0]
            return col.dropna()

        pc_col: pd.Series = pd.Series(dtype=float)
        pc_source = "^PCCE"

        # Primary: native CBOE ticker
        pcce_df = yf.download("^PCCE", period="10d", progress=False)
        if not pcce_df.empty:
            pc_col = _extract_close(pcce_df)

        # Fallback: VIX-derived P/C proxy (^PCCE removed from Yahoo Finance)
        # Mapping: VIX=12→0.58 (complacency), VIX=20→0.77 (neutral), VIX=30→1.01 (fear)
        if pc_col.empty:
            vix_df = yf.download("^VIX", period="10d", progress=False)
            if not vix_df.empty:
                vix_col = _extract_close(vix_df)
                if not vix_col.empty:
                    pc_col = ((vix_col - 15.0) / 25.0 * 0.6 + 0.65).clip(0.40, 1.50)
                    pc_source = "VIX-proxy"

        if len(pc_col) >= 3:
            pc = float(pc_col.tail(5).mean())
            if pc >= 0.90:
                long_adj = +0.05
                short_adj = -0.05
            elif pc <= 0.60:
                long_adj = -0.05
                short_adj = +0.05
            logger.debug(
                "Shapiro P/C overlay: %s 5d avg=%.2f → long_adj=%+.2f short_adj=%+.2f",
                pc_source, pc, long_adj, short_adj,
            )
    except Exception as exc:
        logger.debug("Shapiro P/C fetch failed (non-fatal): %s", exc)

    _PC_CACHE.update({"date": today, "long_adj": long_adj, "short_adj": short_adj})
    return long_adj, short_adj


def _load_weights() -> Dict[str, float]:
    try:
        from adaptive_config_loader import get_adaptive_dict
        w = get_adaptive_dict("ranking_weights", _DEFAULT_WEIGHTS)
        if all(k in w for k in ("rs", "momentum", "structure")):
            return w
    except ImportError:
        pass
    return dict(_DEFAULT_WEIGHTS)


def _load_min_conviction() -> Tuple[float, float]:
    """Return (min_conviction_short, min_conviction_long) with regime-based scaling.

    Michael Platt insight: conviction thresholds should be RAISED in uncertain
    regimes (CHOPPY, MIXED) and relaxed in high-confidence regimes.  In a
    CHOPPY market you want fewer, higher-quality trades; in a STRONG_UPTREND
    almost any long with momentum will work.

    Regime multipliers:
      STRONG_UPTREND  : longs 0.85× (easier — momentum helps), shorts 1.15× (harder)
      MIXED           : both 1.10× (slightly harder — be selective)
      CHOPPY          : both 1.25× (meaningfully harder — quality only)
      STRONG_DOWNTREND: shorts 0.85× (easier), longs 1.20× (very hard to go long)
      UNFAVORABLE     : both 1.40× (almost nothing qualifies — preservation mode)
    """
    try:
        from adaptive_config_loader import get_adaptive_float
        base_short = get_adaptive_float("min_conviction_short", 0.35)
        base_long = get_adaptive_float("min_conviction_long", 0.40)
    except ImportError:
        base_short, base_long = 0.35, 0.40

    try:
        from regime_detector import detect_market_regime
        regime = detect_market_regime()
        _SHORT_MULTS = {
            "STRONG_UPTREND": 1.15,
            "MIXED": 1.10,
            "CHOPPY": 1.25,
            "STRONG_DOWNTREND": 0.85,
            "UNFAVORABLE": 1.40,
        }
        _LONG_MULTS = {
            "STRONG_UPTREND": 0.85,
            "MIXED": 1.10,
            "CHOPPY": 1.25,
            "STRONG_DOWNTREND": 1.20,
            "UNFAVORABLE": 1.40,
        }
        short_mult = _SHORT_MULTS.get(regime, 1.0)
        long_mult = _LONG_MULTS.get(regime, 1.0)
        adj_short = min(0.65, base_short * short_mult)
        adj_long = min(0.65, base_long * long_mult)
        if short_mult != 1.0 or long_mult != 1.0:
            logger.debug(
                "Conviction floors adjusted for regime %s: short %.2f→%.2f (%.0f%%), "
                "long %.2f→%.2f (%.0f%%)",
                regime, base_short, adj_short, short_mult * 100,
                base_long, adj_long, long_mult * 100,
            )
        return adj_short, adj_long
    except Exception:
        return base_short, base_long


def short_conviction(candidate: Dict[str, Any]) -> float:
    """Conviction score for a short candidate (higher = better short).

    Base conviction from RS weakness + negative momentum + structural breakdown,
    then scaled by MTF alignment for shorts and Shapiro put/call sentiment overlay.
    """
    w = _load_weights()
    score = float(candidate.get("score") or candidate.get("rs_pct") or 0.5)
    rs_weakness = max(0.0, min(1.0, 1.0 - score))

    momentum = float(candidate.get("momentum") or candidate.get("recent_return") or 0.0)
    mom_strength = max(0.0, min(1.0, abs(min(0.0, momentum)) / 0.10))

    structure = float(candidate.get("structure_quality") or 0.5)
    struct_weakness = max(0.0, min(1.0, 1.0 - structure))

    base = (rs_weakness * w["rs"]) + (mom_strength * w["momentum"]) + (struct_weakness * w["structure"])

    mtf = float(candidate.get("mtf_score") or 0.5)
    if mtf >= 0.7:
        base *= 1.15
    elif mtf < 0.3:
        base *= 0.85

    # Shapiro sentiment overlay: adjust for crowd extremes
    _, short_adj = _fetch_put_call_adjustment()
    base += short_adj

    # Fröhlich profit-factor overlay: boost sectors with proven historical PF
    sector = candidate.get("sector")
    regime = candidate.get("regime")
    base += _fetch_profit_factor_adjustment(sector, regime)

    return max(0.0, min(1.0, base))


def long_conviction(candidate: Dict[str, Any]) -> float:
    """Conviction score for a long candidate (higher = better long).

    Base conviction from RS + momentum is then scaled by:
      - MTF alignment:      score >= 0.7 → +15%, score < 0.3 → -15%
      - Earnings catalyst:  boost added directly (0-0.25)
      - Sector rotation:    top sector → +10%, bottom → -10%
    """
    w = _load_weights()
    rs = float(candidate.get("rs_pct") or candidate.get("score") or 0.5)
    rs_strength = max(0.0, min(1.0, rs))

    momentum = float(candidate.get("momentum") or candidate.get("recent_return") or 0.0)
    mom_strength = max(0.0, min(1.0, max(0.0, momentum) / 0.10))

    rs_w = w["rs"] / (w["rs"] + w["momentum"]) if (w["rs"] + w["momentum"]) > 0 else 0.5
    mom_w = 1.0 - rs_w
    base = (rs_strength * rs_w) + (mom_strength * mom_w)

    mtf = float(candidate.get("mtf_score") or 0.5)
    if mtf >= 0.7:
        base *= 1.15
    elif mtf < 0.3:
        base *= 0.85

    earnings_boost = float(candidate.get("earnings_boost") or 0.0)
    base += earnings_boost

    sector_mult = float(candidate.get("sector_multiplier") or 1.0)
    if sector_mult > 1.0:
        base *= 1.10
    elif sector_mult < 1.0:
        base *= 0.90

    # Shapiro sentiment overlay: adjust for crowd extremes
    long_adj, _ = _fetch_put_call_adjustment()
    base += long_adj

    # Fröhlich profit-factor overlay: boost sectors with proven historical PF
    sector = candidate.get("sector")
    regime = candidate.get("regime")
    base += _fetch_profit_factor_adjustment(sector, regime)

    return max(0.0, min(1.0, base))


def rank_short_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort short candidates by conviction (highest first), filtering below min threshold."""
    min_conv, _ = _load_min_conviction()
    filtered = [c for c in candidates if short_conviction(c) >= min_conv]
    return sorted(filtered, key=short_conviction, reverse=True)


def rank_long_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort long candidates by conviction (highest first), filtering below min threshold."""
    _, min_conv = _load_min_conviction()
    filtered = [c for c in candidates if long_conviction(c) >= min_conv]
    return sorted(filtered, key=long_conviction, reverse=True)
