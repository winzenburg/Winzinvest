#!/usr/bin/env python3
"""
Options Position Manager
========================
Active management of existing short options (covered calls & CSPs).
Runs every 30 minutes during market hours via the scheduler.

Actions:
  1. PROFIT-TAKE  — Buy-to-close when premium has decayed ≥80% (configurable via risk.json → options_management.profit_take_pct)
  2. STOP-LOSS    — Buy-to-close when loss exceeds 2× collected premium
  3. ROLL         — Close + reopen when DTE ≤7 or position goes ITM
  4. EXPIRY CLOSE — Force-close positions expiring today/tomorrow

Config lives in risk.json → "options_management".

Usage:
  python3 options_position_manager.py              # live execution
  python3 options_position_manager.py --dry-run     # scan + report, no trades
"""

import json
import logging
import os
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Optional

SCRIPTS_DIR = Path(__file__).resolve().parent
TRADING_DIR = SCRIPTS_DIR.parent
LOGS_DIR    = TRADING_DIR / "logs"
RISK_PATH   = TRADING_DIR / "risk.json"
ENV_PATH    = TRADING_DIR / ".env"

LOGS_DIR.mkdir(exist_ok=True)
sys.path.insert(0, str(SCRIPTS_DIR))

from logging_config import setup_rotating_logger
log = setup_rotating_logger("opt_mgr", "options_position_manager.log", max_bytes=10*1024*1024, backup_count=2)

# ── Load .env ─────────────────────────────────────────────────────────────────
if ENV_PATH.exists():
    for line in ENV_PATH.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "4001"))
IB_CLIENT_ID = 194

# ── Config ────────────────────────────────────────────────────────────────────

def _cfg() -> dict:
    try:
        return json.loads(RISK_PATH.read_text()).get("options_management", {})
    except Exception:
        return {}

PROFIT_TAKE_PCT       = lambda: float(_cfg().get("profit_take_pct", 0.80))
REOPEN_AFTER_PT       = lambda: bool(_cfg().get("reopen_after_profit_take", True))
STOP_LOSS_MULT        = lambda: float(_cfg().get("stop_loss_multiplier", 2.0))
ROLL_DTE_THRESH       = lambda: int(_cfg().get("roll_dte_threshold", 7))
ROLL_ITM_THRESH_PCT   = lambda: float(_cfg().get("roll_itm_threshold_pct", -2.0))
CLOSE_DTE_THRESH      = lambda: int(_cfg().get("close_dte_threshold", 1))
ROLL_TARGET_DTE       = lambda: int(_cfg().get("roll_target_dte", 35))
ROLL_TARGET_OTM_PCT   = lambda: float(_cfg().get("roll_target_otm_pct", 10.0))
MAX_ROLLS_PER_DAY     = lambda: int(_cfg().get("max_rolls_per_day", 5))


# ── Notifications ─────────────────────────────────────────────────────────────

def _notify(msg: str) -> None:
    log.info(msg)
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat  = os.getenv("TELEGRAM_CHAT_ID", "")
    if token and chat:
        try:
            import urllib.request, urllib.parse
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = urllib.parse.urlencode({
                "chat_id": chat, "text": f"[opt_mgr] {msg}", "parse_mode": "HTML",
            }).encode()
            urllib.request.urlopen(url, data=data, timeout=5)
        except Exception:
            pass


def _in_market_hours() -> bool:
    import zoneinfo
    now_et = datetime.now(zoneinfo.ZoneInfo("America/New_York"))
    if now_et.weekday() >= 5:
        return False
    open_t  = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    close_t = now_et.replace(hour=15, minute=55, second=0, microsecond=0)
    return open_t <= now_et <= close_t


# ── Price fetching (yfinance, not IB) ────────────────────────────────────────

def _fetch_prices(symbols: list[str]) -> dict[str, float]:
    import yfinance as yf
    prices: dict[str, float] = {}
    if not symbols:
        return prices
    for sym in symbols:
        try:
            h = yf.download(sym, period="2d", progress=False, auto_adjust=True)
            if h.empty:
                continue
            cl = h["Close"]
            if hasattr(cl, "columns"):
                cl = cl.iloc[:, 0]
            prices[sym] = round(float(cl.iloc[-1]), 2)
        except Exception:
            pass
    return prices


