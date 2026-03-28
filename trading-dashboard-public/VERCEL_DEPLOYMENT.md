# Vercel Production Deployment Guide

## Current Status

- **Deployment URL**: https://mission-control-six-zeta.vercel.app/
- **Custom Domain**: winzinvest.com (pending DNS setup)
- **Branch**: main (auto-deploy on push)
- **Build**: Next.js 15.5.12

---

## Vercel Pro Setup (Recommended for Production)

### Why Upgrade to Pro

**Essential for commercial product:**
- **60s function timeout** (vs 10s free) - critical for PDF generation and dashboard data aggregation
- **Commercial license** - required for revenue-generating projects
- **Analytics** - real-time performance monitoring
- **Password protection** - protect staging/preview deployments
- **Priority support** - faster response when issues arise
- **100GB bandwidth** → **1TB bandwidth** - handles customer traffic without overages

**Cost**: $20/month per team member

### How to Upgrade

1. Go to [Vercel Dashboard](https://vercel.com/dashboard) → Settings → Billing
2. Select **Pro** plan
3. Upgrade takes effect immediately

---

## Environment Variables (Production)

Set these in Vercel Dashboard → Your Project → Settings → Environment Variables:

### Required (Production)

```bash
# NextAuth - CRITICAL: generate new secret for production
NEXTAUTH_URL=https://winzinvest.com
NEXTAUTH_SECRET=<run: openssl rand -base64 32>

# Database (if using multi-user auth in production)
DATABASE_URL=postgresql://user:pass@host:5432/dbname?sslmode=require

# Email (Resend)
RESEND_API_KEY=re_your_production_key_here

# Social OAuth (if enabling)
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
FACEBOOK_CLIENT_ID=your_facebook_app_id
FACEBOOK_CLIENT_SECRET=your_facebook_app_secret
APPLE_CLIENT_ID=your_apple_service_id
APPLE_CLIENT_SECRET=your_apple_private_key_jwt
```

### Optional (Production)

```bash
# Trading health service (if deploying separately)
TRADING_HEALTH_URL=https://health.winzinvest.com

# Analytics
NEXT_PUBLIC_POSTHOG_KEY=your_posthog_key
NEXT_PUBLIC_POSTHOG_HOST=https://app.posthog.com
```

### Local Development Only

```bash
# Bootstrap admin (DO NOT set in production)
ADMIN_EMAIL=admin@winzinvest.com
ADMIN_PASSWORD=your_local_password
```

---

## Custom Domain Setup

### 1. Add Domain in Vercel

1. Project → Settings → Domains
2. Add `winzinvest.com` and `www.winzinvest.com`
3. Vercel will provide DNS records

### 2. Configure DNS (at your registrar)

**A Records** (point to Vercel):
```
@     A     76.76.21.21
www   A     76.76.21.21
```

**Or CNAME** (recommended):
```
www   CNAME   cname.vercel-dns.com.
```

**Redirect root** (if using CNAME):
- Use your registrar's redirect feature: `winzinvest.com` → `www.winzinvest.com`

### 3. Enable HTTPS

- Vercel auto-provisions SSL via Let's Encrypt
- Redirect HTTP → HTTPS (automatic with Pro)

---

## Performance Optimizations (Now Active)

### Image Optimization

- **Format conversion**: AVIF → WebP → JPEG fallback
- **Responsive sizes**: 7 device breakpoints configured
- **Lazy loading**: automatic below the fold
- **Cache TTL**: 1 year for immutable assets

### Caching Strategy

| Resource | Cache Policy | Why |
|---|---|---|
| `/api/public-performance` | 5 min cache, 10 min stale | Live data updates every 5 min |
| `/api/*` (other) | No cache | Authentication-sensitive |
| Static assets | 1 year immutable | Versioned by Next.js |
| Illustrations | 1 year immutable | Won't change |

### Function Configuration

- **PDF generation route**: 60s timeout, 1024MB memory
- Handles full Puppeteer rendering for methodology PDF

### Security Headers (Global)

- `X-Content-Type-Options: nosniff` - prevents MIME sniffing
- `X-Frame-Options: SAMEORIGIN` - allows iframe only from same origin
- `X-XSS-Protection: 1; mode=block` - blocks reflected XSS
- `Referrer-Policy: strict-origin-when-cross-origin` - privacy
- `Permissions-Policy` - blocks camera/microphone/geolocation
- `Strict-Transport-Security` - forces HTTPS (HSTS preload eligible)

---

## Pre-Launch Checklist

### Before Going Live

- [ ] **Upgrade to Vercel Pro** ($20/mo)
- [ ] **Generate new `NEXTAUTH_SECRET`** for production (never reuse local dev secret)
- [ ] **Set up production database** (Neon, Supabase, or Railway for Postgres)
- [ ] **Configure Resend API** with production key
- [ ] **Add custom domain** (winzinvest.com)
- [ ] **Test all auth flows** (email/password, social, verification, password reset)
- [ ] **Verify PDF download** works in production
- [ ] **Check `/api/public-performance`** returns live data
- [ ] **Submit sitemap** to Google Search Console (`https://winzinvest.com/sitemap.xml`)
- [ ] **Test mobile responsiveness** on real devices
- [ ] **Run Lighthouse audit** (target: 90+ performance, 100 SEO)

### Optional Enhancements

- [ ] **Google Analytics / PostHog** - track visitor behavior
- [ ] **Sentry** - error monitoring for production
- [ ] **LogDNA / Datadog** - centralized logging
- [ ] **Cloudflare** - add as reverse proxy for DDoS protection (keep Vercel as origin)

---

## Monitoring & Alerts

### Vercel Analytics (Pro)

- Real-time traffic and performance
- Core Web Vitals tracking (LCP, FID, CLS)
- Function execution times
- Bandwidth usage

### Set Up Alerts

1. Project → Settings → Notifications
2. Enable alerts for:
   - Deployment failures
   - Function errors
   - Bandwidth overages

### Health Checks

- **Dashboard health**: `/api/system-status` (authenticated)
- **Public health**: `/api/public-performance` (unauthenticated)
- Set up UptimeRobot or Pingdom to monitor every 5 min

---

## Troubleshooting Common Issues

### Build Failures

**Error**: `Type error: ...` during build
- **Fix**: Run `npm run build` locally first to catch TypeScript errors
- Check `vercel --logs` for full error

**Error**: PDF generation timeout (function > 10s)
- **Fix**: Upgrade to Pro for 60s timeout
- Or: Switch to external PDF service (PDFShift, CloudConvert)

### Performance

**Slow page loads**
- Enable Vercel Analytics to identify bottleneck
- Check `/api/dashboard` response time (should be < 500ms)
- Verify `dashboard_snapshot.json` is fresh (< 5 min old)

**Images not loading**
- Verify files exist in `public/illustrations/`
- Check Vercel build logs for "File not found" warnings

### Authentication

**Session not persisting**
- Verify `NEXTAUTH_SECRET` is set in production env
- Check `NEXTAUTH_URL` matches your domain exactly
- Ensure database is accessible (if using PrismaAdapter)

---

## Cost Estimates

### Vercel Pro

- **Base**: $20/mo per seat
- **Bandwidth**: 1TB included (then $40/100GB)
- **Function executions**: Unlimited (60s max duration)
- **Builds**: Unlimited

### Expected Monthly Cost

**Pre-launch** (development): $20/mo  
**Post-launch** (< 1K visitors/mo): $20-30/mo  
**Growth** (5K visitors/mo): $40-60/mo  
**Scale** (20K visitors/mo): $100-150/mo

For comparison: Cloudflare Pages + Workers would be ~$5-10/mo at similar scale, but requires migration effort.

---

## When to Consider Cloudflare

Migrate to Cloudflare if:
- Hosting costs exceed **$150/mo** consistently
- You need **global edge performance** (international customers)
- You want **built-in DDoS protection** without third-party tools
- You're comfortable with **Next.js adapter** quirks

**Not worth migrating if**: You're under $100/mo and iteration speed matters more than cost optimization.

---

## Support Resources

- **Vercel Docs**: https://vercel.com/docs
- **Next.js Deployment**: https://nextjs.org/docs/deployment
- **Vercel Support**: support@vercel.com (Pro gets priority)
- **Community**: https://github.com/vercel/next.js/discussions
