# Dashboard Integration Setup

Connects your Python trading system to the Winzinvest dashboard for growth tracking (activation metrics, user behavior).

---

## What This Enables

When your trading scripts place a user's **first automated trade**, they call:
```
POST https://winzinvest.com/api/activation
```

This records `User.firstAutomatedTradeAt` in the dashboard database, which:
- Shows on the admin growth dashboard (`/admin/growth`)
- Contributes to the **D7 activation rate** metric (target: 60%)
- Triggers lifecycle events (future: D7 nudge email if not activated)

**Critical:** This is **non-blocking**. If the dashboard is down, trades still execute.

---

## Prerequisites

### 1. Get Your IBKR Account ID

The trading system needs to know which IBKR account maps to which dashboard user.

**Option A: From IB Gateway / TWS**
1. Open TWS or IB Gateway
2. Top-right corner shows your account ID (e.g., `U1234567` for live, `DU9876543` for paper)

**Option B: From Python**
```python
from ib_insync import IB
ib = IB()
ib.connect('127.0.0.1', 4001, clientId=999)
print(ib.managedAccounts())  # ['U1234567']
ib.disconnect()
```

---

### 2. Configure Account Mapping

Edit `trading/config/account_user_map.json`:

```json
{
  "_comment": "Maps IBKR account IDs to Winzinvest user emails for growth tracking",
  
  "U1234567": "ryan@winzinvest.com",
  "DU9876543": "test@example.com"
}
```

**Rules:**
- Account ID is the key (exactly as shown in IB Gateway)
- Email must match your **dashboard login email** (the one you signed up with)
- Add multiple accounts if testing paper + live
- This file is read on every executor run (no restart needed)

---

### 3. Set Environment Variables

Add to `trading/.env`:

```bash
# Dashboard integration (growth tracking)
DASHBOARD_URL=https://winzinvest.com
DASHBOARD_API_TOKEN=your_secure_random_token_here
```

**Generate a token:**
```bash
# Option 1: OpenSSL
openssl rand -hex 32

# Option 2: Python
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Add the same token to Vercel:**
```bash
cd trading-dashboard-public
vercel env add INTERNAL_API_TOKEN production
# Paste the same token you generated above
```

**Why two names?**
- `DASHBOARD_API_TOKEN` (trading system) — outbound calls
- `INTERNAL_API_TOKEN` (dashboard) — validates inbound calls
- Same value, different perspectives

---

### 4. Verify Environment Setup

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

If you see `API Token set: No` or `Account mapping file not found`, fix those first.

---

## How It Works (Automatic)

### 1. Executor Places Trade
```python
# execute_mean_reversion.py, execute_dual_mode.py, etc.

# After confirmed fill:
result = await self.router.submit_parent_and_wait(intent, symbol)
if result.success:
    self.log.info("Fill confirmed: %s %s @ $%.2f", action, symbol, result.filled_price)
    # ... build enriched record, append to self.executions ...
```

### 2. Base Executor Saves and Tracks
```python
# base_executor.py._save_executions() (runs after execute() completes)

for e in self.executions:
    append_jsonl(self.execution_log_path, e)

# NEW: After logging, check for activation
self._try_record_activation()  # Calls dashboard_integration.try_record_activation_for_account()
```

### 3. Dashboard Integration Checks and Calls API
```python
# dashboard_integration.try_record_activation_for_account()

account_id = ib.managedAccounts()[0]  # "U1234567"
user_email = get_user_email(account_id)  # "ryan@winzinvest.com"

if not has_recorded_activation(user_email):  # Local state check
    requests.post(
        "https://winzinvest.com/api/activation",
        json={"milestone": "firstAutomatedTrade"},
        headers={"Authorization": "Bearer <token>", "X-User-Email": user_email},
        timeout=5,
    )
    mark_activation_recorded(user_email)  # Never call again
```

### 4. Dashboard Receives and Updates DB
```typescript
// app/api/activation/route.ts

const token = req.headers.get('Authorization')?.replace('Bearer ', '');
if (token === process.env.INTERNAL_API_TOKEN) {
  const email = req.headers.get('X-User-Email');
  
  await prisma.user.update({
    where: { email },
    data: { firstAutomatedTradeAt: new Date() },
  });
}
```

**Result:** User's activation timestamp appears on `/admin/growth`, contributing to D7 activation rate.

---

## Testing Integration (Step-by-Step)

### Test 1: Verify Configuration

```bash
cd trading/scripts
python3 dashboard_integration.py
```

Expected: See your account ID mapped to your email, API token confirmed.

---

### Test 2: Manual API Call (Simulate Trading System)

```bash
cd trading/scripts
python3 -c "
import os
import sys
sys.path.insert(0, '.')
from dashboard_integration import record_user_activation

# Set env vars for test
os.environ['DASHBOARD_URL'] = 'https://winzinvest.com'
os.environ['DASHBOARD_API_TOKEN'] = 'your_token_here'

