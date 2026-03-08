#!/usr/bin/env python3
"""
Unified executor for both SHORT and LONG signals.

Loads shorts from watchlist_multimode.json and longs from watchlist_longs.json,
detects market regime, enforces allocation caps, runs mixed-portfolio risk gates
(sector concentration, hedging check), then executes shorts then longs.
Uses clientId=103. Logs to shared executions.json (source_script + type per record).
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ib_insync import IB, Stock, MarketOrder, StopOrder, LimitOrder, Order

from atr_stops import calculate_position_size, compute_stop_tp, compute_trailing_amount, fetch_atr
from candidate_ranking import rank_long_candidates, rank_short_candidates, short_conviction, long_conviction
from enriched_record import build_enriched_record
from execution_gates import check_all_gates
from position_filter import load_current_short_symbols
from regime_detector import calculate_portfolio_allocation, detect_market_regime
from risk_config import (
    get_absolute_max_shares,
    get_daily_loss_limit_pct,
    get_max_long_positions,
    get_max_position_pct_of_equity,
    get_max_sector_concentration_pct,
    get_max_short_positions,
    get_max_total_notional_pct,
    get_risk_per_trade_pct,
)
from sector_gates import (
    SECTOR_MAP,
    check_sector_concentration,
    portfolio_sector_exposure as _portfolio_sector_exposure,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            Path(__file__).resolve().parent.parent / "logs" / "execute_dual_mode.log"
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

from paths import TRADING_DIR
WATCHLIST_MULTIMODE_FILE = TRADING_DIR / "watchlist_multimode.json"
WATCHLIST_LONGS_FILE = TRADING_DIR / "watchlist_longs.json"
# Single shared execution log for all executors (type + source_script per record)
EXECUTION_LOG = TRADING_DIR / "logs" / "executions.json"
LOSS_TRACKER = TRADING_DIR / "logs" / "daily_loss.json"

EXEC_PARAMS = {
    "paper_trading": True,
}


def _load_short_candidates() -> List[Dict[str, Any]]:
    """Build short list from watchlist_multimode.json (short_opportunities + premium_selling)."""
    if not WATCHLIST_MULTIMODE_FILE.exists():
        return []
    try:
        data = json.loads(WATCHLIST_MULTIMODE_FILE.read_text())
    except (OSError, ValueError):
        return []
    modes = data.get("modes", {}) or {}
    seen: Set[str] = set()
    out: List[Dict[str, Any]] = []
    for mode_key in ("short_opportunities", "premium_selling"):
        short_list = (modes.get(mode_key) or {}).get("short", [])
        if not isinstance(short_list, list):
            continue
        for item in short_list:
            if not isinstance(item, dict):
                continue
            symbol = item.get("symbol")
            if not isinstance(symbol, str) or not symbol.strip():
                continue
            symbol = symbol.strip().upper()
            if symbol in seen:
                continue
            try:
                price_f = float(item.get("price") or 0)
            except (TypeError, ValueError):
                continue
            if price_f <= 0:
                continue
            seen.add(symbol)
            out.append({
                "symbol": symbol,
                "price": price_f,
                "score": float(item.get("rs_pct", 0)) if item.get("rs_pct") is not None else 0.0,
                "momentum": float(item.get("recent_return", -0.01)) if item.get("recent_return") is not None else -0.01,
            })
    return out


def _load_long_candidates() -> List[Dict[str, Any]]:
    """Load long_candidates from watchlist_longs.json."""
    if not WATCHLIST_LONGS_FILE.exists():
        return []
    try:
        data = json.loads(WATCHLIST_LONGS_FILE.read_text())
    except (OSError, ValueError):
        return []
    candidates = data.get("long_candidates", [])
    if not isinstance(candidates, list):
        return []
    out: List[Dict[str, Any]] = []
    for c in candidates:
        if not isinstance(c, dict) or not c.get("symbol"):
            continue
        try:
            price = float(c.get("price", 0))
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        out.append({"symbol": (c.get("symbol") or "").strip().upper(), "price": price})
    return out


def check_portfolio_hedging(short_notional: float, long_notional: float) -> bool:
    """Block new entries when portfolio is extremely one-sided (>90% on either side)."""
    total = short_notional + long_notional
    if total <= 0:
        return True
    short_pct = short_notional / total
    long_pct = long_notional / total
    if short_pct > 0.90 or long_pct > 0.90:
        logger.warning(
            "Portfolio hedging BLOCKED: %.0f%% short, %.0f%% long — rebalance before new entries",
            100 * short_pct, 100 * long_pct,
        )
        return False
    if short_pct > 0.80 or long_pct > 0.80:
        logger.warning(
            "Portfolio hedging warning: %.0f%% short, %.0f%% long (consider rebalancing)",
            100 * short_pct, 100 * long_pct,
        )
    return True


def _portfolio_notionals(ib: IB) -> Tuple[float, float]:
    """Return (short_notional, long_notional) in USD from ib.portfolio()."""
    short_val = 0.0
    long_val = 0.0
    try:
        for item in ib.portfolio():
            pos = getattr(item, "position", 0)
            val = getattr(item, "marketValue", 0) or 0
            try:
                v = float(val)
            except (TypeError, ValueError):
                continue
            if pos < 0:
                short_val += abs(v)
            elif pos > 0:
                long_val += v
    except Exception as e:
        logger.warning("Could not compute portfolio notionals: %s", e)
    return short_val, long_val


def _get_account_value(ib: IB) -> float:
    """Prefer NetLiquidation, else TotalCashValue. Used for allocation caps."""
    try:
        for av in ib.accountValues():
            if av.tag == "NetLiquidation" and av.currency == "USD":
                return float(av.value)
        for av in ib.accountValues():
            if av.tag == "TotalCashValue" and av.currency == "USD":
                return float(av.value)
    except Exception as e:
        logger.warning("Could not fetch account value: %s", e)
    return 100_000.0


def _load_daily_loss() -> float:
    loss = 0.0
    if LOSS_TRACKER.exists():
        try:
            data = json.loads(LOSS_TRACKER.read_text())
            if data.get("date") == datetime.now().date().isoformat():
                loss = float(data.get("loss", 0) or 0)
        except (OSError, ValueError, TypeError):
            pass
    return loss


def _check_daily_loss_limit(account_equity: float, daily_loss: float, daily_loss_limit_pct: float = 0.03) -> bool:
    limit = account_equity * daily_loss_limit_pct
    if daily_loss >= limit:
        logger.warning("Daily loss limit exceeded: %.2f / %.2f", daily_loss, limit)
        return False
    return True


async def _execute_short(
    ib: IB,
    candidate: Dict[str, Any],
    current_shorts: Set[str],
    max_shorts: int,
    max_short_notional: float,
    current_short_notional: float,
    account_value: float,
    risk_per_trade_pct: float = 0.01,
    max_position_pct: float = 0.05,
    absolute_max_shares: int = 5000,
    regime: str = "CHOPPY",
) -> Tuple[bool, float, Optional[Dict[str, Any]]]:
    """Execute one short. Returns (success, added_notional, enriched_record_or_None).

    Position size is calculated from risk budget and capped by max_position_pct of equity.
    """
    symbol = candidate["symbol"]
    price = candidate["price"]
    if symbol in current_shorts:
        logger.info("Skipping short %s: already short", symbol)
        return False, 0.0, None
    if len(current_shorts) >= max_shorts:
        logger.info("Skipping short %s: max short positions (%d)", symbol, max_shorts)
        return False, 0.0, None

    try:
        contract = Stock(symbol, "SMART", "USD")
        qualified = await ib.qualifyContractsAsync(contract)
        if not qualified:
            logger.error("Contract qualification failed: %s", symbol)
            return False, 0.0, None
        contract = qualified[0]

        atr = fetch_atr(symbol, ib=ib)
        conv = short_conviction(candidate)
        qty = calculate_position_size(
            account_value, price, atr=atr,
            risk_pct=risk_per_trade_pct,
            max_position_pct=max_position_pct,
            absolute_max_shares=absolute_max_shares,
            conviction=conv,
        )
        notional = price * qty
        if current_short_notional + notional > max_short_notional:
            logger.warning(
                "Skipping short %s: allocation cap (%.0f + %.0f > %.0f)",
                symbol, current_short_notional, notional, max_short_notional,
            )
            return False, 0.0, None

        order = MarketOrder("SELL", qty)
        trade = ib.placeOrder(contract, order)
        for _ in range(20):
            await asyncio.sleep(0.5)
            if trade.isDone():
                break
        status = trade.orderStatus.status
        if status not in ("Filled", "PartiallyFilled"):
            ib.cancelOrder(trade.order)
            logger.warning("Short order not filled, cancelled: %s %s", symbol, status)
            return False, 0.0, None

        entry = float(trade.orderStatus.avgFillPrice or price)
        fill_slippage = abs(entry - price) if entry > 0 else 0.0
        fill_commission = 0.0
        try:
            for fill in trade.fills:
                cr = getattr(fill, "commissionReport", None)
                if cr and getattr(cr, "commission", 0):
                    fill_commission += float(cr.commission)
        except Exception:
            pass
        stop_price, profit_price = compute_stop_tp(entry, "SELL", atr=atr)
        trail_amt = compute_trailing_amount(atr=atr, entry_price=entry)
        trailing_stop = Order(
            action="BUY", orderType="TRAIL", totalQuantity=qty,
            auxPrice=trail_amt, tif="GTC",
        )
        ib.placeOrder(contract, trailing_stop)
        ib.placeOrder(contract, LimitOrder("BUY", qty, profit_price))

        rec = build_enriched_record(
            symbol=symbol, side="SHORT", action="SELL",
            source_script="execute_dual_mode.py", status=status,
            order_id=trade.order.orderId, quantity=qty,
            entry_price=entry, stop_price=stop_price, profit_price=profit_price,
            regime_at_entry=regime, conviction_score=conv, atr_at_entry=atr,
            rs_pct=candidate.get("score") or candidate.get("rs_pct"),
            composite_score=candidate.get("composite_score"),
            structure_quality=candidate.get("structure_quality"),
            rvol_atr=candidate.get("rvol_atr"),
            signal_price=price,
            slippage=fill_slippage,
            extra={"commission": fill_commission},
        )
        logger.info("Short placed: %s qty=%d entry=%.2f trail=%.2f tp=%.2f slip=%.4f", symbol, qty, entry, trail_amt, profit_price, fill_slippage)
        return True, abs(entry * qty), rec
    except Exception as e:
        logger.error("Short execution error %s: %s", symbol, e)
        return False, 0.0, None


async def _execute_long(
    ib: IB,
    candidate: Dict[str, Any],
    current_longs: Set[str],
    max_long_notional: float,
    current_long_notional: float,
    account_value: float = 100_000.0,
    risk_per_trade_pct: float = 0.01,
    max_position_pct: float = 0.05,
    absolute_max_shares: int = 5000,
    regime: str = "CHOPPY",
) -> Tuple[bool, float, Optional[Dict[str, Any]]]:
    """Execute one long. Returns (success, added_notional, enriched_record_or_None).

    Position size is calculated from risk budget and capped by max_position_pct of equity.
    """
    symbol = candidate["symbol"]
    price = candidate["price"]
    if symbol in current_longs:
        logger.info("Skipping long %s: already long", symbol)
        return False, 0.0, None

    try:
        contract = Stock(symbol, "SMART", "USD")
        qualified = await ib.qualifyContractsAsync(contract)
        if not qualified:
            logger.error("Contract qualification failed: %s", symbol)
            return False, 0.0, None
        contract = qualified[0]

        atr = fetch_atr(symbol, ib=ib)
        conv = long_conviction(candidate)
        qty = calculate_position_size(
            account_value, price, atr=atr,
            risk_pct=risk_per_trade_pct,
            max_position_pct=max_position_pct,
            absolute_max_shares=absolute_max_shares,
            conviction=conv,
        )
        notional = price * qty
        if current_long_notional + notional > max_long_notional:
            logger.warning(
                "Skipping long %s: allocation cap (%.0f + %.0f > %.0f)",
                symbol, current_long_notional, notional, max_long_notional,
            )
            return False, 0.0, None

        order = MarketOrder("BUY", qty)
        trade = ib.placeOrder(contract, order)
        for _ in range(20):
            await asyncio.sleep(0.5)
            if trade.isDone():
                break
        status = trade.orderStatus.status
        if status not in ("Filled", "PartiallyFilled"):
            ib.cancelOrder(trade.order)
            logger.warning("Long order not filled, cancelled: %s %s", symbol, status)
            return False, 0.0, None

        entry = float(trade.orderStatus.avgFillPrice or price)
        fill_slippage = abs(entry - price) if entry > 0 else 0.0
        fill_commission = 0.0
        try:
            for fill in trade.fills:
                cr = getattr(fill, "commissionReport", None)
                if cr and getattr(cr, "commission", 0):
                    fill_commission += float(cr.commission)
        except Exception:
            pass
        stop_price, tp_price = compute_stop_tp(entry, "BUY", atr=atr)
        trail_amt = compute_trailing_amount(atr=atr, entry_price=entry)
        trailing_stop = Order(
            action="SELL", orderType="TRAIL", totalQuantity=qty,
            auxPrice=trail_amt, tif="GTC",
        )
        ib.placeOrder(contract, trailing_stop)
        ib.placeOrder(contract, LimitOrder("SELL", qty, tp_price))

        rec = build_enriched_record(
            symbol=symbol, side="LONG", action="BUY",
            source_script="execute_dual_mode.py", status=status,
            order_id=trade.order.orderId, quantity=qty,
            entry_price=entry, stop_price=stop_price, profit_price=tp_price,
            regime_at_entry=regime, conviction_score=conv, atr_at_entry=atr,
            rs_pct=candidate.get("rs_pct") or candidate.get("score"),
            composite_score=candidate.get("composite_score"),
            structure_quality=candidate.get("structure_quality"),
            rvol_atr=candidate.get("rvol_atr"),
            signal_price=price,
            slippage=fill_slippage,
            extra={"commission": fill_commission},
        )
        logger.info("Long placed: %s qty=%d entry=%.2f trail=%.2f tp=%.2f slip=%.4f", symbol, qty, entry, trail_amt, tp_price, fill_slippage)
        return True, entry * qty, rec
    except Exception as e:
        logger.error("Long execution error %s: %s", symbol, e)
        return False, 0.0, None


def _current_long_symbols(ib: IB) -> Set[str]:
    out: Set[str] = set()
    try:
        for pos in ib.positions():
            if getattr(pos.contract, "secType", "") != "STK":
                continue
            if getattr(pos, "position", 0) > 0:
                sym = getattr(pos.contract, "symbol", "")
                if isinstance(sym, str) and sym.strip():
                    out.add(sym.strip().upper())
    except Exception as e:
        logger.warning("Could not fetch positions: %s", e)
    return out


async def run() -> None:
    logger.info("=== DUAL-MODE EXECUTOR (SHORT + LONG) ===")
    ib = IB()
    try:
        await ib.connectAsync("127.0.0.1", 4002, clientId=103)
    except Exception as e:
        logger.error("Connection failed: %s", e)
        return

    try:
        regime = detect_market_regime()
        allocation = calculate_portfolio_allocation(regime)
        account_value = _get_account_value(ib)
        short_notional, long_notional = _portfolio_notionals(ib)
        daily_loss = _load_daily_loss()
        current_shorts = load_current_short_symbols(TRADING_DIR, ib)
        current_longs = _current_long_symbols(ib)
        max_short_positions = get_max_short_positions(TRADING_DIR)

        risk_per_trade_pct = get_risk_per_trade_pct(TRADING_DIR)
        max_position_pct_short = get_max_position_pct_of_equity(TRADING_DIR, side="short")
        max_position_pct_long = get_max_position_pct_of_equity(TRADING_DIR, side="long")
        absolute_max_shares = get_absolute_max_shares(TRADING_DIR)
        daily_loss_limit_pct = get_daily_loss_limit_pct(TRADING_DIR)
        max_long_positions = get_max_long_positions(TRADING_DIR)
        max_total_notional_pct = get_max_total_notional_pct(TRADING_DIR)
        max_short_notional = account_value * allocation["shorts"]
        max_long_notional = account_value * allocation["longs"]

        logger.info(
            "Regime=%s allocation shorts=%.0f%% longs=%.0f%% account=$%s short_notional=$%s long_notional=$%s",
            regime, allocation["shorts"] * 100, allocation["longs"] * 100,
            f"{account_value:,.0f}", f"{short_notional:,.0f}", f"{long_notional:,.0f}",
        )
        logger.info(
            "Risk: %.1f%% per trade, max position %.1f%% of equity ($%s), max %d shares/order",
            risk_per_trade_pct * 100, max_position_pct_short * 100,
            f"{account_value * max_position_pct_short:,.0f}", absolute_max_shares,
        )

        if not _check_daily_loss_limit(account_value, daily_loss, daily_loss_limit_pct):
            logger.warning("Trading halted (daily loss limit)")
            return

        try:
            from agents.risk_monitor import is_kill_switch_active
            if is_kill_switch_active():
                logger.warning("Kill switch is active. No executions.")
                return
        except ImportError:
            pass

        if not check_portfolio_hedging(short_notional, long_notional):
            logger.warning("Portfolio hedging gate blocked all new entries")
            return

        sector_exposure, total_notional = _portfolio_sector_exposure(ib)
        max_sector_pct = get_max_sector_concentration_pct(TRADING_DIR)

        short_candidates = rank_short_candidates(_load_short_candidates())
        long_candidates = rank_long_candidates(_load_long_candidates())
        if not short_candidates and not long_candidates:
            logger.info("No short or long candidates")
            return

        executions: List[Dict[str, Any]] = []
        source_script = "execute_dual_mode.py"

        for candidate in short_candidates[:5]:
            symbol = candidate["symbol"]
            estimated_notional = candidate["price"] * (account_value * max_position_pct_short / candidate["price"])
            gates_ok, failed_gates = check_all_gates(
                signal_type="SHORT",
                symbol=symbol,
                notional=estimated_notional,
                daily_loss=daily_loss,
                account_equity=account_value,
                daily_loss_limit_pct=daily_loss_limit_pct,
                sector_exposure=sector_exposure,
                total_notional=total_notional,
                max_sector_pct=max_sector_pct,
                minutes_before_close=60,
                max_notional_pct_of_equity=0.5,
                ib=ib,
            )
            if not gates_ok:
                logger.info("Skipping short %s: gates failed: %s", symbol, ", ".join(failed_gates))
                continue
            ok, added, rec = await _execute_short(
                ib, candidate, current_shorts, max_short_positions,
                max_short_notional, short_notional, account_value,
                risk_per_trade_pct=risk_per_trade_pct,
                max_position_pct=max_position_pct_short,
                absolute_max_shares=absolute_max_shares,
                regime=regime,
            )
            if ok and rec is not None:
                current_shorts.add(symbol)
                short_notional += added
                sector = SECTOR_MAP.get(symbol, "Unknown")
                sector_exposure[sector] = sector_exposure.get(sector, 0.0) - added
                total_notional += added
                executions.append(rec)
            await asyncio.sleep(1)

        for candidate in long_candidates[:5]:
            if len(current_longs) >= max_long_positions:
                logger.info("Max long positions reached (%d/%d). Stopping longs.", len(current_longs), max_long_positions)
                break
            symbol = candidate["symbol"]
            estimated_notional = min(
                account_value * max_position_pct_long,
                candidate["price"] * absolute_max_shares,
            )
            if account_value > 0 and (total_notional + estimated_notional) / account_value > max_total_notional_pct:
                logger.info("Skipping long %s: total notional would exceed %.0f%% cap",
                            symbol, max_total_notional_pct * 100)
                continue
            if not check_sector_concentration(
                sector_exposure, total_notional, symbol, "LONG", estimated_notional, max_sector_pct
            ):
                logger.info("Skipping long %s: sector concentration gate", symbol)
                continue
            ok, added, rec = await _execute_long(
                ib, candidate, current_longs, max_long_notional, long_notional,
                account_value=account_value,
                risk_per_trade_pct=risk_per_trade_pct,
                max_position_pct=max_position_pct_long,
                absolute_max_shares=absolute_max_shares,
                regime=regime,
            )
            if ok and rec is not None:
                current_longs.add(symbol)
                long_notional += added
                sector = SECTOR_MAP.get(symbol, "Unknown")
                sector_exposure[sector] = sector_exposure.get(sector, 0.0) + added
                total_notional += added
                executions.append(rec)
            await asyncio.sleep(1)

        if executions:
            try:
                from trade_log_db import insert_trade
                for e in executions:
                    insert_trade(e)
            except ImportError:
                pass
            EXECUTION_LOG.parent.mkdir(parents=True, exist_ok=True)
            with open(EXECUTION_LOG, "a") as f:
                for e in executions:
                    f.write(json.dumps(e) + "\n")
            logger.info("Logged %d executions to %s", len(executions), EXECUTION_LOG)
    finally:
        ib.disconnect()


if __name__ == "__main__":
    asyncio.run(run())
