# Options Income Automation - Fully Automated System

**Status:** PRODUCTION - Fully automated execution  
**Last Updated:** February 20, 2026

---

## Overview

Your options income layer is now **fully automated**. The system scans for opportunities twice daily and executes qualifying trades automatically without manual approval.

---

## Strategy

### Two-Layer Income Generation

| Type | Description | Automation |
|------|-------------|------------|
| **Covered Calls** | Sell calls on profitable long positions | ✅ Fully automated |
| **Cash-Secured Puts** | Sell puts on watchlist pullbacks near support | ✅ Fully automated |

### Monthly Target

- **Minimum:** 2 trades/month
- **Ideal:** 4 trades/month  
- **Maximum:** 8 trades/month (safety cap)

---

## Automation Rules

### Covered Call Criteria (All Must Pass)

| Rule | Value | Why |
|------|-------|-----|
| **Minimum Position** | 100+ shares | Need full lot for 1 contract |
| **Unrealized Gain** | >5% | Only sell calls on winners |
| **Strike Selection** | +12% OTM | Room for upside continuation |
| **Room to Strike** | >8% from current | Avoid early assignment |
| **DTE** | 35 days | Monthly expiration cycle |
| **Minimum Premium** | >1.5% of stock price | Worth the effort |

**Example:**  
NVDA bought at $140, now $150 (+7.1% gain)  
→ Sell $168 call (12% OTM), collect ~$3.00 premium (2% yield)

---

### Cash-Secured Put Criteria (All Must Pass)

| Rule | Value | Why |
|------|-------|-----|
| **Scanning Universe** | **S&P 500 + Nasdaq 100 + Russell 2000 + ETFs** | **600+ symbols scanned** |
| **Pullback Range** | 3-8% from recent high | Quality dip, not panic |
| **Support Check** | Within 2% of 50 EMA | Near known support level |
| **Volume Check** | <1.5x average | Normal, not panicked selling |
| **Strike Selection** | 1% below 50 EMA | Good entry if assigned |
| **DTE** | 35 days | Monthly cycle |
| **Assignment Risk** | <$5,000 per contract | Position sizing limit |
| **Minimum Premium** | >1.5% of stock price | Worthwhile return |

**Scanning Scope:**  
- Full S&P 500 constituents (~500 stocks)
- Nasdaq 100 constituents (~100 stocks)  
- Russell 2000 high-volume names (~30 stocks)
- Major sector & international ETFs (~30 ETFs)
- **Total: 600+ symbols per scan**

**Example:**  
SPY pulls back 5% from $600 to $570, near 50 EMA at $568  
→ Sell $563 put (1% below EMA), collect ~$11.00 premium (2% yield)

---

## Safety Limits

### Daily Limits
- **Max 2 options per day** - Prevents over-deployment

### Monthly Limits
- **Max 8 options per month** - Caps total risk exposure

### Per-Contract Limits
- **Max $5,000 assignment risk** - Position sizing control
- **Minimum 1.5% premium** - Quality threshold

### Connection Requirements
- IB Gateway must be running
- Paper trading account (port 7497)
- Client ID 102 (separate from stocks)

---

## Automation Schedule

### Twice-Daily Scans (Weekdays Only)

| Time | Action | Purpose |
|------|--------|---------|
| **10:00 AM ET** | Auto-scan & execute | Morning opportunities |
| **2:00 PM ET** | Auto-scan & execute | Afternoon opportunities |

**Cron:** `0 10,14 * * 1-5` (America/New_York)

### Weekly Progress Check

| Time | Action |
|------|--------|
| **Friday 6:00 PM ET** | Review monthly progress |

Reports if you're on track for 2-4 trades/month.

### Monthly Target Monitoring

The system tracks:
- Total options deployed this month
- Distance to minimum target (2)
- Distance to ideal target (4)
- Alert if falling behind in final week

---

## Execution Flow

