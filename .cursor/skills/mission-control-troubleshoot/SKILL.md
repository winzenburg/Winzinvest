---
name: mission-control-troubleshoot
description: Diagnose and fix recurring Mission Control dashboard errors — System Errors count, Stale Data alert, IB connection failures, yfinance DNS errors, clientId conflicts, empty dashboard sections (Audit Trail, Regime card, Strategy Attribution). Use when the user reports dashboard errors, connection failures, or missing data.
---

# Mission Control Troubleshoot

## Step 1 — Fetch the actual errors

```bash
curl -s "http://localhost:8002/api/errors?minutes=60" | python3 -m json.tool
```

Check timestamps. Old errors (>30 min) will expire on their own — tell the user when they clear. Only investigate new ones.

## Step 2 — Classify the error

### IB `Error 326` / `Peer closed connection` / `clientId already in use`
→ **clientId conflict.** Check `030-ib-client-ids.mdc` registry.  
→ The offending script is trying an ID held by a continuous agent (`risk_monitor.py` holds **106 permanently**).  
→ Fix: assign the script a free ID (next unused above 119, skipping 120 and 125). Update the registry rule.

### `Connection failed with all client ids`
→ Script exhausted its entire ID rotation. Usually caused by the above conflict + too few fallback IDs.  
→ Fix: add more IDs to the script's rotation, or pick IDs outside the conflict range.

### yfinance DNS errors (`guce.yahoo.com`, `curl: (6)`, `DNSError`)
→ Transient network blip. Already filtered from error count.  
→ Verify the script has a **cache fallback** (see `041-trading-script-patterns.mdc`).  
→ No action needed unless the error repeats for >30 min.

### `sector_rotation: Failed to download after 3 retries`
→ DNS blip at post-close run. Script falls back to cached `sector_allocation.json`.  
→ Verify: `cat trading/sector_allocation.json | python3 -m json.tool | head -5`  
→ Filtered from error count — no action needed.

### `portfolio_snapshot: Connection failed`
→ Check IDs 111–113 are not in use by another process:  
  `ps aux | grep portfolio_snapshot`  
→ Manual refresh: `curl -X POST http://localhost:8002/api/portfolio/refresh`

---

## Stale Data alert

Fires when `portfolio.json` timestamp is >10 min old **during market hours** (7:25–14:15 MT weekdays only).

```bash
# Manual refresh
curl -X POST http://localhost:8002/api/portfolio/refresh
```

If refresh fails, check IB Gateway is running (`lsof -nP -iTCP:4002`).  
After market close, stale data is expected — the alert is suppressed automatically.

---

## Empty dashboard sections

### Regime & Context card is empty
→ `trading/logs/regime_context.json` doesn't exist yet.  
```bash
cd trading/scripts && python3 -c "
from regime_detector import detect_market_regime, persist_regime_to_context
persist_regime_to_context(detect_market_regime(ib=None))
print('done')
"
```

### Strategy Attribution empty
→ `trades.db` has <30 closed trades or `strategy_scorecard.json` not yet generated.  
→ Normal for new deployments — table shows open trade counts instead via live DB read.  
→ Scorecard auto-generates at post-close (14:30 MT) once 30+ trades have closed.

### Audit Trail not loading
→ Check `/api/audit` endpoint: `curl -s http://localhost:8002/api/audit | head -c 200`  
→ Verify `trading/logs/audit_trail.json` exists and is valid JSON.

---

## Dashboard server is down / returning 404

```bash
# Check if running
lsof -ti :8002

# Restart
kill $(lsof -ti :8002) 2>/dev/null; sleep 2
cd trading && python3 dashboard/api.py &
```

---

## Adding new error patterns to ignore

Only add to `_IGNORED_ERROR_PATTERNS` in `api.py` when ALL are true:
1. The error is handled by retry/fallback in the originating script
2. The error message gives no actionable information to the user
3. It fires repeatedly as noise, not as a real failure signal

Always keep `"Connection failed with all client ids"` visible — it means a script truly couldn't connect.
