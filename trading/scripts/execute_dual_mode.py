#!/usr/bin/env python3
"""
Unified executor for both SHORT and LONG signals.

Loads shorts from watchlist_multimode.json and longs from watchlist_longs.json,
detects market regime, enforces allocation caps, runs mixed-portfolio risk gates
(sector concentration, hedging check), then executes shorts then longs.
Uses clientId=103. Logs to shared executions.json (source_script + type per record).

All broker interaction is routed through OrderRouter — no direct
ib_insync order calls outside this orchestration layer.
"""

import asyncio
import json
import logging
from pathlib import Path

from atr_stops import (
    calculate_position_size,
    compute_stop_tp,
    compute_trailing_amount,
    fetch_atr,
)
from base_executor import BaseExecutor
from broker_data_helpers import atr_from_ib
from candidate_ranking import (
    long_conviction,
    rank_long_candidates,
    rank_short_candidates,
    short_conviction,
)
from enriched_record import build_enriched_record
from execution_policy import ExecutionPolicy, build_intent
from order_router import OrderRouter, SubmitResult
from position_filter import load_current_short_symbols
from pre_trade_guard import PreTradeViolation, assert_no_flip
from regime_detector import calculate_portfolio_allocation
from risk_config import (
    get_allow_outside_rth_entry,
    get_max_long_positions,
    get_max_position_pct_of_equity,
    get_max_short_positions,
    get_max_total_notional_pct,
    get_outside_rth_stop,
    get_outside_rth_take_profit,
)
from sector_gates import (
    SECTOR_MAP,
    check_sector_concentration,
    portfolio_sector_exposure as _portfolio_sector_exposure,
)

from paths import TRADING_DIR

logger = logging.getLogger(__name__)

WATCHLIST_MULTIMODE_FILE = TRADING_DIR / "watchlist_multimode.json"
WATCHLIST_LONGS_FILE    = TRADING_DIR / "watchlist_longs.json"
WATCHLIST_SHORTS_FILE   = TRADING_DIR / "watchlist_shorts.json"


# ---------------------------------------------------------------------------
# Candidate loaders
# ---------------------------------------------------------------------------


def _load_short_candidates() -> list[dict]:
    """
    Build short list from two sources (deduplicated by symbol):
      1. watchlist_multimode.json  — existing premium/opportunistic shorts
      2. watchlist_shorts.json     — new bearish-regime directional shorts
                                     (from nx_screener_shorts.py)
    Candidates from watchlist_shorts.json are preferred when a symbol
    appears in both sources (higher conviction selection criteria).
    """
    seen: set[str] = set()
    out: list[dict] = []

    # ── Source 1: watchlist_multimode.json ────────────────────────────────────
    if WATCHLIST_MULTIMODE_FILE.exists():
        try:
            data = json.loads(WATCHLIST_MULTIMODE_FILE.read_text())
            modes = data.get("modes", {}) or {}
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
                    rs_pct_raw = item.get("rs_pct")
                    rs_pct = float(rs_pct_raw) if rs_pct_raw is not None else 0.0
                    # Normalize rs_pct to a 0-1 hybrid score so multimode and
                    # bearish-screener candidates rank on a comparable scale.
                    # rs_pct is typically -0.01 to -0.10 for short candidates;
                    # cap at -0.10 → normalized score 0.35 (same weight scheme
                    # as nx_screener_shorts._score_short RS component × 0.35).
                    normalized_score = round(min(1.0, max(0.0, -rs_pct / 0.10)) * 0.35, 4)
                    seen.add(symbol)
                    out.append({
                        "symbol": symbol,
                        "price": price_f,
                        "score": normalized_score,
                        "momentum": float(item.get("recent_return", -0.01)) if item.get("recent_return") is not None else -0.01,
                        "_source": "multimode",
                    })
        except (OSError, ValueError):
            pass

    # ── Source 2: watchlist_shorts.json (bearish screener output) ─────────────
    if WATCHLIST_SHORTS_FILE.exists():
        try:
            data = json.loads(WATCHLIST_SHORTS_FILE.read_text())
            for item in data.get("short_candidates", []):
                if not isinstance(item, dict):
                    continue
                symbol = item.get("symbol")
                if not isinstance(symbol, str) or not symbol.strip():
                    continue
                symbol = symbol.strip().upper()
                try:
                    price_f = float(item.get("price") or 0)
                except (TypeError, ValueError):
                    continue
                if price_f <= 0:
                    continue
                entry = {
                    "symbol": symbol,
                    "price": price_f,
                    "score": float(item.get("score", 0)),
                    "momentum": float(item.get("rs_pct", -0.01)),
                    "_source": "bearish_screener",
                }
                if symbol in seen:
                    # Replace the multimode entry with the more specific bearish one
                    out = [e for e in out if e["symbol"] != symbol]
                    out.append(entry)
                else:
                    seen.add(symbol)
                    out.append(entry)
        except (OSError, ValueError):
            pass

    logger.debug("Loaded %d short candidates (%d unique)", len(out), len(seen))
    return out


