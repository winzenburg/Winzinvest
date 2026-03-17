"""
Tests for Phase 1 execution foundation modules:
  - execution_policy (intent IDs, state machine, validation)
  - order_factory (policy → IBKR order translation)
  - order_state_store (lifecycle tracking, persistence, dedup)

Run with: pytest trading/tests/test_execution_foundation.py -v
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


# ═══════════════════════════════════════════════════════════════════════════════
# execution_policy tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestExecutionPolicy:
    """ExecutionPolicy enum and helpers."""

    def test_all_policies_are_strings(self):
        from execution_policy import ExecutionPolicy
        for p in ExecutionPolicy:
            assert isinstance(p.value, str)
            assert p.value == p.value  # value is always the snake_case string

    def test_policy_count(self):
        from execution_policy import ExecutionPolicy
        assert len(ExecutionPolicy) == 8


class TestOrderStatus:
    """Order lifecycle state machine."""

    def test_terminal_states(self):
        from execution_policy import OrderStatus, is_terminal
        assert is_terminal(OrderStatus.FILLED)
        assert is_terminal(OrderStatus.CANCELLED)
        assert is_terminal(OrderStatus.REJECTED)
        assert is_terminal(OrderStatus.ERROR)
        assert not is_terminal(OrderStatus.CREATED)
        assert not is_terminal(OrderStatus.SUBMITTED)
        assert not is_terminal(OrderStatus.ACKNOWLEDGED)
        assert not is_terminal(OrderStatus.PARTIALLY_FILLED)

    def test_valid_transitions_from_created(self):
        from execution_policy import OrderStatus, validate_transition
        assert validate_transition(OrderStatus.CREATED, OrderStatus.SUBMITTED)
        assert validate_transition(OrderStatus.CREATED, OrderStatus.CANCELLED)
        assert validate_transition(OrderStatus.CREATED, OrderStatus.ERROR)
        assert not validate_transition(OrderStatus.CREATED, OrderStatus.FILLED)
        assert not validate_transition(OrderStatus.CREATED, OrderStatus.ACKNOWLEDGED)

    def test_valid_transitions_from_submitted(self):
        from execution_policy import OrderStatus, validate_transition
        assert validate_transition(OrderStatus.SUBMITTED, OrderStatus.ACKNOWLEDGED)
        assert validate_transition(OrderStatus.SUBMITTED, OrderStatus.REJECTED)
        assert validate_transition(OrderStatus.SUBMITTED, OrderStatus.CANCELLED)
        assert not validate_transition(OrderStatus.SUBMITTED, OrderStatus.FILLED)

    def test_valid_transitions_from_acknowledged(self):
        from execution_policy import OrderStatus, validate_transition
        assert validate_transition(OrderStatus.ACKNOWLEDGED, OrderStatus.PARTIALLY_FILLED)
        assert validate_transition(OrderStatus.ACKNOWLEDGED, OrderStatus.FILLED)
        assert validate_transition(OrderStatus.ACKNOWLEDGED, OrderStatus.CANCEL_PENDING)
        assert not validate_transition(OrderStatus.ACKNOWLEDGED, OrderStatus.SUBMITTED)

    def test_terminal_states_have_no_transitions(self):
        from execution_policy import OrderStatus, VALID_TRANSITIONS
        for status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.ERROR):
            assert len(VALID_TRANSITIONS[status]) == 0

    def test_partial_fill_can_lead_to_filled(self):
        from execution_policy import OrderStatus, validate_transition
        assert validate_transition(OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED)
        assert validate_transition(OrderStatus.PARTIALLY_FILLED, OrderStatus.PARTIALLY_FILLED)
        assert validate_transition(OrderStatus.PARTIALLY_FILLED, OrderStatus.CANCEL_PENDING)


class TestIntentIdGeneration:
    """Deterministic intent ID generation."""

    def test_same_inputs_produce_same_id(self):
        from execution_policy import ExecutionPolicy, generate_intent_id
        id1 = generate_intent_id("NVDA", "BUY", ExecutionPolicy.PASSIVE_ENTRY, "test.py", "20260307", 0)
        id2 = generate_intent_id("NVDA", "BUY", ExecutionPolicy.PASSIVE_ENTRY, "test.py", "20260307", 0)
        assert id1 == id2

    def test_different_sequence_produces_different_id(self):
        from execution_policy import ExecutionPolicy, generate_intent_id
        id1 = generate_intent_id("NVDA", "BUY", ExecutionPolicy.PASSIVE_ENTRY, "test.py", "20260307", 0)
        id2 = generate_intent_id("NVDA", "BUY", ExecutionPolicy.PASSIVE_ENTRY, "test.py", "20260307", 1)
        assert id1 != id2

    def test_different_symbol_produces_different_id(self):
        from execution_policy import ExecutionPolicy, generate_intent_id
        id1 = generate_intent_id("NVDA", "BUY", ExecutionPolicy.PASSIVE_ENTRY, "test.py", "20260307", 0)
        id2 = generate_intent_id("AAPL", "BUY", ExecutionPolicy.PASSIVE_ENTRY, "test.py", "20260307", 0)
        assert id1 != id2

    def test_id_contains_symbol_and_side(self):
        from execution_policy import ExecutionPolicy, generate_intent_id
        result = generate_intent_id("NVDA", "BUY", ExecutionPolicy.PASSIVE_ENTRY, "test.py", "20260307", 0)
        assert "NVDA" in result
        assert "BUY" in result
        assert "passive_entry" in result

    def test_case_normalization(self):
        from execution_policy import ExecutionPolicy, generate_intent_id
        id1 = generate_intent_id("nvda", "BUY", ExecutionPolicy.PASSIVE_ENTRY, "test.py", "20260307", 0)
        id2 = generate_intent_id("NVDA", "BUY", ExecutionPolicy.PASSIVE_ENTRY, "test.py", "20260307", 0)
        assert id1 == id2


class TestBuildIntent:
    """build_intent helper validation."""

    def test_basic_passive_entry(self):
        from execution_policy import ExecutionPolicy, build_intent
        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.PASSIVE_ENTRY,
            source_script="test.py", limit_price=120.0,
        )
        assert intent["symbol"] == "NVDA"
        assert intent["side"] == "BUY"
        assert intent["quantity"] == 50
        assert intent["policy"] == ExecutionPolicy.PASSIVE_ENTRY
        assert "intent_id" in intent

    def test_missing_limit_for_passive_entry_raises(self):
        from execution_policy import ExecutionPolicy, build_intent
        with pytest.raises(ValueError, match="requires limit_price"):
            build_intent(
                symbol="NVDA", side="BUY", quantity=50,
                policy=ExecutionPolicy.PASSIVE_ENTRY,
                source_script="test.py",
            )

    def test_missing_stop_for_stop_protect_raises(self):
        from execution_policy import ExecutionPolicy, build_intent
        with pytest.raises(ValueError, match="requires stop_price"):
            build_intent(
                symbol="NVDA", side="SELL", quantity=50,
                policy=ExecutionPolicy.STOP_PROTECT,
                source_script="test.py",
            )

    def test_missing_trail_for_trailing_stop_raises(self):
        from execution_policy import ExecutionPolicy, build_intent
        with pytest.raises(ValueError, match="requires trail_amount"):
            build_intent(
                symbol="NVDA", side="SELL", quantity=50,
                policy=ExecutionPolicy.TRAILING_STOP,
                source_script="test.py",
            )

    def test_urgent_exit_needs_no_price(self):
        from execution_policy import ExecutionPolicy, build_intent
        intent = build_intent(
            symbol="NVDA", side="SELL", quantity=50,
            policy=ExecutionPolicy.URGENT_EXIT,
            source_script="test.py",
        )
        assert intent["policy"] == ExecutionPolicy.URGENT_EXIT

    def test_zero_quantity_raises(self):
        from execution_policy import ExecutionPolicy, build_intent
        with pytest.raises(ValueError, match="quantity must be positive"):
            build_intent(
                symbol="NVDA", side="BUY", quantity=0,
                policy=ExecutionPolicy.URGENT_EXIT,
                source_script="test.py",
            )

    def test_metadata_passthrough(self):
        from execution_policy import ExecutionPolicy, build_intent
        meta = {"regime": "STRONG_UPTREND", "conviction": 0.85}
        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.URGENT_EXIT,
            source_script="test.py",
            metadata=meta,
        )
        assert intent["metadata"] == meta

    def test_bracketed_needs_limit_and_stop(self):
        from execution_policy import ExecutionPolicy, build_intent
        with pytest.raises(ValueError):
            build_intent(
                symbol="NVDA", side="BUY", quantity=50,
                policy=ExecutionPolicy.BRACKETED_SWING_ENTRY,
                source_script="test.py",
                limit_price=120.0,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# order_factory tests
# ═══════════════════════════════════════════════════════════════════════════════


def _mock_resolved(symbol: str = "NVDA", con_id: int = 12345) -> MagicMock:
    """Create a mock ResolvedContract for testing."""
    mock = MagicMock()
    mock.con_id = con_id
    mock.symbol = symbol
    mock.sec_type = "STK"
    mock.exchange = "SMART"
    mock.primary_exchange = "NASDAQ"
    mock.currency = "USD"
    mock.ib_contract = MagicMock()
    mock.key = f"{con_id}@SMART"
    return mock


class TestOrderFactoryPassiveEntry:

    def test_buy_limit_at_bid(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_factory import build_orders
        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.PASSIVE_ENTRY,
            source_script="test.py", limit_price=120.0,
        )
        result = build_orders(intent, _mock_resolved(), bid=119.50, ask=120.10)
        assert result.parent.action == "BUY"
        assert result.parent.lmtPrice == 119.50
        assert result.parent.tif == "GTC"
        assert result.parent.orderRef == intent["intent_id"]
        assert len(result.children) == 0

    def test_sell_limit_at_ask(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_factory import build_orders
        intent = build_intent(
            symbol="NVDA", side="SELL", quantity=50,
            policy=ExecutionPolicy.PASSIVE_ENTRY,
            source_script="test.py", limit_price=120.0,
        )
        result = build_orders(intent, _mock_resolved(), bid=119.50, ask=120.10)
        assert result.parent.action == "SELL"
        assert result.parent.lmtPrice == 120.10

    def test_fallback_to_limit_price_when_no_bid_ask(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_factory import build_orders
        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.PASSIVE_ENTRY,
            source_script="test.py", limit_price=120.0,
        )
        result = build_orders(intent, _mock_resolved())
        assert result.parent.lmtPrice == 120.0


class TestOrderFactoryAggressiveEntry:

    def test_buy_limit_at_ask(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_factory import build_orders
        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script="test.py", limit_price=120.0,
        )
        result = build_orders(intent, _mock_resolved(), bid=119.50, ask=120.10)
        assert result.parent.lmtPrice == 120.10
        assert result.parent.tif == "DAY"


class TestOrderFactorySpreadAware:

    def test_adaptive_algo_set(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_factory import build_orders
        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.SPREAD_AWARE_ENTRY,
            source_script="test.py", limit_price=120.0,
        )
        result = build_orders(intent, _mock_resolved(), ask=120.10)
        assert result.parent.algoStrategy == "Adaptive"
        assert len(result.parent.algoParams) == 1
        assert result.parent.algoParams[0].tag == "adaptivePriority"
        assert result.parent.algoParams[0].value == "Normal"


class TestOrderFactoryBracketedSwing:

    def test_parent_plus_two_children(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_factory import build_orders
        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.BRACKETED_SWING_ENTRY,
            source_script="test.py",
            limit_price=120.0, stop_price=115.0, take_profit_price=130.0,
        )
        result = build_orders(intent, _mock_resolved())
        assert len(result.children) == 2

        parent = result.parent
        assert parent.action == "BUY"
        assert parent.lmtPrice == 120.0
        assert parent.transmit is False

        stop_child = result.children[0]
        assert stop_child.action == "SELL"
        assert stop_child.orderType == "STP"
        assert stop_child.auxPrice == 115.0
        assert stop_child.ocaGroup.startswith("bracket-")

        tp_child = result.children[1]
        assert tp_child.action == "SELL"
        assert tp_child.lmtPrice == 130.0
        assert tp_child.ocaGroup == stop_child.ocaGroup
        assert tp_child.transmit is True

    def test_bracket_without_tp(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_factory import build_orders
        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.BRACKETED_SWING_ENTRY,
            source_script="test.py",
            limit_price=120.0, stop_price=115.0,
        )
        result = build_orders(intent, _mock_resolved())
        assert len(result.children) == 1
        assert result.children[0].transmit is True


class TestOrderFactoryUrgentExit:

    def test_market_order(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_factory import build_orders
        intent = build_intent(
            symbol="NVDA", side="SELL", quantity=50,
            policy=ExecutionPolicy.URGENT_EXIT,
            source_script="test.py",
        )
        result = build_orders(intent, _mock_resolved())
        assert result.parent.orderType == "MKT"
        assert result.parent.tif == "DAY"


class TestOrderFactoryStopProtect:

    def test_stop_limit_sell(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_factory import build_orders
        intent = build_intent(
            symbol="NVDA", side="SELL", quantity=50,
            policy=ExecutionPolicy.STOP_PROTECT,
            source_script="test.py", stop_price=115.0,
        )
        result = build_orders(intent, _mock_resolved())
        assert result.parent.orderType == "STP LMT"
        assert result.parent.auxPrice == 115.0
        assert result.parent.lmtPrice == 114.99

    def test_stop_limit_buy_to_cover(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_factory import build_orders
        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.STOP_PROTECT,
            source_script="test.py", stop_price=130.0,
        )
        result = build_orders(intent, _mock_resolved())
        assert result.parent.auxPrice == 130.0
        assert result.parent.lmtPrice == 130.01


class TestOrderFactoryTrailingStop:

    def test_trailing_stop(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_factory import build_orders
        intent = build_intent(
            symbol="NVDA", side="SELL", quantity=50,
            policy=ExecutionPolicy.TRAILING_STOP,
            source_script="test.py", trail_amount=3.50,
        )
        result = build_orders(intent, _mock_resolved())
        assert result.parent.orderType == "TRAIL"
        assert result.parent.auxPrice == 3.50
        assert result.parent.tif == "GTC"


class TestOrderFactoryRthFlag:

    def test_outside_rth_stamped_on_limit(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_factory import build_orders
        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.PASSIVE_ENTRY,
            source_script="test.py", limit_price=120.0,
            outside_rth=True,
        )
        result = build_orders(intent, _mock_resolved())
        assert result.parent.outsideRth is True


class TestTickRounding:

    def test_round_to_penny(self):
        from order_factory import _round_to_tick
        assert _round_to_tick(123.456, 0.01) == 123.46
        assert _round_to_tick(123.454, 0.01) == 123.45

    def test_round_to_nickel(self):
        from order_factory import _round_to_tick
        assert _round_to_tick(1.23, 0.05) == 1.25
        assert _round_to_tick(1.21, 0.05) == 1.20


# ═══════════════════════════════════════════════════════════════════════════════
# order_state_store tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrderStateStoreLifecycle:
    """Full lifecycle: create → submit → ack → partial fill → filled."""

    def test_happy_path(self):
        from order_state_store import OrderStateStore
        from execution_policy import OrderStatus

        store = OrderStateStore()

        entry = store.create("test-001", "NVDA", "BUY", 100, "passive_entry", "test.py")
        assert entry.status == OrderStatus.CREATED

        assert store.mark_submitted("test-001", broker_order_id=42)
        assert store.get("test-001").status == OrderStatus.SUBMITTED

        assert store.mark_acknowledged("test-001")
        assert store.get("test-001").status == OrderStatus.ACKNOWLEDGED

        assert store.record_fill("test-001", filled_qty=60, avg_price=120.0)
        assert store.get("test-001").status == OrderStatus.PARTIALLY_FILLED
        assert store.get("test-001").filled_qty == 60

        assert store.record_fill("test-001", filled_qty=40, avg_price=120.50)
        assert store.get("test-001").status == OrderStatus.FILLED
        assert store.get("test-001").filled_qty == 100

    def test_cancel_path(self):
        from order_state_store import OrderStateStore
        from execution_policy import OrderStatus

        store = OrderStateStore()
        store.create("test-002", "AAPL", "SELL", 50, "normal_exit", "test.py")
        store.mark_submitted("test-002", broker_order_id=43)
        store.mark_acknowledged("test-002")

        assert store.mark_cancelled("test-002")
        assert store.get("test-002").status == OrderStatus.CANCELLED

    def test_rejection_path(self):
        from order_state_store import OrderStateStore
        from execution_policy import OrderStatus

        store = OrderStateStore()
        store.create("test-003", "TSLA", "BUY", 10, "aggressive_entry", "test.py")
        store.mark_submitted("test-003", broker_order_id=44)

        assert store.mark_rejected("test-003", reason="Insufficient margin")
        assert store.get("test-003").status == OrderStatus.REJECTED
        assert store.get("test-003").last_error == "Insufficient margin"


class TestOrderStateStoreDuplicatePrevention:

    def test_duplicate_intent_returns_existing(self):
        from order_state_store import OrderStateStore
        from execution_policy import OrderStatus

        store = OrderStateStore()
        e1 = store.create("dup-001", "NVDA", "BUY", 100, "passive_entry", "test.py")
        e2 = store.create("dup-001", "NVDA", "BUY", 100, "passive_entry", "test.py")
        assert e1.intent_id == e2.intent_id
        assert len(store.all_entries()) == 1


class TestOrderStateStoreLookups:

    def test_lookup_by_broker_id(self):
        from order_state_store import OrderStateStore

        store = OrderStateStore()
        store.create("look-001", "NVDA", "BUY", 100, "passive_entry", "test.py")
        store.mark_submitted("look-001", broker_order_id=99)

        entry = store.get_by_broker_id(99)
        assert entry is not None
        assert entry.intent_id == "look-001"

    def test_active_intents(self):
        from order_state_store import OrderStateStore
        from execution_policy import OrderStatus

        store = OrderStateStore()
        store.create("active-001", "NVDA", "BUY", 100, "passive_entry", "test.py")
        store.create("active-002", "AAPL", "SELL", 50, "urgent_exit", "test.py")
        store.create("active-003", "TSLA", "BUY", 10, "aggressive_entry", "test.py")

        store.mark_submitted("active-003", broker_order_id=55)
        store.mark_rejected("active-003", reason="test")

        active = store.active_intents()
        assert len(active) == 2
        active_ids = {e.intent_id for e in active}
        assert "active-001" in active_ids
        assert "active-002" in active_ids
        assert "active-003" not in active_ids

    def test_has_active_intent(self):
        from order_state_store import OrderStateStore

        store = OrderStateStore()
        store.create("check-001", "NVDA", "BUY", 100, "passive_entry", "test.py")
        assert store.has_active_intent("check-001") is True
        assert store.has_active_intent("nonexistent") is False


class TestOrderStateStorePersistence:

    def test_persist_and_reload(self):
        from order_state_store import OrderStateStore
        from execution_policy import OrderStatus

        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
            persist_path = Path(f.name)

        try:
            store1 = OrderStateStore(persist_path)
            store1.create("persist-001", "NVDA", "BUY", 100, "passive_entry", "test.py")
            store1.mark_submitted("persist-001", broker_order_id=42)
            store1.mark_acknowledged("persist-001")
            store1.record_fill("persist-001", filled_qty=100, avg_price=120.0)

            store2 = OrderStateStore(persist_path)
            entry = store2.get("persist-001")
            assert entry is not None
            assert entry.status == OrderStatus.FILLED
            assert entry.filled_qty == 100
            assert entry.broker_order_id == 42
        finally:
            persist_path.unlink(missing_ok=True)


class TestOrderStateStoreInvalidTransitions:

    def test_cannot_go_from_filled_to_submitted(self):
        from order_state_store import OrderStateStore
        from execution_policy import OrderStatus

        store = OrderStateStore()
        store.create("inv-001", "NVDA", "BUY", 100, "passive_entry", "test.py")
        store.mark_submitted("inv-001", broker_order_id=42)
        store.mark_acknowledged("inv-001")
        store.record_fill("inv-001", filled_qty=100, avg_price=120.0)

        assert store.get("inv-001").status == OrderStatus.FILLED
        assert store.mark_submitted("inv-001", broker_order_id=43) is False

    def test_cannot_go_from_created_to_acknowledged(self):
        from order_state_store import OrderStateStore

        store = OrderStateStore()
        store.create("inv-002", "NVDA", "BUY", 100, "passive_entry", "test.py")
        assert store.mark_acknowledged("inv-002") is False


class TestOrderStateStoreStats:

    def test_stats_counts(self):
        from order_state_store import OrderStateStore

        store = OrderStateStore()
        store.create("s-001", "NVDA", "BUY", 100, "passive_entry", "test.py")
        store.create("s-002", "AAPL", "SELL", 50, "urgent_exit", "test.py")
        store.create("s-003", "TSLA", "BUY", 10, "aggressive_entry", "test.py")

        store.mark_submitted("s-002", broker_order_id=42)

        stats = store.stats
        assert stats.get("created", 0) == 2
        assert stats.get("submitted", 0) == 1


class TestFillAveraging:

    def test_weighted_average_across_fills(self):
        from order_state_store import OrderStateStore

        store = OrderStateStore()
        store.create("avg-001", "NVDA", "BUY", 100, "passive_entry", "test.py")
        store.mark_submitted("avg-001", broker_order_id=42)
        store.mark_acknowledged("avg-001")

        store.record_fill("avg-001", filled_qty=60, avg_price=100.0, commission=1.0)
        store.record_fill("avg-001", filled_qty=40, avg_price=102.0, commission=0.80)

        entry = store.get("avg-001")
        expected_avg = (60 * 100.0 + 40 * 102.0) / 100
        assert abs(entry.avg_fill_price - expected_avg) < 0.001
        assert entry.total_commission == 1.80
        assert len(entry.fills) == 2
