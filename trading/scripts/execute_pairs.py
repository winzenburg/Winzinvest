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
import sys
from datetime import datetime
from pathlib import Path

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
    except Exception:
        pass
    return longs, shorts


def _notional_per_leg(account_equity: float) -> float:
    """Equal dollar notional per leg: min($50K, 2.5% of equity)."""
    pct_amount = account_equity * NOTIONAL_PCT_PER_LEG
    return min(NOTIONAL_PER_LEG, pct_amount)


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
        """Check open pairs for exit: spread z-score < 0.5 or 15 days.

        Returns list of exit records for logging.
        """
        # TODO: Implement full exit logic (requires live spread z-score + entry date)
        return []

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

        long_price = float(pair.get("long_price") or 0)
        short_price = float(pair.get("short_price") or 0)
        if long_price <= 0 or short_price <= 0:
            self.log.warning("Pair %s/%s: missing prices", long_sym, short_sym)
            return False, []

        long_qty = max(1, int(notional_per_leg / long_price))
        short_qty = max(1, int(notional_per_leg / short_price))
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

            # --- Entry: long leg ---
            long_intent = build_intent(
                symbol=long_sym, side="BUY", quantity=long_qty,
                policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
                source_script=self.script_name,
                limit_price=long_price,
                metadata={"strategy": "pairs_long", "pair_short": short_sym, "sector": sector},
            )
            long_result = await self.router.submit(long_intent, ask=long_price)

            long_filled = long_result.is_filled or long_result.is_partial
            if not long_filled:
                self.log.warning(
                    "Pair %s/%s: long leg not filled (status=%s) — aborting pair",
                    long_sym, short_sym,
                    long_result.status.value if long_result.status else "None",
                )
                return False, []

            # --- Entry: short leg ---
            short_intent = build_intent(
                symbol=short_sym, side="SELL", quantity=short_qty,
                policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
                source_script=self.script_name,
                limit_price=short_price,
                metadata={"strategy": "pairs_short", "pair_long": long_sym, "sector": sector},
            )
            short_result = await self.router.submit(short_intent, bid=short_price)

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

            await self.router.submit_protective_orders(
                parent_result=long_result,
                follow_ups=[long_stop_intent, long_tp_intent],
            )
            await self.router.submit_protective_orders(
                parent_result=short_result,
                follow_ups=[short_stop_intent, short_tp_intent],
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
