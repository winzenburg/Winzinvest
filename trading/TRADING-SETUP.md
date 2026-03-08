# Trading Automation Setup Guide

**Date:** Feb 21, 2026  
**Status:** Ready for configuration

---

## Architecture

```
TradingView Alerts
       ↓ (Webhook POST)
   Webhook Listener (port 5001)
       ↓
   Telegram Notification
   
TradingView Screener (CSV export)
       ↓
   Watchlist Sync Script
       ↓
   ~/.openclaw/workspace/trading/watchlist.json
   
Interactive Brokers (API)
       ↓
   Portfolio Tracker (4 PM daily)
       ↓
   Email Summary
```

---

## Setup Steps

### 1️⃣ Start TradingView Webhook Listener

This daemon listens for alerts from TradingView and routes them to Telegram.

**Start manually:**
```bash
cd ~/.openclaw/workspace/trading
export TELEGRAM_BOT_TOKEN="<your_bot_token>"
export TELEGRAM_CHAT_ID="<your_chat_id>"
python3 webhook_listener.py
```

**Or as background process:**
```bash
nohup python3 webhook_listener.py > webhook_listener.log 2>&1 &
```

**Or as launchd service (macOS):**
Create `~/Library/LaunchAgents/com.pinchy.trading-webhook.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.pinchy.trading-webhook</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/pinchy/.openclaw/workspace/trading/webhook_listener.py</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>TELEGRAM_BOT_TOKEN</key>
        <string>YOUR_BOT_TOKEN</string>
        <key>TELEGRAM_CHAT_ID</key>
        <string>YOUR_CHAT_ID</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/trading-webhook.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/trading-webhook-error.log</string>
</dict>
</plist>
```

Then enable:
```bash
launchctl load ~/Library/LaunchAgents/com.pinchy.trading-webhook.plist
```

**Check if running:**
```bash
curl http://127.0.0.1:5001/healthz || echo "Webhook listener not running"
```

---

### 2️⃣ Configure TradingView Alerts

In TradingView, create a new alert on your chart:

**Alert Name:** "Swing Trading Webhook"

**Condition:** (Your existing entry signal script)

**Alert Actions:**
- Webhook URL: `http://127.0.0.1:5001/tradingview`
- Message:
```json
{
  "symbol": "{{ticker}}",
  "action": "{{strategy.order.action}}",
  "price": "{{close}}",
  "message": "Volume: {{volume}}, RSI: {{RSI}}"
}
```

**Test the alert:**
1. In TradingView, click "Create Alert" → test fire
2. Check Telegram for incoming message
3. If received, webhook is working ✅

---

### 3️⃣ Set Up Interactive Brokers API

**Prerequisites:**
- TWS or IBGateway running
- API enabled in account settings

**Enable API Access:**
1. Log in to TWS/IBGateway
2. Go to File → Global Configuration → API → Settings
3. Enable "Allow connections from localhost"
4. **Port:** 7497 (live) or 4002 (paper trading)
5. Click "OK" and restart TWS/IBGateway

**Test connection:**
```bash
python3 ~/.openclaw/workspace/trading/ib_portfolio_tracker.py
```

Expected output:
```
✅ Connected to IB at 127.0.0.1:7497
✅ Fetched 5 positions
✅ Portfolio saved to ~/.openclaw/workspace/trading/portfolio.json
```

**If connection fails:**
- Verify TWS/IBGateway is running
- Check port: `lsof -i :7497`
- Verify API is enabled in settings
- Check firewall isn't blocking localhost

---

### 4️⃣ Set Up Watchlist Sync

**Initialize watchlist:**
```bash
python3 ~/.openclaw/workspace/trading/watchlist_sync.py report
```

**Add stocks manually:**
```bash
python3 ~/.openclaw/workspace/trading/watchlist_sync.py add NVDA "Strong relative strength"
python3 ~/.openclaw/workspace/trading/watchlist_sync.py add MSFT "Tech rotation signal"
python3 ~/.openclaw/workspace/trading/watchlist_sync.py list
```

**Import from TradingView screener:**
1. In TradingView, export your screener results as CSV
2. Save to: `~/.openclaw/workspace/trading/screener_exports/latest.csv`
3. Run sync:
```bash
python3 ~/.openclaw/workspace/trading/watchlist_sync.py import ~/.openclaw/workspace/trading/screener_exports/latest.csv
python3 ~/.openclaw/workspace/trading/watchlist_sync.py list
```

**Result:** watchlist.json updated with new stocks

