# Trading system agents

Autonomous components that run **independently** from order execution. They are not Cursor AI agents — they are part of the application.

## 1. Signal Validator Agent

**Role:** Sits between the TradingView webhook and order execution. Cross-references incoming signals against portfolio state, recent signals (dedup), market hours, and risk limits.

**Usage:** Call before queuing a signal for execution.

```python
from agents.signal_validator import validate_signal, validate_and_record_last

allowed, reason = validate_signal(
    payload,
    portfolio_shorts=current_short_symbols,
    portfolio_longs=current_long_symbols,
    secret=os.environ.get("TV_WEBHOOK_SECRET"),
    check_market_hours=True,
    check_dedup=True,
)
if not allowed:
    return 400, reason
# Else queue for execution and optionally:
allowed, reason = validate_and_record_last(payload, ...)  # writes last_signal for health check
```

**State:** `logs/recent_signal_ids.json` (dedup), `logs/last_signal.json` (for health).

---

## 2. Risk Monitor Agent

**Role:** Runs on a loop (e.g. every 30–60s). Checks portfolio drawdown, daily P&L, sector concentration. Triggers the **kill switch** if limits are breached. Completely independent from the order execution path.

**Usage:** Run as a separate process (e.g. systemd or supervisor).

```bash
cd trading/scripts && python -m agents.risk_monitor
```

**State:** Writes `trading/kill_switch.json` when triggered. Executors (`execute_candidates`, `execute_dual_mode`) check `is_kill_switch_active()` at start and do not run if active. Clear manually or via API: `agents.risk_monitor.clear_kill_switch()`.

**ClientId:** 106 (avoid overlap with executors 101–105).

---

## 3. Reconnection Agent

**Role:** Monitors the IBKR connection and handles reconnects with exponential backoff. Logs every disconnect/reconnect. Order execution is naturally paused when disconnected (no connection = no orders).

**Usage:** Run in the same process as your main app (e.g. as an asyncio task) or as a separate process that holds an IB connection and reconnects when dropped.

```bash
cd trading/scripts && python -m agents.reconnection_agent
```

**ClientId:** 107.

---

## 3b. Run Risk Monitor + Reconnection together

**Role:** Single process that runs both the Risk Monitor loop and the Reconnection Agent (shared IB connection). Use this instead of running two separate processes.

**Usage:**

```bash
cd trading/scripts && python -m agents.run_all
```

Optional env: `IB_HOST`, `IB_PORT`, `AGENTS_CLIENT_ID=110`, `RISK_MONITOR_INTERVAL=60`, `RECONNECT_CHECK_INTERVAL=30`. Stop with Ctrl+C or SIGTERM.

**Alternative (systemd):** Two separate units if you prefer — one for `python -m agents.risk_monitor`, one for `python -m agents.reconnection_agent` (each uses its own clientId 106 and 107).

---

## 4. EOD Reconciliation Agent

**Role:** Runs after market close. Compares internal trade log (`logs/executions.json`) to IBKR execution reports, flags discrepancies, and generates a summary report.

**Usage:** Run once per day after close (e.g. cron).

```bash
cd trading/scripts && python -m agents.eod_reconciliation
```

If IB is unavailable, reconciliation runs using only the internal log. Report: `logs/reconciliation_YYYY-MM-DD.md`.

**ClientId:** 108 (when connecting to IB).

**Note:** IB execution report fetching may need to be adapted to your ib_insync version (e.g. `reqExecutions()` or equivalent).

---

## 4b. TradingView Webhook Server

**Role:** HTTP endpoint that receives TradingView alerts, validates them (Signal Validator + `TV_WEBHOOK_SECRET`), then either triggers the full pipeline or executes a single signal.

**Usage:** Set `TV_WEBHOOK_SECRET` in `.env` (or env). Run:

```bash
cd trading/scripts && uvicorn agents.webhook_server:app --host 0.0.0.0 --port 8001
```

- **POST /webhook/tradingview** — Body: `{ "symbol": "AAPL", "action": "sell", "secret": "<TV_WEBHOOK_SECRET>" }` for a single signal, or `{ "trigger": "run", "secret": "..." }` to run `execute_dual_mode`. Returns 202 when accepted, 400 when validation fails, 401 when secret is wrong.
- **GET /webhook/health** — Liveness.

Single-signal requests spawn `execute_webhook_signal.py` (one-off order); trigger requests spawn `execute_dual_mode.py`. Both run as subprocesses from `trading/scripts`.

---

## 5. Health Check Agent

**Role:** HTTP endpoint that reports system status: IBKR connection, last signal received, open orders, positions, kill switch. Useful for monitoring from a phone or dashboard.

**Usage:** Requires FastAPI and uvicorn. Run from project root or `trading/scripts`:

```bash
pip install fastapi uvicorn
cd trading/scripts && uvicorn agents.health_check:app --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000/health` or `/status`. To include live IB data, the app must be run in the same process as an IB connection and call `agents.health_check.set_ib(ib)` before starting uvicorn; otherwise only file-based state (last_signal, portfolio summary, kill_switch) is returned.

---

## Shared state files

| File | Purpose |
|------|--------|
| `trading/kill_switch.json` | Set by Risk Monitor when limits breached; read by executors |
| `trading/logs/last_signal.json` | Last accepted signal (Signal Validator / webhook) |
| `trading/logs/recent_signal_ids.json` | Dedup store for Signal Validator |
| `trading/logs/peak_equity.json` | Peak equity for drawdown (Risk Monitor) |

---

## ClientId summary

| Component | ClientId |
|-----------|----------|
| execute_candidates | 101 |
| execute_longs | 102 |
| execute_dual_mode | 103 |
| sync_current_shorts | 104 |
| portfolio_snapshot | 105 |
| risk_monitor | 106 |
| reconnection_agent | 107 |
| eod_reconciliation | 108 |
| execute_webhook_signal | 109 |
| agents.run_all (Risk + Reconnect) | 110 |
