# Mission Control Job Search Dashboard — User Guide

**Updated:** Feb 25, 2026  
**Purpose:** Comprehensive job search pipeline tracking and organization

---

## Overview

Mission Control now includes a dedicated **Career** section with five subsections to keep your job search organized:

1. **Pipeline Overview** — High-level metrics (warm intros, applications, response rates)
2. **Tier 1: Priority Targets** — 5 companies receiving deep research + direct outreach
3. **Tier 2: Strong Alternatives** — 3 backup options (solid but lower priority)
4. **Next Actions** — Actionable tasks with urgency flags
5. **Outreach Timeline** — 3-phase roadmap (Feb-Apr 2026)

---

## Section Breakdown

### Pipeline Overview

**Metrics displayed:**
- **Tier 1 Companies:** 5 priority targets
- **Warm Intros Sent:** Progress toward 5-intro goal
- **Applications:** Active applications in flight
- **Response Rate:** Estimated response rate from outreach
- **Compensation Target:** $180-250K + 0.5-1.5% equity
- **Current Phase:** Warm intro phase (Feb 25-28)

**Status indicators:**
- 🟢 Green (online) = Warm intro pending or request in flight
- 🟡 Yellow (pending) = Research phase (collecting intel)
- 🔴 Red (offline) = Watchlist (lower priority)

---

### Tier 1: Priority Targets (5 Companies)

Each company card shows:
- **Company name** (linked to research)
- **Target role** (Design Ops, Product Design, etc.)
- **Location** (San Francisco, Denver, Remote, etc.)
- **Decision-maker** (VP Product, Head of Design, etc.)
- **Warm intro status** (Pending, Cold intro, 1-degree away)
- **Current status** (Research phase, Warm intro pending, Active application)
- **Notes** (culture, growth stage, strategic fit)

**Current Tier 1:**
1. **Anthropic** — Design Ops (AI safety, smaller team, growth phase)
2. **Scalar** — Design Ops (enterprise AI, rapid growth)
3. **Modal** — Design Ops (serverless platform)
4. **Figma** — Design Systems Lead (1-degree intro available)
5. **Included Health** — Design Ops (healthtech, caregiver alignment)

**Action:** Request warm intros for all 5 by Feb 28.

---

### Tier 2: Strong Alternatives (3 Companies)

Lower-priority watchlist with potential:

1. **Databricks** — Design Ops (data infrastructure)
2. **Gusto** — Design Systems Lead (local: Denver, CO)
3. **Framer** — Design Infrastructure (design tools)

**Status:** All currently in "Watchlist" (cold intro, lower priority)

---

### Next Actions

Auto-populated from `dashboard-data.json`. Currently shows:

- ⚠️ Request warm intros: Anthropic, Scalar, Modal (by Feb 28) — **URGENT**
- ⚠️ Request warm intro: Figma (1-degree intro available) — **URGENT**
- Complete Tier 1 research briefs (by Feb 28)
- Post positioning content on LinkedIn (weekly)

**How urgency works:** Actions with "by Feb 28" are flagged in orange as time-sensitive.

---

### Outreach Timeline

**3-phase approach:**

| Phase | Timeline | Focus |
|-------|----------|-------|
| **Phase 1** | Feb 25-28 | Warm intro requests → 2-3 coffee chats target |
| **Phase 2** | Mar 1-31 | LinkedIn content visibility + thought leadership |
| **Phase 3** | Apr 1+ | Direct outreach + warm intro follow-ups |

---

## How to Update the Dashboard

All data is stored in `dashboard-data.json` under the `career` object. To update:

### 1. Add a New Warm Intro Request

In `dashboard-data.json`, under `warmIntroMetrics`:

```json
"warmIntroMetrics": {
  "targeted": 5,      // Number of people you want to approach
  "requested": 1,     // Number you've actually asked
  "responseRate": null,
  "successRate": null,
  "nextCheck": "2026-02-28"
}
```

**Update `requested` after:**
- Emailing the person requesting the intro
- Asking in Slack or similar
- Following up on existing relationship

### 2. Update Company Status

Each Tier 1 company has a `status` field:
- `"Research phase"` — Gathering intel
- `"Warm intro pending"` — Waiting on friend to connect
- `"Active application"` — Submitted to job board
- `"Phone screen scheduled"` — Moving through pipeline
- `"Onsite scheduled"` — Final stage

**Update `warmIntroStatus`:**
- `"Pending"` — Haven't reached out yet
- `"Pending (1 degree away)"` — Have mutual connection
- `"In flight"` — Asked friend to intro
- `"Connected"` — Friend made the intro
- `"Warm conversation"` — Initial call scheduled/completed
- `"Cold intro"` — Direct outreach (no warm connection)

