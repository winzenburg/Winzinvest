# Deployment Architecture

## Current Setup (March 2026)

Your trading dashboard is split across two services:

```
┌─────────────────────────────────────────────────────────────────┐
│                        PRODUCTION SETUP                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐                          ┌─────────────────┐  │
│  │   Vercel     │                          │  Local Machine  │  │
│  │ (Frontend)   │ ─── API calls ────────> │  (Backend API)  │  │
│  │              │      via tunnel          │                 │  │
│  │ winzinvest   │                          │  Python         │  │
│  │    .com      │                          │  FastAPI        │  │
│  │              │                          │  Port 8888      │  │
│  └──────────────┘                          └─────────────────┘  │
│        │                                            ▲            │
│        │                                            │            │
│        └────────── Cloudflare Tunnel ──────────────┘            │
│           (exposes localhost:8888 to internet)                  │
│           https://[random].trycloudflare.com                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Components Breakdown

### 1. Frontend (Vercel)
- **What**: Next.js dashboard application
- **Hosted on**: Vercel (vercel.com)
- **Domain**: https://www.winzinvest.com
- **Deploys from**: GitHub repo (auto-deploy on push)
- **Needs**: `TRADING_API_URL` and `TRADING_API_KEY` env vars

### 2. Backend API (Your Local Machine)
- **What**: Python FastAPI server (`dashboard_api.py`)
- **Runs on**: Your Mac (localhost:8888)
- **Purpose**: Serves live trading data, account info, visualizations
- **Access**: IB Gateway (port 4001/4002), filesystem, SQLite DB

### 3. Cloudflare Tunnel (Connection Bridge)
- **What**: Secure tunnel that exposes localhost:8888 to the internet
- **Why**: Vercel (frontend) can't reach your local machine directly
- **URL**: `https://[random].trycloudflare.com` (changes on restart)
- **Command**: `cloudflared tunnel --url http://localhost:8888`

---

## Why This Architecture?

**Q: Why not run the Python backend on Vercel too?**

A: The Python backend needs:
- Direct access to IB Gateway (running locally)
- Direct filesystem access to `trading/logs/` and `trading/config/`
- SQLite database access (`trading/logs/trades.db`)
- Low latency to IB Gateway for real-time data

Running it locally is simpler and faster than deploying to a remote server.

---

## Configuration for Each Service

### Vercel Environment Variables (Production)
```
TRADING_API_URL = https://myself-restrictions-decor-dealers.trycloudflare.com
TRADING_API_KEY = 5e3aaab9cf9738b34926df0fc8eac10015ac450cb50b331931850e15b5e396a2

# Plus all your existing vars:
NEXTAUTH_SECRET = (your secret)
NEXTAUTH_URL = https://winzinvest.com
DATABASE_URL = (your Postgres)
# ... etc
```

### Local Backend (.env files)
- `trading/.env`: All trading config (IB ports, Telegram, API keys)
- `trading-dashboard-public/.env.local`: Dev server config (includes TRADING_API_URL for testing)

---

## Deployment Flow

1. **You push code** to GitHub (main branch)
2. **Vercel auto-detects** the push and starts building
3. **Build completes** in 2-3 minutes
4. **Vercel deploys** to winzinvest.com
5. **Frontend makes API calls** to `$TRADING_API_URL` (your tunnel)
6. **Tunnel routes** requests to localhost:8888
7. **Backend responds** with live data

---

## What About Cloudflare Pages?

You have a `wrangler.toml` file, which suggests you experimented with Cloudflare Pages or might migrate there in the future. Currently:

- **Not using**: Cloudflare Pages for hosting
- **Using**: Cloudflare Tunnel (different product) for exposing backend

If you want to switch to Cloudflare Pages later, you can - the codebase supports both. Just update the deployment command and DNS.

---

## Local Testing vs Production

### Local Dev (http://localhost:3000)
- Reads `.env.local` for config
- Can use REMOTE mode (calls backend via tunnel) or LOCAL mode (reads files directly)
- Current: REMOTE mode configured

### Production (https://www.winzinvest.com)
- Reads environment variables from Vercel dashboard
- **Must** use REMOTE mode (can't access local filesystem)
- Requires `TRADING_API_URL` and `TRADING_API_KEY` to be set

---

## Backend Startup

**Automated** (recommended):
```bash
./start_dashboard_backend.sh
```

This script:
- Starts dashboard API on port 8888
- Starts Cloudflare Tunnel
- Displays the tunnel URL
- Provides copy-paste commands for Vercel

**Manual**:
```bash
# Terminal 1: Start API
cd trading/scripts/agents
python3 -m uvicorn dashboard_api:app --host 0.0.0.0 --port 8888

# Terminal 2: Start tunnel
cloudflared tunnel --url http://localhost:8888
```

---

## Common Issues

### "Tunnel URL changed"
The free Cloudflare Tunnel URL changes on every restart. When this happens:
1. Get new URL from tunnel output
2. Update `TRADING_API_URL` in Vercel settings
3. Redeploy on Vercel

**Better solution**: Set up a persistent tunnel with a custom subdomain (see guide).

### "Visualizations not loading"
Check:
1. Backend is running: `curl http://localhost:8888/health`
2. Tunnel is working: `curl https://[tunnel-url]/health`
3. Vercel has env vars set
4. Latest deployment used latest code

### "API key invalid"
- Verify `TRADING_API_KEY` in Vercel matches `DASHBOARD_API_KEY` in `trading/.env`
- No spaces or quotes around the key value

---

## Summary

**You need**:
- ✅ Vercel (for hosting frontend) - already configured
- ✅ Cloudflare Tunnel (for exposing backend) - already running
- ❌ Cloudflare Pages - NOT needed

**To deploy**:
1. Add 2 env vars to Vercel (not Cloudflare Pages)
2. Wait for auto-deploy or trigger manually
3. Done!
