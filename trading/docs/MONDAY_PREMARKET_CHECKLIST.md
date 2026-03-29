# Monday Pre-Market Verification Checklist

**Run this every Monday before 07:25 MT (market open 07:30 MT).**

This checklist ensures all critical systems are running after a weekend or holiday.

---

## 1. IB Gateway Status

```bash
# Check if Gateway is running
ps aux | grep -i "java.*gateway" | grep -v grep

# If not running, start it
cd ~/ibc && ./gatewaystartmacos.sh -inline &

# Wait 45 seconds for initialization
sleep 45

# Test connection
cd trading/scripts && python3 -c "
from ib_insync import IB
ib = IB()
for port in [4001, 4002, 7496, 7497]:
    try:
        ib.connect('127.0.0.1', port, clientId=90, timeout=8)
        print(f'✓ Connected on port {port}')
        print(f'Account: {ib.managedAccounts()}')
        ib.disconnect()
        break
    except Exception as e:
        print(f'✗ Port {port} failed')
"
```

**Expected:** Connection on port 4001 (LIVE) or 4002 (PAPER).

---

## 2. Scheduler & Watchdog Processes

```bash
# Check if scheduler is running
ps aux | grep "scheduler.py" | grep -v grep

# Check if risk monitor (agents) is running
ps aux | grep "agents.*run_all" | grep -v grep

# If either is missing, start them
cd trading/scripts

# Start scheduler
nohup python3 scheduler.py >> ../logs/scheduler.log 2>&1 &
echo $! > ../config/.pids/scheduler.pid

# Start agents (risk_monitor + trade_outcome_resolver)
cd agents
nohup python3 run_all.py >> ../../logs/agents.log 2>&1 &
```

**Expected:** Both processes running with recent PIDs.

---

## 3. Pending Stop Orders (CRITICAL)

Run the position integrity check to ensure all positions have stop coverage:

```bash
cd trading/scripts
python3 position_integrity_check.py 2>&1 | tail -30
```

**Look for:**
- `❌ XX position integrity violation(s) found` — if > 0, proceed to next step
- List of symbols with `NO_STOP_ORDER (WARNING)` or `NO_STOP_ORDER (CRITICAL)`

**If violations exist:**
```bash
# Auto-trigger stop placement
python3 update_atr_stops.py

# Verify all stops were placed
python3 position_integrity_check.py 2>&1 | tail -10
```

**Expected:** `✅ All positions covered` or `16 PENDING STOP` warnings that will be placed at market open via `execute_pending_trades.py`.

---

## 4. Pending Actions from Weekend

```bash
cat trading/logs/pending_actions.json | jq '.actions[] | select(.status == "pending")'
```

**Expected:** 0-2 items (covered calls waiting for ex-div dates).

**If urgent pending actions exist** (BUY orders, stop placements, ITM rolls):
- Execute manually via appropriate script
- Mark `status: "done"` in `pending_actions.json`

---

## 5. Assignment Risk Review

```bash
cat trading/logs/assignment_alerts_today.json
```

**Check for:**
- Any option with level `ITM` or `DEEP_ITM`
- Date stamp should be today or Friday (resets daily)

**If ITM options exist:**
```bash
# Run options manager to attempt auto-roll
cd trading/scripts
python3 options_position_manager.py --dry-run

# If dry-run shows a roll opportunity, execute live
python3 options_position_manager.py
```

---

## 6. Regime Context Integrity

```bash
cat trading/logs/regime_context.json
```

**Expected:** `"regime"` value is one of:
- `STRONG_UPTREND`
- `CHOPPY`
- `MIXED`
- `STRONG_DOWNTREND`
- `UNFAVORABLE`

**If the value is `NEUTRAL`, `RISK_ON`, `TIGHTENING`, or `DEFENSIVE`:**
```bash
# This is a corruption — L2 macro band label in the L1 file
cd trading/scripts
python3 -c "
from regime_detector import detect_market_regime, persist_regime_to_context
r = detect_market_regime()
persist_regime_to_context(r)
print('Fixed:', r)
"
```

See rule `080-regime-context-integrity.mdc` for why this happens.

---

## 7. Disk Space Check

```bash
df -h . | tail -1 | awk '{print "Used: "$3" / "$2" ("$5")"}'
```

**Expected:** < 90% full.

