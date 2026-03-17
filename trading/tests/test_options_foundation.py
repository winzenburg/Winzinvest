"""
Tests for options support in the execution foundation layer.

Verifies:
  - OrderIntent options fields (sec_type, expiry, strike, right)
  - build_intent() validation for options
  - generate_intent_id() produces unique IDs per strike/expiry/right
  - OrderRouter.submit() routes OPT intents to resolve_option()
  - order_factory applies 0.05 tick size for option contracts

Run with: pytest trading/tests/test_options_foundation.py -v
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def _make_mock_ib() -> MagicMock:
    ib = MagicMock()
    ib.positions.return_value = []
    ib.openTrades.return_value = []
    ib.accountValues.return_value = []
    return ib


def _make_mock_trade(order_id: int = 1) -> MagicMock:
    trade = MagicMock()
    trade.order.orderId = order_id
    trade.order.permId = 999
    trade.order.orderRef = ""
    trade.order.action = "SELL"
    trade.order.totalQuantity = 1
    trade.orderStatus.status = "Filled"
    trade.orderStatus.filled = 1
    trade.orderStatus.avgFillPrice = 2.50
    trade.fills = []
    trade.isDone.return_value = True
    trade.statusEvent = MagicMock()
    trade.statusEvent.__iadd__ = MagicMock(return_value=trade.statusEvent)
    trade.fillEvent = MagicMock()
    trade.fillEvent.__iadd__ = MagicMock(return_value=trade.fillEvent)
    return trade


def _make_option_resolved(
    symbol: str = "AAPL", con_id: int = 99999,
) -> MagicMock:
    resolved = MagicMock()
    resolved.con_id = con_id
    resolved.symbol = symbol
    resolved.sec_type = "OPT"
    resolved.exchange = "SMART"
    resolved.primary_exchange = ""
    resolved.currency = "USD"
    resolved.ib_contract = MagicMock()
    resolved.key = f"{con_id}@SMART"
    return resolved


def _make_stock_resolved(
    symbol: str = "NVDA", con_id: int = 12345,
) -> MagicMock:
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
# build_intent — options validation
# ---------------------------------------------------------------------------


class TestBuildIntentOptions:

    def test_build_option_intent_happy_path(self):
        from execution_policy import ExecutionPolicy, build_intent

        intent = build_intent(
            symbol="AAPL", side="SELL", quantity=1,
            policy=ExecutionPolicy.URGENT_EXIT,
            source_script="auto_options_executor.py",
            sec_type="OPT", expiry="20260417", strike=200.0, right="P",
        )

        assert intent["sec_type"] == "OPT"
        assert intent["expiry"] == "20260417"
        assert intent["strike"] == 200.0
        assert intent["right"] == "P"
        assert intent["symbol"] == "AAPL"
        assert intent["side"] == "SELL"

    def test_build_option_intent_missing_expiry_raises(self):
        from execution_policy import ExecutionPolicy, build_intent

        with pytest.raises(ValueError, match="expiry"):
            build_intent(
                symbol="AAPL", side="SELL", quantity=1,
                policy=ExecutionPolicy.URGENT_EXIT,
                source_script="test.py",
                sec_type="OPT", strike=200.0, right="P",
            )

    def test_build_option_intent_missing_strike_raises(self):
        from execution_policy import ExecutionPolicy, build_intent

        with pytest.raises(ValueError, match="expiry"):
            build_intent(
                symbol="AAPL", side="SELL", quantity=1,
                policy=ExecutionPolicy.URGENT_EXIT,
                source_script="test.py",
                sec_type="OPT", expiry="20260417", right="P",
            )

    def test_build_option_intent_missing_right_raises(self):
        from execution_policy import ExecutionPolicy, build_intent

        with pytest.raises(ValueError, match="expiry"):
            build_intent(
                symbol="AAPL", side="SELL", quantity=1,
                policy=ExecutionPolicy.URGENT_EXIT,
                source_script="test.py",
                sec_type="OPT", expiry="20260417", strike=200.0,
            )

    def test_build_option_intent_invalid_right_raises(self):
        from execution_policy import ExecutionPolicy, build_intent

        with pytest.raises(ValueError, match="right must be"):
            build_intent(
                symbol="AAPL", side="SELL", quantity=1,
                policy=ExecutionPolicy.URGENT_EXIT,
                source_script="test.py",
                sec_type="OPT", expiry="20260417", strike=200.0, right="X",
            )

    def test_stock_intent_does_not_set_sec_type(self):
        from execution_policy import ExecutionPolicy, build_intent

        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.URGENT_EXIT,
            source_script="test.py",
        )

        assert "sec_type" not in intent
        assert "expiry" not in intent

    def test_option_intent_with_limit_price(self):
        from execution_policy import ExecutionPolicy, build_intent

        intent = build_intent(
            symbol="SPY", side="SELL", quantity=1,
            policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script="test.py",
            sec_type="OPT", expiry="20260417", strike=500.0, right="C",
            limit_price=3.50,
        )

        assert intent["sec_type"] == "OPT"
        assert intent["limit_price"] == 3.50


# ---------------------------------------------------------------------------
# generate_intent_id — uniqueness for options
# ---------------------------------------------------------------------------


class TestGenerateIntentIdOptions:

    def test_different_strikes_produce_different_ids(self):
        from execution_policy import ExecutionPolicy, generate_intent_id

        id_200 = generate_intent_id(
            "AAPL", "SELL", ExecutionPolicy.URGENT_EXIT, "test.py",
            date_str="20260307", sec_type="OPT",
            expiry="20260417", strike=200.0, right="P",
        )
        id_210 = generate_intent_id(
            "AAPL", "SELL", ExecutionPolicy.URGENT_EXIT, "test.py",
            date_str="20260307", sec_type="OPT",
            expiry="20260417", strike=210.0, right="P",
        )
        assert id_200 != id_210

    def test_different_rights_produce_different_ids(self):
        from execution_policy import ExecutionPolicy, generate_intent_id

        id_put = generate_intent_id(
            "AAPL", "SELL", ExecutionPolicy.URGENT_EXIT, "test.py",
            date_str="20260307", sec_type="OPT",
            expiry="20260417", strike=200.0, right="P",
        )
        id_call = generate_intent_id(
            "AAPL", "SELL", ExecutionPolicy.URGENT_EXIT, "test.py",
            date_str="20260307", sec_type="OPT",
            expiry="20260417", strike=200.0, right="C",
        )
        assert id_put != id_call

    def test_different_expiries_produce_different_ids(self):
        from execution_policy import ExecutionPolicy, generate_intent_id

        id_apr = generate_intent_id(
            "AAPL", "SELL", ExecutionPolicy.URGENT_EXIT, "test.py",
            date_str="20260307", sec_type="OPT",
            expiry="20260417", strike=200.0, right="P",
        )
        id_may = generate_intent_id(
            "AAPL", "SELL", ExecutionPolicy.URGENT_EXIT, "test.py",
            date_str="20260307", sec_type="OPT",
            expiry="20260515", strike=200.0, right="P",
        )
        assert id_apr != id_may

    def test_stock_id_differs_from_option_id(self):
        from execution_policy import ExecutionPolicy, generate_intent_id

        id_stk = generate_intent_id(
            "AAPL", "SELL", ExecutionPolicy.URGENT_EXIT, "test.py",
            date_str="20260307",
        )
        id_opt = generate_intent_id(
            "AAPL", "SELL", ExecutionPolicy.URGENT_EXIT, "test.py",
            date_str="20260307", sec_type="OPT",
            expiry="20260417", strike=200.0, right="P",
        )
        assert id_stk != id_opt

    def test_same_option_params_produce_same_id(self):
        from execution_policy import ExecutionPolicy, generate_intent_id

        id_1 = generate_intent_id(
            "AAPL", "SELL", ExecutionPolicy.URGENT_EXIT, "test.py",
            date_str="20260307", sec_type="OPT",
            expiry="20260417", strike=200.0, right="P",
        )
        id_2 = generate_intent_id(
            "AAPL", "SELL", ExecutionPolicy.URGENT_EXIT, "test.py",
            date_str="20260307", sec_type="OPT",
            expiry="20260417", strike=200.0, right="P",
        )
        assert id_1 == id_2


# ---------------------------------------------------------------------------
# OrderRouter.submit — options contract resolution
# ---------------------------------------------------------------------------


class TestOrderRouterOptions:

    @pytest.mark.asyncio
    async def test_submit_option_calls_resolve_option(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter
        from unittest.mock import patch

        ib = _make_mock_ib()
        trade = _make_mock_trade()
        ib.placeOrder.return_value = trade

        router = OrderRouter(ib, fill_timeout=0.5)
        await router.startup()

        with patch.object(
            router._contract_cache, "resolve_option", new_callable=AsyncMock,
        ) as mock_resolve_opt:
            mock_resolve_opt.return_value = _make_option_resolved()

            intent = build_intent(
                symbol="AAPL", side="SELL", quantity=1,
                policy=ExecutionPolicy.URGENT_EXIT,
                source_script="auto_options_executor.py",
                sec_type="OPT", expiry="20260417", strike=200.0, right="P",
            )

            result = await router.submit(intent, wait_for_fill=False)
            assert result.success is True
            mock_resolve_opt.assert_called_once_with(
                symbol="AAPL", expiry="20260417", strike=200.0, right="P",
            )

    @pytest.mark.asyncio
    async def test_submit_stock_does_not_call_resolve_option(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter
        from unittest.mock import patch

        ib = _make_mock_ib()
        trade = _make_mock_trade()
        ib.placeOrder.return_value = trade

        router = OrderRouter(ib, fill_timeout=0.5)
        await router.startup()

        with (
            patch.object(
                router._contract_cache, "resolve", new_callable=AsyncMock,
            ) as mock_resolve,
            patch.object(
                router._contract_cache, "resolve_option", new_callable=AsyncMock,
            ) as mock_resolve_opt,
        ):
            mock_resolve.return_value = _make_stock_resolved()

            intent = build_intent(
                symbol="NVDA", side="BUY", quantity=50,
                policy=ExecutionPolicy.URGENT_EXIT,
                source_script="test.py",
            )

            result = await router.submit(intent, wait_for_fill=False)
            assert result.success is True
            mock_resolve.assert_called_once_with("NVDA")
            mock_resolve_opt.assert_not_called()

    @pytest.mark.asyncio
    async def test_submit_option_fails_on_resolution_failure(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter
        from unittest.mock import patch

        ib = _make_mock_ib()
        router = OrderRouter(ib, fill_timeout=0.5)
        await router.startup()

        with patch.object(
            router._contract_cache, "resolve_option", new_callable=AsyncMock,
        ) as mock_resolve_opt:
            mock_resolve_opt.return_value = None

            intent = build_intent(
                symbol="AAPL", side="SELL", quantity=1,
                policy=ExecutionPolicy.URGENT_EXIT,
                source_script="test.py",
                sec_type="OPT", expiry="20260417", strike=200.0, right="P",
            )

            result = await router.submit(intent, wait_for_fill=False)
            assert result.success is False
            assert "resolution failed" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_submit_option_with_pre_resolved_skips_cache(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_router import OrderRouter
        from unittest.mock import patch

        ib = _make_mock_ib()
        trade = _make_mock_trade()
        ib.placeOrder.return_value = trade

        router = OrderRouter(ib, fill_timeout=0.5)
        await router.startup()

        resolved = _make_option_resolved()
        intent = build_intent(
            symbol="AAPL", side="SELL", quantity=1,
            policy=ExecutionPolicy.URGENT_EXIT,
            source_script="test.py",
            sec_type="OPT", expiry="20260417", strike=200.0, right="P",
        )

        with patch.object(
            router._contract_cache, "resolve_option", new_callable=AsyncMock,
        ) as mock_resolve_opt:
            result = await router.submit(
                intent, resolved=resolved, wait_for_fill=False,
            )
            assert result.success is True
            mock_resolve_opt.assert_not_called()


# ---------------------------------------------------------------------------
# order_factory — options tick-size
# ---------------------------------------------------------------------------


class TestOrderFactoryOptions:

    def test_option_contract_uses_005_tick(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_factory import build_orders

        resolved = _make_option_resolved()
        intent = build_intent(
            symbol="AAPL", side="SELL", quantity=1,
            policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script="test.py",
            sec_type="OPT", expiry="20260417", strike=200.0, right="P",
            limit_price=2.53,
        )

        built = build_orders(intent, resolved, bid=2.50, ask=2.55)
        assert built.parent.lmtPrice == 2.50
        assert built.intent_id == intent["intent_id"]

    def test_stock_contract_uses_001_tick(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_factory import build_orders

        resolved = _make_stock_resolved()
        intent = build_intent(
            symbol="NVDA", side="BUY", quantity=50,
            policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script="test.py",
            limit_price=120.00,
        )

        built = build_orders(intent, resolved, bid=119.99, ask=120.01)
        assert built.parent.lmtPrice == 120.01

    def test_option_urgent_exit_is_market_order(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_factory import build_orders

        resolved = _make_option_resolved()
        intent = build_intent(
            symbol="AAPL", side="SELL", quantity=1,
            policy=ExecutionPolicy.URGENT_EXIT,
            source_script="test.py",
            sec_type="OPT", expiry="20260417", strike=200.0, right="P",
        )

        built = build_orders(intent, resolved)
        assert built.parent.orderType == "MKT"
        assert built.parent.totalQuantity == 1

    def test_explicit_tick_override_not_changed_for_options(self):
        from execution_policy import ExecutionPolicy, build_intent
        from order_factory import build_orders

        resolved = _make_option_resolved()
        intent = build_intent(
            symbol="AAPL", side="SELL", quantity=1,
            policy=ExecutionPolicy.AGGRESSIVE_ENTRY,
            source_script="test.py",
            sec_type="OPT", expiry="20260417", strike=200.0, right="P",
            limit_price=2.53,
        )

        built = build_orders(intent, resolved, tick_size=0.01, bid=2.50, ask=2.53)
        assert built.parent.lmtPrice == 2.50
