#!/usr/bin/env python3
"""
Auto-Execute Pipeline
Reads screener candidates, auto-executes to IBKR
Enforces position sizing, stops, profit targets, daily loss limits
"""

import json
import os
import pandas as pd
import numpy as np
from ib_insync import IB, Stock, MarketOrder, StopOrder, LimitOrder, Order
from pathlib import Path
import logging
from datetime import datetime
import asyncio
import sys

from atr_stops import calculate_position_size, compute_stop_tp, compute_trailing_amount, fetch_atr
from candidate_ranking import rank_short_candidates, short_conviction, long_conviction
from enriched_record import build_enriched_record
from position_filter import load_current_short_symbols
from regime_detector import detect_market_regime
from risk_config import (
    get_absolute_max_shares,
    get_daily_loss_limit_pct,
    get_max_new_shorts_per_day,
    get_max_position_pct_of_equity,
    get_max_sector_concentration_pct,
    get_max_short_positions,
    get_risk_per_trade_pct,
)
from execution_gates import check_all_gates
from sector_gates import SECTOR_MAP, portfolio_sector_exposure

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).resolve().parent.parent / "logs" / "execute_candidates.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

from paths import TRADING_DIR

_env_path = TRADING_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

WATCHLIST_MULTIMODE_FILE = TRADING_DIR / "watchlist_multimode.json"
CANDIDATES_FILE = TRADING_DIR / "screener_candidates.json"
EXECUTION_LOG = TRADING_DIR / "logs" / "executions.json"
LOSS_TRACKER = TRADING_DIR / "logs" / "daily_loss.json"

EXEC_PARAMS = {
    'paper_trading': True,
}


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


