#!/usr/bin/env python3
"""
Attribution Gap Check — auto-compute missing R-multiples in trades.db.

Amrit Sall (Unknown Market Wizards): clean, complete records are foundational.
You cannot improve what you cannot measure.  The strategy attribution report
is only as good as the R-multiple data it draws from.

Lukas Fröhlich (Next Generation): derive take-profit targets from actual MFE
data grouped by strategy.  This script also builds mfe_targets.json — a
lookup table of P90 MFE (in ATR units) per strategy, which atr_stops.py
uses to set historically-calibrated TP levels instead of fixed multiples.

This script finds all closed trades in trades.db that have an exit_price but
no r_multiple and back-fills the R-multiple from available data:

  Priority 1: stop_price is recorded → stop_distance = entry_price - stop_price
  Priority 2: atr_at_entry is recorded → stop_distance = atr_at_entry × stop_mult
  Priority 3: entry_price only → use a 5% fallback stop

Formula:
  r_multiple = (exit_price - entry_price) / stop_distance   [for longs]
  r_multiple = (entry_price - exit_price) / stop_distance   [for shorts]

Also computes holding_days if it is NULL, from timestamp → exit_timestamp.

Runs:
  - Daily as part of position_integrity_check.py (audit_attribution_gaps)
  - Can also be run standalone:  python3 attribution_gap_check.py

Side effects:
  - UPDATE trades SET r_multiple = ?, holding_days = ? where missing.
  - Writes logs/mfe_targets.json with per-strategy P90 MFE in ATR units.
  - Logs a summary of how many records were fixed.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from paths import TRADING_DIR

logger = logging.getLogger(__name__)

DB_PATH = TRADING_DIR / "logs" / "trades.db"
MFE_TARGETS_FILE = TRADING_DIR / "logs" / "mfe_targets.json"
FALLBACK_STOP_PCT = 0.05   # 5% of entry price when no ATR data


def _load_stop_mult() -> float:
    try:
        from adaptive_config_loader import get_adaptive_float
        return get_adaptive_float("stop_atr_mult", 1.5)
    except ImportError:
        pass
    try:
        _risk = json.loads((TRADING_DIR / "risk.json").read_text())
        return float(_risk.get("trend_runner", {}).get("stop_atr_mult_default", 1.5))
    except Exception:
        return 1.5


def _compute_r_multiple(
    side: str,
    entry_price: float,
    exit_price: float,
    stop_price: float | None,
    atr_at_entry: float | None,
    stop_mult: float,
) -> float | None:
    """Return the R-multiple for a closed trade, or None if insufficient data."""
    if entry_price <= 0 or exit_price <= 0:
        return None

    if stop_price and stop_price > 0:
        if side.upper() == "BUY":
            stop_dist = entry_price - stop_price
        else:
            stop_dist = stop_price - entry_price
    elif atr_at_entry and atr_at_entry > 0:
        stop_dist = atr_at_entry * stop_mult
    else:
        stop_dist = entry_price * FALLBACK_STOP_PCT

    if stop_dist <= 0:
        return None

    if side.upper() == "BUY":
        r = (exit_price - entry_price) / stop_dist
    else:
        r = (entry_price - exit_price) / stop_dist

    return round(r, 3)


def _compute_holding_days(
    timestamp: str | None,
    exit_timestamp: str | None,
) -> int | None:
    """Return holding_days from ISO timestamps, or None on parse error."""
    if not timestamp or not exit_timestamp:
        return None
    try:
        fmt = "%Y-%m-%dT%H:%M:%S"
        def _parse(s: str) -> datetime:
            # Handle fractional seconds and various ISO formats
            for f in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(s[:26], f[:len(f)])
                except ValueError:
                    continue
            return datetime.fromisoformat(s[:19])
        entry_dt = _parse(timestamp)
        exit_dt  = _parse(exit_timestamp)
        return max(0, (exit_dt - entry_dt).days)
    except Exception:
        return None


def _build_mfe_targets() -> dict:
    """Build a per-strategy MFE target table from closed trades.

    Lukas Fröhlich (Next Generation): TP targets should be derived from
    empirical MFE data, not fixed ATR multiples.  For each strategy, we
    query all closed winning trades, compute MFE as a multiple of the
    initial 1R stop distance, and store the P90 (top 10%) as the TP target.

    The resulting file (logs/mfe_targets.json) is consumed by atr_stops.py
    to set historically-calibrated TP levels at runtime.

    MFE proxy: we use the trade's exit_price as a lower bound for MFE since
    we don't record price peaks mid-trade.  For winning trades this gives a
    conservative but usable estimate.  Future improvement: record actual MFE
    from live fills.

    Returns a dict keyed by strategy label, value = {"p90_atr": float, "n": int}.
    """
    try:
        cfg = json.loads((TRADING_DIR / "risk.json").read_text()).get("statistical_tp", {})
    except Exception:
        cfg = {}

    if not cfg.get("enabled", True):
        return {}

    min_samples = int(cfg.get("min_samples", 10))
    percentile = float(cfg.get("mfe_percentile", 90))
    stop_mult = _load_stop_mult()

    targets: dict[str, dict] = {}

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT strategy, side, entry_price, exit_price, stop_price,
                       atr_at_entry, r_multiple
                FROM trades
                WHERE exit_price IS NOT NULL
                  AND entry_price IS NOT NULL
                  AND entry_price > 0
                  AND exit_price > 0
                """
            ).fetchall()
    except Exception as exc:
        logger.warning("MFE targets: DB read failed — %s", exc)
        return {}

    # Group winning trades by strategy and compute MFE in ATR units
    from collections import defaultdict
    strategy_mfe: dict[str, list[float]] = defaultdict(list)

    for row in rows:
        strategy = str(row["strategy"] or "unknown")
        side = str(row["side"] or "BUY").upper()
        entry_price = float(row["entry_price"])
        exit_price = float(row["exit_price"])
        atr = float(row["atr_at_entry"]) if row["atr_at_entry"] else None

        # Only use winning trades for MFE estimation
        if side in ("BUY", "LONG") and exit_price <= entry_price:
            continue
        if side in ("SELL", "SHORT") and exit_price >= entry_price:
            continue

        # Compute MFE in price terms (lower bound: use exit as MFE proxy)
        if side in ("BUY", "LONG"):
            mfe_price = exit_price - entry_price
        else:
            mfe_price = entry_price - exit_price

        # Convert to ATR units
        if atr and atr > 0:
            mfe_atr = mfe_price / atr
        else:
            stop_price = row["stop_price"]
            if stop_price and float(stop_price) > 0:
                stop_dist = abs(entry_price - float(stop_price))
                mfe_atr = mfe_price / stop_dist if stop_dist > 0 else None
            else:
                mfe_atr = mfe_price / (entry_price * FALLBACK_STOP_PCT)

        if mfe_atr and mfe_atr > 0:
            strategy_mfe[strategy].append(mfe_atr)

    for strategy, mfe_list in strategy_mfe.items():
        if len(mfe_list) < min_samples:
            logger.debug(
                "MFE targets: strategy '%s' only has %d samples (need %d) — skipped",
                strategy, len(mfe_list), min_samples,
            )
            continue

        sorted_mfe = sorted(mfe_list)
        idx = int(len(sorted_mfe) * percentile / 100)
        p90 = sorted_mfe[min(idx, len(sorted_mfe) - 1)]
        targets[strategy] = {"p90_atr": round(p90, 3), "n": len(mfe_list)}
        logger.info(
            "MFE targets: strategy '%s' P%.0f MFE = %.2f ATR (n=%d)",
            strategy, percentile, p90, len(mfe_list),
        )

    if targets:
        try:
            MFE_TARGETS_FILE.parent.mkdir(parents=True, exist_ok=True)
            MFE_TARGETS_FILE.write_text(json.dumps({
                "updated": __import__("datetime").datetime.now().isoformat(),
                "percentile": percentile,
                "targets": targets,
            }, indent=2))
            logger.info("MFE targets written to %s (%d strategies)", MFE_TARGETS_FILE, len(targets))
        except Exception as exc:
            logger.warning("Could not write MFE targets file: %s", exc)

    return targets


