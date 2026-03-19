#!/usr/bin/env python3
"""
End-of-Day Performance Gap Analysis.

Compares live trading activity against the optimized backtest targets and
identifies the biggest levers for improvement. Runs automatically via
scheduler at 14:30 MT (post-close) and writes:

  - trading/logs/eod_analysis_YYYY-MM-DD.json  (machine-readable)
  - trading/logs/eod_analysis_YYYY-MM-DD.md    (human-readable report)

The dashboard surfaces the latest report at GET /api/eod-analysis.
"""

import json
import logging
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from paths import TRADING_DIR

LOGS_DIR = TRADING_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOGS_DIR / "eod_analysis.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# ── Backtest baseline (from optimized 37.8% annualized run) ─────────────
BACKTEST = {
    "annualized_return_pct": 37.8,
    "trades_per_month": 37,
    "trades_per_day": 1.7,
    "win_rate": 0.482,
    "avg_win": 378.18,
    "avg_loss": 268.15,
    "risk_per_trade_pct": 0.01,
    "max_position_pct": 0.05,
    "stop_atr_mult": 2.0,
    "tp_atr_mult": 3.5,
    "trailing_atr_mult": 3.0,
    "max_positions": 25,
    "max_holding_days": 20,
    "target_gross_exposure_pct": 85.0,
    "target_options_allocation_pct": 5.0,
}