### 3. Track Applications

In `applicationMetrics`:

```json
"applicationMetrics": {
  "submitted": 0,          // Total applications sent
  "responseRate": null,    // % of applied roles that responded
  "phoneScreens": 0,       // Number of phone screens
  "onsites": 0,            // Number of onsites scheduled
  "offers": 0              // Offers received
}
```

### 4. Add Next Actions

Update the `nextActions` array. Keep each action concise:

```json
"nextActions": [
  "Request warm intros: Anthropic, Scalar, Modal (by Feb 28)",
  "Request warm intro: Figma (1-degree intro available)",
  "Complete Tier 1 research briefs (by Feb 28)",
  "Post positioning content on LinkedIn (weekly)"
]
```

**Tip:** Include dates in your action text (e.g., "by Feb 28") to auto-trigger urgency flagging.

### 5. Update Timeline Phases

```json
"timeline": {
  "phase1": "Warm intros: Feb 25-28 (target 2-3 coffee chats)",
  "phase2": "Content visibility: Mar (LinkedIn, written)",
  "phase3": "Direct outreach + follow-ups: Apr"
}
```

---

## Updating Company Details

To modify a Tier 1 or Tier 2 company entry, update its object directly:

```json
{
  "company": "Anthropic",
  "category": "AI Infrastructure",
  "location": "San Francisco",
  "targetRole": "Design Operations or Product Design",
  "priority": 1,
  "decisionMaker": "Mike Krieger (CPO)",
  "warmIntroStatus": "Pending (via enterprise network)",
  "applicationDate": "2026-02-25",  // Add when applied
  "responseDate": "2026-02-27",     // Add when they respond
  "status": "Warm intro pending",    // Matches dashboard display
  "notes": "Safety-first culture, smaller team, growth phase"
}
```

---

## Dashboard Refresh

The dashboard refreshes automatically every 30 seconds, so changes to `dashboard-data.json` appear live.

**To manually refresh:** Press F5 or visit `file:///Users/pinchy/.openclaw/workspace/dashboard.html`

---

## Recommended Workflow

### Daily (5 min)
1. Open Mission Control dashboard
2. Check **Next Actions** for today's priorities
3. Review warm intro status changes

### Weekly (20 min)
1. Update `applicationMetrics` with new submissions
2. Update company statuses based on responses
3. Add new next actions or mark old ones complete
4. Check Tier 2 for promotion to Tier 1

### Milestone (Phase transition)
1. When moving from Phase 1 to Phase 2: Update `timeline` and `pipelineStage`
2. When receiving offers: Update `applicationMetrics.offers` and note in company status

---

## Quick Reference: Company Data Fields

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `company` | string | "Anthropic" | Company name |
| `category` | string | "AI Infrastructure" | Industry category |
| `location` | string | "San Francisco" | HQ location |
| `targetRole` | string | "Design Operations" | Role you're targeting |
| `priority` | number | 1 or 2 | Tier 1 or Tier 2 |
| `decisionMaker` | string | "Mike Krieger (CPO)" | Key contact |
| `warmIntroStatus` | string | "Pending" | See update section |
| `applicationDate` | string | "2026-02-25" | When you applied |
| `responseDate` | string | "2026-02-27" | When they responded |
| `status` | string | "Warm intro pending" | Current phase |
| `notes` | string | "Safety-first culture..." | Context/research |

---

## Troubleshooting

**Q: The dashboard doesn't show my updates**  
A: Make sure you saved the JSON file, then refresh the browser (F5). Dashboard auto-refreshes every 30 seconds.

**Q: How do I move a company from Tier 2 to Tier 1?**  
A: Update the `priority` field from `2` to `1` and move it in the JSON array. Re-rank if needed.

**Q: Can I add more than 5 Tier 1 companies?**  
A: Yes. Update `warmIntroMetrics.targeted` to match your new count. (But 5 is recommended for depth.)

**Q: Where do I track interview prep notes?**  
A: Add them to the `notes` field for each company, or create a separate `interview-prep/` folder in your job-search directory.

---

## Integration with GitHub

After updating the dashboard:
```bash
cd ~/.openclaw/workspace
git add dashboard-data.json dashboard.html
git commit -m "Update job search: [description of changes]"
git push origin main
```

Changes will auto-deploy to your Vercel instance (Mission Control live dashboard).

---

**Last updated:** Feb 25, 2026  
**Next review:** Weekly (every Friday)
