# Mode Toggle Testing Plan

## Local Testing (http://localhost:3002/dashboard)

### Pre-Test Setup
✅ Dev server running on port 3002  
✅ Backend API running on port 8888  
✅ Cloudflare Tunnel active: `https://myself-restrictions-decor-dealers.trycloudflare.com`  
✅ `.env.local` has `TRADING_API_URL` and `TRADING_API_KEY` configured

### What Changed
The old design had **two separate toggles**:
1. "View" toggle (paper/live) - what data to display
2. "Exec" toggle (paper/live) - what mode is active for execution

The new design has **one unified toggle** that synchronizes both:
- View mode always matches active execution mode
- Single prominent toggle with clear "LIVE" indicator when in live mode
- Simplified UI - no confusion about which mode you're viewing vs executing

---

## Test Cases

### Test 1: Initial Load - Live Mode Display
**Expected**: Dashboard should show "LIVE" mode by default (since Gateway is on port 4001)

**Steps**:
1. Open http://localhost:3002/dashboard in your browser
2. Look at the top-right corner for the mode toggle
3. Verify it shows "LIVE" with a red indicator badge

**Pass Criteria**:
- [ ] Single toggle button visible (not two separate buttons)
- [ ] Shows "LIVE" text with red badge
- [ ] Dashboard displays live account data

---

### Test 2: Switch to Paper Mode
**Expected**: Clicking the toggle should switch to paper mode

**Steps**:
1. Click the mode toggle once
2. Observe the UI change
3. Check that dashboard data updates

**Pass Criteria**:
- [ ] Toggle changes to show "PAPER" (no red badge)
- [ ] Dashboard switches to paper account data
- [ ] No separate "exec" toggle appears
- [ ] Preference saved to localStorage

---

### Test 3: Switch Back to Live Mode
**Expected**: Clicking again should return to live mode

**Steps**:
1. Click the toggle again (from paper → live)
2. Observe the UI change
3. Verify the API endpoint is called

**Pass Criteria**:
- [ ] Toggle shows "LIVE" with red badge again
- [ ] Dashboard switches back to live account data
- [ ] Mode persists in localStorage

---

### Test 4: Backend API Call Verification
**Expected**: Mode changes should update the backend's active mode

**Steps**:
1. Open browser DevTools → Network tab
2. Click the mode toggle to switch modes
3. Look for POST request to `/api/trading-modes`

**Pass Criteria**:
- [ ] POST request sent to `/api/trading-modes` with `{"mode": "paper"}` or `{"mode": "live"}`
- [ ] Request succeeds (200 OK)
- [ ] Response confirms mode was updated

---

### Test 5: Page Reload Persistence
**Expected**: Selected mode should persist across page reloads

**Steps**:
1. Switch to paper mode
2. Refresh the page (Cmd+R / F5)
3. Check the mode toggle after reload

**Pass Criteria**:
- [ ] Mode toggle shows the same mode as before reload
- [ ] Dashboard displays correct account data
- [ ] localStorage has `tradingViewMode` set correctly

---

### Test 6: Visual Design Check
**Expected**: New toggle should look clean and professional

**Steps**:
1. View the toggle in both states (paper and live)
2. Check hover states
3. Verify tooltip appears on hover

**Pass Criteria**:
- [ ] Toggle has smooth transitions
- [ ] LIVE mode has prominent red "LIVE" badge
- [ ] Paper mode has neutral styling
- [ ] Hover tooltip explains "Switch between paper and live trading"
- [ ] Design matches the rest of the dashboard

---

### Test 7: Mode Sync Verification
**Expected**: View mode should always match execution mode (no separate toggles)

**Steps**:
1. Switch to paper mode via toggle
2. Check if there's any other mode selector visible
3. Verify all data on the page is from paper account

**Pass Criteria**:
- [ ] Only ONE mode toggle visible (old "View" and "Exec" toggles are gone)
- [ ] All dashboard sections show data from the selected mode
- [ ] No confusion between "view" vs "execution" mode

---

## Browser Console Checks

Open DevTools Console and verify:

```javascript
// Check localStorage
localStorage.getItem('tradingViewMode')  // Should be "paper" or "live"

// Check API response
// After clicking toggle, look for:
{
  "activeMode": "live",  // or "paper"
  "paperGatewayUp": false,
  "modes": {
    "paper": { "available": true, ... },
    "live": { "available": true, ... }
  }
}
```

---

## API Endpoint Testing (Optional)

Test the mode switching API directly:

```bash
# Get current mode
curl -s http://localhost:3002/api/trading-modes

# Switch to paper (requires authentication cookie - test via browser)
# Or test the backend directly:
curl -s -H "x-api-key: YOUR_KEY" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"mode": "paper"}' \
  https://myself-restrictions-decor-dealers.trycloudflare.com/api/trading-modes
```

---

## Known Issues to Watch For

### ❌ Old Behavior (Should NOT See)
- Two separate toggles (View and Exec)
- Mismatched view/exec modes
- Confusing labels

### ✅ New Behavior (Should See)
- Single unified toggle
- Clear "LIVE" indicator with red badge
- View always matches execution mode
- Clean, intuitive design

---

## Success Criteria Summary

All tests pass if:
1. ✅ Only ONE mode toggle visible throughout the dashboard
2. ✅ Toggle clearly shows current mode (LIVE with badge / PAPER without)
3. ✅ Clicking toggle switches between modes smoothly
4. ✅ Dashboard data updates to reflect selected mode
5. ✅ Mode persists across page reloads
6. ✅ Backend API is called and confirms mode change
7. ✅ No visual bugs or layout issues

---

## What to Report Back

After testing, let me know:
- [ ] All tests passed / which tests failed
- [ ] Any visual issues or unexpected behavior
- [ ] Screenshots of the toggle in both modes (optional but helpful)
- [ ] Ready to deploy to production?

---

## Production Deployment (After Local Tests Pass)

Once local testing is complete:
1. Configure Cloudflare Pages environment variables (see `CLOUDFLARE_PAGES_SETUP.md`)
2. Redeploy the site
3. Test on https://www.winzinvest.com/dashboard
4. Verify the same behavior works in production
