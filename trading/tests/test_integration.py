"""Integration tests: scheduler dry-run, API smoke, trade DB round-trip."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

TRADING_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = TRADING_DIR / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


class TestSchedulerDryRun:
    def test_dry_run_exits_zero(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "scheduler.py"), "--dry-run"],
            capture_output=True,
            text=True,
            timeout=15,
            env={**__import__("os").environ, "PYTHONPATH": str(SCRIPTS_DIR)},
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "AUTOMATED TRADING SCHEDULE" in result.stdout


class TestDashboardAPISmoke:
    """Smoke-test the dashboard API endpoints (requires server running on :8002)."""

    @pytest.fixture(autouse=True)
    def _check_server(self) -> None:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        reachable = sock.connect_ex(("127.0.0.1", 8002)) == 0
        sock.close()
        if not reachable:
            pytest.skip("Dashboard server not running on port 8002")

    def _get(self, path: str) -> Any:
        import urllib.request
        with urllib.request.urlopen(f"http://127.0.0.1:8002{path}", timeout=5) as resp:
            assert resp.status == 200
            return json.loads(resp.read())

    def test_status_endpoint(self) -> None:
        data = self._get("/api/status")
        assert "services" in data
        assert "kill_switch" in data
        assert "healthy" in data

    def test_portfolio_endpoint(self) -> None:
        data = self._get("/api/portfolio")
        assert "account_value" in data
        assert "positions" in data

    def test_performance_endpoint(self) -> None:
        data = self._get("/api/performance")
        assert "total_trades" in data
        assert "win_rate" in data

    def test_screeners_endpoint(self) -> None:
        data = self._get("/api/screeners")
        assert "longs" in data
        assert "shorts" in data
        assert "pairs" in data

    def test_options_endpoint(self) -> None:
        data = self._get("/api/options")
        assert "summary" in data
        assert "options_positions" in data

    def test_errors_endpoint(self) -> None:
        data = self._get("/api/errors?minutes=60")
        assert "errors" in data
        assert isinstance(data["errors"], list)

    def test_logs_endpoint(self) -> None:
        data = self._get("/api/logs/scheduler")
        assert "logs" in data


class TestTradeDBRoundTrip:
    """Full insert -> query open -> update exit -> query closed cycle."""

    def test_full_lifecycle(self, tmp_db: Path) -> None:
        from trade_log_db import init_db, insert_trade, get_open_trades, update_trade_exit, get_closed_trades

        init_db(tmp_db)

        row_id = insert_trade({
            "symbol": "MSFT",
            "action": "BUY",
            "quantity": 50,
            "entry_price": 420.0,
            "stop_price": 411.60,
            "profit_price": 432.60,
            "timestamp": "2026-03-09T09:30:00",
            "strategy": "long_momentum",
            "source_script": "test",
            "status": "Filled",
        }, db_path=tmp_db)
        assert row_id is not None

        open_trades = get_open_trades(db_path=tmp_db)
        assert len(open_trades) == 1
        assert open_trades[0]["symbol"] == "MSFT"

        ok = update_trade_exit(
            trade_id=row_id,
            exit_price=432.0,
            exit_timestamp="2026-03-10T15:00:00",
            exit_reason="take_profit",
            realized_pnl=600.0,
            realized_pnl_pct=2.86,
            holding_days=1,
            max_adverse_excursion=-50.0,
            max_favorable_excursion=650.0,
            db_path=tmp_db,
        )
        assert ok is True

        open_after = get_open_trades(db_path=tmp_db)
        assert len(open_after) == 0

        closed = get_closed_trades(since_days=30, db_path=tmp_db)
        assert len(closed) == 1
        assert closed[0]["exit_reason"] == "take_profit"
        assert closed[0]["realized_pnl"] == pytest.approx(600.0)
        assert closed[0]["max_adverse_excursion"] == pytest.approx(-50.0)
