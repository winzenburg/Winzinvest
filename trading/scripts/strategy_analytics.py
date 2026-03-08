"""
Strategy Analytics Engine — compute rolling performance metrics sliced by
regime, conviction, sector, side, volatility, and exit reason.

Reads closed trades from the DB, computes per-slice statistics, and writes
a strategy_scorecard.json that the adaptive parameter engine consumes.

Run daily after market close, or manually:
    python strategy_analytics.py
"""

import json
import logging
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

from paths import WORKSPACE, TRADING_DIR
SCORECARD_PATH = TRADING_DIR / "analytics" / "strategy_scorecard.json"

ANALYTICS_WINDOW_DAYS = 90
MIN_TRADES_FOR_SCORECARD = 30

CONVICTION_BUCKETS = [
    ("low", 0.0, 0.33),
    ("medium", 0.33, 0.66),
    ("high", 0.66, 1.01),
]

VOLATILITY_BUCKETS = [
    ("low", 0.0, 0.015),
    ("medium", 0.015, 0.03),
    ("high", 0.03, float("inf")),
]


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _compute_slice_metrics(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute aggregate metrics for a list of closed trades."""
    n = len(trades)
    if n == 0:
        return {"trade_count": 0}

    wins = [t for t in trades if (_safe_float(t.get("realized_pnl")) or 0) > 0]
    losses = [t for t in trades if (_safe_float(t.get("realized_pnl")) or 0) <= 0]

    win_rate = len(wins) / n if n > 0 else 0.0

    avg_win_pct = 0.0
    if wins:
        win_pcts = [abs(_safe_float(t.get("realized_pnl_pct")) or 0) for t in wins]
        avg_win_pct = sum(win_pcts) / len(win_pcts)

    avg_loss_pct = 0.0
    if losses:
        loss_pcts = [abs(_safe_float(t.get("realized_pnl_pct")) or 0) for t in losses]
        avg_loss_pct = sum(loss_pcts) / len(loss_pcts)

    expectancy = (win_rate * avg_win_pct) - ((1 - win_rate) * avg_loss_pct)

    gross_wins = sum(max(0, _safe_float(t.get("realized_pnl")) or 0) for t in trades)
    gross_losses = abs(sum(min(0, _safe_float(t.get("realized_pnl")) or 0) for t in trades))
    profit_factor = gross_wins / gross_losses if gross_losses > 0 else float("inf") if gross_wins > 0 else 0.0

    holding_days_vals = [int(t.get("holding_days") or 0) for t in trades if t.get("holding_days") is not None]
    avg_holding_days = sum(holding_days_vals) / len(holding_days_vals) if holding_days_vals else 0.0

    mae_vals = [_safe_float(t.get("max_adverse_excursion")) for t in trades]
    mae_valid = [v for v in mae_vals if v is not None]
    avg_mae = sum(mae_valid) / len(mae_valid) if mae_valid else 0.0

    mfe_vals = [_safe_float(t.get("max_favorable_excursion")) for t in trades]
    mfe_valid = [v for v in mfe_vals if v is not None]
    avg_mfe = sum(mfe_valid) / len(mfe_valid) if mfe_valid else 0.0

    pnl_pcts = [_safe_float(t.get("realized_pnl_pct")) or 0 for t in trades]
    mean_ret = sum(pnl_pcts) / len(pnl_pcts) if pnl_pcts else 0.0
    if len(pnl_pcts) > 1:
        variance = sum((r - mean_ret) ** 2 for r in pnl_pcts) / (len(pnl_pcts) - 1)
        std_ret = math.sqrt(variance) if variance > 0 else 0.0
    else:
        std_ret = 0.0
    sharpe = mean_ret / std_ret if std_ret > 0 else 0.0

    stop_hit_count = sum(1 for t in trades if t.get("exit_reason") == "STOP_HIT")
    stop_hit_pct = stop_hit_count / n if n > 0 else 0.0

    r_multiples = [_safe_float(t.get("r_multiple")) for t in trades]
    r_valid = [r for r in r_multiples if r is not None]
    avg_r = sum(r_valid) / len(r_valid) if r_valid else 0.0
    expectancy_r = avg_r

    return {
        "trade_count": n,
        "win_rate": round(win_rate, 4),
        "avg_win_pct": round(avg_win_pct, 4),
        "avg_loss_pct": round(avg_loss_pct, 4),
        "expectancy": round(expectancy, 4),
        "expectancy_r": round(expectancy_r, 4),
        "avg_r_multiple": round(avg_r, 4),
        "profit_factor": round(profit_factor, 4) if not math.isinf(profit_factor) else 999.0,
        "sharpe": round(sharpe, 4),
        "avg_holding_days": round(avg_holding_days, 1),
        "avg_mae": round(avg_mae, 4),
        "avg_mfe": round(avg_mfe, 4),
        "stop_hit_pct": round(stop_hit_pct, 4),
    }


def _bucket_conviction(score: Optional[float]) -> str:
    if score is None:
        return "unknown"
    for label, lo, hi in CONVICTION_BUCKETS:
        if lo <= score < hi:
            return label
    return "unknown"


def _bucket_volatility(atr: Optional[float], price: Optional[float]) -> str:
    if atr is None or price is None or price <= 0:
        return "unknown"
    ratio = atr / price
    for label, lo, hi in VOLATILITY_BUCKETS:
        if lo <= ratio < hi:
            return label
    return "unknown"


def _group_trades(
    trades: List[Dict[str, Any]],
    key_fn: Any,
) -> Dict[str, List[Dict[str, Any]]]:
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for t in trades:
        k = key_fn(t)
        if k is not None:
            groups[str(k)] = groups.get(str(k), [])
            groups[str(k)].append(t)
    return dict(groups)


def generate_scorecard(
    window_days: int = ANALYTICS_WINDOW_DAYS,
    min_trades: int = MIN_TRADES_FOR_SCORECARD,
) -> Optional[Dict[str, Any]]:
    """Generate the full strategy scorecard from closed trades.

    Returns the scorecard dict, or None if insufficient data.
    """
    from trade_log_db import get_closed_trades

    trades = get_closed_trades(since_days=window_days)
    if len(trades) < min_trades:
        logger.info(
            "Insufficient closed trades for scorecard: %d < %d",
            len(trades), min_trades,
        )
        return None

    scorecard: Dict[str, Any] = {
        "generated_at": datetime.now().isoformat(),
        "window_days": window_days,
        "total_trades": len(trades),
    }

    scorecard["overall"] = _compute_slice_metrics(trades)

    by_side = _group_trades(trades, lambda t: (t.get("side") or "").upper())
    scorecard["by_side"] = {k: _compute_slice_metrics(v) for k, v in by_side.items()}

    by_regime = _group_trades(trades, lambda t: t.get("regime_at_entry"))
    scorecard["by_regime"] = {k: _compute_slice_metrics(v) for k, v in by_regime.items()}

    by_conviction = _group_trades(
        trades,
        lambda t: _bucket_conviction(_safe_float(t.get("conviction_score"))),
    )
    scorecard["by_conviction"] = {k: _compute_slice_metrics(v) for k, v in by_conviction.items()}

    from sector_gates import SECTOR_MAP
    by_sector = _group_trades(
        trades,
        lambda t: SECTOR_MAP.get((t.get("symbol") or "").upper(), "Unknown"),
    )
    scorecard["by_sector"] = {k: _compute_slice_metrics(v) for k, v in by_sector.items()}

    by_vol = _group_trades(
        trades,
        lambda t: _bucket_volatility(
            _safe_float(t.get("atr_at_entry")),
            _safe_float(t.get("entry_price")),
        ),
    )
    scorecard["by_volatility"] = {k: _compute_slice_metrics(v) for k, v in by_vol.items()}

    by_exit = _group_trades(trades, lambda t: t.get("exit_reason"))
    scorecard["by_exit_reason"] = {k: _compute_slice_metrics(v) for k, v in by_exit.items()}

    by_side_regime: Dict[str, Any] = {}
    for side_key, side_trades in by_side.items():
        regime_groups = _group_trades(side_trades, lambda t: t.get("regime_at_entry"))
        by_side_regime[side_key] = {k: _compute_slice_metrics(v) for k, v in regime_groups.items()}
    scorecard["by_side_regime"] = by_side_regime

    return scorecard


def write_scorecard(scorecard: Dict[str, Any]) -> Path:
    """Write the scorecard to disk and return the path."""
    SCORECARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCORECARD_PATH.write_text(json.dumps(scorecard, indent=2))
    logger.info("Scorecard written to %s", SCORECARD_PATH)
    return SCORECARD_PATH


def run() -> Optional[Dict[str, Any]]:
    """Generate and persist the scorecard. Returns it or None."""
    scorecard = generate_scorecard()
    if scorecard is not None:
        write_scorecard(scorecard)
    return scorecard


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    sc = run()
    if sc:
        print(json.dumps(sc, indent=2))
    else:
        print("Not enough data for scorecard")
