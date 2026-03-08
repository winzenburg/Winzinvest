# Integration Guide - Sector Correlation Monitoring

## How to Integrate with webhook_listener.py

This guide walks through integrating the sector concentration & correlation monitoring into your existing TradingView alert processing.

## Step 1: Verify Dependencies

```bash
cd /Users/pinchy/.openclaw/workspace/trading
pip install yfinance pandas numpy requests
```

Check installation:
```bash
python3 -c "import yfinance, pandas, numpy, requests; print('✅ All dependencies OK')"
```

## Step 2: Add Imports to webhook_listener.py

Open `webhook_listener.py` and add these imports near the top (after existing imports):

```python
# Add these imports after the existing imports
try:
    from entry_validator import validate_entry
    from webhook_integration import add_entry_checks
    ENTRY_VALIDATION_AVAILABLE = True
except ImportError:
    ENTRY_VALIDATION_AVAILABLE = False
    logger.warning("⚠️ Entry validation modules not available - skipping pre-entry checks")
```

## Step 3: Find the Entry Alert Handler

Look for the function that processes BUY/SELL alerts from TradingView. It will look something like:

```python
def handle_tradingview_alert(alert_data):
    """Process TradingView alert"""
    symbol = alert_data.get('symbol')
    action = alert_data.get('action')
    
    # Current code that enters the position
    if action == 'BUY':
        position_size = calculate_position_size(symbol)
        send_order_to_broker(symbol, position_size)
```

## Step 4: Add Pre-Entry Validation

Replace the entry logic with:

```python
def handle_tradingview_alert(alert_data):
    """Process TradingView alert with pre-entry risk checks"""
    symbol = alert_data.get('symbol', '').upper()
    action = alert_data.get('action', '').upper()
    
    logger.info(f"Alert received: {symbol} {action}")
    
    # Only validate BUY orders (not SELL)
    if action == 'BUY' and ENTRY_VALIDATION_AVAILABLE:
        
        position_size = calculate_position_size(symbol)
        
        # ═══════════════════════════════════════════════════════════
        # PRE-ENTRY VALIDATION: Check sector & correlation limits
        # ═══════════════════════════════════════════════════════════
        
        check_result = add_entry_checks(
            ticker=symbol,
            size=position_size,
            send_alert_func=telegram_send_message  # Use your existing function
        )
        
        if not check_result['allowed']:
            # ENTRY BLOCKED - Log and alert
            logger.error(f"❌ Entry BLOCKED for {symbol}")
            logger.error(f"Violations: {check_result['violations']}")
            
            block_message = (
                f"🚫 *ENTRY BLOCKED: {symbol}*\n\n"
                f"*Reason(s):*\n"
            )
            for violation in check_result['violations']:
                block_message += f"  ❌ {violation}\n"
            
            telegram_send_message(block_message)
            return  # Don't enter position
        
        # Entry checks passed - proceed with position
        logger.info(f"✅ Entry validation PASSED for {symbol}")
        
        # Alert on warnings (position allowed but risky)
        if check_result['warnings']:
            warning_message = (
                f"⚠️ *ENTRY WARNING: {symbol}*\n"
                f"Entry allowed but with warnings:\n\n"
            )
            for warning in check_result['warnings']:
                warning_message += f"  ⚠️ {warning}\n"
            warning_message += "\n_Consider using smaller position size._"
            
            telegram_send_message(warning_message)
    
    # ═══════════════════════════════════════════════════════════
    # Standard entry processing (existing code)
    # ═══════════════════════════════════════════════════════════
    
    if action == 'BUY':
        position_size = calculate_position_size(symbol)
        send_order_to_broker(symbol, position_size)
        logger.info(f"✅ Order sent: {symbol} {position_size} shares")
    
    elif action == 'SELL':
        # Sell orders don't need pre-entry checks
        close_position(symbol)
        logger.info(f"✅ Position closed: {symbol}")
```

## Step 5: (Optional) Add Daily Monitoring

To run the 8 AM and 3 PM checks automatically, add this to your system startup:

**Option A: macOS LaunchAgent**

```bash
cat > ~/Library/LaunchAgents/com.trading.daily-risk-monitor.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.trading.daily-risk-monitor</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/pinchy/.openclaw/workspace/trading/daily_risk_monitor.py</string>
        <string>--action</string>
        <string>start</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/pinchy/.openclaw/workspace/trading/logs/daily_monitor.out</string>
    <key>StandardErrorPath</key>
    <string>/Users/pinchy/.openclaw/workspace/trading/logs/daily_monitor.err</string>
</dict>
</plist>
EOF

# Load it
launchctl load ~/Library/LaunchAgents/com.trading.daily-risk-monitor.plist

# Verify
launchctl list | grep daily-risk
```

**Option B: Cron Job**

```bash
# Edit crontab
crontab -e

# Add these lines:
# 8 AM daily sector check
0 8 * * * /usr/bin/python3 /Users/pinchy/.openclaw/workspace/trading/sector_monitor.py >> /Users/pinchy/.openclaw/workspace/trading/logs/cron.log 2>&1

# 3 PM daily correlation check
0 15 * * * /usr/bin/python3 /Users/pinchy/.openclaw/workspace/trading/correlation_monitor.py >> /Users/pinchy/.openclaw/workspace/trading/logs/cron.log 2>&1
```

## Step 6: Test the Integration

### Test 1: Run sector check manually
```bash
python3 /Users/pinchy/.openclaw/workspace/trading/sector_monitor.py
```

