# VPS Migration Runbook

Complete guide for migrating your trading system from Mac to AWS Lightsail VPS.

---

## Pre-Migration Checklist

Before you begin:

- [ ] AWS account created
- [ ] Lightsail billing set up
- [ ] Mac scheduler running and stable
- [ ] All Vercel deployments working
- [ ] `.env` credentials available (Telegram, Resend, IB)
- [ ] VNC client installed on Mac: `brew install --cask vnc-viewer`

---

## Phase 1: Provision Lightsail (15 min)

### 1. Create instance

1. Go to https://lightsail.aws.amazon.com/
2. Click **Create instance**
3. Platform: **Linux/Unix**
4. Blueprint: **OS Only** → **Ubuntu 24.04 LTS**
5. Instance plan: **$12/month** (2 GB RAM, 1 vCPU, 60 GB SSD)
6. Instance name: `winzinvest-trading`
7. Click **Create instance**

### 2. Configure firewall

Networking tab → Firewall → Add rules:

| Application | Protocol | Port | Source |
|-------------|----------|------|--------|
| SSH | TCP | 22 | Your IP only |
| Custom | TCP | 8000 | `76.76.21.0/24` (Vercel) |
| Custom | TCP | 8000 | `76.76.19.0/24` (Vercel) |
| Custom | TCP | 5900 | Your IP only (VNC) |

### 3. Assign static IP

1. Networking tab → **Create static IP**
2. Attach to instance
3. **Note this IP** - you'll need it everywhere

---

## Phase 2: Set Up SSH Access (5 min)

### From your Mac:

```bash
# Download default SSH key from Lightsail console
# Or use your existing key

# Copy your public key to VPS
ssh-copy-id -i ~/.ssh/id_ed25519.pub ubuntu@YOUR_VPS_IP

# Test connection
ssh ubuntu@YOUR_VPS_IP
```

If successful, you'll see the Ubuntu welcome message.

---

## Phase 3: Deploy Code (10 min)

### Option A: Automated deployment script

From your Mac:

```bash
cd ~/Library/CloudStorage/GoogleDrive-ryanwinzenburg@gmail.com/My\ Drive/Projects/MIssion\ Control
./deployment/scripts/deploy-to-vps.sh YOUR_VPS_IP
```

This syncs everything and creates `.env` template.

### Option B: Manual deployment

```bash
# Sync trading directory
rsync -avz --delete \
  --exclude=".git" --exclude="__pycache__" --exclude="*.pyc" \
  ~/Library/CloudStorage/GoogleDrive-ryanwinzenburg@gmail.com/My\ Drive/Projects/MIssion\ Control/trading/ \
  ubuntu@YOUR_VPS_IP:~/MissionControl/trading/

# Sync deployment files
rsync -avz \
  ~/Library/CloudStorage/GoogleDrive-ryanwinzenburg@gmail.com/My\ Drive/Projects/MIssion\ Control/deployment/ \
  ubuntu@YOUR_VPS_IP:~/MissionControl/deployment/
```

---

## Phase 4: Configure Environment (10 min)

SSH to VPS:

```bash
ssh ubuntu@YOUR_VPS_IP
```

### Edit `.env`:

```bash
nano ~/MissionControl/trading/.env
```

