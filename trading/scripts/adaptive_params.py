"""
Adaptive Parameter Engine — read strategy scorecard and auto-adjust
strategy parameters within guardrails.

All changes are bounded by min/max guardrails and rate-limited to a max
percentage change per cycle. Writes adaptive_config.json and appends to
adaptation_log.jsonl.

Run daily after the analytics engine:
    python adaptive_params.py
"""

import json
import logging
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from strategy_analytics import MIN_TRADES_FOR_SCORECARD

logger = logging.getLogger(__name__)

from paths import TRADING_DIR
SCORECARD_PATH = TRADING_DIR / "analytics" / "strategy_scorecard.json"
ADAPTIVE_CONFIG_PATH = TRADING_DIR / "adaptive_config.json"
ADAPTATION_LOG_PATH = TRADING_DIR / "logs" / "adaptation_log.jsonl"

# ---------------------------------------------------------------------------
# Guardrails
# ---------------------------------------------------------------------------
GUARDRAILS: Dict[str, Dict[str, float]] = {
    "stop_atr_mult":       {"min": 1.0,   "max": 3.0,  "max_change_pct": 0.10},
    "tp_atr_mult":         {"min": 1.5,   "max": 4.0,  "max_change_pct": 0.10},
    "risk_per_trade_pct":  {"min": 0.005, "max": 0.025, "max_change_pct": 0.10},
    "ranking_weight_rs":        {"min": 0.10, "max": 0.60, "max_change_pct": 0.10},
    "ranking_weight_momentum":  {"min": 0.10, "max": 0.60, "max_change_pct": 0.10},
    "ranking_weight_structure": {"min": 0.10, "max": 0.60, "max_change_pct": 0.10},
    "min_conviction_short": {"min": 0.0, "max": 0.50, "max_change_abs": 0.05},
    "min_conviction_long":  {"min": 0.0, "max": 0.50, "max_change_abs": 0.05},
}

# Regime allocation guardrails (per side per regime)
REGIME_ALLOC_MIN = 0.20
REGIME_ALLOC_MAX = 0.80
REGIME_ALLOC_MAX_CHANGE = 0.10

# Baseline defaults (before any adaptation)
DEFAULTS: Dict[str, Any] = {
    "stop_atr_mult": 1.5,
    "tp_atr_mult": 2.5,
    "risk_per_trade_pct": 0.01,
    "ranking_weights": {"rs": 0.40, "momentum": 0.35, "structure": 0.25},
    "regime_allocations": {
        "STRONG_DOWNTREND": {"shorts": 0.80, "longs": 0.20},
        "MIXED":            {"shorts": 0.60, "longs": 0.40},
        "STRONG_UPTREND":   {"shorts": 0.30, "longs": 0.70},
        "CHOPPY":           {"shorts": 0.50, "longs": 0.50},
    },
    "min_conviction_short": 0.0,
    "min_conviction_long": 0.0,
}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _rate_limit(current: float, proposed: float, max_change_pct: float) -> float:
    """Limit the move to ±max_change_pct of current value."""
    if current <= 0:
        return proposed
    max_delta = abs(current) * max_change_pct
    delta = proposed - current
    if abs(delta) > max_delta:
        delta = math.copysign(max_delta, delta)
    return current + delta


def _rate_limit_abs(current: float, proposed: float, max_change: float) -> float:
    delta = proposed - current
    if abs(delta) > max_change:
        delta = math.copysign(max_change, delta)
    return current + delta


def _load_scorecard() -> Optional[Dict[str, Any]]:
    if not SCORECARD_PATH.exists():
        return None
    try:
        return json.loads(SCORECARD_PATH.read_text())
    except (OSError, ValueError):
        return None


def _load_current_config() -> Dict[str, Any]:
    if ADAPTIVE_CONFIG_PATH.exists():
        try:
            data = json.loads(ADAPTIVE_CONFIG_PATH.read_text())
            if isinstance(data, dict) and "params" in data:
                return data
        except (OSError, ValueError):
            pass
    return {"generation": 0, "params": dict(DEFAULTS)}


# ---------------------------------------------------------------------------
# Adaptation Logic
# ---------------------------------------------------------------------------

