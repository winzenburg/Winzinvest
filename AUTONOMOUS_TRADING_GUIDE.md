# Mission Control - Autonomous Trading Guide

## 🚀 Quick Start

### Step 1: Run Setup Script

```bash
cd "/Users/ryanwinzenburg/Library/CloudStorage/GoogleDrive-ryanwinzenburg@gmail.com/My Drive/Projects/MIssion Control/trading"

./setup_autonomous_trading.sh
```

This will:
- ✅ Create launchd service
- ✅ Load service automatically
- ✅ Set up logging
- ✅ Configure auto-restart

### Step 2: Verify Service is Running

```bash
# Check if service is loaded
launchctl list | grep missioncontrol

# Should show:
# PID    Status    Label
# 12345  0         com.missioncontrol.scheduler
```

### Step 3: Monitor Logs

```bash
# Watch live logs
tail -f trading/logs/scheduler.log

# Watch errors
tail -f trading/logs/scheduler.err
```

---

## 📋 Pre-Monday Checklist

### Critical Items (Must Complete)

- [ ] **TWS/IB Gateway Running**
  - Open Interactive Brokers TWS or Gateway
  - Login with your credentials
  - Keep it running during market hours

- [ ] **API Permissions Enabled**
  - In TWS: File → Global Configuration → API → Settings
  - Enable "Enable ActiveX and Socket Clients"
  - Socket port: 7496 (live) or 7497 (paper)
  - Trusted IPs: 127.0.0.1

- [ ] **Account Type Confirmed**
  - Paper trading for testing
  - Live account for real trading
  - Verify in TWS account selector

- [ ] **Risk Limits Reviewed**
  ```bash
  cat trading/risk.json
  ```
  - Daily loss limit: 3%
  - Max position: 5%
  - Max positions: 25 longs, 25 shorts
  - Leverage: 2x

- [ ] **Test Scripts Manually**
  ```bash
  cd trading/scripts
  
  # Test screener
  python3 nx_screener_production.py --mode all
  
  # Test executor (dry-run if available)
  python3 execute_mean_reversion.py
  ```

- [ ] **Service is Running**
  ```bash
  launchctl list | grep missioncontrol
  ```

- [ ] **Logs are Working**
  ```bash
  ls -lh trading/logs/scheduler.log
  tail -20 trading/logs/scheduler.log
  ```

### Optional (Recommended)

- [ ] **Set Phone Alarms**
  - 6:45 AM MT - Check TWS is running
  - 7:00 AM MT - Pre-market screeners run
  - 7:30 AM MT - Market open execution
  - 2:00 PM MT - End of day check

- [ ] **Backup Current Positions**
  ```bash
  cd trading/scripts
  python3 sync_current_shorts.py
  ```

- [ ] **Test TradingView Indicators**
  - Open TradingView
  - Add NX Complete System Indicator
  - Verify signals match

- [ ] **Review Dashboard**
  ```bash
  cd trading-dashboard-public
  npm run dev
  # Open http://localhost:3003
  ```

---

## 🕐 Trading Schedule (Mountain Time)

The scheduler runs automatically during market hours:

| Time | Task | Description |
|------|------|-------------|
| **07:00** | Pre-Market | Sync positions, run all screeners, export watchlist |
| **07:30** | Market Open | Execute longs, dual-mode, mean reversion |
| **08:00** | Mid-Morning | Options executor |
| **10:00** | Midday Scan | Re-run screeners for fresh signals |
| **10:15** | Midday Execute | Re-run executors on fresh signals |
| **12:00** | Afternoon | Options/pairs check |
| **14:00** | Pre-Close | Portfolio snapshot, daily report |
| **14:30** | Post-Close | Adaptive params, strategy analytics |
| **Every 60s** | Monitoring | Risk monitor loop |

---

## 🎛️ Service Management

### Check Status
```bash
# Is service running?
launchctl list | grep missioncontrol

# Get PID
launchctl list com.missioncontrol.scheduler
```

