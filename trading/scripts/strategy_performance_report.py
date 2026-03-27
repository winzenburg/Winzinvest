"""
Strategy Attribution P&L Report — Steve Clark "do more of what works" principle.

Queries trades.db and produces a breakdown of performance by strategy AND by
strategy-within-regime.  The output tells you:
  - Which strategies are actually generating alpha right now
  - Which strategies should be scaled up vs. scaled down
  - Whether your best strategy in a bull regime is the same as in CHOPPY

Run manually or scheduled (e.g., Friday close):
    python strategy_performance_report.py [--days 90] [--json]

Output is printed to stdout AND saved to logs/strategy_attribution_YYYYMMDD.json.
A Telegram summary is sent when significant regime-specific changes are detected.
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("strategy_performance_report")

SCRIPTS_DIR = Path(__file__).resolve().parent
TRADING_DIR = SCRIPTS_DIR.parent
LOGS_DIR = TRADING_DIR / "logs"
DB_PATH = LOGS_DIR / "trades.db"


_SYSTEMATIC_EXIT_REASONS = frozenset({
    "TRAIL_HIT", "STOP_HIT", "TP_HIT", "TAKE_PROFIT", "PARTIAL_TP",
    "ATR_STOP", "STOP_LOSS", "TRAILING_STOP", "STOP", "PROFIT_TARGET",
    "TIME_STOP", "DTE_CLOSE", "EXPIRY_CLOSE", "PROFIT_ROLL",
})


def _exit_type(exit_reason: Optional[str]) -> str:
    """Classify a trade exit as 'systematic' or 'override'.

    Richard Bargh (Unknown Market Wizards): track discretionary overrides
    separately.  When systematic exits outperform overrides, your rules are
    good and you should trust them.  When overrides outperform, it signals
    either an under-specified rule or a regime the system wasn't designed for.
    """
    if not exit_reason:
        return "unknown"
    if exit_reason.upper().strip() in _SYSTEMATIC_EXIT_REASONS:
        return "systematic"
    return "override"


def _query_trades(days: int = 90) -> List[Dict[str, Any]]:
    if not DB_PATH.exists():
        logger.error("trades.db not found at %s", DB_PATH)
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cur.execute(
        """
        SELECT symbol, side, qty, entry_price, exit_price, realized_pnl, realized_pnl_pct,
               exit_reason, strategy, timestamp, holding_days, stop_price, r_multiple
        FROM trades
        WHERE exit_price IS NOT NULL
          AND entry_price IS NOT NULL AND entry_price > 0
          AND timestamp >= ?
        ORDER BY timestamp DESC
        """,
        (cutoff,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    # Tag each row with exit type for Bargh analysis
    for row in rows:
        row["_exit_type"] = _exit_type(row.get("exit_reason"))
    return rows


def _stats(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute win rate, avg PnL, profit factor, Sharpe estimate, expectancy."""
    if not trades:
        return {
            "count": 0, "win_rate": 0, "avg_pnl_pct": 0,
            "avg_winner_pct": 0, "avg_loser_pct": 0,
            "profit_factor": 0, "expectancy_pct": 0,
        }
    pnls = [float(t.get("realized_pnl_pct") or 0) * 100 for t in trades]
    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p <= 0]
    gross_win = sum(winners) if winners else 0
    gross_loss = abs(sum(losers)) if losers else 1e-9
    profit_factor = gross_win / gross_loss if gross_loss > 0 else 0
    avg_pnl = sum(pnls) / len(pnls)
    win_rate = len(winners) / len(pnls) if pnls else 0
    avg_winner = sum(winners) / len(winners) if winners else 0
    avg_loser = sum(losers) / len(losers) if losers else 0
    expectancy = win_rate * avg_winner + (1 - win_rate) * avg_loser

    import statistics
    sharpe = 0.0
    if len(pnls) >= 5:
        try:
            std = statistics.stdev(pnls)
            sharpe = (avg_pnl / std) * (252 ** 0.5) if std > 0 else 0
        except Exception:
            pass

    return {
        "count": len(trades),
        "win_rate": round(win_rate, 3),
        "avg_pnl_pct": round(avg_pnl, 3),
        "avg_winner_pct": round(avg_winner, 3),
        "avg_loser_pct": round(avg_loser, 3),
        "profit_factor": round(profit_factor, 2),
        "expectancy_pct": round(expectancy, 3),
        "annualized_sharpe": round(sharpe, 2),
    }


