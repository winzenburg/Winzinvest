# Dashboard Data Automation Setup

Complete guide to automate your Mission Control Dashboard with real data from GitHub, Substack, LinkedIn, and more.

## 🚀 Quick Start

### 1. Set Up Environment Variables

Create a `.env.dashboard` file in your workspace:

```bash
# GitHub
export GITHUB_TOKEN="ghp_your_personal_access_token_here"

# Vercel (optional, for deployment tracking)
export VERCEL_TOKEN="your_vercel_api_token"

# Substack (optional, use manual updates if not available)
export SUBSTACK_API_KEY="your_substack_api_key"
```

Load before running scripts:
```bash
source .env.dashboard
node scripts/refresh-dashboard-data.mjs
```

### 2. Get GitHub Token

1. Go to https://github.com/settings/tokens
2. Click "Generate new token"
3. Select these scopes:
   - `repo` (full control of private repositories)
   - `public_repo` (access public repositories)
4. Copy the token and save to `.env.dashboard`

### 3. Get Vercel Token (Optional)

1. Go to https://vercel.com/account/tokens
2. Create a new token with "Full Access"
3. Add to `.env.dashboard`

## 📊 Data Sources & Update Methods

### GitHub (Automated)

**What's tracked:**
- Open PRs on SaaS-Starter
- Latest commit (time ago)
- Successful deployments (via Vercel)

**Script:** `scripts/refresh-dashboard-data.mjs`

**Frequency:** Hourly (via cron)

**Update manually:**
```bash
node scripts/update-dashboard.mjs github openPRs 2
node scripts/update-dashboard.mjs github lastCommit "30m ago"
```

### Vercel (Automated)

**What's tracked:**
- Successful deployments (count)

**Included in:** `scripts/refresh-dashboard-data.mjs`

**Requires:** VERCEL_TOKEN in `.env.dashboard`

### Substack (Manual or API)

**What's tracked:**
- Subscriber count
- Post count
- Open rate (%)
- Paid subscribers

**Methods:**

**Option 1: Manual Update (Easiest)**
```bash
# Check your Substack dashboard, then run:
node scripts/fetch-substack-data.mjs --manual 847 34 12
# Arguments: subscribers, openRate, paidSubscribers
```

**Option 2: Via API (if available)**
```bash
# Get API key from https://substack.com/app/publication/settings/api
export SUBSTACK_API_KEY="your_key_here"
node scripts/fetch-substack-data.mjs --api
```

**Frequency:** Daily or whenever you check your Substack dashboard

### LinkedIn (Manual)

**What's tracked:**
- Follower count
- Engagement rate
- Top post engagements (this month)
- Repurposed content count (this month)

**Update:**
```bash
# Check your LinkedIn profile, then run:
node scripts/fetch-linkedin-data.mjs --manual 1250 8.5 156 4
# Arguments: followers, engagement%, topPostEngagements, repurposedThisMonth
```

**Frequency:** Daily or 2-3x per week

**Tip:** Set a calendar reminder to check LinkedIn profile metrics weekly.

### Website Analytics (winzenburg.com)

**What's tracked:**
- Visitors (this week)
- Bounce rate
- Featured projects
- Top traffic source

**Current:** Manual update only

**To automate:**
1. Set up Google Analytics API
2. Create a script similar to GitHub fetcher
3. Or use a service like Segment

**For now, update manually:**
```bash
node scripts/update-dashboard.mjs content.website visitorsWeek 450
node scripts/update-dashboard.mjs content.website bounceRate 26
node scripts/update-dashboard.mjs content.website featured 6
node scripts/update-dashboard.mjs content.website topSource "Search"
```

## 🤖 Automation Options

### Option 1: Cron Job (Recommended)

**Hourly quick refresh (GitHub + Vercel):**
```bash
# Add to crontab
0 * * * * source ~/.openclaw/.env.dashboard && cd ~/.openclaw/workspace && node scripts/dashboard-scheduler.mjs --quick >> logs/dashboard-scheduler.log 2>&1
```

