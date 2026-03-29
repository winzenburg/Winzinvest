# Quick VPS Setup - Final Steps

## Your VPS Info

- **IP:** `44.238.166.195`
- **SSH Command:** `ssh -i ~/.ssh/winzinvest-trading.pem ubuntu@44.238.166.195`
- **API Key:** `f5d98738b2178bd1939021775cc7dd172e13b3d0ba68a067b2887df00d715edc`
- **VNC Password:** `vncfecbf468`

---

## Step 1: Add Your Credentials (5 min)

SSH into the VPS:

```bash
ssh -i ~/.ssh/winzinvest-trading.pem ubuntu@44.238.166.195
```

Edit the .env file:

```bash
nano ~/MissionControl/trading/.env
```

Fill in these fields (use arrow keys to navigate, type to replace):

```bash
# REQUIRED for IB Gateway
IB_USERNAME=your_ibkr_username
IB_PASSWORD=your_ibkr_password

# REQUIRED for Telegram alerts
TELEGRAM_BOT_TOKEN=7805841622:AAEqz...
TELEGRAM_CHAT_ID=your_chat_id

# REQUIRED for email
RESEND_API_KEY=re_...
```

**Save:** `Ctrl+O`, `Enter`, `Ctrl+X`

**Get Telegram Chat ID (if you don't have it):**

Method 1 - Use @userinfobot:
1. Open Telegram
2. Search for `@userinfobot`
3. Start chat - it shows your ID immediately

Method 2 - API call (after sending your bot a message):
```bash
# On your Mac:
curl "https://api.telegram.org/bot7805841622:AAEqz.../getUpdates" | grep -o '"id":[0-9-]*' | head -1
```

---

## Step 2: Start IB Gateway (5 min)

Still on the VPS, start the IB Gateway Docker container:

```bash
cd ~/MissionControl/deployment
sudo docker-compose up -d
sudo docker logs -f ib-gateway
```

**Wait for:** `"IB Gateway is ready"`

**Then on your Mac**, connect via VNC to complete 2FA:

```bash
open vnc://44.238.166.195:5901
```

Password: `vncfecbf468`

Complete the 2FA challenge in the VNC window. Once authenticated, IB Gateway will auto-reconnect on future restarts.

---

## Step 3: Verify API is Working

Test from your Mac:

```bash
# Health check (no auth)
curl http://44.238.166.195:8888/health

# Dashboard data (with auth)
curl -H "X-API-Key: f5d98738b2178bd1939021775cc7dd172e13b3d0ba68a067b2887df00d715edc" \
  http://44.238.166.195:8888/api/dashboard | jq '.account'
```

Expected: JSON response with account data.

---

## Step 4: Update Vercel Environment Variables

Go to `vercel.com` → Your project → Settings → Environment Variables:

**Add these:**

| Key | Value |
|-----|-------|
| `TRADING_API_URL` | `http://44.238.166.195:8888` |
| `TRADING_API_KEY` | `f5d98738b2178bd1939021775cc7dd172e13b3d0ba68a067b2887df00d715edc` |

**Redeploy** after adding variables.

---

## Step 5: Start VPS Scheduler (ONLY after stopping Mac scheduler)

**On your Mac:**

```bash
# Stop Mac scheduler
cd ~/Library/CloudStorage/GoogleDrive-ryanwinzenburg@gmail.com/My\ Drive/Projects/MIssion\ Control/trading/scripts
pkill -f "python.*scheduler.py"
```

**On VPS:**

```bash
sudo systemctl start trading-scheduler.service
sudo systemctl status trading-scheduler.service
```

---

## Troubleshooting

**Check API logs:**
```bash
sudo journalctl -u trading-api.service -f
```

**Check IB Gateway logs:**
```bash
sudo docker logs -f ib-gateway
```

**Check scheduler logs:**
```bash
sudo journalctl -u trading-scheduler.service -f
```

**Restart a service:**
```bash
sudo systemctl restart trading-api.service
sudo systemctl restart ib-gateway.service
sudo systemctl restart trading-scheduler.service
```

---

## Daily Operations

Everything is automated - the VPS will:
- ✅ Start IB Gateway on boot
- ✅ Start API server on boot
- ✅ Start scheduler on boot
- ✅ Backup logs daily at 1 AM
- ✅ Auto-restart services if they crash

You only need to monitor alerts via Telegram/email.
