# VPS Deployment Status

**Date:** March 28, 2026
**Status:** ✅ Code Complete - Ready for Manual Deployment

---

## What's Been Completed

### ✅ Phase 1: FastAPI Dashboard API

**Status:** Complete and tested locally

Created `trading/scripts/agents/dashboard_api.py` with comprehensive endpoints:

- `/health` - System health check (no auth)
- `/api/dashboard` - Full snapshot data (auth required)
- `/api/public-performance` - Public metrics (no auth)
- `/api/snapshot` - Alias for dashboard (auth required)
- `/api/alerts` - Risk alerts and warnings (auth required)
- `/api/journal` - Trade journal (auth required)
- `/api/audit` - Audit trail (auth required)
- `/api/screeners` - Latest screener results (auth required)
- `/api/strategy-attribution` - Strategy performance (auth required)
- `/api/backtest-results` - Backtest benchmarks (auth required)
- `/api/kill-switch` - Emergency stop (auth + PIN required)
- `/api/system-status` - System summary (auth required)
- `/api/equity-history` - 30-day equity curve (auth required)

**Features:**
- API key authentication via `x-api-key` header
- CORS configured for winzinvest.com and localhost
- Automatic .env loading for configuration
- Comprehensive error handling

**Local test:** ✅ Passed
```bash
cd trading && PYTHONPATH=scripts python3 -m agents.dashboard_api
curl http://localhost:8000/health
# Response: {"status":"ok","timestamp":"...","service":"winzinvest-dashboard-api"}
```

---

### ✅ Phase 2: Vercel API Routes Updated

**Status:** Complete

All Vercel API routes now support dual-mode operation:
- **Local mode:** Reads from filesystem when `TRADING_API_URL` not set
- **Remote mode:** Fetches from VPS API when `TRADING_API_URL` is set

**Updated routes:**
- ✅ `/api/dashboard` - Already used `getSnapshot()` (supports remote)
- ✅ `/api/public-performance` - Already had static fallback
- ✅ `/api/alerts` - Already supports `isRemote`
- ✅ `/api/journal` - Already supports `isRemote`
- ✅ `/api/audit` - Already supports `isRemote`
- ✅ `/api/screeners` - **UPDATED** to support `isRemote`
- ✅ `/api/strategy-attribution` - Already supports `isRemote`
- ✅ `/api/equity-history` - Already supports `isRemote`
- ✅ `/api/backtest-results` - Already supports `isRemote`
- ✅ `/api/system-status` - Already uses `TRADING_HEALTH_URL`

**Infrastructure:**
- `lib/data-access.ts` provides `isRemote`, `remoteGet()`, and `remotePost()`
- All routes check `process.env.TRADING_API_URL` automatically
- API key sent via `x-api-key` header from `process.env.TRADING_API_KEY`

---

### ✅ Phase 3: Docker Configuration

**Status:** Complete

Created `deployment/docker-compose.yml` for IB Gateway:
- Image: `ghcr.io/gnzsnz/ib-gateway:10.45.1b`
- Ports: 4001 (live), 4002 (paper), 5900 (VNC)
- Auto-restart: enabled
- Health check: included
- Volume: `./ib-data` for persistence

**Environment variables:**
- `TWS_USERID`, `TWS_PASSWORD`, `VNC_SERVER_PASSWORD`
- `TRADING_MODE`, `TWOFA_TIMEOUT_ACTION`
- Auto-restart at 23:50 ET (before IB maintenance)

---

### ✅ Phase 4: Systemd Services

**Status:** Complete

Created 3 systemd unit files:

1. **`ib-gateway.service`**
   - Manages Docker Compose for IB Gateway
   - Starts after Docker
   - OneShot with RemainAfterExit

2. **`trading-scheduler.service`**
   - Runs APScheduler daemon
   - Requires IB Gateway
   - Auto-restart on failure

3. **`trading-api.service`**
   - Runs FastAPI dashboard API via Uvicorn
   - Listens on 0.0.0.0:8000
   - 2 workers for better performance

All services:
- Run as `ubuntu` user
- Auto-start on boot
- Journal logging enabled
- Resource limits configured

---

### ✅ Phase 5: Deployment Scripts

**Status:** Complete

Created deployment automation:

1. **`deploy-to-vps.sh`**
   - Syncs code from Mac to VPS
   - Creates `.env` template
   - Provides step-by-step next steps
   - **Usage:** `./deployment/scripts/deploy-to-vps.sh VPS_IP`

2. **`backup-trading-data.sh`**
   - Daily automated backups
   - 7-day local retention
   - Optional S3 sync
   - Cron-ready

---

### ✅ Phase 6: Documentation

**Status:** Complete

Created comprehensive guides:

1. **`deployment/README.md`**
   - Complete deployment overview
   - Architecture diagram
   - Quick start guide
   - Troubleshooting

2. **`deployment/MIGRATION.md`**
   - Step-by-step migration runbook
   - 12 phases with exact commands
   - Timeline: ~2.5 hours
   - Common issues and solutions

3. **`deployment/SECURITY.md`**
   - SSH key setup
   - UFW firewall configuration
   - Fail2Ban setup
   - API authentication
   - Kill switch PIN
   - Optional SSL/TLS
   - Emergency procedures

4. **`trading/requirements.txt`**
   - All Python dependencies
   - VPS-ready format
   - Version pinning

---

## What Requires Manual Execution

The following steps **require you to manually execute** them following the guides:

### 🔲 Phase 7: Provision AWS Lightsail

