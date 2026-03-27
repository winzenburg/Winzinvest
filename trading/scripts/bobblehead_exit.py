#!/usr/bin/env python3
"""
Bobblehead Early Exit — closes failed long setups after 2 days of no confirmation.

Lance Breitstein + Phil Goedeker (Market Wizards: The Next Generation):
  A properly-entered trade should be green within 2 days. If a long position
  is still below its entry price after 'days_window' trading days AND has
  drifted down by at least 0.35× ATR, it is a failed setup — exit at market
  rather than holding to the full ATR stop distance.

This preserves capital and position slots for higher-conviction setups.
The rule applies only to LONG positions entered via executor scripts
(records in trades.db).  Options positions are excluded.

Config lives in risk.json → bobblehead_exit:
  enabled               : bool  (default True)
  days_window           : int   (default 2 — must be holding at least this many days)
  min_loss_atr_fraction : float (default 0.35 — min drift = 0.35 × ATR)
  apply_to_sides        : list  (default ["LONG"])

Scheduler: runs as part of job_options_manager every 30 min, post-open only.
clientId: 139 (see 030-ib-client-ids.mdc)
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yfinance as yf
from ib_insync import IB, MarketOrder, Stock

from paths import TRADING_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [bobblehead_exit] %(levelname)s — %(message)s",
)
logger = logging.getLogger("bobblehead_exit")

CLIENT_ID = 139
DB_PATH = TRADING_DIR / "logs" / "trades.db"
EXIT_LOG = TRADING_DIR / "logs" / "bobblehead_exits.jsonl"
RISK_JSON = TRADING_DIR / "risk.json"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    defaults = {
        "enabled": True,
        "days_window": 2,
        "min_loss_atr_fraction": 0.35,
        "apply_to_sides": ["LONG"],
    }
    try:
        risk = json.loads(RISK_JSON.read_text())
        defaults.update(risk.get("bobblehead_exit", {}))
    except Exception:
        pass
    return defaults


def _load_ib_ports() -> list[int]:
    try:
        base = int(__import__("os").getenv("IB_PORT", "4001"))
    except ValueError:
        base = 4001
    return [base, 4001, 7496, 7497]


# ---------------------------------------------------------------------------
# Trades DB helpers
# ---------------------------------------------------------------------------

def _get_open_long_candidates(days_window: int) -> list[dict]:
    """Return open long positions that have been held >= days_window trading days."""
    cutoff = (datetime.now() - timedelta(days=days_window)).isoformat()
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
                  AND timestamp <= ?
                ORDER BY timestamp ASC
                """,
                (cutoff,),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        logger.error("DB read error: %s", exc)
        return []


