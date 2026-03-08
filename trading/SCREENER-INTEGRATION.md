# AMS NX Screener v2 Integration — Mission Control Dashboard

**Status:** Framework complete, awaiting data source integration

**Date Created:** February 24, 2026  
**Last Updated:** February 24, 2026

---

## Overview

The AMS NX Screener v2 has been integrated into Mission Control dashboard with the following components:

| Component | Status | Details |
|-----------|--------|---------|
| **Screener Logic** | 📋 PLANNED | Pine Script v2 logic replicated in Node.js |
| **Dashboard UI** | ✅ BUILT | Tier 3/2/1 display, metrics, timestamps |
| **Data Structure** | ✅ BUILT | dashboard-data.json with screener section |
| **Daily Executor** | ✅ BUILT (framework) | LaunchAgent plist + screener-executor.mjs |
| **Email Alerts** | 📋 PLANNED | Template ready, Resend API integration needed |
| **Telegram Alerts** | 📋 PLANNED | Message ready, bot integration needed |
| **Data Source** | ❌ NOT STARTED | Requires yfinance/polygon.io/IB API |

---

## File Structure

```
trading/
├── screener-executor.mjs          # Main executor (framework, awaiting data source)
├── SCREENER-INTEGRATION.md        # This file

dashboard.html                      # Updated with screener UI section
dashboard-data.json                 # Updated with screener data structure

LaunchAgents/
└── ai.openclaw.screener-executor-daily.plist  # Daily 8:00 AM MT trigger
```

---

## Architecture

### 1. Daily Execution Flow

**Time:** 8:00 AM MT (Monday-Friday)

```
LaunchAgent fires
  ↓
screener-executor.mjs runs
  ↓
Scan universes (SPY 500 + Nasdaq 100 + Russell 2000 + top 50 ETFs)
  ↓
Apply NX Screener v2 logic to each ticker:
  • ROC (21, 63, 126 bars)
  • RSI (14 bar)
  • Absolute Momentum (126 bar)
  • Relative Strength vs SPY (126 bar)
  • Volume & Liquidity
  • Price Structure (Higher Highs/Lows)
  ↓
Rank by Composite Score
  ↓
Classify into Tiers (Tier 3 > Tier 2 > Tier 1)
  ↓
Update dashboard-data.json
  ↓
Send email to ryanwinzenburg@gmail.com
  ↓
Send Telegram alert to @pinchy_trading_bot
```

### 2. Dashboard Display

**Location:** `dashboard.html` (new screener section after header)

**Shows:**
- Tier 3 candidates (top 20, highest quality)
- Tier 2 candidates (top 15, secondary quality)
- Total candidate count
- Last scan timestamp

### 3. Data Flow

```
screener-executor.mjs
  ↓
dashboard-data.json (screener section)
  ↓
dashboard.html (JavaScript populates UI)
  ↓
Mission Control Dashboard (browser view)
```

---

## Configuration

### Universes to Scan

```javascript
SPY500      // 500 largest cap stocks
NASDAQ100   // 100 largest tech stocks
RUSSELL2000 // 2,000 small-cap stocks
ETFs        // 19 sector + broad market ETFs
```

**Total: ~1,200 tickers scanned daily**

### Tier Thresholds

| Tier | Composite Score | Expected Count/Day |
|------|----------------|--------------------|
| **Tier 3** | ≥ 0.35 | 5-20 |
| **Tier 2** | 0.20-0.35 | 10-30 |
| **Tier 1** | < 0.20 | 20-50 |

### Output Limits

- **Tier 3 displayed:** Top 20 (sorted by score descending)
- **Tier 2 displayed:** Top 15
- **Tier 1 displayed:** Top 10 (in dashboard data)

### Schedule

| Day | Time | Action |
|-----|------|--------|
| Mon-Fri | 8:00 AM MT | Screener runs, results posted |
| Weekends | OFF | No scanning |

---

## Implementation Status

### ✅ COMPLETE

- [x] Dashboard UI layout (screener section)
- [x] Data structure (dashboard-data.json)
- [x] JavaScript population logic
- [x] LaunchAgent plist (daily trigger)
- [x] Screener executor framework
- [x] Tier classification logic
- [x] Email/Telegram templates

### ⏳ IN PROGRESS

**Data Source Integration** — Need to choose and implement one:

1. **yfinance (Python)**
   - Free, no API key
   - Easy to use
   - Slower for large universes (~5-10 min for 1,200 tickers)
   - Recommended for MVP

2. **Polygon.io API**
   - Paid subscription (~$30-100/mo)
   - Fast (~30 sec for 1,200 tickers)
   - More reliable
   - Recommended for production

3. **Interactive Brokers API**
   - Already integrated (IB Gateway running)
   - Real-time data
   - Slower for bulk queries
   - Good for watchlist monitoring, not full universe scans

4. **Alpha Vantage**
   - Free tier (5 req/min) - too slow
   - Paid tiers available
   - Not recommended for 1,200 ticker scan

**Recommendation:** Start with **yfinance** for MVP, upgrade to **Polygon.io** if scan times exceed 10 minutes.

