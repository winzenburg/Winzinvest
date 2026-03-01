# GROUP 2: SAAS METRICS SCOUTS

**Purpose:** Weekly business metrics tracking (Kinlet, Cultivate, Design System)  
**Schedule:** Monday, Wednesday, Friday at 10:00 AM MT  
**Models:** SCOUT_KINLET (llama3.1:8b), SCOUT_CULTIVATE (qwen2.5:7b), SCOUT_DESIGN (deepseek-coder:6.7b) → AGGREGATOR (Claude Sonnet)  
**Cost Budget:** ~$0.05-0.15/week (~$2-3/month typical)

---

## SCOUT_KINLET (llama3.1:8b)

**Input Sources:**
- PostHog API (kinlet.care waitlist page analytics)
- Email signup logs
- Dashboard metrics

**Task:**
Extract and structure Kinlet growth metrics into JSON.

**Expected Input (4k tokens max):**
```json
{
  "analytics_period": "last 7 days",
  "metrics": {
    "page_views": 342,
    "unique_visitors": 128,
    "signups": 12,
    "conversion_rate": 0.094,
    "email_opens": 34,
    "email_clicks": 8,
    "bounce_rate": 0.35
  },
  "previous_week": {
    "signups": 8,
    "conversion_rate": 0.071
  },
  "pipeline": {
    "total_waitlist": 523,
    "tier_1_waitlist": 145
  }
}
```

**Expected Output:**
```json
{
  "findings": [
    "Signups: 12 this week (+50% vs. last week)",
    "Conversion rate: 9.4% (up from 7.1%)",
    "Total waitlist: 523 (12 net new this week)",
    "Bounce rate: 35% (acceptable for early-stage landing page)"
  ],
  "assumptions": [
    "Analytics data accurate within 24h",
    "Signups include only valid email addresses",
    "Conversion = email submits / unique visitors"
  ],
  "risks": [
    "High bounce rate may indicate unclear value prop on hero section",
    "Tier 1 waitlist only 28% of total (most aren't high-intent)"
  ],
  "next_checks": [
    "Analyze bounce cohort: are they hitting CTA or leaving immediately?",
    "Compare Tier 1 vs Tier 2 engagement; identify why 72% aren't prioritizing",
    "A/B test hero section copy to reduce bounce rate to <30%"
  ],
  "confidence": 0.90
}
```

---

## SCOUT_CULTIVATE (qwen2.5:7b)

**Input Sources:**
- Stripe API (revenue, customers, churn)
- GitHub release tags (versioning)
- Support ticket logs

**Task:**
Extract Cultivate business metrics.

**Expected Input:**
```json
{
  "period": "last 7 days",
  "stripe_metrics": {
    "revenue_mrr": 1250,
    "revenue_mrr_previous": 1200,
    "customers_active": 18,
    "customers_new": 1,
    "churn_rate": 0.055,
    "refunds": 0
  },
  "product": {
    "latest_release": "v0.3.2",
    "release_date": "2026-02-23",
    "open_issues": 4,
    "support_tickets": 2
  }
}
```

**Expected Output:**
```json
{
  "findings": [
    "Revenue MRR: $1250 (+$50, +4.2% vs. last week)",
    "Customers: 18 active (+1 new)",
    "Churn: 5.5% (2 customers downgraded/cancelled)",
    "Latest release: v0.3.2 (2 days ago, stable)"
  ],
  "assumptions": [
    "Revenue is accurate to within 1 hour",
    "Churn calculated as: (customers_lost / customers_active_start) * 100"
  ],
  "risks": [
    "5.5% monthly churn is high (target <3% for SaaS)",
    "2 support tickets unresolved (may indicate product issues)",
    "Only 1 new customer this week (growth slowing)"
  ],
  "next_checks": [
    "Analyze the 2 churned customers: Why did they leave? (email survey)",
    "Review 2 open support tickets: Are they blocking other customers?",
    "Investigate 4 open issues: Which are blocking customer adoption?"
  ],
  "confidence": 0.92
}
```

---

## SCOUT_DESIGN (deepseek-coder:6.7b)

**Input Sources:**
- GitHub API (kinetic-ui repo stats)
- Test runner output (last CI run)
- Component checklist (manual tracking)

