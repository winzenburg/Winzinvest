# Waitlist System Deployment Guide

Complete checklist for deploying the waitlist onboarding system to production.

## Prerequisites

- [x] PostgreSQL database configured and accessible
- [x] Resend API key obtained
- [x] Domain verified in Resend (`winzinvest.com`)
- [x] NextAuth configured with admin email

---

## Step 1: Database Migration

Run the Prisma migration to create the `Waitlist` table:

```bash
cd trading-dashboard-public
npx prisma migrate dev --name add_waitlist_model
```

This will:
- Create the `Waitlist` table with all required fields
- Add indexes for efficient queries
- Generate the Prisma client with the new model

For production:
```bash
npx prisma migrate deploy
```

---

## Step 2: Environment Variables

Add the following to your `.env` file (local) and Vercel (production):

```bash
# Resend
RESEND_API_KEY=re_xxxxxxxxxxxxx
RESEND_AUDIENCE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# NextAuth (if not already set)
NEXTAUTH_URL=https://winzinvest.com
NEXTAUTH_SECRET=your-secret-here

# Admin Access
ADMIN_EMAIL=your-admin@email.com

# Database (if not already set)
DATABASE_URL=postgresql://user:password@host:5432/database
```

**Vercel:**
1. Go to project settings → Environment Variables
2. Add each variable above
3. Redeploy

---

## Step 3: Resend Audience Setup

1. Log in to [Resend Dashboard](https://resend.com/audiences)
2. Click "Create Audience"
3. Name: "Winzinvest Beta Waitlist"
4. Copy the Audience ID
5. Paste into `RESEND_AUDIENCE_ID` environment variable

---

## Step 4: Resend Email Automations

Follow the detailed instructions in [`RESEND_EMAIL_AUTOMATION.md`](./RESEND_EMAIL_AUTOMATION.md):

1. Create 4 automations (T+0, T+3, T+7, T+14 days)
2. Paste the HTML email templates
3. Set sender as `onboarding@winzinvest.com`
4. Test with a test email address

---

## Step 5: Domain Verification

In Resend dashboard → Domains:

1. Add `winzinvest.com`
2. Add DNS records (Resend provides the values):
   - TXT record for domain verification
   - DKIM record (CNAME)
   - SPF record (TXT)
   - DMARC record (TXT)
3. Wait for verification (usually 5-15 minutes)

---

## Step 6: Test the Full Flow

### 6.1 Test Waitlist Signup

1. Go to `https://winzinvest.com/landing`
2. Scroll to pricing section
3. Submit test email for each tier
4. Verify:
   - Success message shown
   - Entry appears in PostgreSQL `Waitlist` table
   - Contact appears in Resend audience
   - Welcome email (T+0) arrives immediately

### 6.2 Test Admin Panel

1. Log in with admin account
2. Navigate to `/admin/waitlist`
3. Verify entries appear
4. Test filters (status, tier)
5. Export CSV and verify format
6. Add a note to an entry and save

### 6.3 Test Invitation Flow

1. In admin panel, click "Send Invite" on a pending entry
2. Verify:
   - Status changes to "invited"
   - Invitation email arrives
   - Magic link is generated correctly
3. Click magic link in email
4. Complete onboarding form:
   - Enter name
   - Create password (min 8 chars)
   - Submit
5. Verify:
   - User account created in `User` table
   - Waitlist entry status updated to "active"
   - Can log in with new credentials

### 6.4 Test Edge Cases

- [ ] Submit duplicate email (should succeed silently)
- [ ] Try expired magic link (48+ hours old)
- [ ] Try invalid magic link token
- [ ] Try to access admin panel without admin role
- [ ] Submit waitlist form with invalid email
- [ ] Submit waitlist form with invalid tier

---

## Step 7: Post-Deployment Monitoring

### Daily Checks

- Review pending waitlist entries in admin panel
- Monitor Resend email delivery rates and bounces
- Check PostgreSQL for any database errors in logs

### Weekly Checks

- Review automation email open rates
- Analyze signup conversion by tier
- Export CSV for external analysis if needed

---

## Rollback Plan

If issues arise:

1. **Database:** Prisma migrations are reversible
   ```bash
   npx prisma migrate reset
   ```

2. **Resend:** Pause automations in dashboard (won't delete contacts)

3. **Frontend:** Revert changes:
   ```bash
   git revert HEAD
   git push
   ```

---

## Support & Troubleshooting

### "Email service not configured" error

- Check `RESEND_API_KEY` is set in environment
- Verify API key is active in Resend dashboard
- Check Resend account is not rate-limited

### "Unauthorized" in admin panel

- Verify logged-in user email matches `ADMIN_EMAIL` env var
- Check NextAuth session is valid
- Ensure `authOptions` is correctly imported

### Magic link expired/invalid

- Magic links expire after 48 hours
- Admin can resend invitation to generate new link
- Check `invitedAt` timestamp in database

### Duplicate contacts in Resend

- PostgreSQL enforces unique emails (primary source of truth)
- Resend sync failures are logged but non-blocking
- If sync fails, contact is still in PostgreSQL and can be manually added to Resend

---

## Files Created/Modified

| File | Purpose |
|------|---------|
| `prisma/schema.prisma` | Added `Waitlist` model |
| `app/api/waitlist/route.ts` | Updated to save to PostgreSQL + Resend |
| `app/api/admin/waitlist/route.ts` | Admin API for listing/updating entries |
| `app/admin/waitlist/page.tsx` | Admin UI for managing waitlist |
| `app/admin/waitlist/layout.tsx` | Admin auth wrapper |
| `app/api/admin/send-invitation/route.ts` | Invitation email sender |
| `app/api/verify-invitation/route.ts` | Magic link verification |
| `app/api/complete-onboarding/route.ts` | Account creation from invitation |
| `app/onboard/page.tsx` | Onboarding form UI |
| `docs/RESEND_EMAIL_AUTOMATION.md` | Email sequence templates |

---

## Next Steps (Optional Enhancements)

- Add email preview before sending from admin panel
- Implement bulk invitation sending
- Add analytics dashboard (signup rate, conversion funnel)
- Create waitlist referral system (viral growth)
- Add tier-specific onboarding content
- Implement A/B testing for email subject lines
