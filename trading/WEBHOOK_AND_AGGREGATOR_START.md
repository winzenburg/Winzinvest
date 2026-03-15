# Start Webhook + Data Aggregator (and confirm IB)

Do these in order. **IB Gateway must be running** (and logged in) first.

---

## Step 1: Confirm IB Gateway is reachable

The **data aggregator** and the **FastAPI webhook’s executor** (`execute_webhook_signal.py`) use IB on **port 4002** (aggregator clientId 199, executor clientId 109).

- **IB Gateway** → usually **4001** or **4002**
- **TWS (Trader Workstation)** → **7497** (paper) or **7496** (live)

We’ll confirm IB by running the aggregator once (Step 3).

---

## Step 2: Start the FastAPI webhook (Terminal 1)

**Dependencies:** FastAPI and uvicorn. Install if needed:

```bash
pip3 install fastapi uvicorn
```

From the **Mission Control** repo, `trading/scripts`:

```bash
cd "/Users/ryanwinzenburg/Library/CloudStorage/GoogleDrive-ryanwinzenburg@gmail.com/My Drive/Projects/MIssion Control/trading/scripts"
```

Set the webhook secret (required for TradingView alerts):

```bash
export TV_WEBHOOK_SECRET=your_secret_here
# or: export WEBHOOK_SECRET=your_secret_here
```

Start the FastAPI webhook server:

```bash
PYTHONPATH="." python3 -m uvicorn agents.webhook_server:app --host 0.0.0.0 --port 8001
```

You should see the uvicorn startup message (port 8001).

**Confirm it’s up:**

```bash
curl -s http://127.0.0.1:8001/webhook/health
# Expect: {"ok":true,"service":"webhook"}
```

**TradingView:** Point alerts to `http://your-machine:8001/webhook/tradingview` (use a tunnel URL if TradingView is in the cloud). Body: JSON with `symbol`, `action` (or `side`), and `secret` = `TV_WEBHOOK_SECRET`.

**Note:** The webhook server does not connect to IB itself; it spawns `execute_webhook_signal.py`, which connects to IB (127.0.0.1:4002) when an alert is accepted. IB is verified in Step 3.

---

## Step 3: Run the data aggregator once (verify IB)

In a **second terminal**:

```bash
cd "/Users/ryanwinzenburg/Library/CloudStorage/GoogleDrive-ryanwinzenburg@gmail.com/My Drive/Projects/MIssion Control/trading/scripts"
PYTHONPATH="." python3 dashboard_data_aggregator.py
```

- If you see **"Connected to IBKR"** and **"Dashboard snapshot written to ..."** → IB is reachable and the dashboard snapshot is updated.
- If you see **"Could not connect to IBKR"** or a connection error → check:
  - IB Gateway is running and logged in.
  - Port: aggregator uses **4002**. If your Gateway uses 4001, you’ll need to change the port in `dashboard_data_aggregator.py` (line ~377) or change the Gateway port.

This step **proves** that at least one process (the aggregator) can see IB.

---

## Step 4: Keep the FastAPI webhook running

Leave **Terminal 1** (uvicorn webhook server) running. That process receives TradingView alerts, validates them, and spawns the executor to send orders to IB (127.0.0.1:4002).

---

## Step 5: (Optional) Refresh dashboard data on a schedule

The aggregator is one-shot. To keep Mission Control’s dashboard up to date:

- **Option A:** Run it every 5 minutes via cron:
  ```bash
  */5 * * * * cd /path/to/trading/scripts && PYTHONPATH="." python3 dashboard_data_aggregator.py
  ```
- **Option B:** Run it in a loop in a third terminal:
  ```bash
  while true; do PYTHONPATH="." python3 dashboard_data_aggregator.py; sleep 300; done
  ```

---

## Quick reference

| Component            | Port | IB port | IB clientId |
|----------------------|------|---------|-------------|
| FastAPI webhook      | 8001 | 4002 (executor) | 109 |
| Data aggregator      | —    | 4002    | 199 |

**Alternative:** To use the OpenClaw listener (Telegram approve flow) instead, see [OPENCLAW_TRADINGVIEW_INTEGRATION.md](./OPENCLAW_TRADINGVIEW_INTEGRATION.md) — script `webhook_listener.py`, port 5001, `MOLT_WEBHOOK_SECRET`.
