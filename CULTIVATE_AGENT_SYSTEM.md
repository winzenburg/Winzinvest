# Cultivate Agent System Quick Reference

This document summarizes your 30-agent product creation engine from winzenburg/SaaS-Starter.

## The Single Factory Pipeline

```
Discovery → Validation → Build → Scale
```

**Core Principle**: Validation-first development. No engineering without validated demand.

---

## Tool Lane Responsibilities

| Tool | Responsibility | What It Does | What It Doesn't Do |
|------|---------------|--------------|-------------------|
| **Manus** | Research & synthesis | Niche narrative, pain signals, JTBD seeds, competitor analysis | Code, structured docs |
| **ChatGPT** | Breadth & clustering | Variants, clustering, fast expansion | Depth, critique |
| **Claude** | Depth & critique | Red-team, editorial polish, deep analysis | Code (unless specified) |
| **Cursor Agents** | Structure & organize | Take external research → organize into docs, write code | Research, synthesis, analysis |
| **Lindy AI** | Automation | Outreach, nurture, scheduling, daily briefs | Research, strategy |

**Critical Rule**: Cursor agents do NOT do research. They organize content FROM external AI tools.

---

## Three Operating Modes

### Mode 1: Interactive (Default)
- **When**: Unclear requirements, learning codebase, high-risk changes
- **How**: Real-time collaboration via Cursor Composer
- **Best for**: Exploration, complex decisions

### Mode 2: Ralph Autonomous
- **When**: Well-defined feature, 5-15 atomic stories, clear acceptance criteria
- **How**: Works overnight while you sleep
- **Best for**: Fast shipping, maximizing time
- **Cost**: ~$30-50, 2-8 hours

### Mode 3: Discovery Pack (Parallel)
- **When**: Validating new product ideas
- **How**: Multiple agents run concurrently
- **Best for**: Opportunity validation, market research

---

## Mandatory Gates

| Gate | Threshold | Required Before |
|------|-----------|-----------------|
| **Discovery Score** | ≥ 8.0/10 | Validation |
| **Validation Thresholds** | Must pass | Build |
| **Brand System Doc** | Must exist | Product handoff |
| **Dev Quality Plan** | Must exist | Implementation |

---

## Required Discovery Outputs (per idea)

1. **NICHE-INTEL-{slug}.md** - Niche size, psychographics, subcultures
2. **PAIN-SIGNALS-{slug}.md** - Pain clusters, MAAP analysis
3. **JTBD-{slug}.md** - Persona narrative, main/related/emotional jobs
4. **OPPORTUNITY-{slug}.md** - Winner-take-most dynamics, moat potential (must have Opportunity Score ≥ 8.0)
5. **MANUS-{slug}.md** - Source-of-truth narrative pack
6. **CHATGPT-REFINEMENT-{slug}.md** - Refinement/variants pack
7. **REDTEAM-{slug}.md** - Optional but recommended

**Command**: `npm run discovery:evidence -- <idea-slug>`

---

## Required Validation Outputs (per idea)

1. **VALIDATION-PLAN-{slug}.md** - Tests + thresholds
2. **LANDING-{slug}.md** - Landing page strategy
3. **Semantic landing package** - index.html + styles.css
4. **DISTRIBUTION-{slug}.md** - Channel maps
5. **CONTENTOPS-{slug}.md** - Approval gates + audit trail
6. **PRICING-TEST-{slug}.md** - WTP experiments
7. **CREATIVE-BATCH-{slug}.md** - Glif batching
8. **RESULTS-{slug}.md** - Daily log
9. **LINDY SPECS** - Automation specs

---

## Required Build Outputs (per feature)

1. **PRD-{slug}.md** - Product requirements
2. **ADR-{slug}.md** - Architecture decision record
3. **PostHog plan** - Events/funnel/flags
4. **Supabase plan** - Data model/RLS/edge functions
5. **Clerk plan** - Auth/onboarding
6. **Test plan** - Coverage + acceptance criteria
7. **DEV-QUALITY-{slug}.md** - Lint/test/deploy checklist
8. **COPY-{slug}.md** - UX writing, microcopy, CTAs
9. **MICRO-INTERACTIONS-{slug}.md** - Interaction design
10. **Implementation + a11y audit** - Code + WCAG 2.2 AA audit
11. **Sophisticated visual design** - Multi-layer depth, custom icons, gradients
12. **Personalization design** - Greetings, recommendations, customization
13. **Gamification elements** - Rewards, progress, habit loops
14. **Content quality audit** - Readability, IA, conversion

