#!/usr/bin/env python3
"""
Trade Analytics Generator

Queries trades.db and produces logs/trade_analytics.json consumed by the
dashboard's /analytics page. Run post-close daily (added to scheduler).

Metrics produced:
  - Summary: total trades, win rate, avg R-multiple, total realized PnL
  - By strategy: win rate, avg R, trade count
  - By regime at entry: win rate, avg R, trade count
  - Hold time: avg days winners vs losers
  - Exit reason distribution: stop, take-profit, time stop, manual, partial
  - Monthly PnL: last 12 months (realized_pnl sum per month)
  - Best / worst 5 trades by R-multiple
  - Conviction vs R (binned: high/medium/low conviction score)
  - ATR calibration: percentage of stops that fired vs take-profits vs time stops
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Any

_scripts_dir = Path(__file__).resolve().parent
from paths import TRADING_DIR  # noqa: E402

LOG_DIR = TRADING_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "trade_analytics.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

DB_PATH      = LOG_DIR / "trades.db"
OUTPUT_PATH  = LOG_DIR / "trade_analytics.json"


# ── DB helpers ────────────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection | None:
    if not DB_PATH.exists():
        logger.warning("trades.db not found at %s", DB_PATH)
        return None
    try:
        # Import trade_log_db to trigger any pending schema migrations
        # (e.g. adding excluded_from_pnl column) before we query the DB.
        try:
            import trade_log_db as _tdb  # noqa: F401
        except Exception:
            pass
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as exc:
        logger.error("Cannot open trades.db: %s", exc)
        return None


def _fetch_closed_trades(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return all trades that have been closed (exit_price IS NOT NULL)."""
    cur = conn.execute("""
        SELECT
            id, symbol, side, qty, price, entry_price, exit_price,
            strategy, source_script, status,
            regime_at_entry, conviction_score,
            atr_at_entry, composite_score, structure_quality,
            realized_pnl, realized_pnl_pct, r_multiple,
            holding_days, exit_reason,
            timestamp, exit_timestamp,
            excluded_from_pnl
        FROM trades
        WHERE exit_price IS NOT NULL
          AND excluded_from_pnl IS NULL
        ORDER BY exit_timestamp DESC
    """)
    return [dict(row) for row in cur.fetchall()]


# ── Metric calculators ────────────────────────────────────────────────────────

def _safe_avg(values: list[float]) -> float | None:
    clean = [v for v in values if v is not None]
    return round(sum(clean) / len(clean), 3) if clean else None


def _win_rate(trades: list[dict[str, Any]]) -> float | None:
    rs = [t["r_multiple"] for t in trades if t.get("r_multiple") is not None]
    if not rs:
        return None
    wins = sum(1 for r in rs if r > 0)
    return round(wins / len(rs) * 100, 1)


def _summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    r_vals = [t["r_multiple"] for t in trades if t.get("r_multiple") is not None]
    pnl_vals = [t["realized_pnl"] for t in trades if t.get("realized_pnl") is not None]
    wins = sum(1 for r in r_vals if r > 0)
    losses = sum(1 for r in r_vals if r < 0)
    return {
        "total_closed": len(trades),
        "with_r_data": len(r_vals),
        "win_rate_pct": _win_rate(trades),
        "avg_r_multiple": _safe_avg(r_vals),
        "total_realized_pnl": round(sum(pnl_vals), 2) if pnl_vals else None,
        "wins": wins,
        "losses": losses,
        "breakeven": len(r_vals) - wins - losses,
    }


