"""
Trade log database — SQLite (or Postgres via DATABASE_URL) for queryable trade history.

Schema supports: symbol, side, qty, price, timestamp, strategy, source_script,
status, slippage, stop_hit, order_id, reason, entry/stop/profit prices,
plus enriched entry-time metrics and exit outcome columns for the self-learning loop.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

# Default SQLite path (workspace)
from paths import WORKSPACE, TRADING_DIR
DEFAULT_DB_PATH = TRADING_DIR / "logs" / "trades.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  qty INTEGER NOT NULL DEFAULT 0,
  price REAL,
  entry_price REAL,
  stop_price REAL,
  profit_price REAL,
  timestamp TEXT NOT NULL,
  strategy TEXT,
  source_script TEXT,
  status TEXT,
  slippage REAL,
  stop_hit INTEGER DEFAULT 0,
  order_id TEXT,
  reason TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  -- Entry-time metrics (self-learning)
  regime_at_entry TEXT,
  conviction_score REAL,
  atr_at_entry REAL,
  rs_pct REAL,
  composite_score REAL,
  structure_quality REAL,
  rvol_atr REAL,
  initial_risk_r REAL,
  commission REAL,
  -- Exit outcome columns (filled by trade_outcome_resolver)
  exit_price REAL,
  exit_timestamp TEXT,
  exit_reason TEXT,
  realized_pnl REAL,
  realized_pnl_pct REAL,
  r_multiple REAL,
  holding_days INTEGER,
  max_adverse_excursion REAL,
  max_favorable_excursion REAL
);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
"""

_MIGRATION_COLUMNS: List[tuple] = [
    ("regime_at_entry", "TEXT"),
    ("conviction_score", "REAL"),
    ("atr_at_entry", "REAL"),
    ("rs_pct", "REAL"),
    ("composite_score", "REAL"),
    ("structure_quality", "REAL"),
    ("rvol_atr", "REAL"),
    ("initial_risk_r", "REAL"),
    ("slippage", "REAL"),
    ("commission", "REAL"),
    ("exit_price", "REAL"),
    ("exit_timestamp", "TEXT"),
    ("exit_reason", "TEXT"),
    ("realized_pnl", "REAL"),
    ("realized_pnl_pct", "REAL"),
    ("r_multiple", "REAL"),
    ("holding_days", "INTEGER"),
    ("max_adverse_excursion", "REAL"),
    ("max_favorable_excursion", "REAL"),
    # Audit flag: set when a trade should not count toward performance metrics.
    # Preserves the record but excludes it from PnL calculations.
    ("excluded_from_pnl", "TEXT"),
]


def _get_db_path() -> Path:
    import os
    url = os.environ.get("DATABASE_URL", "").strip()
    if url and url.startswith("sqlite:///"):
        return Path(url.replace("sqlite:///", ""))
    if url and not url.startswith("postgres"):
        return Path(url)
    return DEFAULT_DB_PATH


def _normalize_side(record: Dict[str, Any]) -> str:
    action = record.get("action") or record.get("type") or ""
    if isinstance(action, str):
        a = action.upper()
        if a in ("SELL", "SHORT"):
            return "SELL"
        if a in ("BUY", "LONG"):
            return "BUY"
    return "SELL"


def init_db(db_path: Optional[Path] = None) -> None:
    """Create trades table and indexes if they do not exist, then migrate."""
    path = db_path or _get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    import sqlite3
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()
    migrate_db(path)


def migrate_db(db_path: Optional[Path] = None) -> None:
    """Add any missing columns from _MIGRATION_COLUMNS to the trades table.

    Safe to call repeatedly — only adds columns that don't already exist.
    """
    path = db_path or _get_db_path()
    if not path.exists():
        return
    import sqlite3
    conn = sqlite3.connect(str(path))
    try:
        cur = conn.execute("PRAGMA table_info(trades)")
        existing = {row[1] for row in cur.fetchall()}
        for col_name, col_type in _MIGRATION_COLUMNS:
            if col_name not in existing:
                conn.execute(f"ALTER TABLE trades ADD COLUMN {col_name} {col_type}")
        conn.commit()
    finally:
        conn.close()