def run_attribution_gap_check() -> dict:
    """Find and backfill missing R-multiples in trades.db, then build MFE targets.

    Returns a summary dict: {"checked": N, "filled": N, "unfixable": N, "mfe_strategies": N}.
    """
    stop_mult = _load_stop_mult()
    summary = {"checked": 0, "filled": 0, "unfixable": 0, "mfe_strategies": 0}

    if not DB_PATH.exists():
        logger.warning("trades.db not found at %s — skipping attribution gap check", DB_PATH)
        return summary

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, symbol, side, entry_price, exit_price, stop_price,
                   atr_at_entry, r_multiple, timestamp, exit_timestamp, holding_days
            FROM trades
            WHERE exit_price IS NOT NULL
              AND (r_multiple IS NULL OR holding_days IS NULL)
            """
        ).fetchall()

        summary["checked"] = len(rows)
        if not rows:
            logger.info("Attribution gap check: all closed trades already have R-multiples ✅")
            return summary

        logger.info("Attribution gap check: found %d closed trades missing R/hold data", len(rows))

        filled = 0
        unfixable = 0
        for row in rows:
            trade_id    = row["id"]
            symbol      = row["symbol"]
            side        = row["side"] or "BUY"
            entry_price = float(row["entry_price"] or 0)
            exit_price  = float(row["exit_price"] or 0)
            stop_price  = float(row["stop_price"]) if row["stop_price"] else None
            atr         = float(row["atr_at_entry"]) if row["atr_at_entry"] else None
            r_existing  = row["r_multiple"]
            hold_existing = row["holding_days"]

            updates: dict[str, object] = {}

            # Compute R-multiple if missing
            if r_existing is None:
                r = _compute_r_multiple(side, entry_price, exit_price, stop_price, atr, stop_mult)
                if r is not None:
                    updates["r_multiple"] = r
                else:
                    unfixable += 1
                    logger.debug("Cannot compute R for trade %d (%s) — insufficient price data", trade_id, symbol)

            # Compute holding_days if missing
            if hold_existing is None:
                hd = _compute_holding_days(row["timestamp"], row["exit_timestamp"])
                if hd is not None:
                    updates["holding_days"] = hd

            if not updates:
                continue

            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [trade_id]
            conn.execute(f"UPDATE trades SET {set_clause} WHERE id = ?", values)  # noqa: S608
            filled += 1
            logger.debug(
                "Backfilled %s (id=%d): %s",
                symbol, trade_id, {k: v for k, v in updates.items()},
            )

        conn.commit()
        summary["filled"]    = filled
        summary["unfixable"] = unfixable
        logger.info(
            "Attribution gap check complete: %d fixed, %d unfixable (no stop or ATR data)",
            filled, unfixable,
        )

    # Fröhlich: build MFE-derived TP targets after R-multiple backfill is done
    try:
        mfe_targets = _build_mfe_targets()
        summary["mfe_strategies"] = len(mfe_targets)
    except Exception as exc:
        logger.warning("MFE target build failed (non-fatal): %s", exc)

    return summary


if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [attribution_gap_check] %(levelname)s — %(message)s",
    )
    result = run_attribution_gap_check()
    print(
        f"Attribution gap check: checked={result['checked']} "
        f"filled={result['filled']} unfixable={result['unfixable']}"
    )
    sys.exit(0 if result["unfixable"] == 0 else 1)
