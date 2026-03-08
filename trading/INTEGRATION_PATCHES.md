# Integration Patches for Trade Reconciliation System

This document describes how to integrate the post-execution verification, auto-commit, and disaster recovery modules into existing trading code.

## Overview

The reconciliation system provides 7 new modules:
- `post_execution_verification.py` - Verify trades execute correctly
- `daily_reconciliation.py` - Daily position reconciliation
- `git_auto_commit.py` - Auto-commit trades to GitHub
- `cloud_backup.py` - Daily cloud backups
- `disaster_recovery.py` - Recovery from crashes
- `commission_tracker.py` - Track commissions
- `slippage_tracker.py` - Track slippage on stops

Integration points are:
1. **webhook_listener.py** - Verify positions after entry
2. **stop_manager.py** - Verify stops are placed
3. **Cron jobs** - Daily reconciliation and backup
4. **Git hooks** - Auto-commit after trades

---

## Patch 1: webhook_listener.py Integration

### Purpose
After a BUY entry webhook is received and position is placed, verify that IB actually received the position.

### Current Code Structure
```python
class TradingViewWebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Parse alert_data
        # Send to broker (place position)
        # Send Telegram alert
```

### Patch: Add Post-Entry Verification

**Location:** After position is placed with broker

**Add these imports at top:**
```python
from post_execution_verification import PostExecutionVerifier
from git_auto_commit import auto_commit_trade
import time
```

**Add this function to the webhook handler class:**
```python
def verify_position_entry(self, symbol, quantity):
    """
    Verify that position was actually placed in IB Gateway
    
    Args:
        symbol: Stock symbol
        quantity: Expected quantity
        
    Returns:
        (verified: bool, details: dict)
    """
    try:
        logger.info(f"🔍 Verifying position entry: {symbol} {quantity} shares")
        
        # Give IB a moment to process the order
        time.sleep(1)
        
        # Verify with IB Gateway
        verifier = PostExecutionVerifier()
        if not verifier.connect(timeout_seconds=10):
            logger.warning(f"⚠️  Cannot verify - IB Gateway unavailable")
            return False, {'error': 'IB Gateway unavailable'}
        
        try:
            verified, result = verifier.verify_position_open(symbol, quantity)
            
            if verified:
                logger.info(f"✅ Position verified: {symbol} {quantity} shares in IB")
                return True, result
            else:
                logger.error(f"❌ Position mismatch: {symbol}")
                logger.error(f"   Expected: {quantity}, Actual: {result.get('actual_qty')}")
                return False, result
                
        finally:
            verifier.disconnect()
            
    except Exception as e:
        logger.error(f"❌ Error verifying position: {e}")
        return False, {'error': str(e)}
```

**Modify the BUY handling code:**

BEFORE:
```python
if action == 'BUY':
    # Place position with broker
    position_size = calculate_position_size(symbol, risk_pct)
    send_to_broker(symbol, position_size)
    
    # Send alert
    send_telegram_message(f"BUY {symbol} {position_size} shares")
```

AFTER:
```python
if action == 'BUY':
    # Place position with broker
    position_size = calculate_position_size(symbol, risk_pct)
    send_to_broker(symbol, position_size)
    
    # VERIFY POSITION WAS PLACED
    verified, verification = self.verify_position_entry(symbol, position_size)
    
    if not verified:
        alert_msg = f"⚠️  ENTRY ALERT: Placed {symbol} {position_size} but verification failed!\n"
        alert_msg += f"Expected {position_size}, got {verification.get('actual_qty', 'unknown')}\n"
        alert_msg += "Check IB Gateway and audit logs immediately"
        send_telegram_message(alert_msg)
    else:
        alert_msg = f"✅ BUY {symbol} {position_size} shares (verified in IB)"
        send_telegram_message(alert_msg)
        
        # AUTO-COMMIT THE TRADE
        try:
            auto_commit_trade(
                symbol=symbol,
                action='BUY',
                price=get_current_price(symbol),
                qty=position_size,
                reason='TradingView webhook entry'
            )
        except Exception as e:
            logger.error(f"⚠️  Failed to auto-commit: {e}")
```

### Integration Checklist
- [ ] Add imports for verification and auto-commit
- [ ] Add `verify_position_entry()` method
- [ ] Modify BUY handling to verify and commit
- [ ] Test with a small position entry
- [ ] Monitor logs for verification results

---

## Patch 2: stop_manager.py Integration

### Purpose
After a stop-loss order is placed, verify that IB received it.