def insert_trade(record: Dict[str, Any], db_path: Optional[Path] = None) -> Optional[int]:
    """
    Insert one trade from an execution-style record. Returns row id or None on error.
    Handles both full execution entries and SKIPPED/ERROR stubs, including enriched
    entry-time metrics and exit outcome fields when present.
    """
    path = db_path or _get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    init_db(path)

    symbol = (record.get("symbol") or "").strip().upper()
    if not symbol:
        return None
    side = _normalize_side(record)
    qty = int(record.get("quantity") or record.get("qty") or 0)
    price = _float(record.get("entry_price") or record.get("price"))
    entry_price = _float(record.get("entry_price"))
    stop_price = _float(record.get("stop_price"))
    profit_price = _float(record.get("profit_price"))
    if price is None and entry_price is not None:
        price = entry_price
    ts = record.get("timestamp") or record.get("timestamp_iso") or ""
    strategy = record.get("type") or record.get("strategy") or ""
    source_script = record.get("source_script") or record.get("source") or ""
    status = (record.get("status") or "").strip()
    slippage = _float(record.get("slippage"))
    stop_hit = 1 if record.get("stop_hit") else 0
    order_id = str(record.get("orderId") or record.get("order_id") or "")
    reason = (record.get("reason") or "").strip() or None

    regime_at_entry = record.get("regime_at_entry") or None
    conviction_score = _float(record.get("conviction_score"))
    atr_at_entry = _float(record.get("atr_at_entry"))
    rs_pct = _float(record.get("rs_pct"))
    composite_score = _float(record.get("composite_score"))
    structure_quality = _float(record.get("structure_quality"))
    rvol_atr = _float(record.get("rvol_atr"))
    initial_risk_r = _float(record.get("initial_risk_r"))
    slippage_val = _float(record.get("slippage"))
    commission = _float(record.get("commission"))

    import sqlite3
    try:
        conn = sqlite3.connect(str(path))
        try:
            cur = conn.execute(
                """INSERT INTO trades (
                    symbol, side, qty, price, entry_price, stop_price, profit_price,
                    timestamp, strategy, source_script, status, slippage, stop_hit, order_id, reason,
                    regime_at_entry, conviction_score, atr_at_entry, rs_pct,
                    composite_score, structure_quality, rvol_atr,
                    initial_risk_r, commission
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    symbol, side, qty, price, entry_price, stop_price, profit_price,
                    ts, strategy, source_script, status, slippage_val or slippage, stop_hit, order_id, reason,
                    regime_at_entry, conviction_score, atr_at_entry, rs_pct,
                    composite_score, structure_quality, rvol_atr,
                    initial_risk_r, commission,
                ),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()
    except Exception:
        return None


def update_trade_exit(
    trade_id: int,
    exit_price: float,
    exit_timestamp: str,
    exit_reason: str,
    realized_pnl: float,
    realized_pnl_pct: float,
    holding_days: int,
    max_adverse_excursion: Optional[float] = None,
    max_favorable_excursion: Optional[float] = None,
    commission: Optional[float] = None,
    db_path: Optional[Path] = None,
) -> bool:
    """Update a trade record with exit outcome details and R-multiple. Returns True on success."""
    path = db_path or _get_db_path()
    if not path.exists():
        return False
    import sqlite3
    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute("SELECT initial_risk_r FROM trades WHERE id = ?", (trade_id,)).fetchone()
            r_multiple: Optional[float] = None
            if row:
                initial_risk = row["initial_risk_r"]
                if initial_risk and float(initial_risk) > 0:
                    r_multiple = round(realized_pnl / float(initial_risk), 2)

            conn.execute(
                """UPDATE trades SET
                    exit_price = ?, exit_timestamp = ?, exit_reason = ?,
                    realized_pnl = ?, realized_pnl_pct = ?, r_multiple = ?,
                    holding_days = ?,
                    max_adverse_excursion = ?, max_favorable_excursion = ?,
                    commission = COALESCE(?, commission)
                WHERE id = ?""",
                (
                    exit_price, exit_timestamp, exit_reason,
                    realized_pnl, realized_pnl_pct, r_multiple,
                    holding_days,
                    max_adverse_excursion, max_favorable_excursion,
                    commission,
                    trade_id,
                ),
            )
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception:
        return False


def get_open_trades(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Return trades where status='Filled' and exit_price IS NULL (open positions)."""
    path = db_path or _get_db_path()
    if not path.exists():
        return []
    import sqlite3
    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM trades WHERE status = 'Filled' AND exit_price IS NULL"
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
    except Exception:
        return []


def get_closed_trades(
    since_days: Optional[int] = 90,
    db_path: Optional[Path] = None,
    include_excluded: bool = False,
) -> List[Dict[str, Any]]:
    """Return trades with exit data within the given rolling window.

    Pass since_days=None to return all closed trades.
    By default, trades flagged with excluded_from_pnl are omitted from results.
    Pass include_excluded=True to retrieve all records including flagged ones.
    """
    path = db_path or _get_db_path()
    if not path.exists():
        return []
    import sqlite3
    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        try:
            exclusion_clause = "" if include_excluded else "AND excluded_from_pnl IS NULL"
            if since_days is None:
                rows = conn.execute(
                    f"SELECT * FROM trades WHERE exit_price IS NOT NULL {exclusion_clause} ORDER BY exit_timestamp DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    f"""SELECT * FROM trades
                       WHERE exit_price IS NOT NULL
                         AND exit_timestamp >= datetime('now', ?)
                         {exclusion_clause}
                       ORDER BY exit_timestamp DESC""",
                    (f"-{since_days} days",),
                ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
    except Exception:
        return []


def log_trade(
    symbol: str,
    action: str,
    qty: int,
    price: float,
    strategy: str = "",
    source_script: str = "",
    db_path: Optional[Path] = None,
    **extra: Any,
) -> Optional[int]:
    """Convenience wrapper around insert_trade for simple trade logging."""
    from datetime import datetime

    record: Dict[str, Any] = {
        "symbol": symbol,
        "action": action,
        "quantity": qty,
        "price": price,
        "entry_price": price,
        "strategy": strategy,
        "source_script": source_script,
        "status": "Filled",
        "timestamp": datetime.now().isoformat(),
    }
    record.update(extra)
    return insert_trade(record, db_path=db_path)


def flag_trades_excluded(
    trade_ids: List[int],
    reason: str,
    db_path: Optional[Path] = None,
) -> int:
    """Mark specific trade IDs as excluded from PnL calculations.

    Records are preserved for audit purposes but filtered out by get_closed_trades()
    unless include_excluded=True is passed.  Returns number of rows updated.
    """
    path = db_path or _get_db_path()
    if not path.exists() or not trade_ids:
        return 0
    import sqlite3
    try:
        conn = sqlite3.connect(str(path))
        try:
            placeholders = ",".join("?" * len(trade_ids))
            cur = conn.execute(
                f"UPDATE trades SET excluded_from_pnl = ? WHERE id IN ({placeholders})",
                [reason, *trade_ids],
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()
    except Exception:
        return 0


def get_recent_trades(
    limit: int = 20,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Return the most recent trades ordered by id DESC."""
    path = db_path or _get_db_path()
    if not path.exists():
        return []
    import sqlite3
    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
    except Exception:
        return []


def _float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def backfill_from_executions_json(
    log_path: Optional[Path] = None,
    db_path: Optional[Path] = None,
) -> int:
    """
    Read executions.json (JSONL) and insert each line as a trade if not already present.
    Returns number of rows inserted. Does not deduplicate by content; idempotency
    can be added later (e.g. by order_id + timestamp).
    """
    path = log_path or (TRADING_DIR / "logs" / "executions.json")
    if not path.exists():
        return 0
    db = db_path or _get_db_path()
    init_db(db)
    inserted = 0
    for line in path.read_text().strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            import json
            record = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(record, dict):
            continue
        if insert_trade(record, db_path=db) is not None:
            inserted += 1
    return inserted


if __name__ == "__main__":
    import sys
    path = _get_db_path()
    init_db(path)
    print("DB initialized:", path)
    if (TRADING_DIR / "logs" / "executions.json").exists():
        n = backfill_from_executions_json()
        print("Backfilled", n, "trades")
