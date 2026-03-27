#!/usr/bin/env python3
"""
Winner Pyramid — add to early winners, move stop to breakeven.

Two pyramid layers run in sequence:

Layer 1 — Dhaliwal (Unknown Market Wizards):
  If a long position is up ≥1R within its first 2 days, add 50% more shares
  at the current price and move the stop to breakeven.  This converts early
  momentum into a risk-free runner without adding new downside.

Layer 2 — Kullamägi (Next Generation):
  If a long position's unrealized gain exceeds 2× ATR AND has not yet received
  an open-profit pyramid add today, fund an additional purchase using 30% of
  the open-profit collateral.  This allows significantly larger adds on high-
  conviction breakouts versus the fixed 50%-of-original-qty rule.  The add is
  capped at max_total_pct_of_nlv of NLV so that a runaway winner never
  over-concentrates the portfolio.

Rules (all must pass for each layer):
  1. Position is long (side = BUY, qty > 0 in IB).
  2. Opened within the last 2 calendar days (Layer 1) — no lookback limit (Layer 2).
  3. Layer 1: unrealized P&L ≥ 1R.   Layer 2: unrealized P&L ≥ 2× ATR.
  4. Not already pyramided (by that layer) today.
  5. Pre-trade guard: add would NOT flip or over-size.
  6. Daily budget: each add counts against the LONG slot for the day.

After a successful add: existing ATR stop is cancelled; new stop placed at
breakeven (Layer 1) or at the original stop distance from the new average cost
(Layer 2).  All actions logged to logs/pyramid_log.jsonl and Telegram.

Scheduler job: `job_options_manager` every 30 min.
clientId: 138 (see 030-ib-client-ids.mdc)
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from ib_insync import IB, LimitOrder, Order, Stock, StopOrder

from paths import TRADING_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [winner_pyramid] %(levelname)s — %(message)s",
)
logger = logging.getLogger("winner_pyramid")

CLIENT_ID = 138
DB_PATH = TRADING_DIR / "logs" / "trades.db"
PYRAMID_LOG = TRADING_DIR / "logs" / "pyramid_log.jsonl"
STOP_MULT_DEFAULT = 1.5   # fallback if adaptive config unavailable
MAX_PYRAMID_PER_DAY = 3   # safety: cap total pyramid adds per session


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _load_stop_mult() -> float:
    try:
        from adaptive_config_loader import get_adaptive_float
        return get_adaptive_float("stop_atr_mult", STOP_MULT_DEFAULT)
    except ImportError:
        return STOP_MULT_DEFAULT


def _load_ib_ports() -> list[int]:
    try:
        base = int(__import__("os").getenv("IB_PORT", "4001"))
    except ValueError:
        base = 4001
    return [base, 4001, 7496, 7497]


# ---------------------------------------------------------------------------
# trades.db helpers
# ---------------------------------------------------------------------------

def _get_open_long_records() -> list[dict]:
    """Return open long entries from trades.db entered within the last 2 days (Dhaliwal layer)."""
    cutoff = (datetime.now() - timedelta(days=2)).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT *
            FROM trades
            WHERE side = 'BUY'
              AND status = 'Filled'
              AND exit_price IS NULL
              AND timestamp >= ?
            ORDER BY timestamp DESC
            """,
            (cutoff,),
        ).fetchall()
    return [dict(r) for r in rows]


