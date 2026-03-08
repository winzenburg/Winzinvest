# Core Skills Guide for Your Moltbot Setup

This guide provides a curated list of community skills that align with your Hedgehog Profile and complement your four projects: Swing Trading, Cultivate, Design System, and Kinlet.

---

## Quick Installation Reference

All skills can be installed using the ClawdHub CLI:

```bash
npx clawdhub@latest install <skill-slug>
```

Or manually by copying the skill folder to `~/.openclaw/skills/` (global) or `<project>/skills/` (workspace).

---

## Tier 1: Essential Skills (Install First)

These skills provide foundational capabilities that will benefit all your projects and daily workflows.

| Skill | Slug | Why You Need It |
|-------|------|-----------------|
| **GitHub** | `github` | Core integration for all your projects. Interact with GitHub using the `gh` CLI for PRs, issues, and repo management. Essential for Cultivate, Kinlet, and Design System development. |
| **Slack** | `slack` | Your secondary communication channel. Control Slack from Moltbot for professional notifications and GitHub integration. |
| **Cursor Agent** | `cursor-agent` | Comprehensive skill for using the Cursor CLI agent. Since Cursor is your main AI hub, this creates a powerful bridge between Moltbot and your development environment. |
| **Conventional Commits** | `conventional-commits` | Format commit messages using the Conventional Commits specification. Keeps your commit history clean and meaningful across all projects. |
| **GitHub PR** | `github-pr` | Fetch, preview, merge, and test GitHub PRs locally. Essential for the overnight autonomous coding workflow. |

### Installation Commands - Tier 1

```bash
npx clawdhub@latest install github
npx clawdhub@latest install slack
npx clawdhub@latest install cursor-agent
npx clawdhub@latest install conventional-commits
npx clawdhub@latest install github-pr
```

---

## Tier 2: High-Value Skills by Project

### For Swing Trading

| Skill | Slug | Description |
|-------|------|-------------|
| **TradingView Analysis** | Custom/Browser-based | Logs into TradingView via browser automation, screenshots charts, and performs technical analysis. This aligns perfectly with your existing TradingView workflow. |
| **Finance Skills** | Various | Search ClawdHub for finance-related skills: `npx clawdhub@latest search finance` |

**Note:** The TradingView skill showcased by @bheem1798 uses browser automation rather than an API. You may want to create a custom skill that integrates with your specific Pine Script indicators and screeners.

### For Design System Work

| Skill | Slug | Description |
|-------|------|-------------|
| **UI Audit** | `ui-audit` | AI skill for automated UI audits. Evaluate interfaces against proven UX principles. Perfect for maintaining design system quality. |
| **UX Audit** | `ux-audit` | AI skill for automated design audits. Complements UI Audit with a focus on user experience. |
| **UX Decisions** | `ux-decisions` | AI skill for the Making UX Decisions framework. Helps structure design decisions systematically. |
| **Vercel React Best Practices** | `vercel-react-best-practices` | React and Next.js performance optimization guidelines from Vercel Engineering. Essential for your Next.js-based projects. |
| **Frontend Design** | `frontend-design` | Create distinctive, production-grade frontend interfaces with high design quality. |

### For Cultivate & Kinlet (SaaS Development)

| Skill | Slug | Description |
|-------|------|-------------|
| **Deploy Agent** | `deploy-agent` | Multi-step deployment agent for full-stack apps. Automates your Vercel deployment workflow. |
| **PR Commit Workflow** | `pr-commit-workflow` | Structured workflow for creating commits and pull requests. Ensures consistency. |
| **Coding Agent** | `coding-agent` | Run Codex CLI, Claude Code, OpenCode, or Pi Coding Agent. Enables multi-agent coding orchestration. |
| **Todoist** | `todoist` | Automated task management via Telegram. Keep track of sprint tasks and priorities. |

### Installation Commands - Tier 2

```bash
# Design System
npx clawdhub@latest install ui-audit
npx clawdhub@latest install ux-audit
npx clawdhub@latest install ux-decisions
npx clawdhub@latest install vercel-react-best-practices
npx clawdhub@latest install frontend-design

# SaaS Development
npx clawdhub@latest install deploy-agent
npx clawdhub@latest install pr-commit-workflow
npx clawdhub@latest install coding-agent
npx clawdhub@latest install todoist
```

---

## Tier 3: Productivity & Knowledge Management

These skills enhance your overall productivity and align with your Hedgehog concept of building frameworks that reduce uncertainty.

