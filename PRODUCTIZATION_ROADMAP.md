# Winzinvest Productization Roadmap

Complete synthesis of growth, gamification, and personalization frameworks from the leading practitioners. Everything is now documented in Cursor rules. This roadmap shows **what to build next** and in what order.

---

## Foundation (Completed ✅)

### Growth Infrastructure
- ✅ PMF survey (Sean Ellis 40% benchmark)
- ✅ Activation tracking (D7 first trade metric)
- ✅ Referral mechanics (waitlist growth loop)
- ✅ Admin growth dashboard
- ✅ Database schema updated (Supabase)

### Rules Created
- ✅ `growth-playbook.mdc` — Strategy (Ellis, Balfour, Verna, Chen, Winters, Rachitsky)
- ✅ `growth-metrics-implementation.mdc` — Implementation patterns
- ✅ `trading-dashboard-integration.mdc` — Python ↔ Next.js integration
- ✅ `admin-dashboards.mdc` — Internal metric views
- ✅ `gamification-personalization.mdc` — Ethical engagement design

---

## Phase 1: Transparency & Trust (Next 30 Days)

Based on **Octalysis CD7 (Curiosity) + CD8 (Loss Avoidance) + Hook Model (Variable Reward)**

### 1.1 "What Happened Today" Narrative Widget
**Framework:** Nir Eyal (Hook Model - Variable Reward via curiosity)

Auto-generate natural language summary of daily system activity.

```typescript
interface DailyNarrative {
  date: string;
  summary: string;           // "System screened 47 stocks, executed 3, blocked 5"
  regime: string;            // "STRONG_UPTREND"
  keyDecisions: Array<{
    action: 'entered' | 'exited' | 'blocked' | 'rolled';
    symbol: string;
    reason: string;
  }>;
}
```

**Dashboard widget:**
- Single paragraph narrative (conversational tone)
- 3-5 key decisions with reasons
- Regime context
- Updated once per day after market close

**Data source:** Parse `trading/logs/executions.json` + `rejected_candidates.json`

**Why it works:**
- Satisfies curiosity (users check to see "what happened")
- Builds trust (system is transparent, not a black box)
- Educational (learn system logic over time)
- No action required (passive consumption)

---

### 1.2 Rejected Trades Log (Trust Builder)
**Framework:** Yu-kai Chou (Core Drive 8 - Loss Avoidance)

Show trades the system BLOCKED and why. This builds trust by proving the risk gates work.

```typescript
interface RejectedTrade {
  symbol: string;
  reason: string;              // "Sector exposure 32% (limit: 30%)"
  rejectedAt: string;
  conviction: number;
  outcome?: string;            // "Would have lost $1,200" (if backtest available)
}
```

**Dashboard section:**
- Title: "System Risk Management"
- Shows rejected signals with reasons
- Weekly summary: "System screened 94 stocks, executed 12, blocked 7"
- Breakdown: "3 blocked: sector concentration | 2 blocked: low conviction | 2 blocked: regime gate"

**Why it works:**
- Builds trust ("the system is actually enforcing limits")
- Educational ("I now understand sector concentration")
- Curiosity trigger ("what would have happened if I took TSLA?")

**Data source:** Parse `trading/logs/executions.json` for `status: "REJECTED"` or `status: "BLOCKED"`

---

### 1.3 Portfolio Composition Breakdown
**Framework:** Data visualization (not behavioral psychology)

Show what the system is actually holding (sector mix, strategy mix, long/short balance).

```typescript
interface PortfolioComposition {
  bySector: Array<{ sector: string; notional: number; pct: number }>;
  byStrategy: Array<{ strategy: string; count: number; pct: number }>;
  longShortBalance: { longNotional: number; shortNotional: number; net: number };
  optionsIncome: { premium30d: number; openPositions: number };
}
```

**Dashboard widget:**
- **Sector pie chart** — top 5 sectors + "Other"
- **Strategy breakdown** — SHORT (45%), LONG (35%), MR (15%), OPTIONS (5%)
- **Long/short balance** — visual bar showing net exposure
- **Options premium tracker** — "Collected $2,400 this month"

**Why it works:**
- Answers "what does my portfolio look like?" (transparency)
- No action required (just informational)
- Updated automatically (live data from snapshot)

**Data source:** `trading/logs/snapshot_latest.json` (already exists)

---

## Phase 2: Insight Discovery (Next Sprint)

Based on **Octalysis CD7 (Curiosity) + Hook Model (Variable Reward)**

### 2.1 Performance Explorer (Interactive Filters)
**Framework:** Data discovery (Amplitude/Mixpanel patterns)

Let users slice performance data by regime, strategy, sector, timeframe.

