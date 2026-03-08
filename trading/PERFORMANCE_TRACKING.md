# Performance Tracking & Strategy Scaling

**Objective:** Validate profitability, then scale confidently

---

## Week 1 Target (Feb 24-28)

| Metric | Target | Success Criteria |
|--------|--------|------------------|
| Covered Calls | 1-2 contracts | $200+ premium collected |
| Cash-Secured Puts | 0-1 contracts | $100+ premium collected |
| Total P&L | +$300+ | Positive week = strategy is working |
| Daily Loss Limit Hits | 0 | $1,350 limit never breached |
| Win Rate | 60%+ | More wins than losses |

**Pass/Fail:** If total P&L > $0 and daily limits never breached → **WEEK 1 PASSED**

---

## Profitability Tiers

### TIER 1: Conservative (Weeks 1-2)
**Goal:** Prove the strategy works

- **Trade Frequency:** 2-4 trades/month (opportunistic only)
- **Position Sizes:** Current 1-share canary testing
- **Capital Allocation:** <10% of buying power
- **Success Metric:** Positive P&L for 2 consecutive weeks
- **Next Action:** If passed → Move to TIER 2

### TIER 2: Moderate (Weeks 3-4)
**Goal:** Build confidence, scale cautiously

- **Trade Frequency:** 4-6 trades/month
- **Position Sizes:** Increase by 50% (if TIER 1 succeeded)
- **Capital Allocation:** 10-20% of buying power
- **Success Metric:** Positive P&L for 2 consecutive weeks + 55%+ win rate
- **Next Action:** If passed → Move to TIER 3

### TIER 3: Aggressive (Month 2+)
**Goal:** Optimize profitability at scale

- **Trade Frequency:** 8-12 trades/month
- **Position Sizes:** Full 100% allocation (based on risk rules)
- **Capital Allocation:** 30-50% of buying power
- **Success Metric:** Monthly P&L > $1,000 + 60%+ win rate
- **Next Action:** Maintain or optimize based on review

---

## Weekly Review Cadence (Every Friday 5 PM MT)

### Metrics to Track

```
WEEKLY P&L REPORT
================

Total Trades: ___
Win/Loss Record: ___W / ___L
Win Rate: ___%

Covered Calls:
  - Contracts sold: ___
  - Premium collected: $____
  - Expired profitable: ___%

Cash-Secured Puts:
  - Contracts sold: ___
  - Premium collected: $____
  - Called away/expired profitable: ___%

Daily P&L:
  - Best day: +$____
  - Worst day: -$____
  - Average trade: $____

Risk Metrics:
  - Daily loss limit hits: __
  - Max drawdown: ___%
  - Largest loss: -$____

Tier Status:
  - Current: TIER _ (Conservative/Moderate/Aggressive)
  - Assessment: PASS / NEEDS ADJUSTMENT / FAIL
  - Next action: _______________
```

---

## Strategy Modification Protocol

**When to modify:**
1. Win rate drops below 50% for 2 consecutive weeks
2. Daily loss limit hit more than once per week
3. Premium collected is too low to justify trade time
4. Market regime changes (bull → bear)

**Modification process:**
1. **Propose change** (email to self with rationale)
2. **Paper trade test** (1 week minimum)
3. **Review results** (did modification improve P&L?)
4. **Implement or revert** based on test results

**Example modifications:**
- Adjust strike selection (get more premium but less safety)
- Change expiration (weekly → monthly for less management)
- Expand watchlist (more opportunities vs more risk)
- Increase position size (scale what's working)

---

## Scaling Rules

### RULE 1: Only Scale What's Profitable
```
IF weekly P&L > $0
  AND daily loss limit never breached
  AND win rate > 50%
THEN
  Move to next tier after 2 consecutive passing weeks
ELSE
  Stay in current tier OR move down
```

### RULE 2: Stop If Losing
```
IF 2 consecutive weeks of negative P&L
THEN
  Pause new trades
  Review strategy modifications
  Retest in paper trading
  Only resume after profitable test week
```

### RULE 3: Increase Position Size Carefully
```
Current Position: 1 share / 1 contract
Tier 1 success (week 2) → 1.5x size
Tier 2 success (week 4) → 2x size
Tier 3 success (month 2) → Full allocation per risk rules
```

---

## Monthly Review (End of Each Month)

### 30-Day Assessment

```
MONTH: ____________

Total P&L: $_______
Total Trades: ____
Win Rate: ___%
Best Trade: +$____
Worst Trade: -$____

Strategy Assessment:
☐ WORKING - Continue as-is
☐ WORKING BUT SLOW - Can we increase frequency safely?
☐ MARGINAL - Need modifications to improve ROI
☐ NOT WORKING - Major strategy change needed

Modifications to Test Next Month:
1. ___________________________
2. ___________________________

Portfolio Health:
- Largest loss taken: -$____
- Days we hit daily limit: __
- Emergency brake used: __/month

Next Month Target:
- Tier: TIER _
- Trade Frequency: ___/month
- Min P&L Goal: $_____
```

---

## Escalation Protocol

**Week 1-2 (Testing Phase)**
- Daily monitoring of P&L
- Weekly report every Friday 5 PM
- NO scaling — validation only

**Week 3-4 (Early Validation)**
- If Tier 1 passed: Begin Tier 2
- If Tier 1 failed: Pause, review, modify, retest

**Month 2+ (Optimization)**
- Scale if metrics support it
- Modify strategy if returns plateau
- Target: Profitable by end of Month 1

---

## Success Definition

### Phase 1: Profitability (Weeks 1-2)
✅ **SUCCESS:** Positive P&L for 2 consecutive weeks  
❌ **FAILURE:** Negative P&L OR daily loss limit breached  

### Phase 2: Consistency (Weeks 3-4)
✅ **SUCCESS:** 55%+ win rate + Positive P&L  
❌ **FAILURE:** Win rate < 50% OR monthly P&L negative  

### Phase 3: Scale (Month 2+)
✅ **SUCCESS:** Monthly P&L > $1,000 + 60%+ win rate  
❌ **FAILURE:** Returns plateau or decline → Modify strategy  

---

## Tracking Files

- **Daily:** `logs/portfolio_tracker.log`
- **Weekly:** Email report every Friday 5 PM
- **Monthly:** `MONTHLY_REVIEW_[DATE].md`
- **Performance:** `performance_tracker.py` (runs Fridays)

---

## Next Steps (Monday)

1. ✅ Portfolio liquidated (all positions close Monday)
2. ⏳ Wait for new swing trade positions to establish
3. ⏳ Begin covered call + cash-secured put scanning (3 PM daily)
4. 📊 Track performance daily
5. 📧 Friday weekly report (5 PM)
6. 🎯 Tier assessment end of Week 2

---

**Key Principle:** We only scale when data proves the strategy works. No ego, no assumptions — just numbers.

Start conservative, build confidence, then scale intelligently.
