"""
Order router — the single entry point for all order submission.

Wires together contract_cache → order_factory → order_state_store →
ib.placeOrder → event-driven fill tracking.  Executors call router.submit()
instead of touching ib_insync directly.

This is one of the few modules permitted to import ib_insync.

Design:
  - Event-driven fill tracking via ib_insync Trade callbacks (no polling).
  - Mandatory reconciliation before the first submission.
  - Bounded retries with backoff.
  - Idempotent: duplicate intent_ids are rejected before hitting the broker.
  - Structured logging of every broker interaction.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable, Dict, List, Optional, Union

from ib_insync import IB, Trade

from contract_cache import ContractCache, ResolvedContract
from execution_policy import (
    ExecutionPolicy,
    OrderIntent,
    OrderStatus,
    is_terminal,
)
from order_factory import BuiltOrder, build_orders
from order_state_store import OrderStateStore
from reconciliation_service import ReconciliationReport, ReconciliationService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_FILL_TIMEOUT_SECONDS = 15.0
DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_BACKOFF_SECONDS = 1.0


# ---------------------------------------------------------------------------
# Submit result
# ---------------------------------------------------------------------------


FillCallback = Callable[["str", "SubmitResult"], Union[None, Awaitable[None]]]
"""Sync or async callback: (intent_id, SubmitResult) → None."""


@dataclass
class SubmitResult:
    """Outcome of a router.submit() call."""

    success: bool
    intent_id: str
    broker_order_id: Optional[int] = None
    status: Optional[OrderStatus] = None
    filled_qty: int = 0
    avg_fill_price: float = 0.0
    total_commission: float = 0.0
    error: Optional[str] = None

    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED

    @property
    def is_partial(self) -> bool:
        return self.status == OrderStatus.PARTIALLY_FILLED


# ---------------------------------------------------------------------------
# Order router
# ---------------------------------------------------------------------------


class OrderRouter:
    """Single entry point for all order submission and lifecycle management.

    Usage::

        router = OrderRouter(ib, state_store_path=LOGS_DIR / "order_state.jsonl")
        await router.startup()  # reconcile before anything else

        result = await router.submit(intent)
        if result.success:
            logger.info("Filled %d @ %.2f", result.filled_qty, result.avg_fill_price)

        # On shutdown:
        await router.shutdown()
    """

    def __init__(
        self,
        ib: IB,
        state_store_path: Optional[Path] = None,
        fill_timeout: float = DEFAULT_FILL_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_backoff: float = DEFAULT_RETRY_BACKOFF_SECONDS,
    ) -> None:
        self._ib = ib
        self._contract_cache = ContractCache(ib)
        self._state_store = OrderStateStore(state_store_path)
        self._reconciliation = ReconciliationService(ib, self._state_store)

        self._fill_timeout = fill_timeout
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff

        self._reconciled = False
        self._active_trades: Dict[str, Trade] = {}
        self._fill_events: Dict[str, asyncio.Event] = {}
        self._on_fill_callbacks: List[FillCallback] = []

    # -- Public properties -------------------------------------------------

    @property
    def contract_cache(self) -> ContractCache:
        """Expose contract cache for callers that need pre-resolution."""
        return self._contract_cache

    @property
    def state_store(self) -> OrderStateStore:
        """Expose state store for callers that need to query order state."""
        return self._state_store

    @property
    def is_reconciled(self) -> bool:
        return self._reconciled

    # -- Lifecycle ---------------------------------------------------------

    async def startup(self) -> ReconciliationReport:
        """Reconcile with broker before accepting any new orders.

        MUST be called after connecting to IB and before the first submit().
        """
        logger.info("OrderRouter startup: running reconciliation...")
        report = await self._reconciliation.reconcile()
        self._reconciled = True
        logger.info(
            "OrderRouter ready: reconciled=%s broker_orders=%d positions=%d",
            report.is_clean, report.broker_open_orders, report.broker_positions,
        )
        return report

    async def shutdown(self) -> None:
        """Clean up active trade subscriptions."""
        self._fill_events.clear()
        self._active_trades.clear()
        logger.info("OrderRouter shutdown complete")

    def on_fill(self, callback: FillCallback) -> None:
        """Register a callback invoked when any order reaches a terminal state.

        The callback receives ``(intent_id, SubmitResult)`` and may be either
        a regular function or an ``async def`` coroutine — both are supported.
        Async callbacks are scheduled on the running event loop.
        """
        self._on_fill_callbacks.append(callback)

    # -- Follow-up (protective) orders -------------------------------------

    async def submit_protective_orders(
        self,
        parent_result: SubmitResult,
        follow_ups: List[OrderIntent],
        resolved: Optional[ResolvedContract] = None,
    ) -> List[SubmitResult]:
        """Submit a batch of follow-up orders after a parent fill.

        Typical use: place trailing stop + take-profit after an entry fill.
        Each follow-up is submitted with ``wait_for_fill=False`` because
        protective orders are typically GTC and fill asynchronously.

        Returns one ``SubmitResult`` per follow-up intent.
        """
        if not parent_result.is_filled and not parent_result.is_partial:
            logger.warning(
                "submit_protective_orders called for non-filled parent %s (status=%s); skipping",
                parent_result.intent_id,
                parent_result.status.value if parent_result.status else "None",
            )
            return []

        results: List[SubmitResult] = []
        for intent in follow_ups:
            res = await self.submit(intent, resolved=resolved, wait_for_fill=False)
            results.append(res)
            if not res.success:
                logger.error(
                    "Protective order failed for %s: %s",
                    intent["intent_id"], res.error,
                )
        return results

    # -- Submit (the main API) ---------------------------------------------

    async def submit(
        self,
        intent: OrderIntent,
        resolved: Optional[ResolvedContract] = None,
        bid: Optional[float] = None,
        ask: Optional[float] = None,
        wait_for_fill: bool = True,
    ) -> SubmitResult:
        """Submit an order intent through the full execution pipeline.

        Steps:
          1. Enforce reconciliation gate.
          2. Resolve contract (if not provided).
          3. Check idempotency (reject duplicate active intents).
          4. Register in state store.
          5. Build IBKR orders via order_factory.
          6. Place orders with broker.
          7. Attach event-driven fill tracking.
          8. Optionally wait for fill (bounded timeout).

        Parameters
        ----------
        intent : OrderIntent
            The strategy's declared intent (from build_intent()).
        resolved : ResolvedContract, optional
            Pre-resolved contract.  If None, the router resolves it via
            contract_cache.
        bid, ask : float, optional
            Current bid/ask for price-aware policies.
        wait_for_fill : bool
            If True, blocks until filled, cancelled, or timeout.  If False,
            returns immediately after submission.

        Returns
        -------
        SubmitResult
        """
        intent_id = intent["intent_id"]

        if not self._reconciled:
            logger.error("submit() called before startup reconciliation; rejecting %s", intent_id)
            return SubmitResult(
                success=False, intent_id=intent_id,
                error="Router not reconciled — call startup() first",
            )

        existing = self._state_store.get(intent_id)
        if existing is not None:
            logger.warning("Duplicate intent %s (status=%s); rejecting",
                           intent_id, existing.status.value)
            return SubmitResult(
                success=False, intent_id=intent_id,
                status=existing.status,
                error="Duplicate intent (already submitted or completed)",
            )

        if resolved is None:
            if intent.get("sec_type") == "OPT":
                resolved = await self._contract_cache.resolve_option(
                    symbol=intent["symbol"],
                    expiry=intent["expiry"],
                    strike=intent["strike"],
                    right=intent["right"],
                )
            else:
                resolved = await self._contract_cache.resolve(intent["symbol"])
            if resolved is None:
                err = f"Contract resolution failed for {intent['symbol']}"
                logger.error(err)
                return SubmitResult(success=False, intent_id=intent_id, error=err)

        self._state_store.create(
            intent_id=intent_id,
            symbol=intent["symbol"],
            side=intent["side"],
            quantity=intent["quantity"],
            policy=intent["policy"].value if isinstance(intent["policy"], ExecutionPolicy) else str(intent["policy"]),
            source_script=intent["source_script"],
            metadata=intent.get("metadata"),
        )

        return await self._place_with_retry(intent, resolved, bid, ask, wait_for_fill)

    # -- Cancel ------------------------------------------------------------

    async def cancel(self, intent_id: str) -> bool:
        """Cancel an active order by intent_id.

        Returns True if the cancel was sent or the order was already terminal.
        """
        entry = self._state_store.get(intent_id)
        if entry is None:
            logger.warning("cancel: unknown intent %s", intent_id)
            return False

        if is_terminal(entry.status):
            logger.debug("cancel: intent %s already terminal (%s)", intent_id, entry.status.value)
            return True

        trade = self._active_trades.get(intent_id)
        if trade is None:
            logger.warning("cancel: no active trade for %s; marking cancelled locally", intent_id)
            self._state_store.mark_cancelled(intent_id)
            return True

        try:
            self._ib.cancelOrder(trade.order)
            logger.info("Cancel sent for %s (broker_id=%s)", intent_id, entry.broker_order_id)
            # The status callback will transition to CANCELLED
            return True
        except Exception as exc:
            logger.error("Cancel failed for %s: %s", intent_id, exc)
            self._state_store.mark_error(intent_id, f"Cancel failed: {exc}")
            return False

    # -- Internal: placement with bounded retry ----------------------------

    async def _place_with_retry(
        self,
        intent: OrderIntent,
        resolved: ResolvedContract,
        bid: Optional[float],
        ask: Optional[float],
        wait_for_fill: bool,
    ) -> SubmitResult:
        """Build orders, place them, and optionally wait for fill.

        Retries on transient failures up to max_retries with backoff.
        """
        intent_id = intent["intent_id"]
        last_error = ""

        for attempt in range(1, self._max_retries + 2):  # attempt 1 is first try, not a retry
            try:
                built = build_orders(intent, resolved, bid=bid, ask=ask)
            except ValueError as exc:
                err = f"Order factory error: {exc}"
                logger.error("%s (intent=%s)", err, intent_id)
                self._state_store.mark_error(intent_id, err)
                return SubmitResult(success=False, intent_id=intent_id, error=err)

            try:
                trade = self._place_built_order(built)
            except Exception as exc:
                last_error = f"placeOrder error (attempt {attempt}): {exc}"
                logger.error("%s (intent=%s)", last_error, intent_id)

                if attempt <= self._max_retries:
                    retry_count = self._state_store.increment_retry(intent_id)
                    logger.info(
                        "Retrying %s (attempt %d/%d, backoff=%.1fs)",
                        intent_id, attempt + 1, self._max_retries + 1,
                        self._retry_backoff * attempt,
                    )
                    await asyncio.sleep(self._retry_backoff * attempt)
                    continue
                else:
                    self._state_store.mark_error(intent_id, last_error)
                    return SubmitResult(success=False, intent_id=intent_id, error=last_error)

            broker_order_id = getattr(trade.order, "orderId", 0)
            perm_id = getattr(trade.order, "permId", None)
            self._state_store.mark_submitted(intent_id, broker_order_id, perm_id)

            self._active_trades[intent_id] = trade
            self._attach_callbacks(intent_id, trade)

            logger.info(
                "Order placed: %s %s %s qty=%d policy=%s broker_id=%d",
                intent_id, intent["symbol"], intent["side"],
                intent["quantity"],
                intent["policy"].value if isinstance(intent["policy"], ExecutionPolicy) else intent["policy"],
                broker_order_id,
            )

            for child_order in built.children:
                try:
                    child_trade = self._ib.placeOrder(resolved.ib_contract, child_order)
                    child_ref = getattr(child_order, "orderRef", "")
                    logger.info(
                        "Child order placed: ref=%s broker_id=%d",
                        child_ref, getattr(child_trade.order, "orderId", 0),
                    )
                except Exception as exc:
                    logger.error("Child order failed for %s: %s", intent_id, exc)

            if not wait_for_fill:
                return SubmitResult(
                    success=True, intent_id=intent_id,
                    broker_order_id=broker_order_id,
                    status=OrderStatus.SUBMITTED,
                )

            return await self._wait_for_terminal(intent_id, broker_order_id)

        self._state_store.mark_error(intent_id, last_error)
        return SubmitResult(success=False, intent_id=intent_id, error=last_error)

    def _place_built_order(self, built: BuiltOrder) -> Trade:
        """Place the parent order and return the Trade object."""
        contract = built.resolved_contract.ib_contract
        trade = self._ib.placeOrder(contract, built.parent)
        return trade

    # -- Internal: event-driven fill tracking ------------------------------

    def _attach_callbacks(self, intent_id: str, trade: Trade) -> None:
        """Attach ib_insync event handlers for status and fill updates."""
        fill_event = asyncio.Event()
        self._fill_events[intent_id] = fill_event

        def on_status_change(trade: Trade) -> None:
            self._handle_status_change(intent_id, trade)

        def on_fill(trade: Trade, fill: object) -> None:
            self._handle_fill(intent_id, trade, fill)

        trade.statusEvent += on_status_change
        trade.fillEvent += on_fill

    def _handle_status_change(self, intent_id: str, trade: Trade) -> None:
        """React to broker status updates (event-driven, not polling)."""
        status_str = getattr(trade.orderStatus, "status", "")
        entry = self._state_store.get(intent_id)
        if entry is None:
            return

        logger.info(
            "Status update: %s %s → %s (filled=%s/%s)",
            intent_id, entry.status.value, status_str,
            getattr(trade.orderStatus, "filled", "?"),
            entry.quantity,
        )

        if status_str in ("PreSubmitted", "Submitted"):
            if entry.status == OrderStatus.SUBMITTED:
                self._state_store.mark_acknowledged(intent_id)

        elif status_str == "Cancelled":
            if not is_terminal(entry.status):
                self._state_store.mark_cancelled(intent_id)
            self._signal_complete(intent_id)

        elif status_str == "Inactive":
            reason = "Order went Inactive (possible rejection)"
            if not is_terminal(entry.status):
                self._state_store.mark_rejected(intent_id, reason)
            self._signal_complete(intent_id)

        elif status_str == "Filled":
            self._auto_acknowledge_if_needed(intent_id)
            entry = self._state_store.get(intent_id)
            if entry is None:
                return
            filled = int(getattr(trade.orderStatus, "filled", 0) or 0)
            avg_price = float(getattr(trade.orderStatus, "avgFillPrice", 0.0) or 0.0)
            if filled > entry.filled_qty:
                self._state_store.record_fill(
                    intent_id,
                    filled_qty=filled - entry.filled_qty,
                    avg_price=avg_price,
                    commission=self._extract_commission(trade),
                )
            entry = self._state_store.get(intent_id)
            if entry is not None and entry.status != OrderStatus.FILLED:
                self._state_store.mark_filled(intent_id)
            self._signal_complete(intent_id)

    def _handle_fill(self, intent_id: str, trade: Trade, fill: object) -> None:
        """React to individual fill events."""
        entry = self._state_store.get(intent_id)
        if entry is None:
            return

        exec_obj = getattr(fill, "execution", None)
        if exec_obj is None:
            return

        shares = int(getattr(exec_obj, "shares", 0) or 0)
        price = float(getattr(exec_obj, "price", 0.0) or 0.0)
        commission = 0.0
        cr = getattr(fill, "commissionReport", None)
        if cr and getattr(cr, "commission", 0):
            commission = float(cr.commission)

        logger.info(
            "Fill event: %s %s shares=%d price=%.4f commission=%.4f",
            intent_id, entry.symbol, shares, price, commission,
        )

    def _auto_acknowledge_if_needed(self, intent_id: str) -> None:
        """Auto-transition through ACKNOWLEDGED if broker jumps straight to fill.

        IBKR can report 'Filled' without a prior 'Submitted'/'PreSubmitted'
        event, especially for market orders.  The state machine requires
        SUBMITTED → ACKNOWLEDGED before FILLED, so we bridge the gap.
        """
        entry = self._state_store.get(intent_id)
        if entry is not None and entry.status == OrderStatus.SUBMITTED:
            self._state_store.mark_acknowledged(intent_id)

    def _signal_complete(self, intent_id: str) -> None:
        """Signal that an order has reached a terminal state."""
        event = self._fill_events.get(intent_id)
        if event is not None:
            event.set()

        entry = self._state_store.get(intent_id)
        if entry is not None and is_terminal(entry.status):
            result = SubmitResult(
                success=entry.status == OrderStatus.FILLED,
                intent_id=intent_id,
                broker_order_id=entry.broker_order_id,
                status=entry.status,
                filled_qty=entry.filled_qty,
                avg_fill_price=entry.avg_fill_price,
                total_commission=entry.total_commission,
                error=entry.last_error,
            )
            for cb in self._on_fill_callbacks:
                try:
                    ret = cb(intent_id, result)
                    if inspect.isawaitable(ret):
                        asyncio.ensure_future(ret)
                except Exception as exc:
                    logger.error("on_fill callback error: %s", exc)

        self._cleanup_intent(intent_id)

    def _cleanup_intent(self, intent_id: str) -> None:
        """Remove tracking state for completed intents."""
        self._active_trades.pop(intent_id, None)
        self._fill_events.pop(intent_id, None)

    # -- Internal: wait for terminal state ---------------------------------

    async def _wait_for_terminal(
        self, intent_id: str, broker_order_id: int,
    ) -> SubmitResult:
        """Wait for the order to reach a terminal state (bounded timeout)."""
        event = self._fill_events.get(intent_id)
        if event is None:
            event = asyncio.Event()
            self._fill_events[intent_id] = event

        try:
            await asyncio.wait_for(event.wait(), timeout=self._fill_timeout)
        except asyncio.TimeoutError:
            logger.warning(
                "Fill timeout (%.1fs) for %s; checking final state",
                self._fill_timeout, intent_id,
            )

        entry = self._state_store.get(intent_id)
        if entry is None:
            return SubmitResult(
                success=False, intent_id=intent_id,
                error="Entry disappeared from state store",
            )

        if entry.status == OrderStatus.FILLED:
            return SubmitResult(
                success=True, intent_id=intent_id,
                broker_order_id=broker_order_id,
                status=OrderStatus.FILLED,
                filled_qty=entry.filled_qty,
                avg_fill_price=entry.avg_fill_price,
                total_commission=entry.total_commission,
            )
        elif entry.status == OrderStatus.PARTIALLY_FILLED:
            logger.warning(
                "Partial fill on %s: %d/%d @ %.4f — cancelling remainder",
                intent_id, entry.filled_qty, entry.quantity, entry.avg_fill_price,
            )
            await self.cancel(intent_id)
            return SubmitResult(
                success=True, intent_id=intent_id,
                broker_order_id=broker_order_id,
                status=OrderStatus.PARTIALLY_FILLED,
                filled_qty=entry.filled_qty,
                avg_fill_price=entry.avg_fill_price,
            )
        elif is_terminal(entry.status):
            return SubmitResult(
                success=False, intent_id=intent_id,
                broker_order_id=broker_order_id,
                status=entry.status,
                error=entry.last_error or f"Terminal: {entry.status.value}",
            )
        else:
            logger.warning(
                "Timeout: %s still in %s after %.1fs — cancelling",
                intent_id, entry.status.value, self._fill_timeout,
            )
            await self.cancel(intent_id)
            return SubmitResult(
                success=False, intent_id=intent_id,
                broker_order_id=broker_order_id,
                status=entry.status,
                error=f"Timeout after {self._fill_timeout}s (status={entry.status.value})",
            )

    # -- Helpers -----------------------------------------------------------

    @staticmethod
    def _extract_commission(trade: Trade) -> float:
        """Sum commissions from all fills on a trade."""
        total = 0.0
        try:
            for fill in trade.fills:
                cr = getattr(fill, "commissionReport", None)
                if cr and getattr(cr, "commission", 0):
                    total += float(cr.commission)
        except Exception:
            pass
        return total