| Skill | Slug | Description |
|-------|------|-------------|
| **Prompt Log** | `prompt-log` | Extract conversation transcripts from AI coding session logs (Clawdbot, Claude Code, Codex). Great for building your second brain. |
| **Read GitHub** | `read-github` | Read GitHub repos via gitmcp.io with semantic search and LLM-optimized output. Research competitor codebases efficiently. |
| **DeepWiki** | `deepwiki` | Query the DeepWiki MCP server for GitHub repository documentation and wiki structure. |
| **Linear CLI** | `linearis` | Linear.app CLI for issue tracking. If you use Linear for project management. |
| **CalDAV Calendar** | `caldav-calendar` | Self-hosted calendar integration for scheduling. |
| **OpenRouter Transcription** | `openrouter-transcription` | Multi-lingual audio transcription. Process voice notes from your Telegram workflow. |

### Installation Commands - Tier 3

```bash
npx clawdhub@latest install prompt-log
npx clawdhub@latest install read-github
npx clawdhub@latest install deepwiki
npx clawdhub@latest install linearis
npx clawdhub@latest install openrouter-transcription
```

---

## Tier 4: Infrastructure & Automation

These skills are useful if you want to extend Moltbot's capabilities to home automation or advanced infrastructure management.

| Skill | Slug | Description |
|-------|------|-------------|
| **Home Assistant** | `home-assistant` | Control and automate Home Assistant devices via natural language. |
| **Cloudflare** | `cloudflare` | Manage Cloudflare Workers, KV, D1, R2, and secrets using the Wrangler CLI. |
| **Beeper CLI** | `beeper-cli` | Read, send, and archive messages via Beeper Desktop. Manage all your chats in one place. |

---

## Skills to Create Custom

Based on your unique needs, consider creating custom skills for:

1. **Swing Trading Skill** (Enhanced)
   - Integrate with your specific Pine Script indicators
   - Connect to your TradingView screener criteria
   - Automate morning market briefs with your watchlist

2. **Kinlet Caregiver Research Skill**
   - Monitor caregiver forums and communities
   - Track Alzheimer's research publications
   - Aggregate user feedback patterns

3. **Design System Changelog Skill**
   - Auto-generate changelogs from commits
   - Track component usage across projects
   - Monitor accessibility compliance

---

## Recommended Installation Order

For a clean setup, install skills in this order:

### Phase 1: Foundation (Day 1)
```bash
npx clawdhub@latest install github
npx clawdhub@latest install github-pr
npx clawdhub@latest install conventional-commits
npx clawdhub@latest install slack
```

### Phase 2: Development Workflow (Day 2)
```bash
npx clawdhub@latest install cursor-agent
npx clawdhub@latest install coding-agent
npx clawdhub@latest install pr-commit-workflow
npx clawdhub@latest install deploy-agent
```

### Phase 3: Design & Quality (Day 3)
```bash
npx clawdhub@latest install ui-audit
npx clawdhub@latest install ux-audit
npx clawdhub@latest install vercel-react-best-practices
npx clawdhub@latest install frontend-design
```

### Phase 4: Productivity (Day 4+)
```bash
npx clawdhub@latest install todoist
npx clawdhub@latest install prompt-log
npx clawdhub@latest install read-github
npx clawdhub@latest install openrouter-transcription
```

---

## Verifying Installed Skills

After installation, verify your skills are loaded:

```bash
# List all installed skills
openclaw skills list

# Check skill status
openclaw skills status

# Test a specific skill
openclaw skills test <skill-slug>
```

---

## Security Considerations

When installing community skills, keep these best practices in mind:

| Consideration | Action |
|---------------|--------|
| **Review before install** | Check the skill's source code on GitHub before installing |
| **Use trusted sources** | Prefer skills from ClawdHub or well-known community members |
| **Sandbox sensitive operations** | Enable sandboxing for skills that access sensitive data |
| **Monitor API usage** | Track which skills are consuming API calls |
| **Regular updates** | Keep skills updated for security patches |

---

## Resources

| Resource | URL |
|----------|-----|
| Awesome OpenClaw Skills | https://github.com/VoltAgent/awesome-openclaw-skills |
| OpenClaw Showcase | https://docs.openclaw.ai/start/showcase |
| ClawdHub Registry | Use `npx clawdhub@latest search <term>` |
| OpenClaw Discord | #showcase channel for community projects |

---

## Summary

Your core skill stack should include:

1. **GitHub + GitHub PR** - Version control and code review
2. **Slack** - Professional communication
3. **Cursor Agent** - IDE integration
4. **Conventional Commits + PR Commit Workflow** - Code quality
5. **UI/UX Audit** - Design system quality
6. **Vercel React Best Practices** - Performance optimization
7. **Coding Agent** - Multi-agent development
8. **Todoist** - Task management

This combination creates a powerful, integrated workflow that supports your Hedgehog concept: **building AI-powered frameworks that turn complex, high-stakes uncertainty into clear, actionable decisions at scale.**
