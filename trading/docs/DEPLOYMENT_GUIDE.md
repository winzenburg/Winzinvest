# OpenClaw Trading System - Fast Track Deployment Guide

Version: 1.0  
Date: February 8, 2026  
Estimated Setup Time: 2–3 hours

---

## Overview
This guide will take you from zero to paper trading with confirm-to-execute in a single session. Follow these steps in order, and you'll have a fully functional automated trading system running by the end.

What You'll Build:
- TradingView alerts → Webhook → Risk validation → Telegram confirmation → IBKR paper execution
- Complete logging and monitoring
- All 6 trading strategies ready to deploy
- Safe, tested, and ready to scale

---

## Prerequisites
### Required Accounts
- [x] TradingView Premium Account (for unlimited alerts)
- [x] Interactive Brokers Account (paper trading enabled)
- [x] Telegram Account (for notifications and confirmations)
- [x] Mac mini (or any computer that can run 24/7)

### Required Software
- [x] Python 3.8+
- [x] pip
- [x] IB Gateway or TWS (download from IBKR)
- [x] ngrok (for webhook tunnel) — optional but recommended

---

## Step 1: Prepare IBKR Paper Environment
### 1.1 Download and Install IB Gateway
1. https://www.interactivebrokers.com/en/trading/tws-updateable-latest.php  
2. Download IB Gateway (lighter than TWS)  
3. Install on Mac mini  
4. Launch IB Gateway

### 1.2 Configure API Access
1. Configure → Settings → API → Settings  
2. Enable “ActiveX and Socket Clients”  
3. Socket port: 7497 (paper)  
4. Trusted IPs: 127.0.0.1  
5. Master API client ID: (blank)  
6. Read-Only API: unchecked  
7. OK + restart IB Gateway

### 1.3 Log In to Paper Account
- Select Paper Trading → enter creds → Store Settings on Server → Login → keep running

Checkpoint: IB Gateway shows “Paper Trading”.

---

## Step 2: Install Python Dependencies
### 2.1 Create Project Directory
```bash
cd ~
mkdir -p openclaw-trading && cd openclaw-trading
mkdir -p config trades logs
```

### 2.2 Install Required Packages
```bash
pip3 install ib_insync yfinance pandas flask jsonschema python-dotenv requests
```

Verify:
```bash
python3 -c "import ib_insync; print('ib_insync:', ib_insync.__version__)"
python3 -c "import yfinance; print('yfinance installed')"
python3 -c "import flask; print('flask installed')"
```

---

## Step 3: Configure Secrets and Environment
### 3.1 Generate Webhook Secret
```bash
python3 -c "import secrets; print('MOLT_WEBHOOK_SECRET=' + secrets.token_urlsafe(32))"
```

### 3.2 Create Telegram Bot
- @BotFather → /newbot → copy bot token

### 3.3 Get Your Telegram Chat ID
- @userinfobot → /start → copy chat ID

### 3.4 Create .env
```bash
cd ~/openclaw-trading/config
cp .env.template .env
nano .env
```
Fill:
```
MOLT_WEBHOOK_SECRET=<from 3.1>
IB_HOST=127.0.0.1
IB_PORT=7497
IB_CLIENT_ID=101
TELEGRAM_BOT_TOKEN=<from 3.2>
TELEGRAM_CHAT_ID=<from 3.3>
SAFE_MODE=true
LOG_LEVEL=INFO
```

---

## Step 4: Copy Configuration Files
Place config files in ~/openclaw-trading/config:
- risk.json
- rules_enhanced.md
- watchlist.json
- alerts_schema.json
- feature_flags.json
- webhook_listener.py

Verify with:
```bash
ls -la ~/openclaw-trading/config/
```

---

## Step 5: Test IBKR Connection
Create and run test_ibkr.py (see full guide in chat). Expected: “Connected successfully!”

---

## Step 6: Start the Webhook Listener (Safe Mode)
```bash
cd ~/openclaw-trading
python3 config/webhook_listener.py
```
Test webhook via curl (see full guide). Check Telegram for confirmation prompt.

---

## Step 7: Set Up Webhook Tunnel (ngrok)
```bash
ngrok http 5001
```
Copy HTTPS URL for TradingView alerts.

---

## Step 8: Create TradingView Alerts
- Webhook URL: https://<ngrok>.ngrok.io/webhook
- Message JSON includes your secret; see full guide for template.

---

## Step 9: Enable Confirm-to-Execute (Paper)
- Set SAFE_MODE=false in .env and restart listener.  
- Approve trades via HTTP or Telegram buttons (optional advanced step).

---

## Step 10: Canary Mode Testing
- Enable per-strategy canary_mode in feature_flags.json  
- Run 5–10 1-share trades; verify stops/targets/logs.

---

## Step 11: Enable All Strategies Gradually
- Weeks 1–2: 3 core strategies  
- Weeks 3–4: add swing + pullback (canary)  
- Month 2: add momentum breakout (canary)

---

## Step 12: Monitoring and Maintenance
Daily: process checks, logs, webhook + tunnel status.  
Weekly/Monthly: performance reviews, caps, backups, upgrades.

---

## Step 13: Transition to Live Trading (Future)
Only after sustained paper success. Change IB_PORT=7496 and scale position sizes gradually.

---

## Troubleshooting
- Webhook: listener/tunnel/URL/secret/logs  
- IBKR: API enabled/port/trusted IPs  
- Telegram: token/chat id/interaction  
- Orders: SAFE_MODE, connection, ticker, caps

---

## Summary
You’ll have: alert intake → validation → Telegram confirm → IBKR paper exec → logging/monitoring.  
Strategies: 6; scalable T1→T3.  
Proceed to paper trading; iterate; only then consider live.