### Current Code Structure
```python
class StopLossManager:
    def place_stop(self, symbol, entry_price, quantity, ...):
        # Calculate stop price
        # Place stop order with IB
        # Log to stops_executed.json
```

### Patch: Add Stop Verification

**Add these imports at top:**
```python
from post_execution_verification import PostExecutionVerifier, verify_stop_placed
from commission_tracker import CommissionTracker
```

**Add this method to StopLossManager class:**
```python
def verify_stop_placement(self, symbol, order_id=None):
    """
    Verify that stop-loss order was placed in IB
    
    Args:
        symbol: Stock symbol
        order_id: Order ID (optional)
        
    Returns:
        (verified: bool, details: dict)
    """
    try:
        logger.info(f"🔍 Verifying stop placement: {symbol} (order_id: {order_id})")
        
        # Verify with IB Gateway
        verifier = PostExecutionVerifier()
        if not verifier.connect(timeout_seconds=10):
            logger.warning(f"⚠️  Cannot verify stop - IB Gateway unavailable")
            return False, {'error': 'IB Gateway unavailable'}
        
        try:
            verified, result = verifier.verify_stop_placed(symbol, order_id)
            
            if verified:
                logger.info(f"✅ Stop verified: {symbol}")
                return True, result
            else:
                logger.error(f"❌ Stop not found for {symbol}")
                return False, result
                
        finally:
            verifier.disconnect()
            
    except Exception as e:
        logger.error(f"❌ Error verifying stop: {e}")
        return False, {'error': str(e)}
```

**Modify the place_stop method:**

BEFORE:
```python
def place_stop(self, symbol, entry_price, quantity, ...):
    # ... existing code ...
    
    # Place stop order with IB
    order = self.ib.placeOrder(contract, stop_order)
    
    # Log to stops_executed.json
    self._log_stop(symbol, stop_price, order_id)
    
    logger.info(f"✅ Stop placed: {symbol} @ ${stop_price}")
    return {'order_id': order_id, 'symbol': symbol, 'stop_price': stop_price}
```

AFTER:
```python
def place_stop(self, symbol, entry_price, quantity, ...):
    # ... existing code ...
    
    # Place stop order with IB
    order = self.ib.placeOrder(contract, stop_order)
    
    # Log to stops_executed.json
    self._log_stop(symbol, stop_price, order_id)
    
    logger.info(f"✅ Stop placed: {symbol} @ ${stop_price}")
    
    # VERIFY STOP WAS PLACED
    import time
    time.sleep(1)  # Give IB a moment to process
    
    verified, verification = self.verify_stop_placement(symbol, order_id)
    
    if not verified:
        logger.error(f"❌ Stop verification failed: {symbol}")
        logger.error(f"   Details: {verification}")
        # Log alert but don't crash - position is still protected
    else:
        logger.info(f"✅ Stop verified in IB: {symbol}")
    
    return {
        'order_id': order_id,
        'symbol': symbol,
        'stop_price': stop_price,
        'verified': verified
    }
```

### Integration Checklist
- [ ] Add imports for verification
- [ ] Add `verify_stop_placement()` method
- [ ] Modify `place_stop()` to verify and log result
- [ ] Test with a stop placement
- [ ] Monitor verification logs

---

## Patch 3: Cron Job Setup

### Purpose
Run daily reconciliation and backup at scheduled times.

### Cron Job 1: Daily Reconciliation @ 8:00 PM

**Add to crontab:**
```bash
# Run daily reconciliation at 8:00 PM
0 20 * * * cd ~/.openclaw/workspace && python3 trading/daily_reconciliation.py >> trading/logs/cron_reconciliation.log 2>&1
```

**OR use launchd (macOS):**
```bash
# Create: ~/Library/LaunchAgents/com.trading.daily-reconciliation.plist
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.trading.daily-reconciliation</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/pinchy/.openclaw/workspace/trading/daily_reconciliation.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>20</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/pinchy/.openclaw/workspace/trading/logs/cron_reconciliation.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/pinchy/.openclaw/workspace/trading/logs/cron_reconciliation.err</string>
</dict>
</plist>

# Load it
launchctl load ~/Library/LaunchAgents/com.trading.daily-reconciliation.plist
```

### Cron Job 2: Cloud Backup @ 9:00 PM

**Add to crontab:**
```bash
# Run daily cloud backup at 9:00 PM
0 21 * * * cd ~/.openclaw/workspace && python3 trading/cloud_backup.py >> trading/logs/cron_backup.log 2>&1
```

