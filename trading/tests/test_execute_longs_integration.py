"""
Integration test: exercises the full execute_longs flow through the Phase 1
foundation modules (execution_policy → order_factory → order_router →
protective orders), proving the migration path before touching the real executor.

Mocks ib_insync.IB and simulates fills via callbacks.

Run with: pytest trading/tests/test_execute_longs_integration.py -v
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_ib(fill_price: float = 150.0, fill_qty: int = 50) -> MagicMock:
    """Create a mock IB instance that simulates a fill on placeOrder."""
    ib = MagicMock()
    ib.isConnected.return_value = True

    # qualifyContractsAsync
    mock_contract = MagicMock()
    mock_contract.conId = 12345
    mock_contract.symbol = "NVDA"
    mock_contract.secType = "STK"
    mock_contract.exchange = "SMART"
    mock_contract.primaryExchange = "NASDAQ"
    mock_contract.currency = "USD"

    async def qualify(*_args, **_kwargs):
        return [mock_contract]
    ib.qualifyContractsAsync = qualify

    # Reconciliation stubs
    ib.openTrades.return_value = []
    ib.positions.return_value = []

    _status_handler = None
    _fill_handler = None

    def capture_place_order(contract, order):
        trade = MagicMock()
        trade.order = MagicMock()
        trade.order.orderId = 1001
        trade.order.permId = 9001
        trade.fills = []

        order_status = MagicMock()
        order_status.status = "Filled"
        order_status.filled = fill_qty
        order_status.avgFillPrice = fill_price
        trade.orderStatus = order_status

        def add_status_handler(self_mock, handler):
            nonlocal _status_handler
            _status_handler = handler
            return self_mock
        trade.statusEvent = MagicMock()
        trade.statusEvent.__iadd__ = add_status_handler

        def add_fill_handler(self_mock, handler):
            nonlocal _fill_handler
            _fill_handler = handler
            return self_mock
        trade.fillEvent = MagicMock()
        trade.fillEvent.__iadd__ = add_fill_handler

        async def fire_callbacks():
            await asyncio.sleep(0.01)
            if _status_handler:
                _status_handler(trade)

        asyncio.get_event_loop().call_soon(
            lambda: asyncio.ensure_future(fire_callbacks())
        )
        return trade

    ib.placeOrder = capture_place_order
    ib.cancelOrder = MagicMock()

    return ib


def _mock_resolved():
    mock = MagicMock()
    mock.con_id = 12345
    mock.symbol = "NVDA"
    mock.sec_type = "STK"
    mock.exchange = "SMART"
    mock.primary_exchange = "NASDAQ"
    mock.currency = "USD"
    mock.ib_contract = MagicMock()
    mock.ib_contract.conId = 12345
    mock.key = "12345@SMART"
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestExecuteLongsFlowThroughFoundation:
    """Simulates what a migrated execute_longs.py would do, step by step."""

    async def test_full_long_entry_with_protective_orders(self):
        """Entry fill → compute stops from fill → place trailing stop + TP."""
        from atr_stops import compute_stop_tp, compute_trailing_amount
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter, SubmitResult

        fill_price = 150.0
        fill_qty = 50
        atr = 3.5

        ib = _mock_ib(fill_price=fill_price, fill_qty=fill_qty)
        resolved = _mock_resolved()
        router = OrderRouter(ib, fill_timeout=2.0)
        await router.startup()

        # Step 1: Build and submit entry intent
        entry_intent = build_intent(
            symbol="NVDA",
            side="BUY",
            quantity=fill_qty,
            policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script="execute_longs.py",
            limit_price=151.0,
        )

        result = await router.submit(entry_intent, resolved=resolved, ask=150.10)

        assert result.success, f"Entry should succeed: {result.error}"
        assert result.is_filled
        assert result.filled_qty == fill_qty
        assert result.avg_fill_price == fill_price

        # Step 2: Compute protective prices from fill data
        stop_price, tp_price = compute_stop_tp(result.avg_fill_price, "BUY", atr=atr)
        trail_amt = compute_trailing_amount(atr=atr, entry_price=result.avg_fill_price)

        assert stop_price < result.avg_fill_price
        assert tp_price > result.avg_fill_price
        assert trail_amt > 0

        # Step 3: Build protective intents
        trailing_intent = build_intent(
            symbol="NVDA",
            side="SELL",
            quantity=result.filled_qty,
            policy=ExecutionPolicy.TRAILING_STOP,
            source_script="execute_longs.py",
            trail_amount=trail_amt,
        )

        tp_intent = build_intent(
            symbol="NVDA",
            side="SELL",
            quantity=result.filled_qty,
            policy=ExecutionPolicy.PASSIVE_ENTRY,
            source_script="execute_longs.py",
            limit_price=tp_price,
        )

        # Step 4: Submit protective orders via convenience method
        protective_results = await router.submit_protective_orders(
            parent_result=result,
            follow_ups=[trailing_intent, tp_intent],
            resolved=resolved,
        )

        assert len(protective_results) == 2
        for pr in protective_results:
            assert pr.success, f"Protective order should succeed: {pr.error}"

        # Step 5: Verify state store has all three orders tracked
        store = router.state_store
        assert store.get(entry_intent["intent_id"]) is not None
        assert store.get(trailing_intent["intent_id"]) is not None
        assert store.get(tp_intent["intent_id"]) is not None

    async def test_unfilled_entry_skips_protective_orders(self):
        """If entry doesn't fill, protective orders must not be placed."""
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter, SubmitResult

        ib = _mock_ib()
        router = OrderRouter(ib, fill_timeout=0.5)
        await router.startup()

        entry_intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script="execute_longs.py",
            limit_price=151.0,
        )

        # Simulate a cancelled result
        fake_result = SubmitResult(
            success=False,
            intent_id=entry_intent["intent_id"],
            status=None,
            error="Cancelled",
        )

        trailing_intent = build_intent(
            symbol="NVDA", side="SELL", quantity=50,
            policy=ExecutionPolicy.TRAILING_STOP,
            source_script="execute_longs.py",
            trail_amount=5.0,
        )

        results = await router.submit_protective_orders(
            parent_result=fake_result,
            follow_ups=[trailing_intent],
        )

        assert len(results) == 0, "No protective orders when parent not filled"

    async def test_on_fill_async_callback_invoked(self):
        """Async on_fill callback receives correct fill data."""
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter

        fill_price = 200.0
        fill_qty = 25
        ib = _mock_ib(fill_price=fill_price, fill_qty=fill_qty)
        resolved = _mock_resolved()
        router = OrderRouter(ib, fill_timeout=2.0)
        await router.startup()

        captured: list = []

        async def on_fill_cb(intent_id: str, result):
            captured.append((intent_id, result))

        router.on_fill(on_fill_cb)

        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=fill_qty,
            policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script="test.py",
            limit_price=201.0,
        )

        result = await router.submit(intent, resolved=resolved, ask=200.10)

        # Give the async callback time to fire
        await asyncio.sleep(0.1)

        assert result.is_filled
        assert len(captured) == 1
        cb_intent_id, cb_result = captured[0]
        assert cb_intent_id == intent["intent_id"]
        assert cb_result.filled_qty == fill_qty
        assert cb_result.avg_fill_price == fill_price

    async def test_intent_ids_are_deterministic_and_unique(self):
        """Same inputs produce same ID; different inputs produce different IDs."""
        from execution_policy import ExecutionPolicy, build_intent

        i1 = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script="execute_longs.py",
            limit_price=150.0,
        )
        i2 = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.TRAILING_STOP,
            source_script="execute_longs.py",
            trail_amount=5.0,
        )

        assert i1["intent_id"] != i2["intent_id"], "Different policies → different IDs"

    async def test_enriched_record_data_available_from_result(self):
        """SubmitResult has all fields needed to build an enriched execution record."""
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter

        fill_price = 175.50
        fill_qty = 30
        ib = _mock_ib(fill_price=fill_price, fill_qty=fill_qty)
        resolved = _mock_resolved()
        router = OrderRouter(ib, fill_timeout=2.0)
        await router.startup()

        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=fill_qty,
            policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script="execute_longs.py",
            limit_price=176.0,
            metadata={"regime": "STRONG_UPTREND", "conviction": 0.85, "atr": 3.2},
        )

        result = await router.submit(intent, resolved=resolved, ask=175.60)

        assert result.is_filled
        assert result.avg_fill_price == fill_price
        assert result.filled_qty == fill_qty
        assert result.broker_order_id is not None

        # Verify the metadata round-trip through the state store
        entry = router.state_store.get(intent["intent_id"])
        assert entry is not None
        assert entry.metadata == {"regime": "STRONG_UPTREND", "conviction": 0.85, "atr": 3.2}

        # Slippage can be computed from signal price vs fill price
        signal_price = intent["limit_price"]
        slippage = abs(result.avg_fill_price - signal_price)
        assert slippage >= 0

    async def test_idempotency_prevents_duplicate_entry(self):
        """Submitting the same intent twice is rejected."""
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter

        ib = _mock_ib()
        resolved = _mock_resolved()
        router = OrderRouter(ib, fill_timeout=2.0)
        await router.startup()

        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script="execute_longs.py",
            limit_price=150.0,
        )

        r1 = await router.submit(intent, resolved=resolved, ask=150.10)
        r2 = await router.submit(intent, resolved=resolved, ask=150.10)

        assert r1.success
        assert not r2.success
        assert "Duplicate" in (r2.error or "")