def _mark_exited(trade_id: int, exit_price: float, reason: str = "BOBBLEHEAD_EXIT") -> None:
    """Update trades.db to record the exit."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "UPDATE trades SET exit_price=?, exit_reason=?, status='Closed' WHERE id=?",
                (exit_price, reason, trade_id),
            )
            conn.commit()
    except Exception as exc:
        logger.error("DB update error for trade %d: %s", trade_id, exc)


# ---------------------------------------------------------------------------
# ATR fetch
# ---------------------------------------------------------------------------

def _fetch_atr(symbol: str, period: int = 14) -> Optional[float]:
    """Fetch current ATR(14) via yfinance."""
    try:
        df = yf.download(symbol, period="30d", progress=False)
        if df.empty or len(df) < period:
            return None
        high = df["High"].squeeze()
        low = df["Low"].squeeze()
        close = df["Close"].squeeze()
        cp = close.shift(1)
        import pandas as pd
        import numpy as np
        tr = pd.concat([
            high - low,
            (high - cp).abs(),
            (low - cp).abs(),
        ], axis=1).max(axis=1)
        return float(tr.rolling(period, min_periods=1).mean().iloc[-1])
    except Exception as exc:
        logger.warning("ATR fetch failed for %s: %s", symbol, exc)
        return None


# ---------------------------------------------------------------------------
# Core exit logic
# ---------------------------------------------------------------------------

async def _exit_one(ib: IB, rec: dict, cfg: dict, dry_run: bool) -> bool:
    """Evaluate and exit one position if it meets the bobblehead criteria."""
    symbol: str = rec["symbol"]
    entry_price: float = float(rec.get("entry_price") or rec.get("price") or 0)
    atr_stored: Optional[float] = rec.get("atr_at_entry")
    trade_id: int = rec["id"]

    if not entry_price or entry_price <= 0:
        return False

    # Fetch current price from IB
    current_price: Optional[float] = None
    try:
        contract = Stock(symbol, "SMART", "USD")
        ib.qualifyContracts(contract)
        ib.reqMarketDataType(3)
        ticker = ib.reqMktData(contract, "", False, False)
        ib.sleep(1.5)
        for attr in ("last", "close", "bid"):
            val = getattr(ticker, attr, float("nan"))
            if val and val == val and val > 0:
                current_price = float(val)
                break
    except Exception as exc:
        logger.warning("Could not fetch IB price for %s: %s", symbol, exc)

    if current_price is None:
        return False

    if current_price >= entry_price:
        logger.debug("%s is profitable (%.2f > %.2f) — no bobblehead exit", symbol, current_price, entry_price)
        return False

    # Use stored ATR if available, otherwise fetch fresh
    atr = atr_stored if (atr_stored and atr_stored > 0) else _fetch_atr(symbol)
    if not atr or atr <= 0:
        atr = entry_price * 0.02   # 2% fallback

    min_loss_atr = float(cfg.get("min_loss_atr_fraction", 0.35))
    drift = entry_price - current_price

    if drift < atr * min_loss_atr:
        logger.debug(
            "%s: drift %.2f < threshold %.2f (%.2f×ATR) — not yet a failed setup",
            symbol, drift, atr * min_loss_atr, min_loss_atr,
        )
        return False

    # Fetch qty before the guard so we can tell assert_no_flip this is a close,
    # not a new short. Selling qty ≤ current long position is a reduce/exit, not a flip.
    qty = int(rec.get("qty") or 1)

    # SAFETY: pre-trade guard — pass qty so the guard allows selling ≤ current long
    try:
        from pre_trade_guard import PreTradeViolation, assert_no_flip
        assert_no_flip(ib, symbol, "SHORT", qty=qty)
    except PreTradeViolation as e:
        logger.error("BOBBLEHEAD EXIT blocked by pre-trade guard: %s", e)
        return False
    except Exception:
        pass   # pre_trade_guard not importable

    logger.info(
        "BOBBLEHEAD EXIT: %s — entry=%.2f, now=%.2f, drift=%.2f vs threshold=%.2f (%.2f×ATR)",
        symbol, entry_price, current_price, drift, atr * min_loss_atr, min_loss_atr,
    )

    if dry_run:
        logger.info("[DRY RUN] Would exit %s @ ~%.2f", symbol, current_price)
        return True

    # Place market SELL to close
    try:
        contract = Stock(symbol, "SMART", "USD")
        ib.qualifyContracts(contract)
        # qty already fetched above
        sell_order = MarketOrder("SELL", qty)
        sell_order.tif = "DAY"
        sell_order.outsideRth = False
        trade_obj = ib.placeOrder(contract, sell_order)
        ib.sleep(3)
        fill_price = trade_obj.orderStatus.avgFillPrice or current_price
    except Exception as exc:
        logger.error("Sell order failed for %s: %s", symbol, exc)
        return False

    _mark_exited(trade_id, fill_price)

    # Log to exit journal
    EXIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with EXIT_LOG.open("a") as f:
        f.write(json.dumps({
            "date": datetime.now().date().isoformat(),
            "symbol": symbol,
            "trade_id": trade_id,
            "entry_price": entry_price,
            "exit_price": fill_price,
            "pnl_pct": round((fill_price - entry_price) / entry_price * 100, 2),
            "drift_atr_fractions": round(drift / atr, 2),
            "reason": "BOBBLEHEAD_EXIT",
        }) + "\n")

    # Telegram notification
    try:
        from telegram_notifier import send_telegram
        pnl_pct = (fill_price - entry_price) / entry_price * 100
        send_telegram(
            f"🚪 BOBBLEHEAD EXIT: {symbol}\n"
            f"Entry: ${entry_price:.2f} → Exit: ${fill_price:.2f} ({pnl_pct:+.1f}%)\n"
            f"Drift {drift:.2f} > {min_loss_atr:.2f}× ATR threshold after 2 days — failed setup"
        )
    except Exception:
        pass

    return True


async def run(dry_run: bool = False) -> None:
    """Main entry point — evaluate all stale open longs."""
    cfg = _load_config()
    if not cfg.get("enabled", True):
        logger.info("Bobblehead exit is disabled (risk.json → bobblehead_exit.enabled=false)")
        return

    days_window = int(cfg.get("days_window", 2))
    candidates = _get_open_long_candidates(days_window)
    if not candidates:
        logger.info("No open long positions held ≥ %d days — nothing to evaluate", days_window)
        return

    logger.info("Evaluating %d open long(s) held ≥ %d days for bobblehead exit", len(candidates), days_window)

    ib = IB()
    connected = False
    for port in _load_ib_ports():
        try:
            await ib.connectAsync("127.0.0.1", port, clientId=CLIENT_ID, timeout=15)
            logger.info("Connected to IB on port %d", port)
            connected = True
            break
        except Exception as e:
            logger.debug("Port %d failed: %s", port, e)

    if not connected:
        logger.error("Could not connect to IB Gateway — bobblehead exit skipped")
        return

    try:
        exited = 0
        for rec in candidates:
            try:
                ok = await _exit_one(ib, rec, cfg, dry_run)
                if ok:
                    exited += 1
            except Exception as exc:
                logger.error("Error evaluating %s: %s", rec.get("symbol"), exc)
        logger.info("Bobblehead exit complete: %d position(s) exited", exited)
    finally:
        ib.disconnect()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Bobblehead early exit scanner")
    parser.add_argument("--dry-run", action="store_true", help="Log exits without placing orders")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))
