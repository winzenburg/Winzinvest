# Automated Workflow Triggers

This file defines trigger patterns that activate specialized research and content pipelines. All triggers are case-sensitive and formatted as shown.

---

## Active Workflows

### 1. Research Workflow

**Trigger Pattern:** `Research: [topic]`

**Example:** 
```
Research: AI agents for traders
Research: no-code CRM platforms
Research: caregiver burnout solutions
```

**Pipeline:**
1. **Step 1 — Reddit Research** (30 days)
   - Search subreddits for topic
   - Extract top 10 upvoted posts
   - Mine comments for: pain points, current solutions, feature requests ("I wish...")
   - Categorize complaints and solutions

2. **Step 2 — X/Twitter Research** (30 days)
   - Search tweets/threads on topic
   - Identify trending discussions
   - Extract influencer voices and key arguments
   - Note emerging terminology

3. **Step 3 — Synthesis**
   - Compile into Business Opportunity Brief with sections:
     - Executive Summary (2-3 sentences)
     - Top 3 Pain Points (with quotes/evidence)
     - Current Solutions & Gaps
     - Opportunity Statement
     - Suggested MVP Features (3-5)
     - Market Size Estimate
   
4. **Step 4 — Save & Deliver**
   - Save to `workspace/research/[TOPIC_SLUG]_[DATE].md`
   - Send Telegram summary with key findings
   - Offer follow-up: "Reply 'Build it' to start prototyping"

**Optional Step 5 — Build Prototype**
- Trigger: Reply with "Build it" to research summary
- Action: Spawn sub-agent to prototype simple web app/MVP
- Output: Live prototype URL + code repo link

**Output Format:**
```markdown
# Research Brief: [Topic] — [Date]

## Executive Summary
[2-3 sentence summary]

## Top 3 Pain Points
1. [Pain Point] — "Evidence/quote from Reddit or X"
2. [Pain Point] — "Evidence/quote from Reddit or X"
3. [Pain Point] — "Evidence/quote from Reddit or X"

## Current Solutions & Their Gaps
[What solutions people mention, what they dislike]

## Opportunity Statement
There is an opportunity to build [X] for [Y people] who struggle with [Z].

## Suggested MVP Features
1. [Core feature]
2. [Core feature]
3. [Core feature]
4. [Optional]
5. [Optional]

## Market Size Estimate
[Based on community size, engagement, search volume]

---

## Research Methodology
- **Reddit:** r/[niche] searches, comments mining, voting signals
- **X/Twitter:** Keyword searches, influencer tracking, thread analysis
- **Time Window:** Last 30 days (rolling)
- **Signal Weight:** Community size (500+ upvotes = strong signal), comment volume, influencer endorsement

---

## Next Steps
Reply **"Build it"** to spawn a prototype builder for this opportunity.
```

---

### 2. Content Workflow (Existing)

**Trigger Pattern:** `Content: [topic]`

**Pipeline:**
- Stage 1: Research (web search, trending angles, competitor analysis)
- Stage 2: Writing (YouTube script, blog post, Twitter thread)
- Stage 3: Packaging (markdown + Telegram delivery)

**Output:** `workspace/content/[TOPIC_SLUG]_[DATE].md`

---

## Execution Rules

1. **All triggers are case-sensitive** — Use exact format
2. **Topic slugification:** Replace spaces with dashes, lowercase, max 50 chars
3. **Save immediately** — Don't wait for Telegram delivery
4. **Telegram confirmation** — User can request rebuild/expansion
5. **Build proto on demand** — Only if user explicitly replies "Build it"

---

## Tracking

| Date | Trigger | Topic | Output | Status |
|------|---------|-------|--------|--------|
| [auto-filled] | Research / Content | [auto-filled] | [auto-filled] | [auto-filled] |

*Tracking table updated automatically by agent.*
