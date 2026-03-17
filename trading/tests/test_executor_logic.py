"""
Tests for executor logic — position sizing, stop/TP calculation, and execution gates.

These tests run without an IB Gateway connection. All IB interactions are mocked.
Run with: pytest trading/tests/test_executor_logic.py -v
"""

import math
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts to path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


# ─────────────────────────────────────────────────────────────────────────────
# ATR / Position Sizing Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestComputeStopTp:
    """compute_stop_tp: verify long and short stop/TP directions."""

    def test_long_stop_below_entry(self):
        from atr_stops import compute_stop_tp
        stop, tp = compute_stop_tp(entry_price=100.0, side="BUY", atr=2.0)
        assert stop < 100.0, "Long stop must be below entry"
        assert tp > 100.0, "Long TP must be above entry"

    def test_short_stop_above_entry(self):
        from atr_stops import compute_stop_tp
        stop, tp = compute_stop_tp(entry_price=100.0, side="SELL", atr=2.0)
        assert stop > 100.0, "Short stop must be above entry"
        assert tp < 100.0, "Short TP must be below entry"

    def test_atr_multiplier_applied(self):
        from atr_stops import compute_stop_tp
        stop, tp = compute_stop_tp(entry_price=100.0, side="BUY", atr=2.0, stop_mult=1.5, tp_mult=3.5)
        assert abs(stop - 97.0) < 0.01, f"Expected stop ~97.0, got {stop}"
        assert abs(tp - 107.0) < 0.01, f"Expected tp ~107.0, got {tp}"

    def test_fallback_when_no_atr(self):
        from atr_stops import compute_stop_tp
        stop, tp = compute_stop_tp(entry_price=100.0, side="BUY", atr=None,
                                   fallback_stop_pct=0.02, fallback_tp_pct=0.03)
        assert abs(stop - 98.0) < 0.01, f"Expected stop ~98.0, got {stop}"
        assert abs(tp - 103.0) < 0.01, f"Expected tp ~103.0, got {tp}"

    def test_prices_rounded_to_cents(self):
        from atr_stops import compute_stop_tp
        stop, tp = compute_stop_tp(entry_price=123.456, side="BUY", atr=1.23456)
        assert stop == round(stop, 2)
        assert tp == round(tp, 2)

    def test_side_case_insensitive(self):
        from atr_stops import compute_stop_tp
        stop1, _ = compute_stop_tp(entry_price=100.0, side="sell", atr=2.0)
        stop2, _ = compute_stop_tp(entry_price=100.0, side="SELL", atr=2.0)
        assert stop1 == stop2

    @pytest.mark.parametrize("side", ["BUY", "LONG", "SELL", "SHORT"])
    def test_valid_sides(self, side: str):
        from atr_stops import compute_stop_tp
        stop, tp = compute_stop_tp(entry_price=50.0, side=side, atr=1.0)
        assert stop > 0
        assert tp > 0
        assert stop != tp