def _load_long_candidates() -> list[dict]:
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
    out: list[dict] = []
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


# ---------------------------------------------------------------------------
# Portfolio helpers
# ---------------------------------------------------------------------------


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


def _portfolio_notionals(ib) -> tuple[float, float]:
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


# ---------------------------------------------------------------------------
# Per-candidate execution (short / long)
# ---------------------------------------------------------------------------


async def _execute_short(
    executor: "DualModeExecutor",
    candidate: dict,
    current_shorts: set[str],
    max_shorts: int,
    max_short_notional: float,
    current_short_notional: float,
    max_position_pct: float,
    current_longs: set[str] | None = None,
) -> tuple[bool, float, dict | None]:
    """Execute one short via OrderRouter. Returns (success, added_notional, enriched_record_or_None)."""
    assert executor.router is not None
    symbol = candidate["symbol"]
    price = candidate["price"]

    if symbol in current_shorts:
        executor.log.info("Skipping short %s: already short", symbol)
        return False, 0.0, None

    if current_longs and symbol in current_longs:
        executor.log.warning(
            "Skipping short %s: currently held LONG — will not flip position.", symbol,
        )
        return False, 0.0, None

    if len(current_shorts) >= max_shorts:
        executor.log.info("Skipping short %s: max short positions (%d)", symbol, max_shorts)
        return False, 0.0, None

    try:
        assert_no_flip(executor.ib, symbol, "SHORT")
    except PreTradeViolation as e:
        executor.log.error("Short blocked by pre_trade_guard: %s", e)
        return False, 0.0, None

    try:
        atr = fetch_atr(symbol)
        if atr is None:
            atr = atr_from_ib(symbol, executor.ib)

        conv = short_conviction(candidate)
        qty = calculate_position_size(
            executor.effective_equity, price, atr=atr,
            risk_pct=executor.risk_per_trade_pct,
            max_position_pct=max_position_pct,
            absolute_max_shares=executor.absolute_max_shares,
            conviction=conv,
            cap_equity=executor.net_liq,
        )
        notional = price * qty
        if current_short_notional + notional > max_short_notional:
            executor.log.warning(
                "Skipping short %s: allocation cap (%.0f + %.0f > %.0f)",
                symbol, current_short_notional, notional, max_short_notional,
            )
            return False, 0.0, None

        outside_rth = get_allow_outside_rth_entry(TRADING_DIR)
        entry_intent = build_intent(
            symbol=symbol, side="SELL", quantity=qty,
            policy=ExecutionPolicy.PASSIVE_ENTRY if outside_rth else ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script=executor.script_name,
            limit_price=price, outside_rth=outside_rth,
            metadata={
                "regime": executor.regime, "conviction": conv,
                "atr": atr, "signal_price": price,
            },
        )

        result = await executor.router.submit(entry_intent, bid=price)

        if not result.success or (not result.is_filled and not result.is_partial):
            executor.log.warning(
                "Short order not filled for %s: status=%s error=%s",
                symbol,
                result.status.value if result.status else "None",
                result.error or "",
            )
            return False, 0.0, None

        filled_qty = result.filled_qty
        entry_price = result.avg_fill_price
        fill_commission = result.total_commission

        if filled_qty != qty:
            executor.log.warning("Partial fill on short %s: requested %d, filled %d", symbol, qty, filled_qty)

        fill_slippage = abs(entry_price - price) if entry_price > 0 else 0.0
        stop_price, profit_price = compute_stop_tp(entry_price, "SELL", atr=atr)
        trail_amt = compute_trailing_amount(atr=atr, entry_price=entry_price)

        trailing_intent = build_intent(
            symbol=symbol, side="BUY", quantity=filled_qty,
            policy=ExecutionPolicy.TRAILING_STOP, source_script=executor.script_name,
            trail_amount=trail_amt, outside_rth=get_outside_rth_stop(TRADING_DIR),
        )
        tp_intent = build_intent(
            symbol=symbol, side="BUY", quantity=filled_qty,
            policy=ExecutionPolicy.PASSIVE_ENTRY, source_script=executor.script_name,
            limit_price=profit_price, outside_rth=get_outside_rth_take_profit(TRADING_DIR),
        )

        protective_results = await executor.router.submit_protective_orders(
            parent_result=result, follow_ups=[trailing_intent, tp_intent],
        )
        for pr in protective_results:
            if not pr.success:
                executor.log.error("Protective order failed for %s: %s", symbol, pr.error)

        rec = build_enriched_record(
            symbol=symbol, side="SHORT", action="SELL",
            source_script=executor.script_name,
            status="Filled" if result.is_filled else "PartiallyFilled",
            order_id=result.broker_order_id or 0,
            quantity=filled_qty,
            entry_price=entry_price, stop_price=stop_price, profit_price=profit_price,
            regime_at_entry=executor.regime, conviction_score=conv, atr_at_entry=atr,
            rs_pct=candidate.get("score") or candidate.get("rs_pct"),
            composite_score=candidate.get("composite_score"),
            structure_quality=candidate.get("structure_quality"),
            rvol_atr=candidate.get("rvol_atr"),
            signal_price=price, slippage=fill_slippage,
            extra={"commission": fill_commission},
        )
        executor.log.info(
            "Short placed: %s qty=%d entry=%.2f trail=%.2f tp=%.2f slip=%.4f",
            symbol, filled_qty, entry_price, trail_amt, profit_price, fill_slippage,
        )
        executor.notify_fill("SHORT", symbol, entry_price, filled_qty, trail=trail_amt, tp=profit_price)
        return True, abs(entry_price * filled_qty), rec
    except Exception as e:
        executor.log.error("Short execution error %s: %s", symbol, e)
        return False, 0.0, None


