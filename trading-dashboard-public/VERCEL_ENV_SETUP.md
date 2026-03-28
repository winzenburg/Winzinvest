# Vercel Environment Variables Setup

## Quick Setup: Enable Bootstrap Admin on Production

To make your admin login work on winzinvest.com without OAuth or database:

### 1. Go to Vercel Dashboard

https://vercel.com/dashboard → Your Project → Settings → Environment Variables

### 2. Add These Variables (Production Only)

Click "Add Another" for each:

| Key | Value | Environment |
|-----|-------|-------------|
| `NEXTAUTH_SECRET` | (see below) | Production |
| `NEXTAUTH_URL` | `https://www.winzinvest.com` | Production |
| `ADMIN_EMAIL` | `admin@winzinvest.com` | Production |
| `ADMIN_PASSWORD` | `1W!ll1st0n` | Production |

### 3. Generate NEXTAUTH_SECRET

**CRITICAL**: Never reuse your local dev secret in production. Generate a new one:

```bash
openssl rand -base64 32
```

Copy the output and paste it as the `NEXTAUTH_SECRET` value.

### 4. Redeploy

After adding all env vars:
1. Go to Deployments tab
2. Click "..." menu on latest deployment
3. Select "Redeploy"

Or just wait - the next commit will auto-deploy with the new env vars.

---

## What This Enables

- Sign in at https://www.winzinvest.com/login with:
  - Email: `admin@winzinvest.com`
  - Password: `1W!ll1st0n`
- Access to `/dashboard` with live trading data
- No database or OAuth required

---

## Security Notes

**This setup is secure for initial deployment:**
- Bootstrap admin is only you (single user)
- Password is not exposed in code (only in Vercel env vars)
- Session is JWT-based (no database needed)

**When to migrate to full auth:**
- When adding additional users
- When going fully public with customer accounts
- For multi-user team access

---

## Alternative: Set via Vercel CLI

If you prefer command line:

```bash
# Install Vercel CLI
npm i -g vercel

# Login
vercel login

# Link to your project
cd trading-dashboard-public
vercel link

# Set environment variables
vercel env add NEXTAUTH_SECRET production
# (paste the value from openssl rand -base64 32)

vercel env add NEXTAUTH_URL production
# (paste: https://www.winzinvest.com)

vercel env add ADMIN_EMAIL production
# (paste: admin@winzinvest.com)

vercel env add ADMIN_PASSWORD production
# (paste: 1W!ll1st0n)
```

---

## Production-Ready Checklist

- [ ] Added `NEXTAUTH_SECRET` (new, generated for production)
- [ ] Added `NEXTAUTH_URL=https://www.winzinvest.com`
- [ ] Added `ADMIN_EMAIL=admin@winzinvest.com`
- [ ] Added `ADMIN_PASSWORD=1W!ll1st0n`
- [ ] Redeployed or pushed new commit
- [ ] Tested login at https://www.winzinvest.com/login
- [ ] Verified `/dashboard` loads correctly after login

---

Once these are set, you'll be able to sign in on the live site immediately!
