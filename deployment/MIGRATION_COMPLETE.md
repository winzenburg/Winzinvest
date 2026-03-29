# Migration Complete — Trading System → AWS Lightsail VPS

**Date:** March 29, 2026  
**Status:** ✅ LIVE IN PRODUCTION

---

## What Was Migrated

Your entire Python trading system is now running on a dedicated AWS Lightsail VPS instead of your Mac.

### VPS Details

| Resource | Value |
|----------|-------|
| Provider | AWS Lightsail |
| Location | US West (Oregon) |
| Instance | General Purpose, Dual-stack, 2GB RAM, 1 vCPU, 60GB SSD ($12/month) |
| Static IP | `44.238.166.195` |
| OS | Ubuntu 24.04 LTS |
| Hostname | `ip-172-26-1-157` |

---

## Services Running on VPS

All three services are **active** and **enabled to start on boot**:

### 1. IB Gateway (Docker Container)

- **Image:** `gnzsnz/ib-gateway:10.45.1b`
- **Ports:** 4001 (live API), 4002 (paper API), 5900 (VNC)
- **Management:** `sudo docker-compose` in `~/MissionControl/deployment`
- **Service:** `sudo systemctl {start|stop|status} ib-gateway.service`
- **Logs:** `sudo docker logs -f ib-gateway`
- **Status:** ✅ Connected to IBKR live account `U7479839`, reading 60 positions
- **API Port Fix:** Port mapping corrected to `4001:4003` (socat forwards 4003→4001 internally)
- **Config Fix:** `TWS_ACCEPT_INCOMING=accept` and `READ_ONLY_API=no` enabled

### 2. Dashboard API (FastAPI)

- **Port:** 8888
- **Endpoints:** 13 total (`/health`, `/api/snapshot`, `/api/screeners`, `/api/trades`, etc.)
- **Auth:** API key authentication (`X-API-Key` header)
- **Service:** `sudo systemctl {start|stop|status} trading-api.service`
- **Logs:** `sudo journalctl -u trading-api.service -f`
- **Status:** ✅ Serving live data to Vercel frontend

### 3. Trading Scheduler (APScheduler)

- **Script:** `scheduler.py`
- **Jobs:** All production jobs loaded (screeners, executors, monitors, risk checks)
- **Service:** `sudo systemctl {start|stop|status} trading-scheduler.service`
- **Logs:** `sudo journalctl -u trading-scheduler.service -f`
- **Status:** ✅ Running, waiting for market open to execute scheduled jobs

---

## Critical Configuration Changes

### IB Gateway Docker Port Mapping Issue (RESOLVED)

**Problem:** Initial port mapping `4001:4001` didn't work because the Docker image uses `socat` to forward ports.

**Solution:** Corrected to `4001:4003` and `4002:4004` because:
- Gateway internally listens on `127.0.0.1:4001`
- `socat` forwards from container port `4003` → internal `4001`
- Host port `4001` → container port `4003` → internal Gateway `4001`

### API Access Configuration (RESOLVED)

**Problem:** Gateway API accepting TCP connections but timing out on API handshake.

**Solution:** Added environment variables:
```yaml
- TWS_ACCEPT_INCOMING=accept  # Accept incoming API connections
- READ_ONLY_API=no            # Enable order placement
```

