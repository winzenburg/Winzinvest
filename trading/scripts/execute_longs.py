#!/usr/bin/env python3
"""
Long-only executor: load watchlist_longs.json, place BUY orders with
ATR-based trailing stop and take-profit.

Skips symbols already long. Logs to shared executions.json.

All broker interaction is routed through OrderRouter — no direct
ib_insync order calls outside this orchestration layer.
"""

import asyncio
import json
from pathlib import Path

from atr_stops import (
    calculate_position_size,
    compute_stop_tp,
    compute_trailing_amount,
    fetch_atr,
)
from base_executor import BaseExecutor
from broker_data_helpers import atr_from_ib
from candidate_ranking import long_conviction
from enriched_record import build_enriched_record
from execution_policy import ExecutionPolicy, build_intent
from risk_config import (
    get_allow_outside_rth_entry,
    get_max_long_positions,
    get_outside_rth_stop,
    get_outside_rth_take_profit,
)
from sector_gates import SECTOR_MAP
from pre_trade_guard import PreTradeViolation, assert_no_flip

from paths import TRADING_DIR

WATCHLIST_LONGS_FILE = TRADING_DIR / "watchlist_longs.json"


def _load_long_candidates() -> list[dict]:
    if not WATCHLIST_LONGS_FILE.exists():
        return []
    try:
        data = json.loads(WATCHLIST_LONGS_FILE.read_text())
    except (OSError, ValueError):
        return []
    candidates = data.get("long_candidates", [])
    if not isinstance(candidates, list):
        return []
    result: list[dict] = []
    for c in candidates:
        if not isinstance(c, dict) or not c.get("symbol") or not isinstance(c.get("price"), (int, float)):
            continue
        entry: dict = {
            "symbol": c.get("symbol", "").strip().upper(),
            "price": float(c.get("price", 0)),
        }
        for key in (
            "mtf_score", "earnings_boost", "earnings_date", "sector_multiplier",
            "sector", "rs_pct", "recent_return", "hybrid_score",
            "composite", "structure", "rvol_atr",
        ):
            if key in c:
                entry[key] = c[key]
        result.append(entry)
    return result


