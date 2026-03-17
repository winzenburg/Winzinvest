"""
Integration tests: short-side, pairs two-leg-with-flatten, and webhook signal
flows through the OrderRouter foundation.

All IB interactions are mocked. These tests verify the higher-level
orchestration logic that each executor performs — not the executors
themselves, but the same OrderRouter/policy/factory pipeline they use.

Run with: pytest trading/tests/test_executor_integration.py -v
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------


def _mock_ib(fill_price: float = 150.0, fill_qty: int = 50) -> MagicMock:
    """Create a mock IB that always fills at the given price/qty."""
    ib = MagicMock()
    ib.isConnected.return_value = True

    mock_contract = MagicMock()
    mock_contract.conId = 12345
    mock_contract.symbol = "TEST"
    mock_contract.secType = "STK"
    mock_contract.exchange = "SMART"
    mock_contract.primaryExchange = "NASDAQ"
    mock_contract.currency = "USD"

    async def qualify(*_a, **_kw):
        return [mock_contract]
    ib.qualifyContractsAsync = qualify

    ib.openTrades.return_value = []
    ib.positions.return_value = []

    _status_handler = None

    def capture_place_order(contract, order):
        nonlocal _status_handler
        trade = MagicMock()
        trade.order = MagicMock()
        trade.order.orderId = 1001
        trade.order.permId = 9001
        trade.fills = []

        status = MagicMock()
        status.status = "Filled"
        status.filled = fill_qty
        status.avgFillPrice = fill_price
        trade.orderStatus = status

        def add_status(self_mock, handler):
            nonlocal _status_handler
            _status_handler = handler
            return self_mock
        trade.statusEvent = MagicMock()
        trade.statusEvent.__iadd__ = add_status
        trade.fillEvent = MagicMock()
        trade.fillEvent.__iadd__ = MagicMock(return_value=trade.fillEvent)

        async def fire():
            await asyncio.sleep(0.01)
            if _status_handler:
                _status_handler(trade)

        asyncio.get_event_loop().call_soon(lambda: asyncio.ensure_future(fire()))
        return trade

    ib.placeOrder = capture_place_order
    ib.cancelOrder = MagicMock()
    return ib


def _mock_ib_sequential(fill_sequence: list[dict]) -> MagicMock:
    """Create a mock IB where each successive placeOrder uses the next entry.

    ``fill_sequence`` is a list of dicts, each with optional keys:
      - ``fills`` (bool): whether this call fills (default True)
      - ``price`` (float): fill price (default 100.0)
      - ``qty``   (int):   filled qty (default 50)
    """
    ib = MagicMock()
    ib.isConnected.return_value = True

    mock_contract = MagicMock()
    mock_contract.conId = 12345
    mock_contract.symbol = "TEST"
    mock_contract.secType = "STK"
    mock_contract.exchange = "SMART"
    mock_contract.primaryExchange = "NASDAQ"
    mock_contract.currency = "USD"

    async def qualify(*_a, **_kw):
        return [mock_contract]
    ib.qualifyContractsAsync = qualify

    ib.openTrades.return_value = []
    ib.positions.return_value = []

    call_idx = {"n": 0}

    def capture_place_order(contract, order):
        idx = call_idx["n"]
        call_idx["n"] += 1

        spec = fill_sequence[idx] if idx < len(fill_sequence) else {}
        does_fill = spec.get("fills", True)
        price = spec.get("price", 100.0)
        qty = spec.get("qty", 50)

        trade = MagicMock()
        trade.order = MagicMock()
        trade.order.orderId = 2000 + idx
        trade.order.permId = 8000 + idx
        trade.fills = []

        if does_fill:
            trade.orderStatus.status = "Filled"
            trade.orderStatus.filled = qty
            trade.orderStatus.avgFillPrice = price
        else:
            trade.orderStatus.status = "Cancelled"
            trade.orderStatus.filled = 0
            trade.orderStatus.avgFillPrice = 0.0

        _handler = None

        def add_status(self_mock, handler):
            nonlocal _handler
            _handler = handler
            return self_mock
        trade.statusEvent = MagicMock()
        trade.statusEvent.__iadd__ = add_status
        trade.fillEvent = MagicMock()
        trade.fillEvent.__iadd__ = MagicMock(return_value=trade.fillEvent)

        async def fire():
            await asyncio.sleep(0.01)
            if _handler:
                _handler(trade)

        asyncio.get_event_loop().call_soon(lambda: asyncio.ensure_future(fire()))
        return trade

    ib.placeOrder = capture_place_order
    ib.cancelOrder = MagicMock()
    return ib


def _mock_resolved(symbol: str = "TEST", con_id: int = 12345):
    r = MagicMock()
    r.con_id = con_id
    r.symbol = symbol
    r.sec_type = "STK"
    r.exchange = "SMART"
    r.primary_exchange = "NASDAQ"
    r.currency = "USD"
    r.ib_contract = MagicMock()
    r.ib_contract.conId = con_id
    r.key = f"{con_id}@SMART"
    return r


# ===========================================================================
# Short-side flow (execute_candidates pattern)
# ===========================================================================


@pytest.mark.asyncio
class TestShortSideFlow:
    """Simulates the execute_candidates.py short-side execution path."""

    async def test_short_entry_with_trailing_stop_and_tp(self):
        """SELL entry fill -> trailing stop (BUY) + take-profit (BUY)."""
        from atr_stops import compute_stop_tp, compute_trailing_amount
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter

        fill_price = 85.0
        fill_qty = 30
        atr = 2.0

        ib = _mock_ib(fill_price=fill_price, fill_qty=fill_qty)
        resolved = _mock_resolved("WEAK")
        router = OrderRouter(ib, fill_timeout=2.0)
        await router.startup()

        entry_intent = build_intent(
            symbol="WEAK", side="SELL", quantity=fill_qty,
            policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script="execute_candidates.py",
            limit_price=85.20,
            metadata={"regime": "STRONG_DOWNTREND", "conviction": 0.75},
        )

        result = await router.submit(entry_intent, resolved=resolved, bid=85.00)

        assert result.success
        assert result.is_filled
        assert result.avg_fill_price == fill_price

        stop_price, tp_price = compute_stop_tp(result.avg_fill_price, "SELL", atr=atr)

        assert stop_price > result.avg_fill_price, "Short stop must be above entry"
        assert tp_price < result.avg_fill_price, "Short TP must be below entry"

        trail_amt = compute_trailing_amount(atr=atr, entry_price=result.avg_fill_price)
        assert trail_amt > 0

        trailing_intent = build_intent(
            symbol="WEAK", side="BUY", quantity=fill_qty,
            policy=ExecutionPolicy.TRAILING_STOP,
            source_script="execute_candidates.py",
            trail_amount=trail_amt,
        )
        tp_intent = build_intent(
            symbol="WEAK", side="BUY", quantity=fill_qty,
            policy=ExecutionPolicy.PASSIVE_ENTRY,
            source_script="execute_candidates.py",
            limit_price=tp_price,
        )

        protective = await router.submit_protective_orders(
            parent_result=result,
            follow_ups=[trailing_intent, tp_intent],
            resolved=resolved,
        )

        assert len(protective) == 2
        for pr in protective:
            assert pr.success, f"Protective order should succeed: {pr.error}"

        store = router.state_store
        assert store.get(entry_intent["intent_id"]) is not None
        assert store.get(trailing_intent["intent_id"]) is not None
        assert store.get(tp_intent["intent_id"]) is not None

    async def test_short_entry_gates_metadata_preserved(self):
        """State store preserves short-specific metadata for audit trail."""
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter

        ib = _mock_ib(fill_price=42.0, fill_qty=100)
        resolved = _mock_resolved("BEAR")
        router = OrderRouter(ib, fill_timeout=2.0)
        await router.startup()

        intent = build_intent(
            symbol="BEAR", side="SELL", quantity=100,
            policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script="execute_candidates.py",
            limit_price=42.50,
            metadata={
                "regime": "UNFAVORABLE",
                "conviction": 0.9,
                "score": -0.85,
                "momentum": -0.03,
            },
        )

        result = await router.submit(intent, resolved=resolved, bid=42.00)
        assert result.is_filled

        entry = router.state_store.get(intent["intent_id"])
        assert entry is not None
        assert entry.metadata["regime"] == "UNFAVORABLE"
        assert entry.metadata["conviction"] == 0.9
        assert entry.metadata["score"] == -0.85

    async def test_short_entry_unfilled_records_no_protectives(self):
        """Unfilled short entry must not produce protective orders."""
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter, SubmitResult

        ib = _mock_ib()
        router = OrderRouter(ib, fill_timeout=0.5)
        await router.startup()

        fake_result = SubmitResult(
            success=False, intent_id="fake-short-001",
            status=None, error="Cancelled",
        )

        trailing = build_intent(
            symbol="WEAK", side="BUY", quantity=50,
            policy=ExecutionPolicy.TRAILING_STOP,
            source_script="execute_candidates.py",
            trail_amount=3.0,
        )

        results = await router.submit_protective_orders(
            parent_result=fake_result, follow_ups=[trailing],
        )
        assert len(results) == 0

    async def test_short_and_long_intents_are_distinct(self):
        """Same symbol BUY vs SELL produces different intent IDs."""
        from execution_policy import ExecutionPolicy, build_intent

        short = build_intent(
            symbol="TSLA", side="SELL", quantity=20,
            policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script="execute_candidates.py",
            limit_price=300.0,
        )
        long = build_intent(
            symbol="TSLA", side="BUY", quantity=20,
            policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script="execute_candidates.py",
            limit_price=300.0,
        )
        assert short["intent_id"] != long["intent_id"]


# ===========================================================================
# Pairs two-leg-with-flatten flow (execute_pairs pattern)
# ===========================================================================


@pytest.mark.asyncio
class TestPairsTwoLegFlow:
    """Simulates execute_pairs.py's simultaneous long/short with flatten logic."""

    async def test_both_legs_fill_with_protective_orders(self):
        """Long leg fills, short leg fills -> protective orders for both."""
        from atr_stops import compute_stop_tp
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter

        ib = _mock_ib_sequential([
            {"fills": True, "price": 120.0, "qty": 40},   # long leg
            {"fills": True, "price": 80.0,  "qty": 60},   # short leg
            {"fills": True, "price": 119.0, "qty": 40},   # long stop
            {"fills": True, "price": 125.0, "qty": 40},   # long TP
            {"fills": True, "price": 81.0,  "qty": 60},   # short stop
            {"fills": True, "price": 75.0,  "qty": 60},   # short TP
        ])
        resolved_long = _mock_resolved("STRONG", con_id=11111)
        resolved_short = _mock_resolved("WEAK", con_id=22222)
        router = OrderRouter(ib, fill_timeout=2.0)
        await router.startup()

        long_intent = build_intent(
            symbol="STRONG", side="BUY", quantity=40,
            policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script="execute_pairs.py",
            limit_price=120.0,
            metadata={"strategy": "pairs_long", "pair_short": "WEAK"},
        )
        long_result = await router.submit(
            long_intent, resolved=resolved_long, ask=120.0,
        )
        assert long_result.is_filled
        assert long_result.avg_fill_price == 120.0

        short_intent = build_intent(
            symbol="WEAK", side="SELL", quantity=60,
            policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script="execute_pairs.py",
            limit_price=80.0,
            metadata={"strategy": "pairs_short", "pair_long": "STRONG"},
        )
        short_result = await router.submit(
            short_intent, resolved=resolved_short, bid=80.0,
        )
        assert short_result.is_filled
        assert short_result.avg_fill_price == 80.0

        long_stop, long_tp = compute_stop_tp(120.0, "BUY", atr=3.0, stop_mult=2.0, tp_mult=3.0)
        short_stop, short_tp = compute_stop_tp(80.0, "SELL", atr=2.0, stop_mult=2.0, tp_mult=3.0)

        long_stop_intent = build_intent(
            symbol="STRONG", side="SELL", quantity=40,
            policy=ExecutionPolicy.STOP_PROTECT,
            source_script="execute_pairs.py",
            stop_price=long_stop, limit_price=long_stop,
        )
        long_tp_intent = build_intent(
            symbol="STRONG", side="SELL", quantity=40,
            policy=ExecutionPolicy.PASSIVE_ENTRY,
            source_script="execute_pairs.py",
            limit_price=long_tp,
        )

        long_protectives = await router.submit_protective_orders(
            parent_result=long_result,
            follow_ups=[long_stop_intent, long_tp_intent],
            resolved=resolved_long,
        )
        assert len(long_protectives) == 2
        assert all(p.success for p in long_protectives)

        short_stop_intent = build_intent(
            symbol="WEAK", side="BUY", quantity=60,
            policy=ExecutionPolicy.STOP_PROTECT,
            source_script="execute_pairs.py",
            stop_price=short_stop, limit_price=short_stop,
        )
        short_tp_intent = build_intent(
            symbol="WEAK", side="BUY", quantity=60,
            policy=ExecutionPolicy.PASSIVE_ENTRY,
            source_script="execute_pairs.py",
            limit_price=short_tp,
        )

        short_protectives = await router.submit_protective_orders(
            parent_result=short_result,
            follow_ups=[short_stop_intent, short_tp_intent],
            resolved=resolved_short,
        )
        assert len(short_protectives) == 2
        assert all(p.success for p in short_protectives)

        store = router.state_store
        assert store.get(long_intent["intent_id"]) is not None
        assert store.get(short_intent["intent_id"]) is not None
        assert store.get(long_stop_intent["intent_id"]) is not None
        assert store.get(long_tp_intent["intent_id"]) is not None
        assert store.get(short_stop_intent["intent_id"]) is not None
        assert store.get(short_tp_intent["intent_id"]) is not None

        long_entry = store.get(long_intent["intent_id"])
        assert long_entry is not None and long_entry.filled_qty == 40
        short_entry = store.get(short_intent["intent_id"])
        assert short_entry is not None and short_entry.filled_qty == 60

    async def test_short_leg_fails_triggers_flatten_of_long(self):
        """If short leg doesn't fill, the long leg is immediately flattened.

        This is the critical pairs safety mechanism: no naked positions.
        """
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter

        ib = _mock_ib_sequential([
            {"fills": True, "price": 120.0, "qty": 40},   # long leg fills
            {"fills": False},                                # short leg fails
            {"fills": True, "price": 119.50, "qty": 40},  # flatten long
        ])
        resolved_long = _mock_resolved("STRONG", con_id=11111)
        resolved_short = _mock_resolved("WEAK", con_id=22222)
        router = OrderRouter(ib, fill_timeout=2.0)
        await router.startup()

        long_intent = build_intent(
            symbol="STRONG", side="BUY", quantity=40,
            policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script="execute_pairs.py",
            limit_price=120.0,
        )
        long_result = await router.submit(
            long_intent, resolved=resolved_long, ask=120.0,
        )
        assert long_result.is_filled, "Long leg should fill"

        short_intent = build_intent(
            symbol="WEAK", side="SELL", quantity=60,
            policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script="execute_pairs.py",
            limit_price=80.0,
        )
        short_result = await router.submit(
            short_intent, resolved=resolved_short, bid=80.0,
        )

        short_filled = short_result.is_filled or short_result.is_partial
        assert not short_filled, "Short leg should NOT fill"

        flatten_intent = build_intent(
            symbol="STRONG", side="SELL",
            quantity=long_result.filled_qty,
            policy=ExecutionPolicy.URGENT_EXIT,
            source_script="execute_pairs.py",
            metadata={"reason": "pair_short_leg_failed", "pair_short": "WEAK"},
        )
        flatten_result = await router.submit(
            flatten_intent, resolved=resolved_long,
        )
        assert flatten_result.success, "Flatten should succeed"

        store = router.state_store
        entry = store.get(flatten_intent["intent_id"])
        assert entry is not None
        assert entry.metadata["reason"] == "pair_short_leg_failed"

    async def test_long_leg_fails_aborts_pair_no_flatten_needed(self):
        """If the long leg itself doesn't fill, abort — nothing to flatten."""
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter

        ib = _mock_ib_sequential([{"fills": False}])
        resolved = _mock_resolved("STRONG", con_id=11111)
        router = OrderRouter(ib, fill_timeout=2.0)
        await router.startup()

        long_intent = build_intent(
            symbol="STRONG", side="BUY", quantity=40,
            policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script="execute_pairs.py",
            limit_price=120.0,
        )
        long_result = await router.submit(long_intent, resolved=resolved, ask=120.0)

        long_filled = long_result.is_filled or long_result.is_partial
        assert not long_filled
        assert len(router.state_store.active_intents()) == 0