# ── Position analysis ─────────────────────────────────────────────────────────

def _get_option_positions(ib: Any) -> list[dict]:
    positions: list[dict] = []
    for pos in ib.positions():
        c = pos.contract
        if c.secType != "OPT" or pos.position == 0:
            continue
        positions.append({
            "contract":  c,
            "symbol":    c.symbol,
            "strike":    c.strike,
            "right":     c.right,
            "expiry":    c.lastTradeDateOrContractMonth,
            "qty":       int(pos.position),
            "avg_cost":  float(pos.avgCost),
            "conId":     c.conId,
        })
    return positions


def _get_market_price(ib: Any, contract: Any) -> Optional[float]:
    """Get mid-price for an option contract. Tries IB first, falls back to yfinance."""
    mid = _get_market_price_ib(ib, contract)
    if mid is not None:
        return mid
    return _get_market_price_yf(contract)


def _get_market_price_ib(ib: Any, contract: Any) -> Optional[float]:
    """Try IB market data (delayed type 3) for option mid-price."""
    try:
        ib.qualifyContracts(contract)
        for mdt in (3, 4):
            ib.reqMarketDataType(mdt)
            ticker = ib.reqMktData(contract, "", False, False)
            ib.sleep(2)
            mid = None
            if ticker.bid and ticker.ask and ticker.bid > 0 and ticker.ask > 0:
                mid = (ticker.bid + ticker.ask) / 2.0
            elif ticker.last and ticker.last > 0:
                mid = ticker.last
            elif ticker.close and ticker.close > 0:
                mid = ticker.close
            ib.cancelMktData(contract)
            if mid is not None:
                return mid
        return None
    except Exception as e:
        log.warning(f"IB price fetch failed for {contract.symbol}: {e}")
        return None


def _get_market_price_yf(contract: Any) -> Optional[float]:
    """Fallback: fetch option mid-price from yfinance options chain."""
    try:
        import yfinance as yf
        import math

        symbol = getattr(contract, "symbol", "")
        expiry = getattr(contract, "lastTradeDateOrContractMonth", "")
        strike = getattr(contract, "strike", 0)
        right = getattr(contract, "right", "")
        if not (symbol and expiry and strike and right):
            return None

        yf_expiry = f"{expiry[:4]}-{expiry[4:6]}-{expiry[6:]}"
        chain = yf.Ticker(symbol).option_chain(yf_expiry)
        df = chain.calls if right == "C" else chain.puts
        row = df.loc[df["strike"] == strike]
        if row.empty:
            nearest_idx = (df["strike"] - strike).abs().idxmin()
            row = df.loc[[nearest_idx]]
            if abs(float(row["strike"].iloc[0]) - strike) > strike * 0.02:
                return None

        bid_v = float(row["bid"].iloc[0])
        ask_v = float(row["ask"].iloc[0])
        if bid_v > 0 and ask_v > 0:
            return round((bid_v + ask_v) / 2, 2)
        last_v = float(row["lastPrice"].iloc[0])
        if last_v > 0 and not math.isnan(last_v):
            return round(last_v, 2)
        return None
    except Exception as e:
        log.debug(f"yfinance price fallback failed for {getattr(contract, 'symbol', '?')}: {e}")
        return None


