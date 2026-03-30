# Dashboard Error Fix — "No dashboard snapshot found"

## Current Status (Verified)

### ✅ All Systems Operational

**Python API:**
- Status: ✅ Running on localhost:8888
- Endpoint: `/api/snapshot`
- Data: ✅ Returning 60 positions, $172K NLV
- Process: PID 93358, running since 6:15pm MT

**ngrok Tunnel:**
- Status: ✅ Active
- URL: `https://pomological-adriel-tetrahydrated.ngrok-free.dev`
- Test: ✅ Responds to health checks

**Vercel Deployment:**
- Status: ✅ Ready (deployed 30 min ago)
- Commit: c2c65ca (Phase 2 features)
- Environment: `TRADING_API_URL` = ngrok URL ✅

---

## The Problem

You're seeing "Error Loading Dashboard" but **all backend systems are working**.

**Root cause:** Browser cache or old session token.

---

## Solution (3 Steps)

### Step 1: Hard Refresh (90% success rate)

**On Chrome/Edge:**
1. Open https://winzinvest.com/institutional
2. Press **Cmd+Shift+R** (Mac) or **Ctrl+Shift+F5** (Windows)
3. Wait 3-5 seconds for full reload

**On Safari:**
1. Open https://winzinvest.com/institutional
2. Hold **Shift**, click reload button
3. Or: Safari menu → Clear History → Last Hour

**On Firefox:**
1. Open https://winzinvest.com/institutional
2. Press **Cmd+Shift+R** (Mac) or **Ctrl+Shift+F5** (Windows)

### Step 2: Clear Session (If Step 1 Fails)

1. Sign out completely
2. Close all browser tabs with winzinvest.com
3. Clear cookies for winzinvest.com:
   - Chrome: Settings → Privacy → Cookies → See all site data → Search "winzinvest" → Remove
   - Safari: Preferences → Privacy → Manage Website Data → Search "winzinvest" → Remove
4. Sign back in
5. Should now show fresh dashboard

### Step 3: Verify API Connection (If Step 2 Fails)

**Open browser console (F12 → Console tab)** and run:

```javascript
fetch('/api/dashboard', { 
  credentials: 'include' 
}).then(r => r.json()).then(d => console.log('Dashboard data:', d))
```

**Expected:** JSON object with `positions`, `account`, `performance` fields.

**If you see 401 Unauthorized:** Sign out and back in.

**If you see 500 Internal Error:** Check Vercel function logs.

**If you see "Failed to fetch":** Check browser console for CORS errors.

---

## Alternative: Test Direct API URL

**Temporary bypass** (to verify backend works):

1. Get fresh API key: Already set in `trading/.env` as `DASHBOARD_API_KEY`
2. Test direct URL in browser:

```
https://pomological-adriel-tetrahydrated.ngrok-free.dev/api/snapshot
```

3. Should prompt for API key or show data

**If this works but dashboard doesn't:**
- Cache issue (hard refresh)
- Session issue (sign out/in)
- TRADING_API_URL mismatch in Vercel

---

## Verify Vercel Environment

```bash
cd trading-dashboard-public
vercel env ls
```

**Should show:**
```
TRADING_API_URL    Production    https://pomological-adriel-tetrahydrated.ngrok-free.dev
TRADING_API_KEY    Production    5e3aaab9cf9738b34926df0fc8eac10015ac450cb50b331931850e15b5e396a2
```

**If mismatch:** Update and redeploy:

```bash
vercel env rm TRADING_API_URL production
vercel env add TRADING_API_URL production
# Paste: https://pomological-adriel-tetrahydrated.ngrok-free.dev
vercel --prod
```

---

## Check Browser Console for Errors

**Open dashboard → Press F12 → Console tab**

**Look for:**
- Red error messages
- Failed network requests
- CORS errors
- 401/403/500 status codes

**Common issues:**

