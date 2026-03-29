# Your Custom Deployment Commands

**VPS IP:** `44.238.166.195`  
**Your Home IP:** `75.70.252.171`

All commands below are customized with your actual IPs. Just copy and paste!

---

## Phase 1: ✅ Complete - Lightsail Firewall Setup

**In Lightsail console → `winzinvest-trading` → Networking → Firewall:**

Delete any rules with `0.0.0.0/0`, then add these 4 rules:

**Rule 1 - SSH (Your Mac Only):**
```
Application: SSH
Protocol: TCP
Port: 22
Source: 75.70.252.171/32
```

**Rule 2 - Dashboard API (Vercel Range 1):**
```
Application: Custom
Protocol: TCP
Port: 8000
Source: 76.76.21.0/24
```

**Rule 3 - Dashboard API (Vercel Range 2):**
```
Application: Custom
Protocol: TCP
Port: 8000
Source: 76.76.19.0/24
```

**Rule 4 - VNC for IB Gateway (Your Mac Only):**
```
Application: Custom
Protocol: TCP
Port: 5900
Source: 75.70.252.171/32
```

---

## Phase 2: SSH Key Setup (Run on your Mac)

### Download SSH Key from Lightsail

1. Lightsail console → **Account** → **SSH keys**
2. Click **Download** next to your default key
3. Save to `~/Downloads/`

### Configure SSH Key

```bash
# Move key to .ssh directory
mv ~/Downloads/LightsailDefaultKey-*.pem ~/.ssh/winzinvest-trading.pem

# Set secure permissions (required)
chmod 400 ~/.ssh/winzinvest-trading.pem

# Test connection
ssh -i ~/.ssh/winzinvest-trading.pem ubuntu@44.238.166.195
```

**Expected:** Ubuntu welcome message

Type `exit` after successful connection.

### Create SSH Alias (Optional)

```bash
echo "alias ssh-vps='ssh -i ~/.ssh/winzinvest-trading.pem ubuntu@44.238.166.195'" >> ~/.zshrc
source ~/.zshrc

# Now you can connect with just:
ssh-vps
```

---

## Phase 3: Deploy Code to VPS

```bash
cd ~/Library/CloudStorage/GoogleDrive-ryanwinzenburg@gmail.com/My\ Drive/Projects/MIssion\ Control

./deployment/scripts/deploy-to-vps.sh 44.238.166.195
```

**What this does:**
- Syncs all trading scripts to VPS
- Creates `.env` template
- Sets up directory structure

---

## Phase 4: Configure Environment on VPS

SSH to VPS:

```bash
ssh -i ~/.ssh/winzinvest-trading.pem ubuntu@44.238.166.195
```

Edit `.env`:

```bash
nano ~/MissionControl/trading/.env
```

**Copy from your Mac's `.env` but update these:**

```bash
# IB Gateway (use VPS localhost)
IB_HOST=127.0.0.1
IB_PORT=4001
TRADING_MODE=live

# Telegram (copy from Mac)
TELEGRAM_BOT_TOKEN=your_actual_token_from_mac
TELEGRAM_CHAT_ID=your_actual_chat_id_from_mac

# Email (copy from Mac)
RESEND_API_KEY=your_actual_key_from_mac

# Dashboard API Security (generate NEW)
DASHBOARD_API_KEY=GENERATE_THIS_NOW
KILL_SWITCH_PIN=1234
```

**Generate API key on VPS:**

```bash
openssl rand -hex 32
```

Copy the output and paste it as `DASHBOARD_API_KEY` value.

**Save and exit:** Ctrl+X, Y, Enter

---

## Phase 5: Install Dependencies on VPS

**Still on VPS:**

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
sudo apt install -y docker.io docker-compose
sudo usermod -aG docker ubuntu
newgrp docker

# Verify Docker
docker --version

# Install Python 3.11
sudo apt install -y python3.11 python3.11-venv python3-pip git

# Verify Python
python3.11 --version

# Create virtual environment
python3.11 -m venv ~/trading-env
source ~/trading-env/bin/activate

# Install Python packages
cd ~/MissionControl/trading
pip install -r requirements.txt
```

**This takes ~15 minutes.** Watch for errors.

---

## Phase 6: Deploy IB Gateway

### Update Docker Compose with Credentials

**On VPS:**

```bash
cd ~/MissionControl/deployment
nano docker-compose.yml
```

**Edit these lines** (around line 10-13):

```yaml
- TWS_USERID=your_ib_username
- TWS_PASSWORD=your_ib_password
- VNC_SERVER_PASSWORD=choose_a_vnc_password
```

**Save:** Ctrl+X, Y, Enter

### Start IB Gateway

```bash
cd ~/MissionControl/deployment
docker-compose up -d

