# AI-Augmented Job Search System

**Built:** February 19, 2026  
**Purpose:** Automate discovery, research, and outreach for "AI-Augmented Design Operations Leader" role

---

## Strategic Context

**The Challenge:**  
The role Ryan is looking for doesn't exist on job boards. It needs to be created through direct outreach to decision-makers at companies ready to transform their design operations with AI.

**The Solution:**  
An automated system that finds target companies, researches decision-makers, generates personalized outreach, and tracks conversations—all with human approval gates before any message is sent.

---

## Target Role Profile

**Title Variations:**
- Head of Design Operations
- VP/Director of Design
- Principal Design Technologist
- Chief Design Officer (smaller companies)
- AI + Design Operations Lead (emerging)

**Compensation:** $180k+ total comp  
**Location:** Remote or Colorado-based  
**Company Stage:** Funded startups or established enterprises  
**Team Size:** 15+ designers (implies need for operations)

---

## Target Company Criteria

### Must-Have
- 15+ designers on team (design ops need)
- AI-native OR actively transforming with AI
- Remote-friendly culture
- Funded (Series A+) or profitable

### Nice-to-Have
- Design-forward product companies
- B2B SaaS or enterprise software
- Colorado presence or offices
- Recent AI product launches
- Visible design leadership on LinkedIn

### Red Flags
- <10 designers (too small for ops role)
- Non-technical products (e.g., pure services)
- No remote options + not in Colorado
- Heavily regulated industries (slow AI adoption)

---

## System Components

### 1. Discovery Engine
**Purpose:** Find 5-10 target companies per week  
**Sources:**
- LinkedIn company search (designer count, AI keywords)
- Built In (startup/tech company database)
- AngelList (funded startups)
- Glassdoor (team size estimates)
- Y Combinator batch lists (AI-focused companies)

**Output:** `data/companies.json` with company profiles

---

### 2. Research Agent
**Purpose:** Deep-dive on each discovered company  
**Generates:**
- Company brief (stage, funding, product, design team)
- Decision-maker identification (LinkedIn scraping)
- Pain points & opportunities (AI-generated insights)
- Personalization hooks (recent news, launches, hiring)

**Output:** `data/research/[company_slug].json`

---

### 3. Outreach Generator
**Purpose:** Create personalized messages at scale  
**Templates:**
- Cold LinkedIn message (150 words)
- Follow-up email (if no response)
- Warm intro request (via mutual connections)

**Variables:**
- Company-specific observations
- Role-specific pain points
- Personalization hooks
- Portfolio link with UTM tracking

**Output:** `data/outreach/pending/[contact_id].json`

---

### 4. Approval Queue
**Purpose:** Human-in-loop before any message sent  
**Interface:** CLI + dashboard  
**Workflow:**
1. Agent generates message
2. Ryan reviews in approval queue
3. Ryan edits/approves/rejects
4. Approved messages move to "ready to send"
5. Manual send via LinkedIn/email

**Output:** `data/outreach/approved/[contact_id].json`

---

### 5. Tracking Dashboard
**Purpose:** Monitor outreach performance & follow-ups  
**Metrics:**
- Companies discovered (weekly)
- Decision-makers identified
- Messages sent / response rate
- Conversations scheduled
- Portfolio traffic from outreach (UTM tracking)

**Visualization:** HTML dashboard at `dashboard/index.html`

---

## Messaging Framework

### Core Value Proposition

> "I help design teams integrate AI into their operations—not by adding features, but by architecting how designers work. Companies ready to 10x design output with AI need someone who speaks both languages: design systems AND agentic workflows."

### Outreach Template (LinkedIn)

```
Subject: AI + Design Operations at [Company]

Hi [Name],

I noticed [Company] is [specific observation].

I'm Ryan Winzenburg—15 years architecting design operations for healthcare, fintech, and telecom. Now I'm focused on helping design teams integrate AI into their workflows (not just tools, but how they work).

The role I'm looking for doesn't exist yet: AI-Augmented Design Operations Leader. Someone who can transform a 15-person design team into 50-person output through systematic AI integration.

If [Company] is thinking about this transformation, I'd love a 15-minute conversation.

Portfolio: winzenburg.com?utm_source=linkedin&utm_campaign=outreach&utm_medium=[company_slug]

Best,
Ryan
```

### Follow-Up Cadence