def _analyze_position(pos: dict, spot: float) -> dict:
    """Determine what action (if any) to take on a position."""
    today = date.today()
    exp_date = datetime.strptime(pos["expiry"], "%Y%m%d").date()
    dte = (exp_date - today).days
    strike = pos["strike"]
    qty = pos["qty"]
    collected_premium = abs(pos["avg_cost"])

    # Moneyness
    if pos["right"] == "C":
        otm_pct = (strike - spot) / spot * 100 if spot > 0 else 0
    else:
        otm_pct = (spot - strike) / spot * 100 if spot > 0 else 0

    is_short = qty < 0
    is_itm = otm_pct < 0

    result = {
        **pos,
        "spot": spot,
        "dte": dte,
        "otm_pct": otm_pct,
        "is_itm": is_itm,
        "collected_premium": collected_premium,
        "action": "HOLD",
        "reason": "",
        "priority": 0,
    }

    if not is_short:
        return result

    # Priority 1: Expiring today/tomorrow — force close
    if dte <= CLOSE_DTE_THRESH():
        result["action"] = "CLOSE"
        result["reason"] = f"Expiring in {dte}d"
        result["priority"] = 10
        return result

    # Priority 2: Deep ITM — stop-loss or roll
    if is_itm and otm_pct <= ROLL_ITM_THRESH_PCT():
        result["action"] = "ROLL"
        result["reason"] = f"ITM {abs(otm_pct):.1f}% — assignment risk"
        result["priority"] = 9
        return result

    # Priority 3: DTE approaching — roll before theta cliff
    if dte <= ROLL_DTE_THRESH():
        if is_itm:
            result["action"] = "CLOSE"
            result["reason"] = f"ITM with only {dte}d left"
            result["priority"] = 9
        else:
            result["action"] = "ROLL"
            result["reason"] = f"Only {dte}d to expiry — roll for more premium"
            result["priority"] = 7
        return result

    # Priority 4: Stop-loss — current value exceeds 2× collected premium
    # (handled in execution phase when we have live option prices)
    result["_check_stop_loss"] = True

    # Priority 5: Profit-take — premium decayed ≥80% (PROFIT_TAKE_PCT from risk.json)
    # (handled in execution phase when we have live option prices)
    result["_check_profit_take"] = True

    return result


# ── Execution ─────────────────────────────────────────────────────────────────

def _check_conflicting_orders(ib: Any, contract: Any, label: str) -> bool:
    """Check for open orders that would cause IBKR Error 201 on a BTC.

    IBKR rejects BUY orders if a SELL order already exists on the same
    contract (Error 201). Two order types can cause this:

    1. Direct OPT SELL orders (e.g., a standing GTC covered-call STO).
    2. BAG/COMB combo roll orders where the option is the BUY leg of a
       roll spread (BUY current option + SELL new option). These are
       placed as GTC limit combos and also block a plain BTC.

    Orders placed directly in TWS use clientId=0 and are only visible
    via reqAllOpenOrders(). Returns True if a conflict was found.
    """
    sym = getattr(contract, "symbol", "?")
    strike = getattr(contract, "strike", 0)
    right = getattr(contract, "right", "?")
    expiry = getattr(contract, "lastTradeDateOrContractMonth", "")
    target_con_id = getattr(contract, "conId", 0)

    try:
        all_orders = ib.reqAllOpenOrders()
        ib.sleep(1)
    except Exception as e:
        log.warning("reqAllOpenOrders failed: %s — proceeding anyway", e)
        return False

    for trade in all_orders:
        oc = trade.contract if hasattr(trade, "contract") else getattr(trade, "contract", None)
        oo = trade.order if hasattr(trade, "order") else getattr(trade, "order", None)
        if oc is None or oo is None:
            continue

        sec_type = getattr(oc, "secType", "")

        # Case 1: plain OPT SELL order on the same contract
        if (
            sec_type == "OPT"
            and getattr(oc, "symbol", "") == sym
            and getattr(oc, "strike", 0) == strike
            and getattr(oc, "right", "") == right
            and getattr(oc, "lastTradeDateOrContractMonth", "")[:8] == expiry[:8]
            and getattr(oo, "action", "").upper() == "SELL"
        ):
            log.error(
                "CONFLICT: open OPT SELL on %s (orderId=%s, clientId=%s). "
                "Cancel it in TWS before BTC can proceed.",
                label,
                getattr(oo, "orderId", "?"),
                getattr(oo, "clientId", "?"),
            )
            _notify(
                f"⚠️ <b>BTC blocked</b> — open SELL order exists for {label}\n"
                f"Cancel the GTC SELL in TWS, then retry."
            )
            return True

        # Case 2: BAG/COMB combo roll order that includes our option as a leg.
        # A roll spread (BUY current + SELL new) blocks a standalone BTC because
        # IBKR sees an opposing order on the same underlying option contract.
        if sec_type in ("BAG", "COMB") and target_con_id:
            combo_legs = getattr(oc, "comboLegs", []) or []
            for leg in combo_legs:
                if getattr(leg, "conId", None) == target_con_id:
                    order_id = getattr(oo, "orderId", "?")
                    client_id = getattr(oo, "clientId", "?")
                    log.error(
                        "CONFLICT: open BAG combo roll on %s includes this contract "
                        "(orderId=%s, clientId=%s, leg action=%s). "
                        "Cancel the combo order before BTC can proceed.",
                        label,
                        order_id,
                        client_id,
                        getattr(leg, "action", "?"),
                    )
                    _notify(
                        f"⚠️ <b>BTC blocked</b> — GTC combo roll order for {label} "
                        f"(orderId={order_id}, clientId={client_id}) blocks standalone BTC.\n"
                        f"Cancel the combo roll in TWS or via the API, then retry."
                    )
                    return True

    return False


