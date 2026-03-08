"""
Candidate ranking by conviction score.

For shorts: lower RS + more negative momentum + lower structure = stronger conviction.
For longs: higher RS + more positive momentum = stronger conviction.
Scores are normalized to [0, 1] where 1 = highest conviction.

Weights and minimum conviction thresholds are loaded from adaptive_config.json
when available, falling back to hardcoded defaults.
"""

from typing import Any, Dict, List, Tuple

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
    """
    Conviction score for a short candidate (higher = better short).
    Components:
    - RS weakness: (1 - score) where score is rs_pct in [0, 1]
    - Momentum: abs(momentum) clamped, where more negative = better
    - Structure: (1 - structure_quality) if present
    """
    w = _load_weights()
    score = float(candidate.get("score") or candidate.get("rs_pct") or 0.5)
    rs_weakness = max(0.0, min(1.0, 1.0 - score))

    momentum = float(candidate.get("momentum") or candidate.get("recent_return") or 0.0)
    mom_strength = max(0.0, min(1.0, abs(min(0.0, momentum)) / 0.10))

    structure = float(candidate.get("structure_quality") or 0.5)
    struct_weakness = max(0.0, min(1.0, 1.0 - structure))

    return (rs_weakness * w["rs"]) + (mom_strength * w["momentum"]) + (struct_weakness * w["structure"])


def long_conviction(candidate: Dict[str, Any]) -> float:
    """
    Conviction score for a long candidate (higher = better long).
    """
    w = _load_weights()
    rs = float(candidate.get("rs_pct") or candidate.get("score") or 0.5)
    rs_strength = max(0.0, min(1.0, rs))

    momentum = float(candidate.get("momentum") or candidate.get("recent_return") or 0.0)
    mom_strength = max(0.0, min(1.0, max(0.0, momentum) / 0.10))

    rs_w = w["rs"] / (w["rs"] + w["momentum"]) if (w["rs"] + w["momentum"]) > 0 else 0.5
    mom_w = 1.0 - rs_w
    return (rs_strength * rs_w) + (mom_strength * mom_w)


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
