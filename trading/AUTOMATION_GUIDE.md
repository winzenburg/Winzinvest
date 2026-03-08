# Full Automation Guide

## 🤖 How Automation Works

Your trading system is now set up for **full automation** during trading hours (7:45 AM - 1:45 PM MT).

---

## Architecture

```
Scheduled Scans (Cron)
    ↓
Screeners Find Setups
    ↓
Auto-post to Webhook Listener (localhost)
    ↓
Filters Validate:
  • Watchlist ✓
  • RS Ratio > 1.03 ✓
  • Volume > 1.3x ✓
  • Trading Hours ✓
  • Market Regime ✓
    ↓
Pending Order Created
    ↓
OpenClaw AI Approves (or you do manually)
    ↓
Order → IB Gateway → IBKR Paper Account
    ↓
Execution Logged
```

---

## Current Status

✅ **IB Gateway**: Running on port 4002  
✅ **Webhook Listener**: Running on port 5001  
✅ **Screeners**: Scheduled via cron (8:30 AM, 12:00 PM)  
✅ **Paper Account**: DU4661622 connected  
✅ **Test Order**: Successfully placed  
⏳ **Auto-Approval**: Manual (AUTO_APPROVE=false)  

---

## Automation Levels

### **Level 1: Semi-Automated (Current)**
- Screeners run automatically
- Orders require manual approval
- You approve via: `python3 trading/scripts/manage_orders.py approve <id>`

### **Level 2: Fully Automated**
- Screeners run automatically
- Orders auto-approve if they pass filters
- Enable: Set `AUTO_APPROVE=true` in `.env`

---

## Commands for OpenClaw AI

### List Pending Orders
```bash
cd ~/.openclaw/workspace
python3 trading/scripts/manage_orders.py list
```

### Approve a Specific Order
```bash
python3 trading/scripts/manage_orders.py approve <intent_id>
```

### Approve All Pending
```bash
python3 trading/scripts/manage_orders.py approve-all
```

### Reject an Order
```bash
python3 trading/scripts/manage_orders.py reject <intent_id>
```

### Manually Post a Signal
```bash
python3 trading/scripts/auto_trade_helper.py AAPL buy 175.50 swing_fast_9_13_50 170 182
```

---

## Scheduled Scans

Current cron jobs (already configured):

**8:30 AM MT** - Opening scan
- Runs: `scan_0830_helper.py`
- Looks for: Opening range breakouts, gap plays

**12:00 PM MT** - Midday scan
- Runs: `midday_scan.py`
- Looks for: VWAP touches, box breakouts, pullbacks

**Every 30 min (during trading hours)** - Market check
- Via OpenClaw heartbeat
- Monitors for new setups

---

## Filters (Automatic)

Every signal must pass ALL of these:

| Filter | Threshold | Purpose |
|--------|-----------|---------|
| **Watchlist** | Must be in watchlist.json | Only trade approved tickers |
| **RS Ratio** | > 1.03 vs SPY | Relative strength requirement |
| **Volume** | > 1.3x 20-day avg | Liquidity and momentum |
| **Trading Hours** | 7:45 AM - 1:45 PM MT | Avoid first/last 15 min |
| **Market Regime** | Bull/bear/choppy gates | Setup-specific filters |
| **Feature Flag** | Setup must be enabled | Control which strategies run |

---

## Setup Types (feature_flags.json)

Currently enabled:

| Setup | Max Daily | Confidence | Canary |
|-------|-----------|------------|--------|
| trend_following | 3 | 0.75 | ❌ |
| box_breakout | 2 | 0.80 | ✅ |
| dividend_growth | 1 | 0.70 | ✅ |
| swing_fast_9_13_50 | 3 | 0.80 | ✅ |

**Canary mode**: First order is 1 share for testing

---

## Risk Management (risk.json)

**Position Sizing:**
- Max position: $10,000
- Max portfolio: $50,000
- Max per sector: 30%

