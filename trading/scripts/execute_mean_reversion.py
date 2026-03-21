#!/usr/bin/env python3
"""
Mean Reversion (RSI-2) Executor.

Loads watchlist_mean_reversion.json, places BUY orders with tight stops
(1.0 ATR stop, 1.5 ATR TP). Monitors existing MR positions for RSI(2) > 70 exit.
Uses clientId=107. Writes to shared EXECUTION_LOG.

All broker interaction is routed through OrderRouter — no direct
ib_insync order calls outside this orchestration layer.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

import numpy as np
import pandas as pd
import yfinance as yf

from atr_stops import (
    calculate_position_size,
    compute_stop_tp,
    compute_trailing_amount,
    fetch_atr,
)
from base_executor import BaseExecutor
from broker_data_helpers import atr_from_ib
from enriched_record import build_enriched_record
from execution_policy import ExecutionPolicy, build_intent
from order_router import OrderRouter
from pre_trade_guard import PreTradeViolation, assert_no_flip
from risk_config import (
    get_allow_outside_rth_entry,
    get_max_long_positions,
    get_mr_params,
    get_outside_rth_stop,
    get_outside_rth_take_profit,
)
from sector_gates import SECTOR_MAP

from paths import TRADING_DIR

WATCHLIST_MR_FILE = TRADING_DIR / "watchlist_mean_reversion.json"
MR_POSITIONS_FILE = TRADING_DIR / "logs" / "mr_positions.json"

_mr_cfg = get_mr_params(Path(__file__).resolve().parent.parent)
MR_STOP_ATR_MULT: float = _mr_cfg["stop_atr_mult"]
MR_TP_ATR_MULT: float = _mr_cfg["tp_atr_mult"]
MR_TRAILING_ATR_MULT: float = _mr_cfg["trailing_atr_mult"]
MR_RSI_EXIT_THRESHOLD: float = _mr_cfg["rsi_exit_threshold"]
MAX_CANDIDATES_PER_RUN: int = _mr_cfg["max_candidates_per_run"]


# ---------------------------------------------------------------------------
# MR position persistence
# ---------------------------------------------------------------------------


def _load_mr_positions(live_long_symbols: set[str] | None = None) -> list[str]:
    """Load MR tracked symbols, optionally pruning any that are no longer held long.

    Passing ``live_long_symbols`` removes stale entries that accumulate when
    positions are closed without going through the MR executor's own exit path
    (e.g. stopped out via pending_trades, manually closed, or assigned on options).
    This prevents the position-integrity check from raising false violations.
    """
    if not MR_POSITIONS_FILE.exists():
        return []
    try:
        data = json.loads(MR_POSITIONS_FILE.read_text())
        symbols = data.get("symbols", [])
        if not isinstance(symbols, list):
            return []
        result = [s for s in symbols if isinstance(s, str) and s.strip()]
        if live_long_symbols is not None:
            pruned = [s for s in result if s.upper() not in live_long_symbols]
            if pruned:
                logger.info("Pruning stale MR positions no longer held long: %s", pruned)
                result = [s for s in result if s.upper() in live_long_symbols]
                _save_mr_positions(result)
        return result
    except (OSError, ValueError, TypeError):
        pass
    return []


def _save_mr_positions(symbols: list[str]) -> None:
    MR_POSITIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        MR_POSITIONS_FILE.write_text(
            json.dumps({"symbols": symbols, "updated_at": datetime.now().isoformat()}),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.error("Failed to persist MR positions (data may be lost on restart): %s", exc)


def _compute_rsi2(symbol: str) -> float | None:
    try:
        df = yf.download(symbol, period="1mo", progress=False)
        if df is None or df.empty or len(df) < 4:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        close = df["Close"].values
        if len(close) < 3:
            return None
        diffs = np.diff(close[-3:])
        gains = np.mean(diffs[diffs > 0]) if np.any(diffs > 0) else 0.0
        losses = np.mean(-diffs[diffs < 0]) if np.any(diffs < 0) else 0.0001
        rs = gains / losses if losses > 0 else 100.0
        return float(100 - (100 / (1 + rs)))
    except Exception:
        return None


def _load_mr_candidates() -> list[dict]:
    if not WATCHLIST_MR_FILE.exists():
        return []
    try:
        data = json.loads(WATCHLIST_MR_FILE.read_text())
        candidates = data.get("candidates", [])
        if not isinstance(candidates, list):
            return []
        out: list[dict] = []
        for c in candidates:
            if not isinstance(c, dict):
                continue
            sym = c.get("symbol")
            price = c.get("price")
            if not isinstance(sym, str) or not sym.strip():
                continue
            if not isinstance(price, (int, float)) or float(price) <= 0:
                continue
            out.append({
                "symbol": sym.strip().upper(),
                "price": float(price),
                "rsi2": c.get("rsi2"),
                "sma200": c.get("sma200"),
                "score": c.get("score"),
                "reason": c.get("reason"),
            })
        return out
    except (OSError, ValueError, TypeError):
        return []


# ---------------------------------------------------------------------------
# MeanReversionExecutor
# ---------------------------------------------------------------------------


class MeanReversionExecutor(BaseExecutor):
    script_name = "execute_mean_reversion.py"
    log_file_stem = "execute_mr"
    state_store_name = "order_state_mr.jsonl"
    client_id = 107
    job_lock_name = "execute_mean_reversion"
    position_side = "long"
    use_drawdown_breaker = False

    async def execute(self) -> None:
        assert self.router is not None

        # Phase 1: monitor existing MR positions for RSI exit
        exit_records = await self._monitor_mr_exits()
        if exit_records:
            self.executions.extend(exit_records)

        # Phase 2: enter new MR candidates
        max_longs = get_max_long_positions(TRADING_DIR)
        current_longs = self.current_long_symbols()

        candidates = _load_mr_candidates()
        if not candidates:
            self.log.info("No MR candidates")
            return

        if len(current_longs) >= max_longs:
            self.log.warning(
                "Max long positions reached (%d/%d). No new MR orders.",
                len(current_longs), max_longs,
            )
            return

        mr_symbols = _load_mr_positions(live_long_symbols={s.upper() for s in current_longs})

        for candidate in candidates[:MAX_CANDIDATES_PER_RUN]:
            if len(current_longs) >= max_longs:
                break
            symbol = str(candidate.get("symbol", "")).strip().upper()
            price = float(candidate.get("price", 0))
            estimated_notional = min(
                self.net_liq * self.max_position_pct,
                price * self.absolute_max_shares,
            )

            gates_ok, failed_gates = self.check_gates("LONG", symbol, estimated_notional)
            if not gates_ok:
                self.log.info("Skipping MR %s: gates failed: %s", symbol, ", ".join(failed_gates))
                continue

            ok, rec = await self._execute_one_mr(candidate, current_longs)
            if ok and rec is not None:
                current_longs.add(symbol)
                mr_symbols.append(symbol)
                sector = SECTOR_MAP.get(symbol, "Unknown")
                self.sector_exposure[sector] = self.sector_exposure.get(sector, 0.0) + estimated_notional
                self.total_notional += estimated_notional
                self.executions.append(rec)
            await asyncio.sleep(1)

        if mr_symbols:
            _save_mr_positions(mr_symbols)

    # ------------------------------------------------------------------
    # RSI(2) exit monitor
    # ------------------------------------------------------------------

    async def _monitor_mr_exits(self) -> list[dict]:
        """Check MR positions for RSI(2) > 70 exit. Close via router."""
        assert self.router is not None
        current_longs = self.current_long_symbols()
        # Prune stale entries on every exit-monitor pass
        mr_symbols = _load_mr_positions(live_long_symbols={s.upper() for s in current_longs})
        closed_records: list[dict] = []
        remaining_mr: list[str] = []

        for symbol in mr_symbols:
            if symbol not in current_longs:
                remaining_mr.append(symbol)
                continue

            rsi2 = _compute_rsi2(symbol)
            if rsi2 is None:
                remaining_mr.append(symbol)
                continue
            if rsi2 <= MR_RSI_EXIT_THRESHOLD:
                remaining_mr.append(symbol)
                continue

            qty = 0
            try:
                for pos in self.ib.positions():
                    if getattr(pos.contract, "symbol", "") == symbol and getattr(pos, "position", 0) > 0:
                        qty = int(pos.position)
                        break
            except Exception as e:
                self.log.warning("Could not get position size for %s: %s", symbol, e)
                remaining_mr.append(symbol)
                continue

            if qty <= 0:
                remaining_mr.append(symbol)
                continue

            ok, rec = await self._close_mr_position(symbol, qty)
            if ok and rec is not None:
                closed_records.append(rec)
            else:
                remaining_mr.append(symbol)
            await asyncio.sleep(1)

        _save_mr_positions(remaining_mr)
        return closed_records

    async def _close_mr_position(self, symbol: str, quantity: int) -> tuple[bool, dict | None]:
        """Place URGENT_EXIT SELL to close MR position."""
        assert self.router is not None
        try:
            close_intent = build_intent(
                symbol=symbol, side="SELL", quantity=quantity,
                policy=ExecutionPolicy.URGENT_EXIT,
                source_script=self.script_name,
                metadata={"exit_reason": "rsi_overbought"},
            )

            result = await self.router.submit(close_intent)

            if not result.success or (not result.is_filled and not result.is_partial):
                self.log.warning(
                    "MR close order not filled: %s status=%s error=%s",
                    symbol,
                    result.status.value if result.status else "None",
                    result.error or "",
                )
                return False, None

            rec = build_enriched_record(
                symbol=symbol, side="LONG", action="SELL",
                source_script=self.script_name,
                status="Filled" if result.is_filled else "PartiallyFilled",
                order_id=result.broker_order_id or 0,
                quantity=result.filled_qty,
                entry_price=result.avg_fill_price,
                stop_price=0.0, profit_price=0.0,
                reason="RSI(2) > 70 exit",
                extra={
                    "strategy": "mean_reversion",
                    "exit_reason": "rsi_overbought",
                    "commission": result.total_commission,
                },
            )
            self.log.info("MR position closed: %s qty=%d price=%.2f", symbol, result.filled_qty, result.avg_fill_price)
            return True, rec
        except Exception as e:
            self.log.error("Close error %s: %s", symbol, e)
            return False, None

    # ------------------------------------------------------------------
    # MR entry
    # ------------------------------------------------------------------

    async def _execute_one_mr(
        self,
        candidate: dict,
        current_longs: set[str],
    ) -> tuple[bool, dict | None]:
        """Execute one MR buy via OrderRouter. Uses 1.0 ATR stop, 1.5 ATR TP."""
        assert self.router is not None
        symbol = str(candidate.get("symbol", "")).strip().upper()
        if symbol in current_longs:
            self.log.info("Skipping %s: already long", symbol)
            return False, None
        price = float(candidate.get("price", 0))

        try:
            assert_no_flip(self.ib, symbol, "LONG")
        except PreTradeViolation as e:
            self.log.error("MR long blocked by pre_trade_guard: %s", e)
            return False, None

        try:
            atr = fetch_atr(symbol)
            if atr is None:
                atr = atr_from_ib(symbol, self.ib)

            qty = calculate_position_size(
                self.effective_equity, price, atr=atr,
                risk_pct=self.risk_per_trade_pct,
                max_position_pct=self.max_position_pct,
                absolute_max_shares=self.absolute_max_shares,
                stop_mult=MR_STOP_ATR_MULT,
                conviction=None,
                cap_equity=self.net_liq,
            )

            outside_rth = get_allow_outside_rth_entry(TRADING_DIR)
            entry_intent = build_intent(
                symbol=symbol, side="BUY", quantity=qty,
                policy=ExecutionPolicy.PASSIVE_ENTRY if outside_rth else ExecutionPolicy.AGGRESSIVE_ENTRY,
                source_script=self.script_name,
                limit_price=price, outside_rth=outside_rth,
                metadata={
                    "strategy": "mean_reversion",
                    "signal_price": price, "atr": atr,
                    "rsi2": candidate.get("rsi2"),
                },
            )

            result = await self.router.submit(entry_intent, ask=price)

            if not result.success or (not result.is_filled and not result.is_partial):
                self.log.warning(
                    "MR order not filled for %s: status=%s error=%s",
                    symbol,
                    result.status.value if result.status else "None",
                    result.error or "",
                )
                return False, None

            filled_qty = result.filled_qty
            entry_price = result.avg_fill_price
            fill_commission = result.total_commission
            fill_slippage = abs(entry_price - price) if entry_price > 0 else 0.0

            stop_price, tp_price = compute_stop_tp(
                entry_price, "BUY", atr=atr,
                stop_mult=MR_STOP_ATR_MULT, tp_mult=MR_TP_ATR_MULT,
            )
            trail_amt = compute_trailing_amount(
                atr=atr, entry_price=entry_price,
                trailing_mult=MR_TRAILING_ATR_MULT,
            )

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
                atr_at_entry=atr,
                rs_pct=candidate.get("score"),
                signal_price=price, slippage=fill_slippage,
                reason=candidate.get("reason"),
                extra={
                    "commission": fill_commission,
                    "strategy": "mean_reversion",
                    "rsi2": candidate.get("rsi2"),
                },
            )
            self.log.info(
                "MR placed: %s entry=%.2f trail=%.2f tp=%.2f slip=%.4f",
                symbol, entry_price, trail_amt, tp_price, fill_slippage,
            )

            if filled_qty >= 100:
                try:
                    from post_entry_premium import write_covered_call

                    cc = write_covered_call(self.ib, symbol=symbol, shares_held=filled_qty)
                    self.log.info(
                        "Post-entry CC (%s): status=%s strike=%s premium=$%.0f reason=%s",
                        symbol, cc["status"], cc.get("strike"),
                        cc.get("premium_total", 0), cc.get("reason", ""),
                    )
                except Exception as cc_err:
                    self.log.warning("Post-entry CC failed for %s: %s", symbol, cc_err)

            return True, rec
        except Exception as e:
            self.log.error("Execution error %s: %s", symbol, e)
            return False, None


async def run() -> None:
    await MeanReversionExecutor().run()


if __name__ == "__main__":
    asyncio.run(run())
