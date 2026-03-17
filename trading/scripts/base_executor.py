"""
Shared base class for OrderRouter-based equity executors.

Handles the complete lifecycle that every executor repeats:
    connect → OrderRouter startup → kill switch → drawdown breaker →
    regime detection → account/risk state → daily loss check →
    execute() → save executions → shutdown → disconnect

Subclasses set class attributes for identification, then override
`execute()` with the strategy-specific candidate loop.  All shared
state (equity, risk params, sector exposure, etc.) is available on
`self` when `execute()` runs.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from ib_insync import IB

from execution_gates import check_all_gates
from live_allocation import get_effective_equity as _apply_alloc
from order_router import OrderRouter
from regime_detector import detect_market_regime
from risk_config import (
    get_absolute_max_shares,
    get_daily_loss_limit_pct,
    get_max_position_pct_of_equity,
    get_max_sector_concentration_pct,
    get_net_liquidation_and_effective_equity,
    get_outside_rth_stop,
    get_outside_rth_take_profit,
    get_risk_per_trade_pct,
)
from sector_gates import portfolio_sector_exposure

from paths import TRADING_DIR

_env_path = TRADING_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().split("\n"):
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())


class BaseExecutor(ABC):
    """Template for OrderRouter-based equity executors.

    Subclasses must define the class attributes below and implement
    ``execute()``.  Everything else is handled by the base lifecycle.
    """

    # --- Subclass must set these ---
    script_name: str
    """Filename used in logs and enriched records (e.g. ``"execute_longs.py"``)."""

    log_file_stem: str
    """Base name for the log file (e.g. ``"execute_longs"``)."""

    state_store_name: str
    """Filename inside ``logs/`` for the per-executor order state (e.g. ``"order_state_longs.jsonl"``)."""

    client_id: int
    """IBKR TWS/Gateway clientId for this executor."""

    job_lock_name: str
    """Name used by ``file_utils.job_lock`` to prevent concurrent runs."""

    # --- Optional overrides ---
    position_side: str = "long"
    """Side passed to ``get_max_position_pct_of_equity`` (``"long"`` or ``"short"``)."""

    apply_allocation: bool = True
    """Whether to apply the live-allocation overlay to net_liq / effective_equity."""

    use_drawdown_breaker: bool = True
    """Whether to check the drawdown circuit-breaker before executing."""

    connect_retries: int = 1
    """Number of IB connection attempts (useful for executors that retry on timeout)."""

    connect_timeout: int = 30
    """Base timeout (seconds) for each connection attempt."""

    # ------------------------------------------------------------------
    # Instance state (populated during lifecycle, available in execute())
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        self.ib = IB()
        self.router: OrderRouter | None = None
        self.executions: list[dict] = []

        self.net_liq: float = 0.0
        self.effective_equity: float = 0.0
        self.daily_loss: float = 0.0
        self.regime: str = "CHOPPY"
        self.sector_exposure: dict[str, float] = {}
        self.total_notional: float = 0.0

        self.risk_per_trade_pct: float = 0.01
        self.max_position_pct: float = 0.05
        self.absolute_max_shares: int = 5000
        self.daily_loss_limit_pct: float = 0.03
        self.max_sector_pct: float = 30.0

        self._logger = self._setup_logger()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def log(self) -> logging.Logger:
        return self._logger

    @property
    def state_store_path(self) -> Path:
        return TRADING_DIR / "logs" / self.state_store_name

    @property
    def execution_log_path(self) -> Path:
        return TRADING_DIR / "logs" / "executions.json"

    @property
    def loss_tracker_path(self) -> Path:
        return TRADING_DIR / "logs" / "daily_loss.json"

    # ------------------------------------------------------------------
    # Template entry point
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Acquire a job-lock then execute the full lifecycle."""
        from file_utils import job_lock

        with job_lock(self.job_lock_name, TRADING_DIR / ".pids") as acquired:
            if not acquired:
                self.log.warning(
                    "%s already running (lock exists). Skipping to prevent double-execution.",
                    self.script_name,
                )
                return
            await self._run()

    async def _run(self) -> None:
        mode = os.getenv("TRADING_MODE", "paper")
        if mode == "live":
            self.log.warning("LIVE TRADING MODE — real money at risk")
        self.log.info("=== %s [%s] ===", self.script_name.upper(), mode.upper())

        if not await self._connect():
            return

        self.router = OrderRouter(self.ib, state_store_path=self.state_store_path)

        try:
            await self.router.startup()

            if self._is_kill_switch_active():
                return
            if self.use_drawdown_breaker and self._is_drawdown_breaker_active():
                return

            self.regime = detect_market_regime()
            self.log.info("Market regime: %s", self.regime)

            self._load_account_state()
            self._load_risk_config()

            if not self._check_daily_loss_limit():
                return

            await self.execute()
            self._save_executions()
        finally:
            if self.router is not None:
                await self.router.shutdown()
            self.ib.disconnect()

    # ------------------------------------------------------------------
    # Abstract — implement in subclass
    # ------------------------------------------------------------------

    @abstractmethod
    async def execute(self) -> None:
        """Run the strategy-specific execution logic.

        When this is called, ``self.ib`` is connected, ``self.router`` is
        started, safety gates have passed, and account/risk state is loaded
        onto ``self``.  Append enriched records to ``self.executions`` and
        the base class will persist them after ``execute()`` returns.
        """
        ...

    # ------------------------------------------------------------------
    # Shared helpers (available in execute())
    # ------------------------------------------------------------------

    def current_long_symbols(self) -> set[str]:
        """Return the set of stock symbols currently held long."""
        out: set[str] = set()
        try:
            for pos in self.ib.positions():
                if getattr(pos.contract, "secType", "") != "STK":
                    continue
                if getattr(pos, "position", 0) > 0:
                    sym = getattr(pos.contract, "symbol", "")
                    if isinstance(sym, str) and sym.strip():
                        out.add(sym.strip().upper())
        except Exception as e:
            self.log.warning("Could not fetch positions: %s", e)
        return out

    def check_gates(
        self,
        signal_type: str,
        symbol: str,
        notional: float,
        **overrides: Any,
    ) -> tuple[bool, list[str]]:
        """Run the unified risk gate check, defaulting to ``self.*`` state."""
        return check_all_gates(
            signal_type=signal_type,
            symbol=symbol,
            notional=notional,
            daily_loss=overrides.get("daily_loss", self.daily_loss),
            account_equity=overrides.get("account_equity", self.net_liq),
            daily_loss_limit_pct=overrides.get("daily_loss_limit_pct", self.daily_loss_limit_pct),
            sector_exposure=overrides.get("sector_exposure", self.sector_exposure),
            total_notional=overrides.get("total_notional", self.total_notional),
            max_sector_pct=overrides.get("max_sector_pct", self.max_sector_pct),
            minutes_before_close=overrides.get("minutes_before_close", 60),
            max_notional_pct_of_equity=overrides.get("max_notional_pct_of_equity", 0.5),
            ib=self.ib,
            account_equity_effective=overrides.get(
                "account_equity_effective", self.effective_equity,
            ),
        )

    def notify_fill(
        self,
        side: str,
        symbol: str,
        entry_price: float,
        filled_qty: int,
        stop: float | None = None,
        tp: float | None = None,
        trail: float | None = None,
    ) -> None:
        """Best-effort Telegram notification for a filled trade."""
        try:
            from notifications import notify_info

            detail = f"Entry: ${entry_price:.2f} | Qty: {filled_qty}"
            if stop is not None:
                detail += f" | Stop: ${stop:.2f}"
            if tp is not None:
                detail += f" | TP: ${tp:.2f}"
            if trail is not None:
                detail += f" | Trail: ${trail:.2f}"
            notify_info(f"<b>Trade Filled</b>: {side} {symbol}\n{detail}")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Private lifecycle helpers
    # ------------------------------------------------------------------

    def _setup_logger(self) -> logging.Logger:
        log_dir = TRADING_DIR / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        name = f"executor.{self.log_file_stem}"
        lgr = logging.getLogger(name)
        if not lgr.handlers:
            lgr.setLevel(logging.INFO)
            fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            fh = logging.FileHandler(log_dir / f"{self.log_file_stem}.log")
            fh.setFormatter(fmt)
            sh = logging.StreamHandler()
            sh.setFormatter(fmt)
            lgr.addHandler(fh)
            lgr.addHandler(sh)
        return lgr

    async def _connect(self) -> bool:
        host = os.getenv("IB_HOST", "127.0.0.1")
        port = int(os.getenv("IB_PORT", "4001"))
        last_err: Exception | None = None

        for attempt in range(1, self.connect_retries + 1):
            try:
                timeout = self.connect_timeout + (attempt - 1) * 10
                await self.ib.connectAsync(
                    host, port, clientId=self.client_id, timeout=timeout,
                )
                self.log.info("Connected to IBKR (clientId=%d)", self.client_id)
                return True
            except asyncio.TimeoutError:
                last_err = asyncio.TimeoutError()
                if attempt < self.connect_retries:
                    self.log.warning(
                        "IB connect attempt %d timed out; retrying in 5s...", attempt,
                    )
                    await asyncio.sleep(5)
            except Exception as e:
                last_err = e
                break

        self.log.error("Connection failed: %s", last_err)
        try:
            from notifications import notify_executor_error

            notify_executor_error(
                self.script_name, str(last_err), context="IB connection",
            )
        except Exception:
            pass
        return False

    def _is_kill_switch_active(self) -> bool:
        """Returns ``True`` if the kill switch is active (should abort)."""
        try:
            from agents.risk_monitor import is_kill_switch_active

            if is_kill_switch_active():
                self.log.warning("Kill switch is active. No executions.")
                return True
        except ImportError:
            pass
        return False

    def _is_drawdown_breaker_active(self) -> bool:
        """Returns ``True`` if the circuit-breaker has halted new entries."""
        try:
            from drawdown_circuit_breaker import is_entries_halted

            if is_entries_halted():
                self.log.warning("Drawdown breaker tier 2+ — new entries halted.")
                return True
        except ImportError:
            pass
        return False

    def _load_account_state(self) -> None:
        raw_nlv, raw_eq = get_net_liquidation_and_effective_equity(
            self.ib, TRADING_DIR,
        )
        if self.apply_allocation:
            self.net_liq = _apply_alloc(raw_nlv)
            self.effective_equity = _apply_alloc(raw_eq)
        else:
            self.net_liq = raw_nlv
            self.effective_equity = raw_eq

        self.sector_exposure, self.total_notional = portfolio_sector_exposure(
            self.ib,
        )

        self.daily_loss = 0.0
        if self.loss_tracker_path.exists():
            try:
                data = json.loads(self.loss_tracker_path.read_text())
                if data.get("date") == datetime.now().date().isoformat():
                    self.daily_loss = float(data.get("loss", 0) or 0)
            except (OSError, ValueError, TypeError):
                pass

        self.log.info(
            "Net liq $%s | Effective $%s | Daily loss $%.2f",
            f"{self.net_liq:,.0f}",
            f"{self.effective_equity:,.0f}",
            self.daily_loss,
        )

    def _load_risk_config(self) -> None:
        self.risk_per_trade_pct = get_risk_per_trade_pct(TRADING_DIR)
        self.max_position_pct = get_max_position_pct_of_equity(
            TRADING_DIR, side=self.position_side,
        )
        self.absolute_max_shares = get_absolute_max_shares(TRADING_DIR)
        self.daily_loss_limit_pct = get_daily_loss_limit_pct(TRADING_DIR)
        self.max_sector_pct = get_max_sector_concentration_pct(TRADING_DIR)

    def _check_daily_loss_limit(self) -> bool:
        limit = self.net_liq * self.daily_loss_limit_pct
        if self.daily_loss >= limit:
            self.log.warning(
                "Daily loss limit exceeded: $%.2f / $%.2f — trading halted",
                self.daily_loss,
                limit,
            )
            return False
        return True

    def _save_executions(self) -> None:
        if not self.executions:
            return
        try:
            from trade_log_db import insert_trade

            for e in self.executions:
                insert_trade(e)
        except Exception as exc:
            self.log.warning("trade_log_db insert failed (non-fatal): %s", exc)

        from file_utils import append_jsonl

        for e in self.executions:
            append_jsonl(self.execution_log_path, e)
        self.log.info(
            "Logged %d executions to %s",
            len(self.executions),
            self.execution_log_path,
        )