---

## Key Agent Pods

### Strategy & Portfolio
- **Portfolio Prioritizer** - Score ideas, kill/greenlight meetings
- **Insight & Narrative Strategist** - Unfair insight + narrative briefs
- **Product Strategist** - Insights → PRDs + monetization wedges
- **Moat & MRR Strategist** - Defensibility + expansion revenue
- **Retention Architect** - Activation loops, notification hooks

### Discovery & Validation
- **Niche Intelligence Agent** - Build NICHE-INTEL docs
- **Pain Signal Agent** - Score pains + MAAP
- **JTBD Agent** - Persona narratives + JTBD
- **Opportunity & Moat Agent** - Opportunity score + moat thesis
- **Demand Validator** - Validation plans + dashboards
- **Landing Builder** - Landing copy/assets
- **Distribution Operator** - Channel maps + Lindy specs
- **ContentOps Editor** - Editorial quality + approvals
- **Pricing Tester** - Pricing experiments

### Execution & QA
- **Engineering Architect** - ADRs, schemas, platform decisions
- **Implementer** - Ship small diffs in /src/features
- **Ralph Agent** - Autonomous overnight feature building
- **Test Engineer** - Test plans + suites
- **Dev Quality Assistant** - Pre-code test plans + checklists
- **Accessibility Agent** - WCAG 2.2 AA audits
- **UI Design System Agent** - Component patterns, micro-interactions
- **Content Strategist** - IA, navigation, content structure
- **UX Writer** - Microcopy, interface copy, CTAs

---

## Prioritization Criteria

Favor ideas with:

| Criteria | Why |
|----------|-----|
| **High urgency** | Must be solved now, not later |
| **High willingness-to-pay** | Clear budgeted buyers with authority |
| **Recurring jobs** | Daily/weekly frequency, not one-time |
| **Data moat potential** | Build proprietary data advantages |
| **Workflow embedding** | Deep integration into daily operations |

**Principle**: Boring, inevitable pain > novel "nice-to-have" ideas

---

## Tech Stack

- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript (strict mode)
- **Database**: Drizzle ORM + PostgreSQL (Supabase)
- **API**: tRPC
- **Auth**: Clerk (orgs, roles, onboarding)
- **Analytics**: PostHog (events, funnels, flags)
- **Payments**: Stripe
- **Deploy**: Vercel
- **Testing**: Vitest, Playwright

---

## Key Commands

```bash
# New idea
npm run add-idea "Project Name" "Description"

# AI preliminary score (30-60 seconds)
npm run score-idea "project-slug"

# Auto-continue if score ≥25
npm run idea:continue -- <idea-slug>

# Generate discovery evidence (Manus + ChatGPT)
npm run discovery:evidence -- <idea-slug>

# Create new project
npm run create-project "My Awesome SaaS"

# Manage portfolio
npm run manage-projects list
npm run manage-projects status <project-slug>
```

---

## Operating Principles

1. **Boring, evolutionary code** - Simple, maintainable solutions
2. **Tests define correctness** - Block shipping when missing
3. **Small, verifiable diffs** - Incremental changes with clear intent
4. **Strong typing** - TypeScript strict + Zod at boundaries
5. **Domain-driven structure** - Features are self-contained modules
6. **WCAG 2.2 AA baseline** - Accessibility is non-negotiable

---

## When to Use This System

This system is designed for:
- ✅ Validating new SaaS product ideas
- ✅ Building features with clear requirements
- ✅ Scaling validated products systematically

This system is NOT designed for:
- ❌ Quick hacks or prototypes
- ❌ Non-SaaS products
- ❌ Ideas you want to build "just to learn"

---

**Last updated**: February 7, 2026

**Source**: https://github.com/winzenburg/SaaS-Starter
