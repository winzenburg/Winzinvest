"""
Tail Hedge Check — Dalio structural crash protection.

Runs daily after the main options execution.  Checks whether the portfolio
has a crash hedge in place and, if conditions are right (VIX < threshold,
no recent hedge, budget available), executes a small SPY put debit spread.

Design:  buy 1-2 SPY puts 8% OTM, sell the same number 15% OTM, ~45 DTE.
Max cost ≈ 1.5% NLV/month.  Max gain ≈ 5–7% of portfolio in a 10%+ crash.
The "insurance premium" is funded by the options premium income.

See risk.json → tail_hedge for all tunable parameters.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from ib_insync import IB, Option, ComboLeg, Contract, LimitOrder, util

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("tail_hedge_check")

SCRIPTS_DIR = Path(__file__).resolve().parent
TRADING_DIR = SCRIPTS_DIR.parent
LOGS_DIR = TRADING_DIR / "logs"
sys.path.insert(0, str(SCRIPTS_DIR))

CLIENT_ID = 137  # reserved — not in use by any scheduler job


def _send_telegram(msg: str) -> None:
    try:
        from notifications import send_telegram
        send_telegram(msg)
    except Exception:
        pass


def run() -> None:
    """Entry point: connect IB, evaluate hedge need, execute if warranted."""
    try:
        risk_cfg = json.loads((TRADING_DIR / "risk.json").read_text())
        cfg = risk_cfg.get("tail_hedge", {})
    except Exception as exc:
        logger.error("Could not read risk.json: %s", exc)
        return

    if not cfg.get("enabled", False):
        logger.info("Tail hedge disabled in risk.json — skipping")
        return

    util.patchAsyncio()
    ib = IB()
    connected = False
    for port in [4001, 4002, 7496, 7497]:
        try:
            ib.connect("127.0.0.1", port, clientId=CLIENT_ID, timeout=8)
            connected = True
            logger.info("Connected on port %d", port)
            break
        except Exception:
            pass

    if not connected:
        logger.warning("IB offline — skipping tail hedge check")
        return

    try:
        account_vals = {v.tag: v.value for v in ib.accountValues() if v.currency in ("USD", "")}
        nlv = float(account_vals.get("NetLiquidation", 0))
        if nlv <= 0:
            logger.warning("Could not read NLV — aborting")
            return

        from auto_options_executor import check_tail_hedge_needed
        result = check_tail_hedge_needed(ib, nlv)

        if result["action"] != "execute":
            logger.info("Tail hedge not needed: %s", result["reason"])
            return

        # Place the put debit spread as a BAG combo order
        instrument = result["instrument"]
        expiry_str = result["expiry"].replace("-", "")
        long_strike = result["long_strike"]
        short_strike = result["short_strike"]
        contracts = result["contracts"]
        limit_price = round(result["spread_cost_per_contract"] / 100 * 1.05, 2)  # pay up to 5% above mid

        long_opt = Option(instrument, expiry_str, long_strike, "P", "SMART")
        short_opt = Option(instrument, expiry_str, short_strike, "P", "SMART")
        ib.qualifyContracts(long_opt, short_opt)

        bag = Contract()
        bag.symbol = instrument
        bag.secType = "BAG"
        bag.currency = "USD"
        bag.exchange = "SMART"
        leg1 = ComboLeg()
        leg1.conId = long_opt.conId
        leg1.ratio = 1
        leg1.action = "BUY"
        leg1.exchange = "SMART"
        leg2 = ComboLeg()
        leg2.conId = short_opt.conId
        leg2.ratio = 1
        leg2.action = "SELL"
        leg2.exchange = "SMART"
        bag.comboLegs = [leg1, leg2]

        order = LimitOrder("BUY", contracts, limit_price, tif="DAY")
        trade = ib.placeOrder(bag, order)
        logger.info(
            "Placed tail hedge: BUY %d %s %s $%s/$%s put spread @ $%.2f limit",
            contracts, instrument, result["expiry"], long_strike, short_strike, limit_price,
        )

        for _ in range(60):
            ib.sleep(1)
            filled = sum(f.execution.shares for f in trade.fills)
            if filled >= contracts:
                fill_px = trade.orderStatus.avgFillPrice
                logger.info("FILLED tail hedge @ $%.2f (total cost $%.0f)", fill_px, fill_px * 100 * contracts)
                log_entry = {
                    "placed_at": datetime.now().isoformat(),
                    "instrument": instrument,
                    "expiry": result["expiry"],
                    "long_strike": long_strike,
                    "short_strike": short_strike,
                    "contracts": contracts,
                    "fill_price": fill_px,
                    "nlv_at_hedge": nlv,
                    "vix": result["vix"],
                }
                (LOGS_DIR / "tail_hedge_log.json").write_text(json.dumps(log_entry, indent=2))
                _send_telegram(
                    f"🛡 *Tail Hedge Placed*\n\n"
                    f"{contracts}x {instrument} {result['expiry']} "
                    f"${long_strike}/${short_strike} put spread\n"
                    f"Cost: ${fill_px * 100 * contracts:.0f} total | "
                    f"Max gain: ${result['max_gain']:,.0f}\n"
                    f"VIX: {result['vix']:.1f}"
                )
                break
        else:
            logger.warning("Tail hedge order not filled in 60s — left as open order")
            _send_telegram(
                f"⚠️ *Tail Hedge Pending*\n"
                f"{contracts}x {instrument} {result['expiry']} "
                f"${long_strike}/${short_strike} — not filled in 60s"
            )

    finally:
        ib.disconnect()
        logger.info("Disconnected")


if __name__ == "__main__":
    run()
