# Production Deployment Steps

## Status: Code Ready ✅

All code changes have been pushed to GitHub (main branch). Cloudflare Pages will auto-deploy from GitHub.

---

## 🚀 Deploy to Production (3 Steps)

### Step 1: Configure Cloudflare Pages Environment Variables

**Why**: The frontend needs to know where the Python backend API is located.

**Action**:
1. Go to https://dash.cloudflare.com/
2. Navigate: **Pages** → **winzinvest** → **Settings** → **Environment Variables**
3. Select **Production** environment
4. Add these two variables:

| Variable Name | Value |
|---|---|
| `TRADING_API_URL` | `https://myself-restrictions-decor-dealers.trycloudflare.com` |
| `TRADING_API_KEY` | `5e3aaab9cf9738b34926df0fc8eac10015ac450cb50b331931850e15b5e396a2` |

5. Click **Save**

---

### Step 2: Trigger Deployment

**Option A: Automatic (Recommended)**
- Cloudflare Pages auto-deploys when you push to GitHub
- Your latest push should trigger a build automatically
- Check: **Deployments** tab → Look for "In progress" or recent build

**Option B: Manual (If auto-deploy didn't trigger)**
1. Go to **Deployments** tab
2. Click **Create deployment** button
3. Select branch: **main**
4. Click **Deploy**

**Option C: Retry Latest Build**
1. Go to **Deployments** tab
2. Find the latest deployment
3. Click **⋯** (three dots) → **Retry deployment**

---

### Step 3: Verify Production

Once deployment completes (~2-3 minutes):

**Test 1: Health Check**
```bash
curl https://www.winzinvest.com/api/health
# Should return 200 OK
```

**Test 2: Dashboard Access**
1. Visit https://www.winzinvest.com/dashboard
2. Login with your credentials
3. Check these components:

#### ✅ Visualizations Working
- [ ] **Equity Curve** displays with data points and drawdown line
- [ ] **Correlation Heatmap** shows symbol matrix
- [ ] **Strategy Attribution** table loads
- [ ] **Analytics** section shows stats

#### ✅ Mode Toggle Working
- [ ] Only **ONE** toggle visible (not two)
- [ ] Shows "LIVE" with red badge (if Gateway is on port 4001)
- [ ] Clicking toggle switches modes smoothly
- [ ] Data updates when switching modes

#### ✅ No Errors
- [ ] No "Failed to fetch" errors
- [ ] No console errors in browser DevTools
- [ ] All dashboard sections load

---

## 🔧 If Visualizations Don't Load

### Check 1: Backend API is Running
```bash
# From your local machine:
curl https://myself-restrictions-decor-dealers.trycloudflare.com/health

# Should return:
# {"status":"ok","timestamp":"...","service":"winzinvest-dashboard-api"}
```

If this fails, restart the backend:
```bash
./start_dashboard_backend.sh
```

### Check 2: Environment Variables Are Set
1. Go to Cloudflare Pages → Settings → Environment Variables
2. Verify both `TRADING_API_URL` and `TRADING_API_KEY` are present
3. Verify they're in the **Production** environment (not Preview)

### Check 3: Deployment Used Latest Code
1. Go to Cloudflare Pages → Deployments
2. Check the commit hash matches your latest GitHub commit
3. If not, trigger a new deployment

---

## ⚠️ Important Notes

### Tunnel URL Changes
The tunnel URL (`https://myself-restrictions-decor-dealers.trycloudflare.com`) changes every time you restart the tunnel. This means:

**For Production** (Long-term solution):
You should set up a **persistent tunnel** or use a **static backend URL**:

```bash
# Create a named tunnel (one-time)
cloudflared tunnel create winzinvest-api
cloudflared tunnel route dns winzinvest-api api.winzinvest.com

# Then run it
cloudflared tunnel run winzinvest-api
```

This gives you a stable URL like `https://api.winzinvest.com` that never changes.

**For Now** (Quick testing):
- Keep `./start_dashboard_backend.sh` running
- If you restart it, update the Cloudflare Pages env var with the new URL

### Security Note
The `DASHBOARD_API_KEY` in this guide was previously exposed in Git. After confirming production works, you should:
1. Rotate the key (generate new one in `trading/.env`)
2. Update Cloudflare Pages env var
3. Update your local `.env.local`

See `CREDENTIAL_ROTATION_GUIDE.md` for details.

---

## 📊 Deployment Checklist

- [x] Code pushed to GitHub
- [ ] Cloudflare Pages environment variables configured
- [ ] Deployment triggered and completed
- [ ] Dashboard accessible at winzinvest.com
- [ ] Visualizations loading correctly
- [ ] Mode toggle working
- [ ] No console errors

---

## 🆘 Troubleshooting

### "Invalid or missing API key" errors
- Check that `TRADING_API_KEY` is set correctly in Cloudflare Pages
- Make sure it matches the key in `trading/.env` (DASHBOARD_API_KEY)

### "Failed to fetch" or CORS errors
- Verify `TRADING_API_URL` is set in Cloudflare Pages
- Check that the tunnel is running: `curl $TRADING_API_URL/health`
- Verify CORS settings in `dashboard_api.py` allow `winzinvest.com`

### Mode toggle shows wrong mode
- The mode is read from the backend API
- Check `trading/config/active_mode.json` on your server
- Verify IB Gateway port (4001 = live, 4002 = paper)

### Visualizations show "No data"
- Check backend logs: `tail -f /tmp/dashboard_api.log`
- Verify data files exist: `ls -lh trading/logs/sod_equity_history.jsonl`
- Test endpoint directly: `curl $TUNNEL_URL/api/equity-history`

---

## Next Steps After Deployment

1. **Monitor** the first hour of production usage
2. **Test** all major features (trading, visualizations, mode switching)
3. **Set up** persistent tunnel (optional but recommended)
4. **Rotate** exposed credentials (see guide)
5. **Document** any production-specific configuration

---

## Quick Reference

**Backend API (Local)**:
- Start: `./start_dashboard_backend.sh`
- Port: 8888
- Tunnel: Changes on restart

**Frontend (Production)**:
- URL: https://www.winzinvest.com
- Auto-deploys: From GitHub main branch
- Platform: Cloudflare Pages

**Key Files**:
- Backend API: `trading/scripts/agents/dashboard_api.py`
- Frontend: `trading-dashboard-public/`
- Env Config: `trading/.env` (backend), Cloudflare Pages dashboard (frontend)
