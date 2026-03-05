# Production Deployment Guide

## Complete Trading System - Ready for Live Execution

**Status:** ✅ All components built and tested

### Components

1. **Daily IBKR Snapshot** (`daily_snapshot.py`)
   - Fetches historical data for all 5,342 symbols
   - Batches requests to avoid API limits
   - Caches locally

2. **AMS Screener** (`screener_from_snapshot.py`)
   - Scores all symbols by momentum, RSI, RVOL
   - Returns Tier 2 (top quality) + Tier 3 candidates
   - Fast local processing (no API calls)

3. **Auto-Executor** (`execute_candidates.py`)
   - Reads screener candidates
   - Places market orders to IBKR
   - Enforces stop loss (-50%) + take profit (+100%)
   - Tracks daily loss

4. **Cron Scheduler** (launchd)
   - Runs every 15 minutes during market hours
   - 9:30 AM - 11:30 AM ET: Aggressive scanning
   - 11:30 AM - 2:00 PM ET: Paused (midday)
   - 2:00 PM - 4:00 PM ET: Aggressive scanning
   - After 4:00 PM: Paused (after hours)

---

## Installation (One-Time Setup)

### Step 1: Create Daily Snapshot Cache Directory

```bash
mkdir -p ~/.openclaw/workspace/trading/screener_cache
```

### Step 2: Load launchd Job

```bash
# Copy plist to LaunchAgents
cp ~/.openclaw/workspace/trading/scripts/com.pinchy.screener.plist \
   ~/Library/LaunchAgents/

# Load the job
launchctl load ~/Library/LaunchAgents/com.pinchy.screener.plist

# Verify it's loaded
launchctl list | grep com.pinchy.screener
```

### Step 3: Verify Logs

Monitor execution in real-time:

```bash
tail -f ~/.openclaw/workspace/trading/logs/screener_cron.log
```

---

## Manual Testing (Before Going Live)

### Step 1: Fetch Daily Snapshot

```bash
python3 ~/.openclaw/workspace/trading/scripts/daily_snapshot.py
```

Expected output: Fetches data for all 5,342 symbols, saves to `screener_cache/daily_snapshot.json`

### Step 2: Run Screener

```bash
python3 ~/.openclaw/workspace/trading/scripts/screener_from_snapshot.py
```

Expected output: Scores all symbols, returns Tier 2 + Tier 3 candidates in `trading/screener_candidates.json`

### Step 3: Execute Candidates (Paper Trading)

```bash
python3 ~/.openclaw/workspace/trading/scripts/execute_candidates.py
```

Expected output: Places orders in paper trading account DU4661622

---

## Switching to Live Trading

**Prerequisites:**
- 20+ successful paper trades
- Daily loss limit working correctly
- All executions logged properly

**To enable live trading:**

1. Edit `execute_candidates.py`:
   ```python
   EXEC_PARAMS = {
       'paper_trading': False,  # Change to False
       ...
   }
   ```

2. Restart launchd job:
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.pinchy.screener.plist
   launchctl load ~/Library/LaunchAgents/com.pinchy.screener.plist
   ```

---

## Monitoring & Troubleshooting

### View Current Executions

```bash
tail -100 ~/.openclaw/workspace/trading/logs/executions.json
```

### Check Daily Loss Tracking

```bash
cat ~/.openclaw/workspace/trading/logs/daily_loss.json
```

### View Screener Results

```bash
cat ~/.openclaw/workspace/trading/screener_candidates.json | jq '.tier_2[:5]'
```

### Stop Screener

```bash
launchctl unload ~/Library/LaunchAgents/com.pinchy.screener.plist
```

### Start Screener

```bash
launchctl load ~/Library/LaunchAgents/com.pinchy.screener.plist
```

---

## What Happens Each Day

### 9:00 AM ET (Before Market Open)
- Daily snapshot fetches all 5,342 symbols from IBKR
- Caches data locally

### 9:30 AM ET (Market Open)
- Cron job starts (every 15 minutes)
- AMS screener scores all symbols
- Top candidates identified

### 9:30 AM - 11:30 AM ET (Aggressive Window)
- Screener runs every 15 minutes
- Candidates executed immediately
- Position size: 1 share (paper) or configured amount (live)

### 11:30 AM - 2:00 PM ET (Midday Pause)
- No screening or execution
- Allows time for trades to develop

### 2:00 PM - 4:00 PM ET (Afternoon Window)
- Resume aggressive screening
- Execute candidates

### After 4:00 PM ET (After Hours)
- Pause screener
- Resume pre-market next day

---

## Account Settings

**Paper Trading Account:** DU4661622
- Executes immediately
- Zero risk
- Use for testing (first 20+ trades)

**Position Sizing:**
- Paper: 1 share per trade
- Live: Start with 1 share, scale to 2-3 after 20 successful trades

**Risk Management:**
- Stop Loss: -50% of entry
- Take Profit: +100% of entry (2:1 R:R)
- Daily Loss Limit: -3% of account equity (auto-halt)

---

## Support

For issues:

1. Check logs: `tail -f ~/.openclaw/workspace/trading/logs/screener_cron.log`
2. Verify IBKR connection: Open TWS/Gateway, ensure port 4002 is accessible
3. Test components manually (steps above)

---

**System Status:** ✅ READY FOR PRODUCTION
**Last Updated:** March 5, 2026
**Deployed By:** Mr. Pinchy
