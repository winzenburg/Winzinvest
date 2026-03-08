# Deployment Guide

## Static Export (Current Configuration)

This dashboard is configured for **static export** (`output: 'export'` in `next.config.js`).

### Build Static Site

```bash
cd trading-dashboard-public
npm run build
```

This creates a static site in the `out/` directory with:
- `out/index.html` - Main dashboard
- `out/strategy.html` - Trading strategy page
- `out/journal.html` - Trading journal page

### Deploy Static Site

#### Option 1: Vercel (Recommended)

1. Go to https://vercel.com
2. Click "Add New Project"
3. Import from GitHub: `winzenburg/MissionControl`
4. Configure:
   - **Framework Preset**: Next.js
   - **Root Directory**: `trading-dashboard-public`
   - **Build Command**: `npm run build`
   - **Output Directory**: `out`
5. Click "Deploy"

#### Option 2: GitHub Pages

```bash
# Build static site
npm run build

# Deploy to gh-pages branch
npx gh-pages -d out
```

Then enable GitHub Pages in repo settings pointing to `gh-pages` branch.

#### Option 3: Any Static Host

Upload the `out/` directory to:
- Netlify
- Cloudflare Pages
- AWS S3 + CloudFront
- Any web server

### Step 3: Custom Domain (Optional)

In Vercel project settings:
1. Go to "Domains"
2. Add your domain (e.g., `trading.cultivate-six.vercel.app`)
3. Follow DNS instructions

## Alternative: Deploy to Existing Cultivate Domain

If you want this at `https://cultivate-six.vercel.app/trading`:

### Option A: Monorepo (Recommended)

1. Move this folder into your Cultivate project:
   ```bash
   mv trading-dashboard-public ~/path/to/cultivate/apps/trading
   ```

2. Update Cultivate's `vercel.json`:
   ```json
   {
     "rewrites": [
       {
         "source": "/trading/:path*",
         "destination": "/apps/trading/:path*"
       }
     ]
   }
   ```

### Option B: Separate Subdomain

Keep as separate project, deploy to:
- `trading.cultivate-six.vercel.app`

## Environment Variables

In Vercel project settings, add:

```
# If using Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key

# If using authentication
NEXTAUTH_URL=https://your-domain.vercel.app
NEXTAUTH_SECRET=your-secret-key
```

## Post-Deployment

### Test the Deployment

```bash
curl https://your-domain.vercel.app/api/performance
```

Should return JSON with mock data.

### Set Up Data Sync

On your local machine (where trading system runs):

1. Create sync script (see README.md)
2. Add to crontab:
   ```bash
   */15 * * * * cd /path/to/trading && python scripts/sync_to_cloud.py
   ```

### Monitor

- **Vercel Dashboard**: Check deployments, logs, analytics
- **Uptime**: Use Vercel's built-in monitoring
- **Errors**: Check Vercel logs for any issues

## Troubleshooting

### Build Fails

Check Vercel build logs for:
- Missing dependencies
- TypeScript errors
- Environment variables

### Data Not Showing

1. Check API route: `/api/performance`
2. Verify database connection
3. Check sync script is running

### Slow Performance

1. Enable Vercel Analytics
2. Check bundle size: `npm run build`
3. Optimize images (if any)

## Cost

- **Vercel Hobby**: Free (up to 100GB bandwidth/month)
- **Vercel Pro**: $20/month (unlimited bandwidth)
- **Supabase**: Free tier (500MB database, 2GB bandwidth)

## Next Steps

1. ✅ Deploy to Vercel
2. ⏳ Set up database (Supabase)
3. ⏳ Create sync script
4. ⏳ Add authentication (optional)
5. ⏳ Custom domain (optional)