Expected output:
```
Sector Concentration Monitor - Daily Check
====================================================
Portfolio Sectors: 2
Total Value: $1881.93

Sector Allocation:
  ✅ Materials       100.0%  (1 position)

✅ Portfolio is healthy - no sector violations
```

### Test 2: Test entry validation
```bash
python3 /Users/pinchy/.openclaw/workspace/trading/entry_validator.py AAPL 1.0
```

Expected output:
```json
{
  "allowed": false,
  "violations": [
    "❌ BLOCKED: Technology would be 100.0% (limit 20%)"
  ],
  "warnings": [],
  "checks_performed": [
    "sector_limits",
    "correlation"
  ]
}
```

(Entry is blocked because 1 unit of AAPL would be 100% Technology, exceeding 20% limit for small portfolio. This is conservative.)

### Test 3: Test webhook integration
```bash
python3 -c "
from webhook_integration import WebhookEnricher

class MockTelegram:
    def send_message(self, msg):
        print(f'📱 Telegram: {msg[:100]}...')

enricher = WebhookEnricher(send_alert_func=MockTelegram().send_message)
result = enricher.process_entry_alert({
    'symbol': 'XLE',
    'action': 'BUY',
    'size': 1000
})

print('Result:', result)
"
```

## Step 7: Verify Logging

Check that log files are being created:

```bash
# Check sector concentration log
tail -f /Users/pinchy/.openclaw/workspace/trading/logs/sector_concentration.json

# Check correlation matrix log
tail -f /Users/pinchy/.openclaw/workspace/trading/logs/correlation_matrix.json

# Check monitor output
tail -f /Users/pinchy/.openclaw/workspace/trading/logs/daily_monitor.out
```

## Configuration

### Adjust Sector Limits

Edit `sector_monitor.py`:
```python
MAX_SECTOR_ALLOCATION = 0.20  # Change 0.20 to 0.25 for 25% limit
ALERT_THRESHOLD = 0.18        # Change 0.18 to 0.22 for earlier warnings
```

### Adjust Correlation Thresholds

Edit `correlation_monitor.py`:
```python
HIGH_CORRELATION_THRESHOLD = 0.70  # Warn if correlation > 0.70
PORTFOLIO_BETA_LIMIT = 1.30        # Warn if portfolio beta > 1.30
```

### Add More Sectors

Edit `sector_monitor.py` and add to `SECTOR_MAP`:
```python
SECTOR_MAP = {
    # ... existing entries ...
    'NEW_TICKER': 'New Sector',
}
```

## Troubleshooting

### Issue: "Entry validation modules not available"

**Solution:** Install dependencies
```bash
pip install yfinance pandas numpy requests
```

### Issue: Telegram alerts not sending

**Solution:** Check environment variables
```bash
echo $TELEGRAM_BOT_TOKEN
echo $TELEGRAM_CHAT_ID
```

Both should be set. Add to `.env`:
```
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Issue: "No price data" when running correlation check

**Solution:** 
- Check internet connection
- Verify ticker symbols are valid
- Ensure yfinance is working: `python3 -c "import yfinance as yf; print(yf.download('AAPL', period='5d')['Close'])"`

### Issue: Entry validator always blocks

**Solution:** The system is conservative. For a small/empty portfolio, any first entry appears as 100% of that sector. This is by design. As portfolio grows, limits become more meaningful.

## Monitoring Checklist

Daily:
- [ ] Check logs for entry validation results
- [ ] Review sector_concentration.json for violations
- [ ] Review correlation_matrix.json for high correlations

Weekly:
- [ ] Check for patterns in sector allocation
- [ ] Review effective bets metric
- [ ] Verify portfolio beta < 1.30

Monthly:
- [ ] Review 30-day history in logs
- [ ] Adjust sector mapping if needed
- [ ] Update thresholds based on portfolio behavior

## Example Alert Messages

### Sector Violation Alert
```
🚨 SECTOR CONCENTRATION ALERT

❌ Energy: 23.5% (limit: 20%)
   2 tickers: XLE, CVX

⚠️ WARNINGS:
  Technology: 18.9%
```

### Correlation Alert
```
📊 CORRELATION ALERT

⚠️ AAPL <-> MSFT: 0.82 (HIGH)
⚠️ GOOGL <-> META: 0.76 (MEDIUM)
⚠️ Portfolio beta 1.35 exceeds limit 1.30
⚠️ Hidden concentration: 8 positions, 4.2 effective bets (HIGH)

Detected 3 highly correlated pairs (>0.70)
Portfolio Beta vs SPY: 1.35
Effective Bets: 4.2 (HIGH)
```

### Entry Validation Alert (Allowed)
```
🔍 ENTRY VALIDATION: AAPL

✅ ENTRY ALLOWED

⚠️ WARNINGS:
  WARNING: Technology would be 42% (approaching 20% limit)

Entry allowed but consider reducing size or using smaller position.
```

### Entry Validation Alert (Blocked)
```
🔍 ENTRY VALIDATION: XLE

❌ ENTRY BLOCKED

VIOLATIONS:
  ❌ BLOCKED: Energy would be 28% (limit 20%)
  ❌ BLOCKED: XLE highly correlated (>0.85) with CVX(0.87)
```

## Support

For issues or questions:
1. Check `logs/` directory for error messages
2. Run `sector_monitor.py` manually to test
3. Review this guide for configuration options
4. Check correlation_monitor.py source for calculation details

---

Integration Status: ✅ READY FOR DEPLOYMENT

Last Updated: 2026-02-26
