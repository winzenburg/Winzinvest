"""
Order state store — local canonical truth for order lifecycle.

Tracks intent_id → broker order ID → status → fills → timestamps.
Persists to a JSONL file so state survives restarts and supports
the reconciliation service.

No ib_insync imports in this module.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from execution_policy import OrderStatus, is_terminal, validate_transition

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fill record
# ---------------------------------------------------------------------------


@dataclass
class FillRecord:
    """One partial or full fill event."""

    timestamp: str
    filled_qty: int
    avg_price: float
    commission: float = 0.0


# ---------------------------------------------------------------------------
# Order state entry
# ---------------------------------------------------------------------------


@dataclass
class OrderStateEntry:
    """Full lifecycle state for a single order intent."""

    intent_id: str
    symbol: str
    side: str
    quantity: int
    policy: str
    source_script: str
    status: OrderStatus = OrderStatus.CREATED
    broker_order_id: Optional[int] = None
    broker_perm_id: Optional[int] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    submitted_at: Optional[str] = None
    filled_at: Optional[str] = None
    cancelled_at: Optional[str] = None
    filled_qty: int = 0
    avg_fill_price: float = 0.0
    total_commission: float = 0.0
    fills: List[FillRecord] = field(default_factory=list)
    retry_count: int = 0
    last_error: Optional[str] = None
    metadata: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        """Serialize to a JSON-safe dict."""
        d: Dict[str, object] = {
            "intent_id": self.intent_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "policy": self.policy,
            "source_script": self.source_script,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.broker_order_id is not None:
            d["broker_order_id"] = self.broker_order_id
        if self.broker_perm_id is not None:
            d["broker_perm_id"] = self.broker_perm_id
        if self.submitted_at:
            d["submitted_at"] = self.submitted_at
        if self.filled_at:
            d["filled_at"] = self.filled_at
        if self.cancelled_at:
            d["cancelled_at"] = self.cancelled_at
        if self.filled_qty > 0:
            d["filled_qty"] = self.filled_qty
            d["avg_fill_price"] = self.avg_fill_price
            d["total_commission"] = self.total_commission
        if self.fills:
            d["fills"] = [
                {"timestamp": f.timestamp, "filled_qty": f.filled_qty,
                 "avg_price": f.avg_price, "commission": f.commission}
                for f in self.fills
            ]
        if self.retry_count > 0:
            d["retry_count"] = self.retry_count
        if self.last_error:
            d["last_error"] = self.last_error
        if self.metadata:
            d["metadata"] = self.metadata
        return d


# ---------------------------------------------------------------------------
# State store
# ---------------------------------------------------------------------------


class OrderStateStore:
    """In-memory + persisted order state store.

    Thread-safe.  All mutations go through transition methods that enforce
    the state machine defined in execution_policy.py.

    Usage::

        store = OrderStateStore(Path("trading/logs/order_state.jsonl"))
        entry = store.create(intent)
        store.mark_submitted(entry.intent_id, broker_order_id=42)
        store.record_fill(entry.intent_id, filled_qty=50, avg_price=123.45)
        store.mark_filled(entry.intent_id)
    """

    def __init__(self, persist_path: Optional[Path] = None) -> None:
        self._entries: Dict[str, OrderStateEntry] = {}
        self._by_broker_id: Dict[int, str] = {}
        self._persist_path = persist_path
        self._lock = threading.Lock()

        if persist_path and persist_path.exists():
            self._load_from_disk()

    # -- Creation ----------------------------------------------------------

    def create(
        self,
        intent_id: str,
        symbol: str,
        side: str,
        quantity: int,
        policy: str,
        source_script: str,
        metadata: Optional[Dict[str, object]] = None,
    ) -> OrderStateEntry:
        """Register a new order intent. Raises if intent_id already exists."""
        with self._lock:
            if intent_id in self._entries:
                existing = self._entries[intent_id]
                if is_terminal(existing.status):
                    logger.info(
                        "Intent %s already in terminal state %s; treating as duplicate",
                        intent_id, existing.status.value,
                    )
                else:
                    logger.warning(
                        "Intent %s already active (status=%s); rejecting duplicate",
                        intent_id, existing.status.value,
                    )
                return existing

            entry = OrderStateEntry(
                intent_id=intent_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                policy=policy,
                source_script=source_script,
                metadata=metadata or {},
            )
            self._entries[intent_id] = entry
            self._persist(entry)
            logger.info("Order state created: %s %s %s qty=%d policy=%s",
                        intent_id, symbol, side, quantity, policy)
            return entry

    # -- Transitions -------------------------------------------------------

    def mark_submitted(self, intent_id: str, broker_order_id: int, broker_perm_id: Optional[int] = None) -> bool:
        """Transition to SUBMITTED and record broker order ID."""
        with self._lock:
            entry = self._entries.get(intent_id)
            if entry is None:
                logger.error("mark_submitted: unknown intent %s", intent_id)
                return False
            if not self._transition(entry, OrderStatus.SUBMITTED):
                return False
            entry.broker_order_id = broker_order_id
            entry.broker_perm_id = broker_perm_id
            entry.submitted_at = datetime.now().isoformat()
            self._by_broker_id[broker_order_id] = intent_id
            self._persist(entry)
            return True

    def mark_acknowledged(self, intent_id: str) -> bool:
        """Transition to ACKNOWLEDGED (broker accepted, order is live)."""
        with self._lock:
            entry = self._entries.get(intent_id)
            if entry is None:
                logger.error("mark_acknowledged: unknown intent %s", intent_id)
                return False
            if not self._transition(entry, OrderStatus.ACKNOWLEDGED):
                return False
            self._persist(entry)
            return True

    def record_fill(
        self,
        intent_id: str,
        filled_qty: int,
        avg_price: float,
        commission: float = 0.0,
    ) -> bool:
        """Record a partial or full fill.  Transitions to PARTIALLY_FILLED."""
        with self._lock:
            entry = self._entries.get(intent_id)
            if entry is None:
                logger.error("record_fill: unknown intent %s", intent_id)
                return False

            fill = FillRecord(
                timestamp=datetime.now().isoformat(),
                filled_qty=filled_qty,
                avg_price=avg_price,
                commission=commission,
            )
            entry.fills.append(fill)

            total_filled = sum(f.filled_qty for f in entry.fills)
            if total_filled > 0:
                total_cost = sum(f.filled_qty * f.avg_price for f in entry.fills)
                entry.avg_fill_price = round(total_cost / total_filled, 6)
            entry.filled_qty = total_filled
            entry.total_commission = round(sum(f.commission for f in entry.fills), 4)

            if total_filled >= entry.quantity:
                self._transition(entry, OrderStatus.FILLED)
                entry.filled_at = datetime.now().isoformat()
            elif entry.status not in (OrderStatus.PARTIALLY_FILLED,):
                self._transition(entry, OrderStatus.PARTIALLY_FILLED)

            self._persist(entry)
            logger.info(
                "Fill recorded: %s %s qty=%d/%d price=%.4f",
                intent_id, entry.symbol, total_filled, entry.quantity, avg_price,
            )
            return True

    def mark_filled(self, intent_id: str) -> bool:
        """Explicit transition to FILLED (when broker reports fill complete)."""
        with self._lock:
            entry = self._entries.get(intent_id)
            if entry is None:
                logger.error("mark_filled: unknown intent %s", intent_id)
                return False
            if entry.status == OrderStatus.FILLED:
                return True
            if not self._transition(entry, OrderStatus.FILLED):
                return False
            entry.filled_at = datetime.now().isoformat()
            self._persist(entry)
            return True

    def mark_cancelled(self, intent_id: str) -> bool:
        """Transition to CANCELLED."""
        with self._lock:
            entry = self._entries.get(intent_id)
            if entry is None:
                logger.error("mark_cancelled: unknown intent %s", intent_id)
                return False
            if is_terminal(entry.status):
                logger.debug("Intent %s already terminal (%s), skip cancel", intent_id, entry.status.value)
                return True
            if entry.status not in (OrderStatus.CANCEL_PENDING,):
                self._transition(entry, OrderStatus.CANCEL_PENDING)
            self._transition(entry, OrderStatus.CANCELLED)
            entry.cancelled_at = datetime.now().isoformat()
            self._persist(entry)
            return True

    def mark_rejected(self, intent_id: str, reason: str = "") -> bool:
        """Transition to REJECTED."""
        with self._lock:
            entry = self._entries.get(intent_id)
            if entry is None:
                logger.error("mark_rejected: unknown intent %s", intent_id)
                return False
            if not self._transition(entry, OrderStatus.REJECTED):
                return False
            entry.last_error = reason
            self._persist(entry)
            return True

    def mark_error(self, intent_id: str, error: str) -> bool:
        """Transition to ERROR with reason."""
        with self._lock:
            entry = self._entries.get(intent_id)
            if entry is None:
                logger.error("mark_error: unknown intent %s", intent_id)
                return False
            if not self._transition(entry, OrderStatus.ERROR):
                return False
            entry.last_error = error
            self._persist(entry)
            return True

    def increment_retry(self, intent_id: str) -> int:
        """Increment and return the retry count for an intent."""
        with self._lock:
            entry = self._entries.get(intent_id)
            if entry is None:
                return -1
            entry.retry_count += 1
            entry.updated_at = datetime.now().isoformat()
            self._persist(entry)
            return entry.retry_count

    # -- Lookups -----------------------------------------------------------

    def get(self, intent_id: str) -> Optional[OrderStateEntry]:
        """Look up an entry by intent_id."""
        return self._entries.get(intent_id)

    def get_by_broker_id(self, broker_order_id: int) -> Optional[OrderStateEntry]:
        """Look up an entry by IBKR broker order ID."""
        intent_id = self._by_broker_id.get(broker_order_id)
        if intent_id is None:
            return None
        return self._entries.get(intent_id)

    def active_intents(self) -> List[OrderStateEntry]:
        """Return all non-terminal entries."""
        return [e for e in self._entries.values() if not is_terminal(e.status)]

    def all_entries(self) -> List[OrderStateEntry]:
        """Return all entries (including terminal)."""
        return list(self._entries.values())

    def has_active_intent(self, intent_id: str) -> bool:
        """True if this intent_id exists and is not in a terminal state."""
        entry = self._entries.get(intent_id)
        return entry is not None and not is_terminal(entry.status)

    @property
    def stats(self) -> Dict[str, int]:
        """Counts by status for observability."""
        counts: Dict[str, int] = {}
        for entry in self._entries.values():
            key = entry.status.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    # -- Internal ----------------------------------------------------------

    def _transition(self, entry: OrderStateEntry, target: OrderStatus) -> bool:
        """Enforce valid state machine transition."""
        if not validate_transition(entry.status, target):
            logger.warning(
                "Invalid transition: %s %s → %s (allowed: %s)",
                entry.intent_id,
                entry.status.value,
                target.value,
                ", ".join(s.value for s in sorted(
                    execution_policy_valid_transitions(entry.status),
                    key=lambda s: s.value,
                )) if execution_policy_valid_transitions(entry.status) else "none",
            )
            return False
        entry.status = target
        entry.updated_at = datetime.now().isoformat()
        logger.debug("Transition: %s → %s (%s)", entry.intent_id, target.value, entry.symbol)
        return True

    def _persist(self, entry: OrderStateEntry) -> None:
        """Append the current state to the JSONL persistence file."""
        if self._persist_path is None:
            return
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._persist_path, "a") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")
        except OSError as exc:
            logger.error("Failed to persist order state: %s", exc)

    def _load_from_disk(self) -> None:
        """Replay the JSONL file to rebuild in-memory state.

        Each line is a snapshot of an entry at a point in time.  We keep
        the latest snapshot per intent_id (last-writer-wins).
        """
        if self._persist_path is None or not self._persist_path.exists():
            return

        count = 0
        try:
            with open(self._persist_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    intent_id = d.get("intent_id")
                    if not isinstance(intent_id, str):
                        continue

                    entry = OrderStateEntry(
                        intent_id=intent_id,
                        symbol=d.get("symbol", ""),
                        side=d.get("side", ""),
                        quantity=int(d.get("quantity", 0)),
                        policy=d.get("policy", ""),
                        source_script=d.get("source_script", ""),
                        status=OrderStatus(d.get("status", "created")),
                        broker_order_id=d.get("broker_order_id"),
                        broker_perm_id=d.get("broker_perm_id"),
                        created_at=d.get("created_at", ""),
                        updated_at=d.get("updated_at", ""),
                        submitted_at=d.get("submitted_at"),
                        filled_at=d.get("filled_at"),
                        cancelled_at=d.get("cancelled_at"),
                        filled_qty=int(d.get("filled_qty", 0)),
                        avg_fill_price=float(d.get("avg_fill_price", 0.0)),
                        total_commission=float(d.get("total_commission", 0.0)),
                        retry_count=int(d.get("retry_count", 0)),
                        last_error=d.get("last_error"),
                        metadata=d.get("metadata", {}),
                    )

                    fills_raw = d.get("fills", [])
                    if isinstance(fills_raw, list):
                        for fr in fills_raw:
                            if isinstance(fr, dict):
                                entry.fills.append(FillRecord(
                                    timestamp=fr.get("timestamp", ""),
                                    filled_qty=int(fr.get("filled_qty", 0)),
                                    avg_price=float(fr.get("avg_price", 0.0)),
                                    commission=float(fr.get("commission", 0.0)),
                                ))

                    self._entries[intent_id] = entry
                    if entry.broker_order_id is not None:
                        self._by_broker_id[entry.broker_order_id] = intent_id
                    count += 1

        except OSError as exc:
            logger.error("Failed to load order state from disk: %s", exc)

        logger.info("Loaded %d order state entries from %s", count, self._persist_path)


def execution_policy_valid_transitions(status: OrderStatus) -> frozenset[OrderStatus]:
    """Re-export for use in the _transition method without circular import."""
    from execution_policy import VALID_TRANSITIONS
    return VALID_TRANSITIONS.get(status, frozenset())
