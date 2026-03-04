# Cost Governance - Local-First Policy

**Effective:** March 4, 2026, 9:39 AM  
**Decision:** 100% local-first, Claude only for high-stakes decisions  
**Target:** $2-3/day (down from $15/day)  
**Budget:** $200/month hard cap

---

## Model Routing Decision Tree

```
Task arrives
  ↓
Is it high-stakes? (Trading signals, financial analysis, critical research)
  ├─ YES → Use Claude Haiku
  ├─ NO → Go to next
Is it routine work? (Writing, analysis, research, coding, admin)
  ├─ YES → Use Ollama qwen2.5:7b (local)
  ├─ NO → Go to next
Can it wait for local processing?
  ├─ YES → Use Ollama
  ├─ NO → Escalate with justification (RARE)
```

---

## What Uses Claude (High-Stakes Only)

✅ **CLAUDE — Worth the Cost**
- Trading signal validation (pass/fail decision on real money)
- Portfolio rebalancing decisions
- Risk analysis for new strategies
- Financial market analysis requiring deep reasoning
- Crisis response (system failures, security incidents)

---

## What Uses Ollama (Everything Else)

✅ **OLLAMA — 100% of These Tasks**
- Cron jobs (market monitoring, screener, options scan)
- Heartbeat checks (systems health, alerts)
- Content research (Reddit guides, market analysis)
- Code review and refactoring
- Documentation and writing
- Administrative work
- Subagent spawning (hardcoded to `qwen2.5:7b`)
- Email drafting
- Project planning and organization

---

## Subagent Spawning Rule (HARDCODED)

**Every subagent spawns with:**
```
model=qwen2.5:7b
```

No exceptions. No cloud defaults.

---

## Weekly Cost Review (Fridays @ 2 PM MT)

Track and report:
1. Total spend this week
2. Breakdown: Claude vs. Ollama
3. Escalations used (justify each one)
4. % of work on local vs. cloud (target: 80%+ local)
5. Any opportunities to shift work to local next week

File: `memory/cost-reviews/YYYY-MM-DD-cost-review.md`

---

## If I Catch Spend Over $160 (80% of $200 Budget)

1. **Immediate alert** to Ryan
2. **Freeze Claude usage** except for trading decisions
3. **Shift all non-critical work to Ollama**
4. **Report blockers** — what can't be done locally?
5. **Request approval** before spending further

---

## Current Status (Mar 4, 2026)

- **Last week spend:** $105/week ($15/day) — OVER BUDGET
- **Root cause:** Default Claude usage for all work
- **Fix:** Starting now, Ollama-first for all non-critical tasks
- **Expected result:** $14-21/week ($2-3/day)

---

## Monitoring

- Daily: Count local vs. cloud calls
- Weekly (Friday 2 PM): Full cost report
- Monthly: Total vs. $200 budget; recommend adjustments

This is non-negotiable. Cost overruns violate trust and sustainability.
