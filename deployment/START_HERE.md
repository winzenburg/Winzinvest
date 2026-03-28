# 🚀 VPS Deployment - START HERE

**Your trading system is ready to move to the cloud!**

---

## ✅ What's Already Done (100% Complete)

All code, configuration, and documentation has been created and tested:

### 1. **FastAPI Dashboard API** ✅
   - Created `trading/scripts/agents/dashboard_api.py`
   - 13 REST API endpoints serving all dashboard data
   - API key authentication built-in
   - Tested locally and working
   - **Location:** `trading/scripts/agents/dashboard_api.py`

### 2. **Vercel Frontend Updates** ✅
   - All API routes support remote backend
   - Dual-mode operation (local files OR remote API)
   - Automatic detection via `TRADING_API_URL` env var
   - **No Vercel code changes needed when you deploy!**

### 3. **Docker Configuration** ✅
   - IB Gateway Docker Compose file ready
   - Auto-restart, health checks included
   - VNC access for 2FA setup
   - **Location:** `deployment/docker-compose.yml`

### 4. **Systemd Services** ✅
   - 3 service files for auto-start on boot
   - IB Gateway, Scheduler, Dashboard API
   - **Location:** `deployment/systemd/*.service`

### 5. **Deployment Automation** ✅
   - One-command deployment script
   - Daily backup script (cron-ready)
   - **Location:** `deployment/scripts/`

### 6. **Complete Documentation** ✅
   - Step-by-step migration guide (~2.5 hours)
   - Security hardening guide
   - Troubleshooting and architecture diagrams
   - **Location:** `deployment/*.md`

### 7. **Committed to GitHub** ✅
   - All files committed and pushed
   - Commit: `70247ba`
   - Ready to clone on VPS

---

## 📋 What You Need to Do (Manual Steps)

Follow these guides in order:

### Step 1: Read the Overview (5 min)

**Read:** [`deployment/README.md`](./README.md)

This gives you the big picture of what you're deploying.

---

### Step 2: Follow the Migration Guide (2.5 hours)

**Follow:** [`deployment/MIGRATION.md`](./MIGRATION.md)

This is your step-by-step runbook with 12 phases:

1. ✅ **Provision AWS Lightsail** (15 min)
   - Create Ubuntu 24.04 instance
   - $12/month, 2GB RAM
   - Configure firewall
   - Get static IP

2. ✅ **Set up SSH** (5 min)
   - Copy SSH keys
   - Test connection

3. ✅ **Deploy code** (10 min)
   - Run `./deployment/scripts/deploy-to-vps.sh YOUR_VPS_IP`
   - Or manual rsync

4. ✅ **Configure environment** (10 min)
   - Edit `.env` on VPS
   - Copy your IB, Telegram, Resend credentials
   - Generate API key: `openssl rand -hex 32`

5. ✅ **Install dependencies** (15 min)
   - Docker, Python 3.11
   - Virtual environment
   - `pip install -r requirements.txt`

6. ✅ **Deploy IB Gateway** (30 min)
   - Start Docker container
   - Connect via VNC
   - Complete 2FA setup

7. ✅ **Install services** (10 min)
   - Copy systemd files
   - Enable and start services

8. ✅ **Verify VPS is trading** (15 min)
   - Check logs
   - Test API
   - Verify positions

9. ✅ **Update Vercel** (5 min)
   - Add `TRADING_API_URL` and `TRADING_API_KEY`
   - Redeploy

10. ✅ **Stop Mac scheduler** (5 min)
    - **ONLY after verifying VPS works!**
    - `pkill -f "python.*scheduler.py"`

11. ✅ **Set up backups** (5 min)
    - Add cron job
    - Test backup script

12. ✅ **Configure monitoring** (10 min)
    - UptimeRobot
    - Test Telegram alerts

---

### Step 3: Harden Security (20 min)

**Follow:** [`deployment/SECURITY.md`](./SECURITY.md)

Essential security measures:
- SSH key authentication (disable passwords)
- UFW firewall rules
- Fail2Ban for brute force protection
- API key authentication
- Port isolation

---

## 🎯 Quick Start (If You're in a Hurry)

**Fastest path to production:**

```bash
# 1. Provision Lightsail (manual, 15 min)
# Go to https://lightsail.aws.amazon.com/
# Create Ubuntu 24.04 instance, $12/mo
# Note your static IP

# 2. Deploy code (from your Mac)
cd ~/Library/CloudStorage/GoogleDrive-ryanwinzenburg@gmail.com/My\ Drive/Projects/MIssion\ Control
./deployment/scripts/deploy-to-vps.sh YOUR_VPS_IP

# 3. SSH to VPS and complete setup (follow MIGRATION.md phases 4-7)
ssh ubuntu@YOUR_VPS_IP
# Edit .env with your credentials
# Install Docker, Python, dependencies
# Start IB Gateway, complete 2FA via VNC
# Copy systemd files, enable and start services

# 4. Update Vercel environment variables
# TRADING_API_URL=http://YOUR_VPS_IP:8000
# TRADING_API_KEY=<from VPS .env>
# Redeploy Vercel

# 5. Verify and cutover
# Test: https://www.winzinvest.com/dashboard
# Stop Mac scheduler: pkill -f "python.*scheduler.py"

# Done! ✅
```

**Total time:** ~2.5 hours

---

## 📊 Architecture Overview