# ===========================================================================
# Webhook signal flow (execute_webhook_signal pattern)
# ===========================================================================


@pytest.mark.asyncio
class TestWebhookSignalFlow:
    """Simulates execute_webhook_signal.py's one-shot execution paths."""

    async def test_standard_buy_signal_with_stop_and_tp(self):
        """Standard momentum BUY -> STOP_PROTECT + PASSIVE_ENTRY TP."""
        from atr_stops import compute_stop_tp
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter

        fill_price = 210.0
        fill_qty = 25
        atr = 4.5

        ib = _mock_ib(fill_price=fill_price, fill_qty=fill_qty)
        resolved = _mock_resolved("AAPL")
        router = OrderRouter(ib, fill_timeout=2.0)
        await router.startup()

        entry_intent = build_intent(
            symbol="AAPL", side="BUY", quantity=fill_qty,
            policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script="execute_webhook_signal.py",
            limit_price=210.50,
            metadata={
                "signal_price": 210.50,
                "entry_type": "standard",
                "timeframe": "D",
            },
        )

        result = await router.submit(entry_intent, resolved=resolved, ask=210.10)
        assert result.is_filled
        assert result.avg_fill_price == fill_price

        stop_price, tp_price = compute_stop_tp(fill_price, "BUY", atr=atr)
        exit_side = "SELL"

        stop_intent = build_intent(
            symbol="AAPL", side=exit_side, quantity=fill_qty,
            policy=ExecutionPolicy.STOP_PROTECT,
            source_script="execute_webhook_signal.py",
            stop_price=stop_price, limit_price=stop_price,
        )
        tp_intent = build_intent(
            symbol="AAPL", side=exit_side, quantity=fill_qty,
            policy=ExecutionPolicy.PASSIVE_ENTRY,
            source_script="execute_webhook_signal.py",
            limit_price=tp_price,
        )

        protective = await router.submit_protective_orders(
            parent_result=result,
            follow_ups=[stop_intent, tp_intent],
            resolved=resolved,
        )

        assert len(protective) == 2
        assert all(p.success for p in protective)

    async def test_pullback_buy_with_trailing_stop(self):
        """Pullback BUY entry -> tighter trailing stop + take-profit."""
        from atr_stops import compute_stop_tp, compute_trailing_amount
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter

        fill_price = 155.0
        fill_qty = 40
        atr = 3.0
        pullback_stop_mult = 1.0
        pullback_tp_mult = 2.5

        ib = _mock_ib(fill_price=fill_price, fill_qty=fill_qty)
        resolved = _mock_resolved("MSFT")
        router = OrderRouter(ib, fill_timeout=2.0)
        await router.startup()

        entry_intent = build_intent(
            symbol="MSFT", side="BUY", quantity=fill_qty,
            policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script="execute_webhook_signal.py",
            limit_price=155.50,
            metadata={"entry_type": "pullback", "timeframe": "D"},
        )

        result = await router.submit(entry_intent, resolved=resolved, ask=155.10)
        assert result.is_filled

        stop_price, tp_price = compute_stop_tp(
            fill_price, "BUY", atr=atr,
            stop_mult=pullback_stop_mult, tp_mult=pullback_tp_mult,
        )

        assert stop_price > fill_price - atr * 1.5, "Pullback stop is tighter than standard"

        trail_amt = compute_trailing_amount(
            atr=atr, entry_price=fill_price, trailing_mult=1.5,
        )

        trailing_intent = build_intent(
            symbol="MSFT", side="SELL", quantity=fill_qty,
            policy=ExecutionPolicy.TRAILING_STOP,
            source_script="execute_webhook_signal.py",
            trail_amount=trail_amt,
        )
        tp_intent = build_intent(
            symbol="MSFT", side="SELL", quantity=fill_qty,
            policy=ExecutionPolicy.PASSIVE_ENTRY,
            source_script="execute_webhook_signal.py",
            limit_price=tp_price,
        )

        protective = await router.submit_protective_orders(
            parent_result=result,
            follow_ups=[trailing_intent, tp_intent],
            resolved=resolved,
        )

        assert len(protective) == 2
        assert all(p.success for p in protective)

        store = router.state_store
        entry = store.get(trailing_intent["intent_id"])
        assert entry is not None

    async def test_standard_sell_signal(self):
        """Webhook SELL (short entry) with stop above and TP below."""
        from atr_stops import compute_stop_tp
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter

        fill_price = 90.0
        fill_qty = 60
        atr = 2.5

        ib = _mock_ib(fill_price=fill_price, fill_qty=fill_qty)
        resolved = _mock_resolved("UBER")
        router = OrderRouter(ib, fill_timeout=2.0)
        await router.startup()

        entry = build_intent(
            symbol="UBER", side="SELL", quantity=fill_qty,
            policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script="execute_webhook_signal.py",
            limit_price=90.20,
        )

        result = await router.submit(entry, resolved=resolved, bid=90.00)
        assert result.is_filled

        stop_price, tp_price = compute_stop_tp(fill_price, "SELL", atr=atr)
        assert stop_price > fill_price, "Short stop is above entry"
        assert tp_price < fill_price, "Short TP is below entry"

        stop_intent = build_intent(
            symbol="UBER", side="BUY", quantity=fill_qty,
            policy=ExecutionPolicy.STOP_PROTECT,
            source_script="execute_webhook_signal.py",
            stop_price=stop_price, limit_price=stop_price,
        )
        tp_intent = build_intent(
            symbol="UBER", side="BUY", quantity=fill_qty,
            policy=ExecutionPolicy.PASSIVE_ENTRY,
            source_script="execute_webhook_signal.py",
            limit_price=tp_price,
        )

        protective = await router.submit_protective_orders(
            parent_result=result,
            follow_ups=[stop_intent, tp_intent],
            resolved=resolved,
        )

        assert len(protective) == 2
        assert all(p.success for p in protective)

    async def test_unfilled_webhook_produces_no_protectives(self):
        """If webhook entry doesn't fill, no protective orders are placed."""
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter, SubmitResult

        ib = _mock_ib()
        router = OrderRouter(ib, fill_timeout=0.5)
        await router.startup()

        fake_result = SubmitResult(
            success=False, intent_id="webhook-fake-001",
            status=None, error="Cancelled by timeout",
        )

        stop = build_intent(
            symbol="AAPL", side="SELL", quantity=25,
            policy=ExecutionPolicy.STOP_PROTECT,
            source_script="execute_webhook_signal.py",
            stop_price=200.0, limit_price=200.0,
        )

        results = await router.submit_protective_orders(
            parent_result=fake_result, follow_ups=[stop],
        )
        assert len(results) == 0

    async def test_webhook_idempotency_prevents_double_fill(self):
        """Same webhook signal submitted twice is rejected by router."""
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter

        ib = _mock_ib(fill_price=150.0, fill_qty=30)
        resolved = _mock_resolved("GOOG")
        router = OrderRouter(ib, fill_timeout=2.0)
        await router.startup()

        intent = build_intent(
            symbol="GOOG", side="BUY", quantity=30,
            policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script="execute_webhook_signal.py",
            limit_price=150.0,
        )

        r1 = await router.submit(intent, resolved=resolved, ask=150.10)
        r2 = await router.submit(intent, resolved=resolved, ask=150.10)

        assert r1.success
        assert not r2.success
        assert "Duplicate" in (r2.error or "")
