# Mission Control - Troubleshooting Guide

Common issues and solutions for the Mission Control dashboard.

---

## Dashboard Issues

### Error: "Cannot find module './638.js'"

**Symptom**: Server error when loading dashboard pages

**Cause**: Stale Next.js build cache (`.next` directory)

**Solution**:
```bash
cd trading-dashboard-public
rm -rf .next
npm run dev
```

This clears the webpack cache and rebuilds from scratch.

---

### Warning: "EMFILE: too many open files"

**Symptom**: Many "Watchpack Error (watcher): Error: EMFILE: too many open files" warnings in terminal

**Cause**: macOS has a low default limit for file descriptors. Next.js watches many files for hot reload.

**Impact**: **Not critical** - the dev server still works fine. These are just warnings.

**Solution (optional)**:
```bash
# Increase file descriptor limit (temporary, current session only)
ulimit -n 10240

# Or add to ~/.zshrc for permanent fix
echo "ulimit -n 10240" >> ~/.zshrc
source ~/.zshrc

# Then restart dev server
cd trading-dashboard-public
npm run dev
```

**Alternative**: Ignore the warnings - they don't affect functionality.

---

### Server keeps restarting

**Symptom**: "Found a change in next.config.js. Restarting the server..."

**Cause**: File watcher detecting changes (real or false positives)

**Impact**: Slight delay, but server works after restart

**Solution**:
1. Wait for server to stabilize (usually 2-3 restarts)
2. If it continues, check if another process is modifying files
3. If persistent, restart with clean cache:
   ```bash
   rm -rf .next
   npm run dev
   ```

---

### Port 3000 already in use

**Symptom**: "Port 3000 is in use, trying 3001 instead"

**Cause**: Another dev server is already running on port 3000

**Solution**:
```bash
# Option 1: Use port 3001 (Next.js auto-selects this)
# Just visit http://localhost:3001

# Option 2: Kill the process on port 3000
lsof -ti:3000 | xargs kill -9

# Then restart
npm run dev
```

---

### Dashboard shows "Loading..." forever

**Symptom**: Page stuck on loading state

**Cause**: API route failing or data file missing

**Solution**:
```bash
# 1. Check if dashboard_snapshot.json exists
ls -la trading/logs/dashboard_snapshot.json

# 2. If missing, run data aggregator
cd trading
python3 scripts/dashboard_data_aggregator.py

# 3. Check browser console for errors
# Open DevTools (Cmd+Option+I) and check Console tab

# 4. Check API route is working
curl http://localhost:3001/api/dashboard
```

---

### Dashboard shows error message

**Symptom**: "Error Loading Dashboard" with details

**Cause**: Various (check the error message)

**Common causes:**
1. `dashboard_snapshot.json` not found → Run `dashboard_data_aggregator.py`
2. Invalid JSON in snapshot → Check file syntax
3. API route error → Check terminal logs
4. Network error → Check if dev server is running

**Solution**:
```bash
# Check what the error says, then:

# If "Data file not found"
cd trading && python3 scripts/dashboard_data_aggregator.py

# If "Invalid data format"
cat trading/logs/dashboard_snapshot.json  # Check JSON syntax

# If "Failed to fetch"
# Make sure dev server is running on port 3001
```

---

## Build Issues

### Build fails with TypeScript errors

**Symptom**: `npm run build` fails with type errors

**Cause**: Type mismatches or missing types

**Solution**:
```bash
# 1. Check the specific error message
npm run build

# 2. Fix type issues in the reported files
# Common fixes:
# - Add type guards for external data
# - Replace 'any' with proper types
# - Add missing interface properties

# 3. Verify fix
npm run build
```

---

### Build fails with linter errors

**Symptom**: `npm run build` fails during linting

**Cause**: Code doesn't meet linting rules

**Solution**:
```bash
# 1. Run linter to see errors
npm run lint

# 2. Auto-fix what's possible
npm run lint -- --fix

# 3. Manually fix remaining issues

# 4. Verify
npm run build
```

---

## Data Issues

### No data showing in dashboard

**Symptom**: Dashboard loads but shows empty states or zeros

**Cause**: `dashboard_snapshot.json` is empty or has no data