class TestCalculatePositionSize:
    """calculate_position_size: verify sizing constraints."""

    def test_returns_at_least_one_share(self):
        from atr_stops import calculate_position_size
        shares = calculate_position_size(equity=1000.0, entry_price=500.0, atr=1.0)
        assert shares >= 1

    def test_risk_cap_limits_size(self):
        from atr_stops import calculate_position_size
        # equity=100k, risk_pct=1%, atr=5 → risk_amount=$1000, stop_dist=$7.5
        # shares_from_risk = floor(1000/7.5) = 133
        # Use max_position_pct=1.0 to isolate the risk cap from the position cap.
        # Mock vol_scale and streak_mult so test is deterministic.
        with patch("risk_config.compute_vol_scale", return_value=1.0):
            shares = calculate_position_size(
                equity=100_000, entry_price=100.0, atr=5.0,
                risk_pct=0.01, stop_mult=1.5,
                max_position_pct=1.0,
            )
        assert shares == 133

    def test_position_cap_limits_size(self):
        from atr_stops import calculate_position_size
        # cap_equity=100k, max_position_pct=5% → max_notional=5000, shares=50 at $100
        shares = calculate_position_size(
            equity=100_000, entry_price=100.0, atr=None,
            risk_pct=0.50,  # artificially high to trigger position cap
            max_position_pct=0.05,
        )
        assert shares <= 50, f"Position cap should limit to ~50 shares, got {shares}"

    def test_absolute_max_cap(self):
        from atr_stops import calculate_position_size
        shares = calculate_position_size(
            equity=1_000_000_000, entry_price=1.0, atr=0.001,
            absolute_max_shares=5000,
        )
        assert shares <= 5000

    def test_high_conviction_increases_size(self):
        from atr_stops import calculate_position_size
        base = calculate_position_size(
            equity=100_000, entry_price=100.0, atr=5.0, conviction=0.5
        )
        high = calculate_position_size(
            equity=100_000, entry_price=100.0, atr=5.0, conviction=0.9
        )
        assert high >= base, "High conviction should not decrease position size"

    def test_low_conviction_decreases_size(self):
        from atr_stops import calculate_position_size
        base = calculate_position_size(
            equity=100_000, entry_price=100.0, atr=5.0, conviction=0.6
        )
        low = calculate_position_size(
            equity=100_000, entry_price=100.0, atr=5.0, conviction=0.3
        )
        assert low <= base, "Low conviction should not increase position size"

    def test_zero_equity_returns_min(self):
        from atr_stops import calculate_position_size
        shares = calculate_position_size(equity=0, entry_price=100.0, atr=2.0)
        assert shares >= 1

    def test_zero_entry_price_returns_min(self):
        from atr_stops import calculate_position_size
        shares = calculate_position_size(equity=100_000, entry_price=0.0, atr=2.0)
        assert shares >= 1

    def test_cap_equity_separate_from_risk_equity(self):
        from atr_stops import calculate_position_size
        # Risk sizing on leveraged equity, cap on NLV
        shares_with_cap = calculate_position_size(
            equity=500_000, entry_price=100.0, atr=5.0,
            cap_equity=100_000, max_position_pct=0.05,
        )
        assert shares_with_cap <= 50, "cap_equity should constrain position size"


class TestConvictionTier:
    def test_high_tier(self):
        from atr_stops import conviction_tier
        assert conviction_tier(0.9) == "high"
        assert conviction_tier(0.8) == "high"

    def test_medium_tier(self):
        from atr_stops import conviction_tier
        assert conviction_tier(0.5) == "medium"
        assert conviction_tier(0.79) == "medium"

    def test_low_tier(self):
        from atr_stops import conviction_tier
        assert conviction_tier(0.3) == "low"
        assert conviction_tier(0.0) == "low"

    def test_none_returns_medium(self):
        from atr_stops import conviction_tier
        assert conviction_tier(None) == "medium"


class TestComputeTrailingAmount:
    def test_atr_based_trailing(self):
        from atr_stops import compute_trailing_amount
        amount = compute_trailing_amount(atr=2.0, entry_price=100.0, trailing_mult=3.0)
        assert abs(amount - 6.0) < 0.01

    def test_fallback_when_no_atr(self):
        from atr_stops import compute_trailing_amount
        amount = compute_trailing_amount(atr=None, entry_price=100.0, fallback_pct=0.025)
        assert abs(amount - 2.5) < 0.01

    def test_zero_atr_uses_fallback(self):
        from atr_stops import compute_trailing_amount
        amount = compute_trailing_amount(atr=0.0, entry_price=100.0, fallback_pct=0.025)
        assert abs(amount - 2.5) < 0.01


# ─────────────────────────────────────────────────────────────────────────────
# Kill Switch Logic Tests (file-based state)
# ─────────────────────────────────────────────────────────────────────────────

