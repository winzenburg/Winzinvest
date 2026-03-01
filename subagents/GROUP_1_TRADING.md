# GROUP 1: TRADING SCOUTS

**Purpose:** Daily market monitoring, screener results tracking, position management  
**Schedule:** 8:00 AM MT (pre-market) + 2:00 PM MT (post-market)  
**Models:** SCOUT_MARKET (qwen2.5:7b) → AGGREGATOR (Claude Sonnet)  
**Cost Budget:** ~$0.05-0.10/day (escalates 50% of time)

---

## SCOUT_MARKET (qwen2.5:7b)

**Input Sources:**
- `dashboard-data.json` (screener results, engine monitor)
- `logs/open-positions.json` (live position tracking)
- `trading/screener-results-[DATE].md` (latest candidates)

**Task:**
Extract and structure market data into JSON with findings, assumptions, risks, next_checks.

**Expected Input (4k tokens max):**
```json
{
  "screener_results": {
    "tier3": ["ASML (0.51)", "AMAT (0.509)", ...],
    "tier2": [...]
  },
  "open_positions": [
    {"ticker": "MU", "entry": "420.47", "current": "422.15", "pnl": "-$730", "status": "trailing stop active"},
    {"ticker": "ASML", "entry": "...", "current": "...", "pnl": "...", "status": "..."}
  ],
  "engine_monitor": {
    "last_run": "8:12 AM",
    "candidates_monitored": 7,
    "entries": 0,
    "exits": 0,
    "signals_blocked": 5
  }
}
```

**Expected Output:**
```json
{
  "findings": [
    "2 positions open (MU, ASML): combined P&L -$730",
    "Screener identified 2 Tier 3 candidates at 52-week highs (ASML, AMAT)",
    "5 signals blocked due to 2/2 position max",
    "No exits triggered; trailing stops active on both positions"
  ],
  "assumptions": [
    "Dashboard data accurate within 15 minutes",
    "Trailing stop calculations correct (5% from high-water mark)",
    "No gap risk events overnight"
  ],
  "risks": [
    "MU position at -$730; monitor trailing stop level: $398.64",
    "Earnings calendar: MU earnings Feb 26 (earnings blackout active, position should be closed pre-earnings)",
    "Tech sector concentration: 100% of portfolio in tech (MU, ASML)"
  ],
  "next_checks": [
    "Verify earnings blackout is enforced for MU by Feb 26 EOD",
    "Monitor ASML trailing stop level: $427.14 (5% below high of $449.10)",
    "Check if new screener candidates warrant position entry after current 2 close"
  ],
  "confidence": 0.95
}
```

**Gate Checks (qwen2.5:7b Must Pass):**
- ✅ Output is valid JSON
- ✅ findings[] has 3-5 findings
- ✅ risks[] identifies real risks (positions, concentration, calendar events)
- ✅ next_checks[] are actionable (not vague)
- ✅ No contradictions (e.g., saying position is closed but also calculating its stop)

---

## AGGREGATOR (Claude Sonnet)

**Input:** SCOUT_MARKET JSON output

**Task:**
Merge findings with market context. Identify any urgent actions. Escalate to Opus only if:
- Position at critical risk (gap risk, earnings surprise, extreme DD)
- Trade execution decision needed (not routine monitoring)
- Contradiction detected in scout output

**Expected Output:**
```
📊 TRADING BRIEFING — [DATE] [TIME]

PORTFOLIO STATUS:
- Open: 2/2 positions (MU -0.35%, ASML +1.2%)
- Combined P&L: -$730
- Trailing stops active on both

SCREENER RESULTS:
- Tier 3: 2 candidates (ASML, AMAT at 52-week highs)
- Tier 2: 5 candidates
- Signals blocked: 5 (position max reached)

🚨 CRITICAL ACTIONS (Next 48h):
1. **MU Earnings Feb 26**: Verify blackout exits MU by EOD Feb 25 (1 day warning)
2. **ASML Trailing Stop**: Level at $427.14; monitor for exit signal
3. **Sector Concentration**: 100% tech — consider exiting MU to diversify

CONFIDENCE: High (scout data verified, no escalation needed)

---

Next Scout Run: 2:00 PM MT (post-market)
```

**Escalation Trigger (to Opus):**
- Gap risk detected (earning announcement, earnings surprise, major news)
- Position at extreme DD (<$350 on MU, <$900 on ASML)
- Scout output contradictory or incomplete

---

## Cron Schedule

```bash
# FILE: ~/.openclaw/cron/trading-scouts.sh
0 8 * * * /Users/pinchy/.openclaw/scripts/group-1-scout.sh >> /tmp/group1-8am.log 2>&1
0 14 * * * /Users/pinchy/.openclaw/scripts/group-1-scout.sh >> /tmp/group1-2pm.log 2>&1
```

**Pre-execution Check:**
- Is GROUP 1 already running? (check lock file)
- Is GROUP 2 or GROUP 3 running concurrently? (respect 2-concurrent limit)
- If both: queue GROUP 1, wait for other group to finish

---

## Cost Tracking

| Run | Model | Cost | Escalated? | Notes |
|-----|-------|------|-----------|-------|
| 8 AM, Feb 25 | qwen2.5:7b (free) + Sonnet (if escalate) | ~$0.05 | No | Routine monitoring |
| 2 PM, Feb 25 | " | ~$0.00 | No | Scout only, no escalation |

**Target:** ~$0.10/day max, escalate <50% of time (only for critical events)