def _buy_to_close(ib: Any, contract: Any, qty: int, label: str, dry_run: bool) -> bool:
    """Buy-to-close a short option position."""
    from ib_insync import MarketOrder
    abs_qty = abs(qty)
    log.info(f"  {'[DRY] ' if dry_run else ''}BUY-TO-CLOSE {abs_qty}× {label}")
    if dry_run:
        return True

    # Pre-flight: detect conflicting SELL orders that would cause Error 201
    if _check_conflicting_orders(ib, contract, label):
        return False

    try:
        ib.qualifyContracts(contract)
        order = MarketOrder("BUY", abs_qty, tif="DAY", outsideRth=False)
        trade = ib.placeOrder(contract, order)
        status = ""
        for _ in range(30):
            ib.sleep(1)
            status = trade.orderStatus.status
            if status in ("Filled", "PartiallyFilled"):
                log.info(f"  Order {status}: BTC {abs_qty}× {label}")
                return True
            if status in ("Cancelled", "ApiCancelled", "Inactive"):
                break
        log.warning(f"  Order {status}: BTC {abs_qty}× {label} (not filled in time)")
        return False
    except Exception as e:
        log.error(f"  BTC failed for {label}: {e}")
        return False


def _roll_position(ib: Any, pos: dict, spot: float, dry_run: bool) -> bool:
    """Close existing position and open a new one at target DTE/OTM."""
    from ib_insync import Option, MarketOrder
    label = f"{pos['symbol']} {pos['right']}{pos['strike']} {pos['expiry']}"

    # Step 1: Buy-to-close the existing position
    closed = _buy_to_close(ib, pos["contract"], pos["qty"], label, dry_run)
    if not closed:
        return False

    # Step 2: Find new strike at target OTM% and target DTE
    target_dte = ROLL_TARGET_DTE()
    target_otm = ROLL_TARGET_OTM_PCT() / 100.0
    target_exp_date = date.today() + timedelta(days=target_dte)

    # Snap to a Friday (standard monthly/weekly expiry)
    days_to_fri = (4 - target_exp_date.weekday()) % 7
    if days_to_fri == 0 and target_exp_date.weekday() != 4:
        days_to_fri = 7
    target_exp_date += timedelta(days=days_to_fri)
    target_exp_str = target_exp_date.strftime("%Y%m%d")

    if pos["right"] == "C":
        new_strike = round(spot * (1 + target_otm), 0)
    else:
        new_strike = round(spot * (1 - target_otm), 0)

    # Round to common intervals
    if new_strike >= 200:
        new_strike = round(new_strike / 5) * 5
    elif new_strike >= 50:
        new_strike = round(new_strike / 2.5) * 2.5
    else:
        new_strike = round(new_strike / 1) * 1

    new_contract = Option(pos["symbol"], target_exp_str, new_strike, pos["right"], "SMART")

    log.info(f"  {'[DRY] ' if dry_run else ''}SELL-TO-OPEN {abs(pos['qty'])}× "
             f"{pos['symbol']} {pos['right']}{new_strike} exp {target_exp_str}")

    if dry_run:
        return True

    try:
        qualified = ib.qualifyContracts(new_contract)
        if not qualified:
            log.warning(f"  Could not qualify new contract: {new_contract}")
            _notify(f"⚠️ Roll partial: closed {label} but could not open replacement — "
                    f"{pos['symbol']} {pos['right']}{new_strike} {target_exp_str} not found")
            return False

        order = MarketOrder("SELL", abs(pos["qty"]), tif="DAY", outsideRth=False)
        trade = ib.placeOrder(new_contract, order)
        status = ""
        for _ in range(30):
            ib.sleep(1)
            status = trade.orderStatus.status
            if status in ("Filled", "PartiallyFilled"):
                log.info(f"  Roll complete: {label} → {pos['right']}{new_strike} {target_exp_str} ({status})")
                _notify(f"🔄 Rolled {label} → {pos['right']}{new_strike} exp {target_exp_str}")
                return True
            if status in ("Cancelled", "ApiCancelled", "Inactive"):
                break
        log.warning(f"  Roll STO {status} — new leg may not have filled")
        _notify(f"⚠️ Roll partial: closed {label}, new leg {status}")
        return False
    except Exception as e:
        log.error(f"  Roll STO failed: {e}")
        _notify(f"⚠️ Roll partial: closed {label}, STO failed: {e}")
        return False