```
Mac (local)                    AWS Lightsail VPS                 Vercel
──────────                     ─────────────────                 ──────
                               ┌─────────────────┐
                               │  IB Gateway     │
                               │  (Docker)       │
                               │  Port 4001      │
                               └────────┬────────┘
                                        │
                               ┌────────▼────────┐
                               │  APScheduler    │
                               │  (trading jobs) │
                               └────────┬────────┘
                                        │ writes
                               ┌────────▼────────┐
                               │  logs/*.json    │
                               └────────┬────────┘
                                        │ reads
                               ┌────────▼────────┐
                               │  FastAPI        │
                               │  Port 8000      │
                               └────────┬────────┘
                                        │ HTTP
                               ┌────────▼────────┐
                               │  api/dashboard  │◄────── HTTPS
                               │  (Next.js)      │
                               └─────────────────┘
                                  winzinvest.com
```

**After deployment:**
- Your Mac runs nothing (scheduler stopped)
- VPS runs everything 24/7
- Vercel dashboard fetches data from VPS API
- You access dashboard at winzinvest.com

---

## 💰 Cost

| Service | Monthly | Annual |
|---------|---------|--------|
| AWS Lightsail 2GB | $12 | $144 |
| Vercel (current plan) | $0-20 | $0-240 |
| **Total** | **$12-32** | **$144-384** |

**Recommendation:** Start with Lightsail only ($12/mo). Upgrade Vercel to Pro only if you need longer serverless function timeouts.

---

## 🔒 Security Checklist

Before going live, ensure:

- [ ] SSH password authentication disabled
- [ ] UFW firewall enabled and configured
- [ ] Fail2Ban installed and running
- [ ] Dashboard API key set (VPS and Vercel)
- [ ] Port 4001 (IB Gateway) not exposed externally
- [ ] VNC port 5900 restricted to your IP only
- [ ] UptimeRobot monitoring configured
- [ ] Telegram alerts working
- [ ] Daily backups active

---

## 🆘 Help and Troubleshooting

### If Dashboard Shows "Data Unavailable":
1. Check API: `ssh ubuntu@VPS_IP 'sudo systemctl status trading-api'`
2. Test locally: `curl http://VPS_IP:8000/health`
3. Check logs: `sudo journalctl -u trading-api -n 50`
4. Restart: `sudo systemctl restart trading-api`

### If No Trades Executing:
1. Check scheduler: `sudo systemctl status trading-scheduler`
2. Check IB: `docker logs ib-gateway | grep connected`
3. Check logs: `sudo journalctl -u trading-scheduler -f`
4. Verify kill switch off: `cat ~/MissionControl/trading/kill_switch.json`

### If IB Gateway Disconnected:
1. Check container: `docker ps | grep ib-gateway`
2. Restart: `cd ~/MissionControl/deployment && docker-compose restart ib-gateway`
3. Reconnect 2FA if needed: `open vnc://VPS_IP:5900`

**More help:** See [MIGRATION.md](./MIGRATION.md) troubleshooting section

---

## 📝 Environment Variables Cheat Sheet

### On VPS (~/MissionControl/trading/.env):
```bash
IB_HOST=127.0.0.1
IB_PORT=4001
TRADING_MODE=live
TELEGRAM_BOT_TOKEN=<your_token>
TELEGRAM_CHAT_ID=<your_chat_id>
RESEND_API_KEY=<your_key>
DASHBOARD_API_KEY=$(openssl rand -hex 32)  # Generate this!
KILL_SWITCH_PIN=1234
```

### On Vercel (Production):
```
TRADING_API_URL=http://YOUR_VPS_IP:8000
TRADING_API_KEY=<same as DASHBOARD_API_KEY above>
```

---

## ✅ Post-Deployment Verification

After deployment, test:

```bash
# From your Mac:
curl http://YOUR_VPS_IP:8000/health
# Should return: {"status":"ok",...}

# Test authenticated endpoint:
curl -H "x-api-key: YOUR_KEY" http://YOUR_VPS_IP:8000/api/dashboard | jq '.account'
# Should return your account data

# Visit dashboard:
open https://www.winzinvest.com/dashboard
# Should load live data from VPS

# Check scheduler is working:
ssh ubuntu@YOUR_VPS_IP 'sudo journalctl -u trading-scheduler -n 20'
# Should show recent job executions
```

---

## 🎉 You're Ready!

**Next step:** Open [`MIGRATION.md`](./MIGRATION.md) and start Phase 1.

**Estimated time:** 2-3 hours for complete deployment

**Support:** All documentation is in this `deployment/` folder

---

## 📁 File Reference

| File | Purpose |
|------|---------|
| **START_HERE.md** | This file - your starting point |
| **README.md** | Deployment overview and architecture |
| **MIGRATION.md** | Step-by-step migration runbook (USE THIS) |
| **SECURITY.md** | Security hardening guide |
| **DEPLOYMENT_STATUS.md** | Current status and what's done |
| **docker-compose.yml** | IB Gateway Docker configuration |
| **systemd/*.service** | Auto-start service definitions |
| **scripts/deploy-to-vps.sh** | Automated deployment script |
| **scripts/backup-trading-data.sh** | Daily backup script |

---

Good luck! 🚀

**Questions?** Review the documentation - it covers 99% of issues.

**Ready?** Start with [MIGRATION.md](./MIGRATION.md) Phase 1.