class TestKillSwitchFileState:
    """Test that kill_switch.json is read correctly by execution_gates."""

    def test_active_kill_switch_blocks_execution(self, tmp_path):
        """execution_gates should reject all orders when kill switch is active."""
        ks_file = tmp_path / "kill_switch.json"
        ks_file.write_text('{"active": true, "reason": "test", "timestamp": "2024-01-01T00:00:00"}')

        with patch("execution_gates.KILL_SWITCH_PATH", str(ks_file)):
            from execution_gates import check_kill_switch
            result = check_kill_switch()
            assert result is False, "Kill switch active should block execution"

    def test_inactive_kill_switch_allows_execution(self, tmp_path):
        ks_file = tmp_path / "kill_switch.json"
        ks_file.write_text('{"active": false, "reason": "", "timestamp": "2024-01-01T00:00:00"}')

        with patch("execution_gates.KILL_SWITCH_PATH", str(ks_file)):
            from execution_gates import check_kill_switch
            result = check_kill_switch()
            assert result is True, "Inactive kill switch should allow execution"

    def test_missing_kill_switch_file_allows_execution(self, tmp_path):
        missing = str(tmp_path / "no_such_file.json")
        with patch("execution_gates.KILL_SWITCH_PATH", missing):
            from execution_gates import check_kill_switch
            result = check_kill_switch()
            assert result is True, "Missing kill switch file should default to inactive"


# ─────────────────────────────────────────────────────────────────────────────
# Sector Gate Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSectorGates:
    def test_sector_map_contains_expected_keys(self):
        from sector_gates import SECTOR_MAP
        assert isinstance(SECTOR_MAP, dict)
        assert len(SECTOR_MAP) > 0, "SECTOR_MAP should not be empty"

    def test_portfolio_sector_exposure_empty_positions(self):
        from sector_gates import portfolio_sector_exposure
        mock_ib = MagicMock()
        mock_ib.portfolio.return_value = []
        exposure, total = portfolio_sector_exposure(mock_ib)
        assert exposure == {}, "Empty positions should give empty exposure"
        assert total == 0.0

    def test_portfolio_sector_exposure_aggregation(self):
        from sector_gates import portfolio_sector_exposure
        mock_positions = [
            MagicMock(contract=MagicMock(symbol="AAPL"), marketValue=15000.0),
            MagicMock(contract=MagicMock(symbol="MSFT"), marketValue=9000.0),
        ]
        mock_ib = MagicMock()
        mock_ib.portfolio.return_value = mock_positions
        exposure, total = portfolio_sector_exposure(mock_ib)
        assert isinstance(exposure, dict)
        assert "Technology" in exposure
        assert exposure["Technology"] == 24000.0
        assert total == 24000.0


# ─────────────────────────────────────────────────────────────────────────────
# Trade Log DB Tests (already partially covered — adding edge cases)
# ─────────────────────────────────────────────────────────────────────────────

class TestTradeLogDbEdgeCases:
    def test_insert_and_retrieve(self, tmp_path):
        from trade_log_db import init_db, log_trade, get_recent_trades
        db = tmp_path / "test_trades.db"
        init_db(db)
        log_trade(
            symbol="TSLA",
            action="BUY",
            qty=10,
            price=200.0,
            strategy="momentum_long",
            source_script="execute_longs.py",
            db_path=db,
        )
        trades = get_recent_trades(limit=10, db_path=db)
        assert len(trades) == 1
        assert trades[0]["symbol"] == "TSLA"

    def test_multiple_trades_ordering(self, tmp_path):
        from trade_log_db import init_db, log_trade, get_recent_trades
        db = tmp_path / "test_trades2.db"
        init_db(db)
        for sym in ["AAPL", "GOOGL", "AMZN"]:
            log_trade(symbol=sym, action="BUY", qty=1, price=100.0,
                      strategy="test", source_script="test.py", db_path=db)
        trades = get_recent_trades(limit=10, db_path=db)
        assert len(trades) == 3
        assert trades[0]["symbol"] == "AMZN"
