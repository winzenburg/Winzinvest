# OpenClaw ↔ Cultivate Integration

**Built:** February 19, 2026  
**Purpose:** Automate infrastructure, enforce gates, and support the 30-agent product creation engine

---

## Integration Architecture

```
Discovery (Manus/ChatGPT) → Validation (AI research) → Build (Cursor) → Scale (OpenClaw automation)
         ↓                           ↓                       ↓                    ↓
    [Score ≥8.0]              [Thresholds Pass]      [Brand + Dev Docs]    [Deploy + Monitor]
         ↓                           ↓                       ↓                    ↓
    OpenClaw tracks          OpenClaw validates       OpenClaw scaffolds   OpenClaw instruments
```

---

## My Role in Your Framework

### Phase 1: Discovery (Supporting)
**Your tools:** Manus (niche research), ChatGPT (clustering), Claude (critique)

**My contributions:**
- Track all discovery artifacts in `cultivate/discovery/[idea-slug]/`
- Auto-generate discovery checklist based on Greg Isenberg methodology
- Monitor Discovery Score as docs are created
- **Gate enforcement:** Block progression if score <8.0
- Pull competitor analysis via web scraping
- Create discovery summary dashboard

### Phase 2: Validation (Enforcing)
**Your tools:** Manus (pain validation), ChatGPT (synthesis), Cursor (organize)

**My contributions:**
- Enforce validation thresholds before allowing build phase
- Track validation evidence in structured format
- Generate validation report with pass/fail on each threshold
- **Gate enforcement:** Block build if validation incomplete
- Monitor boring pain vs. novelty (flag if too novel)
- Track urgency/frequency metrics

### Phase 3: Build (Scaffolding)
**Your tools:** Cursor (implementation), ElevenLabs (voice assets)

**My contributions:**
- Scaffold project structure from templates
- Set up PostHog feature flags
- Configure multi-tenancy (Clerk + Supabase RLS)
- Enforce WCAG 2.2 AA baseline checks
- **Gate enforcement:** Require Brand System + Dev Quality docs
- Create deployment pipeline
- Set up monitoring and analytics

### Phase 4: Scale (Automating)
**Your tools:** Lindy AI (outreach), FeedHive (content)

**My contributions:**
- Deploy to Vercel with proper env configs
- Instrument NSM tree + counter-metrics
- Set up automated testing
- Create analytics dashboards
- Monitor user feedback loops
- Generate weekly product health reports

---

## Mandatory Gates (Automated Enforcement)

I'll enforce your gates programmatically:

| Gate | Check | Action if Failed |
|------|-------|------------------|
| **Discovery → Validation** | Score ≥ 8.0 | Block, show missing criteria |
| **Validation → Build** | All thresholds pass | Block, show failing thresholds |
| **Build → Brand** | Brand System doc exists | Block, provide template |
| **Build → Code** | Dev Quality plan exists | Block, provide template |
| **Deploy → Production** | All tests pass + feature flags | Block, show failures |

---

## File Structure I'll Manage

```
cultivate/
├── discovery/
│   ├── [idea-slug]/
│   │   ├── niche-research.md          # From Manus
│   │   ├── pain-validation.md         # From research
│   │   ├── competitor-analysis.md     # Auto-generated
│   │   ├── score.json                 # Discovery Score tracker
│   │   └── gate-status.json           # Phase gate tracking
├── validation/
│   ├── [idea-slug]/
│   │   ├── thresholds.json            # Pass/fail status
│   │   ├── evidence.md                # Supporting data
│   │   └── validation-report.md       # Auto-generated summary
├── build/
│   ├── [product-slug]/
│   │   ├── brand-system.md            # Required gate doc
│   │   ├── dev-quality-plan.md        # Required gate doc
│   │   ├── feature-flags.json         # PostHog config
│   │   └── architecture.md            # Technical spec
├── scale/
│   ├── [product-slug]/
│   │   ├── nsm-tree.json              # North Star Metric
│   │   ├── analytics-dashboard.html   # Real-time metrics
│   │   ├── deployment-log.json        # Deploy history
│   │   └── health-report.md           # Weekly auto-generated
└── templates/
    ├── discovery-checklist.md
    ├── validation-thresholds.md
    ├── brand-system-template.md
    ├── dev-quality-template.md
    └── nsm-tree-template.json
```

---

## Commands I'll Add

```bash
# Discovery phase
cultivate discover start [idea-name]        # Create discovery structure
cultivate discover score [idea-name]        # Calculate current score
cultivate discover gate-check [idea-name]   # Check if ready for validation

# Validation phase
cultivate validate start [idea-name]        # Create validation structure
cultivate validate check [idea-name]        # Run threshold checks
cultivate validate report [idea-name]       # Generate validation report
cultivate validate gate-check [idea-name]   # Check if ready for build

# Build phase
cultivate build scaffold [product-name]     # Create project from template
cultivate build gates [product-name]        # Check Brand + Dev docs exist
cultivate build deploy [product-name]       # Deploy with safety checks

# Scale phase
cultivate scale instrument [product-name]   # Set up NSM tracking
cultivate scale health [product-name]       # Generate health report
cultivate scale dashboard [product-name]    # Launch analytics dashboard
```

---

## Automation I'll Provide

### Daily (via Cron)
- **Morning:** Discovery score check for active ideas (flag if stalled)
- **Afternoon:** Validation threshold monitoring (alert if evidence gaps)
- **Evening:** Build progress summary (PRs, deployments, tests)