**Task:**
Extract design system health metrics.

**Expected Input:**
```json
{
  "repo": "winzenburg/kinetic-ui",
  "period": "last 7 days",
  "github": {
    "open_prs": 2,
    "open_issues": 6,
    "last_commit": "2026-02-24T14:32:00Z"
  },
  "ci": {
    "last_run": "2026-02-24T14:35:00Z",
    "status": "FAILED",
    "failed_tests": 3,
    "test_coverage": 0.82
  },
  "components": {
    "total": 24,
    "completed": 18,
    "in_progress": 4,
    "accessibility_audited": 14
  }
}
```

**Expected Output:**
```json
{
  "findings": [
    "2 PRs awaiting review (oldest: 2 days)",
    "CI FAILED: 3 tests broken (likely from recent commits)",
    "Component status: 18/24 (75%) complete, 14/24 (58%) accessible",
    "Test coverage: 82% (good for design system)"
  ],
  "assumptions": [
    "CI test failures are recent (last commit was 2026-02-24)",
    "Accessibility audit = WCAG 2.1 AA compliance"
  ],
  "risks": [
    "CI failure blocks releases (3 failed tests must be fixed before merging)",
    "2 PRs stale (review latency > 48h)",
    "Accessibility coverage 58% (6 components unaudited)"
  ],
  "next_checks": [
    "Debug 3 failing tests: Are they real failures or flaky tests?",
    "Review 2 oldest PRs: Approve or request changes by EOD today",
    "Plan accessibility audit for 6 remaining components (2 per week)"
  ],
  "confidence": 0.88
}
```

---

## AGGREGATOR (Claude Sonnet)

**Input:** All 3 scouts JSON output

**Task:**
Merge SaaS metrics into single "SaaS Health Report". Identify trends, blockers, opportunities.

**Expected Output:**
```
📊 SAAS HEALTH REPORT — Week of Feb 24, 2026

KINLET (Pre-launch, Waitlist Validation)
✅ Signups: 12 (+50% vs. last week)
✅ Conversion: 9.4% (strong for early-stage)
⚠️ Risk: High bounce rate (35%) — unclear value prop
→ Action: A/B test hero section

CULTIVATE (Early-Stage SaaS)
✅ MRR: $1250 (+4.2%)
✅ Customers: 18 (+1)
⚠️ Risk: Churn 5.5% (too high; target <3%)
⚠️ Risk: Support tickets unresolved
→ Action: Conduct churn survey; close support tickets

KINETIC-UI (Design System)
✅ Components: 18/24 complete (75%)
⚠️ Risk: CI FAILED (3 tests broken)
⚠️ Risk: 2 PRs awaiting review (2+ days old)
→ Action: Fix failing tests; review PRs; plan accessibility audit

STRATEGIC VIEW:
- All 3 projects showing momentum (growth, completion, engagement)
- Blocking issues: CI failures, support tickets, churn investigation
- Next priority: Fix CI, reduce churn, accelerate accessibility audit

Confidence: High (all scouts verified, no escalation needed)

---

Next Scout Run: Friday 10:00 AM MT
```

**Escalation Trigger (to Opus):**
- Churn spike >10% MRR
- Critical CI failure blocking release (>24h broken)
- Customer complaint patterns in support tickets

---

## Cron Schedule

```bash
# FILE: ~/.openclaw/cron/saas-scouts.sh
0 10 * * 1,3,5 /Users/pinchy/.openclaw/scripts/group-2-scout.sh >> /tmp/group2.log 2>&1
# Runs: Monday, Wednesday, Friday at 10:00 AM MT
```

**Pre-execution Check:**
- Is GROUP 2 already running?
- Is GROUP 1 or GROUP 3 running concurrently?
- If concurrent: queue GROUP 2, wait for other to finish

---

## Cost Tracking

| Run | Models | Cost | Escalated? | Notes |
|-----|--------|------|-----------|-------|
| Mon 10 AM | All local (free) | ~$0.00 | No | Routine metrics |
| Wed 10 AM | All local (free) | ~$0.00 | No | Routine metrics |
| Fri 10 AM | Sonnet (if escalate) | ~$0.05 | Possible | Only if churn/blocker detected |

**Target:** ~$0.05-0.15/week max

