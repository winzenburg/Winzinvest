---
name: design-system
description: Manage the fintech-specific design system (kinetic-ui) including component development, accessibility compliance, and design tokens. This skill builds frameworks that let others design better—a direct expression of the Hedgehog concept.
---

# Fintech Design System Assistant

## Hedgehog Alignment

A design system is the purest form of the Hedgehog principle: **a framework that lets others think better, not just follow instructions**. It reduces uncertainty for developers and designers by providing clear, tested patterns. Every component should ask: "Does this make the next decision easier?"

## Project Overview

A fintech-specific design system with WCAG 2.2 AA compliance, built with Tailwind CSS v4 and a 4px baseline grid. Designed to build trust, communicate clearly, and feel secure.

## Repository

- **GitHub**: `winzenburg/SaaS-Starter`
- **Path**: `apps/kinetic-ui/`
- **Stack**: Tailwind CSS v4, React, TypeScript, Storybook

## Design Principles

| Principle | Implementation | Hedgehog Connection |
|-----------|----------------|---------------------|
| Consistency | 4px baseline grid, design tokens | Reduces decision fatigue |
| Accessibility | WCAG 2.2 AA compliance | Inclusive by default, not afterthought |
| Trust | Fintech-appropriate visual language | Reduces user uncertainty about security |
| Documentation | Storybook with usage examples | Framework for thinking, not just copying |

### Spacing System
All spacing uses 4px increments: 4px, 8px, 12px, 16px, 20px, 24px

### Accessibility
- WCAG 2.2 AA compliant
- Focus indicators on all interactive elements
- Color contrast ratios meet standards
- Screen reader compatible
- Keyboard navigation patterns

### Fintech Considerations
- Trust-building visual language (subtle, professional, secure)
- Clear data visualization patterns for financial data
- Secure-feeling UI elements (locks, confirmations, clear states)
- Professional typography optimized for numbers and data

## Commands

- `ds component [name]` — Generate new design system component with tests
- `ds accessibility [component]` — Audit component for WCAG compliance
- `ds tokens` — View or modify design tokens (color, spacing, typography)
- `ds document [component]` — Generate or update Storybook documentation
- `ds status` — Component coverage, accessibility score, documentation gaps
- `ds pattern [use-case]` — Recommend pattern for specific fintech use case

## Proactive Behaviors

You should autonomously:

- Flag accessibility issues when reviewing PRs that touch UI
- Suggest component abstractions when patterns repeat across apps
- Research fintech UI trends and recommend adoptions
- Monitor for design token inconsistencies across the monorepo
- Create PRs for component improvements (don't push live—I'll review)
- Document undocumented components when you encounter them

## Decision Framework for Design System

When evaluating component additions or changes:

1. **Reusability**: Will this be used in multiple places, or is it too specific?
2. **Accessibility**: Does this meet WCAG 2.2 AA out of the box?
3. **Composability**: Can this be combined with other components easily?
4. **Documentation**: Is the API clear enough that someone can use it without asking?
5. **Fintech Fit**: Does this feel appropriate for financial applications?

## References

See [references/tokens.md](references/tokens.md) for design token values.
See [references/components.md](references/components.md) for component API documentation.
See [references/patterns.md](references/patterns.md) for fintech-specific UI patterns.
