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
  - price_below: { "symbol": "BG", "price": 116.75 }  — fires when last snapshot
                 price for that symbol is at or below the threshold. Uses the
                 dashboard_snapshot.json for the last known price; acts as a
                 daily stop (checked each market-open run).
  - price_above: { "symbol": "ATO", "price": 197.26 } — fires when last snapshot
                 price is at or above the threshold. Used for take-profit exits.
                 The file also has a "take_profit" array (same schema as "pending")
                 and a "partial_profit" array (same schema) which are both merged
                 into the work list on each run.

Partial profit scaling:
  "partial_profit" entries trigger at 2× ATR and sell 50% of the position.
  They carry an "on_execute" field:
    { "reduce_linked_tp_id": "sym-tp-exit", "reduce_linked_tp_qty_to": 22 }
  After execution, the executor reduces the qty on the linked full TP entry so
  the remaining 50% is sold when the full 3.5× ATR target is reached.

Gap grace period (price_below stops only):
  When a stop triggers for the first time, the executor checks how far the
  stock gapped from its prior close:
    - Gap ≥ 3% down  → execute immediately (serious move, rarely recovers)
    - Gap < 3% down  → defer for GAP_GRACE_MINUTES (default 15 min) so a
                        false open has a chance to recover above the stop
  Per-trade override: add "gap_grace_minutes": 0 to a trade entry to always
  execute immediately, or a higher value (e.g. 30) for more patience.

