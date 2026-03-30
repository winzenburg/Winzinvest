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

## Phase 1: Discipline Mechanics (Next 30 Days)

Based on **Octalysis CD2 (Development) + CD8 (Loss Avoidance) + SDT (Competence)**

### 1.1 Discipline Streak Tracker
**Framework:** Yu-kai Chou (Core Drive 2), Nir Eyal (Hook Model - Investment phase)

Track days without overriding stops, not days traded.

```typescript
interface DisciplineStreak {
  currentStreak: number;      // Days since last override
  longestStreak: number;      // Personal best
  lastOverrideDate: string;   // When they broke streak
  totalOverrides: number;     // Lifetime count
}
```

**Dashboard widget:**
- 🟢 30+ days: "Elite discipline"
- 🟡 7-29 days: "Building the habit"
- 🔴 0-6 days: "Fresh start"

**Database:**
```sql
ALTER TABLE "User" ADD COLUMN "disciplineStreakDays" INTEGER DEFAULT 0;
ALTER TABLE "User" ADD COLUMN "longestDisciplineStreak" INTEGER DEFAULT 0;
ALTER TABLE "User" ADD COLUMN "lastOverrideAt" TIMESTAMP(3);
```

**API:** `POST /api/discipline-event` (called when user overrides a stop or uses kill switch)

---

### 1.2 Rejected Trades Log
**Framework:** Yu-kai Chou (Core Drive 8 - Loss Avoidance)

Show trades the system BLOCKED and why.

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
- Title: "Trades You Didn't Take"
- Shows last 10 rejected signals
- Monthly summary: "System blocked 47 trades this month — estimated saves: $8,400"

**Data source:** Already logged in `trading/logs/rejected_candidates.json` (if exists) or extend execution scripts to log rejections

---

### 1.3 Behavior Segmentation
**Framework:** BJ Fogg (Behavior Model), Personalization research (Kohavi)

Compute user segment from 30-day behavior, personalize dashboard.

**5 Segments:**

| Segment | Definition | Dashboard Personalization |
|---|---|---|
| **Fearful Executor** | 10+ logins/day, rarely overrides | Calm messaging, hide rejected trades |
| **Override Prone** | 3+ kill switch uses in 30d | Emphasize protection, show loss avoidance |
| **Options Focused** | 70%+ positions have CC | Options income at top, hide short equity signals |
| **Momentum Trader** | Avg hold time <5 days | Pyramid, trailing stop features prominent |
| **Set-and-Forget** | <3 logins/week | Weekly digest, emphasize automation |

**Database:**
```sql
ALTER TABLE "User" ADD COLUMN "behaviorSegment" TEXT;
ALTER TABLE "User" ADD COLUMN "segmentComputedAt" TIMESTAMP(3);
```

**Computation script:** `compute_user_segments.py` (runs weekly, updates `User.behaviorSegment`)

---

## Phase 2: Mastery System (Next Sprint)

Based on **SDT (Competence) + Octalysis CD2 (Development)**

### 2.1 Mastery Levels
**Framework:** Self-Determination Theory (Competence), Ramli John (Product-Led Onboarding)

3-tier progression tied to actual understanding.

| Level | Unlock Criteria | Dashboard Mode | Features |
|---|---|---|---|
| **Novice** | Default | Simple (filtered signals) | Auto-execution, pre-filtered signals, educational tooltips |
| **Practitioner** | 30 days + PMF survey + 10 journal entries | Standard | All signals visible, manual gate overrides (with confirmation) |
| **Expert** | 90 days + 60-day discipline streak | Advanced | Parameter tuning, custom screeners, full analytics |

**Database:**
```sql
ALTER TABLE "User" ADD COLUMN "masteryLevel" TEXT DEFAULT 'novice';
ALTER TABLE "User" ADD COLUMN "masteryUnlockedAt" TIMESTAMP(3);
```

**UI:** Progress indicator showing requirements for next level

---

### 2.2 "Why Was This Blocked?" Tooltips
**Framework:** SDT (Autonomy + Competence)

Educational overlay on every rejected signal.

**Implementation:**
- Hover on rejected trade → tooltip shows full gate analysis
- "Conviction 0.38 < floor 0.40 (91% of floor) — Close but not quite"
- "Regime: CHOPPY — strategy disabled in this regime per your settings"
- Link to docs explaining that specific gate

**Purpose:** Increase competence, reduce frustration from "black box" rejections

---

### 2.3 Rule Override History
**Framework:** SDT (Autonomy), Octalysis CD2 (Development)

Show when user broke their own rules and outcome.

```typescript
interface RuleOverride {
  timestamp: string;
  rule: string;              // "Stop loss override"
  symbol: string;
  reason?: string;           // User's stated reason (from journal)
  outcome: string;           // "Lost $800" or "Saved $400"
}
```

**Dashboard widget:** "Your Override History"
- Not shame-inducing
- Factual: "3 overrides this month, 2 losses, 1 win"
- Learning opportunity: "Overrides during STRONG_DOWNTREND: 0% win rate"

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

These require minimal code and deliver immediate value:

1. **Discipline streak tracker**
   - Read `trading/logs/trades.db` → check for stop overrides → compute streak
   - Display on dashboard: "X days without override"
   - Store in `User.disciplineStreakDays`

2. **Rejected trades summary**
   - Parse `trading/logs/rejected_candidates.json` (if exists)
   - Show count + top 3 rejection reasons
   - "System blocked 12 trades this month: 7 conviction, 3 sector, 2 regime"

3. **Behavior segment (basic version)**
   - Compute from existing data: login frequency, kill switch usage
   - Store in `User.behaviorSegment`
   - Show on admin dashboard (verify segments make sense)

4. **Lifecycle email D0**
   - Send welcome email immediately after signup
   - Emotional framing: "You know the feeling..." (problem-aware)
   - Set expectations: "System will screen pre-market, execute at open"

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
