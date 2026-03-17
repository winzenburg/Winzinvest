#!/usr/bin/env python3
"""
Portfolio Intelligence Engine
==============================
Reads every data source — snapshot, Greeks, scenarios, risk config,
drawdown state, assignment alerts — and produces a ranked list of
recommendations with plain-English explanations and optional queued trades.

Think of it as the system asking itself: "What should I do right now?"

Output: logs/recommendations.json
Each recommendation has:
  priority    — critical / warning / opportunity / info
  category    — risk / income / hedge / rebalance / system
  title       — one-line summary
  detail      — explanation in plain English
  action      — "execute" | "review" | "monitor"
  trade       — optional dict written to pending_trades.json if actionable

Runs: daily at 7:05 MT (just after pre-market screeners), and on-demand.
"""

import json
import logging
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

SCRIPTS_DIR     = Path(__file__).resolve().parent
TRADING_DIR     = SCRIPTS_DIR.parent
LOGS_DIR        = TRADING_DIR / "logs"

SNAPSHOT_PATH   = LOGS_DIR / "dashboard_snapshot.json"
GREEKS_PATH     = LOGS_DIR / "portfolio_greeks.json"
SCENARIOS_PATH  = LOGS_DIR / "scenario_results.json"
RISK_PATH       = TRADING_DIR / "risk.json"
BREAKER_PATH    = LOGS_DIR / "drawdown_breaker_state.json"
ASSIGN_PATH     = LOGS_DIR / "assignment_alerts_today.json"
PENDING_PATH    = LOGS_DIR / "pending_trades.json"
OUTPUT_PATH     = LOGS_DIR / "recommendations.json"

PRIORITY_ORDER = {"critical": 0, "warning": 1, "opportunity": 2, "info": 3}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception as e:
            logger.warning("Could not load %s: %s", path.name, e)
    return {}


def _add(recs: list, priority: str, category: str, title: str,
         detail: str, action: str = "monitor", trade: dict | None = None) -> None:
    recs.append({
        "id":       f"{category}_{len(recs):03d}",
        "priority": priority,
        "category": category,
        "title":    title,
        "detail":   detail,
        "action":   action,
        "trade":    trade,
        "generated_at": datetime.now().isoformat(),
    })


# ── Individual rule modules ───────────────────────────────────────────────────

def _check_greeks(recs: list, greeks: dict, snap: dict) -> None:
    """Rules driven by portfolio-level Greeks."""
    if not greeks:
        return

    nlv         = snap["account"].get("net_liquidation", 164000)
    net_theta   = greeks.get("net_theta", 0)
    net_delta   = greeks.get("net_delta", 0)
    net_vega    = greeks.get("net_vega", 0)
    theta_yield = greeks.get("theta_yield_pct", 0)
    delta_pct   = greeks.get("delta_pct_nlv", 0)

    # Theta yield check
    if theta_yield < 15:
        _add(recs, "opportunity", "income",
             f"Theta yield is {theta_yield:.1f}% annualised — target is 20–30%",
             f"Currently collecting ${net_theta:.0f}/day. "
             f"Selling more covered calls or CSPs on uncovered positions would increase this. "
             f"Target: ${nlv * 0.20 / 365:.0f}/day.",
             "review")

    # Delta concentration
    if delta_pct > 25:
        _add(recs, "warning", "risk",
             f"Net long delta is {delta_pct:+.1f}% of NLV — portfolio is directional",
             f"A 10% market drop would cost ~${abs(net_delta) * 0.10:,.0f} from delta alone "
             f"(before covered call offsets). Consider XOP puts or trimming the largest "
             f"directional position to bring delta below 15%.",
             "review")
    elif delta_pct < -15:
        _add(recs, "warning", "risk",
             f"Net short delta is {delta_pct:+.1f}% of NLV — rally risk elevated",
             "Portfolio profits from down moves but gives back on rallies. "
             "If market sentiment shifts, short positions may need covering.",
             "review")

    # Expiring options
    expiring = [p for p in greeks.get("positions", []) if 0 < p.get("days_to_exp", 99) <= 7]
    if expiring:
        for opt in expiring:
            sym  = opt["symbol"]
            dte  = opt["days_to_exp"]
            spot = opt.get("spot", 0)
            strike = opt.get("strike", 0)
            right  = opt.get("right", "C")
            itm    = (spot > strike if right == "C" else spot < strike)
            label  = "ITM ⚠️" if itm else "OTM"
            _add(recs, "warning" if itm else "info", "risk",
                 f"{sym} expires in {dte} day(s) — {label}",
                 f"Spot ${spot:.2f} vs strike ${strike:.2f}. "
                 + ("Consider closing or rolling now to avoid assignment risk."
                    if itm else
                    "Will expire worthless if spot stays here — monitor for pin risk."),
                 "review")

    # Vega: short vol in high-VIX environment
    if net_vega < -nlv * 0.015:
        _add(recs, "info", "risk",
             f"Portfolio is significantly short volatility (vega ${net_vega:,.0f})",
             f"A 10-point VIX spike would cost ~${abs(net_vega) * 10:,.0f}. "
             "This is normal for a covered-call portfolio but worth monitoring during earnings season.",
             "monitor")


