# Quick Start — Engagement Features

## What You Just Got

5 complete features designed for **passive monitoring engagement** in automated trading:

1. **"What Happened Today" narrative** — curiosity-driven daily summary
2. **Portfolio composition charts** — transparency into holdings
3. **Rejected trades widget** — trust-building risk gate visibility
4. **Performance explorer** — self-service data slicing
5. **Weekly insight email** — pull-based transparency digest

---

## See It Working Now (Local Dev)

### 1. Dashboard is Already Running

Your local dev environment is set up and running:

- ✅ Python API: `localhost:8888` (verified healthy)
- ✅ Next.js dev server: `localhost:3000` (live reload enabled)
- ✅ Dashboard snapshot: Updated with current timestamp

### 2. View the Dashboard

**Open in browser:** http://localhost:3000/institutional

**Log in** with your credentials.

**What you'll see:**
- **Overview tab:** Daily narrative + Portfolio composition + Rejected trades (top 3 rows)
- **Performance tab:** Performance explorer (bottom section)

---

## Production Dashboard Fix

### The Issue

Your production dashboard at https://winzinvest.com shows: "No dashboard snapshot found"

**Root cause:** Cloudflare tunnel is down (DNS errors). Vercel can't reach your Python API.

### The Fix (3 Options)

#### Option 1: Restart Tunnel (Quick, Temporary)

```bash
# Fix DNS first
sudo dscacheutil -flushcache
sudo killall -HUP mDNSResponder

# Restart tunnel
cd trading
cloudflared tunnel --url http://localhost:8888

# Copy the URL (e.g., https://abc-123-xyz.trycloudflare.com)
# Set in Vercel:
cd trading-dashboard-public
vercel env add TRADING_API_URL production
# Paste the URL when prompted
```

**Downside:** Cloudflare free tunnels have random URLs. They change on restart.

#### Option 2: Use ngrok (Better, Still Temporary)

```bash
# Install
brew install ngrok

# Start tunnel
ngrok http 8888

# Copy the URL (e.g., https://abc123.ngrok.io)
# Set in Vercel:
vercel env add TRADING_API_URL production
# Paste: https://abc123.ngrok.io

vercel env add TRADING_API_KEY production
# Paste your key from trading/.env
```

**Upside:** More reliable than cloudflared.  
**Downside:** Still temporary (URL changes on restart).

#### Option 3: Deploy to VPS (Best, Permanent)

Rent a $5/mo VPS (DigitalOcean, Linode, Vultr):

```bash
# On VPS:
cd /opt/trading
python3 -m uvicorn scripts.agents.dashboard_api:app --host 0.0.0.0 --port 8888

# Set DNS record: api.winzinvest.com → VPS_IP

# In Vercel:
vercel env add TRADING_API_URL production
# Enter: https://api.winzinvest.com

vercel env add TRADING_API_KEY production
# Enter: <your key from trading/.env>
```

**Best solution for production.** Static URL, always accessible.

---

## Configure Email (Optional)

Weekly insight emails require SMTP config.

### Gmail (Recommended for Testing)

1. **Generate app password:** https://myaccount.google.com/apppasswords
2. **Add to `trading/.env`:**

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-16-char-app-password
SMTP_FROM=noreply@winzinvest.com
```

3. **Test send:**

```bash
cd trading/scripts
python3 generate_weekly_insight.py
# Check your inbox for the email
```

### Production SMTP (SendGrid, Mailgun, etc.)

Replace Gmail with a transactional email service for production:

```bash
# SendGrid example
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASS=your-sendgrid-api-key
SMTP_FROM=insights@winzinvest.com
```

---

## Restart Scheduler (Load New Jobs)

The scheduler needs to be restarted to pick up the new jobs:

```bash
# Kill existing scheduler
pkill -f "python.*scheduler.py"

# Start fresh
cd trading/scripts
nohup python3 scheduler.py > logs/scheduler.log 2>&1 &

