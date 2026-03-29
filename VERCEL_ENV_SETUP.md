# Vercel Environment Variables - Waitlist System

Add these environment variables to Vercel to complete the deployment.

## How to Add Environment Variables

1. Go to: https://vercel.com/winzenburgs-projects/trading-dashboard-public/settings/environment-variables
2. Click "Add New"
3. Enter each key/value pair below
4. Set environment to: **Production, Preview, and Development**
5. Click "Save"
6. Redeploy after adding all variables

---

## Required Environment Variables

### Core Application

```bash
NEXTAUTH_URL=https://winzinvest.com
```

### Database

```bash
DATABASE_URL=postgresql://postgres:PMgWZAgn5R_w2wZ@db.jmzeqlerxixxdvkayycj.supabase.co:5432/postgres
```

### Authentication & Admin Access

```bash
ADMIN_EMAIL=ryanwinzenburg@gmail.com
```

Replace with your actual email address - this email will have admin access to `/admin/waitlist`.

### NextAuth Secret (if not already set)

Generate with:
```bash
openssl rand -base64 32
```

Then add:
```bash
NEXTAUTH_SECRET=<generated-secret-here>
```

---

## Optional (Add Later When You Configure Resend)

These can be added later once you set up Resend for automated emails:

```bash
RESEND_API_KEY=re_xxxxxxxxxxxxx
RESEND_AUDIENCE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

**The waitlist system works WITHOUT these** - signups will save to PostgreSQL, but automated welcome emails won't send until Resend is configured.

---

## After Adding Variables

1. Go to Vercel deployments
2. Click "Redeploy" on the latest deployment
3. Wait for build to complete (~2 minutes)
4. Test at: https://winzinvest.com/landing

---

## Testing the Deployment

### 1. Test Public Waitlist
- Go to: https://winzinvest.com/landing
- Scroll to pricing section
- Submit a test email
- Should see success message

### 2. Check Database
- Go to Supabase → Table Editor → Waitlist
- Verify entry appears

### 3. Test Admin Panel
- Go to: https://winzinvest.com/admin/waitlist
- Log in with your admin email
- Should see the test entry

---

## Current Status

✅ Code deployed to GitHub  
⏳ Waiting for environment variables in Vercel  
⏳ Waiting for Vercel redeploy after env vars added  

Once you add the environment variables and redeploy, the waitlist system will be fully live!