# ── Profit-take and reopen ────────────────────────────────────────────────

def _select_roll_strategy(pos: dict, spot: float) -> str:
    """
    Choose between a standard same-DTE roll and a diagonal/calendar strategy.

    Rules:
      • Diagonal (up-and-out): covered call where the underlying has rallied
        significantly (spot > strike × 1.05) — roll to higher strike + longer DTE
        to capture more upside and collect additional premium.
      • Calendar: when IV term structure is favorable (short-term IV significantly
        higher than longer-term IV) — buy the near-term back and sell a longer-dated
        option at the same or slightly higher strike.
      • Standard: all other cases — same-DTE roll to target OTM strike.

    Returns one of: "diagonal", "calendar", "standard"
    """
    if pos.get("right") != "C":
        return "standard"  # calendar/diagonal only implemented for covered calls

    strike = float(pos.get("strike") or 0)
    if strike <= 0:
        return "standard"

    # If stock has rallied well above the short strike, use diagonal to chase upside
    if spot > strike * 1.05:
        return "diagonal"

    # If stock is near ATM and current DTE > 21 days remaining, calendar could work
    dte = int(pos.get("dte") or 30)  # "dte" is always set on PROFIT_ROLL actions
    if dte > 14 and abs(spot - strike) / spot < 0.03:
        return "calendar"

    return "standard"