# Watch logs (wait for "Gateway is ready")
docker logs -f ib-gateway
```

Press Ctrl+C when you see "Gateway is ready" (~2 minutes).

### Complete 2FA Setup (From Your Mac)

**On your Mac:**

```bash
open vnc://44.238.166.195:5900
```

**If you don't have VNC Viewer:**

```bash
brew install --cask vnc-viewer
open vnc://44.238.166.195:5900
```

**In VNC window:**
1. Password: Your `VNC_SERVER_PASSWORD`
2. You'll see IB Gateway login screen
3. Enter 2FA code from authenticator app
4. Click Login
5. Close VNC window after successful login

**Test IB connection on VPS:**

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

## Phase 7: Install Systemd Services

**On VPS:**

```bash
# Copy service files
sudo cp ~/MissionControl/deployment/systemd/*.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable services
sudo systemctl enable ib-gateway trading-scheduler trading-api

# Start IB Gateway first
sudo systemctl start ib-gateway
sleep 60

# Start scheduler and API
sudo systemctl start trading-scheduler trading-api

# Check status (all should show "active (running)")
sudo systemctl status ib-gateway
sudo systemctl status trading-scheduler
sudo systemctl status trading-api
```

---

## Phase 8: Verify VPS is Trading

**Test API locally on VPS:**

```bash
# Test health endpoint
curl http://localhost:8000/health

# Get API key from .env
grep DASHBOARD_API_KEY ~/MissionControl/trading/.env

# Test authenticated endpoint (use API key from above)
curl -H "x-api-key: YOUR_API_KEY_HERE" http://localhost:8000/api/dashboard | jq '.account.net_liquidation'
```

Should return your current NLV.

**Test from your Mac:**

```bash
# Test health (no auth)
curl http://44.238.166.195:8000/health

# Test authenticated endpoint
curl -H "x-api-key: YOUR_API_KEY" http://44.238.166.195:8000/api/dashboard | jq '.account'
```

---

## Phase 9: Update Vercel

**Vercel Dashboard → Settings → Environment Variables:**

Add for **Production** environment:

| Key | Value |
|-----|-------|
| `TRADING_API_URL` | `http://44.238.166.195:8000` |
| `TRADING_API_KEY` | `[Paste from VPS .env]` |

**Get API key from VPS:**

```bash
ssh -i ~/.ssh/winzinvest-trading.pem ubuntu@44.238.166.195 'grep DASHBOARD_API_KEY ~/MissionControl/trading/.env'
```

Copy the value and paste into Vercel.

**Redeploy Vercel:**
- Go to Deployments tab
- Click **Redeploy** on latest deployment

**Test:**
- Visit https://www.winzinvest.com/dashboard
- Should load live data from VPS

---

## Phase 10: Stop Mac Scheduler

**⚠️ ONLY DO THIS AFTER VERIFYING VPS IS WORKING!**

**On your Mac:**

```bash
# Stop scheduler
pkill -f "python.*scheduler.py"

# Verify it's stopped
ps aux | grep scheduler.py
```

Should show nothing (or just the grep command itself).

---

## Phase 11: Set Up Backups

**On VPS:**

```bash
# Make backup script executable
chmod +x ~/MissionControl/deployment/scripts/backup-trading-data.sh

# Test it
~/MissionControl/deployment/scripts/backup-trading-data.sh

# Check backup was created
ls -lh ~/backups/

# Add to crontab (runs daily at 3 AM)
crontab -e
```

Press `i` to insert, then add:

```
0 3 * * * ~/MissionControl/deployment/scripts/backup-trading-data.sh >> ~/backup.log 2>&1
```

Press Esc, type `:wq`, press Enter.

---

## 🧪 Quick Verification Commands

**From your Mac - test everything:**

```bash
# SSH
ssh -i ~/.ssh/winzinvest-trading.pem ubuntu@44.238.166.195

# API health
curl http://44.238.166.195:8000/health

# Dashboard
open https://www.winzinvest.com/dashboard

# VNC (if needed)
open vnc://44.238.166.195:5900
```

---

## ✅ Post-Deployment Checklist

- [ ] SSH connection works
- [ ] IB Gateway running: `docker logs ib-gateway | grep Ready`
- [ ] Scheduler running: `sudo systemctl status trading-scheduler`
- [ ] API running: `curl http://localhost:8000/health`
- [ ] Dashboard loads from VPS: https://www.winzinvest.com/dashboard
- [ ] Mac scheduler stopped
- [ ] Backup cron job active

---

## 🚀 Ready to Start?

**First command to run on your Mac:**

```bash
cd ~/Library/CloudStorage/GoogleDrive-ryanwinzenburg@gmail.com/My\ Drive/Projects/MIssion\ Control

./deployment/scripts/deploy-to-vps.sh 44.238.166.195
```

**This will sync your code to the VPS!**

**Want me to walk you through each phase, or are you good to follow this guide on your own?** 🎯