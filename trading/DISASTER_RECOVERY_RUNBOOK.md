# Disaster Recovery Runbook

**Version:** 1.0  
**Last Updated:** 2026-02-26  
**Created by:** Trade Reconciliation System

## Overview

This runbook provides step-by-step procedures to recover from system failures, data loss, or crashes in the trading system.

## Table of Contents

1. [Machine Crash Recovery](#machine-crash-recovery)
2. [IB Gateway Crash Recovery](#ib-gateway-crash-recovery)
3. [Portfolio Data Corruption](#portfolio-data-corruption)
4. [Position Mismatch Investigation](#position-mismatch-investigation)
5. [Git/GitHub Issues](#gitgithub-issues)
6. [Cloud Backup Issues](#cloud-backup-issues)

---

## Machine Crash Recovery

### Scenario
The trading machine has crashed and is being restarted. You need to restore trading state and ensure positions match IB.

### Recovery Steps

#### Step 1: Verify Machine is Up (1-2 minutes)
```bash
# SSH into machine or access directly
ping localhost
# Verify time sync
date
# Check trading system files exist
ls -la ~/.openclaw/workspace/trading/portfolio.json
```

**Outcome:** Machine is running, time is synced, trading files exist.

---

#### Step 2: Start IB Gateway (2-3 minutes)
```bash
# Verify IB Gateway is running
ps aux | grep IB
# If not running, start it:
# - Launch IB Trader Workstation (TWS) or IB Gateway
# - Ensure account is logged in
# - Test connection: telnet localhost 4002
```

**Outcome:** IB Gateway is running and accessible on port 4002.

---

#### Step 3: Run Automated Disaster Recovery (5-10 minutes)
```bash
cd ~/.openclaw/workspace/trading

# Option A: Automated recovery
python3 disaster_recovery.py

# Output will show:
# Step 1: Restore from backup ✅/❌
# Step 2: Query IB Gateway ✅/❌
# Step 3: Reconcile positions ✅/❌
# Final status: RECOVERY_SUCCESS or RECOVERY_PARTIAL
```

**Outcome:** System has been restored to known state and reconciled with IB.

---

#### Step 4: Review Recovery Report
```bash
# Check the recovery log
tail -20 trading/logs/disaster_recovery.jsonl

# Check for any discrepancies
tail -20 trading/logs/verification_mismatches.jsonl
```

**If status is RECOVERY_SUCCESS:**
- ✅ System is ready to resume trading
- Proceed to step 5

**If status is RECOVERY_PARTIAL:**
- ⚠️ Manual investigation required
- See [Position Mismatch Investigation](#position-mismatch-investigation)

---

#### Step 5: Verify Critical Services (5 minutes)
```bash
# Verify portfolio.json is valid
python3 -c "import json; data = json.load(open('portfolio.json')); print(f'Loaded {len(data.get(\"positions\", []))} positions')"

# Verify git is healthy
git status
git log --oneline | head -5

# Run webhook listener test
python3 -c "from webhook_integration import add_entry_checks; print('Webhook integration OK')"
```

**Outcome:** All critical services verified.

---

#### Step 6: Resume Trading
```bash
# Start the trading daemons/services
# (Command depends on your setup - consult DEPLOYMENT_STATUS.txt)

# Monitor the logs
tail -f trading/logs/executor_watchdog.log
```

**Outcome:** System is operational and monitoring resumed.

---

## IB Gateway Crash Recovery

### Scenario
IB Gateway has crashed or lost connection. Positions remain open but you can't execute.

### Recovery Steps

#### Quick Recovery (5 minutes)
```bash
# 1. Restart IB Gateway
# - Kill the process: killall TWS or restart IB Gateway app
# - Restart: Launch TWS or IB Gateway again
# - Wait for account to load and login

# 2. Wait for reconnection (30-60 seconds)

# 3. Verify connection
telnet localhost 4002
# Should see connection or quick close (normal for test)

# 4. Run reconciliation to verify positions
cd ~/.openclaw/workspace/trading
python3 daily_reconciliation.py
```

**Outcome:** IB Gateway is back online, positions verified.

---

#### If Positions Don't Match
```bash
# Run full disaster recovery
python3 disaster_recovery.py

# Review discrepancies
tail -50 trading/logs/disaster_recovery.jsonl
```

**Actions:**
- If discrepancies found, investigate manually
- Contact IB support if positions are missing
- Update portfolio.json if data was corrupted

---

## Portfolio Data Corruption

### Scenario
portfolio.json has been corrupted, deleted, or shows wrong positions.

### Recovery Steps

#### Step 1: Identify Backup to Restore
```bash
# List available backups
python3 -c "from cloud_backup import CloudBackup; import json; backups = CloudBackup.list_backups(); [print(f\"{b.get('timestamp')} - {b.get('status')}\") for b in backups[-10:]]"

# Find the most recent good backup
ls -lt trading/logs/disaster_recovery_backups/ | head -10
```

**Outcome:** You've identified a known-good backup point.

---

#### Step 2: Backup Current Corrupted State
```bash
# Save the corrupted file for investigation
cp trading/portfolio.json trading/portfolio.json.corrupted.$(date +%s)
```

**Outcome:** Corrupted state preserved for forensics.

---

#### Step 3: Restore from Backup
```bash
# Method 1: Use automated restoration
cd trading
python3 disaster_recovery.py

# This will:
# 1. Restore portfolio.json from latest backup
# 2. Query IB Gateway for current positions
# 3. Compare and reconcile

# Method 2: Manual restore
# Extract from backup archive manually
tar -tzf /path/to/backup.tar.gz
tar -xzf /path/to/backup.tar.gz -C . portfolio.json
```

**Outcome:** portfolio.json restored from backup.

---

#### Step 4: Reconcile with IB
```bash
# Run reconciliation
python3 daily_reconciliation.py

# Check for mismatches
tail -50 trading/logs/reconciliation.jsonl
```

**Outcome:** Positions verified against IB Gateway.

---

## Position Mismatch Investigation

### Scenario
Daily reconciliation or post-trade verification shows positions don't match IB.

Example: "Placed 100 AAPL but only 95 found in IB"

### Investigation Steps

#### Step 1: Get Current State
```bash
# What does portfolio.json say?
python3 -c "import json; data = json.load(open('portfolio.json')); aapl = [p for p in data['positions'] if p['symbol'] == 'AAPL']; print(json.dumps(aapl, indent=2))"

# What does IB say?
python3 -c "from post_execution_verification import PostExecutionVerifier; v = PostExecutionVerifier(); v.connect(); ib = v.fetch_ib_positions(); print(f'IB AAPL: {ib.get(\"AAPL\", 0)} shares'); v.disconnect()"
```

**Outcome:** You've identified the exact discrepancy.

---

#### Step 2: Check Recent Trades
```bash
# What trades happened recently?
git log --grep=TRADE --oneline | head -10

# Get the full details
git show <commit-hash>

# Check audit log
tail -50 trading/logs/audit.jsonl | grep AAPL
```

**Outcome:** You understand what trades were executed.

---

#### Step 3: Check Stop Orders
```bash
# Are there pending stops?
cat trading/logs/pending_stops.json | python3 -m json.tool

# Check stop execution log
tail -20 trading/logs/stops_executed.json

# Did a stop execute? Check trade history
python3 -c "from git_auto_commit import GitAutoCommitter; c = GitAutoCommitter(); history = c.get_trade_history(limit=50); [print(h) for h in history if 'AAPL' in h.get('message', '')]"
```

**Outcome:** You've identified whether stops were involved.

---

#### Step 4: Determine Root Cause

**Possible causes:**

| Cause | Indicator | Solution |
|-------|-----------|----------|
| Partial fill | Position qty partially matches | Check all recent fills, verify with IB |
| Stop executed | Stop order in pending_stops | Add back to portfolio if incorrectly removed |
| Order pending | Order status is submitted | Wait for fill or cancel and re-enter |
| IB data lag | Data is 1-2 hours old | Wait and re-reconcile |
| Bug in logic | No matching order found | Manual investigation + code review |

---

#### Step 5: Take Corrective Action

**If it's a fill mismatch:**
```bash
# Add to audit log what happened
# Example: "5 shares of AAPL partial fill at $150.25"
echo '{"timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'", "symbol": "AAPL", "issue": "partial_fill", "qty": 5, "action": "manual_verification_complete"}' >> trading/logs/audit.jsonl

# Update portfolio.json to match actual IB positions
python3 -c "
import json
with open('portfolio.json', 'r') as f:
    data = json.load(f)
# Manually edit positions to match IB
with open('portfolio.json', 'w') as f:
    json.dump(data, f, indent=2)
"

# Commit the fix
git add trading/portfolio.json trading/logs/audit.jsonl
git commit -m '[FIX] Reconciled AAPL position: 95 shares (was 100)'
git push origin main
```

**If it's an open order:**
```bash
# Wait for fill and let verification catch it
# Or cancel order if it's stuck
# Then commit the change
git commit -m '[FIX] Cancelled stale AAPL order'
```

---

## Git/GitHub Issues

### Scenario
Git commits are failing or GitHub push is not working.

### Troubleshooting

#### Check Git Status
```bash
cd ~/.openclaw/workspace
git status
git log --oneline | head -5

# Test commit
echo 'test' > /tmp/test.txt
git add /tmp/test.txt 2>&1
```

**Check for:**
- Repository corruption
- Permissions issues
- Network connectivity

---

#### Fix Common Issues

**Branch mismatch:**
```bash
git branch -v
git checkout main
git fetch origin
git pull origin main
```

**Push failures:**
```bash
# Check remote
git remote -v

# Test push
git push origin main -v

# If auth fails: 
# Re-run: git config --global credential.helper osxkeychain
# Or use SSH instead: git remote set-url origin git@github.com:user/repo.git
```

**Corrupted repository:**
```bash
# Backup current state
cp -r ~/.openclaw/workspace ~/.openclaw/workspace.backup

# Try to repair
git fsck --full

# If severe, restore from backup
rm -rf ~/.openclaw/workspace/.git
cd ~/.openclaw/workspace
git init
git add .
git commit -m '[INIT] Repository recovery'
git remote add origin <github-url>
git push -u origin main
```

---

## Cloud Backup Issues

### Scenario
S3 backup failed or GitHub backup is not accessible.

### Check Backup Status

```bash
# View backup log
tail -20 trading/logs/cloud_backup.jsonl

# List recent backups
python3 -c "from cloud_backup import CloudBackup; backups = CloudBackup.list_backups(); [print(f\"{b.get('timestamp')} - {b.get('status')}\") for b in backups[-10:]]"
```

---

### Troubleshoot S3 Backup

```bash
# Check AWS credentials
aws sts get-caller-identity

# Check S3 bucket
aws s3 ls s3://your-backup-bucket/trading-backups/ | head -10

# Test upload
aws s3 cp /tmp/test.txt s3://your-backup-bucket/test.txt

# Enable S3 backups
export TRADING_BACKUP_S3_BUCKET="your-bucket-name"
python3 cloud_backup.py
```

---

### Troubleshoot GitHub Backups

```bash
# Check git config
git remote -v
git config --global user.name
git config --global user.email

# Test push
git tag test-backup-$(date +%s)
git push origin test-backup-*

# If it fails, see [Git/GitHub Issues](#gitgithub-issues)
```

---

## Prevention Checklist

### Daily Checks ✅
- [ ] Run daily reconciliation @ 8 PM (automatic)
- [ ] Run cloud backup @ 9 PM (automatic)
- [ ] Review reconciliation log for discrepancies
- [ ] Check IB Gateway is running

### Weekly Checks ✅
- [ ] Review commission and slippage reports
- [ ] Test disaster recovery procedure (dry run)
- [ ] Verify git commits are pushing to GitHub
- [ ] Review audit logs for anomalies

### Monthly Checks ✅
- [ ] Test restore from backup
- [ ] Verify 30-day backup retention is working
- [ ] Review overall system health
- [ ] Update this runbook if needed

---

## Contact & Escalation

**For issues not covered here:**

1. **Portfolio discrepancies:** Check audit.jsonl and git log
2. **IB Gateway issues:** Verify TWS/Gateway is running, check credentials
3. **Data loss:** Restore from cloud backup (S3 or GitHub)
4. **Code bugs:** Review logs, check git history, run tests

---

## Appendix: Quick Reference

### Key Files
- **Portfolio state:** `trading/portfolio.json`
- **Stops executed:** `trading/logs/stops_executed.json`
- **Audit log:** `trading/logs/audit.jsonl`
- **Reconciliation log:** `trading/logs/reconciliation.jsonl`
- **Verification log:** `trading/logs/post_execution_verification.jsonl`
- **Recovery log:** `trading/logs/disaster_recovery.jsonl`

### Key Commands
```bash
# Run disaster recovery
python3 trading/disaster_recovery.py

# Run daily reconciliation
python3 trading/daily_reconciliation.py

# Check git status
git log --grep=TRADE --oneline | head -20

# View recent backups
tail -20 trading/logs/cloud_backup.jsonl

# Quick verification test
python3 -c "from post_execution_verification import PostExecutionVerifier; v = PostExecutionVerifier(); print('Connection test...'); v.connect() and print('✅ IB Gateway accessible') or print('❌ IB Gateway not found')"
```

### Exit Codes
- **0:** Success
- **1:** Partial success or mismatches found
- **2:** Failure

---

**End of Disaster Recovery Runbook**