async def _execute_long(
    executor: "DualModeExecutor",
    candidate: dict,
    current_longs: set[str],
    max_long_notional: float,
    current_long_notional: float,
    max_position_pct: float,
    current_shorts: set[str] | None = None,
) -> tuple[bool, float, dict | None]:
    """Execute one long via OrderRouter. Returns (success, added_notional, enriched_record_or_None)."""
    assert executor.router is not None
    symbol = candidate["symbol"]
    price = candidate["price"]

    if symbol in current_longs:
        executor.log.info("Skipping long %s: already long", symbol)
        return False, 0.0, None

    if current_shorts and symbol in current_shorts:
        executor.log.warning(
            "Skipping long %s: currently held SHORT — will not flip position.", symbol,
        )
        return False, 0.0, None

    try:
        assert_no_flip(executor.ib, symbol, "LONG")
    except PreTradeViolation as e:
        executor.log.error("Long blocked by pre_trade_guard: %s", e)
        return False, 0.0, None

    try:
        atr = fetch_atr(symbol)
        if atr is None:
            atr = atr_from_ib(symbol, executor.ib)

        conv = long_conviction(candidate)
        qty = calculate_position_size(
            executor.effective_equity, price, atr=atr,
            risk_pct=executor.risk_per_trade_pct,
            max_position_pct=max_position_pct,
            absolute_max_shares=executor.absolute_max_shares,
            conviction=conv,
            cap_equity=executor.net_liq,
        )
        notional = price * qty
        if current_long_notional + notional > max_long_notional:
            executor.log.warning(
                "Skipping long %s: allocation cap (%.0f + %.0f > %.0f)",
                symbol, current_long_notional, notional, max_long_notional,
            )
            return False, 0.0, None

        outside_rth = get_allow_outside_rth_entry(TRADING_DIR)
        entry_intent = build_intent(
            symbol=symbol, side="BUY", quantity=qty,
            policy=ExecutionPolicy.PASSIVE_ENTRY if outside_rth else ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script=executor.script_name,
            limit_price=price, outside_rth=outside_rth,
            metadata={
                "regime": executor.regime, "conviction": conv,
                "atr": atr, "signal_price": price,
            },
        )

        result = await executor.router.submit(entry_intent, ask=price)

        if not result.success or (not result.is_filled and not result.is_partial):
            executor.log.warning(
                "Long order not filled for %s: status=%s error=%s",
                symbol,
                result.status.value if result.status else "None",
                result.error or "",
            )
            return False, 0.0, None

        filled_qty = result.filled_qty
        entry_price = result.avg_fill_price
        fill_commission = result.total_commission

        if filled_qty != qty:
            executor.log.warning("Partial fill on long %s: requested %d, filled %d", symbol, qty, filled_qty)

        fill_slippage = abs(entry_price - price) if entry_price > 0 else 0.0
        stop_price, tp_price = compute_stop_tp(entry_price, "BUY", atr=atr)
        trail_amt = compute_trailing_amount(atr=atr, entry_price=entry_price)

        trailing_intent = build_intent(
            symbol=symbol, side="SELL", quantity=filled_qty,
            policy=ExecutionPolicy.TRAILING_STOP, source_script=executor.script_name,
            trail_amount=trail_amt, outside_rth=get_outside_rth_stop(TRADING_DIR),
        )
        tp_intent = build_intent(
            symbol=symbol, side="SELL", quantity=filled_qty,
            policy=ExecutionPolicy.PASSIVE_ENTRY, source_script=executor.script_name,
            limit_price=tp_price, outside_rth=get_outside_rth_take_profit(TRADING_DIR),
        )

        protective_results = await executor.router.submit_protective_orders(
            parent_result=result, follow_ups=[trailing_intent, tp_intent],
        )
        for pr in protective_results:
            if not pr.success:
                executor.log.error("Protective order failed for %s: %s", symbol, pr.error)

        rec = build_enriched_record(
            symbol=symbol, side="LONG", action="BUY",
            source_script=executor.script_name,
            status="Filled" if result.is_filled else "PartiallyFilled",
            order_id=result.broker_order_id or 0,
            quantity=filled_qty,
            entry_price=entry_price, stop_price=stop_price, profit_price=tp_price,
            regime_at_entry=executor.regime, conviction_score=conv, atr_at_entry=atr,
            rs_pct=candidate.get("rs_pct") or candidate.get("score"),
            composite_score=candidate.get("composite_score"),
            structure_quality=candidate.get("structure_quality"),
            rvol_atr=candidate.get("rvol_atr"),
            signal_price=price, slippage=fill_slippage,
            extra={"commission": fill_commission},
        )
        executor.log.info(
            "Long placed: %s qty=%d entry=%.2f trail=%.2f tp=%.2f slip=%.4f",
            symbol, filled_qty, entry_price, trail_amt, tp_price, fill_slippage,
        )
        executor.notify_fill("LONG", symbol, entry_price, filled_qty, trail=trail_amt, tp=tp_price)
        return True, entry_price * filled_qty, rec
    except Exception as e:
        executor.log.error("Long execution error %s: %s", symbol, e)
        return False, 0.0, None