def _check_scenarios(recs: list, scenarios: dict, snap: dict) -> None:
    """Rules driven by stress-test scenarios."""
    if not scenarios:
        return

    nlv = snap["account"].get("net_liquidation", 164000)
    for s in scenarios.get("scenarios", []):
        pct = s.get("pnl_pct", 0)
        sev = s.get("severity", "info")
        if sev == "critical":
            _add(recs, "critical", "risk",
                 f"Stress test: '{s['label']}' would lose ${abs(s['total_pnl']):,.0f} ({pct:.1f}% of NLV)",
                 s.get("action", "Review portfolio risk."),
                 "review")
        elif sev == "warning":
            _add(recs, "warning", "risk",
                 f"Stress test: '{s['label']}' would lose ${abs(s['total_pnl']):,.0f} ({pct:.1f}% of NLV)",
                 s.get("action", "Consider hedging."),
                 "review")

    worst = scenarios.get("worst_case", {})
    if worst.get("pnl_pct", 0) < -8:
        _add(recs, "warning", "hedge",
             f"Worst-case scenario: {worst['label']} → ${worst['pnl']:,.0f} ({worst['pnl_pct']:.1f}%)",
             "Buying 2 XOP put contracts ($5 OTM, 45 DTE) would cost roughly $400 "
             "but cap your energy drawdown at approximately -6% NLV in any of these scenarios.",
             "review")


def _check_concentration(recs: list, snap: dict, risk_cfg: dict) -> None:
    """Sector and position concentration rules."""
    nlv           = snap["account"].get("net_liquidation", 164000)
    sector_exp    = snap.get("risk", {}).get("sector_exposure", {})
    positions     = snap.get("positions", {}).get("list", [])
    max_sector    = risk_cfg.get("portfolio", {}).get("max_sector_concentration_pct", 0.45) * 100
    max_position  = risk_cfg.get("equity_longs", {}).get("max_position_pct_of_equity", 0.06) * 100

    for sector, dollars in sector_exp.items():
        pct = abs(dollars) / nlv * 100
        if pct > max_sector and sector not in ("Unknown",):
            # Find which position to trim
            sector_stks = sorted(
                [p for p in positions
                 if p.get("sec_type") == "STK" and p.get("sector") == sector and p.get("quantity", 0) > 0],
                key=lambda x: -abs(x.get("market_value", 0))
            )
            trim_target = sector_stks[0] if sector_stks else None
            detail = (
                f"{sector} is {pct:.1f}% of NLV (limit {max_sector:.0f}%). "
                f"To bring it to {max_sector:.0f}%, reduce exposure by "
                f"~${dollars - (nlv * max_sector / 100):,.0f}."
            )
            if trim_target:
                detail += (
                    f" Largest position: {trim_target['symbol']} "
                    f"(${trim_target['market_value']:,.0f}, {abs(trim_target['market_value'])/nlv*100:.1f}% NLV)."
                )
            _add(recs, "warning", "rebalance",
                 f"{sector} concentration at {pct:.1f}% — over {max_sector:.0f}% limit",
                 detail, "review")

    # Oversized individual positions
    for pos in positions:
        if pos.get("sec_type") != "STK" or pos.get("quantity", 0) <= 0:
            continue
        pct = abs(pos.get("market_value", 0)) / nlv * 100
        if pct > max_position * 1.5:
            _add(recs, "info", "rebalance",
                 f"{pos['symbol']} is {pct:.1f}% of NLV (guideline {max_position:.0f}%)",
                 f"Market value ${pos['market_value']:,.0f}. "
                 f"Trimming to {max_position:.0f}% NLV would free up "
                 f"~${pos['market_value'] - nlv * max_position / 100:,.0f}.",
                 "review")


