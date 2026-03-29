# System Status — Mission Control on AWS VPS

**Date:** March 29, 2026  
**Status:** ✅ FULLY OPERATIONAL

---

## Live Services (All Active)

### 1. IB Gateway (Docker)
- **Status:** ✅ Running
- **Connection:** Connected to IBKR live account `U7479839`
- **Positions:** 60 open positions
- **API Port:** 4001 (via socat port mapping 4003→4001)
- **Management:** `sudo docker-compose` in `~/MissionControl/deployment`
- **VNC Access:** `vnc://44.238.166.195:5900`

### 2. Dashboard API (FastAPI)
- **Status:** ✅ Active on port 8888
- **Endpoints:** 15 total
  - `/health` - Health check
  - `/api/snapshot` - Portfolio snapshot
  - `/api/dashboard` - Full dashboard data
  - `/api/public-performance` - Public metrics
  - `/api/alerts` - Risk alerts
  - `/api/journal` - Trade journal
  - `/api/audit` - Audit trail
  - `/api/screeners` - Latest screener results
  - `/api/analytics` - Trade analytics (NEW)
  - `/api/strategy-attribution` - Strategy performance (NEW)
  - `/api/equity-history` - Historical equity curve
  - `/api/regime` - Market regime
  - `/api/trades` - Recent trades
  - `/api/execution-log` - Order execution history
  - `/api/position-integrity` - Position audit results
- **Auth:** API key via `X-API-Key` header
- **Logs:** `sudo journalctl -u trading-api.service -f`

### 3. Trading Scheduler (APScheduler)
- **Status:** ✅ Active
- **Jobs Loaded:** All production jobs
  - Pre-market: Position integrity check (6:55 AM MT)
  - Market open: Screeners, executors, risk monitors
  - Intraday: Dashboard refresh (every 5 min), options manager (every 30 min)
  - Post-close: Daily reports, snapshots
  - Weekly: Strategy attribution (Fridays), tax-loss harvesting
- **Logs:** `sudo journalctl -u trading-scheduler.service -f`

---

## Frontend (Vercel)

### Domain
- **URL:** `winzinvest.com`
- **Status:** ✅ Live, pulling data from VPS

### Environment Variables
- ✅ `TRADING_API_URL` = `http://44.238.166.195:8888`
- ✅ `TRADING_API_KEY` = `f5d98738b2178bd1939021775cc7dd172e13b3d0ba68a067b2887df00d715edc`

### Data Flow
```
Browser → Vercel (winzinvest.com) → VPS API (44.238.166.195:8888) → Trading Data
```

---

## Key Files Synced to VPS

- ✅ All trading scripts (`~/MissionControl/trading/scripts/`)
- ✅ Configuration files (`risk.json`, `adaptive_config.json`, watchlists)
- ✅ Environment variables (`.env` with credentials)
- ✅ Historical logs (`sod_equity_history.jsonl`, analytics, attribution)
- ✅ Database (`logs/trades.db`)

---

## Critical Fixes Applied

### 1. Docker Port Mapping (RESOLVED)
**Issue:** Port 4001 not accessible  
**Root Cause:** `socat` forwards `4003→4001` internally  
**Fix:** Changed `docker-compose.yml` from `4001:4001` to `4001:4003`

### 2. API Access Disabled (RESOLVED)
**Issue:** Gateway UI showed "connected" but API timed out  
**Root Cause:** `AcceptIncomingConnectionAction` was empty  
**Fix:** Added `TWS_ACCEPT_INCOMING=accept` environment variable

### 3. Missing Analytics Endpoints (RESOLVED)
**Issue:** Dashboard showed "Analytics not available from remote backend"  
**Root Cause:** VPS API missing `/api/analytics` and `/api/strategy-attribution`  
**Fix:** Added both endpoints to `dashboard_api.py`

### 4. Equity History Missing (RESOLVED)
**Issue:** "No equity history data yet"  
**Root Cause:** `sod_equity_history.jsonl` not synced to VPS  
**Fix:** Synced file from Mac to VPS

---

## Current Performance (Live Data)

| Metric | Value |
|--------|-------|
| Net Liquidation Value | $172,726.75 |
| Daily P&L | +$1,504.96 |
| 30-Day Return | +62.89% |
| Win Rate | 66.67% |
| Profit Factor | 2.79 |
| Max Drawdown | -5.51% |
| Sharpe Ratio | 3.26 |
| Total Trades | 75 |

---

## Daily Operations

### Monitor Services
```bash
ssh -i ~/.ssh/winzinvest-trading.pem ubuntu@44.238.166.195

# Check all services
sudo systemctl status ib-gateway trading-api trading-scheduler

# View logs
sudo journalctl -u trading-scheduler -f
sudo journalctl -u trading-api -f
sudo docker logs -f ib-gateway
```

### VNC Access (for IB Gateway 2FA)
```bash
open vnc://44.238.166.195:5900
# Password: [from .env VNC_PASSWORD]
```

### Test IB API Connection
```bash
ssh -i ~/.ssh/winzinvest-trading.pem ubuntu@44.238.166.195
source ~/trading-env/bin/activate
python3 ~/test_ib.py
```

### Generate Fresh Dashboard Snapshot
```bash
cd ~/MissionControl/trading/scripts
source ~/trading-env/bin/activate
python3 dashboard_data_aggregator.py
```

---

## Next Trading Day

The scheduler will automatically:
1. **6:55 AM MT** - Position integrity check, regime update
2. **7:00 AM MT** - Episodic pivot screener (gap opportunities)
3. **7:30 AM MT** - Gap monitor, pre-market orders
4. **9:30 AM MT** - Market open: screeners fire, executors place orders
5. **10:00 AM MT** - Post-open executors (mean reversion, longs)
6. **Every 5 min** - Dashboard snapshot refresh
7. **Every 30 min** - Options manager (profit-take, rolls), winner pyramid, bobblehead exit
8. **3:55 PM MT** - Pre-close snapshot, daily reports
9. **4:00 PM MT** - EOD reconciliation, regime check

All jobs run automatically - no manual intervention required.

---

## Backup & Monitoring

- ✅ Daily backups: 2:00 AM UTC → `~/backups/` (7-day retention)
- ✅ Telegram alerts configured for: position integrity, assignment risk, kill switch
- ✅ Email notifications for: daily reports, options activity, significant moves

---

## Cost

**Total Monthly Cost:** $12.00 (AWS Lightsail 2GB instance)

---

## Documentation

- `MIGRATION.md` - Full migration runbook (10 phases)
- `MIGRATION_COMPLETE.md` - Migration summary and operations guide
- `SECURITY.md` - Security hardening details
- `START_HERE.md` - Quick setup guide
- `QUICK_SETUP.md` - Step-by-step with credentials
- `YOUR_DEPLOYMENT_COMMANDS.md` - Personalized command reference
- `SYSTEM_STATUS.md` - This file (current system status)

---

**Migration Status:** 🎉 COMPLETE - System fully operational on VPS