def _profit_take_and_reopen(ib: Any, pos: dict, spot: float, dry_run: bool) -> bool:
    """Close a profitable short option, then sell-to-open a fresh one at target delta.

    Uses delta_strike_selector for strike selection when available, falling back
    to percentage-based OTM selection. Automatically selects between standard,
    diagonal, and calendar roll strategies based on market conditions.
    """
    from ib_insync import Option, MarketOrder
    label = f"{pos['symbol']} {pos['right']}{pos['strike']} {pos['expiry']}"

    closed = _buy_to_close(ib, pos["contract"], pos["qty"], label, dry_run)
    if not closed:
        return False

    # ── Select roll strategy ─────────────────────────────────────────────────
    roll_strategy = _select_roll_strategy(pos, spot)

    if roll_strategy == "diagonal":
        # Up-and-out: longer DTE + higher strike
        target_dte = max(ROLL_TARGET_DTE() + 21, 45)   # at least 6 weeks out
        target_otm_boost = 0.03                          # 3% higher than standard OTM
        log.info(f"  Strategy: DIAGONAL roll (stock rallied above strike; using +{target_dte}d DTE, +3% strike)")
    elif roll_strategy == "calendar":
        # Same or slightly higher strike, but push to ≥45 DTE for better theta
        target_dte = max(ROLL_TARGET_DTE() + 14, 45)
        target_otm_boost = 0.0                           # keep same OTM as current
        log.info(f"  Strategy: CALENDAR roll (near ATM position; extending DTE to {target_dte}d)")
    else:
        target_dte = ROLL_TARGET_DTE()
        target_otm_boost = 0.0
        log.info(f"  Strategy: STANDARD roll ({target_dte}d DTE)")

    target_exp_date = date.today() + timedelta(days=target_dte)

    days_to_fri = (4 - target_exp_date.weekday()) % 7
    if days_to_fri == 0 and target_exp_date.weekday() != 4:
        days_to_fri = 7
    target_exp_date += timedelta(days=days_to_fri)
    target_exp_str = target_exp_date.strftime("%Y%m%d")

    try:
        from delta_strike_selector import select_strike_by_delta, TARGET_DELTA_COVERED_CALL, TARGET_DELTA_CSP
        target_delta = TARGET_DELTA_COVERED_CALL if pos["right"] == "C" else TARGET_DELTA_CSP
        # For diagonal rolls (stock ran above strike), use a lower delta target
        # so the new strike is selected further OTM, consistent with roll_strategy intent.
        if roll_strategy == "diagonal" and pos["right"] == "C":
            target_delta = max(0.10, target_delta - 0.08)  # e.g. 0.20 → 0.12 (more OTM)
        new_strike = select_strike_by_delta(ib, pos["symbol"], pos["right"], target_exp_str, target_delta)
    except ImportError:
        new_strike = None

    if new_strike is None:
        target_otm = ROLL_TARGET_OTM_PCT() / 100.0 + target_otm_boost
        if pos["right"] == "C":
            new_strike = round(spot * (1 + target_otm), 0)
        else:
            new_strike = round(spot * (1 - target_otm), 0)
        if new_strike >= 200:
            new_strike = round(new_strike / 5) * 5
        elif new_strike >= 50:
            new_strike = round(new_strike / 2.5) * 2.5

    new_contract = Option(pos["symbol"], target_exp_str, new_strike, pos["right"], "SMART")

    strategy_label = {"diagonal": "⬆️ DIAGONAL", "calendar": "📅 CALENDAR", "standard": "🔄 STANDARD"}.get(roll_strategy, "🔄")
    log.info(f"  {'[DRY] ' if dry_run else ''}{strategy_label} REOPEN {abs(pos['qty'])}× "
             f"{pos['symbol']} {pos['right']}{new_strike} exp {target_exp_str}")

    if dry_run:
        _notify(f"[DRY] {strategy_label} Profit-take+reopen {label} → {pos['right']}{new_strike} {target_exp_str}")
        return True

    try:
        qualified = ib.qualifyContracts(new_contract)
        if not qualified:
            log.warning(f"  Could not qualify reopen contract: {new_contract}")
            _notify(f"⚠️ Profit-taken {label} but reopen failed — "
                    f"{pos['right']}{new_strike} {target_exp_str} not found")
            return False

        order = MarketOrder("SELL", abs(pos["qty"]), tif="DAY", outsideRth=False)
        trade = ib.placeOrder(new_contract, order)
        status = ""
        for _ in range(30):
            ib.sleep(1)
            status = trade.orderStatus.status
            if status in ("Filled", "PartiallyFilled"):
                fill = float(trade.orderStatus.avgFillPrice or 0)
                log.info(f"  {strategy_label} Profit-take+reopen: {label} → {pos['right']}{new_strike} "
                         f"{target_exp_str} ({status}, premium=${fill:.2f})")
                _notify(f"{strategy_label} Profit-take+reopen: {label} → {pos['right']}{new_strike} "
                        f"exp {target_exp_str} (${fill:.2f} new premium)")
                return True
            if status in ("Cancelled", "ApiCancelled", "Inactive"):
                break
        log.warning(f"  Reopen STO {status} — new leg may not have filled")
        _notify(f"⚠️ Profit-taken {label}, reopen {status}")
        return False
    except Exception as e:
        log.error(f"  Reopen STO failed: {e}")
        _notify(f"⚠️ Profit-taken {label}, reopen failed: {e}")
        return False