def _regime_for_trade(trade: Dict[str, Any]) -> str:
    """Best-effort regime label for a trade using its timestamp.

    Reads logs/regime_history.jsonl if available, otherwise returns 'UNKNOWN'.
    """
    ts_str = (trade.get("timestamp") or "")[:19]
    if not ts_str:
        return "UNKNOWN"
    try:
        ts = datetime.fromisoformat(ts_str)
        rh_path = LOGS_DIR / "regime_history.jsonl"
        if not rh_path.exists():
            return "UNKNOWN"
        best_regime = "UNKNOWN"
        best_dt = None
        with open(rh_path) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    entry_dt = datetime.fromisoformat(entry.get("timestamp", "")[:19])
                    if entry_dt <= ts:
                        if best_dt is None or entry_dt > best_dt:
                            best_dt = entry_dt
                            best_regime = entry.get("regime", "UNKNOWN")
                except Exception:
                    pass
        return best_regime
    except Exception:
        return "UNKNOWN"


def _audit_strategy_diversity(
    strategy_stats: Dict[str, Any],
    total_trades: int,
) -> tuple[float, List[str]]:
    """Jeffrey Neumann: flag when a single strategy dominates the book.

    A healthy multi-strategy system should not have >50% of its trades in one
    strategy (excluding 'PORTFOLIO_BASELINE' which are passive holds).

    Returns (diversity_score, diversity_flags).
    diversity_score: 0.0 (fully concentrated) → 1.0 (perfectly balanced).
    Herfindahl-Hirschman Index (HHI) based: 1 - HHI, normalised.
    """
    flags: List[str] = []
    # Exclude passive baseline from diversity calculation
    active = {
        k: v for k, v in strategy_stats.items()
        if k not in ("PORTFOLIO_BASELINE", "MANUAL") and v["count"] >= 3
    }
    if not active or total_trades == 0:
        return 1.0, flags

    active_total = sum(v["count"] for v in active.values())
    if active_total == 0:
        return 1.0, flags

    # HHI: sum of squared market-share fractions
    hhi = sum((v["count"] / active_total) ** 2 for v in active.values())
    n = len(active)
    # Normalised HHI: 0 = perfect concentration, 1 = perfect balance
    diversity_score = round(1.0 - (hhi - 1 / n) / (1 - 1 / n) if n > 1 else 0.0, 3)

    # Flag dominant strategies
    for strat, stats in active.items():
        share = stats["count"] / active_total
        if share > 0.55:
            flags.append(
                f"⚠️ CONCENTRATION: {strat} is {share:.0%} of active trades "
                f"(diversity score {diversity_score:.2f}) — add other strategy slots to diversify"
            )
        elif share > 0.40:
            flags.append(
                f"📌 NOTE: {strat} is {share:.0%} of active trades — monitor for over-concentration"
            )

    return diversity_score, flags