**Touch 1 (Day 0):** Initial LinkedIn message  
**Touch 2 (Day 3):** Follow-up if no response ("Bumping this up...")  
**Touch 3 (Day 7):** Email if LinkedIn fails (find email via Hunter.io/RocketReach)  
**Touch 4 (Day 14):** Value-add follow-up (share relevant article/insight)

Stop after 4 touches. Move to "nurture" list for occasional value-add shares.

---

## Data Schema

### Company Record
```json
{
  "id": "uuid",
  "name": "Figma",
  "slug": "figma",
  "url": "https://figma.com",
  "linkedin": "https://linkedin.com/company/figma",
  "stage": "Series D",
  "funding": "$332M",
  "designer_count": 150,
  "location": "San Francisco, CA (Remote)",
  "ai_keywords": ["AI design tools", "auto-layout"],
  "discovered_at": "2026-02-19",
  "status": "researched",
  "notes": ""
}
```

### Contact Record
```json
{
  "id": "uuid",
  "company_id": "uuid",
  "name": "Jane Doe",
  "title": "VP of Design",
  "linkedin": "https://linkedin.com/in/janedoe",
  "email": "jane@figma.com",
  "status": "pending_outreach",
  "outreach_history": [
    {
      "date": "2026-02-20",
      "channel": "linkedin",
      "message": "...",
      "response": null
    }
  ],
  "notes": ""
}
```

---

## Success Metrics

### Week 1-2 (Discovery)
- 50 companies identified
- 150 decision-makers profiled
- 25 outreach messages drafted

### Week 3-4 (Outreach)
- 50 messages sent
- 15% response rate (7-8 responses)
- 5 conversations scheduled

### Month 2 (Optimization)
- 100+ total outreach
- 3-5 companies creating roles
- 1-2 active interview processes

---

## Automation Schedule

**Daily (9:00 AM MT):**
- Discovery agent runs (finds 2-3 new companies)
- Research agent profiles new discoveries
- Outreach generator drafts messages for approval

**Weekly (Sunday 6:00 PM MT):**
- Performance report (companies, contacts, response rate)
- Follow-up queue (who needs touch 2/3/4)
- Portfolio analytics (traffic from outreach)

**Ad-hoc:**
- Human approves/edits messages in queue
- Human sends approved messages via LinkedIn
- Human logs responses in tracking system

---

## Tech Stack

**Language:** Python 3.11+  
**Data Storage:** JSON files (simple, portable)  
**AI Models:** Claude Sonnet 4.5 (research), Gemini Flash (discovery)  
**Web Scraping:** BeautifulSoup, Playwright (for LinkedIn)  
**Analytics:** Simple HTML dashboard + Google Analytics (UTM tracking)  
**Scheduling:** OpenClaw cron jobs

---

## Phase 1 Build (Next 3 Days)

**Day 1: Discovery + Research**
- [x] Project structure
- [ ] Discovery engine (scrape/API)
- [ ] Research agent (company profiling)
- [ ] Test with 10 companies

**Day 2: Outreach + Approval**
- [ ] Outreach generator (template engine)
- [ ] Approval queue (CLI interface)
- [ ] Message editing workflow

**Day 3: Tracking + Dashboard**
- [ ] Tracking system (log responses)
- [ ] Analytics dashboard (HTML)
- [ ] Cron automation setup

---

## Files Structure

```
job-search/
├── PROJECT_BRIEF.md              # This file
├── scripts/
│   ├── discover_companies.py     # Find target companies
│   ├── research_agent.py         # Deep-dive company research
│   ├── generate_outreach.py      # Personalized messages
│   ├── approval_queue.py         # CLI for message review
│   └── track_responses.py        # Log conversations
├── data/
│   ├── companies.json            # Discovered companies
│   ├── contacts.json             # Decision-makers
│   ├── research/                 # Company briefs
│   ├── outreach/
│   │   ├── pending/              # Awaiting approval
│   │   ├── approved/             # Ready to send
│   │   └── sent/                 # Already sent
│   └── responses.json            # Conversation tracking
├── templates/
│   ├── linkedin_cold.txt         # Cold LinkedIn template
│   ├── email_followup.txt        # Email follow-up
│   └── warm_intro.txt            # Mutual connection intro
├── logs/
│   └── job_search.log            # System activity log
└── dashboard/
    └── index.html                # Performance dashboard
```

---

**Status:** Building Phase 1 (Day 1) now...
