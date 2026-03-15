"""Unit tests for trade_log_db — schema, insert, query, migration."""

import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any, Dict

import pytest

from trade_log_db import (
    init_db,
    insert_trade,
    get_open_trades,
    get_closed_trades,
    migrate_db,
    update_trade_exit,
)


class TestSchemaInit:
    def test_creates_db_file(self, tmp_db: Path) -> None:
        init_db(tmp_db)
        assert tmp_db.exists()
        assert tmp_db.stat().st_size > 0

    def test_no_duplicate_columns(self, tmp_db: Path) -> None:
        init_db(tmp_db)
        conn = sqlite3.connect(str(tmp_db))
        cols = [row[1] for row in conn.execute("PRAGMA table_info(trades)").fetchall()]
        conn.close()
        dupes = {k: v for k, v in Counter(cols).items() if v > 1}
        assert dupes == {}, f"Duplicate columns: {dupes}"

    def test_idempotent_init(self, tmp_db: Path) -> None:
        init_db(tmp_db)
        init_db(tmp_db)
        conn = sqlite3.connect(str(tmp_db))
        count = conn.execute("SELECT count(*) FROM trades").fetchone()[0]
        conn.close()
        assert count == 0


class TestInsertTrade:
    def test_insert_returns_row_id(self, tmp_db: Path, sample_trade_record: Dict[str, Any]) -> None:
        row_id = insert_trade(sample_trade_record, db_path=tmp_db)
        assert row_id is not None
        assert isinstance(row_id, int)
        assert row_id >= 1

    def test_round_trip(self, tmp_db: Path, sample_trade_record: Dict[str, Any]) -> None:
        insert_trade(sample_trade_record, db_path=tmp_db)
        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM trades WHERE id = 1").fetchone()
        conn.close()
        assert row["symbol"] == "AAPL"
        assert row["side"] == "BUY"
        assert row["qty"] == 100
        assert row["status"] == "Filled"
        assert row["slippage"] == pytest.approx(0.02)
        assert row["commission"] == pytest.approx(1.0)

    def test_empty_symbol_rejected(self, tmp_db: Path) -> None:
        result = insert_trade({"symbol": "", "action": "BUY"}, db_path=tmp_db)
        assert result is None

    def test_missing_symbol_rejected(self, tmp_db: Path) -> None:
        result = insert_trade({"action": "BUY", "quantity": 10}, db_path=tmp_db)
        assert result is None


class TestMigration:
    def test_migration_idempotent(self, tmp_db: Path) -> None:
        init_db(tmp_db)
        migrate_db(tmp_db)
        migrate_db(tmp_db)
        conn = sqlite3.connect(str(tmp_db))
        cols = [row[1] for row in conn.execute("PRAGMA table_info(trades)").fetchall()]
        conn.close()
        dupes = {k: v for k, v in Counter(cols).items() if v > 1}
        assert dupes == {}


class TestQueries:
    def test_get_open_trades(self, tmp_db: Path, sample_trade_record: Dict[str, Any]) -> None:
        insert_trade(sample_trade_record, db_path=tmp_db)
        open_trades = get_open_trades(db_path=tmp_db)
        assert len(open_trades) == 1
        assert open_trades[0]["symbol"] == "AAPL"

    def test_get_closed_trades_empty(self, tmp_db: Path) -> None:
        init_db(tmp_db)
        closed = get_closed_trades(db_path=tmp_db)
        assert closed == []

    def test_update_exit_creates_closed_trade(self, tmp_db: Path, sample_trade_record: Dict[str, Any]) -> None:
        row_id = insert_trade(sample_trade_record, db_path=tmp_db)
        assert row_id is not None
        ok = update_trade_exit(
            trade_id=row_id,
            exit_price=196.0,
            exit_timestamp="2026-03-10T14:00:00",
            exit_reason="take_profit",
            realized_pnl=550.0,
            realized_pnl_pct=2.89,
            holding_days=1,
            db_path=tmp_db,
        )
        assert ok is True
        open_trades = get_open_trades(db_path=tmp_db)
        assert len(open_trades) == 0
        closed = get_closed_trades(db_path=tmp_db)
        assert len(closed) == 1
        assert closed[0]["exit_reason"] == "take_profit"
