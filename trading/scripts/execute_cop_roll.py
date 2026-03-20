#!/usr/bin/env python3
"""
One-time: Roll COP Apr10 $126C → May15 $130C for a net credit.

Leg 1: BUY TO CLOSE  1x COP 20260410 $126C (close existing short)
Leg 2: SELL TO OPEN  1x COP 20260515 $130C (open new short)

Executes each leg as a GTC limit order near mid-price, waits for fill,
then proceeds to Leg 2 only if Leg 1 confirms filled.

clientId: 134
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
TRADING_DIR  = SCRIPTS_DIR.parent
LOGS_DIR     = TRADING_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(SCRIPTS_DIR))
from env_loader import load_env
load_env()
from kill_switch_guard import kill_switch_active

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "cop_roll.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ── Roll parameters ───────────────────────────────────────────────────────────
SYMBOL   = "COP"
QTY      = 1
BUY_BACK = {"expiry": "20260410", "strike": 126.0, "right": "C"}
SELL_NEW = {"expiry": "20260515", "strike": 130.0, "right": "C"}

# How far from mid to set limit price (tighter = better fill, riskier to miss)
LIMIT_OFFSET = 0.05   # $0.05 away from mid
FILL_WAIT_SEC = 90    # seconds to wait for each leg before giving up


def _resolve_contract(ib, symbol: str, expiry: str, strike: float, right: str):
    """
    Resolve an options contract robustly.

    Strategy:
    1. Qualify the underlying stock to get its conId.
    2. Use reqSecDefOptParams to discover the exchange for this symbol's options.
    3. Use reqContractDetails with the exact strike on the discovered exchange.
    This avoids the "partial Option with strike=0" SMART routing ambiguity.
    """
    from ib_insync import Stock, Option

    # Step 1 — qualify underlying
    stk = Stock(symbol, "SMART", "USD")
    qualified = ib.qualifyContracts(stk)
    if not qualified:
        log.error("Could not qualify underlying %s", symbol)
        return None
    stk_q = qualified[0]
    log.info("Underlying %s conId=%s primaryExchange=%s",
             symbol, stk_q.conId, stk_q.primaryExchange)

    # Step 2 — get option chain metadata
    chains = ib.reqSecDefOptParams(stk_q.symbol, "", stk_q.secType, stk_q.conId)
    ib.sleep(1)
    if not chains:
        log.error("No option chains found for %s", symbol)
        return None
    chain = max(chains, key=lambda c: len(c.strikes))
    log.info("Using exchange=%s for options chain", chain.exchange)

    # Step 3 — reqContractDetails with exact strike
    partial = Option(symbol, expiry, strike, right, chain.exchange, "100", "USD")
    details = ib.reqContractDetails(partial)
    if not details:
        # Fallback to SMART
        log.warning("Exchange %s failed, retrying with SMART", chain.exchange)
        partial = Option(symbol, expiry, strike, right, "SMART", "100", "USD")
        details = ib.reqContractDetails(partial)

    if not details:
        log.error("No contract details found for %s %s $%.1f%s", symbol, expiry, strike, right)
        return None

    return details[0].contract


def _mid_and_contract(ib, symbol: str, expiry: str, strike: float, right: str):
    """Resolve contract and get mid price."""
    contract = _resolve_contract(ib, symbol, expiry, strike, right)
    if not contract:
        return None, None, None

    log.info("Resolved: %s  conId=%s", contract.localSymbol, contract.conId)

    # Request streaming quote; retry for up to 12 seconds to handle
    # the Error 10091 subscription delay on API market data.
    bid, ask = None, None
    ticker = ib.reqMktData(contract, "", False, False)
    for _attempt in range(6):
        ib.sleep(2)
        b = ticker.bid if (ticker.bid and ticker.bid > 0) else None
        a = ticker.ask if (ticker.ask and ticker.ask > 0) else None
        # Also check last trade price as a fallback reference
        last = ticker.last if (ticker.last and ticker.last > 0) else None
        if b or a or last:
            bid, ask = b, a
            if not bid and not ask and last:
                # Use last as mid approximation if no bid/ask yet
                bid = round(last * 0.99, 2)
                ask = round(last * 1.01, 2)
                log.info("  Using last=$%.2f as bid/ask proxy (no quote yet)", last)
            break
        log.info("  Waiting for market data... attempt %d/6", _attempt + 1)
    ib.cancelMktData(contract)

    if bid and ask:
        mid = round((bid + ask) / 2, 2)
    elif ask:
        mid = round(ask * 0.97, 2)
    elif bid:
        mid = round(bid * 1.03, 2)
    else:
        mid = None
        log.warning("No market data for %s — cannot compute mid", contract.localSymbol)

    return contract, mid, (bid, ask)


def _place_limit_and_wait(ib, contract, action: str, qty: int, limit_price: float,
                           label: str, use_market: bool = False) -> tuple[bool, float]:
    """Place a limit (or market) order and poll for fill. Returns (success, fill_price)."""
    from ib_insync import LimitOrder, MarketOrder

    if use_market:
        order = MarketOrder(action, qty)
        order.tif = "DAY"
        order.openClose = "C"   # explicitly mark as closing transaction
        log.info("%s: using MARKET order (closing leg)", label)
    else:
        order = LimitOrder(action, qty, limit_price)
        order.tif = "GTC"
        order.outsideRth = False
        order.openClose = "O"   # opening new short

    trade = ib.placeOrder(contract, order)
    ib.sleep(1)

    log.info("%s: placed %s %dx %s limit=$%.2f orderId=%s",
             label, action, qty, contract.localSymbol, limit_price,
             trade.order.orderId)

    deadline = time.time() + FILL_WAIT_SEC
    while time.time() < deadline:
        ib.sleep(2)
        status = getattr(trade.orderStatus, "status", "")
        fill   = float(trade.orderStatus.avgFillPrice or 0)

        if status in ("Filled", "PartiallyFilled") and fill > 0:
            log.info("%s: FILLED @ $%.4f (status=%s)", label, fill, status)
            return True, fill

        if status in ("Cancelled", "ApiCancelled", "Inactive"):
            log.error("%s: order cancelled/inactive (status=%s)", label, status)
            return False, 0.0

        log.info("%s: waiting... status=%s", label, status)

    # Timed out — cancel the order so we don't have a lingering open order
    log.warning("%s: timed out after %ds — cancelling order", label, FILL_WAIT_SEC)
    try:
        ib.cancelOrder(trade.order)
        ib.sleep(2)
    except Exception as exc:
        log.warning("Cancel failed: %s", exc)
    return False, 0.0


def _check_market_hours() -> None:
    """Abort gracefully if US equity options market is closed."""
    try:
        import pytz
        from datetime import datetime as dt
        et = pytz.timezone("America/New_York")
        now = dt.now(et)
        if now.weekday() >= 5:
            log.error("Market is closed (weekend). Run on a weekday between 9:30–16:00 ET.")
            sys.exit(1)
        mins = now.hour * 60 + now.minute
        if not (9 * 60 + 30 <= mins < 16 * 60):
            log.error(
                "Market is closed (ET time: %s). Options trade 9:30–16:00 ET. "
                "Re-run during market hours.",
                now.strftime("%H:%M %Z"),
            )
            sys.exit(1)
        log.info("Market open ✓  ET time: %s", now.strftime("%H:%M %Z"))
    except ImportError:
        log.warning("pytz not installed — skipping market hours check")


def run() -> None:
    _check_market_hours()

    if kill_switch_active(TRADING_DIR):
        log.error("Kill switch ACTIVE — aborting")
        sys.exit(1)

    from ib_insync import IB
    import logging as _logging
    _logging.getLogger("ib_insync").setLevel(_logging.CRITICAL)

    host = os.getenv("IB_HOST", "127.0.0.1")
    port = int(os.getenv("IB_PORT", "4001"))
    ib = IB()

    connected = False
    for cid in (134, 135, 136):
        try:
            ib.connect(host, port, clientId=cid, timeout=15)
            log.info("Connected to IB Gateway (clientId=%d, port=%d)", cid, port)
            connected = True
            break
        except Exception as exc:
            log.warning("clientId=%d failed: %s", cid, exc)

    if not connected:
        log.error("Cannot connect to IB Gateway at %s:%d", host, port)
        sys.exit(1)

    result = {
        "timestamp": datetime.now().isoformat(),
        "symbol": SYMBOL,
        "roll": f"Apr10 $126C → May15 $130C",
        "legs": []
    }

    try:
        # ── Leg 1: BUY TO CLOSE Apr10 $126C ─────────────────────────────────
        log.info("=" * 55)
        log.info("LEG 1 — BUY TO CLOSE COP Apr10 $126C")
        log.info("=" * 55)

        bb_contract, bb_mid, bb_quotes = _mid_and_contract(
            ib, SYMBOL, BUY_BACK["expiry"], BUY_BACK["strike"], BUY_BACK["right"]
        )

        if not bb_contract or not bb_mid:
            log.error("Could not resolve or price Apr10 $126C — aborting")
            sys.exit(1)

        bid, ask = bb_quotes
        # For a BTC, we pay the ask-side; limit slightly above mid
        btc_limit = round(bb_mid + LIMIT_OFFSET, 2)
        log.info("Apr10 $126C  bid=$%.2f  ask=$%.2f  mid=$%.2f  btc_limit=$%.2f",
                 bid or 0, ask or 0, bb_mid, btc_limit)

        leg1_ok, leg1_fill = _place_limit_and_wait(
            ib, bb_contract, "BUY", QTY, btc_limit, "LEG1-BTC", use_market=True
        )

        result["legs"].append({
            "leg": 1,
            "action": "BUY_TO_CLOSE",
            "expiry": BUY_BACK["expiry"],
            "strike": BUY_BACK["strike"],
            "limit": btc_limit,
            "fill": leg1_fill,
            "success": leg1_ok,
        })

        if not leg1_ok:
            log.error("LEG 1 failed — NOT proceeding to Leg 2. Short call is still open.")
            return

        log.info("✅ LEG 1 COMPLETE — Apr10 $126C closed @ $%.4f", leg1_fill)
        ib.sleep(2)

        # ── Leg 2: SELL TO OPEN May15 $130C ─────────────────────────────────
        log.info("=" * 55)
        log.info("LEG 2 — SELL TO OPEN COP May15 $130C")
        log.info("=" * 55)

        sto_contract, sto_mid, sto_quotes = _mid_and_contract(
            ib, SYMBOL, SELL_NEW["expiry"], SELL_NEW["strike"], SELL_NEW["right"]
        )

        if not sto_contract or not sto_mid:
            log.error(
                "Could not resolve or price May15 $130C — Leg 1 already closed! "
                "COP position is now UNCOVERED. Place Leg 2 manually in TWS."
            )
            result["legs"].append({
                "leg": 2, "action": "SELL_TO_OPEN",
                "expiry": SELL_NEW["expiry"], "strike": SELL_NEW["strike"],
                "fill": 0, "success": False,
                "error": "Could not price contract — place manually"
            })
            return

        bid2, ask2 = sto_quotes
        # For an STO, we collect premium; limit slightly below mid
        sto_limit = round(sto_mid - LIMIT_OFFSET, 2)
        log.info("May15 $130C  bid=$%.2f  ask=$%.2f  mid=$%.2f  sto_limit=$%.2f",
                 bid2 or 0, ask2 or 0, sto_mid, sto_limit)

        leg2_ok, leg2_fill = _place_limit_and_wait(
            ib, sto_contract, "SELL", QTY, sto_limit, "LEG2-STO"
        )

        result["legs"].append({
            "leg": 2,
            "action": "SELL_TO_OPEN",
            "expiry": SELL_NEW["expiry"],
            "strike": SELL_NEW["strike"],
            "limit": sto_limit,
            "fill": leg2_fill,
            "success": leg2_ok,
        })

        if leg2_ok:
            net_credit = round(leg2_fill - leg1_fill, 4)
            net_dollars = round(net_credit * 100, 2)
            log.info("✅ LEG 2 COMPLETE — May15 $130C sold @ $%.4f", leg2_fill)
            log.info("─" * 55)
            log.info("ROLL COMPLETE")
            log.info("  Bought back Apr10 $126C @ $%.4f  (cost  = $%.0f)", leg1_fill, leg1_fill * 100)
            log.info("  Sold      May15 $130C  @ $%.4f  (credit = $%.0f)", leg2_fill, leg2_fill * 100)
            log.info("  Net: %s$%.0f/contract", "+" if net_credit >= 0 else "", net_dollars)
            result["net_credit_per_contract"] = net_credit
            result["net_dollars"]             = net_dollars
        else:
            log.error(
                "LEG 2 FAILED — Apr10 $126C is closed but May15 $130C was NOT opened. "
                "COP is now UNCOVERED. Open Leg 2 manually in TWS immediately."
            )

    finally:
        if ib.isConnected():
            ib.disconnect()
            log.info("Disconnected")

        out = LOGS_DIR / "cop_roll_result.json"
        out.write_text(json.dumps(result, indent=2))
        log.info("Result saved → %s", out)


if __name__ == "__main__":
    run()