```
10:00 AM ET Trigger
     ↓
Connect to IB Gateway
     ↓
Scan Current Positions → Find Covered Call Opportunities
     ↓
Scan Watchlist → Find CSP Opportunities
     ↓
Check Daily Limit (2/day) & Monthly Limit (8/month)
     ↓
For Each Opportunity:
  - Verify all criteria met
  - Check minimum premium (>1.5%)
  - Get real-time option quotes
  - Execute SELL order (market)
  - Wait for fill confirmation
  - Log trade to options_TIMESTAMP.json
  - Send Telegram notification
     ↓
Disconnect from IB Gateway
```

**No manual approval required.** Trades execute immediately if criteria met.

---

## Monitoring & Alerts

### Real-Time Notifications (Telegram)

Every executed trade sends:
```
🤖 AUTO-EXECUTED Options

NVDA $168 C
Type: Covered Call
Premium: $300.00
Expiration: 20260321

✅ Trade logged and confirmed
```

### Weekly Summary (Friday 6PM ET)

Reports monthly progress:
```
📊 Options Income - February 2026

Deployed: 3 trades
Target: 2-4 trades

✅ Minimum target met.
1 more to ideal target
```

### Logs

All trades logged to: `~/.openclaw/workspace/trading/logs/options_*.json`

Each log contains:
- Ticker, strike, right (C/P)
- Fill price and premium collected
- Expiration date
- Execution timestamp

---

## Manual Override

### Temporarily Disable Automation

```bash
openclaw cron disable options-auto-scan
```

### Re-enable

```bash
openclaw cron enable options-auto-scan
```

### View Schedule

```bash
openclaw cron list
```

---

## Test the System

### Manual Test Run

```bash
cd ~/.openclaw/workspace/trading
python3 scripts/auto_options_executor.py
```

This will:
1. Scan for opportunities
2. Execute up to daily limit
3. Log trades
4. Send Telegram notifications

**Safe to run anytime** - respects daily/monthly limits.

---

## Troubleshooting

### "No qualifying opportunities"
✅ **Normal** - means no trades met all criteria. This is good! Quality > quantity.

### "Daily limit reached"
✅ **Expected** - max 2/day to prevent over-trading.

### "Failed to connect to IB"
❌ **Action needed** - Start IB Gateway (port 7497, paper trading).

### "Premium too low"
✅ **Working correctly** - skipped trade below 1.5% minimum.

### "No market data"
⚠️ **Check IB subscription** - may need market data permissions for that ticker.

---

## Performance Tracking

### Target Monthly Income

With 4 trades/month @ ~2% premium each:
- 2 covered calls @ $3,000 stock value = $60/contract × 2 = $120
- 2 CSPs @ $5,000 assignment risk = $100/contract × 2 = $200
- **Total: ~$320/month passive income**

Annualized: **~$3,840/year** from options alone

### Risk Profile

**Covered Calls:**
- Risk: Cap upside if stock continues above strike
- Mitigation: 12% OTM leaves room for appreciation

**Cash-Secured Puts:**
- Risk: Assigned stock at strike if it drops
- Mitigation: Only sell at support levels you'd want to own anyway

---

## System Status

✅ **Auto-executor created** (`auto_options_executor.py`)  
✅ **Cron jobs scheduled** (10 AM & 2 PM ET, weekdays)  
✅ **Weekly monitoring** (Friday 6 PM ET)  
✅ **Safety limits configured** (2/day, 8/month, $5k max risk)  
✅ **Telegram alerts enabled**  
✅ **IB Gateway integration ready**

**Next automatic run:** Monday, 10:00 AM ET

---

## Notes

- **Stock trades still require manual approval** (via Telegram buttons)
- **Options trades are fully automated** (this document)
- Both systems log to separate files for tracking
- IB Gateway must be running during market hours for any trades (stock or options)

---

**Questions?** Check logs at `~/.openclaw/workspace/trading/logs/` or review Telegram notifications.
