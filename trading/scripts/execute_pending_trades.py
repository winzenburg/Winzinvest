#!/usr/bin/env python3
"""
Pending Trades Executor

Reads trading/config/pending_trades.json and executes any trades whose
trigger conditions have been met (date window + portfolio state checks).

Designed to run at market open via the scheduler. Each trade is executed
only once — once triggered it is moved to the `completed` section.

Trigger types supported:
  - not_before: ISO date string, trade will not execute before this date
  - symbol_not_in_portfolio: confirms a symbol is no longer held (e.g. called away)

Legs are executed sequentially. Step 1 must fill before Step 2 places.
"""

import contextlib
import json
import logging
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Generator

from paths import TRADING_DIR

_env_path = TRADING_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

LOG_DIR = TRADING_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_DIR = TRADING_DIR / "config"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "execute_pending_trades.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

PENDING_FILE = CONFIG_DIR / "pending_trades.json"
IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "4001"))
CLIENT_ID = 195  # dedicated client ID for pending trade executor
PID_FILE  = LOG_DIR / "execute_pending_trades.pid"


@contextlib.contextmanager
def _pid_lock(pid_path: Path) -> Generator[None, None, None]:
    """Prevent concurrent runs via a PID file. Exits immediately if already running."""
    if pid_path.exists():
        try:
            existing_pid = int(pid_path.read_text().strip())
            # Check whether that process is still alive
            os.kill(existing_pid, 0)
            logger.error(
                "Another instance is already running (PID %d). Exiting.", existing_pid
            )
            sys.exit(0)
        except (ProcessLookupError, ValueError):
            # Stale PID file — previous run crashed
            logger.warning("Stale PID file found — previous run may have crashed. Continuing.")
    pid_path.write_text(str(os.getpid()))
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            pid_path.unlink()


# ── File helpers ──────────────────────────────────────────────────────────────

def _load_pending() -> dict[str, Any]:
    if not PENDING_FILE.exists():
        return {"pending": [], "completed": []}
    try:
        return json.loads(PENDING_FILE.read_text())
    except Exception as exc:
        logger.error("Failed to read pending_trades.json: %s", exc)
        return {"pending": [], "completed": []}


def _save_pending(data: dict[str, Any]) -> None:
    try:
        PENDING_FILE.write_text(json.dumps(data, indent=2))
    except Exception as exc:
        logger.error("Failed to write pending_trades.json: %s", exc)


# ── Trigger evaluation ────────────────────────────────────────────────────────

def _check_triggers(trade: dict[str, Any], ib_positions: dict[str, int]) -> tuple[bool, str]:
    """Return (ready, reason). ready=True means all conditions are met."""
    trigger = trade.get("trigger", {})
    today = date.today()

    not_before_str = trigger.get("not_before")
    if not_before_str:
        not_before = date.fromisoformat(not_before_str)
        if today < not_before:
            return False, f"not_before {not_before_str} has not passed (today={today})"

    for cond in trigger.get("conditions", []):
        ctype = cond.get("type")
        sym = (cond.get("symbol") or "").upper()

        if ctype == "symbol_not_in_portfolio":
            if sym in ib_positions:
                qty = ib_positions[sym]
                return False, f"{sym} still in portfolio (qty={qty}) — LYB assignment not yet settled"

    return True, "all conditions met"


# ── Order placement ───────────────────────────────────────────────────────────

