# Vercel Environment Setup

This guide configures Vercel to connect to your Python backend for visualizations and live data.

**Note**: Your site is hosted on **Vercel** (not Cloudflare Pages). The Cloudflare Tunnel is only used to expose your local Python backend API to the internet.

## Problem Summary

The dashboard visualizations (Equity Curve, charts, etc.) fail in production because:
- The Next.js frontend needs to call the Python backend API for data
- Vercel environment variables are not configured
- Without `TRADING_API_URL` and `TRADING_API_KEY`, the frontend tries local file access (which fails in production)

## Fix Applied

The Python backend (`dashboard_api.py`) has been updated to return visualization data in the correct format:
- `/api/equity-history` now returns `{ points: [...], count: N }` with computed drawdown values
- All endpoints are working correctly through the Cloudflare Tunnel

## Vercel Configuration

### Step 1: Access Environment Variables

1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Select your **winzinvest** project
3. Go to **Settings** → **Environment Variables**

### Step 2: Add Required Variables

Add these two variables to **Production** environment:

| Variable Name | Value | Purpose |
|---|---|---|
| `TRADING_API_URL` | `https://myself-restrictions-decor-dealers.trycloudflare.com` | Python backend URL |
| `TRADING_API_KEY` | `5e3aaab9cf9738b34926df0fc8eac10015ac450cb50b331931850e15b5e396a2` | Dashboard API authentication |

### Step 3: Redeploy

After adding the variables:
1. Go to **Deployments** tab
2. Click **⋯** (three dots) on the latest deployment
3. Click **Redeploy**
4. Wait for the build to complete (~2-3 minutes)

### Step 4: Verify

Once deployed, visit https://www.winzinvest.com/dashboard and check:
- ✅ Equity Curve displays with data
- ✅ Correlation Heatmap shows
- ✅ Strategy attribution loads
- ✅ Mode toggle shows correct mode (LIVE)

## Testing Locally (Optional)

To test the remote mode locally before deploying:

```bash
# In trading-dashboard-public/.env.local, add:
TRADING_API_URL=https://myself-restrictions-decor-dealers.trycloudflare.com
TRADING_API_KEY=5e3aaab9cf9738b34926df0fc8eac10015ac450cb50b331931850e15b5e396a2

# Restart dev server
cd trading-dashboard-public
npm run dev
```

The dashboard should now show "Remote mode" in the console and fetch data from the Python backend.

## Important Notes

### Tunnel URL Changes

The Cloudflare Tunnel URL (`https://myself-restrictions-decor-dealers.trycloudflare.com`) changes every time you restart the tunnel. This is fine for testing, but for production you should:

**Option A: Use the startup script (recommended)**
```bash
./start_dashboard_backend.sh
```
This script:
- Starts the dashboard API
- Starts the tunnel
- Extracts and displays the tunnel URL
- Provides copy-paste commands for Cloudflare Pages

**Option B: Use a persistent tunnel (future improvement)**
```bash
# Create a named tunnel (one-time setup)
cloudflared tunnel create winzinvest-api
cloudflared tunnel route dns winzinvest-api api.winzinvest.com

# Then use it
cloudflared tunnel run winzinvest-api
```

With a persistent tunnel, you get a stable URL that doesn't change between restarts.

### Security

The current `DASHBOARD_API_KEY` in this guide is the **exposed credential** from the previous Git commit. You should:
1. Rotate it immediately (update `trading/.env` and regenerate)
2. Update this guide with the new key
3. Update Cloudflare Pages with the new key

See `CREDENTIAL_ROTATION_GUIDE.md` for details.

### CORS

The Python backend (`dashboard_api.py`) already allows:
- `https://www.winzinvest.com`
- `https://winzinvest.com`
- `http://localhost:3000`

If you use a different domain, add it to the `allow_origins` list in `dashboard_api.py`.

## Verification Commands

Test all visualization endpoints:

```bash
# Set your API key
API_KEY="5e3aaab9cf9738b34926df0fc8eac10015ac450cb50b331931850e15b5e396a2"
TUNNEL_URL="https://myself-restrictions-decor-dealers.trycloudflare.com"

# Test each endpoint
curl -H "x-api-key: $API_KEY" "$TUNNEL_URL/health"
curl -H "x-api-key: $API_KEY" "$TUNNEL_URL/api/equity-history" | python3 -m json.tool | head -20
curl -H "x-api-key: $API_KEY" "$TUNNEL_URL/api/analytics" | python3 -m json.tool | head -20
curl -H "x-api-key: $API_KEY" "$TUNNEL_URL/api/strategy-attribution" | python3 -m json.tool | head -20
curl -H "x-api-key: $API_KEY" "$TUNNEL_URL/api/dashboard" | python3 -m json.tool | head -40
```

All should return valid JSON with data (not auth errors).
