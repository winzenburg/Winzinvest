# Growth Features Deployment Guide

This guide covers deploying the P0 growth features: PMF survey, activation tracking, and referral mechanics.

## What Was Added

### 1. PMF Survey (Sean Ellis 40% Benchmark)
- **Component:** `app/components/PmfSurveyModal.tsx`
- **API:** `app/api/pmf-survey/route.ts`
- **Database:** `PmfSurvey` table
- **Trigger:** Shows at D14 if user hasn't completed it
- **Admin view:** `app/admin/growth/page.tsx` shows PMF score

### 2. Activation Tracking
- **API:** `app/api/activation/route.ts`
- **Database:** `User.firstAutomatedTradeAt`, `User.activationCompletedAt`
- **Metric:** % of users who place first automated trade within 7 days (target: 60%)
- **Integration point:** Trading system should call `/api/activation` when placing user's first order

### 3. Referral Mechanics
- **Database:** `Waitlist.referralCode`, `Waitlist.referredBy`, `Waitlist.referralCount`
- **Flow:** User joins waitlist → verifies email → gets referral link → shares → friends join → original user's referral count increments
- **Reward:** Each verified referral moves user up 10 spots in waitlist (implement in admin invite flow)
- **Component:** `app/components/WaitlistThankYou.tsx` shows after verification

---

## Pre-Deployment Steps

### 1. Run Database Migration

**On Vercel (or wherever your Postgres lives):**

```bash
npx prisma migrate deploy
```

This applies the migration in `prisma/migrations/20260329221106_add_growth_features/migration.sql`.

**What it does:**
- Adds `firstAutomatedTradeAt`, `activationCompletedAt` to `User` table
- Adds `referralCode`, `referredBy`, `referralCount` to `Waitlist` table
- Creates `PmfSurvey` table with foreign key to `User`
- Adds indexes for performance

### 2. Backfill Referral Codes (Optional)

Existing waitlist entries won't have referral codes. Run this SQL to generate them:

```sql
UPDATE "Waitlist"
SET "referralCode" = UPPER(SUBSTRING(MD5(RANDOM()::text) FROM 1 FOR 8))
WHERE "referralCode" IS NULL;
```

### 3. Verify Environment Variables

Make sure these are set in Vercel:

```
DATABASE_URL=postgres://...
NEXTAUTH_URL=https://winzinvest.com
RESEND_API_KEY=re_...
```

---

## Post-Deployment Testing

### 1. Test Waitlist Referral Flow

1. Go to `https://winzinvest.com/?ref=ABC12345` (use a real referral code from DB)
2. Sign up with a new email
3. Verify email via the link sent
4. Should see the `WaitlistThankYou` component with:
   - Your referral code
   - Copy button
   - Referral count (should show 0 initially)
5. Check database: new user should have `referredBy: 'ABC12345'`
6. Original user's `referralCount` should increment by 1

### 2. Test PMF Survey Modal

1. Manually set a test user's `createdAt` to 14 days ago:
   ```sql
   UPDATE "User" SET "createdAt" = NOW() - INTERVAL '14 days' WHERE email = 'test@example.com';
   ```
2. Log in as that user
3. Visit `/institutional` dashboard
4. PMF survey modal should appear
5. Complete the survey
6. Check database: `PmfSurvey` record should exist
7. Revisit dashboard: modal should not appear again

### 3. Test Activation Tracking

**Manual test (until trading integration is added):**

```bash
curl -X POST https://winzinvest.com/api/activation \
  -H "Content-Type: application/json" \
  -H "Cookie: next-auth.session-token=..." \
  -d '{"milestone": "firstAutomatedTrade"}'
```

Expected: `User.firstAutomatedTradeAt` set to current timestamp.

**Future integration:** Add this call to the trading system's order execution flow:

```python
# In trading/scripts/execute_*.py after confirmed fill:
import requests
import os

def record_activation(user_email: str):
    """Call Next.js API to record first automated trade."""
    try:
        response = requests.post(
            f"{os.getenv('DASHBOARD_URL')}/api/activation",
            json={"milestone": "firstAutomatedTrade"},
            headers={"Authorization": f"Bearer {os.getenv('API_TOKEN')}"},
            timeout=5,
        )
        if response.ok:
            logger.info("Activation recorded for %s", user_email)
    except Exception as e:
        logger.warning("Failed to record activation: %s", e)
```

---

## Monitoring

### PMF Score
- **Target:** 40%+ "Very disappointed"
- **Check frequency:** Weekly during Founding Member phase, monthly after
- **Admin URL:** `https://winzinvest.com/admin/growth`

### Activation Rate
- **Target:** 60%+ D7 activation (first trade within 7 days)
- **Check frequency:** Daily for first 90 days
- **Admin URL:** `https://winzinvest.com/admin/growth`

### Referral Growth
- **Target:** 30%+ of new signups from referrals by Month 3
- **Check frequency:** Weekly
- **Query:**
  ```sql
  SELECT 
    COUNT(*) FILTER (WHERE source = 'referral') * 100.0 / COUNT(*) as referral_pct
  FROM "Waitlist"
  WHERE "verifiedAt" >= NOW() - INTERVAL '7 days';
  ```

---

## Troubleshooting

### PMF Modal Not Showing

Check:
1. User has been active for 14+ days (`User.createdAt`)
2. User hasn't already completed survey (`PmfSurvey` table has no record for that `userId`)
3. Modal wasn't dismissed today (check `sessionStorage` in browser: `pmfSurveyDismissed`)
4. Dashboard API is returning `user` object with `createdDaysAgo` and `hasTakenPmfSurvey`

### Referral Code Not Appearing

Check:
1. Waitlist entry has `referralCode` set (should auto-generate on signup)
2. Email verification completed (`verifiedAt` is not null)
3. `/api/waitlist-status` endpoint returns `referralUrl`

### Activation Not Recording

Check:
1. API call to `/api/activation` is being made (check Next.js logs)
2. User is authenticated (session exists)
3. Trading system has `DASHBOARD_URL` and `API_TOKEN` env vars set
4. Network connectivity between trading system and dashboard

---

## Rollback Plan

If something breaks:

1. **Database:** Migrations are forward-only, but you can manually drop tables/columns if needed:
   ```sql
   DROP TABLE "PmfSurvey";
   ALTER TABLE "User" DROP COLUMN "firstAutomatedTradeAt";
   ALTER TABLE "User" DROP COLUMN "activationCompletedAt";
   ALTER TABLE "Waitlist" DROP COLUMN "referralCode";
   ALTER TABLE "Waitlist" DROP COLUMN "referredBy";
   ALTER TABLE "Waitlist" DROP COLUMN "referralCount";
   ```

2. **Code:** Revert the git commit and redeploy

3. **Partial rollback:** You can disable features individually:
   - PMF modal: Remove from `app/institutional/page.tsx` render
   - Referral: Skip reading `?ref` param in `WaitlistForm.tsx`
   - Activation: Stop calling `/api/activation` from trading system