# Try recording activation
success = record_user_activation('ryan@winzinvest.com')
print('Success:', success)
"
```

**Expected:** Console shows `"✓ Activation milestone recorded for ryan@winzinvest.com: firstAutomatedTrade"`

**Verify:** Log into dashboard → Admin → Growth → see your email in the activation table with a timestamp.

---

### Test 3: End-to-End (Place a Real Trade)

**Only if you're ready to test with real execution!**

1. **Reset local state** (so activation triggers again):
   ```bash
   rm trading/logs/dashboard_activation_state.json
   ```

2. **Run any executor in paper mode:**
   ```bash
   cd trading/scripts
   python3 execute_mean_reversion.py
   ```

3. **Check logs for activation call:**
   ```
   INFO - First trade for user ryan@winzinvest.com (account U1234567) — recording activation milestone
   INFO - ✓ Activation milestone recorded for ryan@winzinvest.com: firstAutomatedTrade
   ```

4. **Verify in dashboard:**
   - Log in → Admin → Growth
   - See your email with `firstTradeAt` timestamp
   - D7 activation count should increment

**If it fails:**
- Check `DASHBOARD_API_TOKEN` is set in `trading/.env`
- Check `INTERNAL_API_TOKEN` is set in Vercel (`vercel env ls`)
- Check account mapping file has your account ID
- Check dashboard logs: `vercel logs winzinvest.com`

---

## Troubleshooting

### Problem: "DASHBOARD_API_TOKEN not set"

**Fix:** Add to `trading/.env`:
```bash
DASHBOARD_API_TOKEN=your_secure_token_here
```

Then restart any running trading scripts (they load `.env` at import time).

---

### Problem: "Account U1234567 not mapped to user email"

**Fix:** Add your account ID to `trading/config/account_user_map.json`:
```json
{
  "U1234567": "your-email@example.com"
}
```

The email must match your dashboard login email exactly.

---

### Problem: Dashboard API returns 401 "Invalid API token"

**Fix:** Verify both sides have the same token:

```bash
# Check trading system
cd trading
cat .env | grep DASHBOARD_API_TOKEN

# Check Vercel
cd trading-dashboard-public
vercel env ls
```

They must match character-for-character.

---

### Problem: Activation records every time script runs (not just first trade)

**Cause:** Local state file is being deleted or not persisting.

**Fix:** Check that `trading/logs/dashboard_activation_state.json` is writable and persists across runs. It should accumulate emails over time:

```json
{
  "recorded_users": [
    "ryan@winzinvest.com",
    "alice@example.com"
  ]
}
```

If this file is on Google Drive sync, make sure it's not being reverted.

---

### Problem: "Failed to record activation (non-critical): ConnectionError"

**Cause:** Dashboard is down or unreachable from trading system.

**Impact:** None — trades still execute. Metrics just won't update.

**Fix:** Check dashboard is reachable:
```bash
curl -I https://winzinvest.com
```

If dashboard is down, activation tracking queues in local state. Next time a trade runs and dashboard is up, it will catch up.

---

## Multi-User Setup (Future)

When you have multiple paying customers (not just yourself):

### 1. Each User Gets Their Own IBKR Account

You'll need sub-accounts or separate IB accounts per user.

**Update mapping:**
```json
{
  "U1111111": "customer-a@example.com",
  "U2222222": "customer-b@example.com",
  "U3333333": "customer-c@example.com"
}
```

### 2. Executor Scripts Need User Context

Current scripts assume single-user (your account). For multi-user:

**Option A: Per-User Execution Runs**
- Run `execute_mean_reversion.py --account U1111111`
- Each run targets one account
- Activation tracked per run

**Option B: Multi-Account Aggregation**
- Query all sub-accounts in one run
- Track which account each fill belongs to
- Batch activation call with all unique emails

This is a future problem — don't over-engineer now. Current single-user setup is correct for the Founding Member phase (you're the only user).

---

## Security Notes

### API Token Storage

- ✅ Store in `.env` files (excluded from git via `.gitignore`)
- ✅ Rotate token quarterly or after any leak
- ❌ Never commit token to git
- ❌ Never log token in plaintext

### Email in Logs

The integration logs user emails at INFO level. This is fine for single-user.

For multi-user (GDPR compliance), consider:
- Redacting emails in logs (`r***@example.com`)
- Using user IDs instead of emails in logs
- Storing only the last 7 days of activation logs

---

## Monitoring

### Check Activation State

```bash
cat trading/logs/dashboard_activation_state.json
```

Shows which users have had activation recorded (prevents duplicate API calls).

### Check Dashboard Logs (Vercel)

```bash
cd trading-dashboard-public
vercel logs winzinvest.com --limit 50 | grep activation
```

Look for:
- `"✓ Activation milestone recorded"` (success)
- `"Invalid API token"` (token mismatch)
- `"User not found"` (email not in dashboard DB)

---

## Summary Checklist

Before running executors with activation tracking:

- [ ] IBKR account ID obtained (from TWS or `ib.managedAccounts()`)
- [ ] `trading/config/account_user_map.json` created with your account → email
- [ ] `DASHBOARD_API_TOKEN` set in `trading/.env`
- [ ] `INTERNAL_API_TOKEN` set in Vercel (`vercel env add`)
- [ ] Tokens match on both sides
- [ ] Self-test passes (`python3 dashboard_integration.py`)
- [ ] Dashboard is reachable (`curl -I https://winzinvest.com`)

After the first trade executes:

- [ ] Activation call appears in trading script logs
- [ ] Your email appears in `/admin/growth` with `firstTradeAt` timestamp
- [ ] D7 activation count increments

---

## Next Steps

Once activation tracking is confirmed working:

1. **Add lifecycle emails** — D3, D7, D14 nudges based on activation status
2. **Behavior segmentation** — track user patterns (frequent checker vs set-and-forget)
3. **Discipline streak** — days without overriding stops (gamification with safety)

See `PRODUCTIZATION_ROADMAP.md` for full implementation sequence.
