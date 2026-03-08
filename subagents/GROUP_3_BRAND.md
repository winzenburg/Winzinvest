# GROUP 3: PERSONAL BRAND SCOUTS

**Purpose:** Job search pipeline + content engagement tracking  
**Schedule:** Tuesday, Thursday at 3:00 PM MT  
**Models:** SCOUT_JOB (qwen2.5:7b), SCOUT_CONTENT (llama3.1:8b) → AGGREGATOR (Claude Sonnet)  
**Cost Budget:** ~$0.05-0.10/week (~$1-2/month typical)

---

## SCOUT_JOB (qwen2.5:7b)

**Input Sources:**
- `job-search/MISSION-CONTROL-GUIDE.md` (dashboard tracking)
- LinkedIn DM logs (warm intro responses)
- Calendar events (scheduled coffee chats)

**Task:**
Extract job search pipeline progress into JSON.

**Expected Input (4k tokens max):**
```json
{
  "period": "last 3 days",
  "tier_1_targets": [
    {"company": "Anthropic", "status": "pending intro", "days_since_request": 0},
    {"company": "Scalar", "status": "pending intro", "days_since_request": 0},
    {"company": "Modal", "status": "pending intro", "days_since_request": 0},
    {"company": "Figma", "status": "awaiting intro", "decision_maker": "Thomas Lowry", "days_elapsed": 2},
    {"company": "Included Health", "status": "research phase", "days_elapsed": 0}
  ],
  "warm_intros": {
    "targeted": 5,
    "requested": 1,
    "responses": 0
  },
  "scheduled_calls": [],
  "deadline": "2026-02-28",
  "days_remaining": 3
}
```

**Expected Output:**
```json
{
  "findings": [
    "Warm intro requests: 1/5 sent (20% complete toward 5-company goal)",
    "0 positive responses yet (normal for day 1-2)",
    "0 coffee chats scheduled",
    "Deadline: Feb 28 (3 days remaining for warm intro targets)"
  ],
  "assumptions": [
    "Intro response time: 24-48h average for professional network",
    "Target: 2-3 coffee chats scheduled by Feb 28"
  ],
  "risks": [
    "Only 3 days to request 4 more intros (very tight timeline)",
    "Figma intro has been pending 2 days (may need follow-up)",
    "No responses yet (normal but concerning if pattern continues through week)"
  ],
  "next_checks": [
    "Send remaining 4 warm intro requests TODAY (Anthropic, Scalar, Modal, Included Health)",
    "Follow up on Figma intro request (check DMs)",
    "Confirm coffee chats scheduled by Feb 27 EOD"
  ],
  "confidence": 0.95
}
```

---

## SCOUT_CONTENT (llama3.1:8b)

**Input Sources:**
- LinkedIn API (post performance, follower count)
- Substack API (Potshards subscribers, open rates)
- Twitter/X API (engagement, reach)

**Task:**
Extract content strategy metrics.

**Expected Input:**
```json
{
  "period": "last 7 days",
  "linkedin": {
    "followers": 1245,
    "followers_new": 12,
    "posts_published": 2,
    "avg_engagement_rate": 0.078,
    "top_post": {"title": "AI agents for X", "views": 892, "likes": 34}
  },
  "potshards": {
    "subscribers": 847,
    "subscribers_new": 15,
    "posts_published": 1,
    "avg_open_rate": 0.62,
    "avg_click_rate": 0.12
  },
  "twitter": {
    "followers": 3200,
    "followers_new": 45,
    "tweets": 8,
    "avg_engagement": 0.042,
    "top_tweet": {"text": "...", "likes": 127}
  }
}
```

**Expected Output:**
```json
{
  "findings": [
    "LinkedIn: 1245 followers (+12 this week, 1% growth)",
    "Potshards: 847 subscribers (+15 this week, 1.8% growth)",
    "Twitter: 3200 followers (+45 this week, 1.4% growth)",
    "Best performer: LinkedIn post 'AI agents for X' (892 views, 3.8% engagement)",
    "Content frequency: Healthy (2 LinkedIn + 1 Potshards + 8 tweets per week)"
  ],
  "assumptions": [
    "Engagement = (likes + comments + shares) / views",
    "Data current to within 24h"
  ],
  "risks": [
    "Growth rate 1-1.8% is slow (target >3% for audience-building phase)",
    "7.8% LinkedIn engagement is solid but declining vs. industry benchmark (10%)",
    "Twitter has highest growth (1.4%) but lowest engagement rate (0.042%)"
  ],
  "next_checks": [
    "Analyze 'AI agents for X' post: what made it perform? Replicate format",
    "Test new content angles: What topics drive >10% LinkedIn engagement?",
    "Compare platforms: Twitter grows followers but low engagement; refocus on LinkedIn quality"
  ],
  "confidence": 0.87
}
```

---

## AGGREGATOR (Claude Sonnet)

**Input:** Both scouts JSON output

**Task:**
Merge into "Personal Brand Status" focusing on Feb 28 job search deadline + content momentum.

**Expected Output:**
```
🚀 PERSONAL BRAND STATUS — Week of Feb 24, 2026

JOB SEARCH PIPELINE
⏰ DEADLINE: Feb 28 (3 DAYS REMAINING)
📊 Progress: 1/5 warm intros sent (20%)
✅ Next Step: Send remaining 4 requests TODAY
⚠️ Risk: Tight timeline — may miss deadline if delays
→ Action: Batch send all remaining intros by EOD Feb 25

CONTENT MOMENTUM
✅ LinkedIn: 1245 followers (+12, +1% vs. last week)
✅ Potshards: 847 subscribers (+15, +1.8% vs. last week)
✅ Twitter: 3200 followers (+45, +1.4% vs. last week)
⚠️ Growth Rate: 1-1.8% is slow (target >3%)
⚠️ LinkedIn Engagement: 7.8% (declining, target 10%+)

TOP PERFORMER:
'AI agents for X' LinkedIn post (892 views, 3.8% engagement)
→ Action: Analyze winning format; publish 1 similar post per week

STRATEGIC INSIGHT:
Job search is the priority now (Feb 28 deadline). Content momentum is healthy but slow. After job search milestone (Mar 1), increase content frequency to accelerate growth to 3%+.

Confidence: High (all scouts verified, no escalation needed)

---

Next Scout Run: Thursday 3:00 PM MT
```

**Escalation Trigger (to Opus):**
- Job search deadline missed (no intros sent by Feb 28)
- Content engagement collapses (>50% drop in engagement rate)
- Unusual negative comment pattern on posts

---

## Cron Schedule

```bash
# FILE: ~/.openclaw/cron/brand-scouts.sh
0 15 * * 2,4 /Users/pinchy/.openclaw/scripts/group-3-scout.sh >> /tmp/group3.log 2>&1
# Runs: Tuesday, Thursday at 3:00 PM MT
```

**Pre-execution Check:**
- Is GROUP 3 already running?
- Is GROUP 1 or GROUP 2 running concurrently?
- If concurrent: queue GROUP 3, wait for other to finish

---

## Cost Tracking

| Run | Models | Cost | Escalated? | Notes |
|-----|--------|------|-----------|-------|
| Tue 3 PM | All local (free) | ~$0.00 | No | Routine tracking |
| Thu 3 PM | Sonnet (if escalate) | ~$0.05 | Possible | Only if deadline risk |

**Target:** ~$0.05-0.10/week max

