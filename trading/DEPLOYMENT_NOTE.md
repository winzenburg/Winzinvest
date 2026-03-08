# Deployment Note

## ⚠️ Important: This System Runs Locally Only

The Mission Control trading system **cannot be deployed to Vercel** or any cloud hosting platform. It must run on your local machine.

### Why Local Only?

1. **IB Gateway Connection**: Requires direct connection to IB Gateway running on `127.0.0.1:4002`
2. **Local File System**: Reads/writes logs, JSON files, SQLite database on your machine
3. **Background Services**: Runs persistent agents (risk monitor, trade resolver, reconnection)
4. **Real-time Data**: Connects directly to IBKR API for live portfolio and market data

### GitHub Purpose

This repo is pushed to GitHub for:
- ✅ **Version control** and backup
- ✅ **Code history** and change tracking
- ✅ **Collaboration** (if needed)
- ❌ **NOT for deployment** to Vercel or cloud

### How to Run

```bash
# On your local machine
cd "/Users/ryanwinzenburg/Library/CloudStorage/GoogleDrive-ryanwinzenburg@gmail.com/My Drive/Projects/MIssion Control/trading"

# Start all services
./start.sh

# Access dashboard
open http://localhost:8002
```

### Auto-Start on Login

The system is configured to auto-start when you log in via:
```
~/Library/LaunchAgents/com.missioncontrol.trading.plist
```

### Services

All services run locally:
- **Dashboard**: http://localhost:8002 (FastAPI + vanilla JS)
- **Webhook**: http://localhost:8001 (TradingView alerts)
- **Agents**: Background risk monitoring and trade resolution
- **Scheduler**: Automated screeners and executors on market hours

### If You Need a Public Dashboard

To create a **separate** public dashboard deployable to Vercel, you would need:

1. **Cloud Database**: Supabase/Postgres for data storage
2. **Sync Script**: Periodic sync from local → cloud
3. **Read-Only API**: Separate API that reads from cloud DB
4. **Static Frontend**: Next.js/React app for Vercel
5. **No IBKR Connection**: Historical data only, no real-time

This would be a completely separate project from the local trading system.

### Current Setup

```
Local Machine (Your Mac)
├── IB Gateway (127.0.0.1:4002)
├── Trading System (./start.sh)
│   ├── Dashboard (localhost:8002)
│   ├── Webhook (localhost:8001)
│   ├── Agents (background)
│   └── Scheduler (cron jobs)
└── Browser → http://localhost:8002

GitHub (winzenburg/MissionControl)
└── Code backup only (not deployed)

Vercel
└── Not applicable for this system
```

### Summary

- ✅ Code is backed up to GitHub
- ✅ System runs locally on your Mac
- ✅ Dashboard accessible at localhost:8002
- ❌ Cannot deploy to Vercel
- ❌ Cannot run in cloud

For questions, see `DASHBOARD_GUIDE.md` or `README.md`.