---

### 5️⃣ Schedule Cron Jobs

**Portfolio review at 4 PM (daily):**
```bash
openclaw cron add \
  --name "portfolio-review" \
  --cron "0 16 * * *" \
  --tz America/Denver \
  --message "Run: python3 ~/.openclaw/workspace/trading/ib_portfolio_tracker.py. Generate email summary of positions, P&L, and compare to market performance. Send email with key metrics and alerts if any position is down >10%." \
  --announce
```

**Watchlist auto-sync (hourly during trading hours):**
```bash
openclaw cron add \
  --name "watchlist-auto-sync" \
  --cron "0 8-17 * * 1-5" \
  --tz America/Denver \
  --message "Check for new screener exports in ~/.openclaw/workspace/trading/screener_exports/. If found, import latest CSV to watchlist. Report any new stocks added." \
  --announce
```

---

## Environment Variables

Store these in `~/.openclaw/openclaw.json` or as environment variables:

```bash
export TELEGRAM_BOT_TOKEN="123456:ABCdefGHIjklMNOpqrSTUVwxyz"
export TELEGRAM_CHAT_ID="987654321"
export IB_HOST="127.0.0.1"
export IB_PORT="7497"  # or 4002 for paper trading
export IB_ACCOUNT="U7479839"
export WEBHOOK_PORT="5001"
```

---

## Testing Checklist

- [ ] Webhook listener running: `curl http://127.0.0.1:5001/healthz`
- [ ] TradingView alert test fires → Telegram message received
- [ ] TWS/IBGateway running with API enabled
- [ ] Portfolio tracker runs: `python3 ib_portfolio_tracker.py`
- [ ] Watchlist JSON created at `~/.openclaw/workspace/trading/watchlist.json`
- [ ] Screener CSV imports without errors
- [ ] Cron jobs created and scheduled

---

## Troubleshooting

### Webhook listener not receiving TradingView alerts

**Possible causes:**
1. Webhook listener not running → `ps aux | grep webhook_listener`
2. Wrong URL in TradingView → Should be `http://127.0.0.1:5001/tradingview`
3. Firewall blocking port 5001 → `sudo lsof -i :5001`
4. Telegram credentials missing → Check environment variables

**Solution:**
```bash
# Start webhook with debug logging
python3 webhook_listener.py 2>&1 | tee /tmp/webhook-debug.log
```

### Portfolio tracker can't connect to IB

**Check:**
1. TWS/IBGateway running? → Look for window or `ps aux | grep TWS`
2. API enabled? → TWS → File → Global Configuration → API
3. Port correct? → 7497 (live) vs 4002 (paper)
4. Firewall? → `sudo lsof -i :7497`

**Solution:**
```bash
# Test IB connection
python3 ib_portfolio_tracker.py 2>&1 | head -20
```

### Watchlist imports but no stocks added

**Check CSV format:**
- Headers must include: `Symbol`, `Name`, `Close`, `Volume`, `RSI`
- TradingView exports should have these columns
- Test: `head -5 latest.csv`

**Solution:**
```bash
# Inspect CSV structure
cat ~/.openclaw/workspace/trading/screener_exports/latest.csv | head -3
```

---

## Usage Examples

**View current portfolio:**
```bash
cat ~/.openclaw/workspace/trading/portfolio.json | jq '.summary'
```

**View watchlist:**
```bash
python3 ~/.openclaw/workspace/trading/watchlist_sync.py list
```

**Remove a stock from watchlist:**
```bash
python3 ~/.openclaw/workspace/trading/watchlist_sync.py remove AAPL
```

**Check webhook logs:**
```bash
tail -f /tmp/trading-webhook.log
```

---

## Next Steps

1. ✅ Install dependencies: `pip install ib_insync requests`
2. ✅ Start webhook listener (background or launchd)
3. ✅ Enable IB API in TWS/IBGateway
4. ✅ Create TradingView alert with webhook URL
5. ✅ Test alert fire → verify Telegram message
6. ✅ Initialize watchlist
7. ✅ Create portfolio review cron job

**Estimated time:** 30 minutes

---

## Architecture Notes

- **Webhook listener** runs continuously on localhost:5001
- **Portfolio tracker** runs on-demand (cron job at 4 PM)
- **Watchlist sync** can run on-demand or scheduled
- All data persists in `~/.openclaw/workspace/trading/`
- JSON files provide simple, version-control-friendly storage

This is your **trading command center**. Everything flows through these scripts.
