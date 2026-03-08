# Activated Skills Guide

## 1. Market Research (`market-research`)

**Purpose**: Synthesize Reddit, X, and community insights into actionable research reports

### Automatic Crons (Running Now)

| Research | Schedule | Next Run | Focus |
|----------|----------|----------|-------|
| **Kinlet** | Mon/Wed/Fri 3 PM MT | Monday 3 PM | Caregiver pain points, language, positioning |
| **Trading** | Tue/Thu 3 PM MT | Tuesday 3 PM | Macro consensus, sector rotation, setups |
| **Job Market** | Sat 2 PM MT | Saturday 2 PM | Design ops salaries, target companies, trends |

### Manual Usage (Telegram Voice Note)

Send a voice note to Telegram with your research request:

> "Go analyze r/Alzheimers and r/dementia. Find what caregivers struggle with most. Email me a synthesis report."

Or text command:
```
/research kinlet caregiver apps on Reddit for feature ideas
/research swing trading setups on X for next week's signals
/research design operations market on LinkedIn for job search
```

### Report Format

Each report includes:
- Executive summary (key takeaway)
- Key insights (3-5 findings with sources)
- Pain points table (frequency, severity, opportunities)
- Actionable recommendations
- Raw sources (links to all referenced posts)

---

## 2. Voice Transcription (`openai-whisper-api`)

**Purpose**: Convert voice notes to text for hands-free research requests

### Command Line Usage

```bash
# Transcribe a Telegram voice note
transcribe-voice-note.sh ~/Downloads/voice_note.m4a

# Output: ~/Downloads/voice_note.txt (transcript)
```

### Workflow Integration

1. Record voice note on phone / Telegram
2. Download to local file
3. Run: `transcribe-voice-note.sh /path/to/audio.m4a`
4. Transcript appears as text file
5. If transcript contains "research", use it to trigger market research

### Voice Note Best Practices

Keep notes short (< 2 min):
- "Research caregiver apps on Reddit. What do they want?"
- "Analyze swing trading sentiment on FinTwit today"
- "Find job postings for design ops roles at startup companies"

---

## 3. GitHub Issues Automation (`gh-issues`)

**Purpose**: Automatically fix issues and manage PRs on your monorepo

### Prerequisites

✅ GitHub CLI authenticated (winzenburg)  
✅ GH_TOKEN configured  
✅ Monorepo: winzenburg/SaaS-Starter (Cultivate, Kinlet, Design System)

### Quick Start

```bash
# Auto-fix issues labeled "bug" in Kinlet
openclaw gh-issues winzenburg/SaaS-Starter --label bug --fork winzenburg/SaaS-Starter

# Auto-fix 5 issues and open PRs
openclaw gh-issues --label enhancement --limit 5 --fork winzenburg/SaaS-Starter

# Monitor PRs for review comments and auto-address
openclaw gh-issues --reviews-only --watch

# Cron mode: spawn one issue fixer per run, fire-and-forget
openclaw cron add \
  --name "gh-issues-auto-fix" \
  --cron "0 9 * * 1-5" \
  --message "Fix one open issue on winzenburg/SaaS-Starter" \
  --cron
```

### How It Works

1. **Fetches** issues matching your filters
2. **Spawns sub-agents** (up to 8 concurrently) to fix each one
3. Each sub-agent:
   - Reads the issue
   - Searches codebase for the problem
   - Implements a fix
   - Runs tests
   - Opens a PR
4. **Monitors PRs** for review comments
5. **Auto-addresses** review feedback with new commits

### Sub-agent Behavior

- Skips issues if confidence < 7/10
- Times out after 60 minutes (complex issues need manual review)
- Posts replies to each reviewer comment
- Never force-pushes or modifies base branch

### Status Tracking

Check PR creation status:
```bash
git log --oneline --grep="fix/issue-" | head -20
```

List your fix branches:
```bash
git branch | grep "fix/issue-"
```

---

## Integration Examples

### Example 1: Kinlet GTM Research Loop

1. Voice note: *"Research caregiver Reddit communities. What's the biggest pain point?"*
2. Transcribed to: `~/Downloads/voice_note.txt`
3. Run: `transcribe-voice-note.sh ~/Downloads/voice_note.txt`
4. Market research cron fires Monday/Wed/Fri with deep caregiver analysis
5. Email report arrives with insights, opportunities, language patterns
6. Use findings to refine Kinlet messaging

### Example 2: Trading Thesis Validation

1. Cron job runs Tue/Thu 3 PM MT
2. Analyzes r/swingtrading, r/stocks, FinTwit
3. Reports: Sector rotation signals, macro consensus, risk factors
4. You get email: "Macro Analysis — Tech Rally Showing Strength, Consumer Weak"
5. Informs your watchlist updates and position sizing

### Example 3: Job Search Intelligence

1. Cron runs Saturday 2 PM MT
2. Scans LinkedIn, design Twitter, Reddit for jobs
3. Reports: Comp benchmarks, in-demand skills, target companies
4. You get email: "Design Ops Market Update — 20 Remote Openings, $180-220k Range"
5. Informs your target list and positioning

### Example 4: Monorepo Quality Automation

1. Weekly cron (9 AM Monday-Friday):
   - Fetches open issues labeled "bug"
   - Spawns sub-agent to fix the first one
   - Agent opens PR automatically
2. When PR gets review comments:
   - Agent auto-addresses feedback
   - Posts replies to each reviewer
   - Pushes updates to same branch

---

## Cost Optimization

| Skill | Cost per Run | Monthly Impact |
|-------|------------|-----------------|
| Market research (3x/week) | ~$0.05 | ~$0.60 |
| Voice transcription (as needed) | ~$0.01 per minute | ~$2-5 |
| gh-issues (1-2 issues/week) | ~$0.10-0.30 | ~$2-5 |
| **Total** | — | **~$5-10/month** |

All under your $200-300/month budget with room to scale.

---

## Troubleshooting

**Market research not running?**
- Check: `openclaw cron list` (should show market-research-* jobs enabled)
- Run manually: `openclaw cron run a94187f8-851a-4ad3-aaf3-1535f30c2eb4` (Kinlet cron ID)

**Voice transcription failing?**
- Verify: `echo $OPENAI_API_KEY` (should not be empty)
- Check file format: `file ~/Downloads/voice_note.m4a` (should be audio file)

**GitHub issues not working?**
- Check auth: `gh auth status` (should show winzenburg, token scopes repo/workflow)
- Test API: `gh api /user --jq '.login'` (should return "winzenburg")

---

## Next Steps

1. ✅ Market research crons are running (auto-deliver Mon-Sat)
2. ✅ Voice transcription ready (use when you record notes)
3. ✅ GitHub automation ready (manual commands + cron options)
4. **Coming soon**: Integrate voice → research pipeline into Telegram bot

Questions? Check the SKILL.md files:
- `/opt/homebrew/lib/node_modules/openclaw/skills/market-research/SKILL.md`
- `/opt/homebrew/lib/node_modules/openclaw/skills/openai-whisper-api/SKILL.md`
- `/opt/homebrew/lib/node_modules/openclaw/skills/gh-issues/SKILL.md`