# ── Main loop ─────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Options Position Manager")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only, no trades")
    args = parser.parse_args()
    dry_run = args.dry_run

    _mode = os.getenv("TRADING_MODE", "paper")
    if _mode == "live":
        log.warning("🔴 LIVE TRADING MODE — real money at risk")
    log.info("Options Position Manager [%s]", _mode.upper())

    if not _in_market_hours() and not dry_run:
        log.info("Outside market hours — nothing to do.")
        return

    from ib_insync import IB
    ib = IB()
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=10)
        log.info("Connected to IB")
    except Exception as e:
        log.error(f"IB connect failed: {e}")
        return

    try:
        positions = _get_option_positions(ib)
        short_opts = [p for p in positions if p["qty"] < 0]

        if not short_opts:
            log.info("No short option positions to manage.")
            return

        log.info(f"Found {len(short_opts)} short option positions to evaluate")

        # Fetch spot prices
        symbols = list({p["symbol"] for p in short_opts})
        prices = _fetch_prices(symbols)

        # Analyze each position
        actions: list[dict] = []
        for pos in short_opts:
            spot = prices.get(pos["symbol"], 0)
            if spot <= 0:
                log.warning(f"No price for {pos['symbol']} — skipping")
                continue
            analysis = _analyze_position(pos, spot)
            actions.append(analysis)

        # Check profit-take and stop-loss (requires live option prices)
        for a in actions:
            if a["action"] != "HOLD":
                continue
            if not (a.get("_check_profit_take") or a.get("_check_stop_loss")):
                continue

            mid = _get_market_price(ib, a["contract"])
            if mid is None:
                continue

            collected = a["collected_premium"] / 100.0  # per-share basis
            profit_pct = 1.0 - (mid / collected) if collected > 0 else 0

            if a.get("_check_profit_take") and profit_pct >= PROFIT_TAKE_PCT():
                if REOPEN_AFTER_PT():
                    a["action"] = "PROFIT_ROLL"
                    a["reason"] = f"Profit-take+reopen: {profit_pct:.0%} decay (mid=${mid:.2f} vs collected=${collected:.2f})"
                else:
                    a["action"] = "CLOSE"
                    a["reason"] = f"Profit-take: {profit_pct:.0%} decay (mid=${mid:.2f} vs collected=${collected:.2f})"
                a["priority"] = 5
                a["current_mid"] = mid
                continue

            # Stop-loss: option now worth ≥2× what we collected
            if a.get("_check_stop_loss") and mid >= collected * STOP_LOSS_MULT():
                a["action"] = "CLOSE"
                a["reason"] = f"Stop-loss: mid=${mid:.2f} ≥ {STOP_LOSS_MULT():.0f}× collected=${collected:.2f}"
                a["priority"] = 8
                a["current_mid"] = mid

        # Sort by priority (highest first)
        to_act = sorted([a for a in actions if a["action"] != "HOLD"],
                        key=lambda x: -x["priority"])
        holds = [a for a in actions if a["action"] == "HOLD"]

        log.info(f"\n{'='*60}")
        log.info(f"SCAN RESULTS: {len(to_act)} actions, {len(holds)} holds")
        log.info(f"{'='*60}")

        for a in to_act:
            right_lbl = "C" if a["right"] == "C" else "P"
            log.info(f"  [{a['action']}] {a['symbol']} {right_lbl}{a['strike']} "
                     f"exp {a['expiry']} ({a['dte']}d) — {a['reason']}")

        if not to_act:
            log.info("  All positions healthy — no action needed.")
            return

        rolls_today = 0
        closes = 0
        reopens = 0
        for a in to_act:
            label = f"{a['symbol']} {a['right']}{a['strike']} {a['expiry']}"

            if a["action"] == "CLOSE":
                success = _buy_to_close(ib, a["contract"], a["qty"], label, dry_run)
                if success:
                    closes += 1
                    _notify(f"{'[DRY] ' if dry_run else ''}✅ Closed {label}: {a['reason']}")

            elif a["action"] == "PROFIT_ROLL":
                if rolls_today >= MAX_ROLLS_PER_DAY():
                    log.warning(f"  Max rolls/day ({MAX_ROLLS_PER_DAY()}) reached — closing without reopen")
                    _buy_to_close(ib, a["contract"], a["qty"], label, dry_run)
                    closes += 1
                    continue
                success = _profit_take_and_reopen(ib, a, a["spot"], dry_run)
                if success:
                    rolls_today += 1
                    reopens += 1

            elif a["action"] == "ROLL":
                if rolls_today >= MAX_ROLLS_PER_DAY():
                    log.warning(f"  Max rolls/day ({MAX_ROLLS_PER_DAY()}) reached — skipping {label}")
                    continue
                success = _roll_position(ib, a, a["spot"], dry_run)
                if success:
                    rolls_today += 1

        log.info(f"\nExecution complete: {closes} closed, {rolls_today} rolled "
                 f"({reopens} profit-take reopens){' [DRY RUN]' if dry_run else ''}")

    finally:
        ib.disconnect()
        log.info("Disconnected from IB")


if __name__ == "__main__":
    main()
