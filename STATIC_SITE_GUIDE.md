# Mission Control - Static Site Guide

The dashboard has two deployment modes:

---

## Mode 1: Dynamic (Vercel) - **CURRENT**

**Best for**: Real-time data from IBKR

**Features:**
- ✅ API routes work (`/api/dashboard`, `/api/alerts`, `/api/audit`)
- ✅ Real-time data from `dashboard_snapshot.json`
- ✅ Auto-refresh every 30 seconds
- ✅ Server-side data processing

**Configuration:**
```js
// next.config.js
const nextConfig = {
  reactStrictMode: true,
  // output: 'export',  // Disabled for API routes
  images: { unoptimized: true },
}
```

**Deploy to:**
- Vercel (recommended)
- Any Node.js hosting (Railway, Render, Fly.io)

**Deploy command:**
```bash
git push origin main  # Vercel auto-deploys
```

---

## Mode 2: Static Export (GitHub Pages)

**Best for**: Demo/portfolio site without real-time data

**Features:**
- ✅ No server required
- ✅ Deploy to GitHub Pages, Netlify, Cloudflare Pages
- ❌ No API routes (must use mock data)
- ❌ No real-time updates

**Configuration:**
```js
// next.config.js
const nextConfig = {
  reactStrictMode: true,
  output: 'export',  // Enable static export
  images: { unoptimized: true },
}
```

**Changes needed:**
1. Remove or comment out `export const dynamic = 'force-dynamic'` from all API routes
2. Update pages to use mock data instead of fetching from `/api/*`
3. Build with `npm run build` (creates `out/` directory)
4. Deploy `out/` directory to static host

---

## Current Status

**Current mode**: Dynamic (Vercel)  
**Deployed to**: https://mission-control-dashboard.vercel.app (or your Vercel URL)  
**Local dev**: http://localhost:3003

**Why not static?**
The institutional dashboard requires real-time data from IBKR via API routes. Static export would lose this functionality and show only mock data.

---

## If You Want Static Export

### Option A: Separate Static Branch

Create a `static` branch with mock data:

```bash
# Create static branch
git checkout -b static

# Update next.config.js to enable output: 'export'
# Update pages to use mock data instead of API calls
# Remove dynamic = 'force-dynamic' from API routes

# Build
npm run build

# Deploy out/ directory to GitHub Pages
```

### Option B: Two Separate Projects

Keep two versions:
1. **mission-control** (dynamic, Vercel) - Real-time data
2. **mission-control-static** (static, GitHub Pages) - Demo with mock data

---

## Recommended Approach

**Use dynamic deployment (Vercel)** for Mission Control because:

1. ✅ Real-time data from IBKR
2. ✅ API routes for data processing
3. ✅ Auto-refresh functionality
4. ✅ Institutional features work fully
5. ✅ Free on Vercel
6. ✅ Auto-deploys from GitHub

**Only use static export if:**
- You want a demo site without real data
- You don't need API routes
- You want to host on GitHub Pages
- You're okay with mock data only

---

## Current Deployment

**Status**: ✅ Pushed to GitHub  
**Commit**: `2a808e4` - Add Cultivate-inspired design system  
**Branch**: `main`  
**Vercel**: Will auto-deploy from main branch

**View on GitHub:**
```bash
gh repo view --web
```

**View on Vercel:**
Visit your Vercel dashboard to see the deployment status.

---

## Summary

Mission Control is deployed in **dynamic mode** with full API route support for real-time IBKR data. The design system and all institutional features are now live on GitHub and will auto-deploy to Vercel.

For a static demo version, create a separate branch with mock data and enable `output: 'export'`.