Required values (copy from your Mac's `.env`):

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

# Dashboard API (generate new key)
DASHBOARD_API_KEY=$(openssl rand -hex 32)  # Run this separately to generate
KILL_SWITCH_PIN=1234  # Choose your 4-digit PIN
```

Save and exit (Ctrl+X, Y, Enter).

---

## Phase 5: Install Dependencies (15 min)

### Still on VPS:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
sudo apt install -y docker.io docker-compose
sudo usermod -aG docker ubuntu
newgrp docker

# Install Python 3.11
sudo apt install -y python3.11 python3.11-venv python3-pip git

# Create Python virtual environment
python3.11 -m venv ~/trading-env
source ~/trading-env/bin/activate

# Install Python dependencies
cd ~/MissionControl/trading
pip install -r requirements.txt
```

Verify installation:

```bash
python3 --version  # Should show 3.11.x
pip list | grep ib-insync  # Should show 0.9.86
docker --version  # Should show Docker version
```

---

## Phase 6: Deploy IB Gateway (30 min)

### 1. Configure Docker Compose:

```bash
cd ~/MissionControl/deployment
nano docker-compose.yml
```

Update environment variables with your IB credentials:
- `TWS_USERID`
- `TWS_PASSWORD`
- `VNC_SERVER_PASSWORD`

Save and exit.

### 2. Start IB Gateway:

```bash
cd ~/MissionControl/deployment
docker-compose up -d

# Watch logs
docker logs -f ib-gateway
```

Wait for: `Gateway is ready` (takes ~2 minutes).

### 3. Complete 2FA Setup:

From your Mac:

```bash
open vnc://YOUR_VPS_IP:5900
```

Password: Your `VNC_SERVER_PASSWORD`

In the VNC window:
1. You'll see IB Gateway login screen
2. Enter your 2FA code from your authenticator app
3. Click **Login**
4. Once authenticated, close VNC window

IB Gateway will remember your credentials and auto-reconnect on restarts.

### 4. Test IB connection:

Back on VPS:

```bash
cd ~/MissionControl/trading/scripts
python3 -c "
from ib_insync import IB
ib = IB()
ib.connect('127.0.0.1', 4001, clientId=999)
print('Connected:', ib.isConnected())
ib.disconnect()
"
```

Should print: `Connected: True`

---

## Phase 7: Install Services (10 min)

### Copy systemd service files:

```bash
sudo cp ~/MissionControl/deployment/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
```

### Enable services:

```bash
sudo systemctl enable ib-gateway
sudo systemctl enable trading-scheduler
sudo systemctl enable trading-api
```

### Start services:

```bash
# Start IB Gateway first
sudo systemctl start ib-gateway
sleep 60  # Wait for IB to be ready

# Start scheduler and API
sudo systemctl start trading-scheduler
sudo systemctl start trading-api
```

### Check status:

```bash
sudo systemctl status ib-gateway
sudo systemctl status trading-scheduler
sudo systemctl status trading-api
```

All should show `active (running)` in green.

---

## Phase 8: Verify VPS is Trading (15 min)

### 1. Check scheduler logs:

```bash
sudo journalctl -u trading-scheduler -f
```

You should see scheduled jobs executing. Press Ctrl+C when done watching.

### 2. Check API:

```bash
# Test health endpoint
curl http://localhost:8000/health

# Test dashboard snapshot (with auth)
curl -H "x-api-key: $(grep DASHBOARD_API_KEY ~/MissionControl/trading/.env | cut -d= -f2)" \
  http://localhost:8000/api/dashboard | jq '.account.net_liquidation'
```

Should return your current NLV.

### 3. Check positions:

```bash
curl -H "x-api-key: $(grep DASHBOARD_API_KEY ~/MissionControl/trading/.env | cut -d= -f2)" \
  http://localhost:8000/api/dashboard | jq '.positions.list | length'
```

Should match your current position count.

---

## Phase 9: Update Vercel (5 min)

### 1. Get API key from VPS:

```bash
ssh ubuntu@YOUR_VPS_IP 'grep DASHBOARD_API_KEY ~/MissionControl/trading/.env'
```

Copy the value after `=`.

### 2. Add to Vercel:

1. Go to https://vercel.com/dashboard
2. Select your project
3. Settings → Environment Variables
4. Add for **Production**:

| Key | Value |
|-----|-------|
| `TRADING_API_URL` | `http://YOUR_VPS_IP:8000` |
| `TRADING_API_KEY` | (paste value from step 1) |

5. Click **Save**
6. Go to Deployments tab
7. Click **Redeploy** on the latest deployment

Wait ~1 minute for deployment to complete.

### 3. Test live site:

Visit https://www.winzinvest.com/dashboard

- Should load live data from VPS
- Positions should match IB
- Performance metrics should be current

---

## Phase 10: Stop Mac Scheduler (5 min)

**ONLY DO THIS AFTER VERIFYING VPS IS WORKING!**

On your Mac:

```bash
# Find scheduler process
ps aux | grep scheduler.py

# Kill it
pkill -f "python.*scheduler.py"

# Verify it's stopped
ps aux | grep scheduler.py  # Should show nothing
```

Now only the VPS is running trades.

---

## Phase 11: Set Up Backups (5 min)

On VPS:

```bash
# Make backup script executable
chmod +x ~/backup-trading-data.sh

# Test it
~/backup-trading-data.sh

# Check backup was created
ls -lh ~/backups/

# Add to crontab for daily execution
crontab -e
```

Add this line (runs at 3 AM daily):

```
0 3 * * * ~/backup-trading-data.sh >> ~/backup.log 2>&1
```

Save and exit.

---

## Phase 12: Configure Monitoring (10 min)

### UptimeRobot:

1. Go to https://uptimerobot.com
2. Sign up (free)
3. Add Monitor → HTTP(s)
   - Friendly Name: `Winzinvest Trading API`
   - URL: `http://YOUR_VPS_IP:8000/health`
   - Monitoring Interval: 5 minutes
4. Add Alert Contact → Your email
5. Save

You'll get email alerts if the API goes down.

### Test Telegram alerts:

```bash
ssh ubuntu@YOUR_VPS_IP
cd ~/MissionControl/trading/scripts
python3 -c "
import os
os.chdir('..')
from scripts.notification_utils import send_telegram_message
send_telegram_message('VPS migration complete! 🚀')
"
```

You should receive a Telegram message.

---

## Post-Migration Checklist

Verify everything is working:

- [ ] VPS services running: `sudo systemctl status ib-gateway trading-scheduler trading-api`
- [ ] IB Gateway connected: `docker logs ib-gateway | grep "Ready"`
- [ ] Dashboard shows live data: https://www.winzinvest.com/dashboard
- [ ] Performance page loading: https://www.winzinvest.com/performance
- [ ] Telegram alerts working
- [ ] Mac scheduler stopped: `ps aux | grep scheduler` shows nothing
- [ ] UptimeRobot monitoring configured
- [ ] Daily backups cron job active: `crontab -l`

---

## Rollback Plan (If Issues Arise)

If VPS has problems:

### Quick rollback to Mac:

```bash
# On Mac
cd ~/Library/CloudStorage/GoogleDrive-ryanwinzenburg@gmail.com/My\ Drive/Projects/MIssion\ Control/trading/scripts
python3 scheduler.py &
```

### On Vercel:

Remove or comment out:
- `TRADING_API_URL`
- `TRADING_API_KEY`

Redeploy.

Dashboard will go back to reading local files (won't work on live site, but dev works).

---

## Common Issues and Solutions

### IB Gateway won't connect:

```bash
# Restart Docker container
docker-compose restart ib-gateway

# Check logs
docker logs ib-gateway

# If 2FA expired, reconnect via VNC:
open vnc://YOUR_VPS_IP:5900
```

### Scheduler not running trades:

```bash
# Check logs
sudo journalctl -u trading-scheduler -n 100

# Verify IB connection from scheduler
sudo journalctl -u trading-scheduler | grep "Connected to IB"

# Restart
sudo systemctl restart trading-scheduler
```

### Dashboard shows "unavailable":

```bash
# Check API status
curl http://localhost:8000/health

# Check API logs
sudo journalctl -u trading-api -n 50

# Verify snapshot file exists
ls -lh ~/MissionControl/trading/logs/dashboard_snapshot.json

# Restart API
sudo systemctl restart trading-api
```

### Vercel can't reach VPS:

```bash
# Verify firewall allows Vercel IPs
sudo ufw status numbered

# Test from external IP (use your phone or another network):
curl http://YOUR_VPS_IP:8000/health

# Check if API is listening on 0.0.0.0, not just localhost:
sudo ss -tlnp | grep 8000
```

---

## Timeline Summary

| Phase | Task | Duration |
|-------|------|----------|
| 1 | Provision Lightsail | 15 min |
| 2 | SSH setup | 5 min |
| 3 | Deploy code | 10 min |
| 4 | Configure .env | 10 min |
| 5 | Install dependencies | 15 min |
| 6 | IB Gateway + 2FA | 30 min |
| 7 | Install services | 10 min |
| 8 | Verify trading | 15 min |
| 9 | Update Vercel | 5 min |
| 10 | Stop Mac | 5 min |
| 11 | Backups | 5 min |
| 12 | Monitoring | 10 min |
| **Total** | **Complete migration** | **~2.5 hours** |

---

## Success!

Your trading system is now running 24/7 on a VPS, independent of your Mac.

Access:
- Dashboard: https://www.winzinvest.com/dashboard
- Public performance: https://www.winzinvest.com/performance
- VPS SSH: `ssh ubuntu@YOUR_VPS_IP`
- IB Gateway VNC: `open vnc://YOUR_VPS_IP:5900`

---

## Questions?

If you encounter any issues during migration:

1. Check logs: `sudo journalctl -u trading-scheduler -f`
2. Verify connectivity: `curl http://localhost:8000/health`
3. Review this guide again — most issues are covered above
