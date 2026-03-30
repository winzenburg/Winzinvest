# Growth Features Test Checklist

Migration completed! Here's how to verify each feature works on production.

---

## ✅ Feature 1: Referral Mechanics

### Test the Flow

1. **Get a referral code from Supabase:**
   - Go to Supabase → Table Editor → `Waitlist` table
   - Pick any verified entry, copy its `referralCode` (8-character code like `A1B2C3D4`)

2. **Test referral signup:**
   - Visit `https://winzinvest.com/?ref=A1B2C3D4` (use your actual code)
   - Sign up with a NEW email
   - Check your email → click verification link

3. **Verify referral tracking worked:**
   - After verification, you should see the `WaitlistThankYou` component with:
     - Your own new referral code
     - Copy button
     - "0 people joined via your link" (initially)
   
4. **Check database:**
   - Go to Supabase → `Waitlist` table
   - Find the new entry → `referredBy` should show the original code
   - Find the original entry → `referralCount` should have incremented by 1

### Expected Results
- ✅ Referral code captured from URL
- ✅ New user created with `referredBy` populated
- ✅ Original user's `referralCount` incremented
- ✅ Thank you page shows shareable link

---

## ✅ Feature 2: PMF Survey Modal

### Test D14 Trigger

**Quick test (backdating a user):**

1. Go to Supabase → SQL Editor → Run:
   ```sql
   UPDATE "User" 
   SET "createdAt" = NOW() - INTERVAL '14 days' 
   WHERE email = 'your-test-email@example.com';
   ```

2. Log into https://winzinvest.com with that account

3. Visit `/institutional` dashboard

4. **Expected:** PMF survey modal appears with:
   - Main question: "How would you feel if you could no longer use Winzinvest?"
   - Three options (Very, Somewhat, Not disappointed)
   - Follow-up questions after selection

5. Complete the survey

6. **Verify in database:**
   ```sql
   SELECT * FROM "PmfSurvey" 
   WHERE "userId" = (SELECT id FROM "User" WHERE email = 'your-test-email@example.com');
   ```

7. Reload dashboard → modal should NOT appear again

### Expected Results
- ✅ Modal appears at D14
- ✅ Dismissible (stores in sessionStorage)
- ✅ Response saved to `PmfSurvey` table
- ✅ Never appears again after completion

---

## ✅ Feature 3: Activation Tracking

### Test API Endpoint

**Manual test (simulating trading system call):**

1. Get an auth session token:
   - Log into https://winzinvest.com
   - Open browser DevTools → Application → Cookies
   - Copy the `next-auth.session-token` value

2. Test the activation API:
   ```bash
   curl -X POST https://winzinvest.com/api/activation \
     -H "Content-Type: application/json" \
     -H "Cookie: next-auth.session-token=YOUR_TOKEN_HERE" \
     -d '{"milestone": "firstAutomatedTrade"}'
   ```

3. **Expected response:**
   ```json
   {"ok": true, "milestone": "firstAutomatedTrade", "recorded": true}
   ```

4. **Verify in database:**
   ```sql
   SELECT email, "firstAutomatedTradeAt", "createdAt"
   FROM "User"
   WHERE email = 'your-email@example.com';
   ```
   
   The `firstAutomatedTradeAt` should now have a timestamp.

5. Call the API again → `"recorded": false` (idempotent, doesn't overwrite)

### Expected Results
- ✅ API accepts the milestone
- ✅ Timestamp recorded in User table
- ✅ Idempotent (calling twice doesn't break anything)

---

## ✅ Feature 4: Admin Growth Dashboard

### Test Admin View

1. Make sure your account has `role = 'admin'` in Supabase:
   ```sql
   UPDATE "User" 
   SET role = 'admin' 
   WHERE email = 'your-email@example.com';
   ```

2. Visit https://winzinvest.com/admin/growth

3. **Expected view:**
   - **PMF Score card** showing:
     - Current score (0% initially, no surveys yet)
     - Target: 40%
     - Distribution bars (very/somewhat/not disappointed)
   - **D7 Activation Rate card** showing:
     - Current rate (0% initially)
     - Target: 60%
     - Total activated vs never activated counts
   - **User Activation Table** with:
     - Email, signup date, days active
     - First trade timestamp
     - Days to activate
     - Status badges (Activated/Pending/At Risk)

### Expected Results
- ✅ Page loads (no auth errors)
- ✅ Shows metric cards with targets
- ✅ Table displays all users
- ✅ Color coding (green/yellow/red) based on targets

---

## Integration Test: Full Waitlist → Referral Flow

End-to-end test of the growth loop:

1. **Alice signs up:**
   - Visit https://winzinvest.com/landing
   - Join Founding Member waitlist with email: `alice@test.com`
   - Verify email via link
   - See thank you page with referral code: `ALICE123`
   - Copy referral link: `https://winzinvest.com/?ref=ALICE123`

2. **Alice shares link:**
   - Share on Twitter, Reddit, etc. (or just test yourself)

3. **Bob joins via Alice's link:**
   - Visit `https://winzinvest.com/?ref=ALICE123`
   - Sign up with email: `bob@test.com`
   - Verify email

4. **Check results:**
   - Alice's waitlist entry: `referralCount = 1`
   - Bob's waitlist entry: `referredBy = 'ALICE123'`, `source = 'referral'`
   - Bob also gets his own referral code to share

5. **Admin dashboard:**
   - Visit `/admin/growth`
   - Should see both Alice and Bob in the metrics

### Expected Results
- ✅ Referral code propagates through entire flow
- ✅ Count increments for referrer
- ✅ Source tagged as 'referral'
- ✅ New user gets their own code to continue the loop

---

## What to Watch For

### Issue: PMF Modal Not Showing
- Check user's `createdAt` (must be 14+ days ago)
- Check `PmfSurvey` table (must not have entry for that user)
- Clear sessionStorage in browser and refresh

### Issue: Referral Count Not Incrementing
- Check new user verified their email (`verifiedAt` not null)
- Check `referredBy` code matches an existing `referralCode`
- Check original user's `referralCount` field

### Issue: Activation Not Recording
- Check API auth (session or Bearer token)
- Check `milestone` value is exactly `"firstAutomatedTrade"`
- Check response: `recorded: true` means it worked

---

## Success Criteria

All three features work if:
- ✅ Referral link generates and tracks conversions
- ✅ PMF modal appears at D14 and saves responses
- ✅ Admin dashboard loads and shows metrics
- ✅ Activation API accepts timestamps without errors

**Next step:** Integrate activation tracking into your Python trading system (see `GROWTH_FEATURES_SUMMARY.md`).
