# Waitlist & Onboarding System

Complete beta testing waitlist with automated email sequences and magic link invitations.

## Features

- **Public Waitlist Form:** Embedded on landing page, captures email + tier selection
- **PostgreSQL Storage:** Source of truth for all signups with status tracking
- **Resend Integration:** Automated drip email sequence (4 emails over 14 days)
- **Admin Dashboard:** View, filter, and manage signups with CSV export
- **Magic Link Invitations:** Secure, time-limited onboarding links
- **Account Creation:** Self-service account setup from invitation

---

## Architecture

```
User Submits Email
    ↓
/api/waitlist (PostgreSQL save + Resend sync)
    ↓
Resend Automation (T+0, T+3, T+7, T+14 emails)
    ↓
Admin Approves → /api/admin/send-invitation
    ↓
Magic Link Email → User clicks
    ↓
/onboard page (verify token)
    ↓
/api/complete-onboarding (create User account)
    ↓
Waitlist status → "active"
```

---

## User Flow

### 1. Signup

User visits `winzinvest.com/landing`, scrolls to pricing, and submits email with tier selection:
- Intelligence
- Automation
- Professional
- Founding Member

Form validates email format and tier, then posts to `/api/waitlist`.

### 2. Automated Emails

User receives 4 automated emails via Resend:
1. **T+0:** Welcome email confirming signup
2. **T+3:** "The Discipline Problem" - Why we built the system
3. **T+7:** "Inside the System" - How regime detection works
4. **T+14:** "You're in Our Next Wave" - Access coming soon

### 3. Admin Approval

Admin logs in, navigates to `/admin/waitlist`, reviews signups, and clicks "Send Invite" for approved users.

### 4. Invitation

User receives invitation email with:
- Personalized greeting
- Tier confirmation
- Magic link (valid 48 hours)

### 5. Onboarding

User clicks magic link → `/onboard?email=...&token=...`

Form verifies token validity and expiry, then prompts for:
- Full name
- Password (min 8 characters)
- Password confirmation

### 6. Account Creation

Upon submission:
- User account created in `User` table
- Waitlist status updated to "active"
- User redirected to `/login?registered=true`

---

## Database Schema

### Waitlist Table

```prisma
model Waitlist {
  id              String   @id @default(cuid())
  email           String   @unique
  tier            String
  status          String   @default("pending")
  source          String   @default("landing")
  metadata        Json?
  invitedAt       DateTime?
  invitationToken String?  @unique
  
  createdAt       DateTime @default(now())
  updatedAt       DateTime @updatedAt

  @@index([status, createdAt])
  @@index([email])
}
```

### Status Values

- `pending` - Awaiting admin review
- `invited` - Invitation sent, awaiting account creation
- `active` - Account created and active
- `rejected` - Not approved for beta

---

## API Routes

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/waitlist` | POST | None | Public signup form |
| `/api/admin/waitlist` | GET | Admin | List/filter entries |
| `/api/admin/waitlist` | PATCH | Admin | Update entry status/notes |
| `/api/admin/send-invitation` | POST | Admin | Send magic link invitation |
| `/api/verify-invitation` | POST | None | Validate magic link |
| `/api/complete-onboarding` | POST | None | Create user account |

---

## Admin Dashboard (`/admin/waitlist`)

Features:
- **Stats Cards:** Total, pending, invited, active counts
- **Filters:** By status, by tier
- **Actions:** Send invite, reject, add notes
- **Export:** Download CSV of all entries
- **Real-time:** Auto-refreshes after actions

Access restricted to users with email matching `ADMIN_EMAIL` environment variable.

---

## Security

- **Email Validation:** Regex + max length checks
- **Tier Validation:** Allowlist of valid tiers
- **Token Generation:** 32-byte crypto-random hex
- **Token Expiry:** 48 hours from invitation send time
- **Password Hashing:** bcryptjs with salt rounds
- **Admin Auth:** NextAuth session + email match
- **Rate Limiting:** (Recommended) Add middleware for `/api/waitlist`
- **CSRF Protection:** NextAuth built-in

---

## Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `RESEND_API_KEY` | Resend API authentication | Yes |
| `RESEND_AUDIENCE_ID` | Target audience for contacts | Yes |
| `NEXTAUTH_URL` | Base URL for magic links | Yes |
| `NEXTAUTH_SECRET` | NextAuth session encryption | Yes |
| `ADMIN_EMAIL` | Admin access control | Yes |

---

## Monitoring & Analytics

### Key Metrics to Track

- **Signup Rate:** New waitlist entries per day
- **Tier Distribution:** Which tier is most popular
- **Conversion Rate:** Invited → Active %
- **Email Performance:** Open rates, click rates per email
- **Time to Activate:** Days from signup to account creation
- **Rejection Rate:** Admin rejection %

### Logs to Monitor

- `/api/waitlist` errors (validation, database)
- `/api/admin/send-invitation` failures (Resend, database)
- `/api/complete-onboarding` errors (password, token)
- Resend delivery failures and bounces

---

## Resend Dashboard Setup

See [`RESEND_EMAIL_AUTOMATION.md`](./RESEND_EMAIL_AUTOMATION.md) for:
- Full HTML email templates
- Automation configuration steps
- Domain verification checklist
- Testing strategy

---

## Testing Checklist

- [ ] Submit valid email + tier → Entry in PostgreSQL
- [ ] Submit duplicate email → Silent success (no error)
- [ ] Submit invalid email → Validation error
- [ ] Receive welcome email immediately (T+0)
- [ ] Admin can view entries, filter by status/tier
- [ ] Admin can add notes and save
- [ ] Admin can export CSV
- [ ] Send invitation → Status changes to "invited"
- [ ] Invitation email arrives with magic link
- [ ] Magic link opens onboarding form with correct email
- [ ] Complete onboarding → User account created
- [ ] Waitlist status updated to "active"
- [ ] Expired magic link (48+ hours) → Error message
- [ ] Invalid token → Error message
- [ ] Non-admin cannot access `/admin/waitlist`

---

## Deployment

See [`WAITLIST_DEPLOYMENT.md`](./WAITLIST_DEPLOYMENT.md) for complete deployment checklist.

Quick start:
```bash
# 1. Run database migration
npx prisma migrate dev --name add_waitlist_model

# 2. Add environment variables to .env and Vercel

# 3. Set up Resend automations (see RESEND_EMAIL_AUTOMATION.md)

# 4. Deploy to Vercel
git push
```

---

## Support

For issues or questions:
- Check logs: `/api/*` routes log errors to console
- Verify environment variables are set correctly
- Ensure Resend domain is verified
- Confirm PostgreSQL connection is working
- Test with a known-good email first
