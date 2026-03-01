# Gap Protection System - Integration Guide

## Overview

The Gap Protection System prevents positions from holding through earnings announcements and major economic events that cause gap risk. It consists of four modules:

1. **earnings_calendar.py** - Fetch and cache earnings dates
2. **econ_calendar.py** - Track major economic events
3. **gap_protector.py** - Core protection logic
4. **gap_protector_scheduler.py** - Scheduled checks and alerts

## Files Created

```
trading/
├── earnings_calendar.py          # Earnings data fetching
├── econ_calendar.py              # Economic events calendar
├── gap_protector.py              # Gap protection logic
├── gap_protector_scheduler.py    # Scheduler & alerts
├── cache/
│   ├── earnings_cache.json       # Cached earnings (auto-created)
│   └── econ_cache.json          # Cached events (auto-created)
├── logs/
│   ├── gap_liquidations.log      # Liquidation history (auto-created)
│   └── gap_alerts.log            # Alert history (auto-created)
└── protected_portfolio.json       # Portfolio with gap data (auto-created)
```

## Quick Start

### 1. Test the Modules

```bash
cd /Users/pinchy/.openclaw/workspace/trading

# Test earnings calendar
python3 earnings_calendar.py

# Test economic calendar
python3 econ_calendar.py

# Test gap protector with mock data
python3 gap_protector.py

# Test scheduler (dry run)
python3 gap_protector_scheduler.py test-all
```

### 2. Configure Environment

Add to `/Users/pinchy/.openclaw/workspace/trading/.env`:

```env
# Gap Protection Configuration
GAP_PROTECTOR_DRY_RUN=true           # Set to false to enable auto-liquidation
AUTO_LIQUIDATE=true                  # Enable automatic liquidation via IB
FINNHUB_API_KEY=your_key_here        # Optional: for alternative earnings fetch
TRADING_ECONOMICS_API_KEY=your_key   # Optional: for economic data

# Telegram alerting
TELEGRAM_BOT_TOKEN=<existing>
TELEGRAM_CHAT_ID=<existing>
```

### 3. Run the Scheduler

#### Option A: Foreground (Development)

```bash
python3 gap_protector_scheduler.py run
```

#### Option B: Background (Production)

```bash
# Create a launchd agent on macOS
cat > ~/Library/LaunchAgents/com.trading.gap-protector.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.trading.gap-protector</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/pinchy/.openclaw/workspace/trading/gap_protector_scheduler.py</string>
        <string>run</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/Users/pinchy/.openclaw/workspace/trading/logs/scheduler.err</string>
    <key>StandardOutPath</key>
    <string>/Users/pinchy/.openclaw/workspace/trading/logs/scheduler.out</string>
</dict>
</plist>
EOF

launchctl load ~/Library/LaunchAgents/com.trading.gap-protector.plist
```

## Integration with Existing Portfolio Tracker

### Patch 1: Enrich portfolio_tracker.py

Add this to the portfolio tracker after fetching positions:

```python
# Add gap protection enrichment
from gap_protector import enrich_portfolio_with_calendar_data, format_gap_protection_report

async def fetch_portfolio_with_gap_protection(ib: IB) -> Dict:
    """Fetch portfolio and enrich with gap protection data"""
    portfolio = await fetch_portfolio(ib)
    
    # Enrich positions with earnings/econ data
    enriched_positions = enrich_portfolio_with_calendar_data(portfolio['positions'])
    portfolio['positions'] = enriched_positions
    
    # Add gap protection summary
    portfolio['gap_protection_report'] = format_gap_protection_report(enriched_positions)
    
    # Check for critical events
    from econ_calendar import check_critical_econ_event
    critical = check_critical_econ_event()
    if critical:
        portfolio['critical_event'] = critical
    
    return portfolio
```

### Patch 2: Add to Portfolio Display

Modify `format_portfolio_report()` in portfolio_tracker.py:

```python
def format_portfolio_report(portfolio: Dict) -> str:
    """Format portfolio with gap protection info"""
    report = existing_report_logic()
    
    # Add gap protection section
    if 'gap_protection_report' in portfolio:
        report += portfolio['gap_protection_report']
    
    # Add critical event warning
    if portfolio.get('critical_event'):
        event = portfolio['critical_event']
        report += f"\n🔴 CRITICAL: {event['description']} - Close positions immediately\n"
    
    return report
```

## Alert System

### Alert Types

1. **Earnings Alert (3:00 PM)**
   - Triggered when position has earnings < 2 days away
   - Action: Warns user, suggests closing position
   - Pre-liquidation: "XYZ earnings tomorrow → will close at open"

2. **Economic Alert (3:00 PM)**
   - Triggered when major econ event < alert_days away
   - Action: Warns user of market volatility
   - Critical events: "CPI in 1 day → closing all positions at open"

3. **Liquidation Alert (8:00 AM)**
   - Triggered when positions violate rules and are auto-liquidated
   - Action: Logs execution, notifies user
   - Post-liquidation: "Closed XYZ @ $105.23 (earnings protection)"

### Sending Alerts

Currently alerts are logged to:
- `trading/logs/gap_alerts.log`
- `trading/logs/gap_liquidations.log`

To enable Telegram alerts:

```python
# In gap_protector_scheduler.py, modify send_alert()
if TELEGRAM_CHAT_ID:
    import requests
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message
    })
```

## Configuration Options

### Environment Variables