def _by_group(trades: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    """Group trades by `key` and compute per-group stats."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for t in trades:
        g = str(t.get(key) or "unknown")
        groups.setdefault(g, []).append(t)

    rows = []
    for label, gtrades in sorted(groups.items()):
        r_vals = [t["r_multiple"] for t in gtrades if t.get("r_multiple") is not None]
        pnl = [t["realized_pnl"] for t in gtrades if t.get("realized_pnl") is not None]
        rows.append({
            "label": label,
            "count": len(gtrades),
            "win_rate_pct": _win_rate(gtrades),
            "avg_r_multiple": _safe_avg(r_vals),
            "total_pnl": round(sum(pnl), 2) if pnl else None,
        })
    return sorted(rows, key=lambda x: x["count"], reverse=True)


def _hold_time_comparison(trades: list[dict[str, Any]]) -> dict[str, Any]:
    winners = [t["holding_days"] for t in trades
               if t.get("r_multiple") is not None and t["r_multiple"] > 0
               and t.get("holding_days") is not None]
    losers  = [t["holding_days"] for t in trades
               if t.get("r_multiple") is not None and t["r_multiple"] < 0
               and t.get("holding_days") is not None]
    return {
        "avg_hold_days_winners": _safe_avg(winners),
        "avg_hold_days_losers":  _safe_avg(losers),
        "winner_count": len(winners),
        "loser_count":  len(losers),
    }


def _exit_reason_distribution(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for t in trades:
        reason = t.get("exit_reason") or "unknown"
        # Normalise common reason strings
        r = reason.lower()
        if "stop" in r and "trailing" not in r:
            label = "hard_stop"
        elif "trailing" in r:
            label = "trailing_stop"
        elif "profit" in r or "tp" in r or "target" in r:
            label = "take_profit"
        elif "partial" in r:
            label = "partial_tp"
        elif "time" in r:
            label = "time_stop"
        elif "manual" in r:
            label = "manual"
        else:
            label = reason
        counts[label] = counts.get(label, 0) + 1
    total = sum(counts.values()) or 1
    return [
        {"reason": k, "count": v, "pct": round(v / total * 100, 1)}
        for k, v in sorted(counts.items(), key=lambda x: -x[1])
    ]


def _monthly_pnl(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    monthly: dict[str, float] = {}
    for t in trades:
        ts = t.get("exit_timestamp") or t.get("timestamp")
        pnl = t.get("realized_pnl")
        if not ts or pnl is None:
            continue
        try:
            month = ts[:7]   # "YYYY-MM"
        except Exception:
            continue
        monthly[month] = monthly.get(month, 0.0) + float(pnl)
    # Return last 12 months
    sorted_months = sorted(monthly.items())[-12:]
    return [{"month": m, "pnl": round(v, 2)} for m, v in sorted_months]


def _top_trades(trades: list[dict[str, Any]], n: int = 5) -> dict[str, Any]:
    with_r = [t for t in trades if t.get("r_multiple") is not None]
    best  = sorted(with_r, key=lambda t: t["r_multiple"], reverse=True)[:n]
    worst = sorted(with_r, key=lambda t: t["r_multiple"])[:n]

    def _fmt(t: dict[str, Any]) -> dict[str, Any]:
        pnl_raw = t.get("realized_pnl")
        return {
            "symbol":    t.get("symbol"),
            "strategy":  t.get("strategy"),
            "r_multiple": round(t["r_multiple"], 2),
            "pnl":       round(pnl_raw if pnl_raw is not None else 0, 2),
            "hold_days": t.get("holding_days"),
            "regime":    t.get("regime_at_entry"),
            "exit_date": (t.get("exit_timestamp") or "")[:10],
        }

    return {
        "best":  [_fmt(t) for t in best],
        "worst": [_fmt(t) for t in worst],
    }


def _conviction_vs_r(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bins: dict[str, list[float]] = {"high": [], "medium": [], "low": [], "unknown": []}
    for t in trades:
        score = t.get("conviction_score")
        r     = t.get("r_multiple")
        if r is None:
            continue
        if score is None:
            bins["unknown"].append(r)
        elif score >= 0.8:
            bins["high"].append(r)
        elif score >= 0.5:
            bins["medium"].append(r)
        else:
            bins["low"].append(r)
    return [
        {
            "tier":      tier,
            "count":     len(rs),
            "avg_r":     _safe_avg(rs),
            "win_rate":  round(sum(1 for r in rs if r > 0) / len(rs) * 100, 1) if rs else None,
        }
        for tier, rs in bins.items()
        if rs
    ]


# ── Main ──────────────────────────────────────────────────────────────────────

def run() -> None:
    logger.info("=== Trade Analytics — %s ===", datetime.now().strftime("%Y-%m-%d %H:%M"))

    conn = _connect()
    if conn is None:
        logger.warning("No database connection — writing empty analytics")
        analytics: dict[str, Any] = {
            "generated_at": datetime.now().isoformat(),
            "error": "trades.db not available",
        }
        OUTPUT_PATH.write_text(json.dumps(analytics, indent=2))
        return

    try:
        trades = _fetch_closed_trades(conn)
        logger.info("Loaded %d closed trades from trades.db", len(trades))

        if not trades:
            analytics = {
                "generated_at": datetime.now().isoformat(),
                "note": "No closed trades yet — analytics will populate as trades complete.",
                "summary": {"total_closed": 0},
            }
        else:
            analytics = {
                "generated_at": datetime.now().isoformat(),
                "summary":               _summary(trades),
                "by_strategy":           _by_group(trades, "strategy"),
                "by_regime":             _by_group(trades, "regime_at_entry"),
                "hold_time":             _hold_time_comparison(trades),
                "exit_reasons":          _exit_reason_distribution(trades),
                "monthly_pnl":           _monthly_pnl(trades),
                "top_trades":            _top_trades(trades),
                "conviction_vs_r":       _conviction_vs_r(trades),
            }
            logger.info(
                "Analytics: %d trades, %.1f%% win rate, avg R=%.2f",
                analytics["summary"]["total_closed"],
                analytics["summary"]["win_rate_pct"] or 0,
                analytics["summary"]["avg_r_multiple"] or 0,
            )

        OUTPUT_PATH.write_text(json.dumps(analytics, indent=2))
        logger.info("Wrote analytics to %s", OUTPUT_PATH)

    finally:
        conn.close()


if __name__ == "__main__":
    run()