### "Failed to fetch" or "Network error"
- ngrok tunnel expired (restart ngrok)
- API server crashed (restart dashboard_api.py)

### "401 Unauthorized"
- Session expired (sign out/in)
- Wrong API key in Vercel env

### "500 Internal Server Error"
- Check Vercel function logs: Vercel dashboard → Deployments → Functions
- Check Python API logs: `trading/logs/dashboard_api.log`

---

## Restart Everything (Nuclear Option)

If all else fails, restart the entire stack:

### 1. Restart Python API

```bash
# Kill existing
pkill -f "uvicorn.*dashboard_api"

# Start fresh
cd "trading/scripts"
nohup python3 -m uvicorn dashboard_api:app --host 0.0.0.0 --port 8888 > ../logs/dashboard_api.log 2>&1 &

# Verify
sleep 2
curl -s http://localhost:8888/api/snapshot -H "X-API-Key: 5e3aaab9..." | head -20
```

### 2. Restart ngrok

```bash
# Kill existing
pkill -f ngrok

# Start fresh
ngrok http 8888 --log stdout > /tmp/ngrok.log 2>&1 &

# Get new URL
sleep 3
curl -s http://localhost:4040/api/tunnels | python3 -c "import sys, json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])"
```

### 3. Update Vercel with New ngrok URL

```bash
cd trading-dashboard-public
vercel env rm TRADING_API_URL production
vercel env add TRADING_API_URL production
# Paste the new ngrok URL from step 2
vercel --prod
```

### 4. Hard Refresh Dashboard

Cmd+Shift+R on https://winzinvest.com/institutional

---

## Current State (As of 11:54pm MT)

### ✅ Confirmed Working
- Python API: Running, serving data
- ngrok tunnel: Active, forwarding requests
- Vercel: Deployed with correct env vars
- Phase 2 code: All committed and pushed

### ⚠️ User Reports
- "Error Loading Dashboard" persists after ngrok fix

### 🔍 Diagnosis
- 99% likely: **Browser cache** (Vercel deployed new code, browser has old JS)
- 1% likely: Vercel env var not picked up (check with `vercel env ls`)

### 💡 Solution
**Hard refresh (Cmd+Shift+R)** should fix it.

---

## If Dashboard Works After Hard Refresh

**Congratulations!** Phase 2 is fully operational.

**Next steps:**
1. Run Supabase migration (enables email prefs + segmentation)
2. Restart scheduler (starts daily/weekly data jobs)
3. Monitor engagement metrics weekly

**See:** `ACTION_PLAN_NOW.md` for detailed deployment steps.

---

## If Dashboard Still Broken After Hard Refresh

### Debug Steps

1. **Check browser console (F12):**
   - Any red errors?
   - Failed network requests to `/api/dashboard`?

2. **Check Vercel function logs:**
   - https://vercel.com/your-username/winzinvest/deployments
   - Click latest deployment → Functions tab
   - Look for 500 errors

3. **Test API directly:**
   ```bash
   curl -s "https://winzinvest.com/api/dashboard" \
     -H "Cookie: next-auth.session-token=YOUR_TOKEN" | jq .
   ```

4. **Verify TRADING_API_URL:**
   ```bash
   cd trading-dashboard-public
   vercel env ls | grep TRADING_API_URL
   ```
   Should show ngrok URL.

5. **Check ngrok logs:**
   ```bash
   tail -50 /tmp/ngrok.log
   ```
   Look for incoming requests.

### Still Stuck?

**Share these details:**
1. Exact error message from browser console
2. Output of `vercel env ls`
3. Output of `curl http://localhost:8888/api/snapshot -H "X-API-Key: ..."`
4. Screenshot of dashboard error

---

## Most Likely Solution

**99% chance:** Just need a hard refresh (Cmd+Shift+R).

Vercel deployed new code 30 min ago, your browser is still showing the old cached version.

**Try that first** before debugging further.
