# Engagement Features — Passive Monitoring for Automated Trading

## Overview

This system implements **passive monitoring engagement** designed specifically for automated trading where users observe rather than act. Unlike traditional gamification (streaks, badges, rewards), these features build engagement through **curiosity, transparency, and insight discovery**.

**Core Philosophy:** Users monitor, they don't operate. Engage through curiosity and transparency, not rewards and streaks.

---

## What Was Built

### 1. "What Happened Today" Narrative Widget (P0)

**Purpose:** Satisfy curiosity about daily system activity.

**Location:** Dashboard Overview tab (top row)

**Data Source:** `trading/logs/daily_narrative.json`  
**Generator:** `trading/scripts/generate_daily_narrative.py`  
**Schedule:** Post-close (14:30 MT daily via scheduler)

**Features:**
- Natural language summary of entries, exits, blocks
- Key decisions with context (symbols, reasons, outcomes)
- At-a-glance stats (screened/executed/blocked)
- Current regime badge
- Expandable detail view

**Component:** `trading-dashboard-public/app/components/DailyNarrative.tsx`  
**API:** `GET /api/daily-narrative`

**Example Output:**
```
"The system screened 12 signals today, executed 4, blocked 8. 
Market regime: CHOPPY. Closed 3 positions."

Key Decisions:
📈 Entered TSLA — High conviction momentum signal (0.78)
🛡️ Blocked AAPL — Sector concentration limit (Technology at 32%)
💰 Exited AMD — Take-profit hit (+2.4R) — P&L: +$1,240
```

---

### 2. Portfolio Composition Widget (P0)

**Purpose:** Show what the system is holding right now (transparency).

**Location:** Dashboard Overview tab (top row, next to narrative)

**Data Source:** Built from `dashboard_snapshot.json` (real-time)  
**API:** `GET /api/portfolio-composition`

**Features:**
- Sector exposure breakdown (top 5 + Other)
- Long/Short balance visualization
- Strategy mix (grid cards)
- Net exposure (long/short/neutral)
- Options premium income (30d)

**Component:** `trading-dashboard-public/app/components/PortfolioComposition.tsx`

**Visual:**
- Horizontal bars for sectors with % and $ notional
- Dual-color balance bar (green=long, red=short)
- 2×2 grid for strategy mix

---

### 3. Rejected Trades Widget (P0)

**Purpose:** Build trust by proving risk gates work. Show "what could have been" curiosity.

**Location:** Dashboard Overview tab (full width below composition)

**Data Source:** `trading/logs/executions.json` (JSONL)  
**API:** `GET /api/rejected-trades?period=today|week|month`

**Features:**
- Summary stats (screened/executed/blocked)
- Block rate %
- Estimated savings (if tracking ex-post outcomes)
- Rejection reason breakdown (conviction, sector, regime, budget, etc.)
- Recent 5-10 blocked signals with symbols and reasons

**Component:** `trading-dashboard-public/app/components/RejectedTradesWidget.tsx`

**Rejection Categories:**
- Low Conviction (below threshold)
- Sector Concentration (limit hit)
- Regime Gate (UNFAVORABLE/DOWNTREND blocks)
- Daily Trade Budget (Brandt limit: 4 longs / 3 shorts per day)
- Daily Loss Limit (Benedict circuit breaker)
- Market Timing (gap risk window)

---

### 4. Performance Explorer (P1)

**Purpose:** Self-service data slicing. Answer "How did X perform in Y conditions?"

**Location:** Dashboard Performance tab (bottom, after Backtest Comparison)

**Data Source:** `trading/logs/executions.json` (closed trades)  
**API:** `GET /api/trade-history`

**Features:**
- 4 filter dropdowns: Timeframe, Regime, Strategy, Sector
- Aggregated stats for filtered set:
  - Total trades, Win rate, Avg R-Multiple, Total P&L
  - Profit Factor, Avg Return %, Best/Worst trade
- Trade history table (last 20 matching)
- Real-time filter updates (no page reload)

**Component:** `trading-dashboard-public/app/components/PerformanceExplorer.tsx`

**Use Cases:**
- "How did SHORT strategy perform in STRONG_DOWNTREND?"
- "Which sectors are most profitable in CHOPPY regimes?"
- "What's my win rate over the last 7 days?"

---

### 5. Weekly Insight Email (P0)

**Purpose:** Pull-based transparency report. No FOMO, no push to trade.

**Schedule:** Fridays at 5:00 PM MT (7:00 PM ET)  
**Generator:** `trading/scripts/generate_weekly_insight.py`