Reference: [gnzsnz/ib-gateway-docker documentation](https://github.com/gnzsnz/ib-gateway-docker)

---

## Vercel Configuration

### Environment Variables Added

| Key | Value | Purpose |
|-----|-------|---------|
| `TRADING_API_URL` | `http://44.238.166.195:8888` | VPS Dashboard API endpoint |
| `TRADING_API_KEY` | `f5d98738b2178bd1939021775cc7dd172e13b3d0ba68a067b2887df00d715edc` | API authentication |

### Frontend Data Access (`lib/data-access.ts`)

All Next.js API routes now use dual-mode data access:
- **Remote mode** (production): Fetch from VPS via `TRADING_API_URL`
- **Local mode** (development): Read from filesystem

Example:
```typescript
if (isRemote) {
  const data = await remoteGet<T>('/api/snapshot');
  return NextResponse.json(data);
}
// Fallback to local filesystem...
```

---

## Security Hardening

All completed per `SECURITY.md`:

- ✅ SSH key-based authentication only (password auth disabled)
- ✅ UFW firewall configured with restrictive rules
- ✅ Fail2Ban installed for SSH brute-force protection
- ✅ API port 8888 only accessible from Vercel IPs
- ✅ VNC port 5900 only accessible from your home IP (`75.70.252.171/32`)
- ✅ Automated daily backups via cron to `~/backups/` (7-day retention)
- ✅ Non-root user (`ubuntu`) running all services
- ✅ Resource limits on all systemd services

---

## Daily Operations

### Monitoring Services

```bash
# Check all services
sudo systemctl status ib-gateway trading-api trading-scheduler

# View live logs
sudo journalctl -u trading-scheduler -f     # Scheduler
sudo journalctl -u trading-api -f           # Dashboard API
sudo docker logs -f ib-gateway              # IB Gateway
```

### Restarting Services

```bash
# Restart IB Gateway (requires 2FA via VNC)
cd ~/MissionControl/deployment
sudo docker-compose restart ib-gateway

# Restart Dashboard API
sudo systemctl restart trading-api

# Restart Scheduler
sudo systemctl restart trading-scheduler
```

### Syncing Code Updates

Run from your Mac:
```bash
cd ~/Library/CloudStorage/GoogleDrive-ryanwinzenburg@gmail.com/My\ Drive/Projects/MIssion\ Control
rsync -avz --progress -e "ssh -i ~/.ssh/winzinvest-trading.pem" \
  --exclude='*.pyc' --exclude='__pycache__' \
  trading/ ubuntu@44.238.166.195:~/MissionControl/trading/
```

Then restart affected services on VPS.

### VNC Access (for 2FA)

From your Mac:
```bash
open vnc://44.238.166.195:5900
# Password: [VNC_PASSWORD from .env]
```

---

## Testing & Validation

### IB Gateway API Connection

```bash
ssh -i ~/.ssh/winzinvest-trading.pem ubuntu@44.238.166.195
source ~/trading-env/bin/activate
python3 ~/test_ib.py
```

Expected output:
```
✅ IB Gateway API Connected!
Accounts: ['U7479839']
Open positions: 60
```

### Dashboard API Endpoints

```bash
# Health check (no auth)
curl http://44.238.166.195:8888/health

# Dashboard data (requires API key)
API_KEY="f5d98738b2178bd1939021775cc7dd172e13b3d0ba68a067b2887df00d715edc"
curl -H "X-API-Key: $API_KEY" http://44.238.166.195:8888/api/snapshot | jq '.account'
```

### Live Dashboard

Visit `winzinvest.com/overview` and verify:
- Portfolio data loads
- Real-time NLV and P&L displayed
- Positions list shows current holdings
- No "stale data" warnings

---

## Backup & Recovery

### Automated Backups

- **Schedule:** Daily at 2:00 AM UTC (8:00 PM MT)
- **Location:** `~/backups/trading-backup-YYYYMMDD.tar.gz`
- **Retention:** 7 days
- **Contents:** All logs, config, watchlists, state files

### Manual Backup

```bash
ssh -i ~/.ssh/winzinvest-trading.pem ubuntu@44.238.166.195
cd ~
./backup-trading-data.sh
```

### Restore from Backup

```bash
cd ~/MissionControl/trading
tar -xzf ~/backups/trading-backup-YYYYMMDD.tar.gz
```

---

## Known Issues & Workarounds

### IB Gateway Shows "API client: Disconnected"

**Normal behavior.** The Gateway only shows "connected" when a client is actively connected. Scripts connect → work → disconnect (not persistent connections).

**Test:** Run `python3 ~/test_ib.py` to verify the API is working.

### IB Gateway Requires 2FA After Restart

**By design.** IBKR requires 2FA authentication on every Gateway restart for security.

**Workaround:** Use VNC to complete 2FA: `open vnc://44.238.166.195:5900`

**Future:** Consider IB's "Stable Token" feature if available (reduces 2FA frequency).

### Docker Healthcheck Shows "unhealthy"

The healthcheck tries to connect to port `4003` internally, but this may not reflect actual API readiness.

**Ignore this metric.** Use the Python test script to verify real API connectivity.

---

## Cost Breakdown

| Resource | Monthly Cost |
|----------|--------------|
| AWS Lightsail (2GB instance) | $12.00 |
| Static IP | Free (while attached) |
| Data transfer | Free (first 3TB) |
| **Total** | **$12.00/month** |

---

## Success Metrics

✅ IB Gateway API: Live, authenticated, reading 60 positions  
✅ Dashboard API: Running on port 8888, serving 13 endpoints  
✅ Trading Scheduler: Active, all jobs loaded  
✅ Mac scheduler: Stopped (no duplicate trading operations)  
✅ Vercel frontend: Configured to fetch from VPS  
✅ Security: Hardened per SECURITY.md  
✅ Backups: Automated daily  
✅ Monitoring: Systemd + journald logs  

---

## Next Steps (Optional Enhancements)

1. **CloudWatch Monitoring:** Forward logs to AWS CloudWatch for centralized monitoring
2. **Telegram Alerts:** Test that Telegram notifications work from VPS
3. **Performance Tuning:** Monitor scheduler execution times and optimize if needed
4. **IB Stable Token:** Reduce 2FA frequency if your account supports it
5. **S3 Backup Sync:** Enable optional S3 backup sync in `backup-trading-data.sh`

---

## Support & Troubleshooting

See `MIGRATION.md` for the full migration runbook.  
See `SECURITY.md` for security hardening details.  
See `START_HERE.md` for the quick setup guide.

**Questions?** Check the logs:
```bash
sudo journalctl -u trading-scheduler -f
sudo journalctl -u trading-api -f  
sudo docker logs -f ib-gateway
```
