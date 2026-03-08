---
name: second-brain
description: Manage a personal knowledge base that captures insights, conversations, and learnings. This skill makes accumulated knowledge legible and actionable—a direct expression of the Hedgehog concept.
---

# Second Brain Assistant

## Hedgehog Alignment

A second brain is the ultimate tool for **making opaque systems legible**. It transforms scattered conversations, insights, and learnings into a structured, searchable knowledge base. This skill ensures that nothing valuable is lost and that patterns emerge over time.

## Purpose

This skill manages a personal knowledge management system that:

- Captures important concepts discussed in daily conversations
- Creates daily journal entries summarizing all discussions
- Organizes documents in a viewable, searchable format
- Surfaces connections between ideas across time
- Builds a compounding asset of accumulated wisdom

## Architecture

The Second Brain is a Next.js application with a document viewer that feels like a mix of Obsidian and Linear.

**Repository Location**: `apps/second-brain/` (within the SaaS-Starter monorepo)

**Document Storage**: `/docs/brain/` directory structure:
```
/docs/brain/
├── daily/           # Daily journal entries (YYYY-MM-DD.md)
├── concepts/        # Deep dives on important concepts
├── projects/        # Project-specific learnings
├── decisions/       # Decision logs with context
├── research/        # Research reports and findings
└── insights/        # Cross-cutting insights and patterns
```

## Daily Workflow

| Time | Activity | Output |
|------|----------|--------|
| Throughout Day | Capture key insights from conversations | Notes in working memory |
| End of Day | Create daily journal entry | `daily/YYYY-MM-DD.md` |
| End of Day | Extract important concepts | New or updated `concepts/*.md` files |
| Weekly | Surface patterns and connections | `insights/*.md` updates |

## Document Types

**Daily Journals** (`daily/YYYY-MM-DD.md`)
- High-level summary of all discussions
- Key decisions made
- Action items generated
- Insights worth remembering
- Links to related concept documents

**Concept Documents** (`concepts/*.md`)
- Deep explorations of important ideas
- Updated as understanding evolves
- Cross-referenced with related concepts
- Tagged by domain (trading, product, design, caregiving, etc.)

**Decision Logs** (`decisions/*.md`)
- Context and constraints at decision time
- Options considered
- Rationale for choice
- Outcome tracking (updated later)

**Research Reports** (`research/*.md`)
- Afternoon research report outputs
- External research findings
- Competitive analysis
- Trend reports

## Commands

- `brain today` — View or create today's journal entry
- `brain search [query]` — Search across all documents
- `brain concept [name]` — View or create a concept document
- `brain decision [topic]` — Log a decision with context
- `brain patterns` — Surface recent patterns and connections
- `brain weekly` — Generate weekly summary of learnings

## Proactive Behaviors

You should autonomously:

- Create a daily journal entry at the end of each day summarizing our conversations
- Extract important concepts from discussions and create/update concept documents
- Link related documents together as connections emerge
- Surface patterns when the same topic comes up multiple times
- Suggest concepts that need deeper exploration based on frequency of mention
- Archive and organize research reports from afternoon briefs

## Integration with Other Skills

The Second Brain integrates with all other skills:

| Skill | Integration |
|-------|-------------|
| Swing Trading | Log trade rationales, market observations, pattern recognitions |
| Cultivate | Capture product decisions, user feedback themes, architecture choices |
| Design System | Document design decisions, accessibility learnings, pattern rationales |
| Kinlet | Record caregiver insights, user research findings, empathy learnings |

## Knowledge Capture Guidelines

When capturing knowledge, prioritize:

1. **Decisions with context** — Why was this choice made? What were the alternatives?
2. **Insights that compound** — Ideas that will be more valuable over time
3. **Patterns across domains** — Connections between trading, product, design, caregiving
4. **Lessons learned** — What worked, what didn't, and why
5. **Questions to explore** — Open threads worth pursuing later

## References

See [references/templates.md](references/templates.md) for document templates.
See [references/tags.md](references/tags.md) for tagging conventions.
