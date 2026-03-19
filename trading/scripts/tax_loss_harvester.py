#!/usr/bin/env python3
"""
Tax-Loss Harvester
==================
Scans portfolio for unrealized losses eligible for tax-loss harvesting.
Identifies positions with losses > threshold held > 30 days, and suggests
correlated replacement names to maintain market exposure while booking the loss.

Runs weekly (Friday pre-close) via the scheduler. Can also be invoked manually.

Wash-sale rules:
  - Cannot repurchase the same security within 30 days before or after the sale.
  - The replacement must be "substantially different" — correlated ETF or
    sector peer, not the identical ticker.

Usage:
  python3 tax_loss_harvester.py              # scan + report
  python3 tax_loss_harvester.py --execute    # scan + execute harvests
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
TRADING_DIR = SCRIPTS_DIR.parent
LOGS_DIR = TRADING_DIR / "logs"
RISK_PATH = TRADING_DIR / "risk.json"
ENV_PATH = TRADING_DIR / ".env"
HARVEST_LOG = LOGS_DIR / "tax_loss_harvests.jsonl"

LOGS_DIR.mkdir(exist_ok=True)
sys.path.insert(0, str(SCRIPTS_DIR))
from kill_switch_guard import kill_switch_active

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [tlh] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGS_DIR / "tax_loss_harvester.log"),
    ],
)
log = logging.getLogger("tlh")

if ENV_PATH.exists():
    for line in ENV_PATH.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "4001"))
IB_CLIENT_ID = 196

MIN_LOSS_USD = 200.0
MIN_LOSS_PCT = 5.0
MIN_HOLDING_DAYS = 31

SECTOR_REPLACEMENTS: Dict[str, List[str]] = {
    "Energy": ["XLE", "VDE", "IYE"],
    "Technology": ["XLK", "VGT", "IGV"],
    "Healthcare": ["XLV", "VHT", "IBB"],
    "Financials": ["XLF", "VFH", "KBE"],
    "Consumer Discretionary": ["XLY", "VCR"],
    "Consumer Staples": ["XLP", "VDC"],
    "Industrials": ["XLI", "VIS"],
    "Materials": ["XLB", "VAW"],
    "Real Estate": ["XLRE", "VNQ", "IYR"],
    "Utilities": ["XLU", "VPU"],
    "Communication Services": ["XLC", "VOX"],
    "ETF": ["SPY", "QQQ", "IWM"],
}


def _notify(msg: str) -> None:
    log.info(msg)
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat = os.getenv("TELEGRAM_CHAT_ID", "")
    if token and chat:
        try:
            import urllib.request, urllib.parse
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = urllib.parse.urlencode({
                "chat_id": chat, "text": f"[TLH] {msg}", "parse_mode": "HTML",
            }).encode()
            urllib.request.urlopen(url, data=data, timeout=5)
        except Exception:
            pass


def _estimate_holding_days(symbol: str, avg_cost: float) -> int:
    """Rough estimate of holding period from execution logs."""
    try:
        exec_path = LOGS_DIR / "executions.json"
        if not exec_path.exists():
            return 60
        text = exec_path.read_text().strip()
        for line in reversed(text.splitlines()):
            try:
                obj = json.loads(line)
                if isinstance(obj, dict) and obj.get("symbol") == symbol:
                    ts = obj.get("timestamp", "")
                    entry_date = datetime.fromisoformat(ts.replace("Z", "").split("+")[0]).date()
                    return (date.today() - entry_date).days
            except (json.JSONDecodeError, ValueError):
                continue
    except Exception:
        pass
    return 60


def scan_harvest_candidates(ib: Any) -> List[Dict[str, Any]]:
    """Scan portfolio for tax-loss harvesting opportunities."""
    candidates: List[Dict[str, Any]] = []
    try:
        from sector_gates import SECTOR_MAP
    except ImportError:
        SECTOR_MAP = {}

    for item in ib.portfolio():
        contract = item.contract
        if getattr(contract, "secType", "") != "STK":
            continue
        if float(item.position or 0) <= 0:
            continue

        symbol = contract.symbol
        qty = float(item.position)
        avg_cost = float(item.averageCost or 0)
        mkt_price = float(item.marketPrice) if item.marketPrice else avg_cost
        mkt_value = float(item.marketValue or 0)
        unrealized_pnl = float(item.unrealizedPNL or 0)

        if unrealized_pnl >= 0:
            continue

        loss_pct = abs(unrealized_pnl / (avg_cost * qty) * 100) if avg_cost * qty > 0 else 0
        if abs(unrealized_pnl) < MIN_LOSS_USD or loss_pct < MIN_LOSS_PCT:
            continue

        holding_days = _estimate_holding_days(symbol, avg_cost)
        if holding_days < MIN_HOLDING_DAYS:
            continue

        sector = SECTOR_MAP.get(symbol, "Unknown")
        replacements = SECTOR_REPLACEMENTS.get(sector, ["SPY"])
        replacements = [r for r in replacements if r != symbol]

        candidates.append({
            "symbol": symbol,
            "quantity": int(qty),
            "avg_cost": round(avg_cost, 2),
            "market_price": round(mkt_price, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "loss_pct": round(loss_pct, 2),
            "holding_days": holding_days,
            "sector": sector,
            "tax_savings_est": round(abs(unrealized_pnl) * 0.24, 2),
            "replacements": replacements[:3],
        })

    candidates.sort(key=lambda c: c["unrealized_pnl"])
    return candidates


def execute_harvest(ib: Any, candidate: Dict[str, Any], replacement: str, dry_run: bool) -> bool:
    """Sell the losing position and buy the replacement."""
    from ib_insync import Stock, MarketOrder
    symbol = candidate["symbol"]
    qty = candidate["quantity"]

    log.info(f"{'[DRY] ' if dry_run else ''}HARVEST: sell {qty} {symbol} "
             f"(loss ${candidate['unrealized_pnl']:,.0f}), buy {replacement}")

    if dry_run:
        return True

    if kill_switch_active():
        log.error("Kill switch active — harvest aborted")
        return False

    try:
        sell_contract = Stock(symbol, "SMART", "USD")
        ib.qualifyContracts(sell_contract)
        sell_order = MarketOrder("SELL", qty, tif="DAY")
        sell_trade = ib.placeOrder(sell_contract, sell_order)

        sell_status = ""
        for _ in range(30):
            ib.sleep(1)
            sell_status = sell_trade.orderStatus.status
            if sell_status in ("Filled", "PartiallyFilled"):
                break
            if sell_status in ("Cancelled", "ApiCancelled", "Inactive"):
                break

        if sell_status not in ("Filled", "PartiallyFilled"):
            log.warning(f"  Sell order not filled for {symbol}: {sell_status}")
            return False

        sell_price = float(sell_trade.orderStatus.avgFillPrice or 0) or candidate["market_price"]
        proceeds = sell_price * qty

        buy_contract = Stock(replacement, "SMART", "USD")
        ib.qualifyContracts(buy_contract)

        import yfinance as yf
        h = yf.download(replacement, period="2d", progress=False, auto_adjust=True)
        if h.empty:
            log.warning(f"  No price data for replacement {replacement}")
            return False
        cl = h["Close"]
        if hasattr(cl, "columns"):
            cl = cl.iloc[:, 0]
        repl_price = float(cl.iloc[-1])
        buy_qty = max(1, int(proceeds / repl_price))

        buy_order = MarketOrder("BUY", buy_qty, tif="DAY")
        buy_trade = ib.placeOrder(buy_contract, buy_order)
        ib.sleep(3)

        harvest_record = {
            "timestamp": datetime.now().isoformat(),
            "sold_symbol": symbol,
            "sold_qty": qty,
            "sold_price": sell_price,
            "loss_harvested": candidate["unrealized_pnl"],
            "tax_savings_est": candidate["tax_savings_est"],
            "replacement": replacement,
            "replacement_qty": buy_qty,
            "buy_status": buy_trade.orderStatus.status,
        }

        with open(HARVEST_LOG, "a") as f:
            f.write(json.dumps(harvest_record) + "\n")

        _notify(f"✅ Harvested <b>{symbol}</b>: loss ${abs(candidate['unrealized_pnl']):,.0f} "
                f"→ bought {buy_qty} {replacement} (~${candidate['tax_savings_est']:,.0f} tax savings)")
        return True

    except Exception as e:
        log.error(f"  Harvest execution failed: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Tax-Loss Harvester")
    parser.add_argument("--execute", action="store_true", help="Execute harvests (default: scan only)")
    parser.add_argument("--max-harvests", type=int, default=3, help="Max harvests per run")
    args = parser.parse_args()

    log.info("Tax-Loss Harvester starting [%s]", "EXECUTE" if args.execute else "SCAN")

    from ib_insync import IB
    ib = IB()
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=10)
        log.info("Connected to IB")
    except Exception as e:
        log.error(f"IB connect failed: {e}")
        return

    try:
        candidates = scan_harvest_candidates(ib)

        if not candidates:
            log.info("No tax-loss harvesting opportunities found.")
            return

        log.info(f"\n{'='*60}")
        log.info(f"HARVEST CANDIDATES: {len(candidates)}")
        log.info(f"{'='*60}")

        total_savings = 0.0
        for c in candidates:
            log.info(f"  {c['symbol']:6s}  loss ${abs(c['unrealized_pnl']):>8,.0f}  "
                     f"({c['loss_pct']:.1f}%)  held {c['holding_days']}d  "
                     f"tax save ~${c['tax_savings_est']:,.0f}  "
                     f"→ {', '.join(c['replacements'])}")
            total_savings += c["tax_savings_est"]

        log.info(f"\nTotal estimated tax savings: ${total_savings:,.0f}")

        if not args.execute:
            _notify(f"📊 TLH Scan: {len(candidates)} candidates, ~${total_savings:,.0f} potential tax savings")
            return

        if kill_switch_active():
            log.error("Kill switch is ACTIVE — tax-loss harvest execution aborted.")
            return

        harvested = 0
        for c in candidates[:args.max_harvests]:
            replacement = c["replacements"][0] if c["replacements"] else "SPY"
            success = execute_harvest(ib, c, replacement, dry_run=False)
            if success:
                harvested += 1

        log.info(f"\nHarvested {harvested}/{min(len(candidates), args.max_harvests)} positions")

    finally:
        ib.disconnect()
        log.info("Disconnected from IB")


if __name__ == "__main__":
    main()
