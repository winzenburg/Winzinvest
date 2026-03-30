# Activation Tracking Integration Checklist

Complete setup and verification for connecting Python trading system → Winzinvest dashboard.

---

## Step 1: Get Your IBKR Account ID

Run the helper script:

```bash
cd trading/scripts
python3 get_account_id.py
```

**Expected output:**
```
Trying 127.0.0.1:4001... ✓ Connected

============================================================
IBKR ACCOUNT ID(S)
============================================================
  U1234567
    Type: Live Trading

============================================================
NEXT STEPS
============================================================
```

**Copy the account ID** (e.g., `U1234567` or `DU9876543` for paper).

---

## Step 2: Configure Account Mapping

Edit `trading/config/account_user_map.json`:

```json
{
  "_comment": "Maps IBKR account IDs to Winzinvest user emails for growth tracking",
  
  "U1234567": "ryan@winzinvest.com"
}
```

**Replace:**
- `U1234567` → your actual account ID from Step 1
- `ryan@winzinvest.com` → your dashboard login email

---

## Step 3: Generate and Set API Token

### Generate Token

```bash
# Option 1: OpenSSL
openssl rand -hex 32

# Option 2: Python
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the output (e.g., `a1b2c3d4e5f6...`).

---

### Set in Trading System

Add to `trading/.env`:

```bash
# Dashboard Integration (Growth Tracking)
DASHBOARD_URL=https://winzinvest.com
DASHBOARD_API_TOKEN=paste_your_token_here
```

---

### Set in Vercel

```bash
cd trading-dashboard-public
vercel env add INTERNAL_API_TOKEN production
```

When prompted, paste the **same token** you added to `trading/.env`.

**Verify it's set:**
```bash
vercel env ls
```

Should show `INTERNAL_API_TOKEN` in the production column.

---

## Step 4: Verify Configuration

Run the integration module's self-test:

```bash
cd trading/scripts
python3 dashboard_integration.py
```

**Expected output:**
```
Dashboard URL: https://winzinvest.com
API Token set: Yes
Account mapping loaded: 1 accounts
  U1234567 → ryan@winzinvest.com
```

**If you see "API Token set: No":**
- Check `trading/.env` has `DASHBOARD_API_TOKEN=...`
- Make sure there are no quotes around the token
- Restart any running trading scripts (they load `.env` at import)

**If you see "Account mapping file not found":**
- Check `trading/config/account_user_map.json` exists
- Check it has valid JSON syntax
- Check the path is correct (run from `trading/scripts/`)

---

## Step 5: Deploy Dashboard Changes

Dashboard changes are already pushed to GitHub. Vercel auto-deploys on push.

**Verify deployment:**
```bash
cd trading-dashboard-public
vercel ls winzinvest
```

Should show a deployment with status "READY" from the last few minutes.

**If deployment failed:**
```bash
vercel logs winzinvest.com --limit 50
```

Check for build errors. The new batch endpoint should appear in the deployment.

---

## Step 6: Test Manual API Call

Verify the dashboard accepts activation calls from your trading system:

```bash
cd trading/scripts
python3 -c "
import os
import sys
sys.path.insert(0, '.')

# Load env
from pathlib import Path
env_path = Path('.').resolve().parent / '.env'
if env_path.exists():
    for line in env_path.read_text().split('\n'):
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            os.environ[k.strip()] = v.strip()

from dashboard_integration import record_user_activation

# Try recording (use your dashboard email)
success = record_user_activation('ryan@winzinvest.com')
print('API call successful:', success)
"
```

**Expected:**
```
✓ Activation milestone recorded for ryan@winzinvest.com: firstAutomatedTrade
API call successful: True
```

**Verify in dashboard:**
1. Log in to https://winzinvest.com/institutional
2. Navigate to Admin → Growth (or directly: https://winzinvest.com/admin/growth)
3. Check the "User Activation Timeline" table
4. Your email should show `firstTradeAt` timestamp (just now)

**If you get 401 "Invalid API token":**
- Token mismatch between `trading/.env` and Vercel
- Run `vercel env ls` and compare
- Re-run `vercel env add INTERNAL_API_TOKEN production` with correct token

**If you get 404 "User not found":**
- Email in `account_user_map.json` doesn't match a user in the dashboard DB
- Check: Log in to dashboard, go to Settings, verify your email matches exactly

---

## Step 7: Test End-to-End (With Real Trade)

**Only proceed if:**
- [ ] Steps 1-6 all passed
- [ ] IB Gateway is running (paper mode recommended)
- [ ] You're OK with placing a test trade

### Reset Activation State

```bash
rm trading/logs/dashboard_activation_state.json
```

This forces the system to call the API again (normally it's idempotent).

---

### Run an Executor

```bash
cd trading/scripts

# Option 1: Mean reversion (if watchlist has candidates)
python3 execute_mean_reversion.py