def _check_uncovered(recs: list, snap: dict) -> None:
    """Long positions that should have covered calls."""
    positions = snap.get("positions", {}).get("list", [])
    call_syms: set[str] = set()
    for p in positions:
        sym = str(p.get("symbol", ""))
        if p.get("sec_type") == "OPT" and p.get("quantity", 0) < 0 and "C " in sym:
            call_syms.add(sym.split(" ")[0])

    hedge_etfs = {"VXX", "VIXY", "TZA", "SQQQ", "SPXS", "UVXY"}

    for pos in positions:
        if (pos.get("sec_type") != "STK"
                or pos.get("quantity", 0) < 100
                or pos.get("symbol") in hedge_etfs):
            continue
        sym = pos.get("symbol", "")
        if sym not in call_syms:
            qty  = int(pos.get("quantity", 0))
            mkt  = pos.get("market_price", 0)
            contracts = qty // 100
            est_premium = mkt * 0.015 * contracts * 100  # ~1.5% OTM rough estimate

            # Resolve strike and expiry to concrete values at write-time so the
            # executor can use them directly without further interpretation.
            raw_strike = mkt * 1.10 if mkt > 0 else 0
            if raw_strike > 200:
                interval = 5.0
            elif raw_strike > 100:
                interval = 2.5
            else:
                interval = 1.0
            concrete_strike = round(round(raw_strike / interval) * interval, 2) if raw_strike > 0 else 0

            from datetime import date, timedelta
            _today = date.today()
            _nm = (_today.month % 12) + 1
            _ny = _today.year + (1 if _today.month == 12 else 0)
            _third_week = date(_ny, _nm, 15)
            _days_to_fri = (4 - _third_week.weekday()) % 7
            concrete_expiry = (_third_week + timedelta(days=_days_to_fri)).strftime("%Y%m%d")

            _add(recs, "opportunity", "income",
                 f"{sym} has {qty} uncovered shares — sell {contracts} covered call(s)",
                 f"Estimated monthly premium at ~1.5% OTM: ${est_premium:.0f}. "
                 f"This is free income on a position you already hold.",
                 "execute",
                 trade={
                     "action":   "SELL_TO_OPEN",
                     "symbol":   sym,
                     "sec_type": "OPT",
                     "right":    "C",
                     "strike":   concrete_strike,
                     "expiry":   concrete_expiry,
                     "quantity": contracts,
                     "note":     f"Alert-monitor queued: {sym} uncovered CC ({qty} shares → {contracts} contracts)",
                     "source":   "intelligence_engine",
                     "priority": "high",
                 })