class LongsExecutor(BaseExecutor):
    script_name = "execute_longs.py"
    log_file_stem = "execute_longs"
    state_store_name = "order_state_longs.jsonl"
    client_id = 102
    job_lock_name = "execute_longs"
    position_side = "long"

    async def execute(self) -> None:
        max_longs = get_max_long_positions(TRADING_DIR)
        current_longs = self.current_long_symbols()

        if len(current_longs) >= max_longs:
            self.log.warning(
                "Max long positions reached (%d/%d). No new longs.",
                len(current_longs), max_longs,
            )
            return

        candidates = _load_long_candidates()
        if not candidates:
            self.log.info("No long candidates")
            return

        self.log.info(
            "Risk %.1f%% per trade | Max position %.1f%% ($%s)",
            self.risk_per_trade_pct * 100,
            self.max_position_pct * 100,
            f"{self.effective_equity * self.max_position_pct:,.0f}",
        )

        for candidate in candidates[:15]:
            if len(current_longs) >= max_longs:
                self.log.info(
                    "Max long positions reached mid-loop (%d/%d). Stopping.",
                    len(current_longs), max_longs,
                )
                break

            symbol = candidate["symbol"]
            estimated_notional = min(
                self.net_liq * self.max_position_pct,
                candidate["price"] * self.absolute_max_shares,
            )
            gates_ok, failed_gates = self.check_gates("LONG", symbol, estimated_notional)
            if not gates_ok:
                self.log.info("Skipping long %s: gates failed: %s", symbol, ", ".join(failed_gates))
                continue

            ok, rec = await self._execute_one(candidate, current_longs)
            if ok and rec is not None:
                current_longs.add(symbol)
                sector = SECTOR_MAP.get(symbol, "Unknown")
                self.sector_exposure[sector] = self.sector_exposure.get(sector, 0.0) + estimated_notional
                self.total_notional += estimated_notional
                self.executions.append(rec)
            await asyncio.sleep(1)

    async def _execute_one(
        self,
        candidate: dict,
        current_longs: set[str],
    ) -> tuple[bool, dict | None]:
        assert self.router is not None
        symbol = candidate["symbol"]
        if symbol in current_longs:
            self.log.info("Skipping %s: already long", symbol)
            return False, None
        price = candidate["price"]

        try:
            atr = fetch_atr(symbol)
            if atr is None:
                atr = atr_from_ib(symbol, self.ib)

            conv = long_conviction(candidate)
            qty = calculate_position_size(
                self.effective_equity, price, atr=atr,
                risk_pct=self.risk_per_trade_pct,
                max_position_pct=self.max_position_pct,
                absolute_max_shares=self.absolute_max_shares,
                conviction=conv,
                cap_equity=self.net_liq,
            )

            outside_rth = get_allow_outside_rth_entry(TRADING_DIR)
            policy = ExecutionPolicy.PASSIVE_ENTRY if outside_rth else ExecutionPolicy.AGGRESSIVE_ENTRY

            entry_intent = build_intent(
                symbol=symbol, side="BUY", quantity=qty,
                policy=policy, source_script=self.script_name,
                limit_price=price, outside_rth=outside_rth,
                metadata={
                    "regime": self.regime, "conviction": conv,
                    "atr": atr, "signal_price": price,
                },
            )

            try:
                assert_no_flip(self.ib, symbol, "LONG")
            except PreTradeViolation as e:
                self.log.error("%s", e)
                return False, None

            result = await self.router.submit(entry_intent, ask=price)

            if not result.success or (not result.is_filled and not result.is_partial):
                self.log.warning(
                    "Long order not filled for %s: status=%s error=%s",
                    symbol,
                    result.status.value if result.status else "None",
                    result.error or "",
                )
                return False, None

            filled_qty = result.filled_qty
            entry_price = result.avg_fill_price
            fill_commission = result.total_commission

            if filled_qty != qty:
                self.log.warning("Partial fill on long %s: requested %d, filled %d", symbol, qty, filled_qty)

            fill_slippage = abs(entry_price - price) if entry_price > 0 else 0.0
            stop_price, tp_price = compute_stop_tp(entry_price, "BUY", atr=atr)
            trail_amt = compute_trailing_amount(atr=atr, entry_price=entry_price)

            trailing_intent = build_intent(
                symbol=symbol, side="SELL", quantity=filled_qty,
                policy=ExecutionPolicy.TRAILING_STOP, source_script=self.script_name,
                trail_amount=trail_amt, outside_rth=get_outside_rth_stop(TRADING_DIR),
            )
            tp_intent = build_intent(
                symbol=symbol, side="SELL", quantity=filled_qty,
                policy=ExecutionPolicy.PASSIVE_ENTRY, source_script=self.script_name,
                limit_price=tp_price, outside_rth=get_outside_rth_take_profit(TRADING_DIR),
            )

            protective_results = await self.router.submit_protective_orders(
                parent_result=result, follow_ups=[trailing_intent, tp_intent],
            )
            for pr in protective_results:
                if not pr.success:
                    self.log.error("Protective order failed for %s: %s", symbol, pr.error)

            rec = build_enriched_record(
                symbol=symbol, side="LONG", action="BUY",
                source_script=self.script_name,
                status="Filled" if result.is_filled else "PartiallyFilled",
                order_id=result.broker_order_id or 0,
                quantity=filled_qty,
                entry_price=entry_price, stop_price=stop_price, profit_price=tp_price,
                regime_at_entry=self.regime, conviction_score=conv, atr_at_entry=atr,
                rs_pct=candidate.get("rs_pct") or candidate.get("score"),
                composite_score=candidate.get("composite_score"),
                structure_quality=candidate.get("structure_quality"),
                rvol_atr=candidate.get("rvol_atr"),
                signal_price=price, slippage=fill_slippage,
                extra={"commission": fill_commission},
            )
            self.log.info(
                "Long placed: %s entry=%.2f trail=%.2f tp=%.2f slip=%.4f",
                symbol, entry_price, trail_amt, tp_price, fill_slippage,
            )
            self.notify_fill("LONG", symbol, entry_price, filled_qty, stop=stop_price, tp=tp_price)
            return True, rec
        except Exception as e:
            self.log.error("Execution error %s: %s", symbol, e)
            return False, None


async def run() -> None:
    await LongsExecutor().run()


if __name__ == "__main__":
    asyncio.run(run())