### 📋 TO DO

- [ ] Install and test yfinance integration
- [ ] Implement data fetching in screener-executor.mjs
- [ ] Test screener logic against known candidates
- [ ] Integrate Resend API for email delivery
- [ ] Integrate Telegram bot for alerts
- [ ] Load LaunchAgent plist: `launchctl load ~/Library/LaunchAgents/ai.openclaw.screener-executor-daily.plist`
- [ ] First run: Tuesday 2026-02-25 8:00 AM MT

---

## Email Alert Template

**To:** ryanwinzenburg@gmail.com  
**Subject:** `AMS NX Screener Daily — [Date]`

```
🎯 AMS NX SCREENER DAILY REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SCAN DATE: February 24, 2026
SCAN TIME: 8:00 AM MT
TOTAL QUALIFIED: 42 candidates

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏆 TOP 10 TIER 3 (HIGHEST QUALITY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. AAPL
   RS: 72% | Z-Score: 1.2 | Momentum: 8.5% | Volume: 1.45x

2. NVDA
   RS: 68% | Z-Score: 0.9 | Momentum: 6.2% | Volume: 1.32x

[... top 10 listed ...]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VIEW ALL RESULTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Tier 1-3 candidates: [Dashboard Link]
Screener logic: AMS NX v2 (aligned with TradingView)
Next scan: Feb 25, 8:00 AM MT
```

---

## Telegram Alert Template

**To:** @pinchy_trading_bot (Telegram)

```
🎯 AMS NX Screener Daily — Feb 24

📊 TOP 5 TIER 3 CANDIDATES:
1. AAPL (RS: 72%, Z: 1.2)
2. NVDA (RS: 68%, Z: 0.9)
3. MSFT (RS: 65%, Z: 0.8)
4. TSLA (RS: 61%, Z: 0.7)
5. META (RS: 58%, Z: 0.6)

📈 Total qualified: 42 candidates

[View all] → Mission Control Dashboard
```

---

## Testing Checklist

Before first production run (Tuesday 8:00 AM MT):

- [ ] screener-executor.mjs runs without errors
- [ ] Data source (yfinance) integrated and tested
- [ ] Sample ticker returns expected scores
- [ ] dashboard-data.json updates correctly
- [ ] dashboard.html displays results
- [ ] Email alert sends to ryanwinzenburg@gmail.com
- [ ] Telegram alert sends to @pinchy_trading_bot
- [ ] LaunchAgent plist loads: `launchctl load ~/Library/LaunchAgents/ai.openclaw.screener-executor-daily.plist`
- [ ] Manual test run: `node trading/screener-executor.mjs`
- [ ] Verify first automated run output

---

## Next Steps (Priority Order)

1. **Integrate Data Source** (yfinance)
   - Install: `pip install yfinance`
   - Implement: Fetch OHLCV for each ticker
   - Test: 5-10 sample tickers

2. **Test Screener Logic**
   - Known good candidates (e.g., AAPL)
   - Known bad candidates (e.g., low liquidity)
   - Verify tier classification

3. **Email Integration** (Resend API)
   - Already configured in workspace
   - Update screener-executor.mjs with email function

4. **Telegram Integration**
   - Use existing @pinchy_trading_bot token
   - Implement message sending in screener-executor.mjs

5. **Load LaunchAgent**
   - Run: `launchctl load ~/Library/LaunchAgents/ai.openclaw.screener-executor-daily.plist`
   - Verify: `launchctl list | grep screener`

6. **First Production Run**
   - Tuesday 2026-02-25 8:00 AM MT
   - Monitor logs: `tail -f logs/screener-executor.log`

---

## Known Limitations (MVP)

- **Weekends off** (no scanning Saturday-Sunday)
- **Single universe scan** (could later split into parallel jobs)
- **No intraday updates** (daily only at 8 AM)
- **Tier 1 not displayed** (only Tier 3 and Tier 2 shown)
- **No historical tracking** (current results only)

---

## Success Criteria

✅ **Daily Execution**
- Screener runs without errors every weekday 8:00 AM MT
- Results posted to Mission Control within 5 minutes
- Email and Telegram alerts sent

✅ **Data Quality**
- Tier 3 candidates have RS > 65%, Z > 0.75
- Tier 2 candidates have RS > 50%, Z > 0.5
- No illiquid stocks (< $500K daily volume)

✅ **Integration**
- Dashboard displays candidates correctly
- Email format matches template
- Telegram alerts reach user immediately

---

## Support & Debugging

**Logs:**
- `logs/screener-executor.log` — Standard output
- `logs/screener-executor-error.log` — Errors
- `logs/dashboard-refresh.log` — Dashboard updates (if run via cron)

**Manual Test:**
```bash
node ~/.openclaw/workspace/trading/screener-executor.mjs
```

**Check LaunchAgent Status:**
```bash
launchctl list | grep screener
```

**View Next Scheduled Run:**
```bash
launchctl list ai.openclaw.screener-executor-daily
```

---

**Owner:** Mr. Pinchy  
**Last Status Update:** February 24, 2026 (framework complete, awaiting data integration)
