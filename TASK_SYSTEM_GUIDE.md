# Proactive Task Management System - Complete Guide

Your autonomous task management system is now live. It includes folder structure, Kanban board, and two daily cron jobs that keep you moving forward.

## 📁 Folder Structure

```
tasks/
├── backlog/         (New ideas, future work)
├── in-progress/     (Currently working on)
├── done/            (Completed)
├── search.html      (Kanban board)
└── index.json       (Task index)
```

## 🎯 5 Initial Tasks (Ready to Execute)

| ID | Title | Goal | Priority | Due |
|--|-|--|--|--|
| 001 | Execute Kinlet Phase 1 GTM | Kinlet | High | Feb 28 |
| 002 | Launch Live Trading System | Swing Trading | Critical | Feb 24 |
| 003 | Job Search Week 1 Outreach | Job Search | High | Mar 1 |
| 004 | Cultivate Dashboard Metrics | Cultivate | Medium | Mar 1 |
| 005 | Test Ollama Integration | Infrastructure | Medium | Mar 10 |

All tasks are in `backlog/` and ready to move to `in-progress/` as you start work.

## 📊 Kanban Board

Open in browser:
```
file:///Users/pinchy/.openclaw/workspace/kanban.html
```

**Features:**
- Three columns: Backlog, In Progress, Done
- Click any task to view full details
- Statistics: Total, Backlog count, In Progress count, Done count
- Auto-refresh every 5 minutes
- Color-coded priorities (Critical/High/Medium/Low)

## ⏰ Two Automated Cron Jobs

### 1️⃣ Morning Task Generation (9:00 AM MT)

**What it does:**
- Reviews your goals (from brain dump)
- Generates 1-2 proactive tasks based on priorities
- Adds them to `tasks/backlog/`
- Re-indexes the Kanban board

**Why it helps:**
- You don't have to think about what to work on
- Tasks are aligned with your stated goals
- Fresh priorities every morning

**LaunchAgent:** `ai.openclaw.morning-tasks.plist`

---

### 2️⃣ Evening Task Summary (6:00 PM MT)

**What it does:**
- Reviews all in-progress tasks
- Counts completed tasks today
- Looks at tomorrow's backlog
- Sends you a Telegram summary

**Example message:**
```
📊 Daily Task Summary

Thursday, Feb 22

Currently Working On:
🔵 Execute Kinlet Phase 1 GTM
🔵 Launch Live Trading System

Completed Today:
✅ Verify trading system rules
✅ Prepare 5 initial tasks

Plan for Tomorrow:
□ Post 3 Reddit microguides
□ Send 15 personalized DMs
□ Request warm intros
+ 2 more in backlog

Stats: 2 in progress · 2 done · 3 backlog
```

**LaunchAgent:** `ai.openclaw.evening-summary.plist`

---

## 🔄 Task File Format

Each task is a Markdown file:

```markdown
# Task Title

**ID:** 001
**Goal:** Kinlet
**Priority:** High
**Created:** 2026-02-22
**Due:** 2026-02-28
**Status:** Backlog

## Description

Clear, actionable description of what needs to be done.

## Context

Background, why it matters, what's already been done.

## Next Actions

- [ ] Step 1
- [ ] Step 2
- [ ] Step 3

## Metrics

How you'll know it's successful.
```

## 📋 How to Use

### To Move a Task

1. Open `kanban.html`
2. Click the task to view details
3. Manually edit the task file:
   - Change `**Status:**` from `Backlog` to `In Progress`
   - Or to `Done` when complete
4. Kanban board auto-refreshes every 5 minutes

**Edit tasks here:**
```
tasks/backlog/[filename].md     → Edit and change Status
tasks/in-progress/[filename].md  → Move from backlog
tasks/done/[filename].md         → Move when complete
```

### To Create a New Task (Manual)

```bash
# Create task file
cat > ~/.openclaw/workspace/tasks/backlog/006-your-task.md << 'EOF'
# Your Task Title

**ID:** 006
**Goal:** Project Name
**Priority:** High
**Created:** 2026-02-22
**Due:** 2026-03-01
**Status:** Backlog

## Description
What needs to be done.

## Context
Why it matters.

## Next Actions
- [ ] Step 1
EOF

# Re-index
cd ~/.openclaw/workspace && node scripts/index-tasks.mjs
```

### To Move a Task Between Columns

1. Edit the task file's `**Status:**` line:
   - `Backlog` → `In Progress` (start working)
   - `In Progress` → `Done` (complete)
2. Save the file
3. Re-index: `node scripts/index-tasks.mjs`
4. Kanban refreshes automatically

## 🚀 Workflow

**Morning (9:00 AM):**
1. I generate 1-2 proactive tasks based on your goals
2. Tasks appear in backlog
3. You can view them in the Kanban board

**Throughout the Day:**
1. Pick a task from backlog
2. Move it to in-progress
3. Work on it
4. Move to done when complete

**Evening (6:00 PM):**
1. I send you a summary via Telegram
2. Shows what you accomplished
3. Shows what's planned for tomorrow
4. Motivational + informative

**Tomorrow Morning:**
1. New tasks auto-generated
2. Repeat cycle

## 📊 Task Statistics

The Kanban board shows:
- **Total:** All tasks across all columns
- **Backlog:** Waiting to start
- **In Progress:** Currently working on
- **Done:** Completed tasks

## 🎯 Priority Levels

Use these when creating tasks:

| Priority | Meaning | Examples |
|----------|---------|----------|
| **Critical** | Must do today/ASAP | Trading launch, major milestones |
| **High** | This week | Kinlet GTM, job search outreach |
| **Medium** | This month | Dashboard setup, testing |
| **Low** | When you have time | Nice-to-haves, exploration |

## 📝 Scripts

| Script | Purpose | When it runs |
|--------|---------|------------|
| `index-tasks.mjs` | Scan tasks/ → Generate index.json | Manually after edits |
| `cron-morning-tasks.mjs` | Generate proactive tasks | 9:00 AM MT daily |
| `cron-evening-summary.mjs` | Send Telegram summary | 6:00 PM MT daily |

## 🔐 Check Cron Jobs

```bash
# List loaded LaunchAgents
launchctl list | grep openclaw

# Unload if needed
launchctl unload ~/Library/LaunchAgents/ai.openclaw.morning-tasks.plist
launchctl unload ~/Library/LaunchAgents/ai.openclaw.evening-summary.plist

# Reload
launchctl load ~/Library/LaunchAgents/ai.openclaw.morning-tasks.plist
launchctl load ~/Library/LaunchAgents/ai.openclaw.evening-summary.plist

# Check logs
tail -f ~/.openclaw/workspace/logs/morning-tasks.log
tail -f ~/.openclaw/workspace/logs/evening-summary.log
```

## 📖 Next Steps

1. **Open the Kanban board:** `kanban.html`
2. **Review the 5 initial tasks**
3. **Tomorrow morning:** New tasks auto-generate at 9:00 AM
4. **Complete the brain dump:** Then I'll refine tasks to perfectly match your goals

## ⚠️ Tomorrow's Brain Dump

After you complete the brain dump interview, I'll:
1. Update all tasks to align with your stated priorities
2. Generate more accurate proactive tasks
3. Adjust cron jobs to better serve your workflow

For now, the 5 initial tasks are placeholders based on your known projects.

---

**Your task system is live and autonomous. Tasks auto-generate, summaries auto-send, and your Kanban board updates automatically.** 🚀
