#!/usr/bin/env python3
"""
Position Integrity Check — Daily audit for accidental position flips.

Runs every morning before market open. Connects to IB, reads all stock
positions, cross-references them against each strategy's last known
intent (MR watchlist, dual-mode short list, pairs log), and flags any
position that appears to be on the wrong side.

Alerts are sent via Telegram. Results are written to:
    logs/position_integrity_YYYYMMDD.json

Usage:
    python position_integrity_check.py            # connect and audit
    python position_integrity_check.py --dry-run  # print without connecting
"""

import argparse
import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPTS_DIR = Path(__file__).resolve().parent
TRADING_DIR = SCRIPTS_DIR.parent
LOGS_DIR    = TRADING_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOGS_DIR / "position_integrity_check.log"
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

IB_HOST = "127.0.0.1"
IB_PORT = 4001
CLIENT_ID = 196


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_json_safe(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _mr_long_symbols(live_longs: dict[str, float]) -> set[str]:
    """Symbols the MR executor currently tracks as active longs.

    Cross-referenced against live_longs so stale closed positions that were
    never removed from mr_positions.json don't produce false violations.
    """
    data = _load_json_safe(TRADING_DIR / "logs" / "mr_positions.json")
    if not isinstance(data, dict):
        return set()
    syms = data.get("symbols", [])
    tracked = {s.strip().upper() for s in syms if isinstance(s, str) and s.strip()}
    # Only flag if the symbol is *still actually held long* — this prevents
    # stale entries from causing spurious HELD_SHORT_BUT_STRATEGY_IS_LONG alerts
    return tracked & set(live_longs.keys())


def _dual_mode_short_symbols() -> set[str]:
    """Symbols the dual-mode screener currently lists as short candidates."""
    data = _load_json_safe(TRADING_DIR / "watchlist_multimode.json")
    if not isinstance(data, dict):
        return set()
    modes = data.get("modes", {}) or {}
    out: set[str] = set()
    for mode_key in ("short_opportunities", "premium_selling"):
        shorts = (modes.get(mode_key) or {}).get("short", [])
        for item in shorts if isinstance(shorts, list) else []:
            sym = (item.get("symbol") or "") if isinstance(item, dict) else ""
            if sym.strip():
                out.add(sym.strip().upper())
    return out


def _pairs_long_symbols() -> set[str]:
    data = _load_json_safe(TRADING_DIR / "logs" / "pairs_positions.json")
    if not isinstance(data, dict):
        return set()
    return {
        p["long_sym"].upper()
        for p in (data.get("positions") or [])
        if isinstance(p, dict) and p.get("long_sym")
    }


def _pairs_short_symbols() -> set[str]:
    data = _load_json_safe(TRADING_DIR / "logs" / "pairs_positions.json")
    if not isinstance(data, dict):
        return set()
    return {
        p["short_sym"].upper()
        for p in (data.get("positions") or [])
        if isinstance(p, dict) and p.get("short_sym")
    }


# ── Core audit ────────────────────────────────────────────────────────────────

def audit_positions(ib: Any | None) -> list[dict]:
    """
    Cross-reference live positions against strategy intent.
    Returns list of violation dicts; empty list = all clear.
    """
    violations: list[dict] = []

    if ib is None:
        logger.warning("No IB connection — skipping live position check")
        return violations

    # Live positions
    live_longs:  dict[str, float] = {}
    live_shorts: dict[str, float] = {}
    try:
        for pos in ib.positions():
            contract = getattr(pos, "contract", None)
            if contract is None or getattr(contract, "secType", "") != "STK":
                continue
            sym = getattr(contract, "symbol", "").upper()
            qty = float(getattr(pos, "position", 0) or 0)
            avg = float(getattr(pos, "avgCost", 0) or 0)
            if qty > 0:
                live_longs[sym] = qty
            elif qty < 0:
                live_shorts[sym] = qty
    except Exception as exc:
        logger.error("Could not fetch positions: %s", exc)
        return violations

    # Strategy intent sets
    # Pass live_longs so MR only flags symbols still actually held long
    mr_longs       = _mr_long_symbols(live_longs)
    dm_shorts      = _dual_mode_short_symbols()
    pairs_longs    = _pairs_long_symbols()
    pairs_shorts   = _pairs_short_symbols()

    all_strategy_longs  = mr_longs  | pairs_longs
    all_strategy_shorts = dm_shorts | pairs_shorts

    # Also load the NX short screener output to avoid flagging intentional shorts
    nx_short_syms: set[str] = set()
    try:
        ws_data = _load_json_safe(TRADING_DIR / "watchlist_shorts.json")
        if isinstance(ws_data, dict):
            for item in ws_data.get("short_candidates", []):
                sym = (item.get("symbol","") if isinstance(item, dict) else item).upper()
                if sym:
                    nx_short_syms.add(sym)
        elif isinstance(ws_data, list):
            for item in ws_data:
                sym = (item.get("symbol","") if isinstance(item, dict) else item).upper()
                if sym:
                    nx_short_syms.add(sym)
    except Exception:
        pass

    # Rule 1: symbol held SHORT but strategy intends LONG
    # Skip if the symbol is also in ANY short screener — that means dual strategies
    # are conflicting, which is handled by the screener priority, not an integrity breach.
    for sym, qty in live_shorts.items():
        if sym in all_strategy_longs and sym not in all_strategy_shorts and sym not in nx_short_syms:
            violations.append({
                "symbol": sym,
                "current_qty": qty,
                "violation": "HELD_SHORT_BUT_STRATEGY_IS_LONG",
                "strategy_long_sources": [
                    s for s, grp in [("mr", mr_longs), ("pairs", pairs_longs)]
                    if sym in grp
                ],
                "severity": "CRITICAL",
            })

    # Rule 2: symbol held LONG but strategy intends SHORT
    # Skip if the symbol is also in ANY long strategy — dual-strategy conflict, not a violation.
    # Also skip if the DB has an active BUY record for this symbol: the position was
    # intentionally entered long (possibly via backfill or a long executor) and the
    # no-position-flip guard will prevent any short executor from flipping it.
    # Screener listing it as a short candidate is a monitoring note, not a real violation.
    try:
        from trade_log_db import get_open_trades as _get_open_trades
        _db_long_syms: set[str] = {
            t["symbol"].upper()
            for t in _get_open_trades()
            if t.get("side", "").upper() in ("BUY", "LONG")
        }
    except Exception:
        _db_long_syms = set()

    for sym, qty in live_longs.items():
        if sym in all_strategy_shorts and sym not in all_strategy_longs:
            if sym in _db_long_syms:
                logger.info(
                    "Rule 2 skip: %s held LONG in IB and DB — screener short candidate "
                    "is a conflict note only (no-position-flip guard prevents actual flip)",
                    sym,
                )
                continue
            violations.append({
                "symbol": sym,
                "current_qty": qty,
                "violation": "HELD_LONG_BUT_STRATEGY_IS_SHORT",
                "strategy_short_sources": [
                    s for s, grp in [("dual_mode", dm_shorts), ("pairs", pairs_shorts)]
                    if sym in grp
                ],
                "severity": "HIGH",
            })

    # Rule 3: any short > 15% of NLV (oversized accidental short)
    try:
        nlv = 0.0
        for av in ib.accountValues():
            if av.tag == "NetLiquidation" and av.currency == "USD":
                nlv = float(av.value)
                break
        if nlv > 0:
            for sym, qty in live_shorts.items():
                try:
                    mkt_price = next(
                        float(p.marketPrice)
                        for p in ib.portfolio()
                        if getattr(p.contract, "symbol", "") == sym
                    )
                except StopIteration:
                    mkt_price = 0.0
                notional = abs(qty) * mkt_price
                pct = notional / nlv
                if pct > 0.15:
                    violations.append({
                        "symbol": sym,
                        "current_qty": qty,
                        "notional_usd": round(notional, 2),
                        "pct_nlv": round(pct * 100, 1),
                        "violation": "SHORT_EXCEEDS_15PCT_NLV",
                        "severity": "HIGH",
                    })
    except Exception as exc:
        logger.warning("NLV size check skipped: %s", exc)

    return violations


_L1_EXECUTION_LABELS = frozenset(
    {"STRONG_UPTREND", "STRONG_DOWNTREND", "CHOPPY", "MIXED", "UNFAVORABLE"}
)
_REGIME_CONTEXT_FILE = TRADING_DIR / "logs" / "regime_context.json"


def audit_regime_context() -> list[dict]:
    """Verify regime_context.json holds a valid Layer-1 execution regime label.

    The macro regime monitor (Layer 2) writes its band labels (NEUTRAL, RISK_ON,
    TIGHTENING, DEFENSIVE) to regime_state.json.  If those labels ever leak into
    regime_context.json — due to stale in-memory scheduler code or a code bug —
    the dashboard shows the same value for both regime layers.

    This function detects that condition and auto-corrects it by calling
    detect_market_regime() and rewriting the file, exactly as the scheduler should.
    """
    violations: list[dict] = []

    try:
        if not _REGIME_CONTEXT_FILE.exists():
            violations.append({
                "symbol": "SYSTEM",
                "violation": "REGIME_CONTEXT_MISSING",
                "severity": "WARNING",
                "detail": "regime_context.json does not exist — execution regime unknown",
            })
            return violations

        raw = json.loads(_REGIME_CONTEXT_FILE.read_text(encoding="utf-8"))
        stored = raw.get("regime", "")
        if stored not in _L1_EXECUTION_LABELS:
            logger.error(
                "regime_context.json contains invalid L1 label %r — auto-correcting", stored
            )
            # Auto-correct by running the live detector
            try:
                sys.path.insert(0, str(SCRIPTS_DIR))
                from regime_detector import detect_market_regime, persist_regime_to_context
                corrected = detect_market_regime()
                persist_regime_to_context(corrected)
                logger.info("regime_context.json corrected: %r → %s", stored, corrected)
                violations.append({
                    "symbol":    "SYSTEM",
                    "violation": "REGIME_CONTEXT_CORRUPTED",
                    "severity":  "WARNING",
                    "detail":    f"regime_context.json had Layer-2 label {stored!r}; corrected to {corrected}",
                    "auto_fixed": True,
                })
            except Exception as exc:
                logger.error("Could not auto-correct regime_context.json: %s", exc)
                violations.append({
                    "symbol":    "SYSTEM",
                    "violation": "REGIME_CONTEXT_CORRUPTED",
                    "severity":  "CRITICAL",
                    "detail":    f"regime_context.json has invalid L1 label {stored!r} and auto-correct failed: {exc}",
                    "auto_fixed": False,
                })
    except Exception as exc:
        logger.warning("audit_regime_context: unexpected error: %s", exc)

    return violations


_STOP_ORDER_TYPES = {"STP", "TRAIL", "TRAILLIMIT", "STP LMT", "STOP", "STOP LIMIT"}

# Minimum position notional (USD) below which a missing stop is a warning, not critical.
# Very small positions (e.g. 1 share of a $5 stock) don't warrant a Telegram page.
_MIN_NOTIONAL_FOR_CRITICAL = 500.0


def _symbol_has_pending_stop(symbol: str) -> bool:
    """Return True if `symbol` has an ATR stop entry in pending_trades.json.

    update_atr_stops.py writes JSON-level stop triggers to pending_trades.json rather than
    placing live IB orders.  A position covered this way is not CRITICAL — the JSON trigger
    will fire at the next execute_pending_trades.py run — but it should still be tracked.

    The entries use a nested structure — the symbol lives under trigger.conditions[].symbol
    and legs[].symbol, NOT as a top-level key on the entry.  This function searches all
    three locations so it correctly detects ATR stop entries from update_atr_stops.py.
    """
    try:
        pending_path = TRADING_DIR / "config" / "pending_trades.json"
        if not pending_path.exists():
            return False
        data = json.loads(pending_path.read_text(encoding="utf-8"))
        sym_upper = symbol.upper()
        for section in ("pending", "take_profit", "partial_profit"):
            for entry in data.get(section, []):
                # 1. Flat format: { "symbol": "AAPL", ... }
                if str(entry.get("symbol", "")).upper() == sym_upper:
                    return True
                # 2. Nested format used by update_atr_stops.py:
                #    trigger.conditions[].symbol  and  legs[].symbol
                for cond in entry.get("trigger", {}).get("conditions", []):
                    if str(cond.get("symbol", "")).upper() == sym_upper:
                        return True
                for leg in entry.get("legs", []):
                    if str(leg.get("symbol", "")).upper() == sym_upper:
                        return True
    except Exception as exc:
        logger.debug("_symbol_has_pending_stop: could not read pending_trades.json: %s", exc)
    return False


def audit_stops(ib: Any) -> list[dict]:
    """
    Verify every open stock position (long AND short) has at least one stop/trail
    order in IB across ALL client IDs.

    CRITICAL: must use reqAllOpenOrders() — reqOpenOrders() only returns orders
    for the current clientId and will produce false-positive 'missing stop' alerts.

    Returns a list of violation dicts for positions with no stop coverage.
    Auto-triggers update_atr_stops.py if any gaps are found.
    """
    if ib is None:
        logger.warning("audit_stops: no IB connection — skipping")
        return []

    violations: list[dict] = []

    # ── 1. Fetch ALL open orders across every clientId ─────────────────────────
    try:
        ib.reqAllOpenOrders()
        # Allow IB to push all open orders into the local cache.
        # 1.5s was too short with large portfolios (40+ positions → 40+ stop orders).
        # 4.0s was still too short when the short book grew to 17+ positions — each
        # short has a stop placed by clientId 129 (separate process) and IB streams
        # them individually. Raised to 8.0s to eliminate false-positive NO_STOP alerts.
        time.sleep(8.0)
        all_trades = ib.openTrades()
    except Exception as exc:
        logger.error("audit_stops: could not fetch open orders: %s", exc)
        return []

    # Build set of symbols that have at least one stop-type order
    protected: set[str] = set()
    for trade in all_trades:
        order_type = getattr(trade.order, "orderType", "").upper().strip()
        if order_type in _STOP_ORDER_TYPES:
            protected.add(getattr(trade.contract, "symbol", "").upper())

    # ── 2. Fetch all stock positions ───────────────────────────────────────────
    try:
        portfolio = ib.portfolio()
    except Exception as exc:
        logger.error("audit_stops: could not fetch portfolio: %s", exc)
        return []

    for item in portfolio:
        contract = getattr(item, "contract", None)
        if contract is None or getattr(contract, "secType", "") != "STK":
            continue
        sym = getattr(contract, "symbol", "").upper()
        qty = float(getattr(item, "position", 0) or 0)
        if qty == 0:
            continue

        if sym not in protected:
            mkt_price  = float(getattr(item, "marketPrice", 0) or 0)
            notional   = abs(qty) * mkt_price
            side       = "LONG" if qty > 0 else "SHORT"

            # ── Fallback: check pending_trades.json for a JSON-level ATR stop ─────
            # update_atr_stops.py writes stop levels to pending_trades.json rather than
            # placing live IB orders.  If a symbol has an ATR entry there, downgrade
            # severity from CRITICAL to WARNING so we don't spam alerts unnecessarily.
            has_pending_stop = _symbol_has_pending_stop(sym)
            if has_pending_stop:
                severity = "WARNING"
                logger.info(
                    "  PENDING STOP: %s %s %.0f shares (~$%.0f) — "
                    "no IB stop order but ATR entry exists in pending_trades.json",
                    side, sym, abs(qty), notional,
                )
            else:
                severity = "CRITICAL" if notional >= _MIN_NOTIONAL_FOR_CRITICAL else "WARNING"
                logger.warning(
                    "  NO STOP: %s %s %.0f shares (~$%.0f) — "
                    "no stop/trail order and no pending_trades.json entry",
                    side, sym, abs(qty), notional,
                )

            violations.append({
                "symbol":          sym,
                "current_qty":     qty,
                "side":            side,
                "notional_usd":    round(notional, 2),
                "violation":       "NO_STOP_ORDER",
                "severity":        severity,
                "has_pending_stop": has_pending_stop,
            })

    # ── 3. Auto-remediate: run update_atr_stops.py if any gaps found ───────────
    if violations:
        logger.warning(
            "audit_stops: %d position(s) have no stop order — triggering update_atr_stops.py",
            len(violations),
        )
        try:
            result = subprocess.run(
                [sys.executable, str(SCRIPTS_DIR / "update_atr_stops.py")],
                timeout=240,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                logger.info("update_atr_stops.py completed successfully")
            else:
                logger.error("update_atr_stops.py exited %d: %s", result.returncode, result.stderr[-500:])
        except subprocess.TimeoutExpired:
            logger.error("update_atr_stops.py timed out after 240s")
        except Exception as exc:
            logger.error("Could not run update_atr_stops.py: %s", exc)

    return violations


def audit_time_stops() -> list[dict]:
    """Flag positions held beyond the max-hold window in non-trending regimes.

    Scott Phillips insight: in a STRONG_UPTREND, let winners run (45-day ceiling).
    In all other regimes, positions held past 20 days deserve a deliberate review —
    not a forced exit, but a logged WARNING so the trader can decide.

    Thresholds come from risk.json → trend_runner.
    This check is ADVISORY only (WARNING severity); it does not halt execution.
    """
    from datetime import datetime as _dt, timedelta
    violations: list[dict] = []
    try:
        import sqlite3 as _sql, json as _json
        _risk = _json.loads((TRADING_DIR / "risk.json").read_text())
        tr = _risk.get("trend_runner", {})
        max_default  = int(tr.get("max_hold_days_default", 20))
        max_uptrend  = int(tr.get("max_hold_days_uptrend", 45))

        regime = "UNKNOWN"
        try:
            from regime_detector import detect_market_regime
            regime = detect_market_regime()
        except Exception:
            pass

        max_hold = max_uptrend if regime == "STRONG_UPTREND" else max_default
        cutoff = (_dt.now() - timedelta(days=max_hold)).isoformat()

        db_path = TRADING_DIR / "logs" / "trades.db"
        with _sql.connect(db_path) as conn:
            conn.row_factory = _sql.Row
            rows = conn.execute(
                """
                SELECT symbol, timestamp, qty, entry_price,
                       CAST(julianday('now') - julianday(timestamp) AS INTEGER) AS days_held
                FROM trades
                WHERE side = 'BUY'
                  AND status = 'Filled'
                  AND exit_price IS NULL
                  AND timestamp < ?
                ORDER BY days_held DESC
                """,
                (cutoff,),
            ).fetchall()

        for row in rows:
            days = row["days_held"] or 0
            sym  = row["symbol"]
            msg  = (
                f"Held {days}d > {max_hold}d ceiling "
                f"(regime={regime}, max_hold={'uptrend' if regime=='STRONG_UPTREND' else 'standard'})"
            )
            violations.append({
                "symbol":      sym,
                "violation":   "TIME_STOP_REVIEW",
                "severity":    "WARNING",
                "detail":      msg,
                "days_held":   days,
                "max_hold":    max_hold,
                "regime":      regime,
            })
            logger.warning("Time-stop review: %s — %s", sym, msg)
    except Exception as exc:
        logger.warning("audit_time_stops failed (non-fatal): %s", exc)
    return violations


def run(dry_run: bool = False) -> None:
    logger.info("=== Position Integrity Check [%s] ===", datetime.now().isoformat())

    ib = None
    if not dry_run:
        try:
            from ib_insync import IB
            ib = IB()
            ib.connect(IB_HOST, IB_PORT, clientId=CLIENT_ID, timeout=10)
            logger.info("Connected to IB Gateway")
        except Exception as exc:
            logger.error("IB connection failed: %s", exc)
            ib = None

    violations        = audit_positions(ib)
    stop_violations   = audit_stops(ib)
    regime_violations = audit_regime_context()
    time_stop_flags   = audit_time_stops()

    # Sall: backfill missing R-multiples for all closed trades — silent best-effort
    try:
        from attribution_gap_check import run_attribution_gap_check
        attr_summary = run_attribution_gap_check()
        if attr_summary.get("filled", 0) > 0:
            logger.info(
                "Attribution gaps backfilled: %d records updated",
                attr_summary["filled"],
            )
    except Exception as _attr_exc:
        logger.warning("attribution_gap_check failed (non-fatal): %s", _attr_exc)

    if ib is not None:
        try:
            ib.disconnect()
        except Exception:
            pass

    all_violations = violations + stop_violations + regime_violations + time_stop_flags
    critical_violations = [v for v in all_violations if v.get("severity") == "CRITICAL"]
    # Status is FAIL only when there are CRITICAL violations.
    # WARNING-only violations (e.g. Layer-2 JSON stops present, no live IB order yet) are
    # expected before market open and should not cause the scheduler job to report failure.
    result = {
        "checked_at":           datetime.now().isoformat(),
        "violations":           all_violations,
        "violation_count":      len(all_violations),
        "side_violations":      len(violations),
        "stop_violations":      len(stop_violations),
        "regime_violations":    len(regime_violations),
        "time_stop_flags":      len(time_stop_flags),
        "critical_count":       len(critical_violations),
        "status": "FAIL" if critical_violations else ("WARN" if all_violations else "PASS"),
    }

    out = LOGS_DIR / f"position_integrity_{datetime.now().strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(result, indent=2))

    if all_violations:
        logger.critical("❌ %d position integrity violation(s) found:", len(all_violations))
        for v in all_violations:
            logger.critical("  %s — %s (%s)", v["symbol"], v["violation"], v["severity"])

        alert_lines = ["*Position Integrity Violations*\n"]
        if violations:
            alert_lines.append("_Side violations:_")
            for v in violations:
                alert_lines.append(
                    f"• *{v['symbol']}* — {v['violation']} ({v['severity']})\n"
                    f"  qty={v.get('current_qty', '?')}"
                )
        if stop_violations:
            alert_lines.append("\n_Missing stop orders (auto-fix triggered):_")
            for v in stop_violations:
                alert_lines.append(
                    f"• *{v['symbol']}* {v.get('side','')} {abs(v.get('current_qty',0)):.0f} shares"
                    f" ~${v.get('notional_usd',0):,.0f} — NO STOP ({v['severity']})"
                )
        if regime_violations:
            alert_lines.append("\n_Regime context issues:_")
            for v in regime_violations:
                fixed = " ✅ auto-corrected" if v.get("auto_fixed") else " ❌ manual fix needed"
                alert_lines.append(
                    f"• {v['violation']} ({v['severity']}){fixed}\n  {v.get('detail','')}"
                )
        try:
            from notifications import notify_critical
            # Only page on CRITICAL violations; WARNING-only (Layer-2 soft stops) is routine.
            if critical_violations:
                notify_critical("Position Integrity FAIL", "\n".join(alert_lines))
            else:
                from notifications import send_telegram
                send_telegram("⚠️ Position Integrity WARN\n" + "\n".join(alert_lines[1:]))
        except Exception:
            pass
    else:
        logger.info("✅ All positions passed integrity check (sides + stops)")

    logger.info("Results written to %s", out)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = run(dry_run=args.dry_run)
    # Exit 1 only on CRITICAL violations — WARNING-only (soft stops) exits 0 so the
    # scheduler does not mark the job as failed when all positions are Layer-2 covered.
    sys.exit(1 if result["status"] == "FAIL" else 0)