def _place_stock_order(ib: Any, sym: str, qty: int, action: str) -> tuple[bool, float]:
    """Buy or sell shares at market. Returns (success, fill_price)."""
    from ib_insync import Stock, MarketOrder
    contract = Stock(sym, "SMART", "USD")
    qualified = ib.qualifyContracts(contract)
    if not qualified:
        logger.error("Could not qualify stock contract for %s", sym)
        return False, 0.0
    order = MarketOrder(action, qty)
    trade = ib.placeOrder(qualified[0], order)
    # Wait up to 30s for fill
    for _ in range(30):
        ib.sleep(1)
        status = getattr(trade.orderStatus, "status", "")
        if status == "Filled":
            fill = float(trade.orderStatus.avgFillPrice or 0)
            logger.info("STK %s %s %d filled @ $%.4f", action, sym, qty, fill)
            return True, fill
        if status in ("Cancelled", "ApiCancelled", "Inactive"):
            logger.error("STK order %s %s cancelled: %s", action, sym, status)
            return False, 0.0
    # Fail closed: do NOT treat a pending order as filled. A $0 fill price on a
    # partially-executed multi-leg trade would log garbage and could place a
    # covered call on shares we don't hold (naked short).
    logger.error(
        "STK %s %s: order still PENDING after 30s — aborting leg (status=%s). "
        "Cancel the order manually if needed.",
        action, sym, status,
    )
    return False, 0.0


def _place_option_order(ib: Any, sym: str, expiry: str, strike: float, right: str,
                         qty: int, action: str) -> tuple[bool, float]:
    """Sell (or buy) an options contract at market. Returns (success, fill_price)."""
    from ib_insync import Option, MarketOrder
    contract = Option(sym, expiry, strike, right, "SMART", currency="USD")
    qualified = ib.qualifyContracts(contract)
    if not qualified:
        logger.error("Could not qualify option %s %s $%s%s exp %s", action, sym, strike, right, expiry)
        return False, 0.0
    order = MarketOrder(action, qty)
    trade = ib.placeOrder(qualified[0], order)
    for _ in range(30):
        ib.sleep(1)
        status = getattr(trade.orderStatus, "status", "")
        if status == "Filled":
            fill = float(trade.orderStatus.avgFillPrice or 0)
            logger.info("OPT %s %s %s$%s exp %s filled @ $%.4f", action, sym, right, strike, expiry, fill)
            return True, fill
        if status in ("Cancelled", "ApiCancelled", "Inactive"):
            logger.error("OPT order %s %s cancelled: %s", action, sym, status)
            return False, 0.0
    logger.error(
        "OPT %s %s: order still PENDING after 30s — aborting leg (status=%s). "
        "Cancel the order manually if needed.",
        action, sym, status,
    )
    return False, 0.0


# ── Trade log ─────────────────────────────────────────────────────────────────

def _log_to_trades_db(sym: str, side: str, qty: int, price: float,
                       strategy: str, source: str) -> None:
    """Insert a filled trade record into trades.db."""
    try:
        from trade_log_db import log_trade
        log_trade(
            symbol=sym,
            action=side,
            qty=qty,
            price=price,
            entry_price=price,
            stop_price=None,
            strategy=strategy,
            source_script=source,
        )
        logger.info("Logged to trades.db: %s %s %d @ $%.4f", side, sym, qty, price)
    except Exception as exc:
        logger.warning("Could not log to trades.db (non-fatal): %s", exc)


# ── Main executor ─────────────────────────────────────────────────────────────

def run() -> None:
    with _pid_lock(PID_FILE):
        _run_inner()


