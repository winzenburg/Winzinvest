# Ollama Integration Roadmap

**Goal:** Replace all API calls with local Ollama for 100% cost savings + privacy

**Timeline:** Complete by Feb 23, 2026 (2-3 hours of work)

---

## Phase 1: Foundation ✅ DONE

| Item | Status | File |
|------|--------|------|
| Mistral 7B pulled | ✅ | (4.4 GB) |
| Neural-Chat 7B pulling | ⏳ 31% | (4.7 GB, ETA 2m16s) |
| Ollama client created | ✅ | `scripts/ollama-client.mjs` |
| Test script created | ✅ | `scripts/test-ollama-integration.mjs` |
| Integration guide created | ✅ | `OLLAMA-SETUP-COMPLETE.md` |

**Next:** Wait for neural-chat to finish (~2 min), then test.

---

## Phase 2: Test & Validate (5 minutes)

Once neural-chat finishes:

```bash
# Test all three task types
cd ~/.openclaw/workspace
node scripts/test-ollama-integration.mjs
```

Expected output:
- ✅ Quick Summary: 2-3 seconds
- ✅ Email Formatting: 3-4 seconds  
- ✅ Research Synthesis: 5-8 seconds

All should succeed. If any fail → models still loading.

---

## Phase 3: Integration (Priority Order)

### Priority 1: Content Writing Engine
**File:** `scripts/content-writing-engine.mjs`  
**Changes:** Replace OpenAI calls with Ollama  
**Effort:** 30 minutes  
**Impact:** Saves $0.30-0.60 per pillar + $0.05-0.10 per spoke

**Code template:**
```javascript
// Add import
import { generate, createPillarPrompt } from './ollama-client.mjs';

// Replace old API call with:
const pillarPrompt = createPillarPrompt(topic, stream);
const result = await generate('pillar-content', pillarPrompt);
const pillarContent = result.text;

// For spokes, use task types:
// - 'spoke-repurposing' for LinkedIn/Twitter/Email versions
// - 'email-formatting' for email summaries
```

### Priority 2: Research Agent
**File:** `scripts/research-agent.mjs`  
**Changes:** Replace synthesis API call with Ollama  
**Effort:** 15 minutes  
**Impact:** Saves $0.15-0.30 per research task

**Code template:**
```javascript
import { generate, createResearchPrompt } from './ollama-client.mjs';

const prompt = createResearchPrompt(topic, findings);
const result = await generate('research-synthesis', prompt);
const synthesis = result.text;
```

### Priority 3: Stream Orchestrators
**Files:** `content-factory-kinlet.mjs`, `content-factory-linkedin.mjs`  
**Changes:** Use Ollama for all generation steps  
**Effort:** 20 minutes  
**Impact:** Full automation cost → $0

### Priority 4: Morning Brief
**File:** `scripts/morning-brief.mjs`  
**Changes:** Use Ollama for summaries if currently using API  
**Effort:** 10 minutes  
**Impact:** Saves $0.05-0.10 per brief

---

## Phase 4: Quality Assurance (30 minutes)

### Test 1: Full Pillar Generation
```bash
# Trigger: Content: Kinlet Managing caregiver burnout
# Verify: Pillar content generates, quality acceptable
# Check: Response time < 20 seconds
```

### Test 2: Full Spoke Repurposing
```bash
# From pillar above, generate:
# - LinkedIn thread (2-3 min)
# - Email version (1-2 min)
# - Twitter thread (1-2 min)
# Verify: All generate, consistency maintained
```

### Test 3: Research → Content Flow
```bash
# Trigger: Research: AI in caregiving
# Verify: Research runs, then auto-generates Kinlet content
# Check: Full pipeline takes < 5 minutes
```

### Test 4: Email Summary
```bash
# Verify: Email with drafts + action buttons delivers
# Check: Can approve, revise, discard from email
```

---

## Estimated Time Savings (Annual)

| Scenario | Hours Saved | $ Saved |
|----------|-------------|---------|
| **Pillar content generation** | 0.5h/week × 52 = 26h | $480-600 (API costs) |
| **Research synthesis** | 0.25h/week × 52 = 13h | $100-150 |
| **Spoke generation** | 0.25h/week × 52 = 13h | $50-100 |
| **Total** | **52 hours** | **$630-850** |

Plus: No rate limits, no API latency, complete local privacy.

---

## Performance Targets (After Integration)

| Task | API Time | Ollama Time | Speedup |
|------|----------|------------|---------|
| Pillar (1,500w) | 45s | 12-15s | 3x faster |
| Email formatting | 20s | 3-4s | 5x faster |
| Research synthesis | 30s | 8-10s | 3x faster |
| Full overnight run | ~5 minutes | ~1-2 minutes | 2.5x faster |

---

## Rollback Plan (If Issues Arise)

If Ollama quality is insufficient for production:

1. Keep old API code in comments
2. Add feature flag: `OLLAMA_ENABLED=true` in `.env`
3. Revert to API by setting `OLLAMA_ENABLED=false`
4. Log: What quality issue occurred

Example:
```javascript
if (process.env.OLLAMA_ENABLED !== 'false') {
  result = await generate('pillar-content', prompt);
} else {
  result = await openai.createChatCompletion({...}); // fallback
}
```

---

## Monitoring & Optimization

After Phase 4, monitor:

| Metric | Target | Check Frequency |
|--------|--------|-----------------|
| Response time | <20s per task | Daily logs |
| Output quality | "Publish-ready" | User feedback |
| Crash rate | 0% | Weekly |
| Cache hit rate | >30% | Weekly |
| Memory usage | <6 GB | Daily |

Optimize based on real usage patterns.

---

## Next Steps (Right Now)

1. ✅ Neural-Chat pull completes (~2 min)
2. ⏳ Run: `node scripts/test-ollama-integration.mjs`
3. ⏳ If all pass → Start Phase 3 integration
4. ⏳ Integrate Priority 1-4 in order
5. ⏳ Run QA tests
6. ⏳ Full deployment

**ETA for complete integration:** Feb 23, 2026, 1:00 AM MT (2-3 hours)

---

**Questions before we start?** Let me know if you want to adjust the priority order or scope.

---

*Status: Foundation complete. Awaiting neural-chat model (~2min). Ready to test & integrate.*
