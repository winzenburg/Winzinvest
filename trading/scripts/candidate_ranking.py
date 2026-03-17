"""
Candidate ranking by conviction score.

For shorts: lower RS + more negative momentum + lower structure = stronger conviction.
For longs: higher RS + more positive momentum = stronger conviction.
Scores are normalized to [0, 1] where 1 = highest conviction.

Conviction is boosted by:
  - MTF alignment (multi-timeframe confirmation)
  - Earnings catalyst (post-earnings drift)
  - Sector rotation (overweight top-RS sectors)

Weights and minimum conviction thresholds are loaded from adaptive_config.json
when available, falling back to hardcoded defaults.
"""

import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

_DEFAULT_WEIGHTS: Dict[str, float] = {"rs": 0.40, "momentum": 0.35, "structure": 0.25}


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
    """Return (min_conviction_short, min_conviction_long)."""
    try:
        from adaptive_config_loader import get_adaptive_float
        return (
            get_adaptive_float("min_conviction_short", 0.0),
            get_adaptive_float("min_conviction_long", 0.0),
        )
    except ImportError:
        return 0.0, 0.0


def short_conviction(candidate: Dict[str, Any]) -> float:
    """Conviction score for a short candidate (higher = better short).

    Base conviction from RS weakness + negative momentum + structural breakdown,
    then scaled by MTF alignment for shorts.
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
