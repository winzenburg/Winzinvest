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
from regime_detector import detect_market_regime, get_macro_size_multiplier
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
        self.macro_size_multiplier: float = 1.0
        self.sector_exposure: dict[str, float] = {}
        self.total_notional: float = 0.0

        self.risk_per_trade_pct: float = 0.01
        self.max_position_pct: float = 0.05
        self.absolute_max_shares: int = 5000
        self.daily_loss_limit_pct: float = 0.03
        self.max_sector_pct: float = 30.0

        # PM margin state (populated in _load_account_state)
        self.excess_liquidity: float = 0.0
        self.margin_budget_pct: float = 0.08

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
    # PM margin helpers
    # ------------------------------------------------------------------

    def get_pm_max_shares(self, symbol: str, action: str) -> int | None:
        """Query IB for PM-aware maximum shares within the margin budget.

        Returns None if PM data is unavailable (callers should use static caps).
        """
        if self.excess_liquidity <= 0:
            return None
        try:
            from pm_margin import compute_pm_max_shares
            return compute_pm_max_shares(
                self.ib, symbol, action,
                excess_liquidity=self.excess_liquidity,
                margin_budget_pct=self.margin_budget_pct,
            )
        except ImportError:
            return None

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

        self.router = self._create_router()

        try:
            await self.router.startup()

            if self._is_kill_switch_active():
                return
            if self.use_drawdown_breaker and self._is_drawdown_breaker_active():
                return

            self.regime = detect_market_regime()
            self.macro_size_multiplier = get_macro_size_multiplier()
            self.log.info(
                "Market regime: %s | Macro size multiplier: %.2f×",
                self.regime,
                self.macro_size_multiplier,
            )

            self._load_account_state()
            self._load_risk_config()

            if not self._check_daily_loss_limit():
                return

            await self.execute()
        finally:
            self._save_executions()
            if self.router is not None:
                await self.router.shutdown()
            self.ib.disconnect()

    # ------------------------------------------------------------------
    # Router creation hook (override for custom timeout, etc.)
    # ------------------------------------------------------------------

    def _create_router(self) -> OrderRouter:
        """Create the OrderRouter for this executor.

        Override in subclasses that need non-default settings (e.g. longer
        fill timeout for pairs trades).
        """
        return OrderRouter(self.ib, state_store_path=self.state_store_path)

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

    async def submit_protective_with_retry(
        self,
        parent_result: Any,
        follow_ups: list[Any],
        symbol: str,
        max_retries: int = 2,
    ) -> list[Any]:
        """Submit protective orders with retry and critical alert on total failure.

        If any protective order fails after all retries, a critical Telegram alert
        is sent so the user knows a position is unprotected.
        """
        assert self.router is not None
        results = await self.router.submit_protective_orders(
            parent_result=parent_result, follow_ups=follow_ups,
        )
        for i, pr in enumerate(results):
            if pr.success:
                continue
            # Retry failed protective orders
            for attempt in range(1, max_retries + 1):
                self.log.warning(
                    "Protective order %d/%d failed for %s (attempt %d): %s — retrying",
                    i + 1, len(results), symbol, attempt, pr.error,
                )
                await asyncio.sleep(2 * attempt)
                retry_results = await self.router.submit_protective_orders(
                    parent_result=parent_result, follow_ups=[follow_ups[i]],
                )
                if retry_results and retry_results[0].success:
                    results[i] = retry_results[0]
                    break
            else:
                self.log.critical(
                    "UNPROTECTED POSITION: %s — protective order failed after %d retries",
                    symbol, max_retries,
                )
                try:
                    from notifications import notify_critical
                    notify_critical(
                        "Unprotected Position",
                        f"<b>{symbol}</b> — protective order (stop/TP) failed after "
                        f"{max_retries} retries.\nManual intervention required.",
                    )
                except Exception:
                    pass
        return results

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
        """Best-effort Telegram notification for a filled trade.

        Gated on the ``trade_executed`` event toggle in notification_prefs.json.
        """
        try:
            from notifications import is_event_enabled, notify_info

            if not is_event_enabled("trade_executed"):
                return

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
        """Returns ``True`` if the kill switch is active (should abort).

        Uses ``kill_switch_guard`` which is **fail-closed**: corrupt or
        unreadable ``kill_switch.json`` → assume active → block trading.
        """
        try:
            from kill_switch_guard import kill_switch_active

            if kill_switch_active():
                self.log.warning("Kill switch is active (fail-closed). No executions.")
                return True
        except ImportError:
            self.log.warning("kill_switch_guard not importable — treating as active (fail-closed)")
            return True
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

        # PM margin: query ExcessLiquidity and margin budget once per run
        try:
            from pm_margin import get_excess_liquidity, clear_cache
            from risk_config import get_margin_budget_pct_per_trade
            clear_cache()
            el = get_excess_liquidity(self.ib)
            if el is not None and el > 0:
                self.excess_liquidity = el
            self.margin_budget_pct = get_margin_budget_pct_per_trade(TRADING_DIR)
            self.log.info(
                "PM state: ExcessLiquidity $%s | margin_budget_pct %.0f%%",
                f"{self.excess_liquidity:,.0f}", self.margin_budget_pct * 100,
            )
        except ImportError:
            pass

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
        base_risk_pct = get_risk_per_trade_pct(TRADING_DIR, side=self.position_side)
        base_position_pct = get_max_position_pct_of_equity(
            TRADING_DIR, side=self.position_side,
        )

        # Drawdown breaker Tier 1 scaling (0.5× at Tier 1, 1.0× otherwise).
        # Tier 2+ already halted execution in _is_drawdown_breaker_active().
        breaker_scale = 1.0
        try:
            from drawdown_circuit_breaker import get_position_scale
            breaker_scale = get_position_scale()
        except ImportError:
            pass

        # Multiplicative dampeners: macro regime × drawdown breaker × Benedict intraday tier
        benedict_scale = self._get_benedict_scale()
        combined_scale = self.macro_size_multiplier * breaker_scale * benedict_scale
        self.risk_per_trade_pct = base_risk_pct * combined_scale
        self.max_position_pct = base_position_pct * combined_scale

        if combined_scale < 1.0:
            self.log.info(
                "Position sizing dampened: macro=%.2f× breaker=%.2f× benedict=%.2f× → combined=%.2f× "
                "(risk_per_trade %.2f%% → %.2f%%, max_position %.2f%% → %.2f%%)",
                self.macro_size_multiplier, breaker_scale, benedict_scale, combined_scale,
                base_risk_pct * 100, self.risk_per_trade_pct * 100,
                base_position_pct * 100, self.max_position_pct * 100,
            )
        self.absolute_max_shares = get_absolute_max_shares(TRADING_DIR)
        self.daily_loss_limit_pct = get_daily_loss_limit_pct(TRADING_DIR)
        self.max_sector_pct = get_max_sector_concentration_pct(TRADING_DIR)

    # ------------------------------------------------------------------
    # Brandt daily trade budget helpers
    # ------------------------------------------------------------------

    def _load_brandt_budget_config(self) -> tuple[int, int, Path]:
        """Return (max_longs, max_shorts, state_file_path) from risk.json."""
        try:
            import json as _j
            _risk = _j.loads((TRADING_DIR / "risk.json").read_text())
            bcs = _risk.get("brandt_conviction_sizing", {})
            budget = bcs.get("daily_budget", {})
            max_l = int(budget.get("max_new_longs_per_day", 4))
            max_s = int(budget.get("max_new_shorts_per_day", 3))
            state_rel = budget.get("state_file", "logs/daily_trade_budget.json")
            state_path = TRADING_DIR / state_rel
        except Exception:
            max_l, max_s = 4, 3
            state_path = TRADING_DIR / "logs" / "daily_trade_budget.json"
        return max_l, max_s, state_path

    def _read_budget_state(self, state_path: Path) -> dict:
        """Load today's budget state, resetting if it's a new day."""
        today = datetime.now().date().isoformat()
        try:
            if state_path.exists():
                data = json.loads(state_path.read_text())
                if data.get("date") == today:
                    return data
        except Exception:
            pass
        return {"date": today, "longs_entered": 0, "shorts_entered": 0}

    def _write_budget_state(self, state_path: Path, state: dict) -> None:
        """Persist updated budget state atomically."""
        try:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(state, indent=2))
        except Exception as exc:
            self.log.warning("Could not write budget state: %s", exc)

    def check_daily_trade_budget(self, side: str) -> bool:
        """Return True if there is remaining daily budget for a new entry.

        Peter Brandt: limit new entries per day per side to force selectivity.
        When the screener overflows, only top-conviction candidates enter.
        Candidates are already sorted highest-conviction-first by rank_*_candidates,
        so the first N to pass gates are always the best available that day.
        """
        max_l, max_s, state_path = self._load_brandt_budget_config()
        state = self._read_budget_state(state_path)
        if side.upper() in ("LONG", "BUY"):
            remaining = max_l - int(state.get("longs_entered", 0))
        else:
            remaining = max_s - int(state.get("shorts_entered", 0))
        if remaining <= 0:
            self.log.info(
                "Brandt daily budget exhausted for %s side (%d/%d) — deferring lower-conviction candidates",
                side,
                (max_l if side.upper() in ("LONG", "BUY") else max_s) - remaining,
                max_l if side.upper() in ("LONG", "BUY") else max_s,
            )
            return False
        return True

    def consume_daily_trade_budget(self, side: str) -> None:
        """Increment the daily entry count after a successful fill."""
        _, _, state_path = self._load_brandt_budget_config()
        state = self._read_budget_state(state_path)
        if side.upper() in ("LONG", "BUY"):
            state["longs_entered"] = int(state.get("longs_entered", 0)) + 1
        else:
            state["shorts_entered"] = int(state.get("shorts_entered", 0)) + 1
        self._write_budget_state(state_path, state)
        self.log.info(
            "Brandt budget consumed: longs=%d shorts=%d",
            state.get("longs_entered", 0),
            state.get("shorts_entered", 0),
        )

    # ------------------------------------------------------------------
    # Bobblehead early-exit helpers (Breitstein / Goedeker)
    # ------------------------------------------------------------------

    def _load_bobblehead_config(self) -> dict:
        """Load bobblehead exit settings from risk.json → bobblehead_exit."""
        defaults = {
            "enabled": True,
            "days_window": 2,
            "min_loss_atr_fraction": 0.35,
            "apply_to_sides": ["LONG"],
        }
        try:
            import json as _j
            _risk = _j.loads((TRADING_DIR / "risk.json").read_text())
            cfg = _risk.get("bobblehead_exit", {})
            defaults.update(cfg)
        except Exception:
            pass
        return defaults

    def should_bobblehead_exit(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        current_price: float,
        atr_at_entry: float,
        holding_days: int,
    ) -> bool:
        """Return True if a position qualifies for an early bobblehead exit.

        Lance Breitstein + Phil Goedeker (Next Generation): a properly-entered
        trade confirms quickly. If it's still below entry after 'days_window'
        days AND has drifted down by at least 'min_loss_atr_fraction' × ATR,
        it is a failed setup — exit early rather than holding to the hard stop.

        This preserves capital and position slots for higher-quality setups.
        """
        cfg = self._load_bobblehead_config()
        if not cfg.get("enabled", True):
            return False
        if side.upper() not in [s.upper() for s in cfg.get("apply_to_sides", ["LONG"])]:
            return False
        if holding_days < int(cfg.get("days_window", 2)):
            return False
        if entry_price <= 0 or atr_at_entry <= 0:
            return False

        min_loss_atr = float(cfg.get("min_loss_atr_fraction", 0.35))

        if side.upper() in ("LONG", "BUY"):
            if current_price >= entry_price:
                return False   # position is profitable — do not exit
            drift = entry_price - current_price
        else:
            if current_price <= entry_price:
                return False
            drift = current_price - entry_price

        if drift < atr_at_entry * min_loss_atr:
            return False   # too small a drift — could be normal noise

        self.log.info(
            "BOBBLEHEAD EXIT: %s %s — still below entry after %d days "
            "(entry=%.2f, now=%.2f, drift=%.2f vs %.2f×ATR threshold)",
            symbol, side, holding_days,
            entry_price, current_price,
            drift, min_loss_atr,
        )
        return True

    def _get_benedict_scale(self) -> float:
        """Larry Benedict tiered position sizing based on today's P&L.

        Unlike the binary kill switch (halts at 3%), this applies a smooth
        size reduction as losses accumulate intraday:
          - loss < tier_1: full size (1.0×)
          - tier_1 ≤ loss < tier_2: 50% size
          - loss ≥ tier_2: 25% size (circuit breaker kills at 3%)

        Thresholds are read from risk.json → drawdown_sizing so they can be
        tuned without a code change. Defaults mirror the original suggestion.
        """
        if self.net_liq <= 0 or self.daily_loss <= 0:
            return 1.0
        try:
            import json as _json
            _risk = _json.loads((TRADING_DIR / "risk.json").read_text())
            ds = _risk.get("drawdown_sizing", {})
            tier1_pct = float(ds.get("tier_1_loss_pct", 0.01))
            tier1_factor = float(ds.get("tier_1_size_factor", 0.50))
            tier2_pct = float(ds.get("tier_2_loss_pct", 0.02))
            tier2_factor = float(ds.get("tier_2_size_factor", 0.25))
        except Exception:
            tier1_pct, tier1_factor = 0.01, 0.50
            tier2_pct, tier2_factor = 0.02, 0.25

        loss_pct = self.daily_loss / self.net_liq
        if loss_pct >= tier2_pct:
            self.log.warning(
                "Benedict tier 2: daily loss %.2f%% ≥ %.0f%% → sizing at %.0f%%",
                loss_pct * 100, tier2_pct * 100, tier2_factor * 100,
            )
            return tier2_factor
        if loss_pct >= tier1_pct:
            self.log.info(
                "Benedict tier 1: daily loss %.2f%% ≥ %.0f%% → sizing at %.0f%%",
                loss_pct * 100, tier1_pct * 100, tier1_factor * 100,
            )
            return tier1_factor
        return 1.0

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
