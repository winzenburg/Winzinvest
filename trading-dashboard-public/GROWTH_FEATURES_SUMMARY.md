# Growth Features - What Got Shipped

All 3 P0 items from the growth playbook are now live in code. You need to run the database migration to enable them.

---

## 1. PMF Survey (Sean Ellis)

### What It Does
Modal appears at Day 14 asking: "How would you feel if you could no longer use Winzinvest?"
- Very disappointed (target: 40%+)
- Somewhat disappointed
- Not disappointed

Follow-up questions capture ideal customer, main benefit, and improvement requests.

### Where It Lives
- **Component:** `app/components/PmfSurveyModal.tsx`
- **API:** `app/api/pmf-survey/route.ts` (POST to save, GET for admin metrics)
- **Database:** `PmfSurvey` table
- **Shown in:** Dashboard (`app/institutional/page.tsx`) at D14, D21, D30 if not completed
- **Admin view:** `app/admin/growth/page.tsx`

### What You See
- User logs in at D14 → modal appears
- Dismissible (will re-prompt at D21, D30)
- After submission, never shown again
- Admin dashboard shows PMF score: "42.5% / 40% target" (green if ≥40%)

### Target Metric
**40%+ "Very disappointed" = PMF achieved**

---

## 2. Activation Tracking

### What It Does
Tracks when a user hits their first automated trade. This is the core activation milestone.

### Where It Lives
- **API:** `app/api/activation/route.ts`
- **Database:** `User.firstAutomatedTradeAt`
- **Admin view:** `app/admin/growth/page.tsx` shows D7 activation rate

### Integration Point (TO DO)
Your **trading system** needs to call this API after executing a user's first order:

```python
# Add to trading/scripts/execute_*.py after confirmed fill
import requests
import os

def record_user_activation(user_email: str):
    """Record first automated trade for growth metrics."""
    try:
        response = requests.post(
            f"{os.getenv('DASHBOARD_URL', 'https://winzinvest.com')}/api/activation",
            json={"milestone": "firstAutomatedTrade"},
            headers={
                "Authorization": f"Bearer {os.getenv('DASHBOARD_API_TOKEN')}",
                "Content-Type": "application/json",
            },
            timeout=5,
        )
        if response.ok:
            logger.info("Activation milestone recorded for %s", user_email)
    except Exception as e:
        logger.warning("Failed to record activation (non-critical): %s", e)

# Call once per user after their first fill
if is_users_first_trade:
    record_user_activation(user_email)
```

You'll need to add:
- Mapping from IBKR account ID to user email (or user ID)
- Check in your DB to see if `firstAutomatedTradeAt` is already set (don't spam the API)

### Target Metric
**60%+ of users place first automated trade within 7 days**

---

## 3. Referral Mechanics

### What It Does
Every waitlist signup gets a unique referral code. Share link → friends join → referral count increments.

### Where It Lives
- **Database:** `Waitlist.referralCode` (8-char hex), `referredBy`, `referralCount`
- **API updates:** `app/api/waitlist/route.ts` (generates code, tracks referrals)
- **Status API:** `app/api/waitlist-status/route.ts` (returns referral URL and count)
- **Component:** `app/components/WaitlistThankYou.tsx` (shows after email verification)
- **Form:** `app/components/WaitlistForm.tsx` (accepts `?ref=CODE` param)

### User Flow
1. Alice joins waitlist → verifies email → sees her referral code: `A1B2C3D4`
2. Alice shares: `https://winzinvest.com/?ref=A1B2C3D4`
3. Bob clicks link → signs up → verifies email
4. Alice's `referralCount` increments by 1
5. Bob also gets his own referral code to share

### Reward Mechanic (TO DO - Admin Implementation)
**Target:** Each verified referral = move up 10 spots in waitlist

Right now the system **tracks** referrals but doesn't automatically **reorder** the waitlist. You'll need to implement the position-boost logic in your admin invite flow.

Suggested approach:
- When inviting users from waitlist, sort by: `(verifiedAt ASC) - (referralCount * 10)`
- Or: manually adjust position when sending invites

### Target Metric
**30%+ of new signups from referrals by Month 3**

---

## Deployment Checklist

### ✅ Done (Already Deployed)
- [x] Schema updated
- [x] Components built
- [x] API routes created
- [x] Admin dashboard built
- [x] Code pushed to production

### ⚠️ Required Next (Before Features Go Live)

1. **Run the database migration:**
   ```bash
   npx prisma migrate deploy
   ```
   This must run against your production Postgres database on Vercel.

2. **Backfill referral codes for existing waitlist entries:**
   ```sql
   UPDATE "Waitlist"
   SET "referralCode" = UPPER(SUBSTRING(MD5(RANDOM()::text) FROM 1 FOR 8))
   WHERE "referralCode" IS NULL;
   ```

3. **Test the flows:**
   - Waitlist signup with `?ref=CODE`
   - Email verification → see referral link
   - Admin login → visit `/admin/growth`
   - Mock a D14 user → see PMF survey modal

---

## Admin URLs (After Migration)

- **Growth Dashboard:** `https://winzinvest.com/admin/growth`
  - PMF score (requires admin role)
  - D7 activation rate
  - User activation timeline

- **PMF Survey Results:** GET `https://winzinvest.com/api/pmf-survey`
  - Returns aggregate score + distribution
  - Admin-only endpoint

- **Activation Metrics:** GET `https://winzinvest.com/api/activation`
  - Returns D7 activation rate + per-user timeline
  - Admin-only endpoint

---

## What Happens Automatically (No Action Required)

- **PMF survey** appears for any user at D14 who hasn't taken it
- **Referral codes** auto-generate on every new waitlist signup
- **WaitlistThankYou** component shows after email verification with copy-to-clipboard referral link
- **Referral tracking** increments when someone signs up via `?ref=CODE` and verifies email

---

## What You Need to Build Manually

### 1. Trading System Integration
Call `/api/activation` after user's first order executes. See integration code above.

### 2. Waitlist Position Boost Logic
Implement position adjustment in your admin invite flow:
```sql
-- Example query to get next users to invite (highest referral count first):
SELECT email, tier, "referralCount", "verifiedAt"
FROM "Waitlist"
WHERE status = 'pending'
ORDER BY "verifiedAt" ASC - (INTERVAL '1 day' * "referralCount" * 10)
LIMIT 10;
```

### 3. Email Nurture Sequence (P1 - Future)
- D0: Welcome + how to get started
- D3: First setup reminder
- D7: Activation nudge (if not activated)
- D14: PMF survey (backup to in-app modal)
- D30: Re-engagement (if churned)

---

## Key Numbers to Watch

| Metric | Target | Current | Status |
|---|---|---|---|
| PMF Score | 40%+ | TBD | Run survey at D14 |
| D7 Activation | 60%+ | TBD | Integrate trading system |
| Referral Rate | 30%+ | TBD | Track weekly |

Check `/admin/growth` weekly during the Founding Member phase. If PMF score is <25% after 20 responses, pause growth and iterate on the product experience.

---

## Migration Command (Run This Next)

SSH into Vercel or wherever your Postgres lives:

```bash
cd trading-dashboard-public
npx prisma migrate deploy
```

Then backfill referral codes for existing waitlist entries (SQL above).

That's it. Features are live once the migration runs.
