# Vercel Dual-Mode Data Access Fixes

**Date**: 2026-03-30  
**Issue**: Phase 2 engagement routes were reading local files on Vercel (serverless), causing empty/broken sections

---

## Root Cause

When Next.js deploys to Vercel, the `trading/logs/` directory **doesn't exist** in the serverless environment. API routes that used `fs.readFileSync()` or `readJson()` from local filesystem failed silently, returning empty data.

**Solution**: Implement dual-mode data access pattern:
- **Remote** (Vercel): Fetch from Python backend via ngrok
- **Local** (dev): Read files directly from filesystem

---

## Routes Fixed (7 total)

### ✓ Fixed Today

| Route | Issue | Fix Applied |
|---|---|---|
| `/api/portfolio-composition` | Reading local `dashboard_snapshot.json` | Added `isRemote` check, fetch from Python `/api/snapshot` |
| `/api/regime-history` | Reading local `regime_history.jsonl` | Added dual-mode + created Python endpoint |
| `/api/daily-narrative` | Reading local `daily_narrative.json` | Added dual-mode + created Python endpoint |
| `/api/decision-context` | Reading local `decision_context.json` | Added dual-mode + created Python endpoint |
| `/api/system-benchmarks` | Reading local `system_benchmarks.json` | Added dual-mode + created Python endpoint |
| `/api/rejected-trades` | Reading local `executions.json` | Added dual-mode + created Python endpoint |
| `/api/trade-history` | Reading local `trades.db` (SQLite) | Added dual-mode + created Python endpoint with SQL |

### ✓ Already Had Dual-Mode

These existing routes were already correctly implemented:
- `/api/dashboard` → uses `getSnapshot()` (dual-mode)
- `/api/alerts` → has `isRemote` check
- `/api/analytics` → has `isRemote` check
- `/api/audit` → has `isRemote` check
- `/api/journal` → has `isRemote` check
- `/api/intelligence` → has `isRemote` check
- `/api/screeners` → has `isRemote` check
- `/api/strategy-attribution` → has `isRemote` check

---

## Python Backend Endpoints Added

Added 5 new endpoints to `trading/scripts/agents/dashboard_api.py`:

```python
GET /api/daily-narrative        → logs/daily_narrative.json
GET /api/decision-context       → logs/decision_context.json (34 positions, 24 decisions)
GET /api/system-benchmarks      → logs/system_benchmarks.json (182 trades, 59.9% WR)
GET /api/rejected-trades        → logs/executions.json (filters rejected)
GET /api/trade-history          → logs/trades.db (SQLite query)
```

All require `x-api-key` header for authentication.

---

## Data Generation Scripts

These run automatically via scheduler (post-close and Sunday):

| Script | Output File | Scheduler Job | Data |
|---|---|---|---|
| `generate_daily_narrative.py` | `daily_narrative.json` | post-close | Today's activity summary |
| `generate_decision_context.py` | `decision_context.json` | post-close | Entry/stop explanations |
| `track_regime_history.py` | `regime_history.jsonl` | post-close | Regime transitions |
| `generate_system_benchmarks.py` | `system_benchmarks.json` | Sunday | Aggregate performance |
| `segment_user_behavior.py` | `user_segments.json` | Sunday | User engagement tiers |

---

## Current Data Status

All endpoints confirmed working via ngrok (tested 2026-03-30 06:37 MT):

```
✓ daily-narrative:      2026-03-29 narrative (95 chars)
✓ decision-context:     34 positions, 24 recent decisions
✓ system-benchmarks:    182 trades, 59.9% WR, $598 avg P&L
✓ rejected-trades:      0 rejections today (empty but working)
✓ trade-history:        182 closed trades from SQLite
✓ regime-history:       1 transition (STRONG_DOWNTREND from 2026-03-29)
✓ portfolio-composition: 13 sectors, 6 strategies, long/short balance
```

---

## Verification Steps

After deployment, verify each feature:

1. **Portfolio Composition** (Overview tab):
   - Should show 13 sectors with percentages
   - Long/Short balance bar (green/red)
   - Strategy breakdown (6 strategies)

2. **Regime History** (Overview tab):
   - Timeline with regime transitions
   - Currently shows 1 entry, will grow over time

3. **System Risk Management** (Risk tab):
   - VaR, CVaR, beta, correlation metrics
   - Margin utilization bars
   - Sector concentration chart

4. **Decision Tooltips** (Positions table):
   - "?" icon next to each position
   - Hover shows why system entered/placed stop

5. **Performance Explorer** (Performance tab):
   - "Your X vs system avg Y" comparison badges
   - Saved filters persisted to localStorage
   - 182 closed trades available for filtering

---

## Architecture Pattern

All dual-mode routes now follow this pattern:

```typescript
import { readJson, remoteGet, isRemote, LOGS_DIR } from '@/lib/data-access';

export async function GET() {
  const unauth = await requireAuth();
  if (unauth) return unauth;

  try {
    let data: any;
    
    if (isRemote) {
      // Vercel: fetch from Python backend
      data = await remoteGet('/api/endpoint-name');
    } else {
      // Local dev: read file directly
      const filePath = path.join(LOGS_DIR, 'filename.json');
      data = readJson(filePath);
    }

    if (!data) {
      return NextResponse.json({ /* fallback */ });
    }

    return NextResponse.json(data);
  } catch (error) {
    console.error('Error:', error);
    return NextResponse.json({ error: 'Failed' }, { status: 500 });
  }
}
```

---

## Deployment Status

- **Backend**: Dashboard API running on port 8888 with all 5 new endpoints ✓
- **Ngrok**: `https://pomological-adriel-tetrahydrated.ngrok-free.dev` tunneling to localhost:8888 ✓
- **Vercel**: Latest deployment `4mya1k6e6` (2026-03-30 06:37 MT) ✓
- **Environment**: `TRADING_API_URL` set to ngrok URL ✓

---

## Next Step for User

**Hard refresh browser** (Cmd+Shift+R) to clear cache and load the new deployment.

All 7 features should now display data:
1. Daily Narrative ✓
2. Portfolio Composition ✓
3. Rejected Trades Widget ✓
4. Decision Tooltips ✓
5. Regime Timeline ✓
6. Performance Explorer comparative context ✓
7. System Risk Management ✓
