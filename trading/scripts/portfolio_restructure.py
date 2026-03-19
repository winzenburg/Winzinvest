#!/usr/bin/env python3
"""
Portfolio Restructure — phased liquidation of hedge, ETF, and low-conviction
positions to free capital for the momentum engine.

Phase 1 (Tue): Close decay hedges (TZA, VXX, VIXY) + worst energy (CF, VLO, USO)
Phase 2 (Wed): Close commodity ETFs (GSG, DBC, PDBC, ERX) + weak names (CZR, LBRT)
Phase 3 (Fri): Auto-review MAYBE positions — trim if 5-day momentum is negative

Before selling any stock with a short covered call, the call is bought-to-close
first to avoid naked exposure.

Usage:
    python portfolio_restructure.py --phase 1           # dry-run Phase 1
    python portfolio_restructure.py --phase 1 --live    # execute Phase 1
    python portfolio_restructure.py --phase auto        # detect current day, run correct phase
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path
from typing import Any

from ib_insync import IB, MarketOrder, Option, Stock

SCRIPTS_DIR = Path(__file__).resolve().parent
TRADING_DIR = SCRIPTS_DIR.parent
LOGS_DIR = TRADING_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(SCRIPTS_DIR))
from env_loader import load_env as _load_env_fn
_load_env_fn()
from sector_gates import SECTOR_MAP
from trade_log_db import update_trade_exit

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [restructure] %(levelname)-8s %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "portfolio_restructure.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "4001"))
IB_CLIENT_ID = 122  # 116 is in portfolio_snapshot retry pool (111-119) — use 122 to avoid Error 326

KILL_SWITCH = TRADING_DIR / "kill_switch.json"
CC_EXCEPTIONS = TRADING_DIR / "covered_call_exceptions.json"

PHASE_1_SYMBOLS = {"TZA", "VXX", "VIXY", "CF", "VLO", "USO"}
PHASE_2_SYMBOLS = {"GSG", "DBC", "PDBC", "ERX", "CZR", "LBRT"}
PHASE_3_MAYBE   = {"AES", "BK", "CE", "CVX", "DE", "EBAY", "OXY", "LYB"}


# ── Notifications ────────────────────────────────────────────────────────────

def _notify(msg: str) -> None:
    try:
        from notifications import notify_info
        notify_info(msg)
    except Exception as e:
        log.warning("Telegram failed: %s", e)


# ── IB helpers ───────────────────────────────────────────────────────────────

def get_nlv(ib: IB) -> float:
    for av in ib.accountValues():
        if av.tag == "NetLiquidation" and av.currency == "USD":
            return float(av.value)
    return 0.0


def get_excess_liquidity(ib: IB) -> float:
    for av in ib.accountValues():
        if av.tag == "ExcessLiquidity" and av.currency == "USD":
            return float(av.value)
    return 0.0


def get_stock_positions(ib: IB) -> dict[str, dict[str, Any]]:
    """Return {SYMBOL: {qty, avg_cost, market_price, market_value, unrealized_pnl}}."""
    out: dict[str, dict[str, Any]] = {}
    for item in ib.portfolio():
        c = item.contract
        if c.secType != "STK" or item.position <= 0:
            continue
        sym = c.symbol.upper()
        qty = int(item.position)
        avg = float(item.averageCost)
        mp = float(item.marketPrice) if item.marketPrice else avg
        mv = float(item.marketValue)
        pnl = float(item.unrealizedPNL)
        out[sym] = {
            "qty": qty, "avg_cost": avg, "market_price": mp,
            "market_value": mv, "unrealized_pnl": pnl,
        }
    return out


def get_open_calls(ib: IB) -> dict[str, list[dict[str, Any]]]:
    """Return {ROOT_SYMBOL: [{strike, expiry, qty, contract}]} for short calls."""
    calls: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in ib.portfolio():
        c = item.contract
        if c.secType == "OPT" and c.right == "C" and int(item.position) < 0:
            calls[c.symbol.upper()].append({
                "strike": float(c.strike),
                "expiry": str(c.lastTradeDateOrContractMonth),
                "qty": abs(int(item.position)),
                "contract": c,
            })
    return dict(calls)


# ── Order execution ──────────────────────────────────────────────────────────

def btc_calls(ib: IB, symbol: str, calls: list[dict], dry_run: bool) -> list[dict]:
    results = []
    for call in calls:
        qty = call["qty"]
        contract = Option(symbol, call["expiry"], call["strike"], "C", "SMART")
        ib.qualifyContracts(contract)
        ib.sleep(0.5)
        label = f"BTC {qty}x {symbol} {call['expiry'][:6]} ${call['strike']}C"

        if dry_run:
            log.info("  [DRY] %s", label)
            results.append({"action": "BTC", "symbol": symbol, "qty": qty, "status": "dry_run", "fill": 0})
            continue

        order = MarketOrder("BUY", qty)
        trade = ib.placeOrder(contract, order)
        ib.sleep(5)
        status = trade.orderStatus.status
        fill = trade.orderStatus.avgFillPrice or 0
        log.info("  %s → %s @ $%.2f", label, status, fill)
        results.append({"action": "BTC", "symbol": symbol, "qty": qty, "status": status, "fill": fill})
    return results


def sell_stock(ib: IB, symbol: str, qty: int, dry_run: bool) -> dict[str, Any]:
    contract = Stock(symbol, "SMART", "USD")
    ib.qualifyContracts(contract)
    ib.sleep(0.5)
    label = f"SELL {qty}x {symbol}"

    if dry_run:
        log.info("  [DRY] %s", label)
        return {"action": "SELL", "symbol": symbol, "qty": qty, "status": "dry_run", "fill": 0}

    order = MarketOrder("SELL", qty)
    trade = ib.placeOrder(contract, order)

    # Wait up to 30s for a confirmed fill before recording to trades.db
    status = ""
    fill = 0.0
    for _ in range(30):
        ib.sleep(1)
        status = trade.orderStatus.status
        fill = float(trade.orderStatus.avgFillPrice or 0)
        if status == "Filled":
            break
        if status in ("Cancelled", "ApiCancelled", "Inactive"):
            break

    if status != "Filled":
        log.error("  %s → NOT FILLED after 30s (status=%s) — skipping DB update", label, status)
    else:
        log.info("  %s → %s @ $%.2f", label, status, fill)
    return {"action": "SELL", "symbol": symbol, "qty": qty, "status": status, "fill": fill}


# ── trades.db updates ────────────────────────────────────────────────────────

def mark_trade_closed(symbol: str, exit_price: float, exit_reason: str) -> None:
    """Find the open DB record for this symbol and mark it closed."""
    db_path = TRADING_DIR / "logs" / "trades.db"
    if not db_path.exists():
        return
    try:
        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT id, entry_price, qty, timestamp FROM trades "
            "WHERE symbol=? AND status='Filled' AND exit_price IS NULL "
            "ORDER BY id DESC LIMIT 1",
            (symbol,),
        ).fetchone()
        if not row:
            log.warning("No open DB record for %s", symbol)
            conn.close()
            return
        trade_id, entry_price, qty, entry_ts = row
        pnl = (exit_price - entry_price) * qty
        pnl_pct = pnl / (entry_price * qty) if entry_price * qty > 0 else 0

        holding_days = 0
        try:
            entry_dt = datetime.fromisoformat(entry_ts[:19])
            holding_days = max(0, (datetime.now() - entry_dt).days)
        except (ValueError, TypeError):
            pass

        update_trade_exit(
            trade_id=trade_id,
            exit_price=exit_price,
            exit_timestamp=datetime.now().isoformat(),
            exit_reason=exit_reason,
            realized_pnl=round(pnl, 2),
            realized_pnl_pct=round(pnl_pct, 4),
            holding_days=holding_days,
        )
        conn.close()
        log.info("  DB: %s closed id=%d pnl=$%.2f", symbol, trade_id, pnl)
    except Exception as e:
        log.error("DB update failed for %s: %s", symbol, e)


# ── Kill switch ──────────────────────────────────────────────────────────────

def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def deactivate_kill_switch() -> None:
    try:
        ks = json.loads(KILL_SWITCH.read_text()) if KILL_SWITCH.exists() else {}
        ks["active"] = False
        ks["reason"] = "Auto-deactivated after Phase 1 restructure"
        ks["deactivated_at"] = datetime.now().isoformat()
        _atomic_write_json(KILL_SWITCH, ks)
        log.info("Kill switch deactivated")
    except Exception as e:
        log.error("Failed to deactivate kill switch: %s", e)


def _is_kill_switch_active() -> bool:
    try:
        if not KILL_SWITCH.exists():
            return False
        ks = json.loads(KILL_SWITCH.read_text())
        return bool(ks.get("active"))
    except Exception:
        return True  # fail closed on unreadable file


# ── Covered-call exceptions cleanup ─────────────────────────────────────────

def remove_cc_exceptions(symbols: set[str]) -> None:
    if not CC_EXCEPTIONS.exists():
        return
    try:
        data = json.loads(CC_EXCEPTIONS.read_text())
        for sym in symbols:
            data.pop(sym, None)
        CC_EXCEPTIONS.write_text(json.dumps(data, indent=2))
        log.info("Removed %d symbols from covered_call_exceptions.json", len(symbols))
    except Exception as e:
        log.warning("Could not update covered_call_exceptions: %s", e)


# ── Phase logic ──────────────────────────────────────────────────────────────

def run_phase(
    ib: IB,
    target_symbols: set[str],
    phase_name: str,
    exit_reason: str,
    dry_run: bool,
) -> list[dict[str, Any]]:
    """Close all target_symbols: BTC calls first, then sell stock."""
    positions = get_stock_positions(ib)
    open_calls = get_open_calls(ib)
    all_results: list[dict[str, Any]] = []

    # Filter to symbols we actually hold
    to_close = [sym for sym in target_symbols if sym in positions]
    if not to_close:
        log.info("%s: no target positions found — nothing to do.", phase_name)
        return []

    log.info("=== %s — %d positions to close ===", phase_name, len(to_close))

    for sym in sorted(to_close):
        pos = positions[sym]
        qty = pos["qty"]
        log.info("\n  Processing %s (%d shares, $%.0f)", sym, qty, pos["market_value"])

        # Step 1: BTC any covered calls
        if sym in open_calls:
            btc_results = btc_calls(ib, sym, open_calls[sym], dry_run)
            all_results.extend(btc_results)
            ib.sleep(1)

        # Step 2: Sell stock
        result = sell_stock(ib, sym, qty, dry_run)
        all_results.append(result)

        # Step 3: Update trades.db — only on confirmed fill
        if not dry_run and result.get("status") == "Filled" and result.get("fill", 0) > 0:
            mark_trade_closed(sym, result["fill"], exit_reason)
        elif not dry_run and result.get("status") != "Filled":
            log.warning("Skipping trades.db update for %s — order not confirmed filled (status=%s)",
                        sym, result.get("status"))

    return all_results


def run_phase_3_maybe(ib: IB, dry_run: bool) -> list[dict[str, Any]]:
    """Auto-review MAYBE positions — trim any with negative 5-day momentum."""
    import yfinance as yf

    positions = get_stock_positions(ib)
    held = [sym for sym in PHASE_3_MAYBE if sym in positions]
    if not held:
        log.info("Phase 3: no MAYBE positions remaining.")
        return []

    log.info("=== PHASE 3 — Reviewing %d MAYBE positions ===", len(held))

    # Fetch 5-day price data
    tickers = " ".join(held)
    data = yf.download(tickers, period="5d", progress=False)
    if data.empty:
        log.warning("Could not fetch price data for MAYBE symbols")
        return []

    close = data["Close"]
    trim_list: list[str] = []
    keep_list: list[str] = []

    for sym in held:
        pos = positions[sym]
        ret_pct = pos["unrealized_pnl"] / (pos["avg_cost"] * pos["qty"]) * 100 if pos["avg_cost"] * pos["qty"] > 0 else 0

        # 5-day momentum
        try:
            if hasattr(close, "columns") and sym in close.columns:
                series = close[sym].dropna()
            else:
                series = close.dropna()
            mom_5d = (float(series.iloc[-1]) / float(series.iloc[0]) - 1) * 100 if len(series) >= 2 else 0
        except Exception:
            mom_5d = 0

        if mom_5d < 0 and ret_pct < 0:
            log.info("  TRIM %s: 5d_mom=%.1f%% ret=%.1f%%", sym, mom_5d, ret_pct)
            trim_list.append(sym)
        else:
            log.info("  KEEP %s: 5d_mom=%.1f%% ret=%.1f%%", sym, mom_5d, ret_pct)
            keep_list.append(sym)

    if not trim_list:
        log.info("Phase 3: all MAYBE positions pass momentum check — keeping all.")
        return []

    return run_phase(ib, set(trim_list), "PHASE 3 TRIMS", "REBALANCE_MAYBE", dry_run)


# ── Main ─────────────────────────────────────────────────────────────────────

def run(phase: int | str, dry_run: bool = True) -> None:
    # Kill switch check — restructure is destructive so we respect it even for sell-side
    if not dry_run and _is_kill_switch_active():
        log.error("Kill switch is ACTIVE — portfolio restructure aborted. Deactivate manually first.")
        sys.exit(1)

    ib = IB()
    ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID, timeout=15)
    log.info("Connected to IB on port %d", IB_PORT)

    results: list[dict[str, Any]] = []
    nlv_before = 0.0
    excess_before = 0.0

    try:
        nlv_before = get_nlv(ib)
        excess_before = get_excess_liquidity(ib)
        log.info("Pre-restructure: NLV=$%.0f  ExcessLiq=$%.0f", nlv_before, excess_before)

        if phase in (1, "1"):
            results = run_phase(ib, PHASE_1_SYMBOLS, "PHASE 1: Hedges + Energy", "REBALANCE_HEDGE", dry_run)
            if not dry_run and results:
                deactivate_kill_switch()
                remove_cc_exceptions(PHASE_1_SYMBOLS)

        elif phase in (2, "2"):
            results = run_phase(ib, PHASE_2_SYMBOLS, "PHASE 2: ETFs + Weak", "REBALANCE_ETF", dry_run)
            if not dry_run and results:
                remove_cc_exceptions(PHASE_2_SYMBOLS)

        elif phase in (3, "3"):
            results = run_phase_3_maybe(ib, dry_run)
            if not dry_run and results:
                trimmed = {r["symbol"] for r in results if r.get("action") == "SELL"}
                remove_cc_exceptions(trimmed)

        elif phase == "auto":
            today = date.today().weekday()  # 0=Mon, 1=Tue, ...
            if today == 1:
                log.info("Auto-detected TUESDAY → Phase 1")
                results = run_phase(ib, PHASE_1_SYMBOLS, "PHASE 1: Hedges + Energy", "REBALANCE_HEDGE", dry_run)
                if not dry_run and results:
                    deactivate_kill_switch()
                    remove_cc_exceptions(PHASE_1_SYMBOLS)
            elif today in (2, 3):
                log.info("Auto-detected WED/THU → Phase 2")
                results = run_phase(ib, PHASE_2_SYMBOLS, "PHASE 2: ETFs + Weak", "REBALANCE_ETF", dry_run)
                if not dry_run and results:
                    remove_cc_exceptions(PHASE_2_SYMBOLS)
            elif today == 4:
                log.info("Auto-detected FRIDAY → Phase 3")
                results = run_phase_3_maybe(ib, dry_run)
                if not dry_run and results:
                    trimmed = {r["symbol"] for r in results if r.get("action") == "SELL"}
                    remove_cc_exceptions(trimmed)
            else:
                log.info("Auto: no restructure phase scheduled for today (%s)", date.today().strftime("%A"))
                return
        else:
            log.error("Unknown phase: %s", phase)
            return

        # Post-trade margin report
        ib.sleep(3)
        nlv_after = get_nlv(ib)
        excess_after = get_excess_liquidity(ib)
    finally:
        ib.disconnect()

    # Summary
    sells = [r for r in results if r.get("action") == "SELL"]
    btcs = [r for r in results if r.get("action") == "BTC"]
    filled_sells = [r for r in sells if r.get("status") in ("Filled", "dry_run")]
    total_proceeds = sum(r.get("fill", 0) * r.get("qty", 0) for r in filled_sells)

    log.info("\n=== RESTRUCTURE SUMMARY ===")
    log.info("  Stocks sold:    %d", len(sells))
    log.info("  Calls BTC'd:    %d", len(btcs))
    log.info("  Est proceeds:   $%s", f"{total_proceeds:,.0f}")
    log.info("  NLV:            $%s → $%s", f"{nlv_before:,.0f}", f"{nlv_after:,.0f}")
    log.info("  Excess Liq:     $%s → $%s", f"{excess_before:,.0f}", f"{excess_after:,.0f}")

    # Telegram summary
    mode = "DRY-RUN" if dry_run else "LIVE"
    lines = [f"<b>Portfolio Restructure ({mode})</b>"]
    for r in results:
        act = r.get("action", "?")
        sym = r.get("symbol", "?")
        qty = r.get("qty", 0)
        st = r.get("status", "?")
        fill = r.get("fill", 0)
        px_str = f" @ ${fill:.2f}" if fill > 0 else ""
        lines.append(f"  {act} {qty}x {sym} → {st}{px_str}")
    lines.append(f"\nNLV: ${nlv_before:,.0f} → ${nlv_after:,.0f}")
    lines.append(f"Excess Liq: ${excess_before:,.0f} → ${excess_after:,.0f}")
    _notify("\n".join(lines))

    # Write result log
    log_path = LOGS_DIR / f"restructure_phase{phase}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    log_path.write_text(json.dumps({
        "phase": str(phase),
        "dry_run": dry_run,
        "timestamp": datetime.now().isoformat(),
        "nlv_before": nlv_before,
        "nlv_after": nlv_after,
        "excess_before": excess_before,
        "excess_after": excess_after,
        "results": results,
    }, indent=2))
    log.info("Log written to %s", log_path.name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Portfolio restructure — phased liquidation")
    parser.add_argument("--phase", required=True, help="1, 2, 3, or auto")
    parser.add_argument("--live", action="store_true", help="Execute real orders (default: dry-run)")
    args = parser.parse_args()

    phase_arg: int | str
    if args.phase in ("1", "2", "3"):
        phase_arg = int(args.phase)
    else:
        phase_arg = args.phase

    run(phase=phase_arg, dry_run=not args.live)
