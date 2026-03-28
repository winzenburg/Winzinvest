# Trading System VPS Deployment

Complete deployment package for migrating your trading system from Mac to AWS Lightsail VPS.

---

## Quick Start

**Estimated time:** 2.5 hours

**Cost:** $12/month (AWS Lightsail)

Follow these steps in order:

1. **[MIGRATION.md](./MIGRATION.md)** - Step-by-step migration runbook
2. **[SECURITY.md](./SECURITY.md)** - Security hardening guide
3. This README - Overview and troubleshooting

---

## What This Deployment Includes

### Infrastructure

- **AWS Lightsail VPS** ($12/mo)
  - Ubuntu 24.04 LTS
  - 2 GB RAM, 1 vCPU, 60 GB SSD
  - Static IP included
  - 1 TB data transfer

### Services

1. **IB Gateway (Docker)**
   - Interactive Brokers API client
   - Runs 24/7 in container
   - Auto-restart on failure
   - VNC access for 2FA setup

2. **Trading Scheduler**
   - APScheduler daemon
   - Executes all trading scripts on schedule
   - Auto-restarts on crash

3. **Dashboard API (FastAPI)**
   - Serves data to Vercel frontend
   - API key authentication
   - CORS configured for winzinvest.com

4. **Backups**
   - Daily automated backups
   - 7-day local retention
   - Optional S3 sync

---

## Directory Structure

```
deployment/
├── README.md                    # This file
├── MIGRATION.md                 # Step-by-step migration guide
├── SECURITY.md                  # Security hardening guide
├── docker-compose.yml           # IB Gateway Docker config
├── systemd/
│   ├── ib-gateway.service       # IB Gateway systemd unit
│   ├── trading-scheduler.service # Scheduler systemd unit
│   └── trading-api.service      # Dashboard API systemd unit
└── scripts/
    ├── deploy-to-vps.sh         # Automated deployment script
    └── backup-trading-data.sh   # Daily backup script
```

---

## Prerequisites

### On your Mac:

- [ ] All trading scripts working locally
- [ ] Scheduler running successfully
- [ ] `.env` file with all credentials
- [ ] VNC client installed: `brew install --cask vnc-viewer`

### AWS:

- [ ] AWS account created
- [ ] Credit card on file
- [ ] IAM user with Lightsail permissions (optional, root works)

### IB Account:

- [ ] Live account or paper trading account
- [ ] TWS/Gateway API enabled
- [ ] 2FA authenticator app (Google Authenticator, Authy, etc.)

---

## Deployment Steps

### Phase 1: Code Preparation (YOU ARE HERE)

✅ **All code is ready:**

- [x] `dashboard_api.py` created with full API endpoints
- [x] `docker-compose.yml` configured for IB Gateway
- [x] Systemd service files created
- [x] Deployment scripts created
- [x] Backup script created
- [x] Vercel API routes updated to support remote backend
- [x] Security documentation complete
- [x] Migration runbook complete

### Phase 2: VPS Setup (Manual - Follow MIGRATION.md)

1. Provision AWS Lightsail instance
2. Configure firewall rules
3. Set up SSH keys
4. Deploy code with `deploy-to-vps.sh`
5. Configure `.env` on VPS

### Phase 3: Service Deployment (Manual - Follow MIGRATION.md)

1. Install Docker and Python
2. Deploy IB Gateway container
3. Complete 2FA setup via VNC
4. Install systemd services
5. Start all services

### Phase 4: Integration (Manual - Follow MIGRATION.md)

1. Verify VPS is trading
2. Update Vercel environment variables
3. Test live dashboard
4. Stop Mac scheduler

### Phase 5: Hardening (Manual - Follow SECURITY.md)

1. Configure UFW firewall
2. Install Fail2Ban
3. Set up API authentication
4. Configure backups
5. Set up monitoring

---

## Testing the Deployment

### On VPS:

```bash
# Test IB connection
docker logs ib-gateway | grep "Ready"

# Test API health
curl http://localhost:8000/health

# Test dashboard snapshot
curl -H "x-api-key: YOUR_KEY" http://localhost:8000/api/dashboard | jq '.account'

# Check scheduler logs
sudo journalctl -u trading-scheduler -n 50
```

