# SUBAGENT ORCHESTRATOR

**Purpose:** Manage 3 concurrent scout groups with memory/cost/isolation constraints  
**Architecture:** Scout → Aggregator → Optional Escalation  
**Safety:** Max 2 concurrent groups, $200/month budget, 4k token context per scout  
**Status:** Ready to deploy

---

## Group Scheduling (No Overlaps)

```
TIME        GROUP 1         GROUP 2         GROUP 3
────────────────────────────────────────────────────
8:00 AM     SCOUT_MARKET
10:00 AM                    SCOUTS (M/W/F)
2:00 PM     SCOUT_MARKET
3:00 PM                                     SCOUTS (T/Th)
────────────────────────────────────────────────────

Max concurrent: 2 groups (enforced by lock files)
```

### GROUP 1: TRADING (Daily)
- **8:00 AM MT**: SCOUT_MARKET (pre-market)
- **2:00 PM MT**: SCOUT_MARKET (post-market)
- **Models**: qwen2.5:7b (scout) + Claude Sonnet (aggregator, optional)
- **Cost**: ~$0.05-0.10/day (~$1.50-3.00/month)

### GROUP 2: SAAS (3x/week)
- **10:00 AM MT** (Mon, Wed, Fri): SCOUT_KINLET + SCOUT_CULTIVATE + SCOUT_DESIGN
- **Models**: llama3.1:8b + qwen2.5:7b + deepseek-coder:6.7b (scouts) + Claude Sonnet (aggregator, optional)
- **Cost**: ~$0.05-0.15/week (~$2-3/month)

### GROUP 3: BRAND (2x/week)
- **3:00 PM MT** (Tue, Thu): SCOUT_JOB + SCOUT_CONTENT
- **Models**: qwen2.5:7b + llama3.1:8b (scouts) + Claude Sonnet (aggregator, optional)
- **Cost**: ~$0.05-0.10/week (~$1-2/month)

---

## Execution Flow

```
ORCHESTRATOR
├─ PRE-FLIGHT CHECK (5 min before scheduled time)
│  ├─ Is this group already running? (check /tmp/group-N.lock)
│  ├─ Is another group running? (check /tmp/group-*.lock)
│  └─ If yes to either: queue, retry in 15 min
│
├─ SPAWN SCOUTS (parallel)
│  ├─ SCOUT_A (qwen2.5:7b, 4k context)
│  ├─ SCOUT_B (llama3.1:8b, 4k context)
│  └─ SCOUT_C (deepseek-coder:6.7b, 4k context)
│
├─ WAIT FOR SCOUTS (max 10 min timeout)
│  └─ Merge all JSON outputs
│
├─ RUN AGGREGATOR (Claude Sonnet)
│  ├─ Input: All scout JSONs + brief context
│  └─ Decision: Escalate to Opus? (gate check)
│
├─ CONDITIONAL ESCALATION (Claude Opus)
│  ├─ Only if Aggregator flags: critical risk, execution decision, contradiction
│  └─ Cost: ~$0.05-0.20 per escalation
│
└─ DELIVER REPORT (Telegram or dashboard)
   ├─ Send formatted findings
   ├─ Log cost and timestamp
   └─ Release lock file
```

---

## Lock File Protocol

```bash
# Before starting group N
touch /tmp/group-N.lock

# After finishing (success or failure)
rm /tmp/group-N.lock

# Pre-flight check
ls /tmp/group-*.lock 2>/dev/null | wc -l
# If >1: current + another running = wait
# If =0: safe to start
# If =1: just us = proceed
```

---

## Memory + Cost Safety

| Constraint | Limit | How Enforced |
|-----------|-------|--------------|
| **Concurrent Scouts** | 2 groups max | Lock files + pre-flight check |
| **Scout Context** | 4k tokens input | Prompt template enforces limit |
| **Scout Output** | JSON only | Schema validation on aggregator input |
| **Monthly Budget** | $200 (hard ceiling) | Cost tracker, alert at $160 (80%) |
| **Escalation Rate** | <50% of runs | Target ~1-2 escalations per group per week |
| **Group 1 Cost** | ~$0.05-0.10/day | Sonnet only on critical events |
| **Group 2 Cost** | ~$0.05-0.15/week | Sonnet only on metrics anomalies |
| **Group 3 Cost** | ~$0.05-0.10/week | Sonnet only on deadline risk/engagement collapse |

**Total typical cost:** ~$10-15/month (1/15th of budget)

---

## Deployment Checklist

- [ ] Read GROUP_1_TRADING.md → understand flow
- [ ] Read GROUP_2_SAAS.md → understand flow
- [ ] Read GROUP_3_BRAND.md → understand flow
- [ ] Create shell scripts: group-1-scout.sh, group-2-scout.sh, group-3-scout.sh
- [ ] Create `~/.openclaw/cron/` directory
- [ ] Add cron entries (or use launchd on macOS)
- [ ] Test GROUP 1 (8 AM run) manually
- [ ] Validate scout outputs are valid JSON
- [ ] Validate aggregator merges cleanly
- [ ] Monitor first week: cost, memory, latency
- [ ] Adjust thresholds if needed
- [ ] Deploy GROUP 2, then GROUP 3

---

## Metrics (Weekly Review)

Every Friday 2 PM MT, report:

1. **Cost This Week**
   - GROUP 1 runs: X (cost: $Y)
   - GROUP 2 runs: X (cost: $Y)
   - GROUP 3 runs: X (cost: $Y)
   - Total: $Z / $200

2. **Escalations This Week**
   - GROUP 1: X escalations to Opus (reason: risk, execution, contradiction)
   - GROUP 2: X escalations (reason: ...)
   - GROUP 3: X escalations (reason: ...)

3. **Quality Metrics**
   - Scout gate failures: X (% of runs where scout output was invalid JSON)
   - Aggregator confidence: avg Y%
   - Latency: max Z minutes

4. **Budget Status**
   - Spend: $Z / $200 (X% of budget)
   - Alert level: Green (< $160) / Yellow (>= $160) / Red (>= $200)

---

## Known Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Scout generates invalid JSON | Aggregator gate checks; re-run if validation fails |
| Concurrent groups exceed 2 | Lock file protocol + pre-flight check (enforced) |
| Cloud costs exceed budget | Weekly tracking; auto-pause escalations at $160 |
| Scout timeout (>10 min) | Timeout enforced; return "incomplete" + retry next cycle |
| Aggregator contradicts itself | Escalate to Opus for conflict resolution |
| Scout misses required fields | Validation loop: re-prompt with stricter schema |

---

## Next Steps

1. **TODAY**: Create shell scripts + test GROUP 1 manually
2. **TOMORROW**: Deploy GROUP 1 live (8 AM + 2 PM runs)
3. **THIS WEEK**: Add GROUP 2 + GROUP 3 scaffolding
4. **NEXT WEEK**: All 3 groups live, running on schedule