### Weekly (Sundays)
- Product health reports for all scaled products
- Portfolio-wide metrics dashboard
- NSM tree review (are metrics moving?)
- Technical debt scan

### On-Demand (You trigger)
- Competitor analysis refresh
- Market size estimation
- User feedback sentiment analysis
- Feature flag performance review

---

## Dashboard I'll Build

**Cultivate Command Center** (HTML dashboard at `cultivate/dashboard/index.html`):

### Discovery Tab
- Active ideas with current scores
- Gate status (Discovery → Validation readiness)
- Days in each phase
- Blocker alerts

### Validation Tab
- Threshold checklist with pass/fail
- Evidence summary
- Market size estimates
- Pain urgency/frequency scores

### Build Tab
- Active products under development
- Gate compliance (Brand + Dev docs)
- Test coverage
- Deploy readiness

### Scale Tab
- NSM trees for all products
- Counter-metrics dashboard
- User feedback sentiment
- Weekly/monthly growth trends

---

## Integration with Your Existing Tools

| Your Tool | My Integration |
|-----------|----------------|
| **Manus** | I organize Manus outputs into structured discovery docs |
| **ChatGPT** | I track synthesis artifacts and enforce formatting |
| **Claude** | I log critiques and create action items from reviews |
| **Cursor** | I scaffold structure, you implement with Cursor |
| **Lindy AI** | I feed validated ideas → Lindy for outreach automation |
| **ElevenLabs** | I generate voice asset specs, you create with ElevenLabs |
| **FeedHive** | I schedule content based on product milestones |
| **PostHog** | I configure feature flags based on validation |

---

## Example Workflow

**Scenario:** You discover a new SaaS idea via Manus research

**1. Discovery (You + Manus → Me organizing)**
```bash
$ cultivate discover start "ai-powered-careplan-builder"
✅ Created: cultivate/discovery/ai-powered-careplan-builder/
📋 Checklist created with Greg Isenberg criteria
📊 Score tracker initialized (current: 0/10)
```

You research with Manus → I organize outputs → Track score

**2. Gate Check (Me enforcing)**
```bash
$ cultivate discover gate-check "ai-powered-careplan-builder"
Discovery Score: 7.5/10

❌ GATE BLOCKED - Score must be ≥8.0

Missing criteria:
- Market size estimation (add to niche-research.md)
- Competitor differentiation unclear (add to competitor-analysis.md)

Run again after addressing gaps.
```

**3. Validation (You + research → Me validating)**
```bash
$ cultivate validate start "ai-powered-careplan-builder"
✅ Moved to validation phase
📋 Threshold checklist created
⏳ Awaiting evidence...
```

You validate with surveys/interviews → I track thresholds

**4. Build (Me scaffolding → You implementing)**
```bash
$ cultivate build scaffold "careplan-builder"
✅ PostHog feature flags configured
✅ Multi-tenancy structure created (Clerk + Supabase)
✅ Brand System template generated
✅ Dev Quality plan template generated
📂 Project ready at: SaaS-Starter/apps/careplan-builder/

Next: Complete Brand System + Dev Quality docs, then begin implementation
```

**5. Scale (Me automating)**
```bash
$ cultivate scale instrument "careplan-builder"
✅ NSM tree configured: "Careplans created per week"
✅ Counter-metrics: churn rate, plan completion rate
✅ Analytics dashboard: cultivate/scale/careplan-builder/dashboard.html
✅ Weekly health reports scheduled (Sundays 8 PM)
```

---

## What I'll Build Next

**Priority 1 (Today/Tomorrow):**
1. Create the file structure (`cultivate/discovery`, `validation`, `build`, `scale`)
2. Build the gate enforcement system
3. Create templates (discovery checklist, validation thresholds, etc.)
4. Build the Discovery Score calculator

**Priority 2 (This Week):**
5. Create the Cultivate Command Center dashboard
6. Set up daily/weekly cron jobs for monitoring
7. Build the validation threshold checker
8. Create the scaffolding system for new products

**Priority 3 (Next Week):**
9. Integrate with PostHog for feature flags
10. Build NSM tree instrumentation
11. Create health report generator
12. Set up portfolio-wide metrics

---

## Your Role vs. My Role (Clear Boundaries)

| Phase | Your Focus | My Focus |
|-------|------------|----------|
| **Discovery** | Research (Manus), synthesis (ChatGPT), critique (Claude) | Organize, track score, enforce gate |
| **Validation** | Interview, survey, validate pain | Structure evidence, check thresholds, enforce gate |
| **Build** | Implement features (Cursor), create assets (ElevenLabs) | Scaffold, deploy, monitor, enforce gates |
| **Scale** | Outreach (Lindy), content (FeedHive) | Instrument NSM, dashboards, health reports |

**Key principle:** I handle plumbing and enforcement. You handle creative work and decision-making.

---

## Success Metrics (How We'll Know This Works)

**Velocity:**
- Time from idea → validated concept: <2 weeks (vs. months)
- Time from validated → deployed: <1 week (vs. months)

**Quality:**
- 0 products shipped without validation (gate enforcement works)
- 100% of products have NSM tree instrumented
- All products maintain ≥80% test coverage

**Leverage:**
- Infrastructure code reused across all products (no rebuilding basics)
- Discovery/validation artifacts reusable for future ideas
- Automated monitoring reduces manual checking to <30 min/week

---

**Ready to start building this integration?** 

I'll create the structure, templates, and gate enforcement system. You keep using your proven tools (Manus, Cursor, etc.) and I'll make sure the framework is enforced and the infrastructure is automated.

Should I begin with Priority 1 (file structure + gate enforcement)?
