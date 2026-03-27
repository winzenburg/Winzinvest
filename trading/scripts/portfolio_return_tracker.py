#!/usr/bin/env python3
"""
Portfolio Return Tracker
========================
Computes a true time-weighted return series from the daily SOD equity history
and measures pace against the 40%+ annual return target.

Data source:  trading/logs/sod_equity_history.jsonl
              (one JSON object per line: {"date": "YYYY-MM-DD", "equity": float})

Output:       trading/logs/portfolio_return_summary.json

Scheduled:    post-close job (14:30 MT) via scheduler.py job_postclose.

Usage:
    python3 portfolio_return_tracker.py            # compute and write output
    python3 portfolio_return_tracker.py --print    # also print summary to stdout
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

_scripts_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_scripts_dir))

from paths import TRADING_DIR, LOGS_DIR

_env_path = TRADING_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "portfolio_return_tracker.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

SOD_HISTORY_PATH = LOGS_DIR / "sod_equity_history.jsonl"
OUTPUT_PATH      = LOGS_DIR / "portfolio_return_summary.json"

ANNUAL_TARGET_PCT = 40.0  # target annualised return in percent


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_equity_history() -> list[dict]:
    """Load and deduplicate SOD equity history. Returns list sorted by date ascending."""
    if not SOD_HISTORY_PATH.exists():
        logger.warning("SOD equity history not found at %s", SOD_HISTORY_PATH)
        return []

    rows: dict[str, float] = {}  # date → equity; deduplicates on date
    for line in SOD_HISTORY_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            d   = obj.get("date", "")
            eq  = float(obj.get("equity", 0))
            if d and eq > 0:
                rows[d] = eq  # last entry for a given date wins
        except (json.JSONDecodeError, ValueError):
            continue

    return sorted([{"date": d, "equity": eq} for d, eq in rows.items()], key=lambda x: x["date"])


def _annualise(cumulative_return: float, trading_days: int) -> float:
    """Annualise a cumulative return over a given number of trading days.

    Uses compounding: (1 + r)^(252 / days) - 1.
    Returns 0.0 if fewer than 2 days of data.
    """
    if trading_days < 2:
        return 0.0
    return ((1 + cumulative_return) ** (252 / trading_days) - 1) * 100


def _compute_rolling_return(history: list[dict], lookback_days: int) -> Optional[float]:
    """Compute annualised return for the most recent `lookback_days` calendar days."""
    if len(history) < 2:
        return None
    cutoff = (date.today() - timedelta(days=lookback_days)).isoformat()
    window = [r for r in history if r["date"] >= cutoff]
    if len(window) < 2:
        return None
    start_eq = window[0]["equity"]
    end_eq   = window[-1]["equity"]
    cum_ret  = (end_eq - start_eq) / start_eq
    return _annualise(cum_ret, len(window) - 1)


def _pace_vs_target(annualised_pct: float) -> dict:
    """Return a human-readable pace-vs-target dict."""
    gap = annualised_pct - ANNUAL_TARGET_PCT
    if gap >= 0:
        label = f"{gap:.1f} points ahead of {ANNUAL_TARGET_PCT:.0f}% target"
        on_pace = True
    else:
        label = f"{abs(gap):.1f} points behind {ANNUAL_TARGET_PCT:.0f}% target"
        on_pace = False
    return {"on_pace": on_pace, "gap_pct": round(gap, 2), "label": label}


def _ytd_return(history: list[dict]) -> Optional[float]:
    """Cumulative YTD return as a percentage (not annualised)."""
    year_start = f"{date.today().year}-01-01"
    ytd = [r for r in history if r["date"] >= year_start]
    if len(ytd) < 2:
        # Fall back to full history if year started before tracking began
        ytd = history
    if len(ytd) < 2:
        return None
    return (ytd[-1]["equity"] - ytd[0]["equity"]) / ytd[0]["equity"] * 100


def _daily_returns(history: list[dict]) -> list[float]:
    """Compute list of daily percentage returns."""
    rets = []
    for i in range(1, len(history)):
        prev = history[i - 1]["equity"]
        curr = history[i]["equity"]
        if prev > 0:
            rets.append((curr - prev) / prev * 100)
    return rets


def _best_worst(daily_rets: list[float]) -> tuple[float, float]:
    if not daily_rets:
        return 0.0, 0.0
    return max(daily_rets), min(daily_rets)


def _atomic_write(path: Path, data: dict) -> None:
    dir_ = path.parent
    dir_.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ── Main ──────────────────────────────────────────────────────────────────────

def run(print_summary: bool = False) -> dict:
    """Compute return metrics and write output. Returns the summary dict."""
    history = _load_equity_history()

    if len(history) < 2:
        logger.warning("Insufficient equity history (%d rows) — need at least 2 days.", len(history))
        result: dict = {
            "computed_at": datetime.now().isoformat(),
            "data_points": len(history),
            "error": "Insufficient history",
        }
        _atomic_write(OUTPUT_PATH, result)
        return result

    daily_rets  = _daily_returns(history)
    best, worst = _best_worst(daily_rets)

    start_equity = history[0]["equity"]
    end_equity   = history[-1]["equity"]
    total_days   = len(history) - 1

    # Full-period cumulative return and annualised rate
    full_cum_ret  = (end_equity - start_equity) / start_equity
    full_annual   = _annualise(full_cum_ret, total_days)

    # Rolling windows
    ret_30d  = _compute_rolling_return(history, 30)
    ret_90d  = _compute_rolling_return(history, 90)
    ytd_ret  = _ytd_return(history)

    # Annualised rate for pace measurement — prefer 90d if available, else full period
    pace_annualised = ret_90d if ret_90d is not None else full_annual
    pace            = _pace_vs_target(pace_annualised)

    # Email-ready one-liner (consumed by daily_options_email.py)
    ytd_str  = f"{ytd_ret:+.1f}% YTD" if ytd_ret is not None else "YTD n/a"
    pace_str = f"annualised: {pace_annualised:.1f}%"
    email_line = f"Portfolio {ytd_str} ({pace_str}) — {pace['label']}."

    result = {
        "computed_at":        datetime.now().isoformat(),
        "data_points":        len(history),
        "history_start":      history[0]["date"],
        "history_end":        history[-1]["date"],
        "start_equity":       round(start_equity, 2),
        "end_equity":         round(end_equity, 2),

        "ytd_return_pct":     round(ytd_ret, 2) if ytd_ret is not None else None,
        "full_period_return_pct": round(full_cum_ret * 100, 2),
        "annualised_return_pct":  round(full_annual, 2),
        "rolling_30d_annualised": round(ret_30d, 2) if ret_30d is not None else None,
        "rolling_90d_annualised": round(ret_90d, 2) if ret_90d is not None else None,

        "pace_annualised_pct": round(pace_annualised, 2),
        "annual_target_pct":   ANNUAL_TARGET_PCT,
        "pace":                pace,

        "best_day_pct":        round(best, 2),
        "worst_day_pct":       round(worst, 2),
        "avg_daily_return_pct": round(sum(daily_rets) / len(daily_rets), 3) if daily_rets else 0.0,

        "email_summary_line":  email_line,
    }

    _atomic_write(OUTPUT_PATH, result)
    logger.info("Return summary written to %s", OUTPUT_PATH)
    logger.info(email_line)

    if print_summary:
        print("\n=== Portfolio Return Summary ===")
        print(f"  History:         {result['history_start']} → {result['history_end']} ({result['data_points']} days)")
        print(f"  Equity:          ${start_equity:,.0f} → ${end_equity:,.0f}")
        print(f"  YTD return:      {ytd_ret:+.1f}%" if ytd_ret is not None else "  YTD return:      n/a")
        print(f"  Annualised:      {full_annual:.1f}%  (30d: {ret_30d:.1f}%  90d: {ret_90d:.1f}%)" if ret_30d and ret_90d else f"  Annualised:      {full_annual:.1f}%")
        print(f"  Target:          {ANNUAL_TARGET_PCT:.0f}%")
        print(f"  Pace:            {pace['label']}")
        print(f"  Best/Worst day:  +{best:.1f}% / {worst:.1f}%")
        print()

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Portfolio Return Tracker — pace vs 40% annual goal")
    parser.add_argument("--print", action="store_true", dest="print_summary", help="Print summary to stdout")
    args = parser.parse_args()
    run(print_summary=args.print_summary)