### View Logs
```bash
# Live output
tail -f trading/logs/scheduler.log

# Live errors
tail -f trading/logs/scheduler.err

# Last 50 lines
tail -50 trading/logs/scheduler.log

# Search logs
grep "ERROR" trading/logs/scheduler.log
grep "executed" trading/logs/scheduler.log
```

### Stop Service
```bash
launchctl unload ~/Library/LaunchAgents/com.missioncontrol.scheduler.plist
```

### Start Service
```bash
launchctl load ~/Library/LaunchAgents/com.missioncontrol.scheduler.plist
```

### Restart Service
```bash
launchctl unload ~/Library/LaunchAgents/com.missioncontrol.scheduler.plist
sleep 2
launchctl load ~/Library/LaunchAgents/com.missioncontrol.scheduler.plist
```

### Remove Service Completely
```bash
# Stop service
launchctl unload ~/Library/LaunchAgents/com.missioncontrol.scheduler.plist

# Delete service file
rm ~/Library/LaunchAgents/com.missioncontrol.scheduler.plist
```

---

## 🚨 Emergency Stop (Kill Switch)

### Quick Stop
```bash
# Stop the service immediately
launchctl unload ~/Library/LaunchAgents/com.missioncontrol.scheduler.plist
```

### Force Kill
```bash
# Find PID
ps aux | grep scheduler.py

# Kill process
kill -9 <PID>
```

### Close All Positions (Manual)
1. Open TWS
2. Go to Portfolio
3. Right-click each position → Close Position
4. Or use "Close All Positions" button

---

## 📊 Monitoring on Monday

### Morning Routine (6:45 AM MT)

1. **Start TWS/Gateway**
   ```bash
   # Make sure TWS is running
   # Login and select account
   ```

2. **Verify Service**
   ```bash
   launchctl list | grep missioncontrol
   ```

3. **Open Log Monitor**
   ```bash
   tail -f trading/logs/scheduler.log
   ```

4. **Watch for Pre-Market (7:00 AM)**
   - Should see "PRE-MARKET" in logs
   - Screeners should run
   - Watchlist should be exported

5. **Watch for Market Open (7:30 AM)**
   - Should see "MARKET OPEN EXECUTION"
   - Executors should run
   - Trades should be placed

### Throughout the Day

**Check every hour:**
- [ ] Service still running: `launchctl list | grep missioncontrol`
- [ ] No errors in logs: `tail -20 trading/logs/scheduler.err`
- [ ] Positions in TWS match expectations
- [ ] Dashboard shows correct data

**Watch for:**
- ✅ Successful screener runs
- ✅ Successful executor runs
- ✅ Trades placed in TWS
- ❌ Error messages in logs
- ❌ Service crashes
- ❌ TWS disconnections

### End of Day (2:00 PM MT)

1. **Check Final Report**
   ```bash
   tail -100 trading/logs/scheduler.log | grep "Pre-close"
   ```

2. **Review Positions**
   - Open TWS Portfolio
   - Verify all positions
   - Check P&L

3. **Check Dashboard**
   ```bash
   cd trading-dashboard-public
   npm run dev
   # Review performance
   ```

4. **Backup Data**
   ```bash
   cd trading/scripts
   python3 sync_current_shorts.py
   ```

---

## 🐛 Troubleshooting

### Service Won't Start

**Check logs:**
```bash
tail -50 trading/logs/scheduler.err
```

**Common issues:**
- Python not found → Check path in plist
- Script not found → Check paths in plist
- Permission denied → Check file permissions
- Import errors → Check PYTHONPATH

**Fix:**
```bash
# Verify Python
which python3

# Verify script exists
ls -l trading/scripts/scheduler.py

# Check permissions
chmod +x trading/scripts/scheduler.py

# Reload service
launchctl unload ~/Library/LaunchAgents/com.missioncontrol.scheduler.plist
launchctl load ~/Library/LaunchAgents/com.missioncontrol.scheduler.plist
```

