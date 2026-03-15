# TradingView ↔ Mission Control Webhooks

How TradingView alerts reach Mission Control and execute (or get approved) via webhooks.

---

## 1. Recommended: FastAPI webhook (no OpenClaw)

**Use this path** for TradingView → validate → execute. No Telegram approve step; validation and execution are handled by the FastAPI server and `execute_webhook_signal.py`.

### Flow

```
TradingView (Pine alert)
   → POST JSON to /webhook/tradingview (port 8001)
   → FastAPI webhook server validates (TV_WEBHOOK_SECRET, symbol, action, portfolio, market hours, dedup)
   → Spawns execute_webhook_signal.py → IB Gateway (127.0.0.1:4002, clientId 109)
```

### Server

| Item | Detail |
|------|--------|
| **Script** | `trading/scripts/agents/webhook_server.py` |
| **Port** | 8001 |
| **Endpoint** | `POST /webhook/tradingview` |
| **Health** | `GET /webhook/health` |

**Start:**
```bash
cd trading/scripts
export TV_WEBHOOK_SECRET=your_secret_here   # or WEBHOOK_SECRET
PYTHONPATH="." python3 -m uvicorn agents.webhook_server:app --host 0.0.0.0 --port 8001
```

**Env:** `TV_WEBHOOK_SECRET` (or `WEBHOOK_SECRET`). Optional: `.env` in `trading/scripts`, `trading/scripts/agents`, or project root.

**Payload (TradingView):**
- Single signal: `{ "symbol": "AAPL", "action": "buy" | "sell", "secret": "<TV_WEBHOOK_SECRET>" }`  
  (also accepts `side` instead of `action`, `ticker` instead of `symbol`.)
- Full pipeline: `{ "trigger": "run", "secret": "<TV_WEBHOOK_SECRET>" }` → runs `execute_dual_mode.py`.
- Pullback entry: `{ "symbol": "AAPL", "entry_type": "pullback", "action": "BUY", "secret": "..." }`.

Validation (market hours, dedup, portfolio/sector gates, kill switch) is applied before the executor is spawned. Executor connects to IB at 127.0.0.1:4002 (clientId 109).

### TradingView alert settings (FastAPI)

- **Webhook URL (local):** `http://127.0.0.1:8001/webhook/tradingview`
- **Webhook URL (public):** Use a tunnel to your machine, then e.g. `https://your-tunnel.example.com/webhook/tradingview`

### Quick checks (FastAPI)

```bash
# Server up?
curl -s http://127.0.0.1:8001/webhook/health

# Test (replace YOUR_SECRET)
curl -X POST http://127.0.0.1:8001/webhook/tradingview \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","action":"buy","secret":"YOUR_SECRET"}'
```

---

## 2. Optional: OpenClaw webhook listener (approve flow)

If you want **Telegram approve/reject** before execution, use the OpenClaw listener instead of (or in addition to) the FastAPI webhook.

### Flow

```
TradingView → POST to port 5001 /webhook
   → Validate + filter (daily loss, earnings blackout, correlation, etc.)
   → Telegram message with approve / reject buttons
   → On approve → execution (IB Gateway)
```

| Item | Detail |
|------|--------|
| **Script** | `trading/scripts/webhook_listener.py` |
| **Port** | 5001 |
| **Endpoint** | `POST /webhook` |
| **Health** | `GET /health` |

**Start:** `cd trading/scripts && python3 webhook_listener.py`  
**Env:** `MOLT_WEBHOOK_SECRET`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `IB_HOST`, `IB_PORT`, `BASE_URL`.

Set **`FULL_AUTO=1`** to execute every passing alert immediately (no approve step).  
`curl http://127.0.0.1:5001/status` shows `full_auto` and `canary`.

- **Webhook URL:** `http://127.0.0.1:5001/webhook` (or your tunnel URL + `/webhook`).
- **Payload:** JSON with `secret` = `MOLT_WEBHOOK_SECRET`; e.g. `symbol`, `side`, `score`, `chart_url`.

---

## 3. Integration summary

| Path | Port | Secret env | Approve step | Use when |
|------|------|------------|--------------|----------|
| **FastAPI webhook** | 8001 | `TV_WEBHOOK_SECRET` | No | Default: validate → execute |
| OpenClaw listener | 5001 | `MOLT_WEBHOOK_SECRET` | Yes (or FULL_AUTO) | You want Telegram approve |

Use **one** as the target for TradingView alerts (or different alerts to different URLs). Both enforce safety (daily loss, earnings blackout, kill switch, etc.); FastAPI does it in the server + executor; OpenClaw does it in the listener before Telegram.

---

## 4. Related docs

- **Alert setup:** [TRADINGVIEW_ALERT_SETUP.md](./TRADINGVIEW_ALERT_SETUP.md)
- **Runbook (start webhook + aggregator):** [WEBHOOK_AND_AGGREGATOR_START.md](./WEBHOOK_AND_AGGREGATOR_START.md)
- **Pine scripts:** `tradingview/*.pine` (alertcondition / alert() for webhook payloads)