### From your Mac:

```bash
# Test API from external IP
curl http://YOUR_VPS_IP:8000/health

# Test authenticated endpoint
curl -H "x-api-key: YOUR_KEY" http://YOUR_VPS_IP:8000/api/dashboard | jq
```

### On Vercel Dashboard:

- Visit https://www.winzinvest.com/dashboard
- Should load data from VPS
- Check browser console for errors

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      User's Browser                          │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTPS
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  Vercel (winzinvest.com)                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Next.js Dashboard (Vercel Edge Functions)           │  │
│  │  - app/api/dashboard/route.ts                        │  │
│  │  - app/api/public-performance/route.ts               │  │
│  │  - app/api/alerts/route.ts                           │  │
│  └─────────────────────┬────────────────────────────────┘  │
└────────────────────────┼───────────────────────────────────┘
                         │ HTTP (API calls)
                         │ API Key: x-api-key header
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               AWS Lightsail VPS (Ubuntu 24.04)               │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  FastAPI Dashboard API (port 8000)                 │    │
│  │  trading/scripts/agents/dashboard_api.py           │    │
│  │  - /health                                         │    │
│  │  - /api/dashboard                                  │    │
│  │  - /api/public-performance                         │    │
│  │  - /api/alerts                                     │    │
│  │  - /api/journal                                    │    │
│  │  - /api/screeners                                  │    │
│  └─────────────────────┬──────────────────────────────┘    │
│                         │ reads                              │
│                         ▼                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Trading Data (trading/logs/)                      │    │
│  │  - dashboard_snapshot.json                         │    │
│  │  - trades_journal.json                             │    │
│  │  - audit_trail.json                                │    │
│  │  - assignment_alerts_today.json                    │    │
│  │  - regime_context.json                             │    │
│  └─────────────────────▲──────────────────────────────┘    │
│                         │ writes                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │  APScheduler (trading/scripts/scheduler.py)        │    │
│  │  - Screeners (nx_screener, pairs, etc.)           │    │
│  │  - Executors (execute_longs, execute_dual_mode)    │    │
│  │  - Monitors (cash_monitor, risk_monitor)          │    │
│  │  - Agents (options_manager, assignment_monitor)    │    │
│  └─────────────────────┬──────────────────────────────┘    │
│                         │ TWS API (port 4001)                │
│                         ▼                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │  IB Gateway (Docker Container)                     │    │
│  │  - Port 4001: Live API                             │    │
│  │  - Port 4002: Paper API                            │    │
│  │  - Port 5900: VNC (2FA setup)                      │    │
│  └─────────────────────┬──────────────────────────────┘    │
│                         │ TCP/IP                             │
└─────────────────────────┼───────────────────────────────────┘
                          │
                          ▼
                  ┌───────────────┐
                  │  IBKR Servers │
                  └───────────────┘
```

---

## Monitoring

### Service Status:

```bash
# Check all services
sudo systemctl status ib-gateway trading-scheduler trading-api

# View logs
sudo journalctl -u trading-scheduler -f
sudo journalctl -u trading-api -f
docker logs -f ib-gateway
```

### External Monitoring:

- **UptimeRobot**: Free monitoring, email alerts
- **Telegram**: Built-in alerts from trading system
- **Vercel Dashboard**: Logs and metrics for frontend

---

## Backup and Recovery

### Automated Backups:

- **Schedule**: Daily at 3 AM MT
- **Retention**: 7 days local
- **Location**: `~/backups/trading-YYYYMMDD.tar.gz`
- **Optional**: S3 sync for off-site storage

### Manual Backup:

```bash
ssh ubuntu@YOUR_VPS_IP
~/backup-trading-data.sh
```

### Restore from Backup:

```bash
# Download backup
scp ubuntu@YOUR_VPS_IP:~/backups/trading-20260328.tar.gz .

# Extract
tar -xzf trading-20260328.tar.gz

# Copy to VPS
rsync -avz logs/ ubuntu@YOUR_VPS_IP:~/MissionControl/trading/logs/