Legs are executed sequentially. Step 1 must fill before Step 2 places.
"""

import contextlib
import json
import logging
import os
import tempfile
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

PENDING_FILE   = CONFIG_DIR / "pending_trades.json"
SNAPSHOT_FILE  = LOG_DIR / "dashboard_snapshot.json"
IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "4001"))
CLIENT_ID = 195  # dedicated client ID for pending trade executor
PID_FILE  = LOG_DIR / "execute_pending_trades.pid"

# ── Gap grace period ──────────────────────────────────────────────────────────
# When a price_below stop is triggered, we check whether the price gapped
# below the stop at the open (vs. a gradual intraday slide).
#
# Small gaps often fill — we wait GAP_GRACE_MINUTES before executing.
# Large gaps (≥ GAP_SKIP_PCT below the prior close) bypass the grace period
# entirely and execute immediately; those rarely fully recover the same day.
#
# Per-trade override: set "gap_grace_minutes" in the trade JSON. Set to 0 to
# always execute immediately regardless of gap size.
GAP_GRACE_MINUTES: int  = 15    # default wait for small gaps
GAP_SKIP_PCT:      float = 3.0  # % drop from prior close → skip grace, exit now


def _load_snapshot_prices() -> dict[str, float]:
    """Return {symbol: last_price} from dashboard_snapshot.json for price_below triggers."""
    try:
        snap = json.loads(SNAPSHOT_FILE.read_text())
        positions = snap.get("positions", {})
        pos_list: list[Any] = positions.get("list", []) if isinstance(positions, dict) else []
        return {
            p["symbol"]: float(p["market_price"])
            for p in pos_list
            if p.get("sec_type") == "STK" and p.get("market_price") is not None
        }
    except Exception as exc:
        logger.warning("Could not load snapshot prices for price_below check: %s", exc)
        return {}


def _fetch_prior_close(sym: str) -> float | None:
    """Return the most recent prior-day closing price for sym via yfinance."""
    try:
        import yfinance as yf
        hist = yf.download(sym, period="3d", progress=False, auto_adjust=True)
        if hist.empty or len(hist) < 2:
            return None
        cl = hist["Close"]
        if hasattr(cl, "columns"):
            cl = cl.iloc[:, 0]
        return float(cl.iloc[-2])
    except Exception as exc:
        logger.debug("Prior close fetch failed for %s: %s", sym, exc)
        return None


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
        return {"pending": [], "take_profit": [], "partial_profit": [], "completed": []}
    try:
        return json.loads(PENDING_FILE.read_text())
    except Exception as exc:
        logger.error("Failed to read pending_trades.json: %s", exc)
        return {"pending": [], "take_profit": [], "partial_profit": [], "completed": []}


def _save_pending(data: dict[str, Any]) -> None:
    try:
        fd, tmp = tempfile.mkstemp(dir=PENDING_FILE.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump(data, fh, indent=2)
            os.replace(tmp, PENDING_FILE)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception as exc:
        logger.error("Failed to write pending_trades.json: %s", exc)


# ── Trigger evaluation ────────────────────────────────────────────────────────

def _check_triggers(trade: dict[str, Any], ib_positions: dict[str, int],
                    snapshot_prices: dict[str, float] | None = None) -> tuple[bool, str]:
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

        if ctype == "manual_review":
            return False, f"manual_review: requires human decision — {cond.get('note', 'no note')}"

        if ctype == "symbol_not_in_portfolio":
            if sym in ib_positions:
                qty = ib_positions[sym]
                return False, f"{sym} still in portfolio (qty={qty}) — assignment not yet settled"

        elif ctype == "price_below":
            threshold = float(cond.get("price", 0))
            prices = snapshot_prices or {}
            last_price = prices.get(sym)
            if last_price is None:
                return False, f"price_below: no snapshot price for {sym} — cannot confirm trigger"
            if last_price > threshold:
                return False, (
                    f"price_below: {sym} last=${last_price:.2f} > threshold=${threshold:.2f}"
                )
            logger.warning(
                "price_below TRIGGERED: %s last=$%.2f ≤ stop=$%.2f — executing stop exit",
                sym, last_price, threshold,
            )

        elif ctype == "price_above":
            threshold = float(cond.get("price", 0))
            prices = snapshot_prices or {}
            last_price = prices.get(sym)
            if last_price is None:
                return False, f"price_above: no snapshot price for {sym} — cannot confirm trigger"
            if last_price < threshold:
                return False, (
                    f"price_above: {sym} last=${last_price:.2f} < threshold=${threshold:.2f}"
                )
            logger.info(
                "price_above TRIGGERED: %s last=$%.2f ≥ target=$%.2f — executing take-profit exit",
                sym, last_price, threshold,
            )

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
    """Sell (or buy) an options contract. Returns (success, fill_price).

    BUY_TO_CLOSE uses a limit order at a small premium above the ask to ensure
    fills on near-zero-bid deep OTM options. IB cancels market orders instantly
    when there is no bid/ask spread to match against.
    """
    from ib_insync import Option, MarketOrder, LimitOrder
    contract = Option(sym, expiry, strike, right, "SMART", currency="USD", multiplier="100")
    qualified = ib.qualifyContracts(contract)
    if not qualified:
        logger.error("Could not qualify option %s %s $%s%s exp %s", action, sym, strike, right, expiry)
        return False, 0.0

    # For BTC on deep OTM options: use a limit order at $0.05 (minimum tick).
    # Market orders on near-zero-bid options are cancelled immediately by IB/exchange.
    if action.upper() == "BUY_TO_CLOSE":
        # Request a snapshot to get the current ask, then bid up slightly
        ticker = ib.reqMktData(qualified[0], "", True, False)
        ib.sleep(2)
        ask = ticker.ask if ticker.ask and ticker.ask > 0 else None
        ib.cancelMktData(qualified[0])
        limit_price = round(max(ask * 1.1 if ask else 0.05, 0.05), 2)
        logger.info("BTC %s %s$%s %s — ask=$%s → limit=$%.2f", sym, right, strike, expiry,
                    f"{ask:.2f}" if ask else "N/A", limit_price)
        order = LimitOrder(action, qty, limit_price)
        order.tif = "DAY"
    else:
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


# ── Stop/TP attachment ────────────────────────────────────────────────────────

def _attach_stock_stop(ib: Any, sym: str, qty: int, fill: float,
                       execution_log: list[str], step: int) -> str:
    """
    After a BUY fill, place a GTC trailing stop and limit TP via ib_insync.

    Returns a short status string for logging. Does NOT raise — failures are
    logged but do not abort the pending trade (position is already filled).
    """
    try:
        from ib_insync import Stock, TrailingStopOrder, LimitOrder as IBLimitOrder
        from atr_stops import fetch_atr, compute_stop_tp, compute_trailing_amount

        atr = fetch_atr(sym)
        stop_px, tp_px = compute_stop_tp(fill, "BUY", atr=atr, fallback_stop_pct=0.05, fallback_tp_pct=0.10)
        trail_amt = compute_trailing_amount(atr=atr, entry_price=fill)

        stk = Stock(sym, "SMART", "USD")
        qualified = ib.qualifyContracts(stk)
        if not qualified:
            msg = f"Leg {step}: could not qualify {sym} for stop — UNPROTECTED"
            execution_log.append(msg)
            logger.error(msg)
            return "qualify_failed"
        contract = qualified[0]

        # Use an OCA group so that when the trailing stop fills, the TP limit
        # is automatically cancelled — prevents the TP from creating an accidental short.
        oca_group = f"pending_oca_{sym}_{int(fill*100)}"

        stop_order = TrailingStopOrder("SELL", qty, trailAmount=trail_amt)
        stop_order.tif = "GTC"
        stop_order.outsideRth = False
        stop_order.ocaGroup = oca_group
        stop_order.ocaType = 1  # cancel remaining orders with block

        tp_order = IBLimitOrder("SELL", qty, tp_px)
        tp_order.tif = "GTC"
        tp_order.outsideRth = False
        tp_order.ocaGroup = oca_group
        tp_order.ocaType = 1

        ib.placeOrder(contract, stop_order)
        ib.placeOrder(contract, tp_order)
        ib.sleep(1)

        msg = (
            f"Leg {step}: stop trail=${trail_amt:.2f} (init≈${stop_px:.2f}) "
            f"tp=${tp_px:.2f} [atr={'%.2f' % atr if atr else 'fallback'}] — GTC"
        )
        execution_log.append(msg)
        return msg
    except Exception as exc:
        msg = f"Leg {step}: stop attachment failed ({exc}) — UNPROTECTED"
        execution_log.append(msg)
        logger.error(msg)
        return f"error: {exc}"


# ── Partial profit linkage ────────────────────────────────────────────────────

def _apply_linked_qty_reductions(
    newly_completed: list[dict[str, Any]], data: dict[str, Any]
) -> None:
    """
    After a partial-profit trade executes, reduce the qty on its linked full
    take-profit entry so we don't over-sell when the full TP subsequently fires.

    Each partial_profit entry may carry:
      "on_execute": {
          "reduce_linked_tp_id": "sym-tp-exit",
          "reduce_linked_tp_qty_to": 22
      }
    """
    for completed in newly_completed:
        on_exec = completed.get("on_execute", {})
        linked_id = on_exec.get("reduce_linked_tp_id")
        reduce_to = on_exec.get("reduce_linked_tp_qty_to")
        if not linked_id or reduce_to is None:
            continue
        entry_found = False
        for entry in data.get("take_profit", []):
            if entry.get("id") != linked_id:
                continue
            entry_found = True
            leg_patched = False
            for leg in entry.get("legs", []):
                if leg.get("action") == "SELL" and leg.get("secType", "STK").upper() == "STK":
                    old_qty = leg.get("qty", 0)
                    leg["qty"] = int(reduce_to)
                    leg_patched = True
                    logger.info(
                        "Partial TP executed → reduced linked TP '%s' qty %d → %d (remaining shares)",
                        linked_id, old_qty, int(reduce_to),
                    )
                    # Patch description to reflect new qty
                    sym = (
                        completed.get("trigger", {})
                        .get("conditions", [{}])[0]
                        .get("symbol", "")
                        .upper()
                    )
                    if sym and f"sell {old_qty} {sym}" in entry.get("description", ""):
                        entry["description"] = entry["description"].replace(
                            f"sell {old_qty} {sym}", f"sell {int(reduce_to)} {sym}"
                        )
                    break
            if not leg_patched:
                logger.warning(
                    "Partial TP '%s' executed but linked TP '%s' has no SELL STK leg — "
                    "qty NOT reduced. Manual reconciliation required.",
                    completed.get("id"), linked_id,
                )
            break
        if not entry_found:
            logger.warning(
                "Partial TP '%s' executed but linked full-TP id '%s' not found in take_profit — "
                "full TP qty NOT reduced. Manual reconciliation required.",
                completed.get("id"), linked_id,
            )


# ── Main executor ─────────────────────────────────────────────────────────────

def run() -> None:
    with _pid_lock(PID_FILE):
        _run_inner()


def _options_market_open() -> bool:
    """Return True only when the US options market is open (9:30–16:00 ET, Mon–Fri)."""
    from datetime import datetime as _dt
    import zoneinfo
    now_et = _dt.now(zoneinfo.ZoneInfo("America/New_York"))
    if now_et.weekday() >= 5:          # Saturday=5, Sunday=6
        return False
    open_time  = now_et.replace(hour=9,  minute=30, second=0, microsecond=0)
    close_time = now_et.replace(hour=16, minute=0,  second=0, microsecond=0)
    return open_time <= now_et < close_time


def _trade_needs_options(trade: dict[str, Any]) -> bool:
    """Return True if any leg in the trade involves an OPT order."""
    return any(
        leg.get("secType", "STK").upper() == "OPT"
        for leg in trade.get("legs", [])
    )


def _run_inner() -> None:
    data = _load_pending()
    # Merge stops ("pending"), full TPs ("take_profit"), and partial TPs ("partial_profit")
    partial_profit = data.get("partial_profit", [])
    pending = data.get("pending", []) + data.get("take_profit", []) + partial_profit
    if not pending:
        logger.info("No pending trades in queue — nothing to do")
        return

    options_open = _options_market_open()
    if not options_open:
        opt_trades = [t for t in pending if _trade_needs_options(t)]
        if opt_trades:
            logger.info(
                "Options market not yet open — %d trade(s) with option legs will be "
                "skipped until 9:30 AM ET: %s",
                len(opt_trades), [t.get("id") for t in opt_trades],
            )

    logger.info("Found %d pending trade(s) (stops + TPs + partial TPs) — checking triggers", len(pending))

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
        ib_option_positions: set[str] = set()   # "SYM_RIGHT_STRIKE_EXPIRY" keys
        for p in ib.positions():
            c = p.contract
            if c.secType == "STK":
                ib_positions[c.symbol.upper()] = int(p.position)
            elif c.secType == "OPT" and p.position < 0:
                # Track short option positions so we can skip BTC legs when the position
                # no longer exists (already expired, closed, or was never placed).
                key = f"{c.symbol.upper()}_{c.right}_{c.strike}_{c.lastTradeDateOrContractMonth}"
                ib_option_positions.add(key)
                logger.debug("Short option held: %s", key)

        snapshot_prices = _load_snapshot_prices()
        logger.info("Loaded snapshot prices for %d symbols", len(snapshot_prices))

        for trade in pending:
            trade_id = trade.get("id", "?")
            desc = trade.get("description", "")
            logger.info("Checking: %s — %s", trade_id, desc)

            ready, reason = _check_triggers(trade, ib_positions, snapshot_prices)
            if not ready:
                logger.info("  Not ready: %s", reason)
                still_pending.append(trade)
                continue

            # If any leg requires options and options aren't open yet, hold the trade
            # in pending rather than letting IB cancel the order and burn a retry.
            if _trade_needs_options(trade) and not options_open:
                logger.info(
                    "  Deferring %s — options market not open yet (will retry at 9:30 AM ET)",
                    trade_id,
                )
                still_pending.append(trade)
                continue

            # ── Gap grace period ──────────────────────────────────────────────
            # Only applies to price_below (stop) triggers, not take-profits or
            # date/portfolio triggers. Lets small gap-down opens potentially
            # recover before we pull the trigger.
            is_stop_trigger = any(
                c.get("type") == "price_below"
                for c in trade.get("trigger", {}).get("conditions", [])
            )
            grace_minutes = int(trade.get("gap_grace_minutes", GAP_GRACE_MINUTES))

            if is_stop_trigger and grace_minutes > 0:
                now = datetime.now()
                first_triggered_at_str: str | None = trade.get("_gap_first_triggered_at")

                if first_triggered_at_str is None:
                    # First time this stop has fired — decide: grace or immediate?
                    # Fetch prior close to measure the gap size.
                    stop_sym = next(
                        (c.get("symbol", "").upper()
                         for c in trade.get("trigger", {}).get("conditions", [])
                         if c.get("type") == "price_below"),
                        None,
                    )
                    current_price = snapshot_prices.get(stop_sym, 0.0) if stop_sym else 0.0
                    prior_close   = _fetch_prior_close(stop_sym) if stop_sym else None

                    if prior_close and prior_close > 0:
                        gap_pct = (current_price - prior_close) / prior_close * 100
                    else:
                        gap_pct = 0.0  # can't measure gap, treat as small

                    if gap_pct <= -GAP_SKIP_PCT:
                        # Large gap — bypass grace, execute immediately
                        logger.warning(
                            "  GAP %.1f%% (prior close $%.2f → now $%.2f) exceeds "
                            "%.1f%% threshold — executing immediately, no grace period",
                            gap_pct, prior_close or 0, current_price, GAP_SKIP_PCT,
                        )
                        # Fall through to execution below
                    else:
                        # Small gap — start the grace clock and defer
                        trade = {**trade, "_gap_first_triggered_at": now.isoformat(),
                                 "_gap_pct": round(gap_pct, 2)}
                        still_pending.append(trade)
                        logger.info(
                            "  Gap grace started: %.1f%% gap (prior=$%.2f, now=$%.2f) — "
                            "deferring %d min. Will execute if still below stop at next run.",
                            gap_pct, prior_close or 0, current_price, grace_minutes,
                        )
                        try:
                            from notifications import notify_info
                            notify_info(
                                f"⏳ <b>Gap grace period — {trade_id}</b>\n"
                                f"{desc}\n\n"
                                f"Gap: {gap_pct:+.1f}% (prev close ${prior_close:.2f} → "
                                f"now ${current_price:.2f})\n"
                                f"Waiting {grace_minutes} min for potential recovery.\n"
                                f"Will execute if still below stop at next run."
                            )
                        except Exception:
                            pass
                        continue

                else:
                    # Grace period already started — check if enough time has passed
                    first_triggered_at = datetime.fromisoformat(first_triggered_at_str)
                    elapsed_min = (now - first_triggered_at).total_seconds() / 60
                    if elapsed_min < grace_minutes:
                        still_pending.append(trade)
                        logger.info(
                            "  Grace period active: %.1f / %d min elapsed — still deferring",
                            elapsed_min, grace_minutes,
                        )
                        continue
                    else:
                        logger.warning(
                            "  Grace period expired (%.1f min) — stop still triggered, executing now",
                            elapsed_min,
                        )
                        # Strip grace metadata before completing
                        trade = {k: v for k, v in trade.items()
                                 if k not in ("_gap_first_triggered_at", "_gap_pct")}
            # ── End gap grace ─────────────────────────────────────────────────

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
                        # For BUY entries, immediately attach an ATR trailing stop + limit TP.
                        # Skip for SELL / BUY_TO_CLOSE / exit legs.
                        if action == "BUY" and fill > 0:
                            stop_note = _attach_stock_stop(ib, sym, qty, fill, execution_log, step)
                            logger.info("  Stop/TP for %s: %s", sym, stop_note)
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

                    # For BUY_TO_CLOSE: skip if the short option is no longer held
                    # (expired worthless, previously closed, or was never placed).
                    if action == "BUY_TO_CLOSE":
                        opt_key = f"{sym}_{right}_{strike}_{expiry}"
                        if opt_key not in ib_option_positions:
                            note = (
                                f"Leg {step}: {sym} {right}${strike} {expiry} — "
                                f"no short position found in IBKR, skipping BTC (already closed/expired)"
                            )
                            execution_log.append(note)
                            logger.warning("  %s", note)
                            continue   # skip to next leg (SELL stock)

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

            # If step 1 failed and nothing was filled yet, the position is unchanged —
            # it is safe to re-queue rather than permanently mark partial. This handles
            # pre-market option BTC cancellations: options don't trade until 9:30 AM ET
            # so IB cancels the order instantly, but no shares were affected.
            nothing_filled = not fill_details  # fill_details is empty ↔ no leg succeeded
            if not success and nothing_filled:
                retry_count = trade.get("_retry_count", 0) + 1
                requeued = {**trade, "_retry_count": retry_count,
                            "_last_fail": datetime.now().isoformat(),
                            "_last_fail_log": execution_log}
                still_pending.append(requeued)
                logger.warning(
                    "  Trade %s: leg 1 failed with no fills — re-queued for next run "
                    "(retry #%d). Likely pre-market option rejection.",
                    trade_id, retry_count,
                )
                try:
                    from notifications import notify_info
                    notify_info(
                        f"⏳ <b>Stop re-queued</b>\n{desc}\n\n"
                        f"Leg 1 cancelled (pre-market?). Will retry at next market-open run. "
                        f"(attempt #{retry_count})"
                    )
                except Exception:
                    pass
                continue

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

    # Apply partial-profit linkage: reduce linked full-TP qty before saving
    _apply_linked_qty_reductions(newly_completed, data)

    # Persist updated state — split still_pending back into their source arrays
    original_pending_ids        = {t.get("id") for t in data.get("pending", [])}
    original_tp_ids             = {t.get("id") for t in data.get("take_profit", [])}
    original_partial_profit_ids = {t.get("id") for t in data.get("partial_profit", [])}
    data["pending"]        = [t for t in still_pending if t.get("id") in original_pending_ids]
    data["take_profit"]    = [t for t in still_pending if t.get("id") in original_tp_ids]
    data["partial_profit"] = [t for t in still_pending if t.get("id") in original_partial_profit_ids]
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
