# Mission Control — Getting Started

Everything you need to run the system from scratch, in order.

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| **Python 3.10+** | `python3 --version` |
| **Node.js 20+** | `node --version` |
| **IBKR Gateway or TWS** | Paper (port 4002) or Live (port 4001) |
| **macOS or Linux** | Windows via WSL2 should work |

---

## 1. Clone / Place the Repo

The project expects this directory layout:

```
Projects/MIssion Control/
├── trading/                  # Python trading engine
├── trading-dashboard-public/ # Next.js dashboard
├── docker-compose.yml        # Optional containerized deployment
└── GETTING_STARTED.md        # This file
```

---

## 2. Python Environment

```bash
cd trading
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Key dependencies: `ib_insync`, `apscheduler`, `fastapi`, `uvicorn`, `yfinance`, `pandas`.

---

## 3. Configure Environment Variables

### Trading engine

```bash
cp trading/.env.template trading/.env
```

Edit `trading/.env` and fill in:

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | From [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | Your Telegram user/group ID |
| `BASE_URL` | Your Cloudflare tunnel URL (or `http://localhost:8001`) |
| `IB_HOST` | IB Gateway host, usually `127.0.0.1` |
| `IB_PORT` | `4002` for paper, `4001` for live |
| `TRADING_MODE` | `paper` or `live` |
| `DAILY_LOSS_LIMIT` | e.g. `-1350` (in dollars) |

### Dashboard

```bash
cp trading-dashboard-public/.env.local.template trading-dashboard-public/.env.local
```

Generate a secret: `openssl rand -base64 32`

| Variable | Description |
|----------|-------------|
| `NEXTAUTH_SECRET` | Random 32-byte base64 string |
| `NEXTAUTH_URL` | `http://localhost:3001` |
| `DASHBOARD_PASSWORD` | Password to log into the dashboard |
| `KILL_SWITCH_PIN` | PIN required to activate the kill switch |

---

## 4. Initialize the Database

```bash
cd trading
python3 -c "from scripts.trade_log_db import init_db; init_db()"
```

This creates `trading/trades.db` with the required schema.

---

## 5. Start IB Gateway / TWS

1. Open IB Gateway or TWS
2. Log into your paper (or live) account
3. Go to **Configure → API → Settings**
4. Check **Enable ActiveX and Socket Clients**
5. Set **Socket port** to `4002` (paper) or `4001` (live)
6. Check **Allow connections from localhost only**

---

## 6. Start All Services

### Option A: Bash script (development)

```bash
cd trading
./start.sh
```

This starts:
- **Dashboard API** on port 8002
- **Health check** on port 8000
- **Next.js frontend** on port 3001
- **Webhook server** on port 8001
- **Background agents** (risk monitor, reconnection, trade resolver)
- **Scheduler** (screeners + executors on market-hours cron)
- **Watchdog** (process health monitor)

```bash
./start.sh status  # Check what's running
./start.sh logs    # Tail all logs
./start.sh stop    # Shut everything down
```

### Option B: Docker Compose (production-like)

> Note: IB Gateway still runs on your host machine — it can't run in Docker because it requires a GUI login. All containers connect to it via `host.docker.internal`.

```bash
docker compose up -d
docker compose ps      # Check health status
docker compose logs -f scheduler  # Follow a service
docker compose down    # Stop
```

---

## 7. Open the Dashboard

Navigate to: **http://localhost:3001**

You'll be redirected to the login page. Enter the `DASHBOARD_PASSWORD` you set in `.env.local`.

### First Login

An onboarding tour will start automatically. Click through to understand each section. The **?** button in the bottom-right reopens it anytime.

---

## 8. Verify the System is Working

Check these in order:

1. **System Monitor** (bottom of dashboard) — should show "healthy"
2. **Kill switch** — should show inactive (green)
3. **Mode toggle** — should show "Paper" for both Viewing and Executing
4. **Positions** tab — should show your IBKR paper account positions
5. **Overview** → Daily P&L — should reflect today's paper account activity

If the dashboard shows "Data: X minutes old" warnings, run the aggregator manually:

```bash
cd trading
python3 scripts/dashboard_data_aggregator.py
```

---

## 9. Switching to Live Trading

1. Ensure your live IBKR Gateway is running on port 4001
2. In the dashboard, change **Executing** to **Live** in the mode toggle
3. The system will rewrite `trading/.env` with `IB_PORT=4001`
4. The red "LIVE TRADING" banner will appear
5. To halt, use the **Kill Switch** (PIN required)

⚠️ **The kill switch pauses new orders but does NOT close existing positions.**

---

## 10. Running Tests

```bash
cd trading
pytest tests/ -v
```

Tests cover:
- Position sizing math (`test_executor_logic.py`)
- Kill switch file state
- Trade log database schema and queries
- Risk controls and circuit breaker
- Integration checks (`test_integration.py`)

---

## 11. Key Files Reference

| File | Purpose |
|------|---------|
| `trading/risk.json` | All risk parameters (position limits, drawdown, sectors) |
| `trading/.env` | Environment variables (IB connection, Telegram, mode) |
| `trading/logs/dashboard_snapshot.json` | What the dashboard reads |
| `trading/kill_switch.json` | Kill switch state |
| `trading/logs/user_action_audit.jsonl` | All dashboard user actions with timestamps |
| `trading/config/notification_prefs.json` | Alert channel preferences |
| `trading-dashboard-public/.env.local` | Dashboard auth and config |

---

## 12. Architecture Overview

```
IB Gateway ─────────────────────────────────────────────────┐
                                                             │
Scheduler (APScheduler)                                      │
  ├── 07:00 MT  Screeners run → watchlist_*.json             │
  ├── 08:00 MT  Executors run → orders placed ──────────────>│
  ├── 11:30 MT  Screeners refresh                            │
  ├── 14:00 MT  Options manager, EOD checks                  │
  └── Every 5m  Dashboard aggregator → snapshot.json         │
                                                             │
Background Agents (always on)                                │
  ├── Risk Monitor (60s)  ─── checks exposure, halts if bad  │
  ├── Reconnection Agent  ─── keeps IB connection alive      │
  └── Trade Resolver      ─── matches fills to outcomes      │
                                                             │
Next.js Dashboard (port 3001)                                │
  ├── Reads snapshot.json every 30s                          │
  ├── Kill switch toggle → kill_switch.json                  │
  └── Mode toggle → trading/.env + active_mode.json          │
```

---

## 13. Troubleshooting

| Symptom | Fix |
|---------|-----|
| "Screener data is X minutes old" | Run `python3 scripts/dashboard_data_aggregator.py` |
| Dashboard shows no positions | Check IB Gateway is running and connected |
| Kill switch won't activate | Check `KILL_SWITCH_PIN` in `.env.local` |
| Login fails | Verify `DASHBOARD_PASSWORD` and `NEXTAUTH_SECRET` in `.env.local` |
| Options not rolling | Check `options_position_manager.py` logs in `trading/logs/` |
| Telegram alerts not sending | Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env` |

---

## 14. Remote Access (Optional)

To access the dashboard from your phone or away from home:

1. Install [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/)
2. Create a tunnel: `cloudflared tunnel create mission-control`
3. Configure and run: `cloudflared tunnel run mission-control`

The tunnel URL is shown in `start.sh` output and sent via Telegram on startup.

> Authentication is required — the dashboard password gate protects the tunnel URL.
