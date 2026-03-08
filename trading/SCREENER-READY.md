# AMS NX Screener Integration — READY FOR DATA SOURCE

**Status:** Framework complete, UI live, awaiting data integration  
**Date:** February 24, 2026, 12:51 PM MT  
**Action:** Next step is integrate yfinance or Polygon.io API

---

## What's Built (✅)

### 1. **Screener Executor Framework**
   - File: `trading/screener-executor.mjs`
   - Scans SPY 500 + Nasdaq 100 + Russell 2000 + top 50 ETFs (~1,200 tickers)
   - Applies NX Screener v2 logic (ROC, RSI, RS, volume, price structure)
   - Tier classification (Tier 3/2/1)
   - Ready for data source integration

### 2. **Dashboard Integration**
   - File: `dashboard.html` (updated)
   - New screener section displays Tier 3 + Tier 2 candidates
   - Shows metrics: RS%, Z-Score, Momentum, Volume
   - Auto-updates from `dashboard-data.json`

### 3. **Data Structure**
   - File: `dashboard-data.json` (updated)
   - Added `screener` object with tier3/tier2/tier1/totalCandidates
   - Timestamp tracking (last scan time)
   - Ready to populate with daily results

### 4. **Daily Execution**
   - File: `LaunchAgents/ai.openclaw.screener-executor-daily.plist`
   - Runs daily 8:00 AM MT (Monday-Friday)
   - Logs to: `logs/screener-executor.log`
   - Ready to load: `launchctl load ~/Library/LaunchAgents/ai.openclaw.screener-executor-daily.plist`

### 5. **Email & Telegram Templates**
   - Both ready to integrate
   - Email: Top 10 Tier 3 candidates + full tier breakdown
   - Telegram: Top 5 Tier 3 + link to dashboard

---

## What's NOT Built (❌)

### 1. **Data Source Integration**
   - Screener framework is complete but has no way to fetch price data
   - Need to add: yfinance or Polygon.io API integration
   - Estimated time: 30 min (yfinance) — 1 hour (Polygon)

### 2. **Email Delivery**
   - Template ready
   - Resend API already configured in workspace
   - Need to: Call Resend API in screener-executor.mjs
   - Estimated time: 15 min

### 3. **Telegram Alerts**
   - Message template ready
   - Bot token available
   - Need to: Call Telegram API in screener-executor.mjs
   - Estimated time: 15 min

---

## Quick Start (Next Steps)

### Option A: yfinance (Recommended for MVP)

```bash
# 1. Install yfinance
pip install yfinance

# 2. Update screener-executor.mjs with data fetching
# (See SCREENER-INTEGRATION.md for full instructions)

# 3. Test with a few tickers
node trading/screener-executor.mjs

# 4. Check dashboard-data.json for results

# 5. If successful, load LaunchAgent
launchctl load ~/Library/LaunchAgents/ai.openclaw.screener-executor-daily.plist
```

### Option B: Polygon.io (Recommended for Production)

```bash
# 1. Get API key from polygon.io
# https://polygon.io (sign up free, upgrade to paid for speed)

# 2. Add to .env or Keychain

# 3. Update screener-executor.mjs with Polygon integration
# (See SCREENER-INTEGRATION.md for full instructions)

# 4. Test, then load LaunchAgent
```

---

## File Changes Summary

| File | Change | Status |
|------|--------|--------|
| `dashboard.html` | Added screener section + updateScreener() function | ✅ |
| `dashboard-data.json` | Added screener object with tier3/tier2/tier1 | ✅ |
| `trading/screener-executor.mjs` | Complete framework, awaiting data source | ✅ |
| `LaunchAgents/ai.openclaw.screener-executor-daily.plist` | Daily trigger (8 AM MT) | ✅ |
| `trading/SCREENER-INTEGRATION.md` | Complete documentation | ✅ |

---

## What Happens When You Load the LaunchAgent

**Daily at 8:00 AM MT:**

1. LaunchAgent fires `screener-executor.mjs`
2. Scans ~1,200 tickers with NX Screener v2 logic
3. Updates `dashboard-data.json` with results
4. Mission Control dashboard auto-refreshes (JavaScript watches JSON)
5. Sends email to ryanwinzenburg@gmail.com
6. Sends Telegram alert to @pinchy_trading_bot

**Total runtime:** ~5-10 minutes (depends on data source)

---

## Dashboard Preview

When live, Mission Control will show:

```
🎛️ Mission Control
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 Trading Screener — AMS NX v2
Last scan: 8:00 AM MT

┌─────────────────────────────────────┐
│ Tier 3 Candidates (Highest Quality) │
├─────────────────────────────────────┤
│ AAPL  RS: 72% | Z: 1.2 | Mom: 8.5%  │
│ NVDA  RS: 68% | Z: 0.9 | Mom: 6.2%  │
│ MSFT  RS: 65% | Z: 0.8 | Mom: 5.8%  │
│ ...                                 │
│ (Tier 3 total: 12 qualified)        │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ Tier 2 Candidates                   │
├─────────────────────────────────────┤
│ TSLA  RS: 61% | Z: 0.7              │
│ META  RS: 58% | Z: 0.6              │
│ ...                                 │
│ (Tier 2 total: 24 qualified)        │
└─────────────────────────────────────┘

Total qualified: 42 candidates
```

---

## Testing Before Production

Run this before enabling daily automation:

```bash
# Manual test
cd ~/.openclaw/workspace
node trading/screener-executor.mjs

# Check output
cat logs/screener-executor.log

# Verify dashboard-data.json was updated
cat dashboard-data.json | jq '.screener'

# Check dashboard.html loads correctly
open dashboard.html
```

---

## What's the Broken Cron?

You had `watchlist-auto-sync` running 211+ times with zero output. This is now **replaced** with the new screener integration.

**Should I delete it?** YES — it's abandoned and only wastes CPU cycles.

```bash
# To delete (if you want)
rm ~/.openclaw/workspace/cron-jobs/watchlist-auto-sync.* 2>/dev/null
```

---

## Ready to Proceed?

What's the next step?

1. **Install yfinance** and integrate data fetching?
2. **Set up Polygon.io** API key and integrate?
3. **Test screener** with sample tickers first?
4. **Load LaunchAgent** and schedule first run?
5. **All of the above** (I can do overnight)?

Let me know. Framework is ready. Just needs data source + alerts hooked up.
