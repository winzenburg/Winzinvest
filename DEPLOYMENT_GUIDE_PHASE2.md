# Phase 2 Deployment Guide

## Quick Checklist

- [x] All Phase 2 features built and committed
- [x] TypeScript errors resolved
- [x] Weekly email tested (sent successfully)
- [x] Python data generators tested
- [x] Scheduler updated with new jobs
- [ ] **Database migration run in Supabase**
- [ ] Frontend deployed to Vercel
- [ ] Scheduler restarted on production server
- [ ] Email subscribers list updated
- [ ] All widgets verified on production dashboard

---

## Step-by-Step Deployment

### 1. Run Database Migration (5 minutes)

**Open Supabase SQL Editor:**
https://supabase.com/dashboard/project/[your-project]/sql/new

**Paste and run:** `SUPABASE_MIGRATION_ENGAGEMENT.sql`

**Verify:**
```sql
SELECT 
  email, 
  "dashboardViewCount", 
  "emailFrequency", 
  "engagementSegment",
  "lastDashboardViewAt"
FROM "User" 
LIMIT 5;
```

Expected: All columns exist, default values applied.

---

### 2. Deploy Frontend (Automatic)

**If Vercel is connected to git:**
```bash
# Already done — git push triggers deploy
```

**Manually trigger if needed:**
```bash
cd trading-dashboard-public
vercel --prod
```

**Monitor:** https://vercel.com/your-username/winzinvest/deployments

**Wait for:** "Ready" status (~2-3 minutes)

---

### 3. Restart Trading System Scheduler

**SSH into your production server** (wherever scheduler.py runs):

```bash
# Find and kill existing scheduler
pkill -f "python.*scheduler.py"

# Restart with new jobs
cd "/path/to/Mission Control/trading/scripts"
nohup python3 scheduler.py > ../logs/scheduler.log 2>&1 &

# Verify jobs loaded
tail -30 ../logs/scheduler.log
```

**Look for:**
```
Scheduler started. Jobs:
  ...
  daily_narrative → [next run time]
  weekly_insight_email → [next run time]
```

---

### 4. Update Email Subscribers

**Edit:** `trading/config/email_subscribers.json`

```json
{
  "weekly_insights": [
    "your-email@example.com",
    "founding-member@example.com"
  ],
  "daily_alerts": [
    "admin@example.com"
  ]
}
```

**Note:** This controls the Python email scripts. User preferences (daily vs weekly) are stored in Supabase `User.emailFrequency` — the Python script will query this before sending.

**TODO:** Update `generate_weekly_insight.py` to respect `User.emailFrequency` from Supabase (currently sends to all in `email_subscribers.json`).

---

### 5. Test All New Features

#### Decision Tooltips
1. Open dashboard → Overview tab
2. Scroll to positions table (if visible on Overview) or Positions tab
3. Look for **?** icons
4. Hover → tooltip appears with entry rationale

#### Regime Timeline
1. Overview tab → scroll down
2. "Regime History" widget should show timeline
3. Verify current regime badge has "Current" label

#### Email Preferences
1. Overview tab → scroll to "Email Insights Frequency"
2. Toggle between Daily / Weekly
3. Refresh page → verify choice persists

#### Saved Filters
1. Performance tab → Performance Explorer
2. Adjust filters (e.g., regime = STRONG_UPTREND)
3. Click "+ Save Current"
4. Name it → Save
5. Reload page → click saved filter → filters apply

#### Comparative Context
1. Performance tab → Performance Explorer
2. If you have 10+ trades: Win Rate and R-Multiple cards show comparison badges
3. Green ↑ = above average, Red ↓ = below average

#### Weekly Email
**Wait for:** Next Friday 5pm MT

**Or test now:**
```bash
cd trading/scripts
python3 generate_weekly_insight.py
```

Check inbox for "Your Week in Review"

---

### 6. Monitor First Week

**View tracking:**
```sql
SELECT 
  email,
  "dashboardViewCount",
  "lastDashboardViewAt",
  "engagementSegment"
FROM "User"
ORDER BY "dashboardViewCount" DESC;
```

**System benchmarks:**
```bash
cat trading/logs/system_benchmarks.json | jq '.benchmarks'
```