def build_report(days: int = 90) -> Dict[str, Any]:
    trades = _query_trades(days)
    if not trades:
        return {"error": "No closed trades found", "days": days}

    # ── Overall ─────────────────────────────────────────────────────────────
    overall = _stats(trades)

    # ── By strategy ──────────────────────────────────────────────────────────
    by_strategy: Dict[str, List] = defaultdict(list)
    for t in trades:
        strat = (t.get("strategy") or "unknown").strip().upper()
        by_strategy[strat].append(t)

    strategy_stats = {}
    for strat, strat_trades in sorted(by_strategy.items(), key=lambda x: -len(x[1])):
        strategy_stats[strat] = _stats(strat_trades)

    # ── By strategy × regime ─────────────────────────────────────────────────
    by_strat_regime: Dict[str, Dict[str, List]] = defaultdict(lambda: defaultdict(list))
    for t in trades:
        strat = (t.get("strategy") or "unknown").strip().upper()
        regime = _regime_for_trade(t)
        by_strat_regime[strat][regime].append(t)

    strat_regime_stats: Dict[str, Dict[str, Any]] = {}
    for strat, regime_map in by_strat_regime.items():
        strat_regime_stats[strat] = {
            regime: _stats(rt) for regime, rt in regime_map.items() if len(rt) >= 3
        }

    # ── Recommendations (Clark: "do more of what works") ─────────────────────
    recommendations: List[str] = []
    current_regime = "UNKNOWN"
    try:
        from regime_detector import detect_market_regime
        current_regime = detect_market_regime()
    except Exception:
        pass

    for strat, stats in strategy_stats.items():
        if stats["count"] < 5:
            continue
        if stats["expectancy_pct"] < -0.5:
            recommendations.append(
                f"⚠️ REDUCE {strat}: expectancy {stats['expectancy_pct']:+.2f}% "
                f"(WR {stats['win_rate']*100:.0f}%, PF {stats['profit_factor']:.2f})"
            )
        elif stats["expectancy_pct"] > 1.0 and stats["profit_factor"] > 1.5:
            recommendations.append(
                f"✅ SCALE UP {strat}: expectancy {stats['expectancy_pct']:+.2f}% "
                f"(WR {stats['win_rate']*100:.0f}%, PF {stats['profit_factor']:.2f})"
            )

        # Check if this strategy works in current regime specifically
        regime_data = strat_regime_stats.get(strat, {}).get(current_regime, {})
        if regime_data and regime_data.get("count", 0) >= 3:
            r_exp = regime_data.get("expectancy_pct", 0)
            if r_exp < -0.5:
                recommendations.append(
                    f"🚫 PAUSE {strat} in {current_regime}: "
                    f"regime-specific expectancy {r_exp:+.2f}%"
                )

    # ── Neumann: strategy diversity check ────────────────────────────────────
    diversity_score, diversity_flags = _audit_strategy_diversity(strategy_stats, len(trades))
    recommendations.extend(diversity_flags)

    # ── Bargh: systematic vs override exit comparison ─────────────────────────
    systematic_trades = [t for t in trades if t.get("_exit_type") == "systematic"]
    override_trades   = [t for t in trades if t.get("_exit_type") == "override"]
    unknown_exit      = [t for t in trades if t.get("_exit_type") == "unknown"]

    def _avg_r(tlist: List[Dict[str, Any]]) -> Optional[float]:
        rs = [float(t["r_multiple"]) for t in tlist if t.get("r_multiple") is not None]
        return round(sum(rs) / len(rs), 3) if rs else None

    bargh_comparison = {
        "systematic_count":  len(systematic_trades),
        "override_count":    len(override_trades),
        "unknown_exit_count": len(unknown_exit),
        "systematic_avg_r":  _avg_r(systematic_trades),
        "override_avg_r":    _avg_r(override_trades),
        "systematic_stats":  _stats(systematic_trades),
        "override_stats":    _stats(override_trades),
    }

    # Emit recommendations if overrides consistently beat systematic exits
    if (
        bargh_comparison["systematic_count"] >= 5
        and bargh_comparison["override_count"] >= 3
        and bargh_comparison["override_avg_r"] is not None
        and bargh_comparison["systematic_avg_r"] is not None
    ):
        sys_r = bargh_comparison["systematic_avg_r"]
        ov_r  = bargh_comparison["override_avg_r"]
        if ov_r > sys_r + 0.3:
            recommendations.append(
                f"🔍 BARGH: overrides avg {ov_r:+.2f}R vs systematic {sys_r:+.2f}R — "
                f"discretion is adding value; consider codifying these patterns"
            )
        elif sys_r > ov_r + 0.3:
            recommendations.append(
                f"✅ BARGH: systematic exits avg {sys_r:+.2f}R vs overrides {ov_r:+.2f}R — "
                f"rules are outperforming discretion; trust the system"
            )

    report = {
        "generated_at": datetime.now().isoformat(),
        "lookback_days": days,
        "current_regime": current_regime,
        "total_trades": len(trades),
        "overall": overall,
        "by_strategy": strategy_stats,
        "by_strategy_regime": strat_regime_stats,
        "recommendations": recommendations,
        "strategy_diversity_score": diversity_score,
        "bargh_exit_comparison": bargh_comparison,
    }
    return report