```env
# Auto-liquidation control
GAP_PROTECTOR_DRY_RUN=true          # true = test mode (don't liquidate)
AUTO_LIQUIDATE=true                 # true = auto-liquidate violations
IB_AUTO_DISCONNECT_IDLE=1800        # Disconnect after 30min idle

# Alerting
TELEGRAM_BOT_TOKEN=...              # For Telegram alerts
TELEGRAM_CHAT_ID=...
WEBHOOK_URL=http://...              # For custom webhooks

# API Keys
FINNHUB_API_KEY=...                 # For earnings data
TRADING_ECONOMICS_API_KEY=...       # For economic data
```

### Hardcoded Events vs. API

The system uses **hardcoded events** for 2026 to avoid API rate limits:

```python
# In econ_calendar.py - HARDCODED_EVENTS list
HARDCODED_EVENTS = [
    {
        'date': '2026-03-18',
        'event': 'FED_DECISION',
        'description': 'FOMC Meeting & Rate Decision',
        'impact': 'HIGH',
        'alert_days': 3
    },
    # ... more events
]
```

To add more events, edit the HARDCODED_EVENTS list in `econ_calendar.py`.

## Rules

### Earnings Rule
- **Trigger**: Next earnings date ≤ 2 days away
- **Action**: Close position at market open
- **Reason**: Prevent gap risk from earnings surprise

### Economic Event Rules

| Event | Alert Days | Action |
|-------|-----------|--------|
| FED_DECISION | 3 | Close all 3 days before |
| FED_ANNOUNCEMENT | 1 | Close all 1 day before |
| CPI | 1 | Close all 1 day before |
| Jobs Report | 1 | Close all 1 day before |
| GDP | 1 | Close all 1 day before |
| Other | 0 | Monitor only |

## Testing

### Test Earnings Calendar
```bash
python3 earnings_calendar.py
# Shows cached earnings dates and tests alert logic
```

### Test Economic Calendar
```bash
python3 econ_calendar.py
# Shows upcoming economic events and liquidation windows
```

### Test Gap Protector
```bash
python3 gap_protector.py
# Shows gap protection analysis for mock positions
```

### Test Scheduler (Dry Run)
```bash
python3 gap_protector_scheduler.py test-all
# Runs both 3PM and 8AM jobs without liquidating
```

## Logs

All activity is logged to:

```
trading/logs/
├── gap_alerts.log              # All alerts sent
├── gap_liquidations.log        # All liquidations executed
├── scheduler.out               # Scheduler stdout (if using launchd)
└── scheduler.err               # Scheduler stderr (if using launchd)
```

Monitor logs:
```bash
tail -f ~/.openclaw/workspace/trading/logs/gap_alerts.log
tail -f ~/.openclaw/workspace/trading/logs/gap_liquidations.log
```

## Cache Management

### Earnings Cache
- File: `trading/cache/earnings_cache.json`
- Expires: Every 24 hours
- Refresh: Automatic on module import

### Economic Cache
- File: `trading/cache/econ_cache.json`
- Expires: Every 6 hours
- Refresh: Automatic on module import

Clear cache manually:
```bash
rm ~/.openclaw/workspace/trading/cache/*.json
```

## Troubleshooting

### No alerts being sent
1. Check `DRY_RUN` is set to `false` in .env
2. Verify IB Gateway is running and connected
3. Check logs in `trading/logs/`

### Positions not auto-liquidating
1. Verify `AUTO_LIQUIDATE=true` in .env
2. Check IB account ID matches `IB_ACCOUNT` in .env
3. Verify positions are fetched correctly: `python3 gap_protector_scheduler.py test-liquidate`
4. Check `dry_run` parameter in auto_liquidate_violations()

### Earnings dates not found
1. Check yfinance is installed: `pip3 list | grep yfinance`
2. Some symbols may not have earnings data available
3. Try adding Finnhub API key for alternative source

### Economic events not updating
1. Check cache file: `cat trading/cache/econ_cache.json`
2. Cache expires every 6 hours
3. Add more events to HARDCODED_EVENTS in econ_calendar.py

## Production Deployment Checklist

- [ ] Test all modules with mock data (see Testing section)
- [ ] Set `GAP_PROTECTOR_DRY_RUN=false` in .env
- [ ] Set `AUTO_LIQUIDATE=true` in .env
- [ ] Configure Telegram alerts (or alternative webhook)
- [ ] Test 3PM earnings check: `python3 gap_protector_scheduler.py test-earnings`
- [ ] Test 8AM liquidation: `python3 gap_protector_scheduler.py test-liquidate`
- [ ] Set up launchd agent or cron for background execution
- [ ] Monitor logs for 1 week before going live
- [ ] Set up log rotation to prevent disk bloat
- [ ] Document any custom events in HARDCODED_EVENTS

## API Limitations

### yfinance
- Rate limit: ~2000 requests/hour
- No authentication needed
- Earnings data: Hit or miss, some symbols unavailable

### Finnhub
- Free tier: 60 requests/minute
- Requires API key
- Earnings data: More reliable than yfinance

### Trading Economics
- Free tier: Limited access
- Requires API key
- Economic data: Comprehensive but rate limited

## Support

For issues or questions:
1. Check logs in `trading/logs/`
2. Run test jobs to verify functionality
3. Review this documentation
4. Check IB Gateway connection

## Next Steps

1. ✅ Gap protection modules created
2. ✅ Scheduler framework built
3. ⏳ Deploy to production
4. ⏳ Monitor alerts for 1 week
5. ⏳ Refine rules based on market behavior