def _get_all_open_long_records() -> list[dict]:
    """Return ALL open long entries from trades.db with no lookback limit (Kullamägi layer)."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT *
                FROM trades
                WHERE side = 'BUY'
                  AND status = 'Filled'
                  AND exit_price IS NULL
                ORDER BY timestamp DESC
                """
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        logger.error("DB read error in _get_all_open_long_records: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Pyramid log helpers (de-duplication)
# ---------------------------------------------------------------------------

def _load_open_profit_pyramid_config() -> dict:
    """Load Kullamägi open-profit pyramid settings from risk.json."""
    defaults = {
        "enabled": True,
        "min_open_profit_atr": 2.0,
        "add_pct_of_open_profit": 0.30,
        "max_total_pct_of_nlv": 0.08,
        "min_add_shares": 1,
    }
    try:
        import json as _j
        risk = _j.loads((TRADING_DIR / "risk.json").read_text())
        defaults.update(risk.get("open_profit_pyramid", {}))
    except Exception:
        pass
    return defaults


def _open_profit_pyramided_today(symbol: str) -> bool:
    """Return True if we already added a Kullamägi open-profit layer to this symbol today."""
    today = datetime.now().date().isoformat()
    if not PYRAMID_LOG.exists():
        return False
    try:
        for line in PYRAMID_LOG.read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if (rec.get("symbol") == symbol
                    and rec.get("date") == today
                    and rec.get("layer") == "kullamagi_open_profit"):
                return True
    except Exception:
        pass
    return False


def _already_pyramided_today(trade_id: int) -> bool:
    """Return True if we already pyramided this trade record today."""
    today = datetime.now().date().isoformat()
    if not PYRAMID_LOG.exists():
        return False
    try:
        for line in PYRAMID_LOG.read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("trade_id") == trade_id and rec.get("date") == today:
                return True
    except Exception:
        pass
    return False


def _pyramided_count_today() -> int:
    today = datetime.now().date().isoformat()
    if not PYRAMID_LOG.exists():
        return 0
    count = 0
    try:
        for line in PYRAMID_LOG.read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("date") == today:
                count += 1
    except Exception:
        pass
    return count


def _log_pyramid(record: dict) -> None:
    PYRAMID_LOG.parent.mkdir(parents=True, exist_ok=True)
    with PYRAMID_LOG.open("a") as f:
        f.write(json.dumps(record) + "\n")


# ---------------------------------------------------------------------------
# IB helpers
# ---------------------------------------------------------------------------

def _current_price_from_ib(ib: IB, symbol: str) -> Optional[float]:
    """Return last price for symbol from IB snapshot (delayed ok)."""
    try:
        contract = Stock(symbol, "SMART", "USD")
        ib.qualifyContracts(contract)
        ib.reqMarketDataType(3)  # delayed
        ticker = ib.reqMktData(contract, "", False, False)
        ib.sleep(1.5)
        for attr in ("last", "close", "bid", "ask"):
            val = getattr(ticker, attr, float("nan"))
            if val and val == val and val > 0:  # not NaN
                return float(val)
    except Exception as exc:
        logger.warning("Could not fetch price for %s: %s", symbol, exc)
    return None


def _cancel_existing_stops(ib: IB, symbol: str) -> list[int]:
    """Cancel all open stop/trail orders for symbol; return cancelled order IDs."""
    cancelled: list[int] = []
    try:
        ib.reqAllOpenOrders()
        ib.sleep(1.0)
        for trade in ib.openTrades():
            if getattr(trade.contract, "symbol", "") != symbol:
                continue
            otype = trade.order.orderType.upper()
            if otype in {"STP", "TRAIL", "TRAILLIMIT", "STP LMT", "STOP", "STOP LIMIT"}:
                ib.cancelOrder(trade.order)
                cancelled.append(trade.order.orderId)
                logger.info("Cancelled stop order %d for %s", trade.order.orderId, symbol)
    except Exception as exc:
        logger.warning("Stop cancellation error for %s: %s", symbol, exc)
    return cancelled


# ---------------------------------------------------------------------------
# Core pyramid logic
# ---------------------------------------------------------------------------

async def _open_profit_pyramid_one(
    ib: IB,
    rec: dict,
    ib_position_qty: int,
    net_liq: float,
) -> bool:
    """Kullamägi open-profit pyramid: add using unrealized gains as collateral.

    When unrealized gain ≥ min_open_profit_atr × ATR, fund an additional
    purchase equal to add_pct × unrealized_gain_dollars, capped at
    max_total_pct_of_nlv × NLV.  This scales add size with position performance
    rather than a fixed 50%-of-original-qty rule.
    """
    cfg = _load_open_profit_pyramid_config()
    if not cfg.get("enabled", True):
        return False

    symbol: str = rec["symbol"]
    entry_price: float = float(rec.get("entry_price") or rec.get("price") or 0)
    atr_at_entry: Optional[float] = rec.get("atr_at_entry")
    trade_id: int = rec["id"]

    if not entry_price or entry_price <= 0:
        return False

    if _open_profit_pyramided_today(symbol):
        logger.debug("%s: Kullamägi layer already applied today", symbol)
        return False

    current_price = _current_price_from_ib(ib, symbol)
    if current_price is None:
        return False

    unrealized_pct = (current_price - entry_price) / entry_price
    if unrealized_pct <= 0:
        return False   # not profitable

    # Determine ATR for threshold check
    stop_mult = _load_stop_mult()
    if atr_at_entry and atr_at_entry > 0:
        atr = atr_at_entry
    else:
        atr = entry_price * 0.02

    min_profit_atr = float(cfg.get("min_open_profit_atr", 2.0))
    unrealized_price_move = current_price - entry_price

    if unrealized_price_move < atr * min_profit_atr:
        logger.debug(
            "%s: open profit %.2f < threshold %.2f (%.1f× ATR) — Kullamägi layer skipped",
            symbol, unrealized_price_move, atr * min_profit_atr, min_profit_atr,
        )
        return False

    # Compute add quantity from open-profit collateral
    open_profit_dollars = unrealized_price_move * ib_position_qty
    add_pct = float(cfg.get("add_pct_of_open_profit", 0.30))
    max_nlv_pct = float(cfg.get("max_total_pct_of_nlv", 0.08))
    min_add_shares = int(cfg.get("min_add_shares", 1))

    add_dollars = open_profit_dollars * add_pct
    max_dollars = net_liq * max_nlv_pct
    add_dollars = min(add_dollars, max_dollars)
    add_qty = max(min_add_shares, int(add_dollars // current_price))

    if add_qty < min_add_shares:
        logger.debug("%s: computed add qty %d < minimum %d — skipped", symbol, add_qty, min_add_shares)
        return False

    # Pre-trade guard
    try:
        from pre_trade_guard import PreTradeViolation, assert_no_flip
        assert_no_flip(ib, symbol, "LONG")
    except ImportError:
        pass
    except Exception as e:
        logger.error("Pre-trade guard blocked Kullamägi pyramid for %s: %s", symbol, e)
        return False

    logger.info(
        "KULLAMÄGI PYRAMID: %s +%d shares @ ~$%.2f | open_profit=$%.0f × %.0f%% = $%.0f "
        "(%.1f× ATR threshold met)",
        symbol, add_qty, current_price,
        open_profit_dollars, add_pct * 100, add_dollars, min_profit_atr,
    )

    try:
        contract = Stock(symbol, "SMART", "USD")
        ib.qualifyContracts(contract)
        buy_order = LimitOrder("BUY", add_qty, round(current_price * 1.005, 2))
        buy_order.tif = "DAY"
        buy_order.outsideRth = False
        buy_trade = ib.placeOrder(contract, buy_order)
        ib.sleep(3)
        filled_price = buy_trade.orderStatus.avgFillPrice or current_price
    except Exception as exc:
        logger.error("Kullamägi BUY failed for %s: %s", symbol, exc)
        return False

    # Log and notify
    log_rec = {
        "date": datetime.now().date().isoformat(),
        "timestamp": datetime.now().isoformat(),
        "layer": "kullamagi_open_profit",
        "trade_id": trade_id,
        "symbol": symbol,
        "add_qty": add_qty,
        "fill_price": round(filled_price, 2),
        "entry_price": entry_price,
        "open_profit_dollars": round(open_profit_dollars, 2),
        "add_pct": add_pct,
        "profit_atr_multiples": round(unrealized_price_move / atr, 2),
    }
    _log_pyramid(log_rec)

    try:
        from notifications import notify_info
        notify_info(
            f"📈 <b>Kullamägi Pyramid</b>: {symbol}\n"
            f"Open profit ${open_profit_dollars:,.0f} × {add_pct*100:.0f}% = +{add_qty} shares\n"
            f"Fill: ${filled_price:.2f} | Profit: {unrealized_pct*100:.1f}% ({unrealized_price_move/atr:.1f}× ATR)"
        )
    except Exception:
        pass

    return True


async def _pyramid_one(
    ib: IB,
    rec: dict,
    ib_position_qty: int,
) -> bool:
    """Attempt to pyramid one long position.  Returns True on success."""
    symbol: str = rec["symbol"]
    entry_price: float = float(rec.get("entry_price") or rec.get("price") or 0)
    atr_at_entry: Optional[float] = rec.get("atr_at_entry")
    trade_id: int = rec["id"]
    original_qty: int = int(rec.get("qty") or 1)

    if not entry_price or entry_price <= 0:
        logger.warning("Skipping %s — missing entry price in trades.db", symbol)
        return False

    # --- 1R threshold ---
    stop_mult = _load_stop_mult()
    if atr_at_entry and atr_at_entry > 0:
        stop_dist = atr_at_entry * stop_mult
    else:
        stop_dist = entry_price * 0.05   # fallback 5% stop
    one_r_pct = stop_dist / entry_price

    current_price = _current_price_from_ib(ib, symbol)
    if current_price is None:
        logger.warning("Skipping %s — could not fetch current price", symbol)
        return False

    unrealized_pct = (current_price - entry_price) / entry_price
    if unrealized_pct < one_r_pct:
        logger.debug(
            "%s not yet at +1R (need +%.1f%%, at +%.1f%%)",
            symbol, one_r_pct * 100, unrealized_pct * 100,
        )
        return False

    # --- Pre-trade guard ---
    try:
        from pre_trade_guard import PreTradeViolation, assert_no_flip
        assert_no_flip(ib, symbol, "LONG")
    except ImportError:
        pass
    except Exception as e:
        logger.error("Pre-trade guard blocked pyramid for %s: %s", symbol, e)
        return False

    # --- Pyramid qty = 50% of original entry qty ---
    add_qty = max(1, round(original_qty * 0.50))
    breakeven_stop = round(entry_price * 0.999, 2)   # 0.1% below cost basis

    logger.info(
        "PYRAMIDING %s: +%d shares @ $%.2f (was up +%.1f%% vs +1R %.1f%%); "
        "stop → BE $%.2f",
        symbol, add_qty, current_price,
        unrealized_pct * 100, one_r_pct * 100, breakeven_stop,
    )

    # --- Place pyramid BUY ---
    try:
        contract = Stock(symbol, "SMART", "USD")
        ib.qualifyContracts(contract)
        buy_order = LimitOrder("BUY", add_qty, round(current_price * 1.005, 2))
        buy_order.tif = "DAY"
        buy_order.outsideRth = False
        buy_trade = ib.placeOrder(contract, buy_order)
        ib.sleep(3)
        filled_price = buy_trade.orderStatus.avgFillPrice or current_price
    except Exception as exc:
        logger.error("Pyramid BUY failed for %s: %s", symbol, exc)
        return False

    # --- Cancel existing stops, replace with breakeven stop ---
    _cancel_existing_stops(ib, symbol)
    try:
        ib.sleep(0.5)
        new_qty = ib_position_qty + add_qty
        stop_order = StopOrder("SELL", new_qty, breakeven_stop)
        stop_order.tif = "GTC"
        stop_order.outsideRth = True
        ib.placeOrder(contract, stop_order)
        logger.info(
            "Breakeven stop placed for %s: $%.2f covering %d shares",
            symbol, breakeven_stop, new_qty,
        )
    except Exception as exc:
        logger.error("Breakeven stop placement failed for %s: %s — position unprotected!", symbol, exc)
        try:
            from notifications import notify_critical
            notify_critical(
                "Pyramid Stop Failed",
                f"<b>{symbol}</b> pyramid add filled but breakeven stop FAILED.\n"
                f"Manual stop at ${breakeven_stop:.2f} required immediately.",
            )
        except Exception:
            pass

    # --- Log and notify ---
    log_rec = {
        "date": datetime.now().date().isoformat(),
        "timestamp": datetime.now().isoformat(),
        "trade_id": trade_id,
        "symbol": symbol,
        "add_qty": add_qty,
        "fill_price": round(filled_price, 2),
        "entry_price": entry_price,
        "unrealized_pct": round(unrealized_pct * 100, 2),
        "one_r_pct": round(one_r_pct * 100, 2),
        "new_stop": breakeven_stop,
        "new_total_qty": ib_position_qty + add_qty,
    }
    _log_pyramid(log_rec)

    try:
        from notifications import notify_info
        notify_info(
            f"🔺 <b>Pyramid Add</b>: {symbol}\n"
            f"Entry ${entry_price:.2f} → now ${current_price:.2f} (+{unrealized_pct*100:.1f}%)\n"
            f"Added {add_qty} shares @ ${filled_price:.2f}\n"
            f"Stop → breakeven ${breakeven_stop:.2f}"
        )
    except Exception:
        pass

    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run() -> None:
    ib = IB()
    connected = False
    for port in _load_ib_ports():
        try:
            await ib.connectAsync("127.0.0.1", port, clientId=CLIENT_ID, timeout=15)
            connected = True
            break
        except Exception as exc:
            logger.warning("IB connect port %d failed: %s", port, exc)

    if not connected:
        logger.error("Could not connect to IB Gateway — winner_pyramid skipped")
        return

    try:
        # Check kill switch
        try:
            from kill_switch_guard import kill_switch_active
            if kill_switch_active():
                logger.warning("Kill switch active — winner_pyramid skipped")
                return
        except ImportError:
            pass

        # Daily limit guard
        if _pyramided_count_today() >= MAX_PYRAMID_PER_DAY:
            logger.info(
                "Max pyramid adds reached for today (%d). Skipping.",
                MAX_PYRAMID_PER_DAY,
            )
            return

        # Fetch NLV for Kullamägi open-profit pyramid sizing
        net_liq = 0.0
        try:
            from risk_config import get_net_liquidation_and_effective_equity
            from pathlib import Path as _P
            nlv, _ = get_net_liquidation_and_effective_equity(ib, _P(__file__).parent.parent)
            net_liq = float(nlv or 0)
        except Exception as exc:
            logger.warning("Could not fetch NLV for open-profit pyramid: %s", exc)

        # Build IB position map: symbol → qty
        ib_positions: dict[str, int] = {}
        for pos in ib.positions():
            if getattr(pos.contract, "secType", "") == "STK" and pos.position > 0:
                sym = pos.contract.symbol.upper()
                ib_positions[sym] = int(pos.position)

        if not ib_positions:
            logger.info("No long equity positions in IB — nothing to pyramid")
            return

        open_records = _get_open_long_records()
        if not open_records:
            logger.info("No qualifying open long records in trades.db")
            return

        logger.info(
            "Checking %d open long records for pyramid opportunity", len(open_records)
        )

        added = 0
        for rec in open_records:
            if added >= MAX_PYRAMID_PER_DAY:
                break
            symbol = rec["symbol"].upper()
            ib_qty = ib_positions.get(symbol)
            if not ib_qty:
                continue  # symbol not actually held in IB

            if _already_pyramided_today(rec["id"]):
                logger.debug("%s already pyramided today (Dhaliwal layer) — skipping", symbol)
                continue

            # Layer 1 — Dhaliwal: +1R early winner add
            success = await _pyramid_one(ib, rec, ib_qty)
            if success:
                added += 1
                await asyncio.sleep(2)

        # Layer 2 — Kullamägi: open-profit collateral add (separate de-dup check)
        # Runs over ALL open longs, not just those entered within 2 days
        all_open_records = _get_all_open_long_records()
        for rec in all_open_records:
            if added >= MAX_PYRAMID_PER_DAY:
                break
            symbol = rec["symbol"].upper()
            ib_qty = ib_positions.get(symbol)
            if not ib_qty:
                continue
            if net_liq <= 0:
                break   # cannot size without NLV

            success = await _open_profit_pyramid_one(ib, rec, ib_qty, net_liq)
            if success:
                added += 1
                await asyncio.sleep(2)

        if added == 0:
            logger.info("No pyramid conditions met this run")
        else:
            logger.info("Pyramid adds executed: %d", added)

    finally:
        ib.disconnect()


if __name__ == "__main__":
    asyncio.run(run())