# ---------------------------------------------------------------------------
# DualModeExecutor
# ---------------------------------------------------------------------------


class DualModeExecutor(BaseExecutor):
    script_name = "execute_dual_mode.py"
    log_file_stem = "execute_dual_mode"
    state_store_name = "order_state_dual_mode.jsonl"
    client_id = 103
    job_lock_name = "execute_dual_mode"
    position_side = "short"

    async def execute(self) -> None:
        allocation = calculate_portfolio_allocation(self.regime)
        max_short_notional = self.net_liq * allocation["shorts"]
        max_long_notional = self.net_liq * allocation["longs"]

        short_notional, long_notional = _portfolio_notionals(self.ib)
        current_shorts = load_current_short_symbols(TRADING_DIR, self.ib)
        current_longs = self.current_long_symbols()
        max_short_positions = get_max_short_positions(TRADING_DIR)
        max_position_pct_short = self.max_position_pct
        max_position_pct_long = get_max_position_pct_of_equity(TRADING_DIR, side="long")
        max_long_positions = get_max_long_positions(TRADING_DIR)
        max_total_notional_pct = get_max_total_notional_pct(TRADING_DIR)

        self.log.info(
            "Regime=%s allocation shorts=%.0f%% longs=%.0f%% net_liq=$%s effective=$%s "
            "short_notional=$%s long_notional=$%s",
            self.regime, allocation["shorts"] * 100, allocation["longs"] * 100,
            f"{self.net_liq:,.0f}", f"{self.effective_equity:,.0f}",
            f"{short_notional:,.0f}", f"{long_notional:,.0f}",
        )
        self.log.info(
            "Risk: %.1f%% per trade, max position %.1f%% of effective ($%s), max %d shares/order",
            self.risk_per_trade_pct * 100, max_position_pct_short * 100,
            f"{self.effective_equity * max_position_pct_short:,.0f}",
            self.absolute_max_shares,
        )

        if not check_portfolio_hedging(short_notional, long_notional):
            self.log.warning("Portfolio hedging gate blocked all new entries")
            return

        short_candidates = rank_short_candidates(_load_short_candidates())
        long_candidates = rank_long_candidates(_load_long_candidates())
        if not short_candidates and not long_candidates:
            self.log.info("No short or long candidates")
            return

        # --- Shorts loop ---
        for candidate in short_candidates[:10]:
            symbol = candidate["symbol"]
            estimated_notional = self.net_liq * max_position_pct_short
            gates_ok, failed_gates = self.check_gates("SHORT", symbol, estimated_notional)
            if not gates_ok:
                self.log.info("Skipping short %s: gates failed: %s", symbol, ", ".join(failed_gates))
                continue
            ok, added, rec = await _execute_short(
                self, candidate, current_shorts, max_short_positions,
                max_short_notional, short_notional,
                max_position_pct=max_position_pct_short,
                current_longs=current_longs,
            )
            if ok and rec is not None:
                current_shorts.add(symbol)
                short_notional += added
                sector = SECTOR_MAP.get(symbol, "Unknown")
                self.sector_exposure[sector] = self.sector_exposure.get(sector, 0.0) - added
                self.total_notional += added
                self.executions.append(rec)
            await asyncio.sleep(1)

        # --- Longs loop ---
        for candidate in long_candidates[:10]:
            if len(current_longs) >= max_long_positions:
                self.log.info(
                    "Max long positions reached (%d/%d). Stopping longs.",
                    len(current_longs), max_long_positions,
                )
                break
            symbol = candidate["symbol"]
            estimated_notional = min(
                self.net_liq * max_position_pct_long,
                candidate["price"] * self.absolute_max_shares,
            )
            if self.net_liq > 0 and (self.total_notional + estimated_notional) / self.net_liq > max_total_notional_pct:
                self.log.info(
                    "Skipping long %s: total notional would exceed %.0f%% cap",
                    symbol, max_total_notional_pct * 100,
                )
                continue
            if not check_sector_concentration(
                self.sector_exposure, self.total_notional, symbol, "LONG",
                estimated_notional, self.max_sector_pct,
            ):
                self.log.info("Skipping long %s: sector concentration gate", symbol)
                continue
            gates_ok, failed_gates = self.check_gates("LONG", symbol, estimated_notional)
            if not gates_ok:
                self.log.info("Skipping long %s: gates failed: %s", symbol, ", ".join(failed_gates))
                continue
            ok, added, rec = await _execute_long(
                self, candidate, current_longs,
                max_long_notional, long_notional,
                max_position_pct=max_position_pct_long,
                current_shorts=current_shorts,
            )
            if ok and rec is not None:
                current_longs.add(symbol)
                long_notional += added
                sector = SECTOR_MAP.get(symbol, "Unknown")
                self.sector_exposure[sector] = self.sector_exposure.get(sector, 0.0) + added
                self.total_notional += added
                self.executions.append(rec)
            await asyncio.sleep(1)


async def run() -> None:
    await DualModeExecutor().run()


if __name__ == "__main__":
    asyncio.run(run())
