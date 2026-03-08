# Mission Control Dashboard

A real-time, dark-mode dashboard for monitoring all your projects, content channels, and system health. Built with Apple-design principles and fintech aesthetics.

## 📊 Overview

The dashboard aggregates metrics from:

| Category | Metrics |
|----------|---------|
| **System Health** | Telegram status, Gateway uptime, Last heartbeat |
| **Content** | Postshards (posts, subscribers, open rate, paid), winzenburg.com (visitors, bounce rate, featured projects, top source), LinkedIn (followers, engagement, top post, repurposed content) |
| **Products** | Kinetic-UI (components, accessibility, test coverage, version), Cultivate (discovery pipeline, validation score, backlog, status) |
| **Career** | Job search (target roles, applications, interviews, company watchlist) |
| **GitHub** | SaaS-Starter (open PRs, CI status, deployments, last commit), Overnight work (PRs created, tasks completed, research, last activity) |
| **Kinlet** | Phase 1 GTM (Week 1 signups, referral rate, email confirmation, engagement) |

## 🚀 Usage

### View the Dashboard

Open in your browser:
```bash
open dashboard.html
# or
open http://localhost:8000/dashboard.html  # if running a local server
```

### Update Metrics

Use the helper script to update dashboard data:

```bash
# System status
node scripts/update-dashboard.mjs system telegram true
node scripts/update-dashboard.mjs system gateway true
node scripts/update-dashboard.mjs system lastHeartbeat "5m ago"

# Postshards
node scripts/update-dashboard.mjs content.postshards posts 15
node scripts/update-dashboard.mjs content.postshards subscribers 900
node scripts/update-dashboard.mjs content.postshards openRate 35
node scripts/update-dashboard.mjs content.postshards paid 14

# Website
node scripts/update-dashboard.mjs content.website visitorsWeek 450
node scripts/update-dashboard.mjs content.website bounceRate 26
node scripts/update-dashboard.mjs content.website featured 6
node scripts/update-dashboard.mjs content.website topSource "Search"

# LinkedIn
node scripts/update-dashboard.mjs content.linkedin followers 1350
node scripts/update-dashboard.mjs content.linkedin engagement 9.2
node scripts/update-dashboard.mjs content.linkedin topPostEngagements 180
node scripts/update-dashboard.mjs content.linkedin repurposedThisMonth 5

# Kinetic-UI
node scripts/update-dashboard.mjs products.kineticsUI components 28
node scripts/update-dashboard.mjs products.kineticsUI a11y 96
node scripts/update-dashboard.mjs products.kineticsUI coverage 90
node scripts/update-dashboard.mjs products.kineticsUI version "1.3.0"

# Cultivate
node scripts/update-dashboard.mjs products.cultivate discovery 10
node scripts/update-dashboard.mjs products.cultivate validation 8
node scripts/update-dashboard.mjs products.cultivate backlog 28
node scripts/update-dashboard.mjs products.cultivate status "Validation"

# Job Search
node scripts/update-dashboard.mjs career targetRoles 4
node scripts/update-dashboard.mjs career applications 3
node scripts/update-dashboard.mjs career interviews 2
node scripts/update-dashboard.mjs career watchlist 15

# GitHub
node scripts/update-dashboard.mjs github openPRs 1
node scripts/update-dashboard.mjs github deployments 4
node scripts/update-dashboard.mjs github lastCommit "30m ago"
node scripts/update-dashboard.mjs github overnightPRs 3
node scripts/update-dashboard.mjs github tasksCompleted 8
node scripts/update-dashboard.mjs github researchDone "Competitor analysis"
node scripts/update-dashboard.mjs github lastActivity "20m ago"

# Kinlet
node scripts/update-dashboard.mjs kinlet signups 25
node scripts/update-dashboard.mjs kinlet referralRate 22
node scripts/update-dashboard.mjs kinlet confirmed 85
node scripts/update-dashboard.mjs kinlet engagement 52
```

## 🎨 Design System

Built with your Cultivate design principles:

- **4px Baseline Grid** - All spacing uses 4px increments (4, 8, 12, 16, 20, 24, 32px)
- **Dark Mode** - WCAG 2.2 AA compliant colors with fintech aesthetic
- **Apple-Style** - Minimal, professional, secure-feeling UI
- **Data Visualization** - Clear metric cards with color-coded status indicators
- **Accessibility** - Focus states, keyboard navigation, reduced-motion support

### Color Palette

| Usage | Color |
|-------|-------|
| Background (Primary) | `#0a0a0a` |
| Background (Secondary) | `#1a1a1a` |
| Text (Primary) | `#f5f5f5` |
| Text (Secondary) | `#b0b0b0` |
| Accent (Primary) | `#00d9ff` (Cyan) |
| Accent (Secondary) | `#6366f1` (Indigo) |
| Success | `#10b981` (Green) |
| Warning | `#f59e0b` (Amber) |
| Danger | `#ef4444` (Red) |

## 🔄 Automation

### Update via Heartbeat

Add to your heartbeat jobs to auto-update metrics:

```bash
# Example: Update every heartbeat
node ~/.openclaw/workspace/scripts/update-dashboard.mjs system telegram true
node ~/.openclaw/workspace/scripts/update-dashboard.mjs system lastHeartbeat "now"
```

### Update via Cron

Create a cron job to fetch fresh data from your APIs (GitHub, Substack, LinkedIn, etc.) and update the dashboard:

```bash
# Every hour, refresh metrics
0 * * * * cd ~/.openclaw/workspace && node scripts/refresh-dashboard-data.mjs
```

## 📁 Files

- `dashboard.html` - Main dashboard UI (open in browser)
- `dashboard-data.json` - Live data source (updated by scripts)
- `scripts/update-dashboard.mjs` - CLI tool to update metrics
- `DASHBOARD.md` - This file

## 🛠️ Extending

### Add a New Metric

1. Open `dashboard-data.json`
2. Add the metric to the appropriate section:
   ```json
   {
     "section": {
       "newMetric": 0
     }
   }
   ```

3. In `dashboard.html`, add a new `<div class="metric">` in the appropriate card:
   ```html
   <div class="metric">
       <div class="metric-label">New Metric</div>
       <div class="metric-value" id="newMetricId">0</div>
       <div class="metric-change">Unit</div>
   </div>
   ```

4. Add to the `updateSection()` function:
   ```javascript
   document.getElementById('newMetricId').textContent = data.section.newMetric || 0;
   ```

### Add a New Card

Copy the card structure and customize the metrics. The dashboard uses CSS Grid, so it will auto-layout.

## 🚀 Next Steps

1. **Open the dashboard** - `open dashboard.html`
2. **Bookmark it** - Add to your browser favorites
3. **Set up automation** - Add metric updates to heartbeat or cron jobs
4. **Customize** - Add more projects or metrics as needed
5. **Monitor** - Check in daily to stay aware of all moving parts

## 📝 Notes

- The dashboard auto-refreshes every 30 seconds
- All data is stored locally in `dashboard-data.json`
- Use the helper script to update metrics from heartbeat or cron jobs
- No API keys or external dependencies needed
- Fully dark mode, WCAG 2.2 AA compliant, optimized for fast loading

---

**Built with design principles from your Cultivate system. Fintech-appropriate, secure-feeling, and built for clarity.**
