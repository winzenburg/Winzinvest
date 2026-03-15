"""Unit tests for the dashboard API logic (data parsing, not HTTP)."""

import json
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

TRADING_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TRADING_DIR / "scripts"))
sys.path.insert(0, str(TRADING_DIR / "dashboard"))


class TestLoadJson:
    def test_loads_valid_json(self, tmp_path: Path) -> None:
        from api import load_json

        f = tmp_path / "good.json"
        f.write_text('{"key": "value"}')
        result = load_json(f)
        assert result == {"key": "value"}

    def test_returns_default_on_missing(self, tmp_path: Path) -> None:
        from api import load_json

        result = load_json(tmp_path / "nonexistent.json", {"fallback": True})
        assert result == {"fallback": True}

    def test_returns_default_on_bad_json(self, tmp_path: Path) -> None:
        from api import load_json

        f = tmp_path / "bad.json"
        f.write_text("not json {{{")
        result = load_json(f, {})
        assert result == {}


class TestPortfolioFromCache:
    def test_parses_positions(self, sample_portfolio_json: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import api
        monkeypatch.setattr(api, "TRADING_DIR", sample_portfolio_json.parent)
        result = api._portfolio_from_cache()
        assert result is not None
        assert result["account_value"] == pytest.approx(1936000.0)
        assert result["positions_count"] == 2
        assert result["positions"][0]["unrealized_pnl"] == pytest.approx(150.0)
        assert result["positions"][1]["unrealized_pnl"] == pytest.approx(250.0)

    def test_total_pnl_calculated(self, sample_portfolio_json: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import api
        monkeypatch.setattr(api, "TRADING_DIR", sample_portfolio_json.parent)
        result = api._portfolio_from_cache()
        assert result is not None
        assert result["total_pnl"] == pytest.approx(400.0)

    def test_avg_cost_uses_averageCost(self, sample_portfolio_json: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import api
        monkeypatch.setattr(api, "TRADING_DIR", sample_portfolio_json.parent)
        result = api._portfolio_from_cache()
        assert result is not None
        assert result["positions"][0]["avg_cost"] == pytest.approx(190.50)

    def test_returns_none_without_cache(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import api
        monkeypatch.setattr(api, "TRADING_DIR", tmp_path)
        result = api._portfolio_from_cache()
        assert result is None


class TestRiskMetrics:
    def test_reads_max_drawdown_from_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import api
        monkeypatch.setattr(api, "TRADING_DIR", tmp_path)
        logs = tmp_path / "logs"
        logs.mkdir()
        (logs / "daily_loss.json").write_text(json.dumps({
            "loss": 500, "sod_equity": 100000, "current_equity": 99500
        }))
        (logs / "peak_equity.json").write_text(json.dumps({"peak_equity": 100000}))
        (tmp_path / "risk.json").write_text(json.dumps({
            "portfolio": {"max_drawdown_pct": 0.1}
        }))
        result = api.get_risk_metrics()
        assert result["max_drawdown_pct"] == pytest.approx(10.0)

    def test_default_drawdown_without_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import api
        monkeypatch.setattr(api, "TRADING_DIR", tmp_path)
        logs = tmp_path / "logs"
        logs.mkdir()
        (logs / "daily_loss.json").write_text("{}")
        (logs / "peak_equity.json").write_text("{}")
        result = api.get_risk_metrics()
        assert result["max_drawdown_pct"] == pytest.approx(10.0)


class TestScreenerResults:
    def test_parses_nested_multimode(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import api
        monkeypatch.setattr(api, "TRADING_DIR", tmp_path)
        (tmp_path / "watchlist_longs.json").write_text(json.dumps({"long_candidates": []}))
        (tmp_path / "watchlist_mean_reversion.json").write_text(json.dumps({"candidates": []}))
        (tmp_path / "watchlist_pairs.json").write_text(json.dumps({"pairs": [{"a": "SPY", "b": "QQQ"}]}))
        (tmp_path / "watchlist_multimode.json").write_text(json.dumps({
            "modes": {
                "short_opportunities": {"short": [{"symbol": "TSLA"}]},
                "premium_selling": {"short": [{"symbol": "NVDA"}]},
            }
        }))
        result = api.get_screener_results()
        assert result["shorts"]["count"] == 1
        assert result["shorts"]["candidates"][0]["symbol"] == "TSLA"
        assert result["premium"]["count"] == 1
        assert result["pairs"]["count"] == 1


class TestPerformanceStats:
    def test_empty_db_returns_zeros(self, tmp_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from trade_log_db import init_db
        init_db(tmp_db)
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_db}")

        import importlib
        import trade_log_db
        importlib.reload(trade_log_db)

        import api
        result = api.get_performance_stats()
        assert result["total_trades"] == 0
        assert result["win_rate"] == 0.0