**If > 90%:**
```bash
# Compress old logs
find trading/logs -name "*.log*" -mtime +7 -exec gzip {} \;

# Archive and remove logs older than 30 days
find trading/logs -name "*.log.*.gz" -mtime +30 -delete
```

---

## 8. Kill Switch Status

```bash
cat trading/kill_switch.json 2>/dev/null || echo "No kill switch file (OK)"
```

**Expected:** File doesn't exist, or `"active": false`.

**If `"active": true`:**
- Determine if the kill switch should be deactivated
- Use the dashboard Kill Switch button, or manually edit the file

---

## 9. Quick Database Health Check

```bash
cd trading
sqlite3 logs/trades.db "SELECT 
  COUNT(*) as total, 
  COUNT(CASE WHEN exit_price IS NULL THEN 1 END) as open 
FROM trades WHERE status = 'Filled';"
```

**Expected:** Open trades count should match IB position count (±2 for options/pairs).

**If significantly different:**
```bash
# Run orphan detector
cd trading/scripts
python3 -c "
from agents.trade_outcome_resolver import find_orphaned_positions
from ib_insync import IB
ib = IB()
ib.connect('127.0.0.1', 4001, clientId=90)
orphans = find_orphaned_positions(ib)
print(f'Orphaned positions: {orphans}')
ib.disconnect()
"
```

---

## 10. Verify First Scheduled Job Will Run

The first job (`job_premarket`) runs at **07:00 MT**. Verify it's scheduled:

```bash
tail -50 trading/logs/scheduler.log | grep "job_premarket\|Next run"
```

**Expected:** Log shows scheduler loaded successfully and next run time for `job_premarket`.

---

## Summary Quick Command

Run all checks in sequence:

```bash
cd "/Users/ryanwinzenburg/Library/CloudStorage/GoogleDrive-ryanwinzenburg@gmail.com/My Drive/Projects/MIssion Control"

echo "=== 1. IB Gateway ==="
ps aux | grep -i "java.*gateway" | grep -v grep | head -1 || echo "NOT RUNNING"

echo -e "\n=== 2. Scheduler & Agents ==="
ps aux | grep "scheduler.py\|run_all.py" | grep -v grep || echo "NOT RUNNING"

echo -e "\n=== 3. Stop Coverage ==="
cd trading/scripts && python3 position_integrity_check.py 2>&1 | tail -5

echo -e "\n=== 4. Pending Actions ==="
cat trading/logs/pending_actions.json | jq '.actions[] | select(.status == "pending") | .description'

echo -e "\n=== 5. Assignment Risk ==="
cat trading/logs/assignment_alerts_today.json | jq '.alerted'

echo -e "\n=== 6. Regime Context ==="
cat trading/logs/regime_context.json | jq '.regime'

echo -e "\n=== 7. Disk Space ==="
df -h . | tail -1 | awk '{print "Used: "$3" / "$2" ("$5")"}'

echo -e "\n=== 8. Kill Switch ==="
cat trading/kill_switch.json 2>/dev/null | jq '.active' || echo "Not active (OK)"

echo -e "\n=== 9. Database Health ==="
sqlite3 trading/logs/trades.db "SELECT COUNT(*) as total, COUNT(CASE WHEN exit_price IS NULL THEN 1 END) as open FROM trades WHERE status = 'Filled';"

echo -e "\n✅ Checklist complete"
```

---

## Critical Failures — Action Required

| Check | Status | Action |
|---|---|---|
| IB Gateway not running | 🔴 CRITICAL | Start Gateway immediately — trading cannot proceed |
| Scheduler not running | 🔴 CRITICAL | Start scheduler — no automated execution without it |
| > 5 positions without stops | 🔴 CRITICAL | Run `update_atr_stops.py` immediately |
| ITM options exist | 🟡 URGENT | Run `options_position_manager.py` or roll manually |
| Disk > 95% full | 🟡 URGENT | Compress/archive logs now |
| Kill switch active (unintended) | 🟡 URGENT | Investigate and clear if appropriate |
| Regime context corrupted | 🟡 MEDIUM | Run regime fix command from §6 |

---

## Post-Checklist

Once all checks pass, verify the dashboard loads correctly:

1. Open `https://winzinvest.com` (or your Cloudflare Pages URL)
2. Check for stale data alert (should not appear during market hours)
3. Verify System Errors count is 0 or low (<3)
4. Confirm positions list matches expectations

**Markets open at 07:30 MT.** All checks should complete by 07:25 MT at the latest.