```typescript
interface PerformanceExplorer {
  filters: {
    regime: string[];        // User selects: STRONG_UPTREND, CHOPPY, etc.
    strategy: string[];      // SHORT, LONG, MR, OPTIONS
    sector: string[];        // Technology, Energy, etc.
    timeframe: string;       // 7d, 30d, 90d, YTD
  };
  metrics: {
    winRate: number;
    avgRMultiple: number;
    totalTrades: number;
    profitFactor: number;
  };
}
```

**Dashboard page:**
- Checkboxes for regime, strategy, sector
- Metrics update on filter change (client-side, no reload)
- "Compare to overall" toggle (shows delta vs unfiltered)

**Why it works:**
- Variable reward (never know what pattern you'll discover)
- Self-service (explore at your own pace)
- Educational (learn which conditions work best)
- No pressure (optional deep-dive, not required)

---

### 2.2 "Why Did the System Do This?" Tooltips
**Framework:** SDT (Competence through understanding)

Educational overlay on every position and decision.

**Implementation:**
- Hover on any position → tooltip shows entry rationale
- "Entered AAPL: Conviction 0.72, STRONG_UPTREND regime, Tech sector at 18% (under 30% limit)"
- "Blocked TSLA: Conviction 0.38 (floor: 0.40) — close but not quite"
- "Exited NVDA: Stop hit at $180.50 after 5 days (-1.2R)"

**Purpose:** Users understand system logic without needing to act

---

### 2.3 Regime History Timeline
**Framework:** Data visualization + educational context

Show regime shifts over time and how portfolio responded.

```typescript
interface RegimeTimeline {
  events: Array<{
    date: string;
    regime: string;           // "STRONG_UPTREND" → "CHOPPY"
    portfolioResponse: string; // "Closed 3 shorts, held 8 longs"
    netImpact: number;         // P&L during that regime
  }>;
}
```

**Dashboard widget:**
- Timeline chart showing regime bands (color-coded)
- Clickable events → see what system did during that regime
- "Your portfolio in STRONG_UPTREND: 12 trades, 9 winners, +$4,200"

**Why it works:**
- Helps users understand system behavior
- Shows regime detection is working
- Educational (learn to recognize regimes visually)

---

## Phase 3: Emotional Progress Onboarding (After Founding Members Fill)

Based on **Samuel Hulick (JTBD), Nir Eyal (Hook Model)**

### 3.1 Lifecycle Email Sequence

**Emotional arc:** Anxious trader → Calm operator

| Day | Emotional State | Email Theme | Hook Model Stage |
|---|---|---|---|
| D0 | Anxious, impulsive | "You know the feeling" (problem identification) | External Trigger |
| D3 | Curious, hopeful | "System found 3 setups" (first value delivery) | Action + Reward |
| D7 | Building trust | "A week in: 4 trades, 11 blocked" (proof it works) | Variable Reward |
| D14 | New identity forming | PMF survey: "Would you go back?" | Investment |
| D30 | Calm, confident | "30 days of discipline" (celebrate transformation) | Internal Trigger |

**Implementation:** Email automation via Resend + APScheduler

---

### 3.2 Onboarding Wizard (JTBD Focus)

**Not:** "Welcome to Winzinvest! Let's set up your account."  
**Instead:** "Let's stop you from blowing up your account. Three quick questions."

**Q1:** "What trading mistake do you make most often?"
- Override stops when scared
- Add to losers
- Chase entries after they've moved
- Forget to set stops

**Q2:** "When do you usually override your rules?"
- Down on the day
- Big winner tempts me to add
- Market volatility spikes
- Bored, looking for action

**Q3:** "What would success look like in 90 days?"
- Followed every stop
- Stopped overriding when down
- Consistent P&L curve
- Trading feels boring (good sign)

**Save responses** → personalize emails and dashboard messaging based on their stated problem.

---

## Phase 4: Advanced Personalization (Scale Phase)

Based on **Ronny Kohavi (A/B testing), Xavier Amatriain (recommendation systems)**

### 4.1 Adaptive Feature Recommendations

**Not random:** "Try covered calls!"  
**Personalized:** "78% of users with your profile use covered calls on longs held >14 days. Want to enable?"

**Recommendation engine inputs:**
- Behavior segment (from Phase 1)
- Current positions (options %, hold times, sectors)
- Feature usage (what they've activated)
- Similar user cohorts (collaborative filtering)

**Implementation:**
```typescript
// app/api/recommendations/route.ts

export async function GET() {
  const user = await getUser(session.email);
  const segment = user.behaviorSegment;
  const similarUsers = await getSimilarUsers(user);
  
  // Find features similar users enabled but this user hasn't
  const unusedFeatures = await getUnusedFeatures(user.id, similarUsers);
  
  return NextResponse.json({
    recommendations: unusedFeatures.map(f => ({
      feature: f.name,
      reason: f.adoptionRate > 0.7 ? 'Popular with similar traders' : 'Matches your style',
      adoptionRate: f.adoptionRate,
    })),
  });
}
```

---

### 4.2 Predictive Prompts (Fogg Timing)

**Prompt at the moment of highest motivation + ability.**

**Examples:**

| Moment | User State | Prompt |
|---|---|---|
| User checks dashboard at 9:28 AM on a day with 3 signals | High motivation (curiosity), high ability (already logged in) | "Pre-market found 3 setups. Enable automation for today?" |
| User manually closes a position that hit stop | High motivation (just experienced stop working) | "Want us to set stops automatically?" |
| User forgets to roll a CC, it expires OTM | High motivation (frustrated they missed it) | "Options manager can handle this. Enable?" |

**Implementation:** Event-based prompts (not time-based)
- Store in `UserEvent` table: `event_type`, `prompt_shown`, `action_taken`
- A/B test prompt timing and copy
- Max 1 prompt per day (no spam)

---

## Metrics to Track (Growth + Engagement)

Add these to the admin dashboard:

| Metric | Target | Framework | Why It Matters |
|---|---|---|---|
| **Discipline streak avg** | 45+ days | Octalysis CD2 | Measures habit formation |
| **Override rate** | <5% | Fogg, SDT | Measures autonomy support |
| **Feature adoption by segment** | 70%+ | Personalization | Validates segmentation |
| **"Aha moment" time** | <48 hours | JTBD, Hook Model | Predicts retention |
| **Mastery level distribution** | 60% Practitioner+ by D90 | SDT Competence | Measures skill growth |

**Implementation:** Extend `app/admin/growth/page.tsx` with new cards for each metric.

---

## Ethical Review Checklist

Before shipping any gamification or personalization feature, verify:

- [ ] **Does NOT reward trading frequency** (checked against FCA research)
- [ ] **Does NOT create FOMO** via social comparison
- [ ] **Does NOT use variable rewards tied to trade outcomes** (that's gambling)
- [ ] **DOES support autonomy** (user controls when/how to use feature)
- [ ] **DOES build competence** (user understands system better)
- [ ] **DOES emphasize loss avoidance** over profit chasing

**If any red flag triggers, kill the feature or redesign it.**

---

## Quick Wins (Implement This Week)

These require minimal code and deliver immediate engagement value:

1. **"What Happened Today" widget**
   - Parse `trading/logs/executions.json` (today's date)
   - Count: entered, exited, blocked
   - Auto-generate narrative: "System executed 3 longs in STRONG_UPTREND regime"
   - Display on dashboard (updates every 5 min with snapshot)

2. **Rejected signals breakdown**
   - Parse execution log for rejected/blocked entries
   - Group by reason: conviction, sector, regime, daily budget
   - Show: "47 signals screened, 12 executed, 7 blocked — Top reason: sector concentration"

3. **Portfolio composition pie chart**
   - Read `snapshot_latest.json`
   - Group positions by sector
   - Display: "Tech 28% | Energy 18% | Healthcare 15% | Other 39%"

4. **Weekly insight email**
   - Sunday night: send summary of past week
   - "This week: 12 trades, 8 winners (67% WR), $4,200 net gain"
   - "Interesting: All 4 losses were in Technology sector"
   - Tone: curious observer, not coach

---

## Resources for Implementation

All frameworks are now documented in `.cursor/rules/`:

- **Growth strategy** → `growth-playbook.mdc`
- **Growth implementation** → `growth-metrics-implementation.mdc`
- **System integration** → `trading-dashboard-integration.mdc`
- **Admin dashboards** → `admin-dashboards.mdc`
- **Gamification ethics** → `gamification-personalization.mdc`

**Reference these when:**
- Adding new metrics → `growth-metrics-implementation.mdc`
- Building admin views → `admin-dashboards.mdc`
- Integrating with trading system → `trading-dashboard-integration.mdc`
- Adding engagement features → `gamification-personalization.mdc` (check ethical constraints first!)

---

## Summary

You now have a complete framework for productizing Winzinvest:

**Growth foundations** → PMF tracking, activation metrics, referral loops  
**Engagement mechanics** → Discipline streaks, mastery levels, personalized dashboards  
**Ethical constraints** → Clear boundaries on what NOT to build (FCA research)  
**Implementation patterns** → Database schema, API structure, component patterns  

**Next action:** Pick any P0 item from `gamification-personalization.mdc` and build it. Discipline streak tracker is the easiest starting point (30 minutes of work, high user impact).

The growth loop is live. The engagement mechanics are mapped. The guardrails are in place. Ship it. 🚀
