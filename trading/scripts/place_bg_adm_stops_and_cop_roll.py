#!/usr/bin/env python3
# DEPRECATED: BG and ADM positions were closed manually on 2026-03-20.
# COP roll was handled separately. This script is kept for audit purposes only.
# DO NOT RUN — positions no longer exist.
"""
One-time: place GTC stop orders for BG and ADM, and price the COP roll.

BG  — LONG 200 @ $126.91  → stop at $116.75 (-8% from entry)
ADM — LONG 200 @ $71.20   → stop at $65.50  (-8% from entry)

COP Apr 10 $126C (ITM/ATM) — price a roll to Apr 17 / May 16 at $129 or $130.

clientId: 129 (one-time, safe per registry)
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
TRADING_DIR = SCRIPTS_DIR.parent
LOGS_DIR    = TRADING_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(SCRIPTS_DIR))
from env_loader import load_env
load_env()
from kill_switch_guard import kill_switch_active

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "bg_adm_stops_cop_roll.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ── Stop parameters ───────────────────────────────────────────────────────────
STOPS = [
    {"symbol": "BG",  "qty": 200, "avg_cost": 126.905, "stop_pct": 0.08},
    {"symbol": "ADM", "qty": 200, "avg_cost": 71.201,  "stop_pct": 0.08},
]

# ── COP roll targets to price ─────────────────────────────────────────────────
COP_BUY_BACK = {"symbol": "COP", "expiry": "20260410", "strike": 126.0, "right": "C", "qty": 1}
COP_ROLL_TARGETS = [
    {"expiry": "20260417", "strike": 128.0, "label": "Apr17 $128"},
    {"expiry": "20260417", "strike": 130.0, "label": "Apr17 $130"},
    {"expiry": "20260516", "strike": 128.0, "label": "May16 $128"},
    {"expiry": "20260516", "strike": 130.0, "label": "May16 $130"},
    {"expiry": "20260516", "strike": 132.0, "label": "May16 $132"},
]


def _mid(ticker) -> float | None:
    bid = ticker.bid if (ticker.bid and ticker.bid > 0) else None
    ask = ticker.ask if (ticker.ask and ticker.ask > 0) else None
    if bid and ask:
        return round((bid + ask) / 2, 3)
    if ask:
        return round(ask * 0.97, 3)
    return None


def resolve_option(ib, symbol: str, expiry: str, strike: float, right: str) -> object | None:
    """Use reqContractDetails to get live conId — works after hours."""
    from ib_insync import Option
    partial = Option(symbol, expiry, 0.0, right, "SMART", "", "USD")
    details = ib.reqContractDetails(partial)
    for d in details:
        c = d.contract
        if abs(c.strike - strike) < 0.01:
            return c
    return None


def run() -> None:
    if kill_switch_active(TRADING_DIR):
        log.error("Kill switch ACTIVE — aborting")
        sys.exit(1)

    from ib_insync import IB, Stock, StopOrder

    host = os.getenv("IB_HOST", "127.0.0.1")
    port = int(os.getenv("IB_PORT", "4001"))
    ib = IB()

    connected = False
    for cid in (129, 130, 131):
        try:
            ib.connect(host, port, clientId=cid, timeout=15)
            log.info("Connected (clientId=%d)", cid)
            connected = True
            break
        except Exception as exc:
            log.warning("clientId=%d failed: %s", cid, exc)

    if not connected:
        log.error("Cannot connect to IB Gateway at %s:%d", host, port)
        sys.exit(1)

    results = {"stops_placed": [], "cop_roll_pricing": [], "timestamp": datetime.now().isoformat()}

    try:
        # ── 1. Place GTC stop orders for BG and ADM ───────────────────────────
        log.info("=" * 60)
        log.info("SECTION 1 — Stop orders for BG and ADM")
        log.info("=" * 60)

        for cfg in STOPS:
            sym         = cfg["symbol"]
            qty         = cfg["qty"]
            avg_cost    = cfg["avg_cost"]
            stop_price  = round(avg_cost * (1 - cfg["stop_pct"]), 2)
            stop_pct_disp = cfg["stop_pct"] * 100

            log.info("%s: avg_cost=$%.2f  stop_pct=%.0f%%  stop_price=$%.2f",
                     sym, avg_cost, stop_pct_disp, stop_price)

            # Check we actually hold this position
            live_pos = 0
            for p in ib.positions():
                if p.contract.symbol == sym and p.contract.secType == "STK":
                    live_pos = int(p.position)
            if live_pos <= 0:
                log.warning("%s: no live LONG position found (live_pos=%d) — skipping", sym, live_pos)
                results["stops_placed"].append({"symbol": sym, "status": "skipped_no_position"})
                continue

            # Check for existing stop orders on this symbol.
            # Use openTrades() — Trade objects have both .contract and .order;
            # openOrders() returns Order objects which have no .contract attribute.
            existing_stops = [
                t for t in ib.openTrades()
                if t.contract.symbol == sym
                   and t.order.orderType in ("STP", "STOP", "STP LMT")
            ]
            if existing_stops:
                log.info("%s: existing stop order already found — skipping to avoid duplicates", sym)
                results["stops_placed"].append({"symbol": sym, "status": "already_exists"})
                continue

            # Qualify stock contract
            stk = Stock(sym, "SMART", "USD")
            qualified = ib.qualifyContracts(stk)
            if not qualified:
                log.error("%s: could not qualify stock contract — skipping", sym)
                results["stops_placed"].append({"symbol": sym, "status": "qualify_failed"})
                continue
            stk = qualified[0]

            # Place GTC stop order (SELL to exit long)
            stop_order = StopOrder("SELL", qty, stop_price)
            stop_order.tif = "GTC"
            stop_order.outsideRth = True   # trigger in pre/post market too

            trade = ib.placeOrder(stk, stop_order)
            ib.sleep(1.5)

            status = getattr(trade.orderStatus, "status", "unknown")
            oid    = trade.order.orderId
            log.info("%s: stop order placed → orderId=%s  status=%s  stop=$%.2f",
                     sym, oid, status, stop_price)

            pct_from_current = (stop_price - avg_cost * (1 - 0)) / avg_cost * 100  # just for reference
            results["stops_placed"].append({
                "symbol": sym,
                "qty": qty,
                "avg_cost": avg_cost,
                "stop_price": stop_price,
                "stop_pct_from_entry": -stop_pct_disp,
                "order_id": oid,
                "status": status,
                "tif": "GTC",
                "outside_rth": True,
            })

        # ── 2. Price the COP Apr 10 $126C roll ───────────────────────────────
        log.info("=" * 60)
        log.info("SECTION 2 — COP Apr10 $126C roll pricing")
        log.info("=" * 60)

        # Get current price of short call (buy-back leg)
        buy_back_contract = resolve_option(
            ib, COP_BUY_BACK["symbol"], COP_BUY_BACK["expiry"],
            COP_BUY_BACK["strike"], COP_BUY_BACK["right"]
        )

        buy_back_mid = None
        if buy_back_contract:
            ticker = ib.reqMktData(buy_back_contract, "", False, False)
            ib.sleep(2.5)
            buy_back_mid = _mid(ticker)
            ib.cancelMktData(buy_back_contract)
            log.info("COP Apr10 $126C bid=%.3f ask=%.3f mid=%.3f",
                     ticker.bid or 0, ticker.ask or 0, buy_back_mid or 0)
        else:
            log.warning("Could not resolve COP Apr10 $126C — will mark as unavailable")
            buy_back_mid = None

        results["cop_roll_pricing"].append({
            "leg": "BUY_BACK",
            "symbol": "COP",
            "expiry": COP_BUY_BACK["expiry"],
            "strike": COP_BUY_BACK["strike"],
            "right": COP_BUY_BACK["right"],
            "mid": buy_back_mid,
            "note": f"Cost to close short call (debit)"
        })

        # Price each roll target
        for target in COP_ROLL_TARGETS:
            tc = resolve_option(ib, "COP", target["expiry"], target["strike"], "C")
            roll_mid = None
            bid_str = ask_str = "n/a"
            if tc:
                tk = ib.reqMktData(tc, "", False, False)
                ib.sleep(2.0)
                roll_mid = _mid(tk)
                bid_str = f"{tk.bid:.3f}" if tk.bid and tk.bid > 0 else "n/a"
                ask_str = f"{tk.ask:.3f}" if tk.ask and tk.ask > 0 else "n/a"
                ib.cancelMktData(tc)

            # Net credit = new premium received − buy-back cost
            net = None
            if roll_mid is not None and buy_back_mid is not None:
                net = round(roll_mid - buy_back_mid, 3)

            log.info(
                "  %-16s  bid=%-6s ask=%-6s mid=%-6s  net=%s",
                target["label"],
                bid_str, ask_str,
                f"{roll_mid:.3f}" if roll_mid else "n/a",
                (f"+${net*100:.0f}/contract" if net and net > 0 else f"-${abs(net)*100:.0f}/contract") if net is not None else "n/a",
            )

            results["cop_roll_pricing"].append({
                "leg": "SELL_NEW",
                "label": target["label"],
                "symbol": "COP",
                "expiry": target["expiry"],
                "strike": target["strike"],
                "right": "C",
                "mid": roll_mid,
                "net_vs_buyback": net,
                "net_per_contract_dollars": round(net * 100, 2) if net is not None else None,
                "note": (
                    "credit roll" if (net or 0) > 0 else
                    "debit roll" if (net or 0) < 0 else "even"
                )
            })

    finally:
        if ib.isConnected():
            ib.disconnect()
            log.info("Disconnected")

    # Save results
    out_path = LOGS_DIR / "bg_adm_stops_cop_roll_results.json"
    out_path.write_text(json.dumps(results, indent=2))
    log.info("Results saved → %s", out_path)

    # Print summary
    print("\n" + "=" * 60)
    print("STOP ORDERS")
    print("=" * 60)
    for s in results["stops_placed"]:
        if "stop_price" in s:
            print(f"  {s['symbol']:<5}  stop=${s['stop_price']:.2f}  ({s['stop_pct_from_entry']:.0f}% from entry)  "
                  f"orderId={s['order_id']}  status={s['status']}")
        else:
            print(f"  {s['symbol']:<5}  {s['status']}")

    print("\n" + "=" * 60)
    print("COP ROLL PRICING")
    print("=" * 60)
    buyback = next((r for r in results["cop_roll_pricing"] if r["leg"] == "BUY_BACK"), {})
    print(f"  Buy back Apr10 $126C: ${buyback.get('mid', 'n/a')}/contract"
          f"  (cost = ${buyback['mid']*100:.0f}/contract)" if buyback.get("mid") else
          f"  Buy back Apr10 $126C: unavailable")
    print()
    print(f"  {'TARGET':<16}  {'PREMIUM':>8}  {'NET ROLL':>14}  TYPE")
    for r in results["cop_roll_pricing"]:
        if r["leg"] != "SELL_NEW":
            continue
        mid_str = f"${r['mid']:.2f}" if r.get("mid") else "n/a"
        net_str = (f"+${r['net_per_contract_dollars']:.0f}" if r.get("net_per_contract_dollars", 0) > 0
                   else f"-${abs(r['net_per_contract_dollars'] or 0):.0f}") if r.get("net_per_contract_dollars") is not None else "n/a"
        print(f"  {r['label']:<16}  {mid_str:>8}  {net_str:>14}/contract  {r.get('note','')}")
    print("=" * 60)


if __name__ == "__main__":
    run()
