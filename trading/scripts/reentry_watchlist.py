#!/usr/bin/env python3
"""
Re-entry Watchlist Monitor

After a position is stopped out, this script monitors the stopped-out
symbol for recovery signals so the system can re-enter at a better price
with trend confirmation.

How it works
------------
1. Query ``trades.db`` for trades closed within the last 30 days with
   ``exit_reason = 'stop'`` (stop-loss exits).
2. Load ``trading/reentry_watchlist.json`` (state file).  For each new
   stopped-out symbol, add an entry with:
     - ``exit_price``: the fill price at stop exit
     - ``exit_date``: ISO date of stop exit
     - ``stop_level``: price that triggered the stop
     - ``status``: "watching"
3. For every symbol currently in the watchlist with status "watching":
   a. Fetch latest price and 20-day RSI via yfinance.
   b. Check recovery conditions:
        • Price > exit_price × (1 + RE_ENTRY_BUFFER)  — price has recovered
          above where we were stopped out, plus a small buffer (default 2%)
        • Price > 20-day SMA  — trend has turned positive
        • RSI(14) > 50  — momentum confirmation
   c. If ALL three conditions are met → alert via notifications and set
      status to "signal_ready".
   d. If symbol has been in watchlist > EXPIRE_DAYS (default 45) without
      a signal → set status to "expired".
4. Persist the updated watchlist back to ``reentry_watchlist.json``.

Scheduler integration
---------------------
Run daily at 09:35 ET (post-open), alongside update_atr_stops.py.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).resolve().parent
TRADING_DIR  = SCRIPT_DIR.parent
PROJECT_ROOT = TRADING_DIR.parent

sys.path.insert(0, str(SCRIPT_DIR))

from atomic_io import atomic_write_json          # noqa: E402
from notifications import notify_event           # noqa: E402

DB_PATH        = TRADING_DIR / "logs" / "trades.db"
WATCHLIST_FILE = TRADING_DIR / "reentry_watchlist.json"
LOGS_DIR       = TRADING_DIR / "logs"
LOG_FILE       = LOGS_DIR / "reentry_watchlist.log"

# ── Config ────────────────────────────────────────────────────────────────────
LOOKBACK_DAYS   = 30     # how far back to scan trades.db for stop exits
EXPIRE_DAYS     = 45     # remove a watchlist entry if no signal in N days
RE_ENTRY_BUFFER = 0.02   # require price 2% above exit_price before signalling
RSI_PERIOD      = 14

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    import trade_log_db as _tdb  # noqa: F401  # imported to verify trade_log_db is importable
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_recent_stop_exits(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return trades closed with exit_reason='stop' in the last LOOKBACK_DAYS days."""
    cutoff = (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()
    cur = conn.execute(
        """
        SELECT symbol, exit_price, exit_timestamp, entry_price
          FROM trades
         WHERE exit_reason = 'stop'
           AND exit_timestamp >= ?
           AND exit_price IS NOT NULL
         ORDER BY exit_timestamp DESC
        """,
        (cutoff,),
    )
    rows = cur.fetchall()
    return [dict(r) for r in rows]


# ── Watchlist state ─────────────────────────────────────────────────────────────

def _load_watchlist() -> list[dict[str, Any]]:
    if not WATCHLIST_FILE.exists():
        return []
    try:
        data = json.loads(WATCHLIST_FILE.read_text())
        if isinstance(data, list):
            return data
    except (OSError, ValueError):
        pass
    return []


def _key(entry: dict[str, Any]) -> str:
    """Unique key = symbol + exit_date to handle re-entering the same stock twice."""
    return f"{entry['symbol']}|{entry.get('exit_date', '')}"


def _entry_date(entry: dict[str, Any]) -> date:
    """Return the most recent relevant date for pruning purposes."""
    for field in ("signal_date", "added_date", "exit_date"):
        val = entry.get(field)
        if val:
            try:
                return date.fromisoformat(val)
            except ValueError:
                pass
    return date.min


# ── Technical indicators ────────────────────────────────────────────────────────

def _calc_rsi_wilder(closes: list[float], period: int = RSI_PERIOD) -> float | None:
    """Wilder smoothed RSI. Requires 2*period+1 bars."""
    if len(closes) < period * 2 + 1:
        return None
    seed = closes[: period + 1]
    avg_gain = sum(max(seed[i] - seed[i - 1], 0) for i in range(1, period + 1)) / period
    avg_loss = sum(max(seed[i - 1] - seed[i], 0) for i in range(1, period + 1)) / period
    for close, prev in zip(closes[period + 1:], closes[period:]):
        delta    = close - prev
        avg_gain = (avg_gain * (period - 1) + max(delta, 0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-delta, 0)) / period
    if avg_loss == 0:
        return 100.0
    return round(100 - 100 / (1 + avg_gain / avg_loss), 1)


def _fetch_metrics(symbol: str) -> dict[str, Any] | None:
    """Fetch price, 20-day SMA, and RSI(14) for a symbol."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="3mo", auto_adjust=True)
        if hist.empty or len(hist) < 21:
            return None
        closes = [float(c) for c in hist["Close"].dropna().tolist()]
        price  = closes[-1]
        sma20  = sum(closes[-20:]) / 20
        rsi    = _calc_rsi_wilder(closes)
        return {"price": price, "sma20": sma20, "rsi": rsi}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Metrics fetch failed for %s: %s", symbol, exc)
        return None


# ── Core logic ─────────────────────────────────────────────────────────────────

def _check_reentry_signal(entry: dict[str, Any], metrics: dict[str, Any]) -> bool:
    """Return True when all three recovery conditions are satisfied."""
    price      = metrics.get("price", 0.0)
    sma20      = metrics.get("sma20", 0.0)
    rsi        = metrics.get("rsi")
    exit_price = entry.get("exit_price", 0.0)

    if not exit_price or not price:
        return False

    price_recovered  = price > exit_price * (1 + RE_ENTRY_BUFFER)
    above_sma        = price > sma20
    momentum_bullish = rsi is not None and rsi > 50

    return price_recovered and above_sma and momentum_bullish


def run() -> None:
    if not DB_PATH.exists():
        logger.warning("trades.db not found at %s — skipping", DB_PATH)
        return

    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Pull recent stop exits from DB ─────────────────────────────────
    conn = _connect()
    try:
        stop_exits = _fetch_recent_stop_exits(conn)
    finally:
        conn.close()

    logger.info("Found %d stop exits in last %d days", len(stop_exits), LOOKBACK_DAYS)

    # ── Step 2: Load current watchlist ─────────────────────────────────────────
    watchlist = _load_watchlist()
    existing_keys = {_key(e) for e in watchlist}

    # ── Step 3: Add new stopped-out symbols ───────────────────────────────────
    new_entries = 0
    for trade in stop_exits:
        symbol = (trade.get("symbol") or "").upper()
        if not symbol:
            continue
        exit_ts = trade.get("exit_timestamp") or ""
        exit_date = exit_ts[:10] if len(exit_ts) >= 10 else date.today().isoformat()
        entry_key = f"{symbol}|{exit_date}"
        if entry_key in existing_keys:
            continue
        exit_price = float(trade.get("exit_price") or 0)
        if exit_price <= 0:
            continue
        watchlist.append({
            "symbol":      symbol,
            "exit_price":  exit_price,
            "entry_price": float(trade.get("entry_price") or 0),
            "exit_date":   exit_date,
            "added_date":  date.today().isoformat(),
            "status":      "watching",
            "signal_date": None,
        })
        existing_keys.add(entry_key)
        logger.info("Added %s to re-entry watchlist (exit_price=%.2f)", symbol, exit_price)
        new_entries += 1

    logger.info("Added %d new symbol(s) to watchlist", new_entries)

    # ── Step 4: Check signals for "watching" entries ──────────────────────────
    today = date.today()
    signals_fired: list[str] = []
    expired_count = 0

    for entry in watchlist:
        if entry.get("status") != "watching":
            continue
        symbol    = entry["symbol"]
        added_str = entry.get("added_date") or entry.get("exit_date") or ""
        try:
            added_date = date.fromisoformat(added_str)
        except ValueError:
            added_date = today

        # Expire stale entries
        if (today - added_date).days > EXPIRE_DAYS:
            entry["status"] = "expired"
            expired_count += 1
            logger.info("Expired re-entry watch for %s (added %s)", symbol, added_str)
            continue

        metrics = _fetch_metrics(symbol)
        if not metrics:
            continue

        if _check_reentry_signal(entry, metrics):
            entry["status"]      = "signal_ready"
            entry["signal_date"] = today.isoformat()
            signals_fired.append(symbol)
            logger.info(
                "RE-ENTRY SIGNAL: %s — price=%.2f (exit=%.2f), SMA20=%.2f, RSI=%.1f",
                symbol,
                metrics["price"],
                entry["exit_price"],
                metrics["sma20"],
                metrics.get("rsi") or 0,
            )
            notify_event(
                "reentry_signal",
                subject=f"📈 Re-entry Signal: {symbol}",
                body=(
                    f"{symbol} has recovered from its stop-loss exit.\n\n"
                    f"  Exit price : ${entry['exit_price']:.2f}\n"
                    f"  Current    : ${metrics['price']:.2f} "
                    f"(+{(metrics['price']/entry['exit_price']-1)*100:.1f}%)\n"
                    f"  SMA-20     : ${metrics['sma20']:.2f}\n"
                    f"  RSI(14)    : {metrics.get('rsi') or 'N/A'}\n\n"
                    "All three recovery conditions met:\n"
                    "  ✅ Price > exit × 1.02\n"
                    "  ✅ Price > 20-day SMA\n"
                    "  ✅ RSI > 50 (bullish momentum)\n\n"
                    "Review the position for potential re-entry."
                ),
                urgent=False,
            )
        else:
            logger.debug(
                "No signal yet for %s — price=%.2f, SMA20=%.2f, RSI=%s",
                symbol,
                metrics.get("price", 0),
                metrics.get("sma20", 0),
                metrics.get("rsi"),
            )

    logger.info(
        "Re-entry scan complete — %d signal(s) fired, %d expired, %d still watching",
        len(signals_fired),
        expired_count,
        sum(1 for e in watchlist if e.get("status") == "watching"),
    )

    # ── Step 5: Prune stale completed/expired entries ─────────────────────────
    # Keep "watching" entries always; prune "signal_ready" and "expired" that
    # are older than EXPIRE_DAYS + 30 days so the file doesn't grow unboundedly.
    prune_cutoff = today - timedelta(days=EXPIRE_DAYS + 30)
    before_prune = len(watchlist)
    watchlist = [
        e for e in watchlist
        if e.get("status") == "watching"
        or _entry_date(e) >= prune_cutoff
    ]
    pruned = before_prune - len(watchlist)
    if pruned:
        logger.info("Pruned %d stale completed/expired entries from watchlist", pruned)

    # ── Step 6: Persist ───────────────────────────────────────────────────────
    atomic_write_json(WATCHLIST_FILE, watchlist)
    logger.info("Watchlist saved to %s", WATCHLIST_FILE)


if __name__ == "__main__":
    run()
