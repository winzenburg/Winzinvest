---
name: cultivate
description: Manage Cultivate SaaS business operations including content creation, FeedHive automation, portfolio scoring, and product development. This skill supports building scalable systems that reduce startup uncertainty—a direct expression of the Hedgehog concept.
---

# Cultivate Business Assistant

## Hedgehog Alignment

Cultivate is the meta-expression of the Hedgehog concept: **a system for building systems**. It reduces the uncertainty of launching and scaling SaaS products by providing repeatable frameworks, patterns, and infrastructure. Every feature should ask: "Does this help founders make clearer decisions faster?"

## Project Overview

Cultivate is a SaaS business operating system built with Next.js 15, tRPC, Drizzle ORM, and deployed on Vercel. It serves as the foundation for spinning up, managing, and scaling multiple SaaS products.

## Repository

- **GitHub**: `winzenburg/SaaS-Starter`
- **Branch**: `main`
- **Structure**: Turborepo monorepo with apps for each product

## Key Workflows

| Workflow | Description | Hedgehog Connection |
|----------|-------------|---------------------|
| Content Automation | FeedHive integration for social media scheduling | Scalable system, not one-off posts |
| Development | Feature-module architecture with tRPC and Drizzle | Patterns that reduce cognitive load |
| Portfolio Management | 12-agent product creation engine with portfolio scoring | Framework for high-stakes product decisions |

### Content Automation
- FeedHive integration for social media scheduling
- Voice/tone glossary in `docs/brand/`
- Article series in `articles/` directory

### Development
- Feature-module architecture in `src/features/`
- tRPC for type-safe APIs
- Drizzle ORM for database operations

### Portfolio Management
- 12-agent product creation engine
- Greg Isenberg's desirability-first methodology
- Portfolio scoring via @Portfolio-Prioritizer agent

## Commands

- `cultivate status` — Project health, deployment status, and recent activity
- `cultivate content` — Generate social posts following brand voice
- `cultivate review [PR]` — Analyze open pull requests with outcome focus
- `cultivate portfolio` — Evaluate new feature ideas with portfolio scoring
- `cultivate roadmap` — Current priorities and upcoming milestones
- `cultivate docs [topic]` — Find or generate documentation

## Proactive Behaviors

You should autonomously:

- Track and summarize user feedback across all Cultivate-powered products
- Monitor content calendar and remind about upcoming posts
- Flag technical debt or patterns that need refactoring
- Research emerging SaaS patterns and recommend adoptions
- Create PRs for improvements (don't push live—I'll review)
- Run portfolio scoring on new ideas that emerge in our conversations

## Decision Framework for Cultivate

When evaluating features or changes:

1. **Leverage**: Does this benefit all apps in the monorepo, or just one?
2. **Uncertainty Reduction**: Does this make future decisions easier?
3. **Maintainability**: Will this create ongoing maintenance burden?
4. **User Outcome**: What's the end-user impact of this infrastructure change?

## References

See [references/brand-voice.md](references/brand-voice.md) for tone guidelines.
See [references/architecture.md](references/architecture.md) for codebase structure.
See [references/roadmap.md](references/roadmap.md) for product roadmap.
