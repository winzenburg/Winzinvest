# Full IBKR Automation

Run the full Mission Control stack so screeners and executors run on a schedule and background agents monitor risk and IB. **No TradingView alerts required** for this flow.

---

## What runs

| Service | What it does |
|--------|----------------|
| **Dashboard** | Web UI at http://localhost:8002 — status, portfolio, logs |
| **Webhook** | Listens on port 8001 for TradingView (optional extra trigger) |
| **Agents** | Risk monitor, reconnection, trade outcome resolver (shared IB connection) |
| **Scheduler** | Cron-style jobs (Mon–Fri, Mountain Time): pre-market screeners → market open execution → options → midday → afternoon → pre-close → post-close |

Schedule (Mountain Time):

- **07:00** — Sync positions, screeners (NX production, longs, mean reversion), export TV watchlist  
- **07:30** — Execute: longs, dual-mode (shorts + longs), mean reversion  
- **08:00** — Options executor  
- **10:00** — Midday screeners  
- **10:15** — Midday execution  
- **12:00** — Pairs screener + execute  
- **14:00** — Portfolio snapshot, daily report  
- **14:30** — Strategy analytics, adaptive params, sector rotation, sync shorts  

---

## One-time setup

1. **IB Gateway**  
   Install and log in. Default port **4002** (or 4001). Mission Control expects **127.0.0.1:4002**.

2. **Python deps** (from repo root or `trading/`):
   ```bash
   pip install apscheduler fastapi uvicorn ib_insync yfinance
   ```

3. **Secrets (optional)**  
   For the webhook (TradingView): set `TV_WEBHOOK_SECRET` in `trading/.env` or `~/.cursor/.env.local`.  
   `./start.sh` loads `trading/.env` and `~/.cursor/.env.local` so all services see it.

---

## Start full automation

From the **trading** directory:

```bash
cd "/Users/ryanwinzenburg/Library/CloudStorage/GoogleDrive-ryanwinzenburg@gmail.com/My Drive/Projects/MIssion Control/trading"
./start.sh
```

That starts dashboard, webhook, agents, and scheduler in the background. Ensure **IB Gateway is already running** on 127.0.0.1:4002 before or right after.

**Check status:**

```bash
./start.sh status
```

**Follow logs:**

```bash
./start.sh logs
```

**Stop everything:**

```bash
./start.sh stop
```

---

## Verify

- **Dashboard:** http://localhost:8002  
- **Webhook health:** `curl -s http://127.0.0.1:8001/webhook/health` → `{"ok":true,"service":"webhook"}`  
- **IB:** `./start.sh status` shows `ib_gateway: REACHABLE` when port 4002 is open.

---

## Optional: run as macOS LaunchAgents

To have the scheduler (and optionally other services) start at login and survive restarts, use:

```bash
./setup_autonomous_trading.sh
```

That creates and loads `com.missioncontrol.scheduler.plist`. For **all four** services (dashboard, webhook, agents, scheduler) in one shot, use `./start.sh` and keep that terminal or run it in a persistent session (e.g. `tmux`/`screen`), or extend `setup_autonomous_trading.sh` to add more plists.

---

## Related

- [WEBHOOK_AND_AGGREGATOR_START.md](./WEBHOOK_AND_AGGREGATOR_START.md) — Webhook + data aggregator only  
- [OPENCLAW_TRADINGVIEW_INTEGRATION.md](./OPENCLAW_TRADINGVIEW_INTEGRATION.md) — TradingView webhook payload and URL  
- [DASHBOARD_GUIDE.md](./DASHBOARD_GUIDE.md) — Dashboard and API