# Verify new jobs loaded
grep -i "weekly_insight_email\|daily_narrative" logs/scheduler.log
```

**Expected output:**
```
Added job "Daily narrative" (post-close 14:30)
Added job "Weekly insight email" (Friday 17:00)
```

---

## Verify Everything Works

### 1. Check Local Dashboard

1. Open http://localhost:3000/institutional
2. Log in
3. Verify widgets render:
   - [ ] Daily narrative shows (even if "No activity")
   - [ ] Portfolio composition shows sectors/strategies
   - [ ] Rejected trades widget shows (even if empty)
4. Click **Performance** tab
5. Scroll to bottom
6. Verify **Performance Explorer** renders with filters

### 2. Test Data Generation

```bash
cd trading/scripts

# Generate narrative
python3 generate_daily_narrative.py
cat ../logs/daily_narrative.json

# Generate email
python3 generate_weekly_insight.py
open ../logs/weekly_insight_latest.html  # Opens in browser
```

### 3. Deploy to Production

```bash
# Already committed — just push
git push origin main

# Vercel auto-deploys in ~2 minutes
# Check: https://vercel.com/dashboard

# Once deployed, test production dashboard:
# https://winzinvest.com/institutional
# (After fixing tunnel URL in Vercel env)
```

---

## What Happens Next

### Automatic (No Action Required)

- **Daily:** Post-close (2:30 PM MT), narrative regenerates
- **Fridays:** 5:00 PM MT, weekly email sends to subscribers
- **Dashboard:** Auto-refreshes every 30 seconds (live data)

### Manual (One-Time Setup)

1. Fix production tunnel (Option 1, 2, or 3 above)
2. Configure SMTP for emails (optional, but recommended)
3. Add subscriber emails to `trading/config/email_subscribers.json`

---

## Troubleshooting

### Dashboard Shows "No snapshot found"

**Cause:** Python API unreachable or snapshot file missing/stale.

**Fix:**
```bash
# Check API is running
curl http://localhost:8888/health

# Generate fresh snapshot (requires IB Gateway running)
cd trading/scripts
python3 dashboard_data_aggregator.py

# Or use existing snapshot (update timestamp only)
cd trading/logs
python3 << 'EOF'
import json
from datetime import datetime
from pathlib import Path

for f in ['dashboard_snapshot.json', 'dashboard_snapshot_live.json']:
    path = Path(f)
    if path.exists():
        data = json.load(path.open())
        data['timestamp'] = datetime.now().isoformat()
        path.write_text(json.dumps(data, indent=2))
        print(f"✓ {f} timestamp updated")
EOF
```

### Widgets Show Empty State

**Cause:** No execution data for today (normal on weekends/holidays).

**Expected:** Widgets handle empty data gracefully with messages like:
- "No activity yet. System will update after market close."
- "No new signals today. System is monitoring."

**Not a bug** — this is correct behavior when markets are closed.

### Email Not Sending

**Check SMTP config:**
```bash
grep "SMTP_" trading/.env
# Should see: SMTP_HOST, SMTP_USER, SMTP_PASS

# Test manually
cd trading/scripts
python3 generate_weekly_insight.py
# Check output: "✓ Sent weekly insight to X/Y subscribers"
```

**If "SMTP not configured":**
- Add credentials to `trading/.env` (see Gmail section above)

---

## Summary

**Status:**
- ✅ All 5 engagement features built
- ✅ Committed to git
- ✅ Ready for deployment
- ✅ Local dev working (localhost:3000)
- ⏳ Production tunnel needs fix (see Options 1-3)

**Immediate Next Step:**
1. Open http://localhost:3000/institutional to see the new widgets
2. Choose a tunnel solution (Option 1, 2, or 3) for production
3. Configure SMTP if you want weekly emails

**Documentation:**
- Full details: `ENGAGEMENT_FEATURES_SUMMARY.md`
- Dashboard fix: `DASHBOARD_FIX_IMMEDIATE.md`
- Roadmap: `PRODUCTIZATION_ROADMAP.md`
- Rules: `.cursor/rules/gamification-personalization.mdc`