# Restart services
ssh ubuntu@YOUR_VPS_IP 'sudo systemctl restart trading-scheduler trading-api'
```

---

## Cost Breakdown

| Service | Monthly Cost | Notes |
|---------|--------------|-------|
| AWS Lightsail 2GB | $12 | Includes 1TB transfer, static IP |
| Data transfer (over 1TB) | ~$0 | Unlikely to exceed |
| Vercel Pro (optional) | $20 | For serverless functions >10s |
| **Total** | **$12-32** | Minimum $12 without Vercel Pro |

**Annual cost:** $144 minimum

---

## Security Overview

See [SECURITY.md](./SECURITY.md) for full details.

### Implemented Security Measures:

1. ✅ SSH key authentication (password login disabled)
2. ✅ UFW firewall (restrictive inbound rules)
3. ✅ Fail2Ban (auto-ban SSH brute force)
4. ✅ API key authentication (dashboard API)
5. ✅ Port isolation (IB Gateway not exposed externally)
6. ✅ VNC access restricted to your IP only
7. ✅ Systemd service isolation (separate users)
8. ✅ Docker container isolation (IB Gateway)

---

## Troubleshooting

### Dashboard shows "Data unavailable":

1. Check API is running: `sudo systemctl status trading-api`
2. Test API locally: `curl http://localhost:8000/health`
3. Check logs: `sudo journalctl -u trading-api -n 50`
4. Verify snapshot exists: `ls -lh ~/MissionControl/trading/logs/dashboard_snapshot.json`
5. Restart API: `sudo systemctl restart trading-api`

### No trades executing:

1. Check scheduler: `sudo systemctl status trading-scheduler`
2. Check IB connection: `docker logs ib-gateway | grep "connected"`
3. Check logs: `sudo journalctl -u trading-scheduler -f`
4. Verify scheduler config: `cat ~/MissionControl/trading/scripts/scheduler.py`
5. Check kill switch: `cat ~/MissionControl/trading/kill_switch.json`

### IB Gateway disconnected:

1. Check container: `docker ps | grep ib-gateway`
2. View logs: `docker logs ib-gateway`
3. Restart: `docker-compose restart ib-gateway`
4. Reconnect via VNC if 2FA expired: `open vnc://YOUR_VPS_IP:5900`

### Vercel can't reach VPS:

1. Check firewall: `sudo ufw status`
2. Verify API is listening on 0.0.0.0: `sudo ss -tlnp | grep 8000`
3. Test from external IP: `curl http://YOUR_VPS_IP:8000/health`
4. Check Vercel logs for specific errors

---

## Maintenance

### Weekly:

- [ ] Review Telegram alerts
- [ ] Check UptimeRobot status
- [ ] Verify backups exist: `ls ~/backups/`

### Monthly:

- [ ] Review systemd logs: `sudo journalctl --since "30 days ago" | grep ERROR`
- [ ] Check disk usage: `df -h`
- [ ] Update system: `sudo apt update && sudo apt upgrade -y`

### Quarterly:

- [ ] Review security: `sudo last`, `sudo journalctl -u sshd --since "90 days ago"`
- [ ] Test backup restore procedure
- [ ] Verify all monitoring still active

---

## Support

If you encounter issues during deployment:

1. **Check logs first**: Most issues are visible in systemd/docker logs
2. **Review this documentation**: Common issues are covered
3. **Test components individually**: IB → Scheduler → API → Vercel

---

## Next Steps

**Ready to deploy?** Follow **[MIGRATION.md](./MIGRATION.md)** step by step.

---

## Files Summary

| File | Purpose | Used By |
|------|---------|---------|
| `README.md` | This overview | You (documentation) |
| `MIGRATION.md` | Step-by-step deployment | You (manual execution) |
| `SECURITY.md` | Security hardening guide | You (manual execution) |
| `docker-compose.yml` | IB Gateway Docker config | Docker on VPS |
| `systemd/ib-gateway.service` | IB Gateway service | Systemd on VPS |
| `systemd/trading-scheduler.service` | Scheduler service | Systemd on VPS |
| `systemd/trading-api.service` | API service | Systemd on VPS |
| `scripts/deploy-to-vps.sh` | Automated deployment | You (from Mac) |
| `scripts/backup-trading-data.sh` | Daily backup script | Cron on VPS |

---

Good luck with your deployment! 🚀