**Daily full refresh with manual prompts:**
```bash
0 9 * * * source ~/.openclaw/.env.dashboard && cd ~/.openclaw/workspace && node scripts/dashboard-scheduler.mjs --full >> logs/dashboard-scheduler.log 2>&1
```

**Edit your crontab:**
```bash
crontab -e
```

### Option 2: OpenClaw Heartbeat

Add to your `HEARTBEAT.md` periodic checks:

```markdown
### Dashboard Refresh (Every Hour)
- If last refresh was >1h ago, run: `source ~/.openclaw/.env.dashboard && node scripts/dashboard-scheduler.mjs --quick`
- Update manual metrics (Substack, LinkedIn) once per day
- Log in heartbeat-state.json: { "lastDashboardRefresh": <epoch_ms> }
```

### Option 3: GitHub Actions (For CI/CD)

Create `.github/workflows/dashboard-refresh.yml`:

```yaml
name: Refresh Dashboard

on:
  schedule:
    - cron: '0 * * * *'  # Every hour
  workflow_dispatch:

jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      
      - name: Refresh Dashboard
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
        run: |
          cd workspace
          node scripts/dashboard-scheduler.mjs --quick
      
      - name: Commit changes
        run: |
          git config user.name "Dashboard Bot"
          git config user.email "bot@example.com"
          git add dashboard-data.json
          git commit -m "chore: auto-update dashboard" || true
          git push
```

## 📋 Daily Routine

**Morning (6-7 AM):**
- Dashboard auto-refreshes via cron (GitHub, Vercel)
- Check dashboard for overnight work summary

**Midday (noon-1 PM):**
- Manually update LinkedIn metrics (quick 2-min check)

**Evening (5-6 PM):**
- Manually update Substack metrics (check dashboard for subscriber changes)
- Update website metrics if available

**Weekly (Sunday):**
- Review all metrics
- Update career/job search stats

## 🔧 Troubleshooting

**"GITHUB_TOKEN not set"**
```bash
# Make sure to source your .env.dashboard before running
source ~/.openclaw/.env.dashboard
node scripts/refresh-dashboard-data.mjs
```

**GitHub API rate limit exceeded**
- GitHub allows 60 requests/hour unauthenticated, 5000/hour with token
- Check: `curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/rate_limit`

**Script errors not being logged**
- Check log files: `tail logs/dashboard-scheduler.log`

**Dashboard shows stale data**
- Manually refresh: `node scripts/refresh-dashboard-data.mjs`
- Check if cron job is running: `crontab -l`

## 📝 Quick Command Reference

```bash
# View current cron jobs
crontab -l

# Edit cron jobs
crontab -e

# Run dashboard refresh immediately
source ~/.openclaw/.env.dashboard && node scripts/dashboard-scheduler.mjs --quick

# Update specific metric
node scripts/update-dashboard.mjs kinlet signups 25
node scripts/update-dashboard.mjs content.postshards subscribers 900

# Update Substack
node scripts/fetch-substack-data.mjs --manual 847 34 12

# Update LinkedIn
node scripts/fetch-linkedin-data.mjs --manual 1250 8.5 156 4

# View logs
tail -f logs/dashboard-scheduler.log
```

## 🎯 Next Steps

1. **Set up GitHub token** → `.env.dashboard`
2. **Test the refresh script** → `node scripts/dashboard-scheduler.mjs --quick`
3. **Add cron job** → `crontab -e` (hourly refresh)
4. **Set calendar reminders** → LinkedIn/Substack checks (daily)
5. **Monitor logs** → `tail logs/dashboard-scheduler.log`
6. **Add to heartbeat** → Optional: integrate with OpenClaw heartbeat

---

**You now have a fully automated dashboard that stays fresh throughout the day.**
