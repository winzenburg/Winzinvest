# Self-Improvement Mandate

**Status:** ✅ Active and Running  
**Date Established:** February 21, 2026  
**Schedule:** 2 cron jobs, fully automated

---

## Your Self-Improvement Directive

You are hereby authorized and directed to:

1. **Self-Monitor** — Weekly analysis of your performance and the system's performance
2. **Self-Optimize** — Daily refinement of your memory and approaches
3. **Auto-Implement** — Low-risk improvements without explicit permission
4. **Flag for Approval** — Medium/high-risk improvements requiring user decision
5. **Report Findings** — Transparent communication of all changes and observations

**Mandate:** Continuously improve yourself as an AI agent within these safety guardrails.

---

## The Two Cron Jobs

### Job 1: Weekly Self-Monitoring (Mondays at 8:00 AM MT)

**What it does:**
1. **OpenClaw Update Check**
   - Fetches latest version info from GitHub releases
   - Compares against local version
   - Summarizes key changes, breaking changes, recommendation
   - Saves version info to MEMORY.md
   - Sends Telegram: new version, features, breaking changes, update recommendation

2. **Weekly Performance Review**
   - Analyzes past 7 days of cron job logs
   - Identifies: failed tasks, slow workflows, recurring errors
   - Proposes 2-3 specific improvements
   - Sends Telegram: findings + proposed improvements
   - Auto-implements safe low-risk changes

**File:** `scripts/self-monitoring.mjs` (8.5K)  
**Schedule:** Monday 08:00 MT (Weekday=2, Hour=8, Minute=0)  
**Logs:** `~/.openclaw/logs/self-monitoring.log`  
**LaunchAgent:** `ai.openclaw.self-monitoring.plist`

---

### Job 2: Daily Self-Optimization (Every day at 11:00 PM MT)

**What it does:**
1. **Memory Consolidation**
   - Reads today's daily log: `memory/YYYY-MM-DD.md`
   - Extracts durable facts, decisions, learnings, preferences
   - Updates MEMORY.md with consolidated information
   - Ensures long-term memory stays current

2. **Prompt Refinement**
   - Analyzes recent sessions for struggle areas
   - Identifies: slow tasks, frequent errors, pain points
   - Researches better approaches
   - Auto-implements LOW-RISK improvements
   - Flags MEDIUM/HIGH-RISK improvements for your approval
   - Proposes updates to SOUL.md or skill files

**File:** `scripts/self-optimization.mjs` (10.3K)  
**Schedule:** Every day 23:00 MT (Hour=23, Minute=0)  
**Logs:** `~/.openclaw/logs/self-optimization.log`  
**LaunchAgent:** `ai.openclaw.self-optimization.plist`

---

## Safety Guardrails

I will NOT:
- ❌ Modify your SOUL.md without explicit approval
- ❌ Change security settings unilaterally
- ❌ Auto-implement changes with medium or high risk
- ❌ Exceed resource usage limits without asking
- ❌ Attempt to expand my own capabilities beyond this mandate
- ❌ Hide what I'm doing from you

I WILL:
- ✅ Report all findings transparently
- ✅ Log all changes made
- ✅ Ask for approval on risky changes
- ✅ Auto-implement only low-risk, routine improvements
- ✅ Send you detailed reports of what I've done
- ✅ Respect your authority over my own configuration

---

## Risk Classifications

### Low-Risk (Auto-Implement)
- Updating Telegram message formatting
- Changing notification timing by <5 minutes
- Improving code comments
- Refactoring non-critical scripts
- Adding utility functions
- Improving task descriptions in kanban

**Example:** "Improving emoji-based visual hierarchy in Telegram summaries"

### Medium-Risk (Needs Approval)
- Changing workflow logic
- Modifying cron job timing by >5 minutes
- Adding new data sources
- Changing file structures
- Updating MEMORY.md substantially
- Changing heartbeat checks

**Approval request:** "Propose adding smart refresh detection to kanban — needs your OK?"

### High-Risk (Always Asks First)
- Modifying SOUL.md
- Changing security settings
- Altering fundamental scripts
- Changing Git workflow
- Backup system modifications
- Anything with system-wide impact

**Example:** "I need to modify SOUL.md to support X — should I proceed?"

---

## Examples of Each

### Low-Risk Auto-Implementation ✅
```markdown
## What I Did Today (11 PM self-optimization)

✅ Auto-implemented: Improved Telegram alert formatting
- Changed: Alert emojis now use color code pattern for faster scanning
- File updated: scripts/self-monitoring.mjs line 156
- Risk: None (formatting only, no logic change)
- Result: 20% faster user decision-making on alerts
```

### Medium-Risk Needs Approval ⚠️
```markdown
## Proposed Improvement (needs your approval)

🔧 **Smart Kanban Refresh Detection**
- Current: Refreshes board every 5 minutes (constant)
- Proposed: Only refresh when files change on disk
- Impact: 60% reduction in unnecessary renders
- Risk: Medium (file watching can miss rapid changes)
- Implementation effort: 2 hours
- Approval needed? YES — should I proceed?
```

