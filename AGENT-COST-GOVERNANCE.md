# Agent Cost Governance Framework

**Effective Date:** February 25, 2026  
**Budget:** $200/month (SET)  
**Model Hierarchy:** Ollama (local) → Claude Haiku → Claude Opus (only emergency)

---

## The Rule: DEFAULT LOCAL, ESCALATE ON GATE FAILURE

Every agent and sub-agent must follow this pattern:

```
Task assigned
  ↓
1. DEFAULT: Try Ollama (local) first
   - Zero cost ✅
   - Instant inference ✅
   - 100% private ✅
   - Use for: classification, filtering, summarization, routing
  ↓
2. GATE CHECK: Is output good enough?
   - Schema valid? (JSON, required fields present)
   - No contradictions? (logically sound)
   - Complete? (all required info present)
   - Confidence level matches requirements?
  ↓
   YES → Use local output, STOP ✅
   NO → Go to Step 3
  ↓
3. ESCALATE: Document why local failed
   - In ROUTE JSON, set reason field
   - Example: "Gate check failed: JSON schema violated"
   - Example: "Output contradicts itself; needs human-level reasoning"
   - NOT acceptable: "Would be faster" or "Just to be safe"
  ↓
4. TRY: Claude Haiku (cloud, fast, cheap)
   - Cost: ~$0.80 per M input tokens
   - Use for: complex reasoning, multi-step work, nuance
  ↓
5. FINAL ESCALATION: Claude Opus (rare emergency only)
   - Cost: ~$15 per M input tokens
   - Use for: high-stakes financial decisions, red-team analysis
   - Requires explicit approval
```

---

## Sub-Agent Spawning Rules

**BEFORE spawning any sub-agent:**

1. ✅ Check: Are fewer than 2 local generations currently running?
   - If NO: Return plan + request aggregation instead (batch work)
   - If YES: Proceed

2. ✅ Assign model explicitly:
   ```
   sessions_spawn({
     task: "...",
     model: "qwen2.5:7b"  // ← REQUIRED (Ollama model)
   })
   ```

3. ✅ Cap input context at 4K tokens
   - Summarize before sending to local 7B
   - Large context = system thrashing

4. ✅ Require structured JSON output
   - Parse and validate schema
   - Re-run if invalid (local only, no escalation for schema errors)

5. ✅ No recursive agent spawning
   - Max depth: 2 (main → subagent → no more)

---

## Cost Tracking (Weekly)

**Every Friday 2 PM MT, generate cost report:**

```
Weekly Cost Report — Week of [DATE]

Total Spend This Week: $XXX
Budget Status: $XX.XX / $200.00 used

Breakdown by Service:
- Ollama (local): $0.00 ✅ (target: 80%+ of work)
- Claude Haiku: $X.XX
- Claude Opus: $0.00

Escalations This Week:
[List each escalation with reason]

Local vs Cloud Usage:
- Local: X% of tasks ✅
- Cloud: X% of tasks
- Target: 80%+ local

Issues/Optimizations:
- [Any patterns of over-escalation?]
- [Any tasks that should move to local?]

Recommendation:
[Continue/adjust strategy]
```

---

## Agent Spawning Checklist

**For EVERY sub-agent spawn, verify:**

- [ ] Fewer than 2 local jobs running
- [ ] Model = qwen2.5:7b (or appropriate local model)
- [ ] Input context ≤ 4K tokens
- [ ] Output format = JSON (structured, parseable)
- [ ] Task description includes success criteria
- [ ] No nested agent spawning (max depth 2)
- [ ] Task timeout reasonable (60-3600 seconds)
- [ ] Cleanup = "keep" (for manual review) or "delete" (auto-purge)

**If any check fails:** Don't spawn. Return plan + ask for adjustment.

---

## Current Active Agents (Monitor These)

| Agent | Model | Purpose | Cost | Status |
|-------|-------|---------|------|--------|
| main (you) | Claude Haiku | Orchestration | tracked | ACTIVE |
| trading-screener (cron 8 AM) | Ollama | Candidate filtering | $0.00 | LIVE |
| kinlet-gtm (sub-agent) | Ollama | Reddit/DM execution | $0.00 | LAST RUN: Feb 25 |
| infrastructure-repair | Ollama | System health checks | $0.00 | PENDING |
| overnight-work (cron) | Ollama | Planning/prep | $0.00 | LAST RUN: Feb 25 |

---

## Examples: When to Use Each Model

### ✅ USE OLLAMA (Always Try First)

- Classify screener candidates (T1/T2/T3)
- Filter by sector concentration limits
- Validate webhook JSON schema
- Extract metrics from text
- Route tasks to appropriate handler
- Summarize Reddit threads
- Check voice compliance (peer vs corporate tone)
- Parse and categorize caregiver feedback

### ⚠️ USE HAIKU (If Ollama Gates Fail)

- Complex market narrative analysis
- Multi-step reasoning (if/then chains)
- Nuanced caregiver messaging
- Risk assessment with contradictions
- Portfolio rebalancing logic

### 🚨 USE OPUS (Rare Emergency Only)

- High-stakes financial decisions ($50K+)
- Red-team analysis of risky trades
- Institutional risk assessment
- **Requires explicit approval before spawning**

---

## Monthly Budget Review (1st of Month)

**Every 1st of month at 9 AM MT:**

1. Pull full cost report from all providers
2. Compare: Budgeted ($200) vs Actual ($$)
3. Calculate: % local vs cloud usage
4. Review: Any runaway costs?
5. Adjust: Next month's strategy if needed

**Alert Threshold:** If spend > $160 (80% of budget), default harder to local.  
**Hard Stop:** If spend = $200, STOP all cloud escalations immediately.

---

## Escalation Justification Template

**Every time you escalate to cloud, use this format:**

```json
{
  "timestamp": "2026-02-25T21:00:00Z",
  "task": "Analysis of market regime shift",
  "local_attempt": "Ollama qwen2.5:7b",
  "gate_failure": "Output contradicts itself: says VIX rising but suggests long entries",
  "escalation": "claude-haiku-4-5",
  "estimated_cost": "$0.015",
  "justification": "Multi-step reasoning needed to resolve contradiction; local output invalid"
}
```

---

## The Golden Rule

> **If you're tempted to use cloud for speed, convenience, or "just to be safe" — use local instead, even at 70% confidence. That's the whole point of the framework.**

Cost governance isn't about perfection. It's about **discipline**.

---

## Emergency Override (You Only)

If you explicitly approve cloud use for a task (e.g., "use Opus for this trade decision"), I will:
1. Document it with your approval timestamp
2. Flag cost impact
3. Note it in weekly report
4. Continue framework enforcement going forward

**This is the ONLY exception.**

---

**Last Updated:** February 25, 2026  
**Framework Status:** 🟢 ACTIVE  
**All Agents:** ⚠️ MUST COMPLY