### Service Keeps Crashing

**Check error log:**
```bash
tail -100 trading/logs/scheduler.err
```

**Common causes:**
- TWS not running
- API connection failed
- Import errors
- Missing dependencies

**Fix:**
1. Stop service
2. Test manually: `cd trading/scripts && python3 scheduler.py --dry-run`
3. Fix errors
4. Restart service

### No Trades Being Placed

**Check:**
1. TWS is running
2. API is enabled
3. Correct port (7496 live, 7497 paper)
4. Screeners are finding candidates
5. Risk gates are passing

**Debug:**
```bash
# Check screener output
cat trading/watchlist_multimode.json

# Check executor logs
grep "execute" trading/logs/scheduler.log

# Run executor manually
cd trading/scripts
python3 execute_mean_reversion.py
```

### Logs Not Updating

**Check service status:**
```bash
launchctl list | grep missioncontrol
```

**If PID is "-":**
- Service crashed
- Check error log
- Restart service

**If PID exists but no logs:**
- Check log file permissions
- Check disk space
- Restart service

---

## 📈 Performance Monitoring

### Daily Metrics to Track

1. **Number of Trades**
   ```bash
   grep "executed" trading/logs/scheduler.log | wc -l
   ```

2. **Screener Results**
   ```bash
   grep "candidates" trading/logs/scheduler.log
   ```

3. **Errors**
   ```bash
   grep "ERROR" trading/logs/scheduler.log
   ```

4. **P&L**
   - Check TWS Portfolio
   - Check Dashboard

### Weekly Review

Every Friday:
- Review total trades
- Calculate win rate
- Check max drawdown
- Verify risk limits
- Adjust parameters if needed

---

## 🎯 Success Criteria

### Week 1 Goals

- [ ] Service runs all week without crashes
- [ ] All scheduled tasks execute
- [ ] Trades placed successfully
- [ ] No risk limit violations
- [ ] Logs are clean (no critical errors)
- [ ] P&L is positive (or at least controlled losses)

### If Everything Works

After successful Week 1:
- ✅ Keep service running
- ✅ Continue monitoring daily
- ✅ Reduce monitoring frequency gradually
- ✅ Focus on performance optimization

### If Issues Arise

If problems in Week 1:
- ⚠️ Stop service
- ⚠️ Switch to manual execution
- ⚠️ Debug and fix issues
- ⚠️ Test thoroughly
- ⚠️ Restart service when ready

---

## 📞 Quick Reference

### Essential Commands

```bash
# Check status
launchctl list | grep missioncontrol

# View logs
tail -f trading/logs/scheduler.log

# Stop service
launchctl unload ~/Library/LaunchAgents/com.missioncontrol.scheduler.plist

# Start service
launchctl load ~/Library/LaunchAgents/com.missioncontrol.scheduler.plist

# Test manually
cd trading/scripts && python3 scheduler.py --dry-run
```

### Essential Files

- Service: `~/Library/LaunchAgents/com.missioncontrol.scheduler.plist`
- Scheduler: `trading/scripts/scheduler.py`
- Risk Config: `trading/risk.json`
- Output Log: `trading/logs/scheduler.log`
- Error Log: `trading/logs/scheduler.err`

### Support

- Technical Spec: `trading/docs/NX_SCREENER_TECHNICAL_SPEC.md`
- Strategy Guide: `trading-dashboard-public/app/strategy/page.tsx`
- TradingView Guide: `tradingview/README.md`

---

## ✅ You're Ready!

The autonomous trading system is now set up and ready for Monday. Remember:

1. **Test everything manually first**
2. **Monitor closely on Day 1**
3. **Have kill switch ready**
4. **Start small, scale up**
5. **Trust the system, but verify**

**Good luck! 📈🚀**

---

**Last Updated**: March 8, 2026  
**Version**: 1.0.0  
**Status**: Production Ready
