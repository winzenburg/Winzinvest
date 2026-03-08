# Autonomous Councils - Complete Guide

Your two nightly councils are now running. They analyze your business and security posture every night, then deliver comprehensive briefings by 7:00 AM.

## 📊 Council 1: Business Council

**Schedule:** 11:00 PM Mountain Time (nightly)

### What It Does

The Business Council analyzes your business metrics and delivers strategic recommendations:

**Data Collection:**
1. **GitHub Activity**
   - List all repos with updates from last 7 days
   - Count open issues across all repos
   - Track fork/star activity

2. **Task Completion**
   - Completed tasks: Count items in `tasks/done/`
   - Backlog items: Count items in `tasks/backlog/`
   - Completion rate: `done / (done + backlog) * 100%`
   - Trend: Strong (>60%), Steady (40-60%), Needs Attention (<40%)

3. **Active Projects**
   - Scans for folders: kinlet, cultivate, design-system, swing-trading, content, knowledge
   - Counts files in each project
   - Reports status

4. **Strategic Analysis**
   - Identifies top 3 recommendations
   - Flags urgent items

### Sample Report

```
📊 BUSINESS COUNCIL REPORT

Date: 2026-02-22

Strategic Recommendations:
1. ✅ Task completion at 65% - maintain momentum
2. GitHub activity healthy (4 repos active)
3. 6 projects active - portfolio diversified

Key Metrics:
• Task Completion: 65% 📈 Strong
• GitHub Activity: 4 repos active
• Open Issues: 8
• Active Projects: 6

Urgent Items:
✅ None

Council Status: ✅ All systems analyzed
```

### Recommendations Logic

| Metric | Good | Fair | Poor |
|--------|------|------|------|
| Task Completion | >60% | 40-60% | <40% |
| Active Repos | >3 | 1-3 | 0 |
| Open Issues | <10 | 10-20 | >20 |
| Project Count | >4 | 2-4 | <2 |

---

## 🔐 Council 2: Security Council

**Schedule:** 11:30 PM Mountain Time (nightly)

### What It Does

The Security Council performs comprehensive security scans:

**Security Checks:**

1. **Hardcoded Secrets**
   - Scans `.env`, `.env.local`, `config.js`, `config.json`, `secrets.json`, `credentials.json`
   - Detects API keys, passwords, tokens, private keys
   - Severity: CRITICAL

2. **Vulnerable Dependencies**
   - Scans `package.json` for known-vulnerable npm packages
   - Scans `requirements.txt` for known-vulnerable Python packages
   - Checks versions against security databases
   - Severity: HIGH

3. **Webhook Security**
   - Verifies webhook files have authentication
   - Checks for HTTPS vs HTTP
   - Verifies WEBHOOK_SECRET environment variable
   - Severity: HIGH

4. **Session History Patterns** (when available)
   - Detects suspicious command patterns
   - Alerts on potential security issues

### Sample Report

```
🔐 SECURITY COUNCIL REPORT

Date: 2026-02-22

Status: 🟢 SECURE

Issues Found:
🔴 Critical: 0
🟠 High: 0
🟡 Medium: 0
🟢 Low: 0

Top Issues:
✅ None detected

Recommended Actions:
✅ All security checks passed

Last Scan: 11:32 PM
```

### Status Levels

| Status | Issues | Action |
|--------|--------|--------|
| 🟢 SECURE | None or low-severity only | Monitor |
| 🟡 CAUTION | High issues (1-2) or medium issues (>2) | Review recommended |
| 🟠 AT RISK | High issues (>2) | Action required |
| 🔴 CRITICAL | Critical issues found | Immediate action required |

---

## 📬 How You'll Receive Reports

Both councils deliver reports via **Telegram** by 7:00 AM:

**Timeline:**
- 11:00 PM: Business Council runs
- 11:30 PM: Security Council runs
- 6:00-7:00 AM: Both reports arrive in Telegram

**Format:**
- Markdown-formatted for readability
- Emoji status indicators
- Actionable recommendations
- Summary metrics

---

## 🔧 Managing the Councils

### Check Status

```bash
# List both councils
launchctl list | grep council

# Output should show:
# -	0	ai.openclaw.council-business
# -	0	ai.openclaw.council-security
```

### Check Logs

```bash
# Business Council logs
tail -f ~/.openclaw/workspace/logs/council-business.log

# Security Council logs
tail -f ~/.openclaw/workspace/logs/council-security.log

# Check for errors
tail -f ~/.openclaw/workspace/logs/council-business.err.log
tail -f ~/.openclaw/workspace/logs/council-security.err.log
```

### Reload a Council

If a council needs to be restarted:

```bash
# Reload Business Council
launchctl unload ~/Library/LaunchAgents/ai.openclaw.council-business.plist
launchctl load ~/Library/LaunchAgents/ai.openclaw.council-business.plist

# Reload Security Council
launchctl unload ~/Library/LaunchAgents/ai.openclaw.council-security.plist
launchctl load ~/Library/LaunchAgents/ai.openclaw.council-security.plist

# Or reload both
launchctl unload ~/Library/LaunchAgents/ai.openclaw.council-*.plist
launchctl load ~/Library/LaunchAgents/ai.openclaw.council-*.plist
```

### Disable a Council

```bash
# Disable Business Council temporarily
launchctl unload ~/Library/LaunchAgents/ai.openclaw.council-business.plist

# Disable Security Council temporarily
launchctl unload ~/Library/LaunchAgents/ai.openclaw.council-security.plist
```

### Run a Council Manually

Test a council immediately without waiting for the scheduled time:

```bash
# Run Business Council now
node ~/.openclaw/workspace/scripts/council-business.mjs

# Run Security Council now
node ~/.openclaw/workspace/scripts/council-security.mjs
```

---

## 🎯 What The Councils Monitor

### Business Council Monitors

- **Code Health:**
  - Are your repos being actively maintained?
  - How many open issues need attention?
  - Any stale repositories?

- **Productivity:**
  - Task completion rate trending up or down?
  - How much backlog is waiting?
  - Are you shipping at the right pace?

- **Portfolio Health:**
  - How many projects are active?
  - Are you too scattered or too focused?

- **Strategic Alerts:**
  - If completion <30%: "Prioritize backlog"
  - If issues >10: "Triage open issues"
  - If repos inactive: "Update stale repos"

### Security Council Monitors

- **Credential Exposure:**
  - Any hardcoded API keys, passwords, tokens?
  - Are secrets in version control?

- **Dependency Risk:**
  - Outdated packages with CVEs?
  - Known-vulnerable npm or Python packages?

- **Endpoint Security:**
  - Webhooks properly authenticated?
  - Using HTTPS everywhere?
  - Secrets properly configured?

- **Session Safety:**
  - Suspicious command patterns?
  - Risky operations logged?

---

## 📈 Using Council Reports

### Business Council Actions

**If completion rate is high (>60%):**
- ✅ Maintain current pace
- Consider taking on one additional project

**If completion rate is low (<40%):**
- ⚠️ Pause new work
- Focus on clearing backlog
- Break large tasks into smaller ones

**If repos are inactive:**
- 📌 Archive unused repos
- Or: Schedule time to update them
- Consider consolidating similar work

**If issues are piling up (>10):**
- 🔴 Triage this week
- Label by priority
- Assign or close non-critical issues

### Security Council Actions

**If critical issues found:**
- 🚨 Fix immediately
- Don't commit more code until resolved
- Verify fix didn't introduce new issues

**If high-severity issues found:**
- ⚠️ Fix within 24-48 hours
- May want to disable affected service
- Test fix thoroughly

**If medium-severity issues found:**
- 📌 Plan fix for next sprint
- Monitor affected system
- Document workaround if needed

**If all green:**
- ✅ Keep doing what you're doing
- Maintain current security practices

---

## 💡 Tips for Best Results

### For Business Council

1. **Keep GitHub updated:**
   - Push commits regularly
   - Close completed PRs
   - Triage open issues weekly

2. **Maintain the task system:**
   - Move tasks through backlog → in-progress → done
   - The council reads from these folders

3. **Review recommendations:**
   - Each morning report has 3 specific recommendations
   - Act on at least one per week

### For Security Council

1. **Use environment variables:**
   - Set WEBHOOK_SECRET in .env
   - Never hardcode credentials

2. **Keep dependencies updated:**
   - Run `npm audit` or `pip check` weekly
   - Update vulnerable packages ASAP

3. **Secure webhook endpoints:**
   - Always verify incoming requests
   - Use HTTPS only
   - Log all webhook activity

---

## 📊 Files & Configuration

| File | Purpose |
|------|---------|
| `scripts/council-business.mjs` | Business analysis script |
| `scripts/council-security.mjs` | Security scanning script |
| `~/Library/LaunchAgents/ai.openclaw.council-business.plist` | Business Council scheduler |
| `~/Library/LaunchAgents/ai.openclaw.council-security.plist` | Security Council scheduler |
| `logs/council-business.log` | Business Council logs |
| `logs/council-security.log` | Security Council logs |
| `COUNCILS_GUIDE.md` | This file |

---

## 🚀 Next Steps

The councils are now running and will deliver briefings every morning. You'll start seeing:

**Tomorrow at ~7:00 AM:**
- Business Council Report (task completion, GitHub activity, strategic recommendations)
- Security Council Report (security status, any issues found)

Monitor the logs if you want to see what they're finding:
```bash
tail -f ~/.openclaw/workspace/logs/council-*.log
```

---

**Your autonomous councils are live. Every morning you'll wake up to a briefing of what your systems are telling you about your business and security posture.** 🎯🔐