**OR use launchd (macOS):**
```bash
# Create: ~/Library/LaunchAgents/com.trading.daily-backup.plist
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.trading.daily-backup</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/pinchy/.openclaw/workspace/trading/cloud_backup.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>21</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/pinchy/.openclaw/workspace/trading/logs/cron_backup.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/pinchy/.openclaw/workspace/trading/logs/cron_backup.err</string>
</dict>
</plist>

# Load it
launchctl load ~/Library/LaunchAgents/com.trading.daily-backup.plist
```

### Verification

```bash
# Check cron jobs are running
crontab -l

# Check macOS launchd jobs
launchctl list | grep trading

# Monitor logs
tail -f trading/logs/cron_reconciliation.log
tail -f trading/logs/cron_backup.log
```

---

## Patch 4: Git Hooks Integration (Optional)

### Purpose
Auto-commit trades even if manual commits fail.

### Setup

**Create: .git/hooks/post-commit** (optional - for additional logging)

```bash
#!/bin/bash
# Log successful commits
COMMIT_MSG=$(git log --format=%B -n 1)
if [[ "$COMMIT_MSG" == *"[TRADE]"* ]]; then
    echo "[$(date)] Auto-committed: $COMMIT_MSG" >> trading/logs/git_hooks.log
fi
```

**Make it executable:**
```bash
chmod +x .git/hooks/post-commit
```

---

## Patch 5: Test Integration

### Test Script

Create: `trading/test_integration.py`

```python
#!/usr/bin/env python3
"""
Test the integrated reconciliation and backup system
"""

import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_post_execution_verification():
    """Test post-execution verification module"""
    logger.info("Testing post_execution_verification...")
    try:
        from post_execution_verification import PostExecutionVerifier
        verifier = PostExecutionVerifier()
        logger.info("✅ post_execution_verification imported successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False

def test_daily_reconciliation():
    """Test daily reconciliation module"""
    logger.info("Testing daily_reconciliation...")
    try:
        from daily_reconciliation import DailyReconciler
        logger.info("✅ daily_reconciliation imported successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False

def test_git_auto_commit():
    """Test git auto-commit module"""
    logger.info("Testing git_auto_commit...")
    try:
        from git_auto_commit import GitAutoCommitter
        committer = GitAutoCommitter()
        if committer.git_available:
            logger.info("✅ git_auto_commit available")
            return True
        else:
            logger.warning("⚠️  Git not available")
            return False
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False

def test_cloud_backup():
    """Test cloud backup module"""
    logger.info("Testing cloud_backup...")
    try:
        from cloud_backup import CloudBackup
        logger.info("✅ cloud_backup imported successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False

def test_disaster_recovery():
    """Test disaster recovery module"""
    logger.info("Testing disaster_recovery...")
    try:
        from disaster_recovery import DisasterRecoveryManager
        logger.info("✅ disaster_recovery imported successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False

if __name__ == '__main__':
    results = {
        'post_execution_verification': test_post_execution_verification(),
        'daily_reconciliation': test_daily_reconciliation(),
        'git_auto_commit': test_git_auto_commit(),
        'cloud_backup': test_cloud_backup(),
        'disaster_recovery': test_disaster_recovery()
    }
    
    print("\n" + "="*70)
    print("INTEGRATION TEST RESULTS")
    print("="*70)
    
    for module, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{module:40s} {status}")
    
    print("="*70)
    
    if all(results.values()):
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed - check log above")
        sys.exit(1)
```

**Run it:**
```bash
python3 trading/test_integration.py
```

---

## Checklist: Complete Integration

- [ ] Patch webhook_listener.py with post-entry verification
- [ ] Patch stop_manager.py with stop verification
- [ ] Configure daily reconciliation cron/launchd job @ 8 PM
- [ ] Configure cloud backup cron/launchd job @ 9 PM
- [ ] Create git auto-commit integration hook (optional)
- [ ] Run integration test script
- [ ] Monitor logs for 1 week to verify everything works
- [ ] Test disaster recovery procedure (dry run)
- [ ] Document any custom changes in INTEGRATION_NOTES.md

---

## Troubleshooting

### IB Gateway Connection Fails
```bash
# Check IB Gateway is running
ps aux | grep IB

# Test connection
telnet localhost 4002

# Check firewall
sudo lsof -i :4002
```

### Cron Jobs Not Running
```bash
# Check crontab
crontab -l

# Check logs
tail -20 /var/log/system.log | grep cron

# Test command manually
cd ~/.openclaw/workspace && python3 trading/daily_reconciliation.py
```

### Git Commits Failing
```bash
# Check git status
git status

# Check remote
git remote -v

# Test commit locally
git log --oneline | head -5
```

---

**End of Integration Patches**
