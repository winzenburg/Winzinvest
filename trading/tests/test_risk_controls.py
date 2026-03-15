"""Unit tests for risk control components: kill switch, file_utils, notifications."""

import json
from pathlib import Path

import pytest


class TestKillSwitch:
    def test_inactive_state(self, sample_kill_switch_inactive: Path) -> None:
        data = json.loads(sample_kill_switch_inactive.read_text())
        assert data["active"] is False

    def test_active_state(self, sample_kill_switch_active: Path) -> None:
        data = json.loads(sample_kill_switch_active.read_text())
        assert data["active"] is True
        assert "daily loss" in data["reason"]

    def test_risk_json_limits(self, sample_risk_json: Path) -> None:
        data = json.loads(sample_risk_json.read_text())
        assert data["portfolio"]["daily_loss_limit_pct"] == 0.03
        assert data["portfolio"]["max_drawdown_pct"] == 0.1
        assert data["equity_shorts"]["max_short_positions"] == 25


class TestFileUtils:
    def test_append_jsonl_creates_file(self, tmp_path: Path) -> None:
        from file_utils import append_jsonl

        target = tmp_path / "test.jsonl"
        append_jsonl(target, {"symbol": "AAPL", "action": "BUY"})
        assert target.exists()
        lines = target.read_text().strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["symbol"] == "AAPL"

    def test_append_jsonl_multiple_records(self, tmp_path: Path) -> None:
        from file_utils import append_jsonl

        target = tmp_path / "multi.jsonl"
        for i in range(5):
            append_jsonl(target, {"index": i})
        lines = target.read_text().strip().splitlines()
        assert len(lines) == 5
        for i, line in enumerate(lines):
            assert json.loads(line)["index"] == i

    def test_append_jsonl_creates_parent_dirs(self, tmp_path: Path) -> None:
        from file_utils import append_jsonl

        target = tmp_path / "sub" / "dir" / "deep.jsonl"
        append_jsonl(target, {"ok": True})
        assert target.exists()


class TestNotifications:
    def test_send_telegram_no_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        import importlib
        import notifications
        importlib.reload(notifications)
        result = notifications.send_telegram("test message")
        assert result is False

    def test_notify_executor_error_no_crash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        import importlib
        import notifications
        importlib.reload(notifications)
        notifications.notify_executor_error("test_script.py", "some error", context="unit test")