**Solution**:
```bash
# 1. Check if aggregator ran successfully
cat trading/logs/dashboard_aggregator.log

# 2. Run aggregator manually
cd trading
python3 scripts/dashboard_data_aggregator.py

# 3. Check output file
cat trading/logs/dashboard_snapshot.json

# 4. If still empty, check IBKR connection
# Make sure TWS/IB Gateway is running and connected
```

---

### Data is stale

**Symptom**: "Last updated" timestamp is old (>5 minutes)

**Cause**: Data aggregator not running on schedule

**Solution**:
```bash
# 1. Check if cron job is set up
crontab -l | grep dashboard_aggregator

# 2. If missing, add cron job
crontab -e
# Add: */5 * * * * /path/to/run_dashboard_aggregator.sh

# 3. Or run manually for testing
cd trading
python3 scripts/dashboard_data_aggregator.py
```

---

### Metrics are incorrect

**Symptom**: Numbers don't match expectations

**Cause**: Calculation error or data parsing issue

**Solution**:
```bash
# 1. Check aggregator logs for errors
cat trading/logs/dashboard_aggregator.log

# 2. Run aggregator with verbose output
cd trading
python3 scripts/dashboard_data_aggregator.py

# 3. Check IBKR account values
# Log into TWS and verify numbers manually

# 4. Check audit trail for context
cat trading/logs/audit_trail.json | tail -n 50
```

---

## Font Issues

### Fonts not loading

**Symptom**: Dashboard uses system fonts instead of Playfair/Inter/JetBrains Mono

**Cause**: Font import failed or CSS not applied

**Solution**:
```bash
# 1. Check layout.tsx has font imports
cat trading-dashboard-public/app/layout.tsx | grep "next/font"

# 2. Check globals.css has font classes
cat trading-dashboard-public/app/globals.css | grep "font-"

# 3. Clear Next.js cache
cd trading-dashboard-public
rm -rf .next
npm run dev

# 4. Check browser DevTools Network tab
# Look for font requests (should see Playfair, Inter, JetBrains Mono)
```

---

## Git/Deployment Issues

### Vercel build fails

**Symptom**: Deployment fails on Vercel

**Cause**: Various (check Vercel logs)

**Common causes:**
1. Build error → Fix locally first
2. Missing environment variables → Add in Vercel dashboard
3. Wrong output directory → Check `vercel.json` and `next.config.js`

**Solution**:
```bash
# 1. Test build locally first
cd trading-dashboard-public
npm run build

# 2. If local build succeeds, check Vercel logs
# Visit Vercel dashboard → Deployments → Click failed deployment → View logs

# 3. Common fixes:
# - Add environment variables in Vercel dashboard
# - Check vercel.json is correct
# - Ensure next.config.js matches deployment type
```

---

### Git push rejected

**Symptom**: `git push` fails

**Cause**: Various (check error message)

**Common causes:**
1. No remote configured
2. Authentication failed
3. Branch protection rules
4. Large files

**Solution**:
```bash
# 1. Check remote
git remote -v

# 2. If no remote, add one
git remote add origin https://github.com/yourusername/mission-control.git

# 3. Check authentication
gh auth status

# 4. If auth failed, login
gh auth login

# 5. Try push again
git push -u origin main
```

---

## Performance Issues

### Dashboard loads slowly

**Symptom**: Page takes >2 seconds to load

**Cause**: Large data files, slow API routes, or unoptimized components

**Solution**:
```bash
# 1. Check data file size
ls -lh trading/logs/dashboard_snapshot.json

# 2. If >1MB, optimize data structure
# - Remove unnecessary fields
# - Limit historical data (e.g., last 30 days only)

# 3. Check API route performance
# Open browser DevTools → Network tab
# Look for slow requests (>500ms)

# 4. Optimize components
# - Use React.memo for expensive components
# - Lazy load heavy components
# - Use canvas instead of SVG for charts
```

---

### Chart rendering is slow

**Symptom**: Equity curve or other charts lag

**Cause**: Too many data points or inefficient rendering

