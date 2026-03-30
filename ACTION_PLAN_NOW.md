# Action Plan — What You Need to Do Right Now

All Phase 2 features are built, tested, and committed. Vercel has auto-deployed.

Here's what you need to do to go live:

---

## STEP 1: Run Database Migration (5 minutes)

### Open Supabase SQL Editor

https://supabase.com/dashboard

Navigate to: **Your Project → SQL Editor → New Query**

### Paste and Run

Copy the entire contents of `SUPABASE_MIGRATION_ENGAGEMENT.sql` into the editor and click **Run**.

**What it does:**
- Adds 5 new columns to User table (engagement tracking)
- Creates index for fast segment queries
- Safe to run multiple times (uses `IF NOT EXISTS`)

### Verify

Run this query to confirm:

```sql
SELECT 
  email,
  "dashboardViewCount",
  "emailFrequency",
  "engagementSegment"
FROM "User"
LIMIT 3;
```

Expected: All columns exist, defaults applied (dashboardViewCount = 0, emailFrequency = 'weekly').

---

## STEP 2: Test Production Dashboard (2 minutes)

### Visit Your Dashboard

https://winzinvest.com/institutional

**Sign in** (use your existing account)

### What You Should See

**Overview Tab:**
1. Daily Narrative widget at top
2. Portfolio Composition charts
3. Rejected Trades widget
4. **NEW:** Regime History timeline (shows current STRONG_DOWNTREND)
5. **NEW:** Email Preferences panel (Daily vs Weekly)

**Performance Tab:**
1. Performance Explorer with:
   - **NEW:** Quick Filters section (All Options Income, Shorts in Downtrends, etc)
   - **NEW:** Comparative context badges (Your X ↑/↓ System Avg Y)

**Positions Tab:**
1. Position table (existing)
2. **NEW:** Small **?** icons next to each symbol (decision tooltips)
3. Hover → see entry rationale

### If You See Errors

**"Error loading decision context"** → Run manually:
```bash
cd trading/scripts
python3 generate_decision_context.py
python3 track_regime_history.py
```

**"No regime history"** → Normal on first day (needs 2+ days of data to show timeline)

---

## STEP 3: Configure Email List (2 minutes)

### Edit Subscribers File

`trading/config/email_subscribers.json`

**Current content:**
```json
{
  "weekly_insights": [
    "ryan@winzinvest.com"
  ],
  "daily_alerts": [
    "admin@example.com"
  ]
}
```

**Add your real email(s):**
```json
{
  "weekly_insights": [
    "your-real-email@gmail.com"
  ],
  "daily_alerts": []
}
```

### Test Email Delivery

```bash
cd trading/scripts
python3 generate_weekly_insight.py
```

Check your inbox for: **"Your Week in Review — March 29, 2026"**

---

## STEP 4: Restart Scheduler (2 minutes)

**On your production server** (wherever scheduler.py runs):

```bash
# Kill existing scheduler
pkill -f "python.*scheduler.py"

# Navigate to scripts dir
cd "/Users/ryanwinzenburg/Library/CloudStorage/GoogleDrive-ryanwinzenburg@gmail.com/My Drive/Projects/MIssion Control/trading/scripts"

# Restart in background
nohup python3 scheduler.py > ../logs/scheduler.log 2>&1 &

# Verify it started
sleep 3
tail -30 ../logs/scheduler.log
```

**Look for:**
```
Scheduler started. Jobs:
  postclose → 2026-03-30 14:30:00-07:00
  weekly_insight_email → 2026-04-04 17:00:00-07:00
  sunday_catchup → 2026-03-30 18:00:00-07:00
```

**New jobs should include:**
- Daily: `generate_daily_narrative`, `generate_decision_context`, `track_regime_history`
- Weekly: `segment_user_behavior`, `generate_system_benchmarks`

---

## STEP 5: Verify Automated Data Generation (Tomorrow)

### Monday 2:30pm MT (After Market Close)

Check that daily scripts ran:

```bash
cd trading/logs

# Should have today's date
ls -lh decision_context.json
ls -lh daily_narrative.json

# Should have new entry appended
tail -1 regime_history.jsonl
```

### Friday 5:00pm MT (Weekly Email)

Check your inbox for weekly insight email.

### Sunday 6:00pm MT (Weekly Analytics)

Check that benchmarks and segments generated:

```bash
ls -lh trading/logs/system_benchmarks.json
ls -lh trading/logs/user_segments.json
```

---

## Complete!

After completing steps 1-4, **Phase 2 is LIVE**.

### What Happens Next (Automatic)

- **Daily (weekdays 2:30pm MT):** System generates narrative, decision context, regime history
- **Weekly (Fridays 5pm MT):** System sends insight emails to all subscribers
- **Weekly (Sundays 6pm MT):** System updates benchmarks and user segments
- **Every dashboard visit:** View tracking increments, segment recalculates after 7 days

### What You Control

- Email frequency (dashboard → Email Preferences)
- Saved filters (create as many as you want)
- Subscribers list (edit `email_subscribers.json`)

---

## Need Help?

**Docs:**
- Feature reference: `PHASE_2_COMPLETE.md`
- Deployment guide: `DEPLOYMENT_GUIDE_PHASE2.md`
- Session summary: `SESSION_SUMMARY_PHASE2.md`

**Troubleshooting:**
- See `DEPLOYMENT_GUIDE_PHASE2.md` → Troubleshooting section
- Check scheduler logs: `trading/logs/scheduler.log`
- Check Vercel logs: Vercel dashboard

**Rollback:**
- See `SESSION_SUMMARY_PHASE2.md` → Rollback Plan section

---

## Timeline Estimate

- **Step 1 (DB migration):** 5 minutes
- **Step 2 (Test dashboard):** 2 minutes
- **Step 3 (Email config):** 2 minutes
- **Step 4 (Restart scheduler):** 2 minutes
- **Step 5 (Verify):** 1 minute tomorrow, 1 minute Friday, 1 minute Sunday

**Total:** ~15 minutes of your time, spread across this week.

---

## Verification Checklist

After steps 1-4, verify:

- [ ] Dashboard loads without errors
- [ ] Regime timeline visible on Overview tab
- [ ] Email preferences panel visible on Overview tab
- [ ] Decision tooltips render (hover **?** icons)
- [ ] Saved filters section in Performance Explorer
- [ ] Comparative context badges show (if 10+ trades)
- [ ] View tracking increments (`SELECT "dashboardViewCount" FROM "User" WHERE email = 'yours';`)
- [ ] Weekly email preview exists: `trading/logs/weekly_insight_latest.html`

When all checked, **Phase 2 is complete and operational.**
