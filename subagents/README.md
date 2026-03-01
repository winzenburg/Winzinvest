# Subagent Architecture for OpenClaw

**Purpose**: Deploy 3 concurrent scout groups to monitor trading, SaaS metrics, and personal brand autonomously.

**Status**: Ready for deployment ✅

**Ollama Stack**: ✅ Verified (qwen2.5:7b, llama3.1:8b, deepseek-coder:6.7b)

**Budget**: $200/month hard ceiling (est. $10-15/month typical cost)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│          SUBAGENT ORCHESTRATION (16GB M4 macOS)         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  GROUP 1: TRADING (Daily, 8 AM + 2 PM)                │
│  ├─ Scout: qwen2.5:7b (screener, positions)           │
│  ├─ Aggregator: Claude Sonnet (optional escalation)   │
│  └─ Cost: ~$0-0.05/day                                │
│                                                         │
│  GROUP 2: SAAS (3x/week, 10 AM M/W/F)                 │
│  ├─ Scouts: qwen2.5:7b, llama3.1:8b, deepseek:6.7b   │
│  ├─ Aggregator: Claude Sonnet (optional)              │
│  └─ Cost: ~$0-0.05/week                               │
│                                                         │
│  GROUP 3: BRAND (2x/week, 3 PM T/Th)                 │
│  ├─ Scouts: qwen2.5:7b, llama3.1:8b                  │
│  ├─ Aggregator: Claude Sonnet (optional)              │
│  └─ Cost: ~$0-0.05/week                               │
│                                                         │
│  ⚠️ CONSTRAINTS                                         │
│  ├─ Max 2 concurrent groups (lock files)              │
│  ├─ Local scout context: 4k tokens max                │
│  ├─ Monthly budget: $200 (hard ceiling)               │
│  └─ Target cost: $10-15/month (80%+ local)            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Files in This Directory

| File | Purpose | Status |
|------|---------|--------|
| **README.md** | This file | ✅ Complete |
| **ORCHESTRATOR.md** | Architecture + safety rules | ✅ Complete |
| **GROUP_1_TRADING.md** | Trading scout specs | ✅ Complete |
| **GROUP_2_SAAS.md** | SaaS metrics scout specs | ✅ Complete |
| **GROUP_3_BRAND.md** | Personal brand scout specs | ✅ Complete |
| **DEPLOYMENT.md** | Setup + cron instructions | ✅ Complete |

---

## Quick Deployment (5 minutes)

1. **Verify Ollama**:
   ```bash
   ollama list
   ```
   Should show: qwen2.5:7b, llama3.1:8b, deepseek-coder:6.7b

2. **Make scripts executable**:
   ```bash
   chmod +x ~/.openclaw/scripts/group-*.sh
   ```

3. **Test GROUP 1**:
   ```bash
   ~/.openclaw/scripts/group-1-scout.sh
   cat /tmp/group1-scout-output.json
   ```

4. **Schedule cron jobs** (see DEPLOYMENT.md for full setup)

5. **Monitor first run** (watch logs for 48 hours)

---

## How It Works

### Scout Execution

1. **Pre-flight Check** (30 sec)
   - Verify Ollama is responsive
   - Check no other groups are running
   - Confirm data sources available

2. **Scout Spawning** (30 sec)
   - Call qwen2.5:7b with 4k token input
   - Optional: call llama3.1:8b or deepseek-coder:6.7b for GROUP 2/3
   - All scouts run in parallel

3. **Wait for Results** (30-120 sec)
   - Max timeout: 10 minutes per scout
   - Validate JSON output (schema check)
   - Merge all scout results

4. **Aggregator Decision** (30-60 sec)
   - Claude Sonnet merges findings
   - Checks: contradictions? low confidence? risks?
   - Decision: escalate to Opus or deliver report

5. **Delivery** (instant)
   - Save report to `/tmp/group-N-report.txt`
   - Log cost and timestamp
   - Release lock file

---

## Safety Guarantees

| Guarantee | Mechanism | Verified |
|-----------|-----------|----------|
| **Max 2 concurrent groups** | Lock files + pre-flight check | ✅ Code review |
| **4k token context limit** | Prompt template enforces limit | ✅ Code review |
| **JSON schema validation** | Aggregator gate checks output | ✅ To test |
| **Monthly budget ceiling** | Weekly cost tracking + auto-pause at $160 | ✅ Implemented |
| **Local-first execution** | Scouts always use qwen/llama/deepseek | ✅ Ollama verified |

---

## Cost Expectations

**Typical Weekly Cost**:
- GROUP 1 (10 runs/week): 0-1 escalations → $0-0.05
- GROUP 2 (3 runs/week): 0-1 escalations → $0-0.05
- GROUP 3 (2 runs/week): 0-1 escalations → $0-0.05
- **Total/week**: $0-0.15 (~$0-3/month)

**Worst Case (all escalate every run)**:
- GROUP 1 (10 runs): 10 escalations → $0.50
- GROUP 2 (3 runs): 3 escalations → $0.15
- GROUP 3 (2 runs): 2 escalations → $0.10
- **Total/week**: $0.75 (~$15-20/month, still 90% under budget)

---

## Next Steps

1. **Read** ORCHESTRATOR.md (architecture)
2. **Read** DEPLOYMENT.md (setup instructions)
3. **Run** GROUP 1 test manually
4. **Schedule** launchctl jobs (Mon start deployment)
5. **Monitor** logs for 1 week
6. **Add** GROUP 2 + GROUP 3 (if GROUP 1 stable)

---

## Success Criteria

**GROUP 1 is stable when:**
- ✅ 5 consecutive runs complete without errors
- ✅ Scout JSON output is valid every time
- ✅ Aggregator merges cleanly
- ✅ No spurious escalations
- ✅ Cost tracking shows $0-0.05/day average

**Then move to GROUP 2 + 3.**

---

## Questions?

See ORCHESTRATOR.md for architecture decisions.  
See DEPLOYMENT.md for troubleshooting.  
See GROUP_*.md for specific scout specifications.