**Stop Loss:**
- Trend following: 2% below entry
- Box breakout: Below box support
- Swing fast: 1.5% below entry

**Take Profit:**
- Target: 2:1 or 3:1 reward:risk
- Trailing stop after +2%

---

## Enabling Full Auto-Approval

**⚠️ Important:** Only enable after you've tested and trust the filters!

1. Edit `.env`:
   ```bash
   AUTO_APPROVE=true
   ```

2. Restart webhook listener:
   ```bash
   cd ~/.openclaw/workspace/trading
   # Press Ctrl+C in the terminal running the listener
   ./start_listener.sh
   ```

3. Monitor logs:
   ```bash
   ls -lt trading/logs/
   ```

---

## Monitoring

### Check Pending Orders
```bash
ls -la trading/pending/
```

### View Execution Logs
```bash
ls -la trading/logs/
cat trading/logs/<latest>.json
```

### Check Webhook Status
```bash
curl http://127.0.0.1:5001/status
```

### IB Gateway Connection
```bash
python3 -c "from ib_insync import IB; ib=IB(); ib.connect('127.0.0.1', 4002, 101); print(ib.managedAccounts()); ib.disconnect()"
```

---

## Safety Features

1. **Canary Mode**: First order for each setup is 1 share
2. **Trading Hours**: Only executes 7:45 AM - 1:45 PM MT
3. **Paper Account**: All orders go to DU4661622 (paper)
4. **Watchlist**: Only trades approved tickers
5. **Max Daily Trades**: Limited per setup type
6. **Manual Override**: You can always reject pending orders

---

## Telegram Integration (Optional)

Want to get notifications and approve/reject from your phone?

1. Create Telegram bot via @BotFather
2. Get your chat ID
3. Add to `.env`:
   ```
   TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
   TELEGRAM_CHAT_ID=123456789
   ```
4. Restart webhook listener

You'll get messages like:
```
Pending BUY AAPL @ 175.50 (canary=true, qty=1)
[Approve] [Reject]
```

---

## What OpenClaw AI Does

During trading hours (7:45 AM - 1:45 PM MT), I will:

1. **Monitor heartbeat** every 30 minutes
2. **Check for pending orders** in `trading/pending/`
3. **Evaluate each order** against filters
4. **Auto-approve** if AUTO_APPROVE=true and filters pass
5. **Notify you** of executions
6. **Log everything** to `trading/logs/`

You can override me anytime by:
- Manually rejecting orders
- Disabling setups in `feature_flags.json`
- Setting `AUTO_APPROVE=false`

---

## Testing Before Going Live

### Test 1: Mock Alert (Outside Trading Hours)
```bash
curl -X POST http://127.0.0.1:5001/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "secret": "yPLn-BfFFWVe1vkrXE7qgkUgRjlqGRlsQGBYsIquC80",
    "ticker": "AAPL",
    "timeframe": "15",
    "signal": "buy",
    "price": 175.50,
    "setup_type": "swing_fast_9_13_50"
  }'
```

Expected: `{"status":"rejected","reason":"Outside trading window"}`

### Test 2: Manual Order Approval
```bash
# Create a test order (during trading hours)
python3 trading/scripts/auto_trade_helper.py AAPL buy 175.50 swing_fast_9_13_50 170 182

# List it
python3 trading/scripts/manage_orders.py list

# Approve it
python3 trading/scripts/manage_orders.py approve <intent_id>

# Check IB Gateway for execution
```

---

## Ready to Go Live?

When you're confident everything works:

1. Set `AUTO_APPROVE=true` in `.env`
2. Restart webhook listener
3. Let the screeners run during trading hours
4. Monitor `trading/logs/` for executions
5. Review daily summary after market close

**The system will:**
- Scan at 8:30 AM and 12:00 PM
- Post signals that pass filters
- Auto-approve and execute
- Log everything

**You'll get:**
- Notifications (if Telegram configured)
- Daily summaries from OpenClaw
- Execution logs in `trading/logs/`

---

🚀 **You're ready for full automation!**