**Solution**:
```tsx
// In EquityCurve.tsx or similar:

// 1. Limit data points
const maxPoints = 100;
const sampledData = data.length > maxPoints 
  ? data.filter((_, i) => i % Math.ceil(data.length / maxPoints) === 0)
  : data;

// 2. Use requestAnimationFrame for smooth rendering
useEffect(() => {
  const render = () => {
    // Draw chart
  };
  requestAnimationFrame(render);
}, [data]);

// 3. Debounce resize events
const debouncedResize = debounce(() => {
  // Redraw chart
}, 100);
```

---

## macOS-Specific Issues

### "Too many open files" system-wide

**Symptom**: Many processes showing EMFILE errors

**Cause**: macOS default file descriptor limit is too low

**Solution**:
```bash
# Check current limits
ulimit -n  # Soft limit
ulimit -Hn # Hard limit

# Increase for current session
ulimit -n 10240

# Permanent fix: Add to ~/.zshrc
echo "ulimit -n 10240" >> ~/.zshrc
source ~/.zshrc

# System-wide fix (requires restart)
sudo launchctl limit maxfiles 65536 200000
```

---

## Python Issues

### Data aggregator fails

**Symptom**: `dashboard_data_aggregator.py` crashes

**Cause**: Various (check error message)

**Common causes:**
1. IBKR not connected
2. Missing dependencies
3. Invalid data from IBKR
4. File permission issues

**Solution**:
```bash
# 1. Check IBKR connection
# Make sure TWS or IB Gateway is running

# 2. Check dependencies
pip3 install ib_insync numpy pandas

# 3. Run with verbose output
cd trading
python3 scripts/dashboard_data_aggregator.py

# 4. Check logs
cat trading/logs/dashboard_aggregator.log

# 5. Check file permissions
ls -la trading/logs/
```

---

## Quick Diagnostics

### Check everything is working

```bash
# 1. Check dev server is running
lsof -ti:3001  # Should return a PID

# 2. Check data file exists and is recent
ls -lh trading/logs/dashboard_snapshot.json
stat trading/logs/dashboard_snapshot.json  # Check modification time

# 3. Check API route works
curl http://localhost:3001/api/dashboard

# 4. Check for build errors
cd trading-dashboard-public && npm run build

# 5. Check for linter errors
npm run lint

# 6. Check git status
git status
```

---

## Getting Help

### Before asking for help, collect:

1. **Error message** (exact text)
2. **Terminal output** (last 50 lines)
3. **Browser console** (if dashboard issue)
4. **Steps to reproduce**
5. **What you've tried**

### Check these files for clues:

- `trading/logs/dashboard_aggregator.log` - Data aggregator errors
- `trading/logs/audit_trail.json` - System events
- Browser DevTools Console - Frontend errors
- Terminal output - Dev server errors

---

## Common Fixes Summary

| Issue | Quick Fix |
|-------|-----------|
| Cannot find module | `rm -rf .next && npm run dev` |
| EMFILE warnings | `ulimit -n 10240` (optional, not critical) |
| Port in use | Visit `http://localhost:3001` instead |
| No data | Run `dashboard_data_aggregator.py` |
| Stale data | Set up cron job or run aggregator manually |
| Build fails | Check error, fix, run `npm run build` again |
| Fonts not loading | Clear cache: `rm -rf .next` |

---

## Prevention

### Before committing:
```bash
# Run quality gates
npm run lint
npm run build
git status  # Should be clean
```

### Before deploying:
```bash
# Test locally
npm run dev
# Visit all pages, check for errors

# Build test
npm run build

# Check logs
cat trading/logs/dashboard_aggregator.log
```

### Regular maintenance:
```bash
# Weekly: Check audit trail for issues
cat trading/logs/audit_trail.json | tail -n 100

# Weekly: Verify data aggregator is running
crontab -l | grep dashboard_aggregator

# Monthly: Clean old logs
find trading/logs -name "*.log" -mtime +30 -delete
```

---

## Still Stuck?

1. Read the error message carefully
2. Search this file for keywords from the error
3. Check the relevant documentation:
   - Design issues → `DESIGN_QUICK_REFERENCE.md`
   - Quality gates → `.cursor/rules/020-mission-control-gates.mdc`
   - Agent workflows → `AGENTS.md`
4. Check recent git commits for changes
5. Try reverting recent changes to isolate the issue

---

**Last Updated**: March 7, 2026