def _check_cash_drag(recs: list, snap: dict, risk_cfg: dict) -> None:
    """Idle cash that should be working."""
    cash_pct = risk_cfg.get("cash_monitor", {}).get("cash_idle_threshold_pct", 0.15) * 100
    total_cash = snap["account"].get("total_cash", 0)
    nlv        = snap["account"].get("net_liquidation", 164000)
    cash_ratio = (total_cash / nlv * 100) if nlv > 0 else 0

    if total_cash > 0 and cash_ratio > cash_pct:
        _add(recs, "opportunity", "income",
             f"${total_cash:,.0f} idle cash ({cash_ratio:.1f}% of NLV)",
             f"Cash above {cash_pct:.0f}% NLV could be deployed into cash-secured puts "
             f"on screener picks, earning premium while waiting for assignment.",
             "review")


def _check_drawdown(recs: list, breaker: dict, snap: dict) -> None:
    """Drawdown circuit breaker state."""
    tier = breaker.get("tier", 0)
    dd   = breaker.get("drawdown_pct", 0)
    if tier >= 3:
        _add(recs, "critical", "risk",
             f"Drawdown breaker TIER 3 active — kill switch engaged ({dd:.1f}% loss)",
             "All trading halted. Review what caused the loss before reactivating.",
             "review")
    elif tier == 2:
        _add(recs, "critical", "risk",
             f"Drawdown breaker TIER 2 — new entries halted ({dd:.1f}% loss)",
             "No new positions can be opened. Focus on managing existing positions.",
             "monitor")
    elif tier == 1:
        _add(recs, "warning", "risk",
             f"Drawdown breaker TIER 1 — position sizes reduced 50% ({dd:.1f}% loss)",
             "New positions will be half normal size. Consider reviewing what is driving the loss.",
             "monitor")


def _check_performance(recs: list, snap: dict) -> None:
    """Daily P&L and trailing performance observations."""
    perf = snap.get("performance", {})
    nlv  = snap["account"].get("net_liquidation", 164000)

    daily_pnl = perf.get("daily_pnl", 0)
    daily_pct = perf.get("daily_return_pct", 0)
    win_rate  = perf.get("win_rate", 0)
    pf        = perf.get("profit_factor", 0)
    sharpe    = perf.get("sharpe_ratio", 0)

    if daily_pnl < -nlv * 0.02:
        _add(recs, "warning", "risk",
             f"Down {abs(daily_pct):.2f}% today (${abs(daily_pnl):,.0f})",
             "Approaching daily loss limit. Monitor positions closely — "
             "drawdown breaker tiers at -3%, -5%, -8%.",
             "monitor")

    if win_rate > 0 and win_rate < 45:
        _add(recs, "info", "system",
             f"Win rate is {win_rate:.0f}% — below the 50% threshold",
             "While a win rate below 50% can be fine if winners are larger than losers "
             f"(profit factor: {pf:.2f}x), it may indicate entry timing issues. "
             "Review the screener's signal quality.",
             "review")

    if sharpe > 3:
        _add(recs, "info", "system",
             f"Sharpe ratio is {sharpe:.2f} — exceptionally high",
             "A Sharpe above 3 often indicates an unusually low-volatility period. "
             "This may compress if market conditions normalise. Maintain risk discipline.",
             "monitor")


def _check_assignment_alerts(recs: list, assign: dict) -> None:
    """ITM short options near assignment risk."""
    if not assign:
        return
    today = date.today().isoformat()
    if assign.get("date") != today:
        return
    alerted = assign.get("alerted", {})
    for key, level in alerted.items():
        if level in ("ITM", "DEEP_ITM", "DIVIDEND"):
            sym = key.split("_")[0]
            _add(recs, "critical" if level in ("DEEP_ITM", "DIVIDEND") else "warning",
                 "risk",
                 f"{sym} option is {level.replace('_', ' ')} — assignment risk",
                 f"Short option on {sym} is in-the-money. "
                 "Consider buying to close or rolling out and up before expiry "
                 "to avoid forced assignment.",
                 "review")


