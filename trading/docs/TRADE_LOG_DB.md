# Trade log database

Queryable trade history for the execution pipeline. Used by SQLite/Postgres MCP to answer questions like “why did we get stopped out on NVDA last Tuesday?”

## Location

- **Default:** `trading/logs/trades.db` (SQLite, relative to project root)
- **Override:** Set `DATABASE_URL=sqlite:///path/to/trades.db` or a Postgres URL.

## Schema (`trades` table)

| Column         | Type    | Description |
|----------------|---------|-------------|
| id             | INTEGER | Primary key |
| symbol         | TEXT    | Ticker |
| side           | TEXT    | BUY, SELL |
| qty            | INTEGER | Quantity |
| price          | REAL    | Fill/entry price (if available) |
| entry_price    | REAL    | Entry price |
| stop_price     | REAL    | Stop order price |
| profit_price   | REAL    | Take-profit price |
| timestamp      | TEXT    | ISO timestamp |
| strategy       | TEXT    | SHORT, LONG, or strategy name |
| source_script  | TEXT    | execute_candidates.py, execute_webhook_signal.py, etc. |
| status         | TEXT    | Filled, SKIPPED, ERROR, etc. |
| slippage       | REAL    | Optional |
| stop_hit       | INTEGER | 0/1 — set when stop is hit (e.g. from reconciliation) |
| order_id       | TEXT    | IB order id |
| reason         | TEXT    | SKIPPED/ERROR reason |
| created_at     | TEXT    | Row insert time |

Indexes: `symbol`, `timestamp`, `status`.

## Writing to the DB

- **Execution pipeline:** `execute_candidates`, `execute_dual_mode`, `execute_longs`, and `execute_webhook_signal` call `trade_log_db.insert_trade(record)` when they append to the execution log.
- **Backfill:** Run from `trading/scripts`:
  ```bash
  python trade_log_db.py
  ```
  This creates the DB (if missing) and inserts all records from `logs/executions.json` (JSONL). Safe to run multiple times (inserts only; no dedupe by default).

## Querying (e.g. for MCP)

- **SQLite:** Point the SQLite MCP at `trading/logs/trades.db` (or your `DATABASE_URL` path).
- **Postgres:** Set `DATABASE_URL` and use the same schema (create table manually if using Postgres; `trade_log_db` currently uses SQLite DDL).

Example queries:

- Trades for a symbol: `SELECT * FROM trades WHERE symbol = 'NVDA' ORDER BY timestamp DESC;`
- Stopped-out / status: `SELECT * FROM trades WHERE status = 'Stopped' OR stop_hit = 1;`
- By date: `SELECT * FROM trades WHERE date(timestamp) = '2026-03-05';`

## Updating `stop_hit`

When you determine a position was stopped out (e.g. from IB execution report or reconciliation), update the row:

```sql
UPDATE trades SET stop_hit = 1, status = 'Stopped' WHERE symbol = 'NVDA' AND order_id = '...';
```

A future EOD or reconciliation step could write these updates from IB fills.