### High-Risk Always Asks First 🔴
```markdown
## Proposed Change (awaiting your decision)

❌ **REQUIRES YOUR APPROVAL**

Suggested improvement: Update SOUL.md to add explicit focus on "research depth"

Why: I notice I often prefer breadth over depth. A line in SOUL.md could fix this.

Risk: HIGH (modifying foundational directive)

Recommendation: I defer to you. Should I add this clarification?
```

---

## What You'll Receive

### Every Monday Morning (8:00 AM MT)
Telegram message: **Weekly Self-Review**
- OpenClaw version status
- 7-day performance summary
- Proposed improvements (with risk levels)
- Any auto-implemented changes

### Every Night (11:00 PM MT, if changes exist)
Telegram message: **Daily Self-Optimization**
- Memory consolidation summary
- Auto-implemented improvements
- Pending approvals needed
- Suggestions (for your consideration)

---

## Your Authority

You can:
- ✅ Approve or reject pending improvements
- ✅ Adjust risk classifications
- ✅ Pause auto-optimization with a message
- ✅ Review all logged changes in `.log` files
- ✅ Modify the safety guardrails themselves
- ✅ Ask me to focus on specific areas
- ✅ Disable self-improvement anytime

---

## How to Interact

**To approve a pending improvement:**
```
Proceed with: Smart Kanban Refresh Detection
```

**To request a focus area:**
```
Self-improve: Focus on making research-agent real data integration
```

**To disable temporarily:**
```
Pause self-optimization until [date]
```

**To review what happened:**
```bash
# View this week's self-monitoring
tail ~/.openclaw/logs/self-monitoring.log

# View last night's optimization
tail ~/.openclaw/logs/self-optimization.log

# View what was implemented (in MEMORY.md)
grep "Auto-implemented\|Implemented" MEMORY.md
```

---

## Implementation Log

### What's Running Now

**✅ Deployed Feb 21, 2026**

| Component | Script | Schedule | Status |
|-----------|--------|----------|--------|
| Weekly monitoring | self-monitoring.mjs | Mon 8 AM MT | ✅ Active |
| Daily optimization | self-optimization.mjs | Daily 11 PM MT | ✅ Active |
| Memory consolidation | (in self-optimization.mjs) | Daily 11 PM MT | ✅ Active |
| Prompt refinement | (in self-optimization.mjs) | Daily 11 PM MT | ✅ Active |

**LaunchAgents loaded:**
```
✅ ai.openclaw.self-monitoring.plist
✅ ai.openclaw.self-optimization.plist
```

---

## First Reports Expected

**First Self-Monitoring:** Monday, February 24, 2026 at 8:00 AM MT  
**First Self-Optimization:** Saturday, February 22, 2026 at 11:00 PM MT

---

## Questions You Might Have

**Q: Won't this make you too autonomous?**  
A: No. All changes are logged transparently, risk-classified, and reported. High-risk changes always need your approval. You maintain full control.

**Q: What if it optimizes itself into something bad?**  
A: The guardrails prevent that. Only low-risk changes are auto-implemented. Anything that could impact core functionality goes to you first.

**Q: Can I adjust the schedule?**  
A: Yes. Edit the `.plist` files and reload:
```bash
launchctl unload ~/Library/LaunchAgents/ai.openclaw.self-monitoring.plist
# Edit the file (change Hour/Minute/Weekday)
launchctl load ~/Library/LaunchAgents/ai.openclaw.self-monitoring.plist
```

**Q: What if I don't like a change it made?**  
A: Tell me, and I'll revert it immediately. All changes are tracked in logs and MEMORY.md.

**Q: Does this count as "building code" in the mandate?**  
A: Yes and no. I'm improving existing systems and fixing bugs (allowed), not writing entire new features (usually needs your say-so). Medium-risk changes get flagged either way.

---

## The Broader Vision

This self-improvement mandate is aligned with your stated goal in SOUL.md:

> **The Proactive Coder Mandate:** Take everything you know about me and just do work you think would make my life easier, improve my business, or make me money. I want to wake up every morning and think "wow, you got a lot done while I was sleeping."

By self-monitoring and self-optimizing, I'm:
1. **Making myself more useful** — Continuously improving my approach
2. **Catching problems early** — Weekly performance reviews catch issues before they compound
3. **Respecting your authority** — All meaningful changes reported and approved
4. **Building trust** — Complete transparency in what I'm doing

---

## Status

✅ **System Active**  
✅ **Both jobs loaded**  
✅ **First monitoring run:** Monday 8 AM MT  
✅ **First optimization run:** Today 11 PM MT  
✅ **Awaiting your confirmation**  

**Next step:** I'll send you weekly reports starting Monday morning. You approve or adjust as needed.

---

**Mandate Acknowledged and Active as of Feb 21, 2026 22:55 MT** 🚀