class CandidateExecutor:
    """Execute screener candidates to IBKR"""

    def __init__(self):
        self.ib = IB()
        self.executions = []
        self.daily_loss = 0.0
        self.account_equity = 0.0
        self.effective_equity = 0.0
        self.current_shorts = set()
        self.risk_per_trade_pct = 0.01
        self.max_position_pct = 0.05
        self.absolute_max_shares = 5000
        self.daily_loss_limit_pct = 0.03
        self.max_new_shorts_per_day = None
        self.new_shorts_today = 0
        self.sector_exposure = {}
        self.total_notional = 0.0
        self.max_sector_pct = 30.0
        self.regime = "CHOPPY"

    async def connect(self):
        """Connect to IBKR"""
        try:
            await self.ib.connectAsync(
                os.getenv("IB_HOST", "127.0.0.1"),
                int(os.getenv("IB_PORT", "4001")),
                clientId=101,
            )
            logger.info("Connected to IBKR")
            return True
        except Exception as e:
            logger.error("Connection failed: %s", e)
            try:
                from notifications import notify_executor_error
                notify_executor_error("execute_candidates.py", str(e), context="IB connection")
            except Exception:
                pass
            return False

    def load_candidates(self):
        """Load candidates from screener output. Prefers watchlist_multimode.json, falls back to screener_candidates.json."""
        if WATCHLIST_MULTIMODE_FILE.exists():
            candidates = self._load_from_multimode()
            if candidates is not None:
                return candidates
        if CANDIDATES_FILE.exists():
            return self._load_from_tier_file()
        logger.error(f"No candidates file found: {WATCHLIST_MULTIMODE_FILE} or {CANDIDATES_FILE}")
        return []

    def _load_from_multimode(self):
        """Build candidate list from watchlist_multimode.json (short_opportunities + premium_selling short lists)."""
        try:
            with open(WATCHLIST_MULTIMODE_FILE, 'r') as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            logger.warning(f"Failed to load multimode file: {e}")
            return None
        modes = data.get("modes", {})
        if not isinstance(modes, dict):
            return []
        seen = set()
        candidates = []
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
                    logger.debug(f"Skipping {symbol}: invalid price {price}")
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
        logger.info(f"Loaded {len(candidates)} candidates from watchlist_multimode (short_opportunities + premium_selling)")
        return candidates

    def _load_from_tier_file(self):
        """Fallback: load from legacy screener_candidates.json (tier_2, tier_3)."""
        with open(CANDIDATES_FILE, 'r') as f:
            data = json.load(f)
        tier2 = data.get('tier_2', [])
        tier3 = data.get('tier_3', [])
        candidates = tier2 + tier3
        logger.info(f"Loaded {len(tier2)} Tier 2 + {len(tier3)} Tier 3 candidates from screener_candidates.json")
        return candidates

    def load_daily_loss(self):
        """Load today's cumulative loss"""
        if LOSS_TRACKER.exists():
            with open(LOSS_TRACKER, 'r') as f:
                data = json.load(f)
            today = datetime.now().date().isoformat()
            if data.get('date') == today:
                self.daily_loss = data.get('loss', 0.0)
                logger.info(f"Daily loss so far: ${self.daily_loss:.2f}")
        return self.daily_loss

    def get_account_equity(self):
        """Set net liquidation and effective equity (buying power / leverage) from IB."""
        try:
            from risk_config import get_net_liquidation_and_effective_equity
            net_liq, effective = get_net_liquidation_and_effective_equity(self.ib, TRADING_DIR)
            self.account_equity = net_liq
            self.effective_equity = effective
            return self.account_equity
        except Exception as e:
            logger.warning(f"Could not fetch account equity: {e}")
        return 100000.0

    def check_daily_loss_limit(self):
        """Check if daily loss limit exceeded"""
        equity = self.account_equity or 100000.0
        loss_limit = equity * self.daily_loss_limit_pct
        if self.daily_loss >= loss_limit:
            logger.warning(f"⚠️ DAILY LOSS LIMIT EXCEEDED: ${self.daily_loss:.2f} / ${loss_limit:.2f}")
            logger.warning("Trading halted for remainder of day")
            return False
        return True

    async def execute_candidate(self, candidate):
        """Execute a single candidate"""
        try:
            symbol = candidate['symbol']
            score = candidate['score']
            momentum = candidate['momentum']
            price = candidate['price']

            entry_price = price
            action = 'BUY' if momentum > 0 else 'SELL'

            if action == 'SELL' and symbol in self.current_shorts:
                logger.info(f"Skipping {symbol}: already short")
                return False

            if action == 'SELL' and len(self.current_shorts) >= self.max_short_positions:
                logger.info(f"Skipping {symbol}: would exceed max short positions ({self.max_short_positions})")
                self.executions.append({
                    "symbol": symbol,
                    "type": "SHORT",
                    "source_script": "execute_candidates.py",
                    "status": "SKIPPED",
                    "reason": "max short positions",
                    "timestamp": datetime.now().isoformat(),
                })
                return False

            if action == 'SELL' and self.max_new_shorts_per_day is not None and self.new_shorts_today >= self.max_new_shorts_per_day:
                logger.info(f"Skipping {symbol}: max new shorts per day reached ({self.new_shorts_today}/{self.max_new_shorts_per_day})")
                self.executions.append({
                    "symbol": symbol,
                    "type": "SHORT",
                    "source_script": "execute_candidates.py",
                    "status": "SKIPPED",
                    "reason": "max new shorts per day",
                    "timestamp": datetime.now().isoformat(),
                })
                return False

            equity_net = self.account_equity or 100_000.0
            equity_effective = self.effective_equity or equity_net
            equity = equity_effective
            notional_short = min(equity_effective * self.max_position_pct, price * self.absolute_max_shares) if action == 'SELL' else 0.0
            if action == 'SELL':
                gates_ok, failed_gates = check_all_gates(
                    signal_type='SHORT',
                    symbol=symbol,
                    notional=notional_short,
                    daily_loss=self.daily_loss,
                    account_equity=equity_net,
                    daily_loss_limit_pct=self.daily_loss_limit_pct,
                    sector_exposure=self.sector_exposure,
                    total_notional=self.total_notional,
                    max_sector_pct=self.max_sector_pct,
                    minutes_before_close=60,
                    max_notional_pct_of_equity=0.5,
                    ib=self.ib,
                    account_equity_effective=equity_effective,
                )
                if not gates_ok:
                    reason = "gates: " + ", ".join(failed_gates)
                    logger.info(f"Skipping {symbol}: {reason}")
                    self.executions.append({
                        "symbol": symbol,
                        "type": "SHORT",
                        "source_script": "execute_candidates.py",
                        "status": "SKIPPED",
                        "reason": reason,
                        "timestamp": datetime.now().isoformat(),
                    })
                    return False

            contract = Stock(symbol, 'SMART', 'USD')
            contracts = await self.ib.qualifyContractsAsync(contract)
            if not contracts:
                logger.error(f" ❌ Contract qualification failed")
                return False
            contract = contracts[0]

            atr = fetch_atr(symbol, ib=self.ib)
            side = 'SHORT' if action == 'SELL' else 'LONG'
            conv = short_conviction(candidate) if side == 'SHORT' else long_conviction(candidate)
            qty = calculate_position_size(
                equity, price, atr=atr,
                risk_pct=self.risk_per_trade_pct,
                max_position_pct=self.max_position_pct,
                absolute_max_shares=self.absolute_max_shares,
                conviction=conv,
            )
            logger.info(f"Executing: {symbol} | Score: {score:.3f} | Mom: {momentum:+.2f} | Price: ${price:.2f} | Qty: {qty} | Conv: {conv:.2f}")

            entry_order = MarketOrder(action, qty)
            trade = self.ib.placeOrder(contract, entry_order)

            logger.info(f" 📝 Order ID: {trade.order.orderId} | {action} {qty} @ MKT")
            for _ in range(40):
                await asyncio.sleep(0.5)
                if trade.isDone():
                    break

            fill_status = trade.orderStatus.status
            if fill_status not in ('Filled', 'PartiallyFilled'):
                self.ib.cancelOrder(trade.order)
                logger.warning(f"Order not filled, cancelled: {symbol} {fill_status}")
                self.executions.append({
                    'symbol': symbol,
                    'type': 'SHORT' if action == 'SELL' else 'LONG',
                    'source_script': 'execute_candidates.py',
                    'status': 'CANCELLED',
                    'reason': f'not filled: {fill_status}',
                    'timestamp': datetime.now().isoformat(),
                })
                return False

            filled_qty = int(trade.orderStatus.filled or qty)
            if filled_qty != qty:
                logger.warning("Partial fill on %s %s: requested %d, filled %d", action, symbol, qty, filled_qty)
            entry_fill = float(trade.orderStatus.avgFillPrice or entry_price)
            fill_slippage = abs(entry_fill - price) if entry_fill > 0 else 0.0
            fill_commission = 0.0
            try:
                for fill in trade.fills:
                    cr = getattr(fill, "commissionReport", None)
                    if cr and getattr(cr, "commission", 0):
                        fill_commission += float(cr.commission)
            except Exception:
                pass
            stop_price, profit_price = compute_stop_tp(entry_fill, action, atr=atr)

            trail_amt = compute_trailing_amount(atr=atr, entry_price=entry_fill)
            if action == 'SELL':
                trailing_stop = Order(
                    action='BUY', orderType='TRAIL', totalQuantity=filled_qty,
                    auxPrice=trail_amt, tif='GTC',
                )
                self.ib.placeOrder(contract, trailing_stop)
                self.ib.placeOrder(contract, LimitOrder('BUY', filled_qty, profit_price))
                logger.info(f" Trailing stop: ${trail_amt:.2f} trail | TP: ${profit_price:.2f}")

            execution = build_enriched_record(
                symbol=symbol,
                side=side,
                action=action,
                source_script='execute_candidates.py',
                status=fill_status,
                order_id=trade.order.orderId,
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
                signal_price=price,
                slippage=fill_slippage,
                extra={'score': float(score), 'momentum': float(momentum), 'commission': fill_commission},
            )
            self.executions.append(execution)
            logger.info(f" ✅ EXECUTED: {symbol} | Entry: ${entry_fill:.2f} | Stop: ${stop_price:.2f} | Target: ${profit_price:.2f}")

            if action == 'SELL':
                self.current_shorts.add(symbol)
                self.new_shorts_today += 1
                sector = SECTOR_MAP.get(symbol, "Unknown")
                self.sector_exposure[sector] = self.sector_exposure.get(sector, 0.0) - abs(entry_fill * qty)
                self.total_notional += abs(entry_fill * qty)
            return True

        except Exception as e:
            logger.error(f" ❌ Execution error: {e}")
            return False

    def save_executions(self):
        """Save execution log and write to trade log DB."""
        try:
            from trade_log_db import insert_trade
            for exec_data in self.executions:
                insert_trade(exec_data)
        except Exception as exc:
            logger.warning("trade_log_db insert failed (non-fatal): %s", exc)
        from file_utils import append_jsonl
        for exec_data in self.executions:
            append_jsonl(EXECUTION_LOG, exec_data)
        logger.info("Logged %d executions", len(self.executions))

    async def run(self):
        """Run full execution pipeline"""
        logger.info("=" * 60)
        logger.info("EXECUTION PIPELINE")
        logger.info("=" * 60)
        logger.info(f"Mode: {'PAPER' if EXEC_PARAMS['paper_trading'] else 'LIVE'}")
        logger.info(f"Risk per trade: {self.risk_per_trade_pct*100:.1f}%")
        logger.info(f"Max position: {self.max_position_pct*100:.1f}% of equity, abs max {self.absolute_max_shares} shares")
        logger.info("Stops: ATR-based trailing")
        logger.info("=" * 60)

        if not await self.connect():
            return False

        try:
            from agents.risk_monitor import is_kill_switch_active
            if is_kill_switch_active():
                logger.warning("Kill switch is active. No executions.")
                self.ib.disconnect()
                return False
        except ImportError:
            pass

        self.current_shorts = load_current_short_symbols(TRADING_DIR, self.ib)
        self.max_short_positions = get_max_short_positions(TRADING_DIR)
        self.risk_per_trade_pct = get_risk_per_trade_pct(TRADING_DIR)
        self.max_position_pct = get_max_position_pct_of_equity(TRADING_DIR, side="short")
        self.absolute_max_shares = get_absolute_max_shares(TRADING_DIR)
        self.daily_loss_limit_pct = get_daily_loss_limit_pct(TRADING_DIR)
        self.max_new_shorts_per_day = get_max_new_shorts_per_day(TRADING_DIR)
        self.new_shorts_today = _count_new_shorts_today(EXECUTION_LOG)
        self.sector_exposure, self.total_notional = portfolio_sector_exposure(self.ib)
        self.max_sector_pct = get_max_sector_concentration_pct(TRADING_DIR)

        self.regime = detect_market_regime(ib=self.ib)
        logger.info(f"Market regime: {self.regime}")

        candidates = self.load_candidates()
        self.load_daily_loss()
        self.get_account_equity()

        logger.info(f"Account equity: ${self.account_equity:.2f}")

        if not self.check_daily_loss_limit():
            logger.warning("Daily loss limit exceeded. No executions.")
            self.ib.disconnect()
            return False

        if not candidates:
            logger.info("No candidates to execute")
            self.ib.disconnect()
            return True

        candidates = rank_short_candidates(candidates)
        logger.info(f"Executing top {min(5, len(candidates))} of {len(candidates)} candidates (ranked by conviction)...")
        logger.info("")

        for candidate in candidates[:5]:
            await self.execute_candidate(candidate)
            await asyncio.sleep(1)

        self.save_executions()

        logger.info("")
        logger.info("=" * 60)
        logger.info(f"EXECUTION COMPLETE: {len(self.executions)} trades")
        logger.info("=" * 60)

        self.ib.disconnect()
        return True


async def main():
    from file_utils import job_lock
    with job_lock("execute_candidates", TRADING_DIR / ".pids") as acquired:
        if not acquired:
            logger.warning("execute_candidates already running (lock exists). Skipping to prevent double-execution.")
            return
        executor = CandidateExecutor()
        await executor.run()


if __name__ == "__main__":
    asyncio.run(main())
