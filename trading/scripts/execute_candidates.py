#!/usr/bin/env python3
"""
Auto-Execute Pipeline
Reads screener candidates, auto-executes to IBKR.
Enforces position sizing, stops, profit targets, daily loss limits.

All broker interaction is routed through OrderRouter — no direct
ib_insync order calls outside this orchestration layer.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from atr_stops import (
    calculate_position_size,
    compute_stop_tp,
    compute_trailing_amount,
    fetch_atr,
)
from base_executor import BaseExecutor
from broker_data_helpers import atr_from_ib
from candidate_ranking import long_conviction, rank_short_candidates, short_conviction
from enriched_record import build_enriched_record
from execution_policy import ExecutionPolicy, build_intent
from position_filter import load_current_short_symbols
from risk_config import (
    get_max_new_shorts_per_day,
    get_max_short_positions,
    get_outside_rth_stop,
    get_outside_rth_take_profit,
)
from sector_gates import SECTOR_MAP

from paths import TRADING_DIR

WATCHLIST_MULTIMODE_FILE = TRADING_DIR / "watchlist_multimode.json"
CANDIDATES_FILE = TRADING_DIR / "screener_candidates.json"


def _count_new_shorts_today(log_path: Path) -> int:
    """Count SHORT/SELL executions in the log with timestamp today."""
    if not log_path.exists():
        return 0
    today = datetime.now().date().isoformat()
    count = 0
    try:
        for line in log_path.read_text().strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            ts = obj.get("timestamp") or obj.get("timestamp_iso") or ""
            if not str(ts).startswith(today):
                continue
            if obj.get("action") == "SELL" or obj.get("type") == "SHORT":
                count += 1
    except (OSError, ValueError):
        pass
    return count


# ---------------------------------------------------------------------------
# Candidate loaders
# ---------------------------------------------------------------------------


def _load_from_multimode() -> list[dict] | None:
    """Build candidate list from watchlist_multimode.json."""
    if not WATCHLIST_MULTIMODE_FILE.exists():
        return None
    try:
        data = json.loads(WATCHLIST_MULTIMODE_FILE.read_text())
    except (OSError, ValueError):
        return None
    modes = data.get("modes", {})
    if not isinstance(modes, dict):
        return []
    seen: set[str] = set()
    candidates: list[dict] = []
    for mode_key in ("short_opportunities", "premium_selling"):
        short_list = modes.get(mode_key, {}).get("short", [])
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
            price = item.get("price")
            try:
                price_f = float(price) if price is not None else 0.0
            except (TypeError, ValueError):
                continue
            if price_f <= 0:
                continue
            seen.add(symbol)
            score = item.get("rs_pct", 0)
            try:
                score_f = float(score)
            except (TypeError, ValueError):
                score_f = 0.0
            momentum = item.get("recent_return", -0.01)
            try:
                momentum_f = float(momentum)
            except (TypeError, ValueError):
                momentum_f = -0.01
            candidates.append({
                "symbol": symbol,
                "price": price_f,
                "score": score_f,
                "momentum": momentum_f,
            })
    return candidates


def _load_from_tier_file() -> list[dict]:
    """Fallback: load from legacy screener_candidates.json."""
    if not CANDIDATES_FILE.exists():
        return []
    data = json.loads(CANDIDATES_FILE.read_text())
    tier2 = data.get("tier_2", [])
    tier3 = data.get("tier_3", [])
    return tier2 + tier3


class CandidateExecutor(BaseExecutor):
    script_name = "execute_candidates.py"
    log_file_stem = "execute_candidates"
    state_store_name = "order_state_candidates.jsonl"
    client_id = 101
    job_lock_name = "execute_candidates"
    position_side = "short"
    apply_allocation = False
    use_drawdown_breaker = False

    def __init__(self) -> None:
        super().__init__()
        self.current_shorts: set[str] = set()
        self.max_short_positions: int = 10
        self.max_new_shorts_per_day: int | None = None
        self.new_shorts_today: int = 0

    async def execute(self) -> None:
        self.current_shorts = load_current_short_symbols(TRADING_DIR, self.ib)
        self.max_short_positions = get_max_short_positions(TRADING_DIR)
        self.max_new_shorts_per_day = get_max_new_shorts_per_day(TRADING_DIR)
        self.new_shorts_today = _count_new_shorts_today(self.execution_log_path)

        candidates = _load_from_multimode()
        if candidates is None:
            candidates = _load_from_tier_file()
        if not candidates:
            self.log.info("No candidates to execute")
            return

        candidates = rank_short_candidates(candidates)
        self.log.info(
            "Executing top %d of %d candidates (ranked by conviction)...",
            min(5, len(candidates)), len(candidates),
        )

        for candidate in candidates[:5]:
            await self._execute_candidate(candidate)
            await asyncio.sleep(1)

    async def _execute_candidate(self, candidate: dict) -> bool:
        assert self.router is not None
        try:
            symbol = candidate["symbol"]
            score = candidate["score"]
            momentum = candidate["momentum"]
            price = candidate["price"]

            action = "BUY" if momentum > 0 else "SELL"
            side = "SHORT" if action == "SELL" else "LONG"

            if action == "SELL" and symbol in self.current_shorts:
                self.log.info("Skipping %s: already short", symbol)
                return False

            if action == "SELL" and len(self.current_shorts) >= self.max_short_positions:
                self.log.info(
                    "Skipping %s: would exceed max short positions (%d)",
                    symbol, self.max_short_positions,
                )
                self.executions.append({
                    "symbol": symbol, "type": "SHORT",
                    "source_script": self.script_name,
                    "status": "SKIPPED", "reason": "max short positions",
                    "timestamp": datetime.now().isoformat(),
                })
                return False

            if (
                action == "SELL"
                and self.max_new_shorts_per_day is not None
                and self.new_shorts_today >= self.max_new_shorts_per_day
            ):
                self.log.info(
                    "Skipping %s: max new shorts per day reached (%d/%d)",
                    symbol, self.new_shorts_today, self.max_new_shorts_per_day,
                )
                self.executions.append({
                    "symbol": symbol, "type": "SHORT",
                    "source_script": self.script_name,
                    "status": "SKIPPED", "reason": "max new shorts per day",
                    "timestamp": datetime.now().isoformat(),
                })
                return False

            equity_net = self.net_liq or 100_000.0
            equity_effective = self.effective_equity or equity_net

            if action == "SELL":
                notional_short = min(
                    equity_effective * self.max_position_pct,
                    price * self.absolute_max_shares,
                )
                gates_ok, failed_gates = self.check_gates("SHORT", symbol, notional_short)
                if not gates_ok:
                    reason = "gates: " + ", ".join(failed_gates)
                    self.log.info("Skipping %s: %s", symbol, reason)
                    self.executions.append({
                        "symbol": symbol, "type": "SHORT",
                        "source_script": self.script_name,
                        "status": "SKIPPED", "reason": reason,
                        "timestamp": datetime.now().isoformat(),
                    })
                    return False

            atr = fetch_atr(symbol)
            if atr is None:
                atr = atr_from_ib(symbol, self.ib)

            conv = short_conviction(candidate) if side == "SHORT" else long_conviction(candidate)
            qty = calculate_position_size(
                equity_effective, price, atr=atr,
                risk_pct=self.risk_per_trade_pct,
                max_position_pct=self.max_position_pct,
                absolute_max_shares=self.absolute_max_shares,
                conviction=conv,
            )
            self.log.info(
                "Executing: %s | Score: %.3f | Mom: %+.2f | Price: $%.2f | Qty: %d | Conv: %.2f",
                symbol, score, momentum, price, qty, conv,
            )

            entry_intent = build_intent(
                symbol=symbol, side=action, quantity=qty,
                policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
                source_script=self.script_name, limit_price=price,
                metadata={
                    "regime": self.regime, "conviction": conv,
                    "atr": atr, "signal_price": price,
                    "score": score, "momentum": momentum,
                },
            )

            result = await self.router.submit(
                entry_intent,
                bid=price if action == "SELL" else None,
                ask=price if action == "BUY" else None,
            )

            if not result.success or (not result.is_filled and not result.is_partial):
                self.log.warning(
                    "Order not filled, cancelled: %s status=%s error=%s",
                    symbol,
                    result.status.value if result.status else "None",
                    result.error or "",
                )
                self.executions.append({
                    "symbol": symbol, "type": side,
                    "source_script": self.script_name,
                    "status": "CANCELLED",
                    "reason": f"not filled: {result.status.value if result.status else 'unknown'}",
                    "timestamp": datetime.now().isoformat(),
                })
                return False

            filled_qty = result.filled_qty
            entry_fill = result.avg_fill_price
            fill_commission = result.total_commission

            if filled_qty != qty:
                self.log.warning(
                    "Partial fill on %s %s: requested %d, filled %d",
                    action, symbol, qty, filled_qty,
                )

            fill_slippage = abs(entry_fill - price) if entry_fill > 0 else 0.0
            stop_price, profit_price = compute_stop_tp(entry_fill, action, atr=atr)

            if action == "SELL":
                trail_amt = compute_trailing_amount(atr=atr, entry_price=entry_fill)

                trailing_intent = build_intent(
                    symbol=symbol, side="BUY", quantity=filled_qty,
                    policy=ExecutionPolicy.TRAILING_STOP,
                    source_script=self.script_name,
                    trail_amount=trail_amt,
                    outside_rth=get_outside_rth_stop(TRADING_DIR),
                )
                tp_intent = build_intent(
                    symbol=symbol, side="BUY", quantity=filled_qty,
                    policy=ExecutionPolicy.PASSIVE_ENTRY,
                    source_script=self.script_name,
                    limit_price=profit_price,
                    outside_rth=get_outside_rth_take_profit(TRADING_DIR),
                )

                protective_results = await self.router.submit_protective_orders(
                    parent_result=result,
                    follow_ups=[trailing_intent, tp_intent],
                )
                for pr in protective_results:
                    if not pr.success:
                        self.log.error("Protective order failed for %s: %s", symbol, pr.error)

                self.log.info("Trailing stop: $%.2f trail | TP: $%.2f", trail_amt, profit_price)

            execution = build_enriched_record(
                symbol=symbol, side=side, action=action,
                source_script=self.script_name,
                status="Filled" if result.is_filled else "PartiallyFilled",
                order_id=result.broker_order_id or 0,
                quantity=filled_qty,
                entry_price=float(entry_fill),
                stop_price=float(stop_price),
                profit_price=float(profit_price),
                regime_at_entry=self.regime,
                conviction_score=conv,
                atr_at_entry=atr,
                rs_pct=candidate.get("score") or candidate.get("rs_pct"),
                composite_score=candidate.get("composite_score"),
                structure_quality=candidate.get("structure_quality"),
                rvol_atr=candidate.get("rvol_atr"),
                signal_price=price, slippage=fill_slippage,
                extra={
                    "score": float(score),
                    "momentum": float(momentum),
                    "commission": fill_commission,
                },
            )
            self.executions.append(execution)
            self.log.info(
                "EXECUTED: %s | Entry: $%.2f | Stop: $%.2f | Target: $%.2f",
                symbol, entry_fill, stop_price, profit_price,
            )

            if action == "SELL":
                self.current_shorts.add(symbol)
                self.new_shorts_today += 1
                sector = SECTOR_MAP.get(symbol, "Unknown")
                self.sector_exposure[sector] = (
                    self.sector_exposure.get(sector, 0.0) - abs(entry_fill * qty)
                )
                self.total_notional += abs(entry_fill * qty)
            return True

        except Exception as e:
            self.log.error("Execution error: %s", e)
            return False


async def main() -> None:
    await CandidateExecutor().run()


if __name__ == "__main__":
    asyncio.run(main())
