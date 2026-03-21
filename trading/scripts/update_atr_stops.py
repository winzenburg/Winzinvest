#!/usr/bin/env python3
"""
Daily ATR Stop Updater

Runs every morning at 9:35 AM ET (after the open settles).
For every long stock position currently held in IBKR:

  1. Fetch the 14-period ATR via yfinance
  2. Compute new_stop = current_price - (1.5 × ATR)
  3. Apply the ratchet rule: new_stop = max(existing_stop, new_stop)
     — stops only move UP, never down
  4. If no stop entry exists yet, create one automatically
  5. Write updated stops back to pending_trades.json atomically

This ensures every position always has a live stop, and winning
positions naturally trail their stops upward each day.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── path bootstrap ────────────────────────────────────────────────────────────
_scripts_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_scripts_dir))

from paths import TRADING_DIR
from atomic_io import atomic_write_json

_env_path = TRADING_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# ── logging ───────────────────────────────────────────────────────────────────
LOG_DIR = TRADING_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "update_atr_stops.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

CONFIG_DIR  = TRADING_DIR / "config"
PENDING_FILE = CONFIG_DIR / "pending_trades.json"

STOP_ATR_MULT       = 1.5
PARTIAL_TP_ATR_MULT = 2.0   # scale-out target: sell 50% of position at 2× ATR above entry
TP_ATR_MULT         = 3.5   # full TP target: sell remaining 50% at 3.5× ATR above entry
SCALE_OUT_PCT       = 0.50  # fraction of shares to sell at partial TP
# Symbols to never place stops on (hedges, inverse ETFs)
SKIP_SYMBOLS  = {"TZA", "SQQQ", "SPXU", "SDOW", "SPXS"}

IB_HOST   = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT   = int(os.getenv("IB_PORT", "4001"))
CLIENT_ID = 129   # dedicated client ID for ATR stop updater


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_pending() -> dict:
    if PENDING_FILE.exists():
        return json.loads(PENDING_FILE.read_text(encoding="utf-8"))
    return {"pending": [], "take_profit": [], "completed": []}


def _stop_entry_id(sym: str) -> str:
    return f"{sym.lower()}-stop-exit"


def _existing_stop_price(pending: list[dict], sym: str) -> Optional[float]:
    """Return the current stop price for sym if an entry exists, else None."""
    entry_id = _stop_entry_id(sym)
    for trade in pending:
        if trade.get("id") == entry_id:
            for cond in trade.get("trigger", {}).get("conditions", []):
                if cond.get("type") == "price_below" and cond.get("symbol", "").upper() == sym:
                    return float(cond["price"])
    return None


def _build_stop_entry(sym: str, avg_cost: float, qty: int, stop_price: float,
                      atr: float, has_cc: bool, cc_strike: Optional[float],
                      cc_expiry: Optional[str], cc_qty: int) -> dict:
    """Build a fresh stop entry dict for pending_trades.json."""
    stop_pct = (stop_price - avg_cost) / avg_cost * 100
    max_loss  = (stop_price - avg_cost) * qty
    legs = []

    if has_cc and cc_strike and cc_expiry and cc_qty > 0:
        legs.append({
            "step": 1,
            "action": "BUY_TO_CLOSE",
            "symbol": sym,
            "secType": "OPT",
            "right": "C",
            "strike": cc_strike,
            "expiry": cc_expiry,
            "qty": cc_qty,
            "order_type": "LMT",
            "notes": f"Close {cc_qty}x {sym} ${cc_strike}C covered call first"
        })
        legs.append({
            "step": 2,
            "action": "SELL",
            "symbol": sym,
            "secType": "STK",
            "qty": qty,
            "order_type": "MKT",
            "notes": f"Exit full {sym} position — ATR stop triggered at ${stop_price:.2f}"
        })
    else:
        legs.append({
            "step": 1,
            "action": "SELL",
            "symbol": sym,
            "secType": "STK",
            "qty": qty,
            "order_type": "MKT",
            "notes": f"Exit full {sym} position — ATR stop triggered at ${stop_price:.2f}"
        })

    return {
        "id": _stop_entry_id(sym),
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "description": (
            f"ATR STOP: {'BTC + ' if has_cc else ''}sell {qty} {sym} if price ≤ "
            f"${stop_price:.2f} (1.5× ATR ${atr:.2f} below avg ${avg_cost:.2f})"
        ),
        "status": "pending",
        "trigger": {
            "conditions": [{
                "type": "price_below",
                "symbol": sym,
                "price": stop_price,
                "note": f"ATR stop: 1.5 × ATR(${atr:.2f}) = ${atr * STOP_ATR_MULT:.2f} below avg_cost ${avg_cost:.2f}"
            }]
        },
        "legs": legs,
        "rationale": {
            "entry_price": avg_cost,
            "stop_price": stop_price,
            "atr_14": round(atr, 2),
            "stop_atr_mult": STOP_ATR_MULT,
            "stop_pct": round(stop_pct, 1),
            "max_loss_per_share": round(stop_price - avg_cost, 2),
            "max_loss_total": round(max_loss, 0),
            "last_updated": datetime.now().isoformat(),
        },
        "executed_at": None,
        "execution_log": []
    }


def _partial_tp_entry_id(sym: str) -> str:
    return f"{sym.lower()}-partial-tp"


def _full_tp_entry_id(sym: str) -> str:
    return f"{sym.lower()}-tp-exit"


def _existing_trigger_price(entries: list[dict], entry_id: str, sym: str,
                             trigger_type: str) -> Optional[float]:
    """Return the current trigger price for a specific entry id and condition type."""
    for t in entries:
        if t.get("id") == entry_id:
            for cond in t.get("trigger", {}).get("conditions", []):
                if (cond.get("type") == trigger_type
                        and cond.get("symbol", "").upper() == sym):
                    return float(cond["price"])
    return None


def _build_partial_tp_entry(sym: str, avg_cost: float, qty: int,
                             tp_price: float, atr: float,
                             partial_qty: int, remaining_qty: int) -> dict:
    """Build a partial TP entry that sells ~50% of the position at 2× ATR."""
    gain_pct = (tp_price - avg_cost) / avg_cost * 100
    return {
        "id": _partial_tp_entry_id(sym),
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "description": (
            f"ATR PARTIAL TP: sell {partial_qty} {sym} (50%) if price ≥ "
            f"${tp_price:.2f} (2× ATR ${atr:.2f} above avg ${avg_cost:.2f})"
        ),
        "status": "pending",
        "trigger": {
            "conditions": [{
                "type": "price_above",
                "symbol": sym,
                "price": tp_price,
                "note": (
                    f"Partial TP: 2× ATR(${atr:.2f}) = +${atr * PARTIAL_TP_ATR_MULT:.2f} "
                    f"above avg ${avg_cost:.2f}"
                ),
            }]
        },
        "legs": [{
            "step": 1,
            "action": "SELL",
            "symbol": sym,
            "secType": "STK",
            "qty": partial_qty,
            "order_type": "MKT",
            "notes": f"Scale out 50% of {sym} at 2× ATR — bank gains, let rest run",
        }],
        "rationale": {
            "entry_price": avg_cost,
            "partial_tp_price": tp_price,
            "atr_14": round(atr, 2),
            "tp_atr_mult": PARTIAL_TP_ATR_MULT,
            "gain_pct": round(gain_pct, 1),
            "partial_qty": partial_qty,
            "remaining_qty": remaining_qty,
            "last_updated": datetime.now().isoformat(),
        },
        "on_execute": {
            "reduce_linked_tp_id": _full_tp_entry_id(sym),
            "reduce_linked_tp_qty_to": remaining_qty,
        },
        "executed_at": None,
        "execution_log": [],
    }


def _build_full_tp_entry(sym: str, avg_cost: float, qty: int,
                         tp_price: float, atr: float) -> dict:
    """Build a full TP entry that sells the remaining position at 3.5× ATR."""
    gain_pct = (tp_price - avg_cost) / avg_cost * 100
    return {
        "id": _full_tp_entry_id(sym),
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "description": (
            f"ATR TAKE-PROFIT: sell {qty} {sym} if price ≥ "
            f"${tp_price:.2f} (3.5× ATR ${atr:.2f} above avg ${avg_cost:.2f})"
        ),
        "status": "pending",
        "trigger": {
            "conditions": [{
                "type": "price_above",
                "symbol": sym,
                "price": tp_price,
                "note": (
                    f"Full TP: 3.5× ATR(${atr:.2f}) = +${atr * TP_ATR_MULT:.2f} "
                    f"above avg ${avg_cost:.2f}"
                ),
            }]
        },
        "legs": [{
            "step": 1,
            "action": "SELL",
            "symbol": sym,
            "secType": "STK",
            "qty": qty,
            "order_type": "MKT",
            "notes": f"Full exit of remaining {sym} position at 3.5× ATR target",
        }],
        "rationale": {
            "entry_price": avg_cost,
            "tp_price": tp_price,
            "atr_14": round(atr, 2),
            "tp_atr_mult": TP_ATR_MULT,
            "gain_pct": round(gain_pct, 1),
            "last_updated": datetime.now().isoformat(),
        },
        "executed_at": None,
        "execution_log": [],
    }


# ── Short stop helpers ────────────────────────────────────────────────────────

def _short_stop_entry_id(sym: str) -> str:
    return f"{sym.lower()}-short-stop"


def _short_tp_entry_id(sym: str) -> str:
    return f"{sym.lower()}-short-tp"


def _existing_short_stop_price(pending: list[dict], sym: str) -> Optional[float]:
    """Return the current cover-stop price for a short position, or None."""
    entry_id = _short_stop_entry_id(sym)
    for trade in pending:
        if trade.get("id") == entry_id:
            for cond in trade.get("trigger", {}).get("conditions", []):
                if cond.get("type") == "price_above" and cond.get("symbol", "").upper() == sym:
                    return float(cond["price"])
    return None


def _build_short_stop_entry(sym: str, avg_cost: float, qty: int,
                             stop_price: float, tp_price: float, atr: float) -> dict:
    """
    Build a pending_trades entry that covers a short if the price rises to stop_price.
    stop_price = avg_cost + 1.5 × ATR  (loss limit — cover to cut loss)
    tp_price   = avg_cost - 3.5 × ATR  (profit target — cover to lock gain)
    """
    stop_pct     = (stop_price - avg_cost) / avg_cost * 100
    max_loss      = round((stop_price - avg_cost) * qty, 0)
    cover_leg: dict = {
        "step": 1,
        "action": "BUY",
        "symbol": sym,
        "secType": "STK",
        "qty": qty,
        "order_type": "MKT",
        "notes": f"Cover {qty} {sym} short — ATR stop triggered at ${stop_price:.2f}",
    }
    return {
        "id": _short_stop_entry_id(sym),
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "description": (
            f"SHORT STOP: cover {qty} {sym} if price ≥ ${stop_price:.2f} "
            f"(1.5× ATR ${atr:.2f} above avg short ${avg_cost:.2f}). "
            f"Take-profit at ${tp_price:.2f} (3.5× ATR below avg)."
        ),
        "status": "pending",
        "trigger": {
            "conditions": [{
                "type": "price_above",
                "symbol": sym,
                "price": stop_price,
                "note": (
                    f"Short stop: 1.5 × ATR(${atr:.2f}) = ${atr * STOP_ATR_MULT:.2f} "
                    f"above avg_cost ${avg_cost:.2f}"
                ),
            }]
        },
        "legs": [cover_leg],
        "rationale": {
            "side": "SHORT",
            "entry_price": avg_cost,
            "stop_price": stop_price,
            "tp_price": tp_price,
            "atr_14": round(atr, 2),
            "stop_atr_mult": STOP_ATR_MULT,
            "tp_atr_mult": TP_ATR_MULT,
            "stop_pct": round(stop_pct, 1),
            "max_loss_per_share": round(stop_price - avg_cost, 2),
            "max_loss_total": max_loss,
            "last_updated": datetime.now().isoformat(),
        },
        "executed_at": None,
        "execution_log": [],
    }


def _build_short_tp_entry(sym: str, avg_cost: float, qty: int,
                           tp_price: float, atr: float) -> dict:
    """Cover a short at take-profit when price drops to tp_price."""
    return {
        "id": _short_tp_entry_id(sym),
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "description": (
            f"SHORT TP: cover {qty} {sym} if price ≤ ${tp_price:.2f} "
            f"(3.5× ATR ${atr:.2f} below avg short ${avg_cost:.2f})."
        ),
        "status": "pending",
        "trigger": {
            "conditions": [{
                "type": "price_below",
                "symbol": sym,
                "price": tp_price,
                "note": (
                    f"Short TP: 3.5 × ATR(${atr:.2f}) = ${atr * TP_ATR_MULT:.2f} "
                    f"below avg_cost ${avg_cost:.2f}"
                ),
            }]
        },
        "legs": [{
            "step": 1,
            "action": "BUY",
            "symbol": sym,
            "secType": "STK",
            "qty": qty,
            "order_type": "MKT",
            "notes": f"Cover {qty} {sym} short — take-profit at ${tp_price:.2f}",
        }],
        "rationale": {
            "side": "SHORT",
            "entry_price": avg_cost,
            "tp_price": tp_price,
            "atr_14": round(atr, 2),
            "tp_atr_mult": TP_ATR_MULT,
            "last_updated": datetime.now().isoformat(),
        },
        "executed_at": None,
        "execution_log": [],
    }


def _get_ib_short_positions() -> dict[str, dict]:
    """
    Connect to IBKR and return {symbol: {qty (positive abs value), avg_cost}}
    for all short stock positions.
    """
    try:
        import logging as _logging
        from ib_insync import IB
        _logging.getLogger("ib_insync").setLevel(_logging.CRITICAL)
    except ImportError:
        logger.error("ib_insync not installed")
        return {}

    ib = IB()
    for port in [IB_PORT, 4001, 7496, 7497]:
        try:
            ib.connect(IB_HOST, port, clientId=CLIENT_ID + 1, timeout=15)
            break
        except Exception:
            continue

    if not ib.isConnected():
        logger.error("Cannot connect to IBKR for short positions")
        return {}

    result: dict[str, dict] = {}
    try:
        for p in ib.positions():
            c = p.contract
            sym = c.symbol.upper()
            if c.secType == "STK" and p.position < 0 and sym not in SKIP_SYMBOLS:
                result[sym] = {
                    "qty": abs(int(p.position)),
                    "avg_cost": float(p.avgCost),
                }
    finally:
        ib.disconnect()

    return result


def _get_ib_positions() -> dict[str, dict]:
    """
    Connect to IBKR and return {symbol: {qty, avg_cost, short_calls: [(strike, expiry, qty)]}}
    for all long stock positions.
    """
    try:
        import logging as _logging
        from ib_insync import IB
        _logging.getLogger("ib_insync").setLevel(_logging.CRITICAL)
    except ImportError:
        logger.error("ib_insync not installed")
        return {}

    ib = IB()
    for port in [IB_PORT, 4001, 7496, 7497]:
        try:
            ib.connect(IB_HOST, port, clientId=CLIENT_ID, timeout=15)
            break
        except Exception:
            continue

    if not ib.isConnected():
        logger.error("Cannot connect to IBKR — skipping stop update")
        return {}

    result: dict[str, dict] = {}
    try:
        for p in ib.positions():
            c = p.contract
            sym = c.symbol.upper()
            if c.secType == "STK" and p.position > 0 and sym not in SKIP_SYMBOLS:
                result[sym] = {
                    "qty": int(p.position),
                    "avg_cost": float(p.avgCost),
                    "short_calls": [],
                }
            elif c.secType == "OPT" and p.position < 0 and c.right.upper() == "C":
                sym = c.symbol.upper()
                if sym not in result:
                    result[sym] = {"qty": 0, "avg_cost": 0.0, "short_calls": []}
                result[sym]["short_calls"].append((
                    float(c.strike),
                    c.lastTradeDateOrContractMonth,
                    abs(int(p.position)),
                ))
    finally:
        ib.disconnect()

    return {k: v for k, v in result.items() if v["qty"] > 0}


def run() -> None:
    logger.info("=== ATR Stop Updater — %s ===", datetime.now().strftime("%Y-%m-%d %H:%M"))

    from atr_stops import fetch_atr

    positions = _get_ib_positions()
    if not positions:
        logger.warning("No positions returned from IBKR — nothing to update")
        return

    logger.info("Loaded %d long stock position(s) from IBKR", len(positions))

    data    = _load_pending()
    pending = data.get("pending", [])

    # Build a mutable index of existing stop entries by id
    stop_index: dict[str, int] = {
        t.get("id"): i for i, t in enumerate(pending)
    }

    updated, created, unchanged, skipped = [], [], [], []
    atr_cache: dict[str, float] = {}  # avoid fetching ATR twice per symbol

    for sym, pos in positions.items():
        qty      = pos["qty"]
        avg_cost = pos["avg_cost"]
        calls    = pos.get("short_calls", [])

        # Pick the nearest-expiry call if multiple
        cc_strike: Optional[float] = None
        cc_expiry: Optional[str]   = None
        cc_qty    = 0
        if calls:
            calls_sorted = sorted(calls, key=lambda x: x[1])  # sort by expiry
            cc_strike, cc_expiry, cc_qty = calls_sorted[0]

        # Fetch ATR — cache to avoid a second network call in the TP loop
        atr = fetch_atr(sym)
        if not atr:
            logger.warning("  %s: ATR unavailable — skipping", sym)
            skipped.append(sym)
            continue
        atr_cache[sym] = atr

        new_stop = round(avg_cost - atr * STOP_ATR_MULT, 2)
        existing = _existing_stop_price(pending, sym)

        # Ratchet rule — stops only move UP
        if existing is not None:
            if new_stop <= existing:
                logger.info(
                    "  %s: stop unchanged $%.2f (new=$%.2f ≤ existing) ATR=$%.2f",
                    sym, existing, new_stop, atr,
                )
                unchanged.append(sym)
                # Still update the rationale/atr fields without changing price
                entry_id = _stop_entry_id(sym)
                if entry_id in stop_index:
                    idx = stop_index[entry_id]
                    pending[idx]["rationale"]["atr_14"] = round(atr, 2)
                    pending[idx]["rationale"]["last_updated"] = datetime.now().isoformat()
                continue

            # Stop moves up
            entry_id = _stop_entry_id(sym)
            if entry_id in stop_index:
                idx = stop_index[entry_id]
                old_stop = existing
                pending[idx]["trigger"]["conditions"][0]["price"] = new_stop
                pending[idx]["trigger"]["conditions"][0]["note"] = (
                    f"ATR stop: 1.5 × ATR(${atr:.2f}) = ${atr * STOP_ATR_MULT:.2f} "
                    f"below avg_cost ${avg_cost:.2f}"
                )
                pending[idx]["rationale"].update({
                    "stop_price": new_stop,
                    "atr_14": round(atr, 2),
                    "stop_pct": round((new_stop - avg_cost) / avg_cost * 100, 1),
                    "max_loss_per_share": round(new_stop - avg_cost, 2),
                    "max_loss_total": round((new_stop - avg_cost) * qty, 0),
                    "last_updated": datetime.now().isoformat(),
                })
                pending[idx]["description"] = (
                    f"ATR STOP: {'BTC + ' if calls else ''}sell {qty} {sym} if price ≤ "
                    f"${new_stop:.2f} (1.5× ATR ${atr:.2f} below avg ${avg_cost:.2f})"
                )
                logger.info(
                    "  %s: stop raised $%.2f → $%.2f (+$%.2f) ATR=$%.2f",
                    sym, old_stop, new_stop, new_stop - old_stop, atr,
                )
                updated.append(f"{sym}: ${old_stop:.2f}→${new_stop:.2f}")
        else:
            # No stop entry yet — create one
            new_entry = _build_stop_entry(
                sym, avg_cost, qty, new_stop, atr,
                has_cc=bool(calls), cc_strike=cc_strike,
                cc_expiry=cc_expiry, cc_qty=cc_qty,
            )
            pending.append(new_entry)
            stop_index[new_entry["id"]] = len(pending) - 1
            logger.info(
                "  %s: NEW stop created at $%.2f (ATR=$%.2f, avg=$%.2f)",
                sym, new_stop, atr, avg_cost,
            )
            created.append(f"{sym}: ${new_stop:.2f}")

    data["pending"] = pending

    # ── Partial TP + Full TP updates ─────────────────────────────────────────
    # Only for non-CC positions — the options engine manages upside on CC positions.
    partial_profit = data.get("partial_profit", [])
    take_profit    = data.get("take_profit", [])

    partial_tp_index: dict[str, int] = {t.get("id"): i for i, t in enumerate(partial_profit)}
    full_tp_index:    dict[str, int] = {t.get("id"): i for i, t in enumerate(take_profit)}

    tp_updated, tp_created, partial_updated, partial_created = [], [], [], []

    for sym, pos in positions.items():
        calls = pos.get("short_calls", [])
        if calls:
            continue  # CC positions — options engine handles upside

        qty      = pos["qty"]
        avg_cost = pos["avg_cost"]

        atr = atr_cache.get(sym) or fetch_atr(sym)
        if not atr:
            continue  # already logged in the stop loop above

        partial_qty   = max(1, qty // 2)
        remaining_qty = qty - partial_qty
        partial_price = round(avg_cost + atr * PARTIAL_TP_ATR_MULT, 2)
        full_tp_price = round(avg_cost + atr * TP_ATR_MULT, 2)

        # ── Partial TP (2× ATR, 50% of shares) ───────────────────────────────
        partial_id     = _partial_tp_entry_id(sym)
        existing_part  = _existing_trigger_price(partial_profit, partial_id, sym, "price_above")

        if existing_part is not None:
            if partial_price > existing_part:   # ratchet — only move up
                idx = partial_tp_index[partial_id]
                partial_profit[idx]["trigger"]["conditions"][0]["price"] = partial_price
                partial_profit[idx]["rationale"].update({
                    "partial_tp_price": partial_price,
                    "atr_14": round(atr, 2),
                    "last_updated": datetime.now().isoformat(),
                })
                partial_profit[idx]["description"] = (
                    f"ATR PARTIAL TP: sell {partial_qty} {sym} (50%) if price ≥ "
                    f"${partial_price:.2f} (2× ATR ${atr:.2f} above avg ${avg_cost:.2f})"
                )
                partial_updated.append(f"{sym}: ${existing_part:.2f}→${partial_price:.2f}")
                logger.info("  %s: partial TP raised $%.2f → $%.2f", sym, existing_part, partial_price)
        else:
            entry = _build_partial_tp_entry(
                sym, avg_cost, qty, partial_price, atr, partial_qty, remaining_qty
            )
            partial_profit.append(entry)
            partial_tp_index[partial_id] = len(partial_profit) - 1
            partial_created.append(f"{sym}: ${partial_price:.2f}")
            logger.info(
                "  %s: NEW partial TP created at $%.2f (sell %d of %d shares)",
                sym, partial_price, partial_qty, qty,
            )

        # ── Full TP (3.5× ATR, remaining shares after partial) ────────────────
        full_tp_id    = _full_tp_entry_id(sym)
        existing_full = _existing_trigger_price(take_profit, full_tp_id, sym, "price_above")

        if existing_full is not None:
            if full_tp_price > existing_full:   # ratchet — only move up
                idx = full_tp_index[full_tp_id]
                current_qty = take_profit[idx].get("legs", [{}])[0].get("qty", remaining_qty)
                take_profit[idx]["trigger"]["conditions"][0]["price"] = full_tp_price
                take_profit[idx]["rationale"].update({
                    "tp_price": full_tp_price,
                    "atr_14": round(atr, 2),
                    "last_updated": datetime.now().isoformat(),
                })
                take_profit[idx]["description"] = (
                    f"ATR TAKE-PROFIT: sell {current_qty} {sym} if price ≥ "
                    f"${full_tp_price:.2f} (3.5× ATR ${atr:.2f} above avg ${avg_cost:.2f})"
                )
                tp_updated.append(f"{sym}: ${existing_full:.2f}→${full_tp_price:.2f}")
                logger.info("  %s: full TP raised $%.2f → $%.2f", sym, existing_full, full_tp_price)
        else:
            entry = _build_full_tp_entry(sym, avg_cost, remaining_qty, full_tp_price, atr)
            take_profit.append(entry)
            full_tp_index[full_tp_id] = len(take_profit) - 1
            tp_created.append(f"{sym}: ${full_tp_price:.2f} (qty={remaining_qty})")
            logger.info(
                "  %s: NEW full TP created at $%.2f (sell %d remaining shares)",
                sym, full_tp_price, remaining_qty,
            )

    data["partial_profit"] = partial_profit
    data["take_profit"]    = take_profit

    # ── Short stop + TP processing ────────────────────────────────────────────
    short_positions = _get_ib_short_positions()
    short_updated, short_created, short_unchanged, short_skipped = [], [], [], []

    if short_positions:
        logger.info("")
        logger.info("Processing %d short position(s)...", len(short_positions))

        # Re-index pending now (may have grown from long stop creation above)
        short_stop_index: dict[str, int] = {t.get("id"): i for i, t in enumerate(pending)}
        take_profit_list = data.get("take_profit", [])
        short_tp_index: dict[str, int] = {t.get("id"): i for i, t in enumerate(take_profit_list)}

        for sym, pos in short_positions.items():
            qty      = pos["qty"]
            avg_cost = pos["avg_cost"]

            atr = atr_cache.get(sym) or fetch_atr(sym)
            if not atr:
                logger.warning("  %s (short): ATR unavailable — skipping", sym)
                short_skipped.append(sym)
                continue
            atr_cache[sym] = atr

            # For shorts: stop = cover if price RISES above entry + 1.5×ATR
            #             TP   = cover if price FALLS below entry - 3.5×ATR
            new_stop = round(avg_cost + atr * STOP_ATR_MULT, 2)
            new_tp   = round(avg_cost - atr * TP_ATR_MULT, 2)

            existing_stop = _existing_short_stop_price(pending, sym)

            if existing_stop is not None:
                # Ratchet rule inverted for shorts: stop only moves DOWN
                # (as price falls, we lower the stop to lock in gains)
                if new_stop >= existing_stop:
                    logger.info(
                        "  %s (short): stop unchanged $%.2f (new=$%.2f ≥ existing) ATR=$%.2f",
                        sym, existing_stop, new_stop, atr,
                    )
                    short_unchanged.append(sym)
                    # Still refresh rationale/ATR
                    entry_id = _short_stop_entry_id(sym)
                    if entry_id in short_stop_index:
                        idx = short_stop_index[entry_id]
                        pending[idx]["rationale"]["atr_14"] = round(atr, 2)
                        pending[idx]["rationale"]["last_updated"] = datetime.now().isoformat()
                else:
                    # Stop moves down (tighter, locking in more profit on the short)
                    entry_id = _short_stop_entry_id(sym)
                    if entry_id in short_stop_index:
                        idx = short_stop_index[entry_id]
                        pending[idx]["trigger"]["conditions"][0]["price"] = new_stop
                        pending[idx]["rationale"].update({
                            "stop_price": new_stop,
                            "tp_price": new_tp,
                            "atr_14": round(atr, 2),
                            "last_updated": datetime.now().isoformat(),
                        })
                        pending[idx]["description"] = (
                            f"SHORT STOP: cover {qty} {sym} if price ≥ ${new_stop:.2f} "
                            f"(1.5× ATR ${atr:.2f} above avg short ${avg_cost:.2f}). "
                            f"Take-profit at ${new_tp:.2f}."
                        )
                        logger.info(
                            "  %s (short): stop tightened $%.2f → $%.2f ATR=$%.2f",
                            sym, existing_stop, new_stop, atr,
                        )
                        short_updated.append(f"{sym}: ${existing_stop:.2f}→${new_stop:.2f}")
            else:
                # No stop yet — create both stop and TP entries
                stop_entry = _build_short_stop_entry(sym, avg_cost, qty, new_stop, new_tp, atr)
                pending.append(stop_entry)
                short_stop_index[stop_entry["id"]] = len(pending) - 1
                logger.info(
                    "  %s (short): NEW stop created at $%.2f (ATR=$%.2f, avg=$%.2f)",
                    sym, new_stop, atr, avg_cost,
                )

                tp_entry = _build_short_tp_entry(sym, avg_cost, qty, new_tp, atr)
                take_profit_list.append(tp_entry)
                short_tp_index[tp_entry["id"]] = len(take_profit_list) - 1
                logger.info(
                    "  %s (short): NEW take-profit created at $%.2f",
                    sym, new_tp,
                )
                short_created.append(f"{sym}: stop=${new_stop:.2f} / tp=${new_tp:.2f}")

        data["pending"]     = pending
        data["take_profit"] = take_profit_list

    # ── Single atomic save ────────────────────────────────────────────────────
    atomic_write_json(PENDING_FILE, data)

    logger.info("")
    logger.info("═══ STOP UPDATE COMPLETE ═══")
    logger.info("  Stops updated:    %d  %s", len(updated),         updated)
    logger.info("  Stops created:    %d  %s", len(created),         created)
    logger.info("  Stops unchanged:  %d  %s", len(unchanged),       unchanged)
    logger.info("  Stops skipped:    %d  %s", len(skipped),         skipped)
    logger.info("  Partial TPs upd:  %d  %s", len(partial_updated), partial_updated)
    logger.info("  Partial TPs new:  %d  %s", len(partial_created), partial_created)
    logger.info("  Full TPs updated: %d  %s", len(tp_updated),      tp_updated)
    logger.info("  Full TPs created: %d  %s", len(tp_created),      tp_created)
    logger.info("  Short stops new:  %d  %s", len(short_created),   short_created)
    logger.info("  Short stops upd:  %d  %s", len(short_updated),   short_updated)
    logger.info("  Short stops skip: %d  %s", len(short_skipped),   short_skipped)

    # Send notification if anything changed
    any_changes = any([updated, created, partial_updated, partial_created,
                       tp_updated, tp_created, short_created, short_updated])
    if any_changes:
        try:
            from notifications import notify_info
            stop_lines    = "\n".join(f"  ↑ stop {s}" for s in updated) + \
                            "\n".join(f"  + stop {s}" for s in created)
            partial_lines = "\n".join(f"  ↑ pTP {s}" for s in partial_updated) + \
                            "\n".join(f"  + pTP {s}" for s in partial_created)
            tp_lines      = "\n".join(f"  ↑ TP {s}" for s in tp_updated) + \
                            "\n".join(f"  + TP {s}" for s in tp_created)
            short_lines   = "\n".join(f"  + short stop {s}" for s in short_created) + \
                            "\n".join(f"  ↓ short stop {s}" for s in short_updated)
            notify_info(
                f"📐 <b>ATR Levels Updated</b>\n"
                f"{stop_lines}{partial_lines}{tp_lines}{short_lines}"
            )
        except Exception:
            pass


if __name__ == "__main__":
    run()