**Action Required:** Follow [MIGRATION.md Phase 1](./MIGRATION.md#phase-1-provision-lightsail-15-min)

1. Create Lightsail instance ($12/mo, 2GB RAM)
2. Configure firewall rules
3. Assign static IP

**Estimated time:** 15 minutes

---

### 🔲 Phase 8: Deploy IB Gateway

**Action Required:** Follow [MIGRATION.md Phase 6](./MIGRATION.md#phase-6-deploy-ib-gateway-30-min)

1. Install Docker on VPS
2. Copy `docker-compose.yml` to VPS
3. Start IB Gateway container
4. Complete 2FA via VNC

**Estimated time:** 30 minutes

---

### 🔲 Phase 9: Install Python Environment

**Action Required:** Follow [MIGRATION.md Phase 5](./MIGRATION.md#phase-5-install-dependencies-15-min)

1. Install Python 3.11 on VPS
2. Create virtual environment
3. Install dependencies from `requirements.txt`
4. Test IB connection

**Estimated time:** 15 minutes

---

### 🔲 Phase 10: Sync Trading Scripts

**Action Required:** Follow [MIGRATION.md Phase 3](./MIGRATION.md#phase-3-deploy-code-10-min)

**Option A:** Use automated script
```bash
./deployment/scripts/deploy-to-vps.sh YOUR_VPS_IP
```

**Option B:** Manual rsync
```bash
rsync -avz --exclude=".git" trading/ ubuntu@YOUR_VPS_IP:~/MissionControl/trading/
```

**Estimated time:** 10 minutes

---

### 🔲 Phase 11: Configure Services

**Action Required:** Follow [MIGRATION.md Phase 7](./MIGRATION.md#phase-7-install-services-10-min)

1. Copy systemd service files to `/etc/systemd/system/`
2. Enable services
3. Start services
4. Verify status

**Estimated time:** 10 minutes

---

### 🔲 Phase 12: Update Vercel

**Action Required:** Follow [MIGRATION.md Phase 9](./MIGRATION.md#phase-9-update-vercel-5-min)

1. Get `DASHBOARD_API_KEY` from VPS `.env`
2. Add to Vercel environment variables:
   - `TRADING_API_URL=http://YOUR_VPS_IP:8000`
   - `TRADING_API_KEY=your_key_here`
3. Redeploy Vercel

**Estimated time:** 5 minutes

---

### 🔲 Phase 13: Security Hardening

**Action Required:** Follow [SECURITY.md](./SECURITY.md)

1. Set up SSH key authentication
2. Configure UFW firewall
3. Install Fail2Ban
4. Verify API authentication
5. Set up monitoring

**Estimated time:** 20 minutes

---

### 🔲 Phase 14: Migration Cutover

**Action Required:** Follow [MIGRATION.md Phase 10](./MIGRATION.md#phase-10-stop-mac-scheduler-5-min)

**CRITICAL:** Only do this after verifying VPS is working!

1. Verify VPS is trading
2. Test dashboard loads from VPS
3. Stop Mac scheduler: `pkill -f "python.*scheduler.py"`
4. Verify Mac scheduler is stopped

**Estimated time:** 5 minutes

---

## Environment Variables Required

### On VPS (`~/MissionControl/trading/.env`)

```bash
# IB Gateway
IB_HOST=127.0.0.1
IB_PORT=4001
TRADING_MODE=live

# Telegram
TELEGRAM_BOT_TOKEN=your_actual_token
TELEGRAM_CHAT_ID=your_actual_chat_id

# Email (Resend)
RESEND_API_KEY=your_actual_key

# Dashboard API Security
DASHBOARD_API_KEY=<generate with: openssl rand -hex 32>
KILL_SWITCH_PIN=1234

# Optional: AWS S3 Backup
# AWS_ACCESS_KEY_ID=
# AWS_SECRET_ACCESS_KEY=
```

### On Vercel (Production Environment)

```
TRADING_API_URL=http://YOUR_VPS_IP:8000
TRADING_API_KEY=<same as DASHBOARD_API_KEY from VPS>
NEXTAUTH_SECRET=<existing>
NEXTAUTH_URL=https://www.winzinvest.com
ADMIN_EMAIL=<existing>
ADMIN_PASSWORD=<existing>
DATABASE_URL=<existing>
```

---

## Testing Checklist

After deployment, verify:

### VPS Tests:

```bash
# SSH access works
ssh ubuntu@YOUR_VPS_IP

# Services running
sudo systemctl status ib-gateway trading-scheduler trading-api

# IB Gateway connected
docker logs ib-gateway | grep "Ready"

# API health
curl http://localhost:8000/health

# API with auth
curl -H "x-api-key: YOUR_KEY" http://localhost:8000/api/dashboard | jq '.account'

# Scheduler logs
sudo journalctl -u trading-scheduler -n 50
```

### Dashboard Tests:

- [ ] https://www.winzinvest.com/dashboard loads
- [ ] Positions match IB
- [ ] Performance metrics current
- [ ] https://www.winzinvest.com/performance loads
- [ ] No console errors

### Alert Tests:

- [ ] Telegram message received: `python3 -c "from notification_utils import send_telegram_message; send_telegram_message('Test')"`
- [ ] UptimeRobot configured and monitoring

---

## Summary

**Code Status:** ✅ 100% Complete

**Manual Tasks Remaining:** 8 phases (see above)

**Estimated Total Time:** ~2.5 hours

**Next Step:** Start with [MIGRATION.md](./MIGRATION.md)

---

## Questions?

Refer to:
- **Migration:** [MIGRATION.md](./MIGRATION.md)
- **Security:** [SECURITY.md](./SECURITY.md)
- **Overview:** [README.md](./README.md)
- **Troubleshooting:** All 3 guides above