**Regime transitions:**
```bash
tail -10 trading/logs/regime_history.jsonl
```

---

## Troubleshooting

### Email not sending
1. Check Resend API key in `trading/.env`: `RESEND_API_KEY=re_...`
2. Verify FROM_EMAIL domain verified in Resend dashboard
3. Test manually: `python3 generate_weekly_insight.py`
4. Check logs: `grep -i "email\|resend" trading/logs/scheduler.log`

### Tooltips not appearing
1. Verify `decision_context.json` exists: `ls -lh trading/logs/decision_context.json`
2. Run generator manually: `python3 generate_decision_context.py`
3. Check API: `curl -H "Cookie: your-auth-cookie" http://localhost:3000/api/decision-context?symbol=AAPL`

### Comparative context not showing
1. Check system benchmarks: `cat trading/logs/system_benchmarks.json`
2. Verify trade count: If < 10 trades in filtered view, badges are hidden by design
3. Run generator: `python3 generate_system_benchmarks.py`

### Regime timeline empty
1. Initialize history: `python3 track_regime_history.py`
2. Check file: `cat trading/logs/regime_history.jsonl`
3. Wait 1 day for second entry (timeline needs 2+ points to be interesting)

### User segment not updating
1. Check view count in DB: `SELECT email, "dashboardViewCount" FROM "User";`
2. Verify API: `curl -H "Cookie: your-auth-cookie" http://localhost:3000/api/user-segment`
3. Segments only update after 7+ days of data

---

## Performance Impact

### Client (Browser)
- **+3 API calls** on dashboard load (decision-context, regime-history, system-benchmarks)
- **+1 POST** on every dashboard visit (view tracking)
- **Payload:** ~20-50KB total for new widgets (gzipped)
- **Impact:** < 500ms added to initial dashboard load

### Server (Python)
- **Daily jobs:** +3 scripts (~30 seconds total at post-close)
- **Weekly jobs:** +3 scripts (~60 seconds total on Sundays)
- **Memory:** Minimal (all scripts are stateless, short-lived)

### Database (Supabase)
- **+5 columns** on User table (negligible storage)
- **+1 index** on engagementSegment
- **Queries:** Simple selects/updates (< 10ms each)

**Overall:** Negligible performance impact.

---

## Success Criteria (30 Days)

### Engagement Lift
- [ ] 20%+ increase in daily active dashboard users
- [ ] 30%+ of users interact with Performance Explorer filters
- [ ] 15%+ of users save at least one custom filter
- [ ] 60%+ email open rate (vs 40% baseline if no personalization)

### Trust Indicators
- [ ] 50%+ of users hover at least one decision tooltip
- [ ] 25%+ of users scroll to regime timeline
- [ ] Users who view rejected trades widget have 15%+ higher retention

### Personalization Effectiveness
- [ ] Users in correct segment (measured by email open rate matching frequency pref)
- [ ] Daily cohort has 2x+ dashboard views vs weekly cohort
- [ ] No complaints about email frequency (opt-out rate < 2%)

---

## Support Resources

**Documentation:**
- `PHASE_2_COMPLETE.md` — Feature overview
- `ENGAGEMENT_FEATURES_SUMMARY.md` — Original Phase 1 summary
- `.cursor/rules/gamification-personalization.mdc` — Philosophy and framework

**Frameworks:**
- Yu-kai Chou: *Actionable Gamification* (Octalysis)
- Nir Eyal: *Hooked* (habit loops)
- BJ Fogg: *Tiny Habits* (B=MAP model)
- Deci & Ryan: SDT (Self-Determination Theory)

**Contact:** For issues or feature requests, see dashboard settings or email admin.

---

## Deployment Complete

After following all steps above, **Phase 2 is LIVE**.

Users will see:
- Educational tooltips on positions
- Regime history timeline on Overview
- Email preference controls
- Saved filter presets in Performance Explorer
- "Your X vs avg Y" comparison badges
- Weekly insight emails (Fridays 5pm MT)
- Personalized dashboard layouts (based on segment, future enhancement)

**Monitor metrics weekly.** Iterate based on real user behavior, not assumptions.
