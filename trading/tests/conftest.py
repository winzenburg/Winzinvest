"""Shared test fixtures for the trading system test suite."""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

TRADING_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = TRADING_DIR / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """Return a temporary SQLite DB path (file does not exist yet)."""
    return tmp_path / "test_trades.db"


@pytest.fixture()
def sample_trade_record() -> Dict[str, Any]:
    return {
        "symbol": "AAPL",
        "action": "BUY",
        "quantity": 100,
        "price": 190.50,
        "entry_price": 190.50,
        "stop_price": 186.69,
        "profit_price": 196.22,
        "timestamp": "2026-03-09T10:00:00",
        "strategy": "long_momentum",
        "source_script": "execute_longs.py",
        "status": "Filled",
        "slippage": 0.02,
        "commission": 1.0,
    }


@pytest.fixture()
def sample_portfolio_json(tmp_path: Path) -> Path:
    """Create a realistic portfolio.json in tmp_path and return its path."""
    pf = {
        "summary": {
            "net_liquidation": 1936000.0,
            "total_cash_value": 1885000.0,
        },
        "positions": [
            {
                "symbol": "AAPL",
                "secType": "STK",
                "position": 100,
                "marketPrice": 192.0,
                "marketValue": 19200.0,
                "averageCost": 190.50,
                "unrealizedPNL": 150.0,
                "realizedPNL": 0.0,
            },
            {
                "symbol": "SPY",
                "secType": "STK",
                "position": -50,
                "marketPrice": 510.0,
                "marketValue": -25500.0,
                "averageCost": 515.0,
                "unrealizedPNL": 250.0,
                "realizedPNL": 0.0,
            },
        ],
        "timestamp": "2026-03-09T11:00:00",
    }
    path = tmp_path / "portfolio.json"
    path.write_text(json.dumps(pf))
    return path


@pytest.fixture()
def sample_risk_json(tmp_path: Path) -> Path:
    """Create a risk.json in tmp_path."""
    risk = {
        "equity_shorts": {"max_short_positions": 25, "max_sector_concentration_pct": 30},
        "equity_longs": {"max_long_positions": 25},
        "options": {"max_options_per_day": 5},
        "portfolio": {
            "daily_loss_limit_pct": 0.03,
            "max_drawdown_pct": 0.1,
        },
    }
    path = tmp_path / "risk.json"
    path.write_text(json.dumps(risk))
    return path


@pytest.fixture()
def sample_kill_switch_inactive(tmp_path: Path) -> Path:
    path = tmp_path / "kill_switch.json"
    path.write_text(json.dumps({"active": False, "reason": "test"}))
    return path


@pytest.fixture()
def sample_kill_switch_active(tmp_path: Path) -> Path:
    path = tmp_path / "kill_switch.json"
    path.write_text(json.dumps({"active": True, "reason": "daily loss limit"}))
    return path
