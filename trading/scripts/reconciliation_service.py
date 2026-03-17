"""
Reconciliation service — sync positions, open orders, and local state on startup.

MUST be called before any new orders are submitted after a connect or reconnect.
This is a non-negotiable execution invariant.

This is one of the few modules permitted to import ib_insync.

Workflow:
  1. Fetch open orders from IBKR.
  2. Fetch current positions from IBKR.
  3. Compare with local OrderStateStore.
  4. Resolve discrepancies (orphaned orders, missing state, stale state).
  5. Log a structured reconciliation report.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set

from ib_insync import IB, Trade

from execution_policy import OrderStatus, is_terminal
from order_state_store import OrderStateStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Position snapshot (broker truth)
# ---------------------------------------------------------------------------


@dataclass
class BrokerPosition:
    """A single position as reported by IBKR."""

    con_id: int
    symbol: str
    sec_type: str
    quantity: int  # signed: negative = short
    avg_cost: float
    market_value: float


# ---------------------------------------------------------------------------
# Reconciliation report
# ---------------------------------------------------------------------------


@dataclass
class ReconciliationReport:
    """Structured output from the reconciliation process."""

    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    broker_open_orders: int = 0
    broker_positions: int = 0
    local_active_intents: int = 0
    orphaned_broker_orders: List[Dict[str, object]] = field(default_factory=list)
    stale_local_intents: List[str] = field(default_factory=list)
    synced_intents: List[str] = field(default_factory=list)
    position_mismatches: List[Dict[str, object]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    is_clean: bool = True

    def to_dict(self) -> Dict[str, object]:
        return {
            "timestamp": self.timestamp,
            "broker_open_orders": self.broker_open_orders,
            "broker_positions": self.broker_positions,
            "local_active_intents": self.local_active_intents,
            "orphaned_broker_orders": self.orphaned_broker_orders,
            "stale_local_intents": self.stale_local_intents,
            "synced_intents": self.synced_intents,
            "position_mismatches": self.position_mismatches,
            "errors": self.errors,
            "is_clean": self.is_clean,
        }


# ---------------------------------------------------------------------------
# Reconciliation service
# ---------------------------------------------------------------------------


class ReconciliationService:
    """Startup reconciliation between local state and broker truth.

    Usage::

        recon = ReconciliationService(ib, state_store)
        report = await recon.reconcile()
        if not report.is_clean:
            logger.warning("Reconciliation found issues: %s", report.to_dict())
        # Now safe to submit new orders.
    """

    MAX_RECONCILIATION_RETRIES = 3

    def __init__(self, ib: IB, state_store: OrderStateStore) -> None:
        self._ib = ib
        self._store = state_store

    async def reconcile(self) -> ReconciliationReport:
        """Run the full reconciliation sequence.

        Steps:
          1. Fetch broker open orders.
          2. Match them against local state.
          3. Mark stale local intents (no matching broker order).
          4. Flag orphaned broker orders (no matching local intent).
          5. Fetch positions for informational logging.

        Returns a ReconciliationReport.
        """
        report = ReconciliationReport()

        broker_trades = await self._fetch_open_orders(report)
        broker_positions = self._fetch_positions(report)

        report.broker_open_orders = len(broker_trades)
        report.broker_positions = len(broker_positions)

        active_intents = self._store.active_intents()
        report.local_active_intents = len(active_intents)

        self._match_orders_to_intents(broker_trades, active_intents, report)
        self._log_positions(broker_positions, report)

        if report.orphaned_broker_orders or report.stale_local_intents or report.position_mismatches:
            report.is_clean = False

        self._log_report(report)
        return report

    # -- Broker queries ----------------------------------------------------

    async def _fetch_open_orders(self, report: ReconciliationReport) -> List[Trade]:
        """Fetch all open orders from IBKR."""
        try:
            trades = self._ib.openTrades()
            return list(trades)
        except Exception as exc:
            msg = f"Failed to fetch open orders: {exc}"
            logger.error(msg)
            report.errors.append(msg)
            report.is_clean = False
            return []

    def _fetch_positions(self, report: ReconciliationReport) -> List[BrokerPosition]:
        """Fetch all current positions from IBKR."""
        positions: List[BrokerPosition] = []
        try:
            for pos in self._ib.positions():
                con = pos.contract
                positions.append(BrokerPosition(
                    con_id=getattr(con, "conId", 0),
                    symbol=getattr(con, "symbol", ""),
                    sec_type=getattr(con, "secType", ""),
                    quantity=int(getattr(pos, "position", 0)),
                    avg_cost=float(getattr(pos, "avgCost", 0.0)),
                    market_value=float(getattr(pos, "marketValue", 0.0) if hasattr(pos, "marketValue") else 0.0),
                ))
        except Exception as exc:
            msg = f"Failed to fetch positions: {exc}"
            logger.error(msg)
            report.errors.append(msg)
            report.is_clean = False
        return positions

    # -- Matching logic ----------------------------------------------------

    def _match_orders_to_intents(
        self,
        broker_trades: List[Trade],
        active_intents: list,
        report: ReconciliationReport,
    ) -> None:
        """Match broker open orders against local active intents."""

        broker_order_refs: Dict[str, Trade] = {}
        broker_order_ids: Dict[int, Trade] = {}
        for trade in broker_trades:
            order = trade.order
            ref = getattr(order, "orderRef", "") or ""
            oid = getattr(order, "orderId", 0)
            if ref:
                broker_order_refs[ref] = trade
            if oid:
                broker_order_ids[oid] = trade

        matched_intent_ids: Set[str] = set()
        matched_broker_refs: Set[str] = set()
        matched_broker_oids: Set[int] = set()

        for entry in active_intents:
            matched = False

            if entry.intent_id in broker_order_refs:
                matched = True
                matched_intent_ids.add(entry.intent_id)
                matched_broker_refs.add(entry.intent_id)
                report.synced_intents.append(entry.intent_id)
                self._sync_status_from_trade(entry, broker_order_refs[entry.intent_id])

            elif entry.broker_order_id is not None and entry.broker_order_id in broker_order_ids:
                matched = True
                matched_intent_ids.add(entry.intent_id)
                matched_broker_oids.add(entry.broker_order_id)
                report.synced_intents.append(entry.intent_id)
                self._sync_status_from_trade(entry, broker_order_ids[entry.broker_order_id])

            if not matched:
                report.stale_local_intents.append(entry.intent_id)
                if entry.status in (OrderStatus.SUBMITTED, OrderStatus.ACKNOWLEDGED, OrderStatus.PARTIALLY_FILLED):
                    logger.warning(
                        "Stale intent %s (%s) — no matching broker order; marking cancelled",
                        entry.intent_id, entry.status.value,
                    )
                    self._store.mark_cancelled(entry.intent_id)

        for trade in broker_trades:
            order = trade.order
            ref = getattr(order, "orderRef", "") or ""
            oid = getattr(order, "orderId", 0)

            if ref in matched_broker_refs:
                continue
            if oid in matched_broker_oids:
                continue

            report.orphaned_broker_orders.append({
                "order_id": oid,
                "order_ref": ref,
                "symbol": getattr(trade.contract, "symbol", ""),
                "action": getattr(order, "action", ""),
                "quantity": getattr(order, "totalQuantity", 0),
                "order_type": getattr(order, "orderType", ""),
                "status": getattr(trade.orderStatus, "status", ""),
            })
            logger.warning(
                "Orphaned broker order: id=%d ref=%s %s %s qty=%s",
                oid, ref,
                getattr(trade.contract, "symbol", "?"),
                getattr(order, "action", "?"),
                getattr(order, "totalQuantity", "?"),
            )

    def _sync_status_from_trade(self, entry, trade: Trade) -> None:
        """Update local state to match broker-reported status."""
        broker_status = getattr(trade.orderStatus, "status", "")
        filled = int(getattr(trade.orderStatus, "filled", 0) or 0)

        if broker_status == "Filled" and entry.status != OrderStatus.FILLED:
            avg_price = float(getattr(trade.orderStatus, "avgFillPrice", 0.0) or 0.0)
            if filled > entry.filled_qty:
                self._store.record_fill(entry.intent_id, filled - entry.filled_qty, avg_price)
            self._store.mark_filled(entry.intent_id)

        elif broker_status == "Cancelled" and not is_terminal(entry.status):
            self._store.mark_cancelled(entry.intent_id)

        elif broker_status in ("PreSubmitted", "Submitted") and entry.status == OrderStatus.SUBMITTED:
            self._store.mark_acknowledged(entry.intent_id)

        elif filled > entry.filled_qty and entry.status not in (OrderStatus.FILLED,):
            avg_price = float(getattr(trade.orderStatus, "avgFillPrice", 0.0) or 0.0)
            self._store.record_fill(entry.intent_id, filled - entry.filled_qty, avg_price)

    # -- Position logging --------------------------------------------------

    def _log_positions(
        self, positions: List[BrokerPosition], report: ReconciliationReport,
    ) -> None:
        """Log current positions for the reconciliation report."""
        for pos in positions:
            logger.info(
                "Position: %s %s qty=%d avg_cost=%.2f",
                pos.symbol, pos.sec_type, pos.quantity, pos.avg_cost,
            )

    # -- Reporting ---------------------------------------------------------

    def _log_report(self, report: ReconciliationReport) -> None:
        """Emit a structured log of the reconciliation outcome."""
        if report.is_clean:
            logger.info(
                "Reconciliation clean: %d broker orders, %d positions, %d local intents synced",
                report.broker_open_orders,
                report.broker_positions,
                len(report.synced_intents),
            )
        else:
            logger.warning(
                "Reconciliation issues: orphaned=%d stale=%d errors=%d",
                len(report.orphaned_broker_orders),
                len(report.stale_local_intents),
                len(report.errors),
            )
            for orphan in report.orphaned_broker_orders:
                logger.warning("  Orphaned: %s", orphan)
            for stale in report.stale_local_intents:
                logger.warning("  Stale local intent: %s", stale)
            for err in report.errors:
                logger.error("  Error: %s", err)
