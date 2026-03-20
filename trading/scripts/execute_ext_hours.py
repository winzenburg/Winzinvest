#!/usr/bin/env python3
"""
Extended-Hours Executor — place LIMIT orders outside regular trading hours.

Sessions supported (ET):
  Pre-market  :  4:00 AM –  9:29 AM
  After-hours : 16:01 PM –  8:00 PM  (20:00)

All orders are LIMIT with outsideRth=True. Market orders are NOT supported
by IBKR in extended sessions. tif defaults to DAY (expires end of current
extended session); use GTC to persist across sessions.

Watchlist:  trading/watchlist_ext_hours.json
Log:        trading/logs/ext_hours.log
            trading/logs/executions.json  (shared)
            trading/logs/trades.db        (shared)

Run:
    python execute_ext_hours.py           # live — places real orders
    python execute_ext_hours.py --dry-run # simulate, no orders placed
    python execute_ext_hours.py --force   # skip session-window check
"""

import argparse
import contextlib
import json
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Generator

from ib_insync import IB, LimitOrder, Stock

from paths import TRADING_DIR
from pre_trade_guard import PreTradeViolation, assert_no_flip
from trade_log_db import insert_trade

_env_path = TRADING_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "4001"))
CLIENT_ID = 115  # dedicated ext-hours client ID

WATCHLIST   = TRADING_DIR / "watchlist_ext_hours.json"
EXEC_LOG    = TRADING_DIR / "logs" / "executions_ext_hours.jsonl"
KILL_SWITCH = TRADING_DIR / "kill_switch.json"
PID_FILE    = TRADING_DIR / "logs" / "execute_ext_hours.pid"


@contextlib.contextmanager
def _pid_lock(pid_path: Path) -> Generator[None, None, None]:
    """Prevent concurrent pre-market and after-hours runs from overlapping."""
    if pid_path.exists():
        try:
            existing_pid = int(pid_path.read_text().strip())
            os.kill(existing_pid, 0)
            logger.error(
                "Another ext-hours instance is already running (PID %d). Exiting.", existing_pid
            )
            sys.exit(0)
        except (ProcessLookupError, ValueError):
            logger.warning("Stale ext-hours PID file — previous run may have crashed. Continuing.")
    pid_path.write_text(str(os.getpid()))
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            pid_path.unlink()

