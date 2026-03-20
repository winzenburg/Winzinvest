#!/usr/bin/env python3
"""
One-time: Sell 2x APA Apr 17 $41 Call (covered call, ~8% OTM).
Position: 241 shares LONG, avg cost $33.98, current ~$38.02.
Regime: RISK_ON.  DTE: 41 days.  Contracts: 2 (covers 200 of 241 shares).
clientId: 126 (one-time, safe per 030-ib-client-ids.mdc)
"""

import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
TRADING_DIR = SCRIPTS_DIR.parent
LOGS_DIR = TRADING_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(SCRIPTS_DIR))
from env_loader import load_env
load_env()

from kill_switch_guard import kill_switch_active
from ib_fill_wait import wait_ib_order_filled

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "execute_apa_cc.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ── Order parameters ──────────────────────────────────────────────────────────
SYMBOL       = "APA"
EXPIRY       = "20260417"       # April 17, 2026
STRIKE       = 41.0
RIGHT        = "C"
CONTRACTS    = 2
ORDER_ACTION = "SELL"
GTC          = True             # GTC limit — stays on book if market is closed
FILL_WAIT    = int(os.environ.get("IB_ORDER_FILL_WAIT_SEC", "30"))


def run() -> bool:
    if kill_switch_active(TRADING_DIR):
        log.error("Kill switch is ACTIVE — aborting")
        return False

    from ib_insync import IB, Option, LimitOrder
    ib = IB()

    log.info("=" * 60)
    log.info("APA COVERED CALL — %s %s $%.0f%s x%d", SYMBOL, EXPIRY, STRIKE, RIGHT, CONTRACTS)
    log.info("=" * 60)

    # ── Connect ──────────────────────────────────────────────────────────────
    host = os.getenv("IB_HOST", "127.0.0.1")
    port = int(os.getenv("IB_PORT", "4001"))
    connected = False
    for cid in (126, 127, 128):
        try:
            ib.connect(host, port, clientId=cid, timeout=15)
            log.info("Connected (clientId=%d)", cid)
            connected = True
            break
        except Exception as exc:
            log.warning("clientId=%d failed: %s", cid, exc)

    if not connected:
        log.error("Cannot connect to IB Gateway at %s:%d", host, port)
        return False

    try:
        # ── Discover available option chain ───────────────────────────────────
        from ib_insync import Stock
        # APA trades on NASDAQ (NMS); qualifying via SMART often gives wrong conId
        stock = Stock(SYMBOL, "NASDAQ", "USD")
        qualified_stocks = ib.qualifyContracts(stock)
        if not qualified_stocks:
            log.error("Could not qualify underlying stock %s", SYMBOL)
            return False
        stock = qualified_stocks[0]
        log.info("Underlying: %s  conId=%s  exchange=%s  primaryExchange=%s",
                 stock.symbol, stock.conId, stock.exchange, stock.primaryExchange)
        chains = ib.reqSecDefOptParams(stock.symbol, "", stock.secType, stock.conId)
        ib.sleep(1)
        log.info("Raw chains returned: %d", len(chains))
        for c in chains:
            log.info("  chain: exchange=%s  nStrikes=%d  nExps=%d",
                     c.exchange, len(c.strikes), len(c.expirations))

        if not chains:
            log.error("No option chain returned for %s", SYMBOL)
            return False

        # Pick the chain with the most strikes (usually SMART or CBOE)
        chain = max(chains, key=lambda c: len(c.strikes))
        log.info("Chain: exchange=%s  expirations=%d  strikes=%d",
                 chain.exchange, len(chain.expirations), len(chain.strikes))

        # Find the nearest expiration to our target
        target_exp = EXPIRY
        available_exps = sorted(chain.expirations)
        chosen_exp = min(available_exps, key=lambda e: abs(int(e) - int(target_exp)))
        log.info("Available expirations near %s: %s … chosen: %s",
                 target_exp, available_exps[:6], chosen_exp)

        # Find the nearest OTM strike at or above target
        avail_strikes = sorted(float(s) for s in chain.strikes if float(s) >= STRIKE - 3)
        if not avail_strikes:
            log.error("No strikes >= %.0f found in chain", STRIKE - 3)
            return False
        chosen_strike = min(avail_strikes, key=lambda s: abs(s - STRIKE))
        log.info("Target strike: %.1f  →  chosen: %.1f  (from %s)",
                 STRIKE, chosen_strike, [s for s in avail_strikes[:8]])

        # ── Enumerate all listed calls for this expiry via partial lookup ────
        # Strike=0.0 means "unspecified" — IB returns all listed contracts.
        partial = Option(SYMBOL, chosen_exp, 0.0, RIGHT, "SMART", "", "USD")
        all_details = ib.reqContractDetails(partial)
        if not all_details:
            log.warning("No listed contracts on SMART for %s %s %s; trying ISE", SYMBOL, chosen_exp, RIGHT)
            partial.exchange = chain.exchange
            all_details = ib.reqContractDetails(partial)

        log.info("Listed %s %s %s contracts: %d", SYMBOL, chosen_exp, RIGHT, len(all_details))
        available_listed = sorted(
            [(d.contract.strike, d.contract) for d in all_details],
            key=lambda x: x[0]
        )
        log.info("Available listed strikes: %s", [s for s, _ in available_listed])

        if not available_listed:
            log.error("No listed %s calls found for %s %s", RIGHT, SYMBOL, chosen_exp)
            return False

        # Closest strike at or above STRIKE; fall back to nearest if all below
        otm_candidates = [(s, c) for s, c in available_listed if s >= STRIKE - 0.5]
        if otm_candidates:
            chosen_strike_final, opt = min(otm_candidates, key=lambda x: x[0])
        else:
            chosen_strike_final, opt = min(available_listed, key=lambda x: abs(x[0] - STRIKE))
        log.info("Selected: %s  conId=%s  strike=%.1f", opt.localSymbol, opt.conId, opt.strike)

        # ── Get mid price ─────────────────────────────────────────────────────
        ticker = ib.reqMktData(opt, "", False, False)
        ib.sleep(2)
        bid = ticker.bid if ticker.bid and ticker.bid > 0 else None
        ask = ticker.ask if ticker.ask and ticker.ask > 0 else None

        if bid and ask:
            mid = round((bid + ask) / 2, 2)
            log.info("Bid=%.2f  Ask=%.2f  Mid=%.2f", bid, ask, mid)
        elif ask:
            mid = round(ask * 0.95, 2)
            log.warning("No bid — using 95%% of ask: %.2f", mid)
        else:
            log.error("No market data returned — cannot price order")
            return False

        if mid < 0.05:
            log.error("Mid price %.2f seems too low — aborting", mid)
            return False

        ib.cancelMktData(opt)

        # ── Place limit STO order ─────────────────────────────────────────────
        order = LimitOrder(ORDER_ACTION, CONTRACTS, mid)
        order.tif = "GTC" if GTC else "DAY"
        order.transmit = True
        order.account = ""  # use default account

        log.info(
            "Placing: %s %d %s %s $%.0f%s @ $%.2f (TIF=%s)",
            ORDER_ACTION, CONTRACTS, SYMBOL, EXPIRY, STRIKE, RIGHT, mid, order.tif,
        )
        trade = ib.placeOrder(opt, order)

        filled, status = wait_ib_order_filled(ib, trade, max_sec=FILL_WAIT)
        fill_price = float(trade.orderStatus.avgFillPrice or mid)

        log.info(
            "Order result: status=%s  filled=%s  orderId=%s  price=%.2f",
            status, filled, trade.order.orderId, fill_price,
        )
        if filled:
            premium_total = round(fill_price * CONTRACTS * 100, 2)
            log.info(
                "✅ FILLED — premium collected: $%.2f (%.2f × %d × 100)",
                premium_total, fill_price, CONTRACTS,
            )
        else:
            log.info(
                "⏳ Order working (GTC) — orderId=%s  status=%s  "
                "Will fill when APA options market opens if placed after hours.",
                trade.order.orderId, status,
            )

        return True

    finally:
        try:
            if ib.isConnected():
                ib.disconnect()
                log.info("Disconnected")
        except Exception as exc:
            log.warning("Disconnect error: %s", exc)


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
