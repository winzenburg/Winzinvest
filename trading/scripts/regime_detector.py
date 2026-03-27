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


def _compute_leading_stress_score() -> float:
    """O'Shea leading indicator composite: stress score 0.0 (none) → 1.0 (severe).

    Uses three forward-looking signals that historically lead equity regime changes
    by 2–4 weeks:
      1. VIX term structure inversion — when short-dated vol > long-dated vol,
         the market expects near-term stress. Normal contango has VIX9D < VIX30.
      2. Credit spread proxy (HYG/IEF 30-day return) — high-yield bonds lead
         equities into stress.  A deteriorating HY/IG spread signals risk-off.
      3. S&P 500 breadth (% of 20 large-cap proxies above 50-day MA) — a
         narrow, top-heavy rally (few stocks holding up the index) is fragile.

    Returns the composite stress score.  Scores >= 0.55 indicate elevated stress;
    >= 0.75 indicates high probability of regime deterioration within 2 weeks.
    """
    try:
        import yfinance as yf
        import numpy as np
        import pandas as _pd
    except ImportError:
        return 0.0

    stress_components = []

    # ── 1. VIX term structure ──────────────────────────────────────────────────
    try:
        vix9d = yf.download("^VIX9D", period="5d", progress=False)
        vix30 = yf.download("^VIX", period="5d", progress=False)
        if not vix9d.empty and not vix30.empty:
            def _last_close(df: "_pd.DataFrame") -> float:
                if isinstance(df.columns, _pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                c = df["Close"] if "Close" in df.columns else df.iloc[:, 3]
                if isinstance(c, _pd.DataFrame):
                    c = c.iloc[:, 0]
                return float(c.dropna().iloc[-1])
            v9 = _last_close(vix9d)
            v30 = _last_close(vix30)
            # Spread: positive = normal contango; negative = inverted (stressed)
            spread = (v30 - v9) / v30 if v30 > 0 else 0
            if spread < -0.05:       # deeply inverted
                ts_stress = 1.0
            elif spread < 0.0:       # mildly inverted
                ts_stress = 0.7
            elif spread < 0.05:      # very flat contango
                ts_stress = 0.4
            else:
                ts_stress = 0.0      # healthy contango → no stress
            stress_components.append(("vix_term_structure", ts_stress, f"VIX9D={v9:.1f}/VIX30={v30:.1f} spread={spread:.3f}"))
    except Exception:
        pass

    # ── 2. Credit spread proxy (HYG/IEF 30-day return ratio) ─────────────────
    try:
        hyg = yf.download("HYG", period="45d", progress=False)
        ief = yf.download("IEF", period="45d", progress=False)
        if not hyg.empty and not ief.empty:
            def _pct_change_30d(df: "_pd.DataFrame") -> float:
                if isinstance(df.columns, _pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                c = df["Close"] if "Close" in df.columns else df.iloc[:, 3]
                if isinstance(c, _pd.DataFrame):
                    c = c.iloc[:, 0]
                c = c.dropna()
                if len(c) < 20:
                    return 0.0
                return float((c.iloc[-1] / c.iloc[-20] - 1))
            hyg_ret = _pct_change_30d(hyg)
            ief_ret = _pct_change_30d(ief)
            # If HYG is falling while IEF is flat/rising → risk-off flight to quality
            relative = hyg_ret - ief_ret
            if relative < -0.04:     # HY underperforming bonds by 4%+
                cs_stress = 1.0
            elif relative < -0.02:
                cs_stress = 0.6
            elif relative < 0.0:
                cs_stress = 0.3
            else:
                cs_stress = 0.0
            stress_components.append(("credit_spread", cs_stress, f"HYG_30d={hyg_ret:.3f} IEF_30d={ief_ret:.3f} rel={relative:.3f}"))
    except Exception:
        pass

    # ── 3. Market breadth (% of large-caps above 50-day MA) ───────────────────
    # Proxy: check 20 large-cap SPY holdings that yfinance handles reliably
    breadth_syms = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "BRK-B",
                    "JPM", "LLY", "V", "UNH", "XOM", "MA", "PG", "JNJ",
                    "HD", "AVGO", "MRK", "CVX", "PEP"]
    try:
        above_50 = 0
        total = 0
        for sym in breadth_syms:
            try:
                d = yf.download(sym, period="70d", progress=False)
                if d is None or d.empty or len(d) < 50:
                    continue
                if isinstance(d.columns, _pd.MultiIndex):
                    d.columns = d.columns.get_level_values(0)
                c = d["Close"] if "Close" in d.columns else d.iloc[:, 3]
                if isinstance(c, _pd.DataFrame):
                    c = c.iloc[:, 0]
                c = c.dropna()
                if len(c) >= 50 and float(c.iloc[-1]) > float(c.rolling(50).mean().iloc[-1]):
                    above_50 += 1
                total += 1
            except Exception:
                pass
        if total >= 10:
            breadth_pct = above_50 / total
            if breadth_pct < 0.35:       # fewer than 35% above 50-day → deteriorating breadth
                breadth_stress = 1.0
            elif breadth_pct < 0.50:
                breadth_stress = 0.6
            elif breadth_pct < 0.65:
                breadth_stress = 0.3
            else:
                breadth_stress = 0.0
            stress_components.append(("breadth", breadth_stress, f"{above_50}/{total}={breadth_pct:.0%} above 50-day"))
    except Exception:
        pass

    # ── 4. Put/call ratio sentiment (Jason Shapiro: fade the crowd) ──────────
    # Primary: ^PCCE (CBOE equity put/call). Fallback: VIX-derived proxy since
    # Yahoo Finance removed ^PCCE.  Mapping: VIX=12→0.58, VIX=20→0.77, VIX=30→1.01.
    # High P/C → panic → contrarian bullish (low stress). Low P/C → complacency → elevated stress.
    try:
        def _series_last_close(df: "_pd.DataFrame") -> "_pd.Series":
            if isinstance(df.columns, _pd.MultiIndex):
                df = df.copy()
                df.columns = df.columns.get_level_values(0)
            col = df["Close"] if "Close" in df.columns else df.iloc[:, 3]
            if isinstance(col, _pd.DataFrame):
                col = col.iloc[:, 0]
            return col.dropna()

        pc_col: "_pd.Series" = _pd.Series(dtype=float)
        pc_source = "^PCCE"

        # Try native CBOE ticker first
        pcce_df = yf.download("^PCCE", period="10d", progress=False)
        if not pcce_df.empty:
            pc_col = _series_last_close(pcce_df)

        # Fallback: derive P/C proxy from VIX (^PCCE removed from Yahoo Finance)
        if pc_col.empty:
            vix_df = yf.download("^VIX", period="10d", progress=False)
            if not vix_df.empty:
                vix_col = _series_last_close(vix_df)
                if not vix_col.empty:
                    pc_col = ((vix_col - 15.0) / 25.0 * 0.6 + 0.65).clip(0.40, 1.50)
                    pc_source = "VIX-proxy"

        if len(pc_col) >= 3:
            pc_5d = float(pc_col.tail(5).mean())
            # Complacency (low P/C) → higher stress for longs; panic (high) → lower
            if pc_5d < 0.50:
                pc_stress = 1.0
            elif pc_5d < 0.60:
                pc_stress = 0.7
            elif pc_5d < 0.70:
                pc_stress = 0.4
            elif pc_5d < 0.90:
                pc_stress = 0.1
            elif pc_5d < 1.10:
                pc_stress = 0.0
            else:
                pc_stress = 0.0
            stress_components.append((
                "put_call_ratio",
                pc_stress,
                f"{pc_source} 5d avg={pc_5d:.2f} (low=complacency/stress, high=fear/bullish)",
            ))
    except Exception:
        pass

    if not stress_components:
        return 0.0

    composite = sum(s for _, s, _ in stress_components) / len(stress_components)
    logger.info(
        "Leading stress score: %.2f | %s",
        composite,
        " | ".join(f"{k}={s:.2f} ({note})" for k, s, note in stress_components),
    )
    return composite


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


def _read_cached_regime() -> Optional[RegimeType]:
    """Read the last persisted regime from regime_context.json.

    Returns None if the file is missing, unreadable, or stale (>24h).
    """
    try:
        if not _REGIME_CONTEXT_FILE.exists():
            return None
        raw = json.loads(_REGIME_CONTEXT_FILE.read_text())
        cached = raw.get("regime")
        if cached not in ("STRONG_DOWNTREND", "MIXED", "STRONG_UPTREND", "CHOPPY", "UNFAVORABLE"):
            return None
        updated = raw.get("updated_at", "")
        if updated:
            age_hours = (datetime.now() - datetime.fromisoformat(updated)).total_seconds() / 3600
            if age_hours > 24:
                logger.warning("Cached regime is %.0fh old — treating as stale", age_hours)
                return None
        return cached
    except Exception:
        return None


def detect_market_regime(use_leading_indicators: bool = True) -> RegimeType:
    """Classify current regime from SPY price vs 200 SMA and VIX level.

    Falls back to the last cached regime (from regime_context.json) when
    yfinance is unavailable, then to CHOPPY as a last resort.  This prevents
    aggressive trading during outages that coincide with market stress.

    O'Shea leading indicator overlay (enabled by default):
    After determining the base regime from lagging indicators (SPY/SMA/VIX),
    a composite stress score is computed from three forward-looking signals:
      - VIX term structure (VIX9D vs VIX30) — stress shows up in short-dated vol first
      - Credit spread proxy (HYG vs IEF 30-day return) — HY bonds lead equities by weeks
      - Market breadth (% of large-cap proxies above 50-day MA) — narrow rallies fail

    If the stress score signals imminent deterioration, the base regime is downgraded
    BEFORE the lagging signals confirm — giving 1–2 weeks of early warning.

    Downgrade thresholds:
      stress >= 0.75 AND base is CHOPPY/MIXED  → STRONG_DOWNTREND
      stress >= 0.60 AND base is STRONG_UPTREND → MIXED (reduce long allocation)
      stress >= 0.85                            → UNFAVORABLE (capital preservation)

    Set use_leading_indicators=False to use the legacy lagging-only logic.
    """
    regime = _fetch_regime_from_yfinance()
    if regime is None:
        cached = _read_cached_regime()
        if cached is not None:
            logger.warning("Regime detection failed (yfinance) — using cached regime: %s", cached)
            return cached
        logger.warning("Regime detection failed and no cached state — defaulting to CHOPPY")
        return "CHOPPY"

    if not use_leading_indicators:
        return regime

    # O'Shea overlay: compute leading stress and potentially downgrade the base regime
    try:
        stress = _compute_leading_stress_score()
    except Exception as exc:
        logger.debug("Leading stress computation failed (non-fatal): %s", exc)
        return regime

    original = regime
    if stress >= 0.85:
        regime = "UNFAVORABLE"
    elif stress >= 0.75 and regime in ("CHOPPY", "MIXED", "STRONG_DOWNTREND"):
        regime = "STRONG_DOWNTREND"
    elif stress >= 0.60 and regime == "STRONG_UPTREND":
        regime = "MIXED"
    elif stress >= 0.60 and regime == "CHOPPY":
        regime = "MIXED"

    if regime != original:
        logger.warning(
            "O'Shea leading indicator DOWNGRADE: %s → %s (stress_score=%.2f) "
            "— leading indicators signaling deterioration ahead of lagging confirmation",
            original, regime, stress,
        )
        try:
            from notifications import send_telegram
            send_telegram(
                f"⚠️ *Regime Downgrade (Leading Indicators)*\n\n"
                f"Base (lagging): {original}\n"
                f"Adjusted: *{regime}*\n"
                f"Stress score: {stress:.2f}\n\n"
                f"Signals: VIX term structure, credit spreads, market breadth"
            )
        except Exception:
            pass

    return regime


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


_L1_VALID = frozenset({"STRONG_UPTREND", "STRONG_DOWNTREND", "CHOPPY", "MIXED", "UNFAVORABLE"})


def persist_regime_to_context(regime: RegimeType) -> None:
    """Write current regime (and updated_at) to logs/regime_context.json, preserving existing note and catalysts.

    SAFETY: rejects any value that is not a valid Layer-1 execution regime label.
    Layer-2 macro band labels (NEUTRAL, RISK_ON, TIGHTENING, DEFENSIVE) must NEVER
    be written here — they belong in regime_state.json only.
    """
    # Guard: never allow a non-L1 label to pollute regime_context.json.
    # This can happen if the caller passes result.get("regime") from regime_monitor
    # (which uses the macro-band vocabulary) instead of detect_market_regime().
    if str(regime).upper() not in _L1_VALID:
        raise ValueError(
            f"persist_regime_to_context received invalid Layer-1 label {regime!r}. "
            f"Valid values: {sorted(_L1_VALID)}. "
            "Did you accidentally pass a macro-band label? Use detect_market_regime() instead."
        )
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