LIMIT_OFFSET_BUY  = 0.003   # bid up 0.3 % to favour fill
LIMIT_OFFSET_SELL = 0.003   # bid down 0.3 % to favour fill

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ext_hours] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(TRADING_DIR / "logs" / "ext_hours.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# ── Session helpers ──────────────────────────────────────────────────────────

def _now_et() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        et = ZoneInfo("America/New_York")
    except ImportError:
        try:
            from dateutil import tz as _tz
            et = _tz.gettz("America/New_York")
        except ImportError:
            # Last resort: detect offset from current UTC vs local offset
            import time
            is_dst = time.daylight and time.localtime().tm_isdst > 0
            et = timezone(timedelta(hours=-4 if is_dst else -5))
    return datetime.now(tz=et)


def _in_extended_session() -> tuple[bool, str]:
    """Return (in_session, session_name). session_name is 'pre-market', 'after-hours', or ''."""
    now = _now_et()
    if now.weekday() >= 5:
        return False, ""
    hour, minute = now.hour, now.minute
    total = hour * 60 + minute
    if 240 <= total < 570:     # 4:00–9:29 AM
        return True, "pre-market"
    if 961 <= total < 1200:    # 4:01–8:00 PM
        return True, "after-hours"
    return False, ""


# ── Kill-switch ──────────────────────────────────────────────────────────────

def _kill_switch_active() -> tuple[bool, str]:
    try:
        ks = json.loads(KILL_SWITCH.read_text())
        if ks.get("active"):
            return True, ks.get("reason", "kill switch active")
        return False, ""
    except FileNotFoundError:
        return False, ""
    except Exception as exc:
        # Fail closed: unreadable state file is treated as active kill switch
        # to prevent trading when we cannot confirm it's safe to do so.
        reason = f"kill switch file unreadable — failing closed ({exc})"
        logger.error("Kill switch read error: %s", exc)
        return True, reason


# ── Price helper ─────────────────────────────────────────────────────────────

def _get_last_price(ib: IB, symbol: str) -> float | None:
    """Return last/market price from IB portfolio or live quote."""
    for item in ib.portfolio():
        if getattr(item.contract, "symbol", "") == symbol and \
                getattr(item.contract, "secType", "") == "STK":
            mp = item.marketPrice
            if mp and mp > 0:
                return float(mp)
    # Fallback: request live snapshot
    try:
        contract = Stock(symbol, "SMART", "USD")
        ib.qualifyContracts(contract)
        ticker = ib.reqMktData(contract, "", True, False)
        ib.sleep(2)
        price = ticker.last or ticker.close or ticker.bid
        ib.cancelMktData(contract)
        if price and price > 0:
            return float(price)
    except Exception as e:
        logger.warning("Could not get live price for %s: %s", symbol, e)
    return None


def _get_position_qty(ib: IB, symbol: str) -> float:
    for pos in ib.positions():
        if getattr(pos.contract, "secType", "") == "STK" and \
                getattr(pos.contract, "symbol", "").upper() == symbol.upper():
            return float(pos.position)
    return 0.0


# ── Order execution ──────────────────────────────────────────────────────────

def _place_order(
    ib: IB,
    symbol: str,
    action: str,
    qty: int,
    limit_price: float,
    tif: str,
    note: str,
    dry_run: bool,
) -> dict[str, Any]:
    """Qualify, place, and log one extended-hours limit order. Returns result dict."""
    contract = Stock(symbol, "SMART", "USD")
    ib.qualifyContracts(contract)

    order = LimitOrder(action.upper(), qty, round(limit_price, 2))
    order.outsideRth = True
    order.tif = tif.upper()

    result: dict[str, Any] = {
        "symbol":       symbol,
        "action":       action.upper(),
        "qty":          qty,
        "limit_price":  round(limit_price, 2),
        "tif":          tif.upper(),
        "note":         note,
        "dry_run":      dry_run,
        "timestamp":    datetime.now().isoformat(),
        "status":       "DRY_RUN" if dry_run else "PENDING",
        "order_id":     None,
    }

    if dry_run:
        logger.info(
            "[DRY-RUN] Would place %s %s %d @ $%.2f (outsideRth=True tif=%s)",
            action.upper(), symbol, qty, limit_price, tif.upper()
        )
        return result

    trade = ib.placeOrder(contract, order)
    result["order_id"] = trade.order.orderId

    # Wait up to 30s for fill. Extended-hours limit orders often take time.
    # Only log to trades.db on a confirmed fill — logging a pending order
    # creates ghost trades in the journal and breaks open-position tracking.
    for _ in range(30):
        ib.sleep(1)
        status = trade.orderStatus.status
        if status == "Filled":
            break
        if status in ("Cancelled", "ApiCancelled", "Inactive"):
            break

    result["status"]   = trade.orderStatus.status
    result["fill_qty"] = trade.orderStatus.filled
    result["avg_px"]   = trade.orderStatus.avgFillPrice

    logger.info(
        "Placed %s %s %d @ $%.2f | status=%s orderId=%d",
        action.upper(), symbol, qty, limit_price,
        result["status"], result["order_id"],
    )

    # Only persist to trades.db when we have a confirmed fill
    if action.upper() == "BUY" and result["status"] == "Filled":
        fill_px = float(result["avg_px"] or limit_price)
        insert_trade({
            "symbol":        symbol,
            "action":        "BUY",
            "side":          "BUY",
            "qty":           qty,
            "entry_price":   round(fill_px, 4),
            "strategy":      "ext_hours",
            "source_script": "execute_ext_hours.py",
            "status":        "Filled",
            "reason":        note or "Extended-hours entry",
            "timestamp":     result["timestamp"],
            "order_id":      str(result["order_id"]),
        })
    elif action.upper() == "BUY" and result["status"] != "Filled":
        logger.warning(
            "BUY %s NOT logged to trades.db — order status is '%s', not Filled.",
            symbol, result["status"],
        )

    # Append to executions log (JSONL format — one record per line)
    _append_execution_log(result)

    return result


def _append_execution_log(record: dict[str, Any]) -> None:
    """Append one execution record as a JSONL line (append mode — no read/write race)."""
    EXEC_LOG.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record) + "\n"
    with open(EXEC_LOG, "a", encoding="utf-8") as fh:
        fh.write(line)


# ── Notifications ─────────────────────────────────────────────────────────────

def _notify(msg: str) -> None:
    try:
        from notifications import is_event_enabled, notify_info
        if not is_event_enabled("trade_executed"):
            return
        notify_info(msg)
    except Exception as e:
        logger.warning("Telegram notification failed: %s", e)


# ── Main ─────────────────────────────────────────────────────────────────────

