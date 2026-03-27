#!/usr/bin/env python3
"""
Pairs Executor — Simultaneous long/short execution with bracket orders.

Loads watchlist_pairs.json, connects to IBKR (clientId=110), places entry
orders on long leg (BUY) and short leg (SELL) with 2 ATR stop / 3 ATR TP each.
Tracks open pairs in pairs_positions.json. Exit logic: close both legs when
spread z-score reverts to < 0.5 or after 15 days.

All broker interaction is routed through OrderRouter — no direct
ib_insync order calls outside this orchestration layer.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atomic_io import atomic_write_json

from atr_stops import compute_stop_tp, fetch_atr
from base_executor import BaseExecutor
from broker_data_helpers import atr_from_ib
from enriched_record import build_enriched_record
from execution_policy import ExecutionPolicy, build_intent
from order_router import OrderRouter
from risk_config import (
    get_outside_rth_stop,
    get_outside_rth_take_profit,
    get_pairs_params,
)
from sector_gates import SECTOR_MAP

PAIRS_FILL_TIMEOUT_SECONDS = 45.0
MIN_LEG_PRICE = 5.0

from paths import TRADING_DIR

WATCHLIST_PAIRS_FILE = TRADING_DIR / "watchlist_pairs.json"
PAIRS_POSITIONS_FILE = TRADING_DIR / "logs" / "pairs_positions.json"

_pairs_cfg = get_pairs_params(Path(__file__).resolve().parent.parent)
MAX_PAIRS_PER_RUN: int = _pairs_cfg["max_pairs_per_run"]
NOTIONAL_PER_LEG = 50_000.0          # hard floor in dollars — not configurable by design
NOTIONAL_PCT_PER_LEG: float = _pairs_cfg["notional_pct_per_leg"]
PAIRS_STOP_ATR_MULT: float = _pairs_cfg["stop_atr_mult"]
PAIRS_TP_ATR_MULT: float = _pairs_cfg["tp_atr_mult"]
PAIRS_MAX_DAYS: int = _pairs_cfg["max_days"]
PAIRS_EXIT_ZSCORE: float = _pairs_cfg["exit_zscore"]


# ---------------------------------------------------------------------------
# Watchlist & position helpers
# ---------------------------------------------------------------------------


def _load_watchlist_pairs() -> list[dict]:
    if not WATCHLIST_PAIRS_FILE.exists():
        return []
    try:
        data = json.loads(WATCHLIST_PAIRS_FILE.read_text(encoding="utf-8"))
        pairs = data.get("pairs", [])
        if not isinstance(pairs, list):
            return []
        return [p for p in pairs if isinstance(p, dict) and p.get("long_sym") and p.get("short_sym")]
    except (OSError, ValueError):
        return []


def _load_pairs_positions() -> list[dict]:
    if not PAIRS_POSITIONS_FILE.exists():
        return []
    try:
        data = json.loads(PAIRS_POSITIONS_FILE.read_text(encoding="utf-8"))
        positions = data.get("positions", [])
        if not isinstance(positions, list):
            return []
        return positions
    except (OSError, ValueError):
        return []


def _save_pairs_positions(positions: list[dict]) -> None:
    data = {"positions": positions, "updated_at": datetime.now().isoformat()}
    atomic_write_json(PAIRS_POSITIONS_FILE, data)


def _current_position_symbols(ib) -> tuple[set[str], set[str]]:
    """Return (long_symbols, short_symbols) from the pairs position book."""
    longs: set[str] = set()
    shorts: set[str] = set()
    try:
        open_pairs = _load_pairs_positions()
        for pair in open_pairs:
            long_sym = (pair.get("long_sym") or "").strip().upper()
            short_sym = (pair.get("short_sym") or "").strip().upper()
            if long_sym:
                longs.add(long_sym)
            if short_sym:
                shorts.add(short_sym)
    except Exception as exc:
        logger.warning("Failed to read pairs positions — treating as empty: %s", exc)
    return longs, shorts


def _notional_per_leg(account_equity: float) -> float:
    """Equal dollar notional per leg: min($50K, notional_pct_per_leg × equity). Currently 4% from risk.json."""
    pct_amount = account_equity * NOTIONAL_PCT_PER_LEG
    return min(NOTIONAL_PER_LEG, pct_amount)


def _fetch_live_quote(symbol: str) -> tuple[float, float, float]:
    """Fetch live bid/ask/last for a symbol via yfinance.

    Returns (bid, ask, last). Any value may be 0.0 on failure.
    """
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        info = t.info or {}
        bid = float(info.get("bid", 0) or 0)
        ask = float(info.get("ask", 0) or 0)
        last = float(info.get("regularMarketPrice", 0) or info.get("currentPrice", 0) or 0)
        return bid, ask, last
    except Exception as exc:
        logger.warning("Live quote failed for %s: %s — using watchlist price", symbol, exc)
        return 0.0, 0.0, 0.0


# ---------------------------------------------------------------------------
# PairsExecutor
# ---------------------------------------------------------------------------


class PairsExecutor(BaseExecutor):
    script_name = "execute_pairs.py"
    log_file_stem = "execute_pairs"
    state_store_name = "order_state_pairs.jsonl"
    client_id = 110
    job_lock_name = "execute_pairs"
    position_side = "long"
    use_drawdown_breaker = False
    connect_retries = 3
    connect_timeout = 15

    def _create_router(self) -> OrderRouter:
        """Override: pairs need a longer fill timeout for limit orders."""
        return OrderRouter(
            self.ib,
            state_store_path=self.state_store_path,
            fill_timeout=PAIRS_FILL_TIMEOUT_SECONDS,
        )

    def _load_account_state(self) -> None:
        """Override: pairs applies allocation only to effective equity, not net_liq."""
        from live_allocation import get_effective_equity as _apply_alloc_pct
        from risk_config import get_net_liquidation_and_effective_equity
        from sector_gates import portfolio_sector_exposure

        raw_nlv, raw_eq = get_net_liquidation_and_effective_equity(self.ib, TRADING_DIR)
        self.net_liq = raw_nlv
        self.effective_equity = _apply_alloc_pct(raw_eq)

        self.sector_exposure, self.total_notional = portfolio_sector_exposure(self.ib)

        self.daily_loss = 0.0
        if self.loss_tracker_path.exists():
            try:
                import json as _json
                data = _json.loads(self.loss_tracker_path.read_text())
                if data.get("date") == datetime.now().date().isoformat():
                    self.daily_loss = float(data.get("loss", 0) or 0)
            except (OSError, ValueError, TypeError):
                pass

        self.log.info(
            "Net liq $%s | Effective $%s | Daily loss $%.2f",
            f"{self.net_liq:,.0f}", f"{self.effective_equity:,.0f}", self.daily_loss,
        )

    async def execute(self) -> None:
        assert self.router is not None

        notional_leg = _notional_per_leg(self.effective_equity)
        long_symbols, short_symbols = _current_position_symbols(self.ib)

        pairs = _load_watchlist_pairs()
        if not pairs:
            self.log.info("No pairs in watchlist")
            return

        pairs = sorted(pairs, key=lambda p: float(p.get("spread_zscore") or 0), reverse=True)

        await self._check_exits()

        open_positions = _load_pairs_positions()

        for pair in pairs[:MAX_PAIRS_PER_RUN]:
            if len(self.executions) >= MAX_PAIRS_PER_RUN * 2:
                break
            ok, recs = await self._execute_pair(
                pair, long_symbols, short_symbols, notional_leg,
            )
            if ok and recs:
                self.executions.extend(recs)
                long_sym = (pair.get("long_sym") or "").strip().upper()
                short_sym = (pair.get("short_sym") or "").strip().upper()
                long_symbols.add(long_sym)
                short_symbols.add(short_sym)
                open_positions.append({
                    "long_sym": long_sym,
                    "short_sym": short_sym,
                    "sector": pair.get("sector"),
                    "entry_date": datetime.now().date().isoformat(),
                    "spread_zscore_at_entry": pair.get("spread_zscore"),
                })
                self.total_notional += notional_leg * 2
                sector = pair.get("sector", "Unknown")
                self.sector_exposure[sector] = self.sector_exposure.get(sector, 0.0) + notional_leg
            await asyncio.sleep(1)

        if open_positions:
            _save_pairs_positions(open_positions)

    # ------------------------------------------------------------------
    # Exit monitoring (placeholder)
    # ------------------------------------------------------------------

    async def _check_exits(self) -> list[dict]:
        """Close open pairs when spread z-score reverts or max holding period is reached.

        Exit triggers:
          - Spread z-score < PAIRS_EXIT_ZSCORE (mean reversion complete)
          - Position held > PAIRS_MAX_DAYS (time-based stop)

        Returns list of exit records for logging.
        """
        assert self.router is not None
        positions = _load_pairs_positions()
        if not positions:
            return []

        exits: list[dict] = []
        remaining: list[dict] = []
        today = datetime.now().date()

        for pair in positions:
            long_sym = (pair.get("long_sym") or "").strip().upper()
            short_sym = (pair.get("short_sym") or "").strip().upper()
            entry_date_str = pair.get("entry_date")
            entry_zscore = float(pair.get("spread_zscore_at_entry") or 0)

            if not long_sym or not short_sym:
                remaining.append(pair)
                continue

            # Time-based exit: held longer than max days
            days_held = 0
            if entry_date_str:
                try:
                    from datetime import date as _date
                    entry_d = _date.fromisoformat(entry_date_str)
                    days_held = (today - entry_d).days
                except (ValueError, TypeError):
                    pass

            should_exit = False
            exit_reason = ""

            if days_held >= PAIRS_MAX_DAYS:
                should_exit = True
                exit_reason = f"max_holding_period ({days_held}d >= {PAIRS_MAX_DAYS}d)"

            # Z-score reversion check via current spread
            if not should_exit:
                try:
                    _, _, long_last = _fetch_live_quote(long_sym)
                    _, _, short_last = _fetch_live_quote(short_sym)
                    if long_last > 0 and short_last > 0 and entry_zscore != 0:
                        current_ratio = long_last / short_last
                        entry_long_price = float(pair.get("long_entry_price") or 0)
                        entry_short_price = float(pair.get("short_entry_price") or 0)
                        if entry_long_price > 0 and entry_short_price > 0:
                            entry_ratio = entry_long_price / entry_short_price
                            ratio_change = abs(current_ratio - entry_ratio) / entry_ratio
                            estimated_zscore = entry_zscore * (1 - ratio_change * 5)
                            if estimated_zscore < PAIRS_EXIT_ZSCORE:
                                should_exit = True
                                exit_reason = f"spread_reverted (est z={estimated_zscore:.2f} < {PAIRS_EXIT_ZSCORE})"
                except Exception as e:
                    self.log.debug("Z-score check failed for %s/%s: %s", long_sym, short_sym, e)

            if not should_exit:
                remaining.append(pair)
                continue

            self.log.info("Exiting pair %s/%s: %s", long_sym, short_sym, exit_reason)

            # Close both legs via URGENT_EXIT
            try:
                # Find current position sizes from IB
                long_qty = short_qty = 0
                for pos in self.ib.positions():
                    sym = getattr(pos.contract, "symbol", "")
                    if getattr(pos.contract, "secType", "") != "STK":
                        continue
                    if sym == long_sym and pos.position > 0:
                        long_qty = int(pos.position)
                    elif sym == short_sym and pos.position < 0:
                        short_qty = abs(int(pos.position))

                if long_qty > 0:
                    sell_intent = build_intent(
                        symbol=long_sym, side="SELL", quantity=long_qty,
                        policy=ExecutionPolicy.URGENT_EXIT,
                        source_script=self.script_name,
                        metadata={"reason": exit_reason, "strategy": "pairs_exit"},
                    )
                    await self.router.submit(sell_intent)
                    self.log.info("Closed long leg %s qty=%d", long_sym, long_qty)

                if short_qty > 0:
                    cover_intent = build_intent(
                        symbol=short_sym, side="BUY", quantity=short_qty,
                        policy=ExecutionPolicy.URGENT_EXIT,
                        source_script=self.script_name,
                        metadata={"reason": exit_reason, "strategy": "pairs_exit"},
                    )
                    await self.router.submit(cover_intent)
                    self.log.info("Closed short leg %s qty=%d", short_sym, short_qty)

                exits.append({
                    "long_sym": long_sym, "short_sym": short_sym,
                    "exit_reason": exit_reason, "days_held": days_held,
                })
            except Exception as e:
                self.log.error("Pairs exit failed for %s/%s: %s", long_sym, short_sym, e)
                remaining.append(pair)

        if len(remaining) != len(positions):
            _save_pairs_positions(remaining)
            self.log.info("Pairs exits: %d closed, %d remaining", len(exits), len(remaining))

        return exits

    # ------------------------------------------------------------------
    # Execute one pair
    # ------------------------------------------------------------------

    async def _execute_pair(
        self,
        pair: dict,
        long_symbols: set[str],
        short_symbols: set[str],
        notional_per_leg: float,
    ) -> tuple[bool, list[dict]]:
        """Execute one pair: BUY long leg, SELL short leg via OrderRouter.

        If one leg fills but the other doesn't, the filled leg is immediately
        flattened via URGENT_EXIT to avoid a naked position.
        """
        assert self.router is not None
        long_sym = (pair.get("long_sym") or "").strip().upper()
        short_sym = (pair.get("short_sym") or "").strip().upper()
        sector = pair.get("sector", "Unknown")

        if not long_sym or not short_sym:
            return False, []

        if long_sym in long_symbols or short_sym in short_symbols:
            self.log.info("Skipping pair %s/%s: leg already in position", long_sym, short_sym)
            return False, []

        # --- Fetch live quotes; fall back to watchlist prices ---
        long_bid, long_ask, long_last = _fetch_live_quote(long_sym)
        short_bid, short_ask, short_last = _fetch_live_quote(short_sym)

        long_price = long_ask or long_last or float(pair.get("long_price") or 0)
        short_price = short_bid or short_last or float(pair.get("short_price") or 0)
        if long_price <= 0 or short_price <= 0:
            self.log.warning("Pair %s/%s: missing prices after live quote", long_sym, short_sym)
            return False, []

        if long_price < MIN_LEG_PRICE or short_price < MIN_LEG_PRICE:
            self.log.info(
                "Skipping pair %s/$%.2f / %s/$%.2f: leg below $%.0f min",
                long_sym, long_price, short_sym, short_price, MIN_LEG_PRICE,
            )
            return False, []

        long_qty = max(1, int(notional_per_leg / long_price))
        short_qty = max(1, int(notional_per_leg / short_price))

        # PM dynamic cap: tighten qty if margin budget is the binding constraint
        pm_long = self.get_pm_max_shares(long_sym, "BUY")
        pm_short = self.get_pm_max_shares(short_sym, "SELL")
        if pm_long is not None and pm_long >= 0:
            long_qty = min(long_qty, max(1, pm_long))
        if pm_short is not None and pm_short >= 0:
            short_qty = min(short_qty, max(1, pm_short))

        long_notional = long_qty * long_price
        short_notional = short_qty * short_price

        for sym, side, notional in [
            (long_sym, "LONG", long_notional),
            (short_sym, "SHORT", short_notional),
        ]:
            gates_ok, failed = self.check_gates(side, sym, notional)
            if not gates_ok:
                self.log.info(
                    "Skipping pair %s/%s: gates failed for %s: %s",
                    long_sym, short_sym, sym, ", ".join(failed),
                )
                return False, []

        try:
            long_atr = fetch_atr(long_sym)
            if long_atr is None:
                long_atr = atr_from_ib(long_sym, self.ib)
            short_atr = fetch_atr(short_sym)
            if short_atr is None:
                short_atr = atr_from_ib(short_sym, self.ib)

            # --- Flip guard for both legs ---
            from pre_trade_guard import PreTradeViolation, assert_no_flip
            try:
                assert_no_flip(self.ib, long_sym, "LONG")
                assert_no_flip(self.ib, short_sym, "SHORT")
            except PreTradeViolation as e:
                self.log.error("Pair blocked by flip guard: %s", e)
                return False, []

            # --- Entry: long leg (Adaptive algo works the spread) ---
            long_limit = long_ask if long_ask > 0 else long_price
            long_intent = build_intent(
                symbol=long_sym, side="BUY", quantity=long_qty,
                policy=ExecutionPolicy.SPREAD_AWARE_ENTRY,
                source_script=self.script_name,
                limit_price=long_limit,
                metadata={"strategy": "pairs_long", "pair_short": short_sym, "sector": sector},
            )
            long_result = await self.router.submit(
                long_intent, bid=long_bid or None, ask=long_ask or None,
            )

            long_filled = long_result.is_filled or long_result.is_partial
            if not long_filled:
                self.log.warning(
                    "Pair %s/%s: long leg not filled (status=%s) — aborting pair",
                    long_sym, short_sym,
                    long_result.status.value if long_result.status else "None",
                )
                return False, []

            # --- Entry: short leg (Adaptive algo works the spread) ---
            short_limit = short_bid if short_bid > 0 else short_price
            short_intent = build_intent(
                symbol=short_sym, side="SELL", quantity=short_qty,
                policy=ExecutionPolicy.SPREAD_AWARE_ENTRY,
                source_script=self.script_name,
                limit_price=short_limit,
                metadata={"strategy": "pairs_short", "pair_long": long_sym, "sector": sector},
            )
            short_result = await self.router.submit(
                short_intent, bid=short_bid or None, ask=short_ask or None,
            )

            short_filled = short_result.is_filled or short_result.is_partial
            if not short_filled:
                self.log.warning(
                    "Pair %s/%s: short leg not filled (status=%s) — flattening long leg",
                    long_sym, short_sym,
                    short_result.status.value if short_result.status else "None",
                )
                flatten_intent = build_intent(
                    symbol=long_sym, side="SELL", quantity=long_result.filled_qty,
                    policy=ExecutionPolicy.URGENT_EXIT,
                    source_script=self.script_name,
                    metadata={"reason": "pair_short_leg_failed", "pair_short": short_sym},
                )
                await self.router.submit(flatten_intent)
                return False, []

            long_entry = long_result.avg_fill_price
            short_entry = short_result.avg_fill_price
            long_fill_qty = long_result.filled_qty
            short_fill_qty = short_result.filled_qty

            # --- Protective orders for both legs ---
            long_stop, long_tp = compute_stop_tp(
                long_entry, "BUY", atr=long_atr,
                stop_mult=PAIRS_STOP_ATR_MULT, tp_mult=PAIRS_TP_ATR_MULT,
            )
            short_stop, short_tp = compute_stop_tp(
                short_entry, "SELL", atr=short_atr,
                stop_mult=PAIRS_STOP_ATR_MULT, tp_mult=PAIRS_TP_ATR_MULT,
            )

            outside_rth_stop = get_outside_rth_stop(TRADING_DIR)
            outside_rth_tp = get_outside_rth_take_profit(TRADING_DIR)

            long_stop_intent = build_intent(
                symbol=long_sym, side="SELL", quantity=long_fill_qty,
                policy=ExecutionPolicy.STOP_PROTECT, source_script=self.script_name,
                stop_price=long_stop, limit_price=long_stop,
                outside_rth=outside_rth_stop,
            )
            long_tp_intent = build_intent(
                symbol=long_sym, side="SELL", quantity=long_fill_qty,
                policy=ExecutionPolicy.PASSIVE_ENTRY, source_script=self.script_name,
                limit_price=long_tp, outside_rth=outside_rth_tp,
            )
            short_stop_intent = build_intent(
                symbol=short_sym, side="BUY", quantity=short_fill_qty,
                policy=ExecutionPolicy.STOP_PROTECT, source_script=self.script_name,
                stop_price=short_stop, limit_price=short_stop,
                outside_rth=outside_rth_stop,
            )
            short_tp_intent = build_intent(
                symbol=short_sym, side="BUY", quantity=short_fill_qty,
                policy=ExecutionPolicy.PASSIVE_ENTRY, source_script=self.script_name,
                limit_price=short_tp, outside_rth=outside_rth_tp,
            )

            await self.submit_protective_with_retry(
                parent_result=long_result,
                follow_ups=[long_stop_intent, long_tp_intent],
                symbol=long_sym,
            )
            await self.submit_protective_with_retry(
                parent_result=short_result,
                follow_ups=[short_stop_intent, short_tp_intent],
                symbol=short_sym,
            )

            long_rec = build_enriched_record(
                symbol=long_sym, side="LONG", action="BUY",
                source_script=self.script_name,
                status="Filled" if long_result.is_filled else "PartiallyFilled",
                order_id=long_result.broker_order_id or 0,
                quantity=long_fill_qty,
                entry_price=long_entry, stop_price=long_stop, profit_price=long_tp,
                atr_at_entry=long_atr,
                composite_score=pair.get("long_score"),
                signal_price=long_price,
                reason=f"pairs_long {sector} {short_sym}",
                extra={
                    "strategy": "pairs_long", "pair_short": short_sym,
                    "sector": sector, "commission": long_result.total_commission,
                },
            )
            short_rec = build_enriched_record(
                symbol=short_sym, side="SHORT", action="SELL",
                source_script=self.script_name,
                status="Filled" if short_result.is_filled else "PartiallyFilled",
                order_id=short_result.broker_order_id or 0,
                quantity=short_fill_qty,
                entry_price=short_entry, stop_price=short_stop, profit_price=short_tp,
                atr_at_entry=short_atr,
                composite_score=pair.get("short_score"),
                signal_price=short_price,
                reason=f"pairs_short {sector} {long_sym}",
                extra={
                    "strategy": "pairs_short", "pair_long": long_sym,
                    "sector": sector, "commission": short_result.total_commission,
                },
            )

            self.log.info(
                "Pair placed: %s BUY %d @ %.2f (stop=%.2f tp=%.2f) | %s SELL %d @ %.2f (stop=%.2f tp=%.2f)",
                long_sym, long_fill_qty, long_entry, long_stop, long_tp,
                short_sym, short_fill_qty, short_entry, short_stop, short_tp,
            )
            return True, [long_rec, short_rec]
        except Exception as e:
            self.log.error("Pair execution error %s/%s: %s", long_sym, short_sym, e)
            return False, []


async def run() -> None:
    await PairsExecutor().run()


if __name__ == "__main__":
    asyncio.run(run())