def _run_inner() -> None:
    data = _load_pending()
    pending = data.get("pending", [])
    if not pending:
        logger.info("No pending trades in queue — nothing to do")
        return

    logger.info("Found %d pending trade(s) — checking triggers", len(pending))

    # Connect to IBKR to check portfolio and place orders
    try:
        from ib_insync import IB
        import logging as _logging
        _logging.getLogger("ib_insync").setLevel(_logging.CRITICAL)
    except ImportError:
        logger.error("ib_insync not installed — cannot execute pending trades")
        return

    ib = IB()
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=CLIENT_ID, timeout=15)
        logger.info("Connected to IBKR (port %d)", IB_PORT)
    except Exception as exc:
        logger.error("Cannot connect to IBKR: %s", exc)
        return

    still_pending: list[dict[str, Any]] = []
    newly_completed: list[dict[str, Any]] = []

    try:
        # Build current portfolio snapshot
        ib_positions: dict[str, int] = {}
        for p in ib.positions():
            c = p.contract
            if c.secType == "STK":
                ib_positions[c.symbol.upper()] = int(p.position)

        for trade in pending:
            trade_id = trade.get("id", "?")
            desc = trade.get("description", "")
            logger.info("Checking: %s — %s", trade_id, desc)

            ready, reason = _check_triggers(trade, ib_positions)
            if not ready:
                logger.info("  Not ready: %s", reason)
                still_pending.append(trade)
                continue

            logger.info("  ✓ Triggers met — executing now")
            execution_log: list[str] = []
            success = True
            fill_details: dict[str, float] = {}

            for leg in sorted(trade.get("legs", []), key=lambda x: x.get("step", 1)):
                step     = leg.get("step", 1)
                action   = leg.get("action", "BUY").upper()
                sym      = (leg.get("symbol") or "").upper()
                sec_type = leg.get("secType", "STK").upper()
                qty      = int(leg.get("qty", 0))
                notes    = leg.get("notes", "")

                logger.info("  Leg %d: %s %s %s x%d — %s", step, action, sec_type, sym, qty, notes)

                if sec_type == "STK":
                    ok, fill = _place_stock_order(ib, sym, qty, action)
                    if ok:
                        fill_details[f"leg{step}_fill"] = fill
                        execution_log.append(
                            f"Leg {step}: {action} {qty} {sym} @ ${fill:.4f} — OK"
                        )
                        # Brief pause for broker to process the fill before placing the next leg
                        time.sleep(3)
                        _log_to_trades_db(sym, action, qty, fill,
                                          strategy="pending_cc", source="execute_pending_trades.py")
                    else:
                        execution_log.append(f"Leg {step}: {action} {qty} {sym} — FAILED")
                        success = False
                        break

                elif sec_type == "OPT":
                    expiry = leg.get("expiry", "")
                    strike = float(leg.get("strike", 0))
                    right  = leg.get("right", "C").upper()
                    ok, fill = _place_option_order(ib, sym, expiry, strike, right, qty, action)
                    if ok:
                        fill_details[f"leg{step}_fill"] = fill
                        execution_log.append(
                            f"Leg {step}: {action} {qty} {sym} {right}${strike} {expiry} @ ${fill:.4f} — OK"
                        )
                        _log_to_trades_db(
                            f"{sym}{right}{int(strike)}", action, qty, fill,
                            strategy="covered_call", source="execute_pending_trades.py",
                        )
                    else:
                        execution_log.append(
                            f"Leg {step}: {action} {qty} {sym} {right}${strike} — FAILED"
                        )
                        success = False
                        break

            # Notify
            status_emoji = "✅" if success else "⚠️"
            status_word  = "executed" if success else "PARTIALLY FAILED"
            log_lines    = "\n".join(f"  {line}" for line in execution_log)
            notify_msg   = (
                f"{status_emoji} <b>Pending Trade {status_word}</b>\n"
                f"{desc}\n\n{log_lines}"
            )
            try:
                from notifications import notify_info
                notify_info(notify_msg)
            except Exception:
                pass

            completed_record = {
                **trade,
                "status": "executed" if success else "partial",
                "executed_at": datetime.now().isoformat(),
                "execution_log": execution_log,
                "fill_details": fill_details,
            }
            newly_completed.append(completed_record)
            logger.info("  Trade %s: %s", trade_id, status_word.upper())
            for line in execution_log:
                logger.info("    %s", line)

    finally:
        ib.disconnect()

    # Persist updated state
    data["pending"] = still_pending
    data.setdefault("completed", []).extend(newly_completed)
    _save_pending(data)

    if newly_completed:
        logger.info(
            "Executed %d pending trade(s). %d remaining in queue.",
            len(newly_completed), len(still_pending),
        )
    else:
        logger.info("No trades triggered today. %d still pending.", len(still_pending))


if __name__ == "__main__":
    run()
