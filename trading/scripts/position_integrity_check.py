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
import sys
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


def _mr_long_symbols() -> set[str]:
    """Symbols the MR executor currently tracks as active longs."""
    data = _load_json_safe(TRADING_DIR / "logs" / "mr_positions.json")
    if not isinstance(data, dict):
        return set()
    syms = data.get("symbols", [])
    return {s.strip().upper() for s in syms if isinstance(s, str) and s.strip()}


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
    mr_longs       = _mr_long_symbols()
    dm_shorts      = _dual_mode_short_symbols()
    pairs_longs    = _pairs_long_symbols()
    pairs_shorts   = _pairs_short_symbols()

    all_strategy_longs  = mr_longs  | pairs_longs
    all_strategy_shorts = dm_shorts | pairs_shorts

    # Rule 1: symbol held SHORT but strategy intends LONG
    for sym, qty in live_shorts.items():
        if sym in all_strategy_longs:
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
    for sym, qty in live_longs.items():
        if sym in all_strategy_shorts:
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

    violations = audit_positions(ib)

    if ib is not None:
        try:
            ib.disconnect()
        except Exception:
            pass

    result = {
        "checked_at": datetime.now().isoformat(),
        "violations": violations,
        "violation_count": len(violations),
        "status": "FAIL" if violations else "PASS",
    }

    out = LOGS_DIR / f"position_integrity_{datetime.now().strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(result, indent=2))

    if violations:
        logger.critical("❌ %d position integrity violation(s) found:", len(violations))
        for v in violations:
            logger.critical("  %s — %s (%s)", v["symbol"], v["violation"], v["severity"])

        alert_lines = ["*Position Integrity Violations*\n"]
        for v in violations:
            alert_lines.append(
                f"• *{v['symbol']}* — {v['violation']} ({v['severity']})\n"
                f"  qty={v.get('current_qty', '?')}"
            )
        try:
            from notifications import notify_critical
            notify_critical("Position Integrity FAIL", "\n".join(alert_lines))
        except Exception:
            pass
    else:
        logger.info("✅ All positions passed integrity check")

    logger.info("Results written to %s", out)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = run(dry_run=args.dry_run)
    sys.exit(0 if result["status"] == "PASS" else 1)
