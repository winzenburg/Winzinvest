"""
Tests for order_router — the central submission pipeline.

All IB interactions are mocked. These tests verify:
  - Reconciliation gate (must call startup before submit)
  - Full submit lifecycle (resolve → factory → place → fill)
  - Idempotent duplicate rejection
  - Cancel flow
  - Bounded retries on transient failures
  - Event-driven fill tracking (no polling)
  - Partial fill + timeout → cancel
  - Child order placement (brackets)
  - on_fill callback invocation

Run with: pytest trading/tests/test_order_router.py -v
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_mock_ib() -> MagicMock:
    """Create a mock IB connection with the minimum API surface."""
    ib = MagicMock()
    ib.positions.return_value = []
    ib.openTrades.return_value = []
    ib.accountValues.return_value = []
    return ib


def _make_mock_trade(
    order_id: int = 1,
    status: str = "Filled",
    filled: int = 50,
    avg_price: float = 120.0,
    perm_id: int = 999,
) -> MagicMock:
    """Create a mock Trade with realistic attributes."""
    trade = MagicMock()

    trade.order.orderId = order_id
    trade.order.permId = perm_id
    trade.order.orderRef = ""
    trade.order.action = "BUY"
    trade.order.totalQuantity = filled

    trade.orderStatus.status = status
    trade.orderStatus.filled = filled
    trade.orderStatus.avgFillPrice = avg_price

    trade.fills = []
    trade.isDone.return_value = status in ("Filled", "Cancelled", "Inactive")

    trade.statusEvent = MagicMock()
    trade.statusEvent.__iadd__ = MagicMock(return_value=trade.statusEvent)
    trade.fillEvent = MagicMock()
    trade.fillEvent.__iadd__ = MagicMock(return_value=trade.fillEvent)

    return trade


def _make_mock_resolved(symbol: str = "NVDA", con_id: int = 12345) -> MagicMock:
    """Create a mock ResolvedContract."""
    resolved = MagicMock()
    resolved.con_id = con_id
    resolved.symbol = symbol
    resolved.sec_type = "STK"
    resolved.exchange = "SMART"
    resolved.primary_exchange = "NASDAQ"
    resolved.currency = "USD"
    resolved.ib_contract = MagicMock()
    resolved.key = f"{con_id}@SMART"
    return resolved


# ---------------------------------------------------------------------------
# Reconciliation gate
# ---------------------------------------------------------------------------


class TestReconciliationGate:

    @pytest.mark.asyncio
    async def test_submit_before_startup_is_rejected(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter

        ib = _make_mock_ib()
        router = OrderRouter(ib)

        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.URGENT_EXIT,
            source_script="test.py",
        )

        result = await router.submit(intent)
        assert result.success is False
        assert "reconciled" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_startup_enables_submission(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter

        ib = _make_mock_ib()
        trade = _make_mock_trade()
        ib.placeOrder.return_value = trade

        router = OrderRouter(ib, fill_timeout=0.5)

        with patch.object(router._contract_cache, "resolve", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = _make_mock_resolved()
            report = await router.startup()
            assert report is not None
            assert router.is_reconciled

            intent = build_intent(
                symbol="NVDA", side="BUY", quantity=50,
                policy=ExecutionPolicy.URGENT_EXIT,
                source_script="test.py",
            )
            result = await router.submit(intent, wait_for_fill=False)
            assert result.success is True
            assert result.status.value == "submitted"


# ---------------------------------------------------------------------------
# Full submit lifecycle
# ---------------------------------------------------------------------------


class TestSubmitLifecycle:

    @pytest.mark.asyncio
    async def test_submit_with_pre_resolved_contract(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter

        ib = _make_mock_ib()
        trade = _make_mock_trade(order_id=42)
        ib.placeOrder.return_value = trade

        router = OrderRouter(ib, fill_timeout=0.5)
        await router.startup()

        resolved = _make_mock_resolved()
        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.URGENT_EXIT,
            source_script="test.py",
        )

        result = await router.submit(intent, resolved=resolved, wait_for_fill=False)
        assert result.success is True
        assert result.broker_order_id == 42
        ib.placeOrder.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_resolves_contract_if_not_provided(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter

        ib = _make_mock_ib()
        trade = _make_mock_trade()
        ib.placeOrder.return_value = trade

        router = OrderRouter(ib, fill_timeout=0.5)
        await router.startup()

        with patch.object(router._contract_cache, "resolve", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = _make_mock_resolved()

            intent = build_intent(
                symbol="NVDA", side="BUY", quantity=50,
                policy=ExecutionPolicy.URGENT_EXIT,
                source_script="test.py",
            )
            result = await router.submit(intent, wait_for_fill=False)
            assert result.success is True
            mock_resolve.assert_called_once_with("NVDA")

    @pytest.mark.asyncio
    async def test_submit_fails_on_contract_resolution_failure(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter

        ib = _make_mock_ib()
        router = OrderRouter(ib)
        await router.startup()

        with patch.object(router._contract_cache, "resolve", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = None

            intent = build_intent(
                symbol="BADTICKER", side="BUY", quantity=50,
                policy=ExecutionPolicy.URGENT_EXIT,
                source_script="test.py",
            )
            result = await router.submit(intent)
            assert result.success is False
            assert "resolution failed" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_state_store_tracks_submission(self):
        from execution_policy import ExecutionPolicy, OrderStatus, build_intent
        from order_router import OrderRouter

        ib = _make_mock_ib()
        trade = _make_mock_trade(order_id=77)
        ib.placeOrder.return_value = trade

        router = OrderRouter(ib, fill_timeout=0.5)
        await router.startup()

        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.URGENT_EXIT,
            source_script="test.py",
        )
        result = await router.submit(
            intent, resolved=_make_mock_resolved(), wait_for_fill=False,
        )

        entry = router.state_store.get(intent["intent_id"])
        assert entry is not None
        assert entry.broker_order_id == 77
        assert entry.status == OrderStatus.SUBMITTED


# ---------------------------------------------------------------------------
# Idempotency / duplicate rejection
# ---------------------------------------------------------------------------


class TestIdempotency:

    @pytest.mark.asyncio
    async def test_duplicate_intent_rejected(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter

        ib = _make_mock_ib()
        trade = _make_mock_trade()
        ib.placeOrder.return_value = trade

        router = OrderRouter(ib, fill_timeout=0.5)
        await router.startup()

        resolved = _make_mock_resolved()
        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.URGENT_EXIT,
            source_script="test.py",
        )

        r1 = await router.submit(intent, resolved=resolved, wait_for_fill=False)
        assert r1.success is True

        r2 = await router.submit(intent, resolved=resolved, wait_for_fill=False)
        assert r2.success is False
        assert "duplicate" in (r2.error or "").lower()

        assert ib.placeOrder.call_count == 1


# ---------------------------------------------------------------------------
# Cancel flow
# ---------------------------------------------------------------------------


class TestCancel:

    @pytest.mark.asyncio
    async def test_cancel_active_order(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter

        ib = _make_mock_ib()
        trade = _make_mock_trade(status="PreSubmitted")
        trade.isDone.return_value = False
        ib.placeOrder.return_value = trade

        router = OrderRouter(ib, fill_timeout=0.5)
        await router.startup()

        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.URGENT_EXIT,
            source_script="test.py",
        )
        await router.submit(intent, resolved=_make_mock_resolved(), wait_for_fill=False)

        ok = await router.cancel(intent["intent_id"])
        assert ok is True
        ib.cancelOrder.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_unknown_intent(self):
        from order_router import OrderRouter

        ib = _make_mock_ib()
        router = OrderRouter(ib)
        await router.startup()

        ok = await router.cancel("nonexistent-intent-id")
        assert ok is False


# ---------------------------------------------------------------------------
# Bounded retries
# ---------------------------------------------------------------------------


class TestBoundedRetries:

    @pytest.mark.asyncio
    async def test_retry_on_transient_place_error(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter

        ib = _make_mock_ib()

        call_count = 0
        good_trade = _make_mock_trade(order_id=99)

        def place_side_effect(contract, order):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Gateway timeout")
            return good_trade

        ib.placeOrder.side_effect = place_side_effect

        router = OrderRouter(ib, fill_timeout=0.5, max_retries=2, retry_backoff=0.01)
        await router.startup()

        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.URGENT_EXIT,
            source_script="test.py",
        )
        result = await router.submit(
            intent, resolved=_make_mock_resolved(), wait_for_fill=False,
        )
        assert result.success is True
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retries_are_bounded(self):
        from execution_policy import ExecutionPolicy, OrderStatus, build_intent
        from order_router import OrderRouter

        ib = _make_mock_ib()
        ib.placeOrder.side_effect = ConnectionError("Always fails")

        router = OrderRouter(ib, fill_timeout=0.5, max_retries=1, retry_backoff=0.01)
        await router.startup()

        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.URGENT_EXIT,
            source_script="test.py",
        )
        result = await router.submit(
            intent, resolved=_make_mock_resolved(), wait_for_fill=False,
        )
        assert result.success is False
        assert ib.placeOrder.call_count == 2  # 1 initial + 1 retry

        entry = router.state_store.get(intent["intent_id"])
        assert entry is not None
        assert entry.status == OrderStatus.ERROR


# ---------------------------------------------------------------------------
# Event-driven fill callbacks
# ---------------------------------------------------------------------------


class TestEventDrivenFills:

    @pytest.mark.asyncio
    async def test_status_callback_triggers_fill(self):
        from execution_policy import ExecutionPolicy, OrderStatus, build_intent
        from order_router import OrderRouter

        ib = _make_mock_ib()
        trade = _make_mock_trade(order_id=55, status="PreSubmitted", filled=0)
        trade.isDone.return_value = False

        status_handlers: list = []
        fill_handlers: list = []

        original_status_event = MagicMock()
        original_fill_event = MagicMock()

        def capture_status(self_mock, handler):
            status_handlers.append(handler)
            return self_mock
        original_status_event.__iadd__ = capture_status

        def capture_fill(self_mock, handler):
            fill_handlers.append(handler)
            return self_mock
        original_fill_event.__iadd__ = capture_fill

        trade.statusEvent = original_status_event
        trade.fillEvent = original_fill_event

        ib.placeOrder.return_value = trade

        router = OrderRouter(ib, fill_timeout=2.0)
        await router.startup()

        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.URGENT_EXIT,
            source_script="test.py",
        )

        submit_task = asyncio.create_task(
            router.submit(intent, resolved=_make_mock_resolved(), wait_for_fill=True)
        )

        await asyncio.sleep(0.05)

        trade.orderStatus.status = "Filled"
        trade.orderStatus.filled = 50
        trade.orderStatus.avgFillPrice = 120.50
        trade.isDone.return_value = True

        for handler in status_handlers:
            handler(trade)

        result = await asyncio.wait_for(submit_task, timeout=3.0)
        assert result.success is True
        assert result.filled_qty == 50
        assert result.avg_fill_price == 120.50
        assert result.status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_on_fill_callback_invoked(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter

        ib = _make_mock_ib()
        trade = _make_mock_trade(order_id=66, status="PreSubmitted", filled=0)
        trade.isDone.return_value = False

        status_handlers: list = []
        fill_handlers: list = []

        original_status_event = MagicMock()
        original_fill_event = MagicMock()

        def capture_status(self_mock, handler):
            status_handlers.append(handler)
            return self_mock
        original_status_event.__iadd__ = capture_status

        def capture_fill(self_mock, handler):
            fill_handlers.append(handler)
            return self_mock
        original_fill_event.__iadd__ = capture_fill

        trade.statusEvent = original_status_event
        trade.fillEvent = original_fill_event

        ib.placeOrder.return_value = trade

        router = OrderRouter(ib, fill_timeout=2.0)
        await router.startup()

        callback_calls: list = []
        router.on_fill(lambda iid, res: callback_calls.append((iid, res)))

        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.URGENT_EXIT,
            source_script="test.py",
        )

        task = asyncio.create_task(
            router.submit(intent, resolved=_make_mock_resolved(), wait_for_fill=True)
        )
        await asyncio.sleep(0.05)

        trade.orderStatus.status = "Filled"
        trade.orderStatus.filled = 50
        trade.orderStatus.avgFillPrice = 121.0
        for h in status_handlers:
            h(trade)

        await asyncio.wait_for(task, timeout=3.0)
        assert len(callback_calls) == 1
        assert callback_calls[0][0] == intent["intent_id"]
        assert callback_calls[0][1].is_filled


# ---------------------------------------------------------------------------
# Timeout handling
# ---------------------------------------------------------------------------


class TestTimeoutHandling:

    @pytest.mark.asyncio
    async def test_timeout_cancels_unfilled_order(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter

        ib = _make_mock_ib()
        trade = _make_mock_trade(order_id=88, status="PreSubmitted", filled=0)
        trade.isDone.return_value = False
        trade.statusEvent.__iadd__ = MagicMock(return_value=trade.statusEvent)
        trade.fillEvent.__iadd__ = MagicMock(return_value=trade.fillEvent)
        ib.placeOrder.return_value = trade

        router = OrderRouter(ib, fill_timeout=0.2)
        await router.startup()

        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.URGENT_EXIT,
            source_script="test.py",
        )

        result = await router.submit(
            intent, resolved=_make_mock_resolved(), wait_for_fill=True,
        )
        assert result.success is False
        assert "timeout" in (result.error or "").lower()
        ib.cancelOrder.assert_called()


# ---------------------------------------------------------------------------
# Factory error propagation
# ---------------------------------------------------------------------------


class TestFactoryErrors:

    @pytest.mark.asyncio
    async def test_factory_validation_error_propagated(self):
        from execution_policy import ExecutionPolicy, OrderStatus, build_intent
        from order_router import OrderRouter

        ib = _make_mock_ib()
        router = OrderRouter(ib)
        await router.startup()

        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.PASSIVE_ENTRY,
            source_script="test.py",
            limit_price=120.0,
        )

        with patch("order_router.build_orders", side_effect=ValueError("Missing bid/ask")):
            result = await router.submit(
                intent, resolved=_make_mock_resolved(), wait_for_fill=False,
            )
            assert result.success is False
            assert "factory error" in (result.error or "").lower()

            entry = router.state_store.get(intent["intent_id"])
            assert entry.status == OrderStatus.ERROR


# ---------------------------------------------------------------------------
# Child orders (brackets)
# ---------------------------------------------------------------------------


class TestChildOrders:

    @pytest.mark.asyncio
    async def test_bracket_places_parent_and_children(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter

        ib = _make_mock_ib()
        trade = _make_mock_trade(order_id=100)
        ib.placeOrder.return_value = trade

        router = OrderRouter(ib, fill_timeout=0.5)
        await router.startup()

        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.BRACKETED_SWING_ENTRY,
            source_script="test.py",
            limit_price=120.0, stop_price=115.0, take_profit_price=130.0,
        )
        result = await router.submit(
            intent, resolved=_make_mock_resolved(), wait_for_fill=False,
        )
        assert result.success is True
        assert ib.placeOrder.call_count == 3  # parent + stop + TP


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------


class TestShutdown:

    @pytest.mark.asyncio
    async def test_shutdown_clears_tracking(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter

        ib = _make_mock_ib()
        trade = _make_mock_trade()
        ib.placeOrder.return_value = trade

        router = OrderRouter(ib, fill_timeout=0.5)
        await router.startup()

        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.URGENT_EXIT,
            source_script="test.py",
        )
        await router.submit(intent, resolved=_make_mock_resolved(), wait_for_fill=False)

        await router.shutdown()
        assert len(router._active_trades) == 0
        assert len(router._fill_events) == 0