def run(dry_run: bool = False, force_session: bool = False) -> None:
    # Session window check
    in_session, session_name = _in_extended_session()
    if not in_session and not force_session:
        logger.error(
            "Not currently in an extended-hours session. "
            "Pre-market: 4:00–9:29 AM ET | After-hours: 4:01–8:00 PM ET. "
            "Use --force to override."
        )
        sys.exit(1)
    if in_session:
        logger.info("Extended-hours session: %s ✅", session_name)

    # Kill switch — block BUYs, allow SELLs (position reduces are always permitted)
    ks_active, ks_reason = _kill_switch_active()
    if ks_active:
        logger.warning("Kill switch ACTIVE: %s — BUY orders will be skipped", ks_reason)

    # Load watchlist — silently exit if empty (safe for scheduled runs)
    if not WATCHLIST.exists():
        logger.info("Watchlist not found: %s — nothing to do (scheduled no-op). ✅", WATCHLIST)
        return

    # Reject stale watchlists (> 4 h old during market/extended hours)
    wl_age_hours = (datetime.now().timestamp() - WATCHLIST.stat().st_mtime) / 3600
    if wl_age_hours > 4:
        logger.warning(
            "Extended-hours watchlist is %.1f h old — skipping to avoid trading stale signals.",
            wl_age_hours,
        )
        return

    try:
        raw: list = json.loads(WATCHLIST.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Could not read watchlist %s: %s", WATCHLIST, exc)
        return
    orders = [o for o in raw if isinstance(o, dict) and "symbol" in o]
    if not orders:
        logger.info("Watchlist has no orders — nothing to do (scheduled no-op). ✅")
        return

    logger.info("Loaded %d order(s) from watchlist", len(orders))

    # Connect to IB
    ib = IB()
    ib.connect(IB_HOST, IB_PORT, clientId=CLIENT_ID, timeout=15)
    logger.info("Connected to IBKR on port %d", IB_PORT)

    results: list[dict[str, Any]] = []

    try:
        for entry in orders:
            symbol     = str(entry.get("symbol", "")).strip().upper()
            action     = str(entry.get("action", "BUY")).strip().upper()
            qty_raw    = entry.get("qty")
            limit_raw  = entry.get("limit_price")
            tif        = str(entry.get("tif", "DAY")).strip().upper()
            note       = str(entry.get("note", ""))

            if not symbol:
                logger.warning("Skipping entry with no symbol: %s", entry)
                continue

            # Kill switch blocks new BUYs
            if ks_active and action == "BUY":
                logger.warning("SKIP %s BUY — kill switch active", symbol)
                continue

            # Resolve quantity — null/omit = close full position
            if qty_raw is None or qty_raw == 0:
                live_qty = _get_position_qty(ib, symbol)
                if live_qty == 0:
                    logger.warning("SKIP %s — no live position to close", symbol)
                    continue
                qty = abs(int(live_qty))
                logger.info("%s qty=None → closing full position (%d shares)", symbol, qty)
            else:
                qty = int(qty_raw)

            if qty <= 0:
                logger.warning("SKIP %s — qty resolved to 0", symbol)
                continue

            # Pre-trade flip guard — only check for new entries, not close-outs.
            # SELL-to-close on an existing long is not a short entry.
            if action == "BUY":
                try:
                    assert_no_flip(ib, symbol, "BUY")
                except PreTradeViolation as e:
                    logger.error("SKIP %s — %s", symbol, e)
                    continue

            # Resolve limit price — auto-price from last market price if not specified
            if limit_raw:
                limit_price = float(limit_raw)
            else:
                last = _get_last_price(ib, symbol)
                if last is None:
                    logger.error("SKIP %s — could not determine price for auto-limit", symbol)
                    continue
                if action == "BUY":
                    limit_price = round(last * (1 + LIMIT_OFFSET_BUY), 2)
                else:
                    limit_price = round(last * (1 - LIMIT_OFFSET_SELL), 2)
                logger.info("%s auto-limit: $%.2f (last=$%.2f offset=%.1f%%)",
                            symbol, limit_price, last,
                            LIMIT_OFFSET_BUY * 100 if action == "BUY" else LIMIT_OFFSET_SELL * 100)

            result = _place_order(ib, symbol, action, qty, limit_price, tif, note, dry_run)
            results.append(result)

        # Summary Telegram message
        if results:
            lines = [f"<b>Extended-Hours Orders {'(DRY-RUN) ' if dry_run else ''}— {session_name or 'manual'}</b>"]
            for r in results:
                fill_status = r.get("status", "?")
                px          = r.get("avg_px")
                px_str      = f" filled @ ${px:.2f}" if px and float(px) > 0 else ""
                lines.append(
                    f"  {r['action']} {r['symbol']} {r['qty']}sh "
                    f"lim=${r['limit_price']:.2f} {r.get('tif','DAY')} → {fill_status}{px_str}"
                )
            _notify("\n".join(lines))

        placed = sum(1 for r in results if not r.get("dry_run"))
        dry    = sum(1 for r in results if r.get("dry_run"))
        logger.info("Done. Placed: %d | Dry-run: %d | Skipped: %d",
                    placed, dry, len(orders) - len(results))
    finally:
        ib.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Place extended-hours LIMIT orders via IBKR")
    parser.add_argument("--dry-run",  action="store_true", help="Simulate — no real orders placed")
    parser.add_argument("--force",    action="store_true", help="Skip session-window check")
    args = parser.parse_args()
    with _pid_lock(PID_FILE):
        run(dry_run=args.dry_run, force_session=args.force)
