# Waitlist System - Setup Checklist

Quick-start guide to get the waitlist system running in production.

## Prerequisites (Verify First)

- [x] PostgreSQL database running and accessible
- [ ] Resend account created (free tier works)
- [ ] Domain verified in Resend (`winzinvest.com`)
- [ ] Admin email set in environment

---

## Step 1: Database Migration (5 minutes)

Run this command in the `trading-dashboard-public` directory:

```bash
npx prisma migrate dev --name add_waitlist_model
```

This creates the `Waitlist` table with all required fields and indexes.

**Verify it worked:**
```bash
npx prisma studio
```
Open Prisma Studio and check that the `Waitlist` model appears.

---

## Step 2: Environment Variables (3 minutes)

### Local Development (`.env.local`)

Create or update `.env.local` in `trading-dashboard-public/`:

```bash
# Database (if not already set)
DATABASE_URL=postgresql://user:password@localhost:5432/winzinvest

# Resend
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
RESEND_AUDIENCE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# NextAuth (if not already set)
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=your-random-secret-here

# Admin Access
ADMIN_EMAIL=your@email.com
```

### Vercel Production

1. Go to Vercel project → Settings → Environment Variables
2. Add each variable above (use production values)
3. Set `NEXTAUTH_URL=https://winzinvest.com`
4. Redeploy

---

## Step 3: Resend Setup (10 minutes)

### 3.1 Get API Key
1. Go to [Resend API Keys](https://resend.com/api-keys)
2. Create new API key
3. Copy to `RESEND_API_KEY`

### 3.2 Create Audience
1. Go to [Resend Audiences](https://resend.com/audiences)
2. Click "Create Audience"
3. Name: "Winzinvest Beta Waitlist"
4. Copy Audience ID to `RESEND_AUDIENCE_ID`

### 3.3 Verify Domain
1. Go to [Resend Domains](https://resend.com/domains)
2. Add `winzinvest.com`
3. Add DNS records provided by Resend
4. Wait for verification (~5-15 minutes)

---

## Step 4: Email Automations (15 minutes)

Follow the complete guide in [`RESEND_EMAIL_AUTOMATION.md`](./RESEND_EMAIL_AUTOMATION.md).

Quick summary:
1. Create 4 automations in Resend dashboard
2. Set triggers to "Contact added to audience"
3. Set delays: 0 min, 3 days, 7 days, 14 days
4. Paste HTML email templates from the doc
5. Set sender: `onboarding@winzinvest.com`

---

## Step 5: Test Locally (10 minutes)

```bash
# Start dev server
cd trading-dashboard-public
npm run dev
```

### Test Checklist

1. **Public Signup:**
   - Go to `http://localhost:3000/landing`
   - Submit email with a tier
   - Check PostgreSQL `Waitlist` table for entry
   - Check Resend audience for contact

2. **Admin Panel:**
   - Log in with admin account
   - Go to `/admin/waitlist`
   - Verify entries appear
   - Test filters and CSV export

3. **Invitation Flow:**
   - Click "Send Invite" on a pending entry
   - Check email inbox for invitation
   - Click magic link
   - Complete onboarding form
   - Verify user created in `User` table
   - Verify can log in with new credentials

---

## Step 6: Deploy to Production (5 minutes)

```bash
git add .
git commit -m "Add waitlist onboarding system with automated email sequences"
git push
```

Vercel will automatically deploy. Monitor the deployment logs for any errors.

---

## Step 7: Post-Deployment Verification (5 minutes)

1. **Submit Test Signup:**
   - Go to `https://winzinvest.com/landing`
   - Submit a test email
   - Check PostgreSQL production database
   - Check Resend audience

2. **Verify Welcome Email:**
   - Check inbox for immediate welcome email
   - Verify sender is `onboarding@winzinvest.com`
   - Verify email renders correctly

3. **Test Admin Panel:**
   - Log in to production with admin account
   - Go to `/admin/waitlist`
   - Verify test entry appears

4. **Test Invitation:**
   - Send invitation to test entry
   - Click magic link
   - Complete onboarding
   - Verify can log in

---

## Common Issues & Fixes

### "Database error" when submitting waitlist form

**Cause:** `DATABASE_URL` not set or PostgreSQL not accessible

**Fix:**
```bash
# Verify connection
psql $DATABASE_URL -c "SELECT 1"

# Check Prisma client is generated
npx prisma generate
```

### "Email service not configured" in invitation

**Cause:** `RESEND_API_KEY` not set

**Fix:** Add to environment variables and redeploy

### "Unauthorized" in admin panel

**Cause:** Logged-in email doesn't match `ADMIN_EMAIL`

**Fix:** Set `ADMIN_EMAIL` to your actual login email

### Welcome email not arriving

**Cause:** Automation not configured or domain not verified

**Fix:**
1. Check Resend dashboard → Automations
2. Verify domain status in Resend → Domains
3. Check Resend logs for delivery errors

### Magic link shows "Invalid invitation"

**Cause:** Token expired (48 hours) or tampered

**Fix:** Admin can resend invitation to generate fresh token

---

## Monitoring After Launch

**Daily:**
- Check admin panel for new signups
- Review Resend email delivery rates
- Monitor PostgreSQL for errors

**Weekly:**
- Analyze signup rate trends
- Review tier distribution
- Check email open/click rates
- Batch invite approved users

**Monthly:**
- Export CSV for external analysis
- Review conversion funnel (signup → invite → active)
- Optimize email content based on engagement

---

## Next Steps (Optional)

After the system is stable, consider:
- Rate limiting on `/api/waitlist` (e.g., 3 signups per IP per day)
- Admin notification when new signup arrives
- Waitlist position number ("You're #47 on the list")
- Referral system (viral growth)
- A/B testing email subject lines
- Tier-specific onboarding content

---

## Files Reference

| File | Purpose |
|------|---------|
| [`prisma/schema.prisma`](../prisma/schema.prisma) | Database schema with `Waitlist` model |
| [`app/api/waitlist/route.ts`](../app/api/waitlist/route.ts) | Public signup endpoint |
| [`app/components/WaitlistForm.tsx`](../app/components/WaitlistForm.tsx) | Signup form component |
| [`app/admin/waitlist/page.tsx`](../app/admin/waitlist/page.tsx) | Admin dashboard UI |
| [`app/api/admin/waitlist/route.ts`](../app/api/admin/waitlist/route.ts) | Admin API |
| [`app/api/admin/send-invitation/route.ts`](../app/api/admin/send-invitation/route.ts) | Invitation sender |
| [`app/onboard/page.tsx`](../app/onboard/page.tsx) | Onboarding form |
| [`app/api/verify-invitation/route.ts`](../app/api/verify-invitation/route.ts) | Token validator |
| [`app/api/complete-onboarding/route.ts`](../app/api/complete-onboarding/route.ts) | Account creator |
| [`docs/RESEND_EMAIL_AUTOMATION.md`](./RESEND_EMAIL_AUTOMATION.md) | Email templates |
| [`docs/WAITLIST_DEPLOYMENT.md`](./WAITLIST_DEPLOYMENT.md) | Full deployment guide |
| [`docs/WAITLIST_README.md`](./WAITLIST_README.md) | System overview |

---

## Support

If you encounter issues not covered here, check:
1. Vercel deployment logs
2. PostgreSQL query logs
3. Resend delivery logs
4. Browser console for frontend errors

For development help: Refer to [WAITLIST_README.md](./WAITLIST_README.md)