def _load_json(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _load_executions(path: Path) -> List[Dict[str, Any]]:
    """Load JSONL executions file."""
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                records.append(obj)
        except json.JSONDecodeError:
            continue
    return records


def _get_trades_from_db() -> List[Dict[str, Any]]:
    db_path = LOGS_DIR / "trades.db"
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(str(db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM trades ORDER BY timestamp DESC").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _parse_ts(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "").split("+")[0])


def generate_analysis() -> Dict[str, Any]:
    """Build the full end-of-day analysis."""
    today = datetime.now().strftime("%Y-%m-%d")
    report: Dict[str, Any] = {
        "date": today,
        "generated_at": datetime.now().isoformat(),
        "backtest_target": BACKTEST,
    }

    # ── Portfolio State ─────────────────────────────────────────────────
    pf = _load_json(TRADING_DIR / "portfolio.json")
    if pf:
        positions = pf.get("positions", [])
        summary = pf.get("summary", {})
        nlv = float(summary.get("net_liquidation") or 0)
        long_not = float(summary.get("long_notional") or 0)
        short_not = float(summary.get("short_notional") or 0)

        stk = [p for p in positions if p.get("secType") == "STK"]
        opt = [p for p in positions if p.get("secType") == "OPT"]
        longs = [p for p in stk if (p.get("position") or 0) > 0]
        shorts = [p for p in stk if (p.get("position") or 0) < 0]

        gross_pct = (long_not + short_not) / nlv * 100 if nlv > 0 else 0
        net_pct = (long_not - short_not) / nlv * 100 if nlv > 0 else 0
        idle_pct = max(0, 100 - long_not / nlv * 100) if nlv > 0 else 100
        opt_capital = sum(abs(p.get("marketValue") or 0) for p in opt)
        opt_pct = opt_capital / nlv * 100 if nlv > 0 else 0

        total_unrealized = sum(float(p.get("unrealizedPNL") or 0) for p in positions)
        long_pnl = sum(float(p.get("unrealizedPNL") or 0) for p in longs)
        short_pnl = sum(float(p.get("unrealizedPNL") or 0) for p in shorts)
        opt_pnl = sum(float(p.get("unrealizedPNL") or 0) for p in opt)

        report["portfolio"] = {
            "net_liquidation": round(nlv, 2),
            "long_notional": round(long_not, 2),
            "short_notional": round(short_not, 2),
            "gross_exposure_pct": round(gross_pct, 1),
            "net_exposure_pct": round(net_pct, 1),
            "idle_capital_pct": round(idle_pct, 1),
            "options_capital_pct": round(opt_pct, 2),
            "position_counts": {
                "stk_long": len(longs),
                "stk_short": len(shorts),
                "options": len(opt),
                "total": len(positions),
            },
            "unrealized_pnl": {
                "total": round(total_unrealized, 2),
                "longs": round(long_pnl, 2),
                "shorts": round(short_pnl, 2),
                "options": round(opt_pnl, 2),
            },
        }

        # Largest positions as % of NLV
        big_positions = []
        for p in stk:
            mv = abs(float(p.get("marketValue") or 0))
            pct = mv / nlv * 100 if nlv > 0 else 0
            if pct > BACKTEST["max_position_pct"] * 100:
                big_positions.append({
                    "symbol": p.get("symbol"),
                    "pct_of_nlv": round(pct, 1),
                    "limit": BACKTEST["max_position_pct"] * 100,
                })
        report["oversized_positions"] = big_positions

    # ── Daily P&L ───────────────────────────────────────────────────────
    daily = _load_json(LOGS_DIR / "daily_loss.json")
    peak = _load_json(LOGS_DIR / "peak_equity.json")
    if daily:
        sod = float(daily.get("sod_equity") or 0)
        cur = float(daily.get("current_equity") or 0)
        day_pnl = cur - sod if sod > 0 else 0
        day_pct = day_pnl / sod * 100 if sod > 0 else 0
        peak_eq = float((peak or {}).get("peak_equity") or 0)
        dd = (peak_eq - cur) / peak_eq * 100 if peak_eq > 0 else 0
        report["daily_pnl"] = {
            "sod_equity": round(sod, 2),
            "eod_equity": round(cur, 2),
            "pnl_dollars": round(day_pnl, 2),
            "pnl_pct": round(day_pct, 3),
            "peak_equity": round(peak_eq, 2),
            "drawdown_from_peak_pct": round(dd, 3),
        }

    # ── Trade Activity ──────────────────────────────────────────────────
    executions = _load_executions(LOGS_DIR / "executions.json")
    today_execs = [
        e for e in executions
        if e.get("timestamp", "")[:10] == today
    ]

    all_db_trades = _get_trades_from_db()
    today_db_trades = [t for t in all_db_trades if (t.get("timestamp") or "")[:10] == today]
    open_trades = [t for t in all_db_trades if t.get("exit_price") is None]
    closed_today = [t for t in all_db_trades if (t.get("exit_timestamp") or "")[:10] == today]

    # Trades in last 30 days for velocity calc
    thirty_ago = (datetime.now() - timedelta(days=30)).isoformat()
    recent_execs = [e for e in executions if e.get("timestamp", "") >= thirty_ago]
    trading_days_30d = len(set(e.get("timestamp", "")[:10] for e in recent_execs)) or 1

    by_source = Counter(e.get("source_script", "unknown") for e in today_execs)
    by_source_30d = Counter(e.get("source_script", "unknown") for e in recent_execs)

    report["trade_activity"] = {
        "today": {
            "new_entries": len(today_execs),
            "closed": len(closed_today),
            "by_source": dict(by_source),
        },
        "last_30d": {
            "total_entries": len(recent_execs),
            "trading_days": trading_days_30d,
            "entries_per_day": round(len(recent_execs) / trading_days_30d, 1),
            "by_source": dict(by_source_30d),
        },
        "open_positions_in_db": len(open_trades),
        "backtest_target_per_day": BACKTEST["trades_per_day"],
    }

    # ── Regime ──────────────────────────────────────────────────────────
    regime = _load_json(LOGS_DIR / "regime_context.json")
    if regime:
        report["regime"] = {
            "current": regime.get("regime"),
            "note": regime.get("note", ""),
            "updated_at": regime.get("updated_at", ""),
        }

    # ── Strategy Execution Check ────────────────────────────────────────
    strategies_expected = [
        "execute_longs.py",
        "execute_dual_mode.py",
        "execute_mean_reversion.py",
        "execute_pairs.py",
        "auto_options_executor.py",
    ]
    strategies_that_traded = set(by_source.keys())
    strategies_idle = [
        s for s in strategies_expected
        if s not in strategies_that_traded
    ]
    report["strategy_coverage"] = {
        "expected": strategies_expected,
        "traded_today": list(strategies_that_traded),
        "idle_today": strategies_idle,
        "coverage_pct": round(
            len(strategies_that_traded) / len(strategies_expected) * 100, 0
        ) if strategies_expected else 0,
    }

    # ── Screener Pipeline ───────────────────────────────────────────────
    wl_longs = _load_json(TRADING_DIR / "watchlist_longs.json")
    wl_multi = _load_json(TRADING_DIR / "watchlist_multimode.json")
    wl_mr = _load_json(TRADING_DIR / "watchlist_mean_reversion.json")

    long_cands = len((wl_longs or {}).get("long_candidates", []))
    modes = (wl_multi or {}).get("modes", {})
    short_cands = len(modes.get("short_opportunities", {}).get("short", []))
    premium_cands = len(modes.get("premium_selling", {}).get("short", []))
    mr_cands = len((wl_mr or {}).get("candidates", []))

    total_signals = long_cands + short_cands + mr_cands + premium_cands
    conversion = len(today_execs) / total_signals * 100 if total_signals > 0 else 0

    report["signal_pipeline"] = {
        "long_candidates": long_cands,
        "short_candidates": short_cands,
        "mean_reversion_candidates": mr_cands,
        "premium_candidates": premium_cands,
        "total_signals": total_signals,
        "trades_executed": len(today_execs),
        "conversion_rate_pct": round(conversion, 2),
    }

    # ── Gap Analysis (vs backtest target) ───────────────────────────────
    gaps: List[Dict[str, Any]] = []

    # Trade velocity
    actual_per_day = report["trade_activity"]["last_30d"]["entries_per_day"]
    target_per_day = BACKTEST["trades_per_day"]
    if actual_per_day < target_per_day * 0.5:
        gaps.append({
            "category": "Trade Velocity",
            "severity": "CRITICAL",
            "detail": (
                f"Averaging {actual_per_day:.1f} trades/day vs "
                f"{target_per_day:.1f} target ({actual_per_day/target_per_day*100:.0f}% of target)"
            ),
            "recommendation": "Check that all executors are in the scheduler and not gated by regime/filter thresholds.",
        })

    # Strategy coverage
    if len(strategies_idle) >= 2:
        gaps.append({
            "category": "Strategy Coverage",
            "severity": "HIGH",
            "detail": f"{len(strategies_idle)} of {len(strategies_expected)} strategies idle today: {', '.join(strategies_idle)}",
            "recommendation": "Verify scheduler jobs include all executors and regime gates aren't blocking entries.",
        })

    # Capital utilization
    portfolio_data = report.get("portfolio", {})
    idle = portfolio_data.get("idle_capital_pct", 100)
    if idle > 40:
        gaps.append({
            "category": "Capital Utilization",
            "severity": "HIGH",
            "detail": f"{idle:.0f}% of capital idle (target gross exposure: {BACKTEST['target_gross_exposure_pct']}%)",
            "recommendation": "Increase position sizing or number of concurrent positions to deploy more capital.",
        })

    # Options allocation
    opt_pct_val = portfolio_data.get("options_capital_pct", 0)
    if opt_pct_val < BACKTEST["target_options_allocation_pct"] * 0.3:
        gaps.append({
            "category": "Options Overlay",
            "severity": "MEDIUM",
            "detail": f"Options allocation at {opt_pct_val:.1f}% vs {BACKTEST['target_options_allocation_pct']}% target",
            "recommendation": "Options premium strategies (CC, IC, CSP) are significantly underweight.",
        })

    # Oversized positions
    for pos in report.get("oversized_positions", []):
        gaps.append({
            "category": "Position Concentration",
            "severity": "MEDIUM",
            "detail": f"{pos['symbol']} is {pos['pct_of_nlv']:.1f}% of NLV (limit: {pos['limit']}%)",
            "recommendation": f"Consider trimming {pos['symbol']} to stay within position size limits.",
        })

    # Signal conversion
    if total_signals > 20 and conversion < 1.0:
        gaps.append({
            "category": "Signal Conversion",
            "severity": "MEDIUM",
            "detail": f"{total_signals} signals screened but only {len(today_execs)} converted ({conversion:.1f}%)",
            "recommendation": "Screeners are finding opportunities but executors aren't acting. Check gate thresholds.",
        })

    # Drawdown check
    dd_val = report.get("daily_pnl", {}).get("drawdown_from_peak_pct", 0)
    if dd_val > 5:
        gaps.append({
            "category": "Drawdown Warning",
            "severity": "HIGH" if dd_val > 8 else "MEDIUM",
            "detail": f"Currently {dd_val:.1f}% below peak equity (max allowed: 10%)",
            "recommendation": "Consider reducing gross exposure until recovery begins.",
        })

    report["gaps"] = gaps
    report["gap_count"] = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for g in gaps:
        sev = g["severity"]
        if sev in report["gap_count"]:
            report["gap_count"][sev] += 1

    # ── Score (0-100) ───────────────────────────────────────────────────
    score = 100
    score -= report["gap_count"]["CRITICAL"] * 25
    score -= report["gap_count"]["HIGH"] * 15
    score -= report["gap_count"]["MEDIUM"] * 5
    report["health_score"] = max(0, min(100, score))

    return report


def _render_markdown(report: Dict[str, Any]) -> str:
    """Render the analysis as a human-readable markdown report."""
    lines: List[str] = []
    date = report["date"]
    score = report.get("health_score", 0)

    lines.append(f"# EOD Analysis — {date}")
    lines.append(f"")
    lines.append(f"**Generated:** {report['generated_at']}")
    lines.append(f"**Health Score:** {score}/100")
    lines.append(f"")

    # Daily P&L
    dp = report.get("daily_pnl", {})
    if dp:
        pnl = dp.get("pnl_dollars", 0)
        sign = "+" if pnl >= 0 else ""
        lines.append(f"## Daily P&L")
        lines.append(f"")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| SOD Equity | ${dp.get('sod_equity', 0):,.2f} |")
        lines.append(f"| EOD Equity | ${dp.get('eod_equity', 0):,.2f} |")
        lines.append(f"| Day P&L | {sign}${abs(pnl):,.2f} ({sign}{dp.get('pnl_pct', 0):.2f}%) |")
        lines.append(f"| Peak Equity | ${dp.get('peak_equity', 0):,.2f} |")
        lines.append(f"| Drawdown | {dp.get('drawdown_from_peak_pct', 0):.2f}% |")
        lines.append(f"")

    # Portfolio
    pf = report.get("portfolio", {})
    if pf:
        counts = pf.get("position_counts", {})
        upnl = pf.get("unrealized_pnl", {})
        lines.append(f"## Portfolio")
        lines.append(f"")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Net Liquidation | ${pf.get('net_liquidation', 0):,.2f} |")
        lines.append(f"| Gross Exposure | {pf.get('gross_exposure_pct', 0):.1f}% |")
        lines.append(f"| Net Exposure | {pf.get('net_exposure_pct', 0):.1f}% |")
        lines.append(f"| Idle Capital | {pf.get('idle_capital_pct', 0):.1f}% |")
        lines.append(f"| Options Allocation | {pf.get('options_capital_pct', 0):.1f}% |")
        lines.append(f"| Positions | {counts.get('stk_long', 0)}L / {counts.get('stk_short', 0)}S / {counts.get('options', 0)} OPT |")
        lines.append(f"| Unrealized P&L | ${upnl.get('total', 0):,.2f} (L: ${upnl.get('longs', 0):,.2f} / S: ${upnl.get('shorts', 0):,.2f} / O: ${upnl.get('options', 0):,.2f}) |")
        lines.append(f"")

    # Trade Activity
    ta = report.get("trade_activity", {})
    if ta:
        td = ta.get("today", {})
        l30 = ta.get("last_30d", {})
        lines.append(f"## Trade Activity")
        lines.append(f"")
        lines.append(f"| Metric | Today | 30d Avg | Backtest Target |")
        lines.append(f"|--------|-------|---------|-----------------|")
        lines.append(f"| New Entries | {td.get('new_entries', 0)} | {l30.get('entries_per_day', 0):.1f}/day | {BACKTEST['trades_per_day']:.1f}/day |")
        lines.append(f"| Closed | {td.get('closed', 0)} | — | — |")
        lines.append(f"")
        if td.get("by_source"):
            lines.append(f"**Today by source:** {', '.join(f'{k}: {v}' for k, v in td['by_source'].items())}")
            lines.append(f"")

    # Strategy Coverage
    sc = report.get("strategy_coverage", {})
    if sc:
        lines.append(f"## Strategy Coverage ({sc.get('coverage_pct', 0):.0f}%)")
        lines.append(f"")
        for s in sc.get("expected", []):
            status = "TRADED" if s in sc.get("traded_today", []) else "IDLE"
            icon = "+" if status == "TRADED" else "-"
            lines.append(f"  {icon} {s}: **{status}**")
        lines.append(f"")

    # Signal Pipeline
    sp = report.get("signal_pipeline", {})
    if sp:
        lines.append(f"## Signal Pipeline")
        lines.append(f"")
        lines.append(f"| Source | Candidates |")
        lines.append(f"|--------|-----------|")
        lines.append(f"| Long | {sp.get('long_candidates', 0)} |")
        lines.append(f"| Short | {sp.get('short_candidates', 0)} |")
        lines.append(f"| Mean Reversion | {sp.get('mean_reversion_candidates', 0)} |")
        lines.append(f"| Premium | {sp.get('premium_candidates', 0)} |")
        lines.append(f"| **Total Signals** | **{sp.get('total_signals', 0)}** |")
        lines.append(f"| Converted | {sp.get('trades_executed', 0)} ({sp.get('conversion_rate_pct', 0):.1f}%) |")
        lines.append(f"")

    # Gaps
    gaps = report.get("gaps", [])
    if gaps:
        lines.append(f"## Performance Gaps ({len(gaps)} issues)")
        lines.append(f"")
        for i, g in enumerate(gaps, 1):
            lines.append(f"### {i}. [{g['severity']}] {g['category']}")
            lines.append(f"")
            lines.append(f"{g['detail']}")
            lines.append(f"")
            lines.append(f"> **Action:** {g['recommendation']}")
            lines.append(f"")
    else:
        lines.append(f"## Performance Gaps")
        lines.append(f"")
        lines.append(f"No significant gaps detected. All systems operating within target parameters.")
        lines.append(f"")

    # Regime
    reg = report.get("regime", {})
    if reg:
        lines.append(f"## Market Regime")
        lines.append(f"")
        lines.append(f"**{reg.get('current', 'UNKNOWN')}**")
        if reg.get("note"):
            lines.append(f"")
            lines.append(f"_{reg['note']}_")
        lines.append(f"")

    return "\n".join(lines)


def main() -> None:
    logger.info("Generating end-of-day analysis...")
    report = generate_analysis()
    today = report["date"]

    json_path = LOGS_DIR / f"eod_analysis_{today}.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Wrote %s", json_path)

    md_path = LOGS_DIR / f"eod_analysis_{today}.md"
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    logger.info("Wrote %s", md_path)

    latest_path = LOGS_DIR / "eod_analysis_latest.json"
    latest_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    score = report.get("health_score", 0)
    gap_count = sum(report.get("gap_count", {}).values())
    logger.info("Health score: %d/100, %d gaps found", score, gap_count)

    if report.get("gap_count", {}).get("CRITICAL", 0) > 0:
        try:
            from notifications import notify_critical
            crit_gaps = [g for g in report.get("gaps", []) if g["severity"] == "CRITICAL"]
            msg = "\n".join(f"• {g['detail']}" for g in crit_gaps)
            notify_critical("EOD Analysis: Critical Gaps", msg)
        except Exception:
            pass


if __name__ == "__main__":
    main()