def print_report(report: Dict[str, Any]) -> None:
    print(f"\n{'='*60}")
    print(f"  STRATEGY ATTRIBUTION REPORT")
    print(f"  {report['lookback_days']}d lookback | Current regime: {report['current_regime']}")
    print(f"  Generated: {report['generated_at'][:16]}")
    print(f"{'='*60}")

    overall = report["overall"]
    print(f"\n📊 OVERALL ({report['total_trades']} trades)")
    print(f"   WR: {overall['win_rate']*100:.0f}%  |  "
          f"Avg: {overall['avg_pnl_pct']:+.2f}%  |  "
          f"PF: {overall['profit_factor']:.2f}  |  "
          f"Expectancy: {overall['expectancy_pct']:+.2f}%  |  "
          f"Sharpe: {overall['annualized_sharpe']:.2f}")

    print(f"\n📋 BY STRATEGY")
    for strat, s in report["by_strategy"].items():
        if s["count"] < 2:
            continue
        regime_note = ""
        regime_data = report["by_strategy_regime"].get(strat, {}).get(report["current_regime"], {})
        if regime_data and regime_data.get("count", 0) >= 3:
            regime_note = f"  [{report['current_regime']}: {regime_data['expectancy_pct']:+.2f}%]"
        print(f"   {strat:25s} n={s['count']:3d}  "
              f"WR={s['win_rate']*100:.0f}%  "
              f"E={s['expectancy_pct']:+.2f}%  "
              f"PF={s['profit_factor']:.2f}  "
              f"W={s['avg_winner_pct']:+.2f}%/L={s['avg_loser_pct']:+.2f}%"
              f"{regime_note}")

    diversity = report.get("strategy_diversity_score", None)
    if diversity is not None:
        label = "excellent" if diversity >= 0.8 else "good" if diversity >= 0.6 else "low — consider more strategy variety"
        print(f"\n🧩 STRATEGY DIVERSITY SCORE: {diversity:.2f} ({label})")

    bargh = report.get("bargh_exit_comparison", {})
    if bargh.get("systematic_count", 0) + bargh.get("override_count", 0) > 0:
        sys_r  = bargh.get("systematic_avg_r")
        ov_r   = bargh.get("override_avg_r")
        sys_r_str = f"{sys_r:+.2f}R" if sys_r is not None else "N/A"
        ov_r_str  = f"{ov_r:+.2f}R"  if ov_r  is not None else "N/A"
        print(f"\n🔑 EXIT ANALYSIS (Bargh: systematic vs discretionary)")
        print(f"   Systematic exits : n={bargh['systematic_count']:3d}  avg_R={sys_r_str}  "
              f"WR={bargh['systematic_stats'].get('win_rate', 0)*100:.0f}%  "
              f"E={bargh['systematic_stats'].get('expectancy_pct', 0):+.2f}%")
        print(f"   Override exits   : n={bargh['override_count']:3d}  avg_R={ov_r_str}  "
              f"WR={bargh['override_stats'].get('win_rate', 0)*100:.0f}%  "
              f"E={bargh['override_stats'].get('expectancy_pct', 0):+.2f}%")

    if report["recommendations"]:
        print(f"\n💡 RECOMMENDATIONS")
        for r in report["recommendations"]:
            print(f"   {r}")
    else:
        print(f"\n✅ No strategy adjustments needed")
    print()


def _send_telegram_summary(report: Dict[str, Any]) -> None:
    recs = report.get("recommendations", [])
    if not recs:
        return
    try:
        from notifications import send_telegram
        lines = [f"📊 *Strategy Attribution ({report['lookback_days']}d)*\n"]
        lines.append(f"Regime: {report['current_regime']}")
        lines.append(f"Total trades: {report['total_trades']}")
        lines.append("")
        for r in recs[:5]:
            lines.append(r)
        send_telegram("\n".join(lines))
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=90, help="Lookback window in days")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    report = build_report(days=args.days)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)

    # Save to logs
    out_path = LOGS_DIR / f"strategy_attribution_{datetime.now().strftime('%Y%m%d')}.json"
    try:
        out_path.write_text(json.dumps(report, indent=2))
        logger.info("Saved to %s", out_path)
    except Exception as exc:
        logger.warning("Could not save report: %s", exc)

    _send_telegram_summary(report)


if __name__ == "__main__":
    main()