# Option 2: Dual mode (shorts + longs)
python3 execute_dual_mode.py

# Option 3: Longs only
python3 execute_longs.py
```

---

### Check Logs

Look for these lines in the executor output:

```
INFO - Fill confirmed: BUY AAPL @ $180.50
INFO - First trade for user ryan@winzinvest.com (account U1234567) — recording activation milestone
INFO - ✓ Activation milestone recorded for ryan@winzinvest.com: firstAutomatedTrade
```

**If you see "Account U1234567 not mapped to user email":**
- Check `account_user_map.json` has your account ID
- Check capitalization matches exactly

**If you see "DASHBOARD_API_TOKEN not set":**
- Check `trading/.env` has the token
- Restart the executor script

**If you see "Dashboard API returned 401":**
- Token mismatch (see Step 6)

**If you see "Dashboard API timeout":**
- Dashboard is down or unreachable
- Check: `curl -I https://winzinvest.com`
- Trade still executed (non-blocking)

---

### Verify in Dashboard

1. Log in to https://winzinvest.com/institutional
2. Go to Admin → Growth
3. Check "User Activation Timeline" table
4. Your email should have:
   - `Days Active`: however long since you signed up
   - `First Trade`: timestamp of the trade you just placed
   - `Days to Activate`: difference between signup and first trade
   - Status badge: Green "Activated"

**If `Days to Activate` is negative or very large:**
- Your `User.createdAt` timestamp is wrong in the DB
- This happens if you manually created the user record
- Fix: Update `createdAt` in Supabase to match when you actually signed up

---

## Troubleshooting

### Problem: Activation records every time script runs

**Cause:** Local state file is being deleted or overwritten.

**Fix:** Check that `trading/logs/dashboard_activation_state.json` persists:

```bash
cat trading/logs/dashboard_activation_state.json
```

Should contain:
```json
{
  "recorded_users": [
    "ryan@winzinvest.com"
  ]
}
```

If this file is on Google Drive sync, it might revert. Solution:
- Move `trading/logs/` to a non-synced location (local disk)
- Or: Add to `.gitignore` and `.gdriveignore`

---

### Problem: Multiple Accounts (Paper + Live)

**Scenario:** You're testing in paper (`DU123`) but also have live account (`U123`).

**Fix:** Map both in `account_user_map.json`:

```json
{
  "U1234567": "ryan@winzinvest.com",
  "DU1234567": "ryan@winzinvest.com"
}
```

Activation only records once per email (API is idempotent).

---

### Problem: Import Error in dashboard_integration.py

**Error:** `ModuleNotFoundError: No module named 'requests'`

**Fix:** Install requests:
```bash
cd trading
pip install requests
```

Or add to `requirements.txt` if not already there.

---

## Success Criteria

You've successfully integrated when:

- [x] `python3 get_account_id.py` shows your account ID
- [x] `account_user_map.json` has your account → email mapping
- [x] `trading/.env` has `DASHBOARD_API_TOKEN`
- [x] `vercel env ls` shows `INTERNAL_API_TOKEN`
- [x] `python3 dashboard_integration.py` shows all green
- [x] Manual API call test succeeds (Step 6)
- [x] End-to-end test shows activation in dashboard (Step 7)

---

## What Happens Next (Automatic)

Once setup is complete, **every executor script automatically tracks activation**:

- `execute_mean_reversion.py` → tracks activation
- `execute_dual_mode.py` → tracks activation
- `execute_longs.py` → tracks activation
- `spotlight_monitor.py` → tracks activation
- `execute_ext_hours.py` → tracks activation

**All inherit from `BaseExecutor`, which calls `_try_record_activation()` after fills.**

No per-script configuration needed. It just works.

---

## Metrics You Can Now Track

With activation tracking live, the admin dashboard shows:

| Metric | Target | Description |
|---|---|---|
| **D7 Activation Rate** | 60%+ | % of users who place first trade within 7 days |
| **Total Activated** | — | Count of users with at least 1 trade |
| **Days to First Trade** | <4 days (ideal) | Per-user timeline |

**Action item:** Check `/admin/growth` weekly. If D7 rate is <40%:
- Send activation nudge email at D3
- Simplify onboarding (reduce friction)
- Add "quick start" tutorial

See `gamification-personalization.mdc` → Fogg Behavior Model section for activation optimization strategies.

---

## Next: Add More Milestones (Future)

Right now we only track `firstAutomatedTrade`. Future milestones:

- `firstStopFollowed` — user didn't override a stop (discipline milestone)
- `firstCoveredCall` — user enabled options automation
- `activationCompleted` — all core features used

Add new milestones by:
1. Calling `record_user_activation(email, milestone='newMilestone')`
2. Adding the field to `User` model in Prisma schema
3. Updating the activation API to handle the new milestone

See `growth-metrics-implementation.mdc` for the pattern.
