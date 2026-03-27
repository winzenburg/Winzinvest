#!/usr/bin/env python3
"""
One-time MPC covered call unwind.
Step 1: Buy back MPC Apr 240C (1 contract) to close the short call.
Step 2: Sell 51 shares of MPC at market.
"""
from __future__ import annotations

import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

HOST      = "127.0.0.1"
PORT      = 4001
CLIENT_ID = 135  # unique client ID to avoid collision with scheduler


def _wait_for_fill(ib: object, trade: object, timeout: float = 30.0) -> bool:
    import ib_insync
    deadline = time.time() + timeout
    while time.time() < deadline:
        ib.sleep(0.5)
        status = trade.orderStatus.status
        if status == "Filled":
            return True
        if status in ("Cancelled", "Inactive"):
            return False
    return False


def run() -> None:
    import ib_insync

    ib = ib_insync.IB()
    logger.info("Connecting to IBKR at %s:%d (clientId=%d)…", HOST, PORT, CLIENT_ID)
    ib.connect(HOST, PORT, clientId=CLIENT_ID)
    logger.info("Connected")

    try:
        # ── Step 1: Buy back the MPC Apr 240C to close the short call ──
        call = ib_insync.Option(
            conId=808559128,
            symbol="MPC",
            lastTradeDateOrContractMonth="20260417",
            strike=240.0,
            right="C",
            exchange="SMART",
            currency="USD",
        )
        ib.qualifyContracts(call)

        logger.info("Step 1 — BUY 1 MPC Apr 240C to close short call…")
        call_order = ib_insync.MarketOrder(action="BUY", totalQuantity=1, tif="DAY")
        call_trade = ib.placeOrder(call, call_order)
        ib.sleep(1.0)

        filled = _wait_for_fill(ib, call_trade, timeout=30.0)
        if not filled:
            logger.error(
                "MPC call order did NOT fill (status: %s). "
                "Aborting — do NOT sell the stock until the call is closed.",
                call_trade.orderStatus.status,
            )
            return

        fill_price = call_trade.orderStatus.avgFillPrice
        logger.info("✅ MPC 240C closed — filled @ $%.4f", fill_price)

        # ── Step 2: Sell 51 shares of MPC ──
        stock = ib_insync.Stock(
            conId=89495776,
            symbol="MPC",
            exchange="SMART",
            currency="USD",
        )
        ib.qualifyContracts(stock)

        logger.info("Step 2 — SELL 51 MPC at market…")
        stock_order = ib_insync.MarketOrder(action="SELL", totalQuantity=51, tif="DAY")
        stock_trade = ib.placeOrder(stock, stock_order)
        ib.sleep(1.0)

        filled = _wait_for_fill(ib, stock_trade, timeout=30.0)
        if filled:
            fill_price = stock_trade.orderStatus.avgFillPrice
            logger.info("✅ MPC stock sold — 51 shares @ $%.2f (~$%.0f proceeds)", fill_price, fill_price * 51)
        else:
            logger.error(
                "MPC stock order did NOT fill (status: %s). Check TWS.",
                stock_trade.orderStatus.status,
            )

    finally:
        logger.info("Disconnecting…")
        ib.disconnect()


if __name__ == "__main__":
    run()