def _adapt_stop_tp(
    scorecard: Dict[str, Any],
    current: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Adjust stop/TP multipliers based on MAE/MFE and stop-hit frequency."""
    changes: Dict[str, Any] = {}
    reasoning: Dict[str, str] = {}

    overall = scorecard.get("overall", {})
    stop_hit_pct = overall.get("stop_hit_pct", 0)
    avg_mae = overall.get("avg_mae", 0)
    avg_mfe = overall.get("avg_mfe", 0)

    cur_stop = current.get("stop_atr_mult", DEFAULTS["stop_atr_mult"])
    cur_tp = current.get("tp_atr_mult", DEFAULTS["tp_atr_mult"])

    g = GUARDRAILS["stop_atr_mult"]
    if stop_hit_pct > 0.60 and avg_mfe > avg_mae:
        proposed = cur_stop * 1.05
        reason = f"{stop_hit_pct:.0%} stop exits with positive MFE -> widen"
    elif stop_hit_pct < 0.25 and avg_mae < cur_stop * 0.5:
        proposed = cur_stop * 0.95
        reason = f"Only {stop_hit_pct:.0%} stop exits, low MAE -> tighten"
    else:
        proposed = cur_stop
        reason = "no change"
    new_stop = _clamp(_rate_limit(cur_stop, proposed, g["max_change_pct"]), g["min"], g["max"])
    changes["stop_atr_mult"] = round(new_stop, 3)
    reasoning["stop_atr_mult"] = f"{reason} ({cur_stop:.3f} -> {new_stop:.3f})"

    g = GUARDRAILS["tp_atr_mult"]
    by_exit = scorecard.get("by_exit_reason", {})
    tp_metrics = by_exit.get("TP_HIT", {})
    trail_metrics = by_exit.get("TRAIL_HIT", {})
    tp_count = tp_metrics.get("trade_count", 0)
    trail_count = trail_metrics.get("trade_count", 0)
    total_wins = tp_count + trail_count
    if total_wins > 0 and tp_count / total_wins > 0.70:
        proposed = cur_tp * 1.05
        reason = f"{tp_count}/{total_wins} wins hit TP -> extend target"
    elif total_wins > 0 and tp_count / total_wins < 0.30 and avg_mfe > 0:
        proposed = cur_tp * 0.95
        reason = f"Only {tp_count}/{total_wins} hit TP -> tighten target"
    else:
        proposed = cur_tp
        reason = "no change"
    new_tp = _clamp(_rate_limit(cur_tp, proposed, g["max_change_pct"]), g["min"], g["max"])
    changes["tp_atr_mult"] = round(new_tp, 3)
    reasoning["tp_atr_mult"] = f"{reason} ({cur_tp:.3f} -> {new_tp:.3f})"

    return changes, reasoning


def _adapt_risk_per_trade(
    scorecard: Dict[str, Any],
    current: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Scale risk per trade based on recent Sharpe / profit factor."""
    changes: Dict[str, Any] = {}
    reasoning: Dict[str, str] = {}

    overall = scorecard.get("overall", {})
    sharpe = overall.get("sharpe", 0)
    profit_factor = overall.get("profit_factor", 0)
    cur_risk = current.get("risk_per_trade_pct", DEFAULTS["risk_per_trade_pct"])
    g = GUARDRAILS["risk_per_trade_pct"]

    if sharpe > 1.5 and profit_factor > 2.0:
        proposed = cur_risk * 1.05
        reason = f"Strong Sharpe={sharpe:.2f} PF={profit_factor:.2f} -> increase risk"
    elif sharpe < 0.5 or profit_factor < 1.0:
        proposed = cur_risk * 0.95
        reason = f"Weak Sharpe={sharpe:.2f} PF={profit_factor:.2f} -> decrease risk"
    else:
        proposed = cur_risk
        reason = "no change"

    new_risk = _clamp(_rate_limit(cur_risk, proposed, g["max_change_pct"]), g["min"], g["max"])
    changes["risk_per_trade_pct"] = round(new_risk, 4)
    reasoning["risk_per_trade_pct"] = f"{reason} ({cur_risk:.4f} -> {new_risk:.4f})"
    return changes, reasoning


def _adapt_ranking_weights(
    scorecard: Dict[str, Any],
    current: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Adjust ranking component weights based on correlation with outcomes.

    Uses a simple heuristic: compare win rate in high vs low buckets for each
    implied dimension. True correlation requires per-trade component values
    which we approximate from conviction buckets and regime slices.
    """
    changes: Dict[str, Any] = {}
    reasoning: Dict[str, str] = {}

    cur_weights = current.get("ranking_weights", dict(DEFAULTS["ranking_weights"]))
    w_rs = cur_weights.get("rs", 0.40)
    w_mom = cur_weights.get("momentum", 0.35)
    w_struct = cur_weights.get("structure", 0.25)

    by_conviction = scorecard.get("by_conviction", {})
    high_wr = (by_conviction.get("high", {}).get("win_rate") or 0)
    low_wr = (by_conviction.get("low", {}).get("win_rate") or 0)

    if high_wr > low_wr + 0.10:
        w_rs *= 1.03
        w_mom *= 1.03
        reason_note = f"High conviction WR ({high_wr:.2f}) >> low ({low_wr:.2f}); boost RS+momentum"
    elif low_wr > high_wr + 0.10:
        w_struct *= 1.05
        reason_note = f"Low conviction WR ({low_wr:.2f}) > high ({high_wr:.2f}); boost structure"
    else:
        reason_note = "conviction buckets balanced; no change"

    total = w_rs + w_mom + w_struct
    if total > 0:
        w_rs /= total
        w_mom /= total
        w_struct /= total

    g_rs = GUARDRAILS["ranking_weight_rs"]
    g_mom = GUARDRAILS["ranking_weight_momentum"]
    g_struct = GUARDRAILS["ranking_weight_structure"]
    w_rs = _clamp(w_rs, g_rs["min"], g_rs["max"])
    w_mom = _clamp(w_mom, g_mom["min"], g_mom["max"])
    w_struct = _clamp(w_struct, g_struct["min"], g_struct["max"])

    total = w_rs + w_mom + w_struct
    w_rs /= total
    w_mom /= total
    w_struct /= total

    changes["ranking_weights"] = {
        "rs": round(w_rs, 4),
        "momentum": round(w_mom, 4),
        "structure": round(w_struct, 4),
    }
    reasoning["ranking_weights"] = reason_note
    return changes, reasoning


def _adapt_regime_allocations(
    scorecard: Dict[str, Any],
    current: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Shift shorts/longs allocation per regime based on side performance."""
    changes: Dict[str, Any] = {}
    reasoning: Dict[str, str] = {}

    cur_allocs = current.get("regime_allocations", dict(DEFAULTS["regime_allocations"]))
    by_side_regime = scorecard.get("by_side_regime", {})
    new_allocs: Dict[str, Dict[str, float]] = {}

    for regime in ("STRONG_DOWNTREND", "MIXED", "STRONG_UPTREND", "CHOPPY"):
        cur = cur_allocs.get(regime, DEFAULTS["regime_allocations"].get(regime, {"shorts": 0.5, "longs": 0.5}))

        short_data = by_side_regime.get("SELL", {}).get(regime, {})
        long_data = by_side_regime.get("BUY", {}).get(regime, {})

        short_exp = short_data.get("expectancy", 0)
        long_exp = long_data.get("expectancy", 0)
        short_wr = short_data.get("win_rate", 0.5)
        long_wr = long_data.get("win_rate", 0.5)

        cur_short_alloc = cur.get("shorts", 0.5)
        target = cur_short_alloc

        if short_exp > long_exp + 0.005:
            target = cur_short_alloc + 0.03
        elif long_exp > short_exp + 0.005:
            target = cur_short_alloc - 0.03

        target = _clamp(target, REGIME_ALLOC_MIN, REGIME_ALLOC_MAX)
        target = _rate_limit_abs(cur_short_alloc, target, REGIME_ALLOC_MAX_CHANGE)
        target = _clamp(target, REGIME_ALLOC_MIN, REGIME_ALLOC_MAX)

        new_allocs[regime] = {
            "shorts": round(target, 3),
            "longs": round(1.0 - target, 3),
        }
        if abs(target - cur_short_alloc) > 0.001:
            reasoning[f"regime_{regime}"] = (
                f"short_exp={short_exp:.4f} long_exp={long_exp:.4f} "
                f"-> shorts {cur_short_alloc:.2f} -> {target:.3f}"
            )

    changes["regime_allocations"] = new_allocs
    return changes, reasoning


def _adapt_conviction_thresholds(
    scorecard: Dict[str, Any],
    current: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Raise min conviction if low-conviction trades have negative expectancy."""
    changes: Dict[str, Any] = {}
    reasoning: Dict[str, str] = {}

    by_conviction = scorecard.get("by_conviction", {})
    low_metrics = by_conviction.get("low", {})
    low_exp = low_metrics.get("expectancy", 0)

    cur_short = current.get("min_conviction_short", 0.0)
    cur_long = current.get("min_conviction_long", 0.0)

    g_short = GUARDRAILS["min_conviction_short"]
    g_long = GUARDRAILS["min_conviction_long"]

    if low_exp < -0.005 and low_metrics.get("trade_count", 0) >= 5:
        new_short = _rate_limit_abs(cur_short, cur_short + 0.03, g_short["max_change_abs"])
        new_long = _rate_limit_abs(cur_long, cur_long + 0.03, g_long["max_change_abs"])
        reason = f"Low conviction expectancy={low_exp:.4f} < 0 -> raise threshold"
    elif low_exp > 0.01 and cur_short > 0:
        new_short = _rate_limit_abs(cur_short, cur_short - 0.02, g_short["max_change_abs"])
        new_long = _rate_limit_abs(cur_long, cur_long - 0.02, g_long["max_change_abs"])
        reason = f"Low conviction expectancy={low_exp:.4f} positive -> lower threshold"
    else:
        new_short = cur_short
        new_long = cur_long
        reason = "no change"

    changes["min_conviction_short"] = round(_clamp(new_short, g_short["min"], g_short["max"]), 3)
    changes["min_conviction_long"] = round(_clamp(new_long, g_long["min"], g_long["max"]), 3)
    reasoning["min_conviction"] = reason
    return changes, reasoning


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def adapt() -> Optional[Dict[str, Any]]:
    """Run one adaptation cycle. Returns the new config or None if no scorecard."""
    scorecard = _load_scorecard()
    if scorecard is None:
        logger.info("No scorecard found; skipping adaptation")
        return None

    if scorecard.get("total_trades", 0) < MIN_TRADES_FOR_SCORECARD:
        logger.info("Scorecard has < %d trades; skipping", MIN_TRADES_FOR_SCORECARD)
        return None

    config = _load_current_config()
    current_params = config.get("params", dict(DEFAULTS))
    generation = config.get("generation", 0)

    all_changes: Dict[str, Any] = {}
    all_reasoning: Dict[str, str] = {}

    for adapt_fn in (
        _adapt_stop_tp,
        _adapt_risk_per_trade,
        _adapt_ranking_weights,
        _adapt_regime_allocations,
        _adapt_conviction_thresholds,
    ):
        changes, reasons = adapt_fn(scorecard, current_params)
        all_changes.update(changes)
        all_reasoning.update(reasons)

    new_params = dict(current_params)
    new_params.update(all_changes)

    new_config = {
        "updated_at": datetime.now().isoformat(),
        "generation": generation + 1,
        "params": new_params,
        "reasoning": all_reasoning,
    }

    ADAPTIVE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ADAPTIVE_CONFIG_PATH.write_text(json.dumps(new_config, indent=2))
    logger.info("Adaptive config written (gen %d) -> %s", generation + 1, ADAPTIVE_CONFIG_PATH)

    _append_log(new_config, current_params)
    return new_config


def _append_log(new_config: Dict[str, Any], old_params: Dict[str, Any]) -> None:
    """Append one line to adaptation_log.jsonl with before/after + reasoning."""
    ADAPTATION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "generation": new_config.get("generation"),
        "before": old_params,
        "after": new_config.get("params"),
        "reasoning": new_config.get("reasoning"),
    }
    with open(ADAPTATION_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    result = adapt()
    if result:
        print(json.dumps(result, indent=2))
    else:
        print("No adaptation performed (insufficient data or missing scorecard)")
