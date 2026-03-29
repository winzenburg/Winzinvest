# Vercel Database Connection Fix

The waitlist API is failing with "Could not add you to the waitlist" which means it can't connect to Supabase.

## Quick Fix: Use Supabase Connection Pooler

Vercel is a **serverless platform** and needs the connection pooler, not the direct connection.

### Get the Correct Connection String from Supabase

1. Go to: https://supabase.com/dashboard/project/jmzeqlerxixxdvkayycj/settings/database
2. Scroll to **"Connection string"** section
3. Look for **"Connection pooling"** tab (not "Direct connection")
4. Select **"Transaction"** mode
5. Copy the connection string

It should look like:
```
postgresql://postgres.jmzeqlerxixxdvkayycj:[PASSWORD]@aws-0-us-west-1.pooler.supabase.com:6543/postgres?pgbouncer=true
```

**Key differences from direct connection:**
- Port: `6543` (not `5432`)
- Hostname: Contains `.pooler.` 
- Parameter: `?pgbouncer=true`

### Update in Vercel

1. Go to: https://vercel.com/winzenburgs-projects/trading-dashboard-public/settings/environment-variables
2. Find `DATABASE_URL` (if it exists, edit it; if not, add it)
3. Replace with the **pooler connection string** from above
4. Save
5. **Redeploy** the latest deployment

---

## Alternative: Check if DATABASE_URL Was Added

If you haven't added `DATABASE_URL` to Vercel yet, that's the issue.

**Verify it exists:**
1. Go to Vercel environment variables page
2. Look for `DATABASE_URL` in the list
3. If it's missing → Add it
4. If it exists → Update it to use the pooler URL

---

## After Updating

Wait ~2 minutes for the redeploy, then test:

```bash
curl -X POST https://www.winzinvest.com/api/waitlist \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","tier":"intelligence"}'
```

**Expected:** `{"ok":true,"id":"..."}`

---

## Checklist

- [ ] Get **connection pooler** URL from Supabase (port 6543)
- [ ] Add/update `DATABASE_URL` in Vercel with pooler URL
- [ ] Add `NEXTAUTH_URL=https://winzinvest.com`
- [ ] Add `ADMIN_EMAIL=ryanwinzenburg@gmail.com`
- [ ] Add `NEXTAUTH_SECRET` (generate if needed)
- [ ] Redeploy from Vercel
- [ ] Test waitlist submission

---

## Connection Pooler vs Direct Connection

| Connection Type | Port | Use Case |
|----------------|------|----------|
| **Direct** | 5432 | Long-lived connections (your local dev, VPS) |
| **Pooler** | 6543 | Serverless (Vercel, Lambda, edge functions) |

**Vercel requires the pooler** because each request creates a new connection and serverless platforms can exhaust database connections without pooling.