# ── Queue actionable trades ────────────────────────────────────────────────────

def _queue_trades(recs: list) -> list[dict]:
    """Pull 'execute' recommendations and write to pending_trades.json."""
    executable = [r for r in recs if r.get("action") == "execute" and r.get("trade")]
    if not executable:
        return []

    # Don't overwrite existing pending trades (would lose previously queued items)
    existing: dict = _load(PENDING_PATH)
    existing_trades: list = existing.get("trades", [])
    existing_notes = {t.get("note", "") for t in existing_trades}

    new_trades = []
    for rec in executable:
        t = rec["trade"]
        if t.get("note", "") not in existing_notes:
            new_trades.append(t)

    if new_trades:
        all_trades = existing_trades + new_trades
        PENDING_PATH.write_text(json.dumps({
            "generated_at": datetime.now().isoformat(),
            "reason":       "Queued by portfolio intelligence engine",
            "trades":       all_trades,
        }, indent=2))
        logger.info("Queued %d new trade(s) in pending_trades.json", len(new_trades))

    return new_trades


# ── Main ──────────────────────────────────────────────────────────────────────

def run_intelligence() -> dict[str, Any]:
    snap      = _load(SNAPSHOT_PATH)
    greeks    = _load(GREEKS_PATH)
    scenarios = _load(SCENARIOS_PATH)
    risk_cfg  = _load(RISK_PATH)
    breaker   = _load(BREAKER_PATH)
    assign    = _load(ASSIGN_PATH)

    if not snap:
        logger.error("No snapshot available — run dashboard_data_aggregator first")
        return {}

    recs: list[dict] = []

    _check_drawdown(recs, breaker, snap)
    _check_assignment_alerts(recs, assign)
    _check_scenarios(recs, scenarios, snap)
    _check_greeks(recs, greeks, snap)
    _check_concentration(recs, snap, risk_cfg)
    _check_uncovered(recs, snap)
    _check_cash_drag(recs, snap, risk_cfg)
    _check_performance(recs, snap)

    # Sort: critical first, then warning, opportunity, info
    recs.sort(key=lambda r: PRIORITY_ORDER.get(r["priority"], 99))

    queued = _queue_trades(recs)

    summary = {
        "critical":    sum(1 for r in recs if r["priority"] == "critical"),
        "warning":     sum(1 for r in recs if r["priority"] == "warning"),
        "opportunity": sum(1 for r in recs if r["priority"] == "opportunity"),
        "info":        sum(1 for r in recs if r["priority"] == "info"),
        "queued_trades": len(queued),
    }

    output = {
        "generated_at":    datetime.now().isoformat(),
        "summary":         summary,
        "recommendations": recs,
    }

    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    logger.info(
        "Intelligence engine: %d critical, %d warning, %d opportunity, %d info — %d trade(s) queued",
        summary["critical"], summary["warning"], summary["opportunity"],
        summary["info"], summary["queued_trades"],
    )
    return output


if __name__ == "__main__":
    result = run_intelligence()
    if result:
        print(f"\n{'='*70}")
        print(f"  PORTFOLIO INTELLIGENCE — {result['generated_at'][:16]}")
        print(f"{'='*70}")
        icons = {"critical": "🚨", "warning": "⚠️ ", "opportunity": "💡", "info": "ℹ️ "}
        for r in result["recommendations"]:
            icon = icons.get(r["priority"], "• ")
            print(f"\n  {icon} [{r['category'].upper()}] {r['title']}")
            print(f"     {r['detail'][:150]}")
            if r.get("action") == "execute":
                print(f"     → QUEUED FOR EXECUTION")
        s = result["summary"]
        print(f"\n{'─'*70}")
        print(f"  {s['critical']} critical  |  {s['warning']} warnings  |  "
              f"{s['opportunity']} opportunities  |  {s['queued_trades']} trade(s) queued")
        print(f"{'='*70}\n")
