# OpenClaw Configuration Changelog

This document tracks all updates made to your Moltbot/OpenClaw configuration files.

---

## v3.0 — February 7, 2026 (OpenClaw v2026.2.6 Update)

This is a major update driven by the release of OpenClaw v2026.2.6, significant security advisories, and new community research. Every configuration file has been updated.

### Critical Security Updates

The OpenClaw ecosystem experienced a wave of security incidents in late January and early February 2026. These updates address the most urgent findings.

| Threat | Severity | Status in Your Config |
|--------|----------|----------------------|
| CVE-2026-25253 (WebSocket origin bypass, RCE) | CVSS 8.8 | Mitigated by updating to v2026.2.6 |
| 42,665 publicly exposed instances | Critical | Gateway bound to `127.0.0.1` with token auth |
| 341 malicious ClawHub skills | High | Code safety scanner enabled; weekly audit scheduled |
| 7.1% of skills mishandle secrets (Snyk) | High | Credential redaction enabled; env vars enforced |
| Moltbook breach (1.5M tokens, 35K emails) | High | Moltbook security warnings added to SOUL.md and IDENTITY.md |
| Indirect prompt injection via trusted integrations (Zenity) | Medium | Prompt injection guardrail added to SOUL.md |

### Model Updates (`moltbot.json`, `SOUL.md`)

OpenClaw v2026.2.6 introduces support for three new models with forward-compatibility fallbacks.

| Model | Provider | Recommended Use |
|-------|----------|-----------------|
| **Claude Opus 4.6** | Anthropic | Complex reasoning, strategy, architecture (upgraded from 4.5) |
| **GPT-5.3-Codex** | OpenAI | Coding assistance (replaces generic Codex CLI for code routing) |
| **xAI Grok** | xAI | Fallback and alternative perspective (new provider) |

The `piMono` dependency has been bumped to `0.52.7` for Opus 4.6 compatibility.

### New Features Enabled (`moltbot.json`)

| Feature | Description | Configuration Key |
|---------|-------------|-------------------|
| **Voyage AI Memory** | Native vector memory support replaces experimental session memory | `memory.provider: "voyage-ai"` |
| **Web UI Token Dashboard** | Visual dashboard for monitoring token consumption by model | `webUI.tokenDashboard.enabled: true` |
| **Session History Caps** | Prevents context overflow by capping session payloads | `sessions.historyPayloadCap.enabled: true` |
| **Code Safety Scanner** | Scans skills for malicious code on install | `skills.safety.scanner.enabled: true` |
| **Credential Redaction** | Redacts secrets from config.get gateway responses | `security.credentialRedaction.enabled: true` |
| **Compaction Retries** | Multiple retry attempts on context overflow | `compaction.retries.enabled: true` |
| **Telegram Thread Auto-Inject** | DM topic threadIds auto-injected | `channels.telegram.autoInjectThreadId: true` |
| **Slack Mention Stripping** | Strips mentions in /new and /reset commands | `channels.slack.stripMentions: true` |

### New Cron Jobs (`moltbot.json`)

| Job | Schedule | Purpose |
|-----|----------|---------|
| `security-audit` | Sundays 3:00 AM | Weekly security self-check across all dimensions |
| `token-usage-review` | Fridays 8:00 PM | Weekly token usage analysis and optimization recommendations |

### File-by-File Changes

**`moltbot.json`**: Added `version` field, updated primary model to Opus 4.6, added GPT-5.3-Codex and Grok to multi-model routing, added Voyage AI memory config, enabled session history caps, enabled code safety scanner, enabled credential redaction, added gateway auth token, added canvas and A2UI auth requirements, added compaction retries, added Telegram thread auto-inject, added Slack mention stripping, added web UI token dashboard, added two new cron jobs (security-audit, token-usage-review), updated best practices with security-first guidance.

**`SOUL.md`**: Updated security guardrails with current threat statistics (341 malicious skills, 42,665 exposed instances, Moltbook breach), added prompt injection prohibition, added config exposure prohibition, added Moltbook breach warning, updated multi-model strategy table for v2026.2.6 models, added weekly security audit directive, strengthened safe interaction patterns for Moltbook.

**`IDENTITY.md`**: Added security alert tone calibration, added v2026.2.6 platform notes for Telegram and Slack, added Moltbook security posture section, added security event triggers to context-aware proactivity, added security concern interaction pattern, updated boundaries with anti-prompt-injection rules.

**`HEARTBEAT.md`**: Added security quick scan (every other heartbeat), added critical alert tier for security events, added rule against executing external code during heartbeat.

**`USER.md`**: No changes needed (user profile remains current).

**`CHANGELOG.md`**: This file (new).

---

## v2.0 — February 6, 2026 (Hedgehog + Video Integration)

Integrated the user's Hedgehog Profile as the central operating principle and incorporated recommendations from Alex Finn's videos.

### Key Changes
- Rewrote SOUL.md with Hedgehog Profile as core directive
- Created IDENTITY.md for presentation and communication style
- Created USER.md for user profile and preferences
- Created HEARTBEAT.md for periodic monitoring
- Created second-brain skill for knowledge management
- Created moltbook skill for agent social networking
- Created market-research skill based on ChatPRD workflows
- Added proactive coder mandate
- Added daily rhythms (morning brief, afternoon research, overnight work)
- Added multi-model strategy
- Added security guardrails

---

## v1.0 — February 5, 2026 (Initial Setup)

Initial Moltbot configuration for four projects: Swing Trading, Cultivate, Design System, and Kinlet.

### Files Created
- SOUL.md (basic)
- moltbot.json (basic)
- swing-trading/SKILL.md
- cultivate/SKILL.md
- design-system/SKILL.md
- kinlet/SKILL.md