**Content:**
- This week's activity (entries, exits, blocks)
- Performance (P&L, win rate, W/L ratio)
- Risk management summary (why signals were blocked)
- Current regime context
- Link to full dashboard (not actionable CTAs)

**Subscribers:** `trading/config/email_subscribers.json` → `weekly_insights[]`

**Design:**
- Clean, editorial style (serif headlines, neutral colors)
- NOT urgent/pushy (no red alerts, no "ACT NOW")
- Transparency-focused ("Here's what your system did")
- CTA: "View Full Dashboard" (not "Trade Now")

**Email Preview:** `trading/logs/weekly_insight_latest.html`

**SMTP Config (`.env`):**
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
SMTP_FROM=noreply@winzinvest.com
```

---

## Architecture Summary

### Data Flow

```
Execution Logs         →    Python Generators        →    JSON Cache Files        →    API Routes        →    React Components
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
executions.json (JSONL)  →  generate_daily_narrative  →  daily_narrative.json    →  /api/daily-narrative  →  DailyNarrative.tsx
executions.json (JSONL)  →  (real-time at API layer)  →  (none)                  →  /api/rejected-trades  →  RejectedTradesWidget.tsx
dashboard_snapshot.json  →  (built by aggregator)     →  dashboard_snapshot.json →  /api/portfolio-comp   →  PortfolioComposition.tsx
executions.json (JSONL)  →  (real-time at API layer)  →  (none)                  →  /api/trade-history    →  PerformanceExplorer.tsx
executions.json (JSONL)  →  generate_weekly_insight   →  weekly_insight_*.html   →  (email via SMTP)      →  User inbox
```

### Scheduled Jobs (via scheduler.py)

| Job | Schedule | Script | Purpose |
|---|---|---|---|
| Daily Narrative | Mon-Fri 14:30 MT (post-close) | `generate_daily_narrative.py` | Writes `daily_narrative.json` |
| Weekly Email | Fri 17:00 MT | `generate_weekly_insight.py` | Sends transparency digest |

---

## How to Use (User Guide)

### Dashboard Widgets

1. **Open the dashboard:** https://winzinvest.com/institutional (production) or http://localhost:3000/institutional (local dev)

2. **Overview Tab (default view):**
   - Top row: Key metrics (NLV, P&L, Sharpe, positions)
   - Second row: **Daily Narrative** + **Portfolio Composition**
   - Third row: **Rejected Trades** (full width)
   - Fourth row: Equity curve

3. **Performance Tab:**
   - Scroll to bottom: **Performance Explorer**
   - Use filters to slice trade history by regime/strategy/sector/timeframe
   - Stats update in real-time as you adjust filters

### Weekly Email

- Delivered every Friday at 7 PM ET to inbox
- No action required — just transparency
- Configure subscribers in `trading/config/email_subscribers.json`
- Opt out via dashboard settings (when built) or remove from config file

---

## Technical Implementation

### Frontend (Next.js / React)

**New Components:**
- `app/components/DailyNarrative.tsx` — 250 lines
- `app/components/PortfolioComposition.tsx` — 230 lines
- `app/components/RejectedTradesWidget.tsx` — 215 lines
- `app/components/PerformanceExplorer.tsx` — 280 lines

**New API Routes:**
- `app/api/daily-narrative/route.ts` — Serves daily narrative JSON
- `app/api/portfolio-composition/route.ts` — Builds sector/strategy mix from snapshot
- `app/api/rejected-trades/route.ts` — Filters and groups rejected signals from JSONL
- `app/api/trade-history/route.ts` — Returns closed trades for explorer

**Changes to Existing Files:**
- `app/institutional/page.tsx` — Added 3 new widgets to Overview tab, 1 to Performance tab

### Backend (Python Trading System)

**New Scripts:**
- `trading/scripts/generate_daily_narrative.py` — Parses executions, writes narrative JSON
- `trading/scripts/generate_weekly_insight.py` — Generates HTML email, sends via SMTP

**New Config:**
- `trading/config/email_subscribers.json` — Email subscription list

**Changes to Existing Files:**
- `trading/scripts/scheduler.py` — Added `generate_daily_narrative` to post-close job, added weekly email job (Fri 17:00)

---

## Data Formats

### daily_narrative.json

```json
{
  "date": "2026-03-29",
  "timestamp": "2026-03-29T14:30:00",
  "summary": "The system screened 12 signals, executed 4, blocked 8. Market regime: CHOPPY.",
  "regime": "CHOPPY",
  "decisions": [
    {
      "action": "entered",
      "symbol": "TSLA",
      "reason": "High conviction momentum signal (0.78)"
    },
    {
      "action": "blocked",
      "symbol": "AAPL",
      "reason": "Sector concentration limit"
    }
  ],
  "stats": {
    "screened": 12,
    "executed": 4,
    "blocked": 8
  }
}
```

### Portfolio Composition API Response

```json
{
  "sectors": [
    { "sector": "Technology", "notional": 45000, "pct": 32.0, "positionCount": 8 }
  ],
  "strategies": [
    { "strategy": "SHORT", "count": 15, "pct": 40.0, "notional": 55000 }
  ],
  "longNotional": 85000,
  "shortNotional": -55000,
  "netNotional": 30000,
  "totalNotional": 140000,
  "optionsPremium30d": 2400
}
```

### Rejected Trades API Response

```json
{
  "period": "Today",
  "totalScreened": 15,
  "totalExecuted": 7,
  "totalBlocked": 8,
  "reasons": [
    { "reason": "Low Conviction", "count": 4, "pct": 50.0 },
    { "reason": "Sector Concentration", "count": 3, "pct": 37.5 }
  ],
  "recentSignals": [
    {
      "symbol": "AAPL",
      "reason": "Conviction 0.52 below threshold 0.55",
      "conviction": 0.52,
      "rejectedAt": "2026-03-29T10:15:00"
    }
  ]
}
```

---

## Testing

### Local Development

1. **Start Python API:**
   ```bash
   cd trading/scripts/agents
   python3 -m uvicorn dashboard_api:app --host 0.0.0.0 --port 8888 --reload
   ```

2. **Start Next.js dev server:**
   ```bash
   cd trading-dashboard-public
   npm run dev
   ```

3. **Access:** http://localhost:3000/institutional

4. **Generate test data:**
   ```bash
   cd trading/scripts
   python3 generate_daily_narrative.py
   python3 generate_weekly_insight.py
   ```

5. **Check outputs:**
   - `trading/logs/daily_narrative.json`
   - `trading/logs/weekly_insight_latest.html` (open in browser)

### Production Deployment

1. **Commit and push:**
   ```bash
   git add .
   git commit -m "Add passive monitoring engagement features"
   git push origin main
   ```

2. **Vercel auto-deploys** from GitHub (no manual deploy needed)

3. **Start scheduler** (if not running):
   ```bash
   cd trading/scripts
   nohup python3 scheduler.py > logs/scheduler.log 2>&1 &
   ```

4. **Verify jobs:**
   ```bash
   tail -f trading/logs/scheduler.log | grep "NARRATIVE\|INSIGHT"
   ```

---

## Monitoring

### Dashboard Health Checks

- **Daily narrative refreshes:** Post-close (14:30 MT)
- **API endpoints respond:** `/api/daily-narrative`, `/api/portfolio-composition`, `/api/rejected-trades`, `/api/trade-history`
- **Components render:** No React errors in browser console
- **Data freshness:** `daily_narrative.json` timestamp should match today

### Email Delivery

- **Check logs:** `trading/logs/scheduler.log` → search for "WEEKLY INSIGHT"
- **Preview HTML:** Open `trading/logs/weekly_insight_latest.html` in browser
- **Test send:** Run `python3 generate_weekly_insight.py` manually
- **Verify SMTP:** Check inbox for delivery (Fridays 7 PM ET)

---

## Next Steps (Phase 2)

### Recommended Enhancements

1. **"Why Did the System Do This?" Tooltips** (P1)
   - Add info icons next to key decisions
   - Tooltip explains the rule/gate that triggered
   - Example: "Blocked due to sector concentration: Technology exposure was 32%, limit is 30%"

2. **Regime History Timeline** (P1)
   - Visual timeline showing regime transitions over 30/90 days
   - Annotate with major trades on regime change days
   - Helps users see how the system adapts

3. **Portfolio Style Segmentation** (P2)
   - Backend: Classify users by their portfolio characteristics
   - Frontend: Customize widget priorities per segment
   - Segments: Nervous Monitor, Weekly Checker, Options Income, Momentum Heavy, Long-Only

4. **Insight Email Personalization** (P2)
   - Per-user: "Your portfolio gained 2.4% this week"
   - Highlight strategies that matched their holdings
   - Adjust content depth by check-in frequency

5. **Performance Milestones** (P2)
   - Celebrate system achievements (not user actions):
     - "System passed 100 trades"
     - "Highest Sharpe ratio recorded: 4.2"
     - "50-trade win streak in STRONG_UPTREND"

---

## Configuration Files

### Email Subscribers

**File:** `trading/config/email_subscribers.json`

```json
{
  "weekly_insights": [
    "user@example.com",
    "another@example.com"
  ],
  "daily_alerts": [
    "admin@example.com"
  ]
}
```

### SMTP Settings

**File:** `trading/.env`

```bash
# Email configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
SMTP_FROM=noreply@winzinvest.com
```

---

## Framework Alignment

### Octalysis Core Drives (Yu-kai Chou)

| Core Drive | Applied Via |
|---|---|
| **CD7: Unpredictability & Curiosity** | Daily narrative (what happened?), Performance explorer (discover patterns) |
| **CD8: Loss Avoidance** | Rejected trades (see risk gates working) |
| **CD2: Development & Accomplishment** | Portfolio composition (understand system performance), Performance metrics |
| **CD1: Epic Meaning & Calling** | Weekly email (founding member, community contribution) |

### Hook Model (Nir Eyal)

| Hook Phase | Implementation |
|---|---|
| **Trigger** | Weekly email (external), Dashboard notification dot (internal) |
| **Action** | Open dashboard, select filters |
| **Variable Reward** | Discover surprising patterns (e.g., "SHORT worked 90% in DOWNTREND") |
| **Investment** | Learn system behavior → better understanding → more trust |

### Fogg Behavior Model (BJ Fogg)

| Element | Implementation |
|---|---|
| **Motivation** | Curiosity (what did the system do?), Trust (is it working?) |
| **Ability** | Zero effort (passive monitoring, auto-generated insights) |
| **Prompt** | Weekly email, Dashboard visit habit |

**Result:** High motivation + High ability = Behavior occurs reliably.

---

## Ethical Safeguards

### What We Do NOT Do

- ❌ Celebrate trading frequency ("You made 10 trades today!")
- ❌ Leaderboards or competitive elements
- ❌ Push notifications about "hot opportunities"
- ❌ Streaks that punish breaks ("You missed your daily check-in!")
- ❌ Animations for trade execution
- ❌ Time-pressure CTAs ("Act now before close!")

### What We DO

- ✅ Transparency about system decisions
- ✅ Curiosity-driven exploration
- ✅ Trust-building through risk gate visibility
- ✅ Education about market context
- ✅ Opt-in, pull-based engagement (not push)

---

## Metrics to Track (Future)

### Engagement Metrics
- Daily active users (DAU) viewing dashboard
- Time spent in Performance Explorer
- Filter interactions (regime/strategy/sector changes)
- Email open rate (weekly insights)
- Email click-through to dashboard

### Correlation with Retention
- Do users who check daily narrative stay longer?
- Does performance explorer usage correlate with subscription renewal?
- Do users who receive weekly emails have higher NPS?

### Trust Indicators
- Rejected trades widget views
- Portfolio composition check frequency
- Response to regime change notifications

---

## Deployment Checklist

- [x] Create React components
- [x] Create API routes
- [x] Build Python generators
- [x] Add scheduler jobs
- [x] Configure email subscribers
- [x] Test type safety (no TypeScript errors)
- [ ] Deploy to Vercel (automatic on git push)
- [ ] Configure SMTP for email sending
- [ ] Restart scheduler to load new jobs
- [ ] Verify widgets render on production dashboard
- [ ] Send test weekly email
- [ ] Monitor engagement in first week

---

## Files Changed

### Created
- `trading-dashboard-public/app/components/DailyNarrative.tsx`
- `trading-dashboard-public/app/components/PortfolioComposition.tsx`
- `trading-dashboard-public/app/components/RejectedTradesWidget.tsx`
- `trading-dashboard-public/app/components/PerformanceExplorer.tsx`
- `trading-dashboard-public/app/api/daily-narrative/route.ts`
- `trading-dashboard-public/app/api/portfolio-composition/route.ts`
- `trading-dashboard-public/app/api/rejected-trades/route.ts`
- `trading-dashboard-public/app/api/trade-history/route.ts`
- `trading/scripts/generate_daily_narrative.py`
- `trading/scripts/generate_weekly_insight.py`
- `trading/config/email_subscribers.json`

### Modified
- `trading-dashboard-public/app/institutional/page.tsx` — Integrated new widgets
- `trading/scripts/scheduler.py` — Added daily narrative + weekly email jobs

---

## Summary

**Built 5 complete engagement features in one session:**

1. ✅ Daily narrative widget (curiosity driver)
2. ✅ Portfolio composition charts (transparency)
3. ✅ Rejected trades widget (trust builder)
4. ✅ Performance explorer (self-service insight)
5. ✅ Weekly insight email (pull-based engagement)

**Philosophy:** Engage through curiosity and transparency, not rewards and streaks. Users monitor, they don't operate.

**Next:** Deploy, test with real usage, measure engagement metrics, iterate on Phase 2 features based on user behavior patterns.
