# 30-Day System Validation Plan

**Start Date:** February 19, 2026 (tomorrow)  
**End Date:** March 20, 2026  
**Current Profile:** Conservative ($45k, no leverage)

---

## Phase 1: Prove the System (Days 1-30)

### Success Criteria ("Proven")

To advance to Phase 2 (moderate leverage), you must hit **ALL** of these:

| Metric | Target | Why It Matters |
|--------|--------|----------------|
| **Total Trades** | ≥10 completed | Enough data to measure edge |
| **Win Rate** | ≥50% | Positive expectancy baseline |
| **Average R-Ratio** | ≥1.5 | Winners bigger than losers |
| **Max Drawdown** | ≤10% | Risk control working |
| **Daily Loss Limits Hit** | 0 | Circuit breakers not needed |
| **Margin Calls** | 0 | N/A for Phase 1 (no leverage) |
| **System Uptime** | >95% | Technical reliability |
| **False Signals** | <30% | Quality of entry signals |

### Weekly Checkpoints

**Every Sunday at 6PM:**
1. Run performance dashboard
2. Review all trades (winners + losers)
3. Answer checkpoint questions
4. Update validation tracker

---

## Week 1 (Feb 19-23): System Familiarization

### Goals
- [ ] First live trade executed successfully
- [ ] Test approve/reject workflow in real market
- [ ] Get comfortable with Telegram alerts
- [ ] Verify all safety features working

### Checkpoint Questions (Sunday Feb 23)
1. Did all alerts arrive on time?
2. Were approve/reject buttons responsive?
3. Did orders execute correctly in IBKR?
4. Any system errors or false positives?
5. Comfort level: 1-10?

### Expected Activity
- **Trades:** 1-3
- **Focus:** Learning the system, not P&L

---

## Week 2 (Feb 24-Mar 2): Build Confidence

### Goals
- [ ] Execute 3-5 trades
- [ ] Follow the plan (don't override filters)
- [ ] Track why you reject signals
- [ ] Identify any issues with screener/indicator

### Checkpoint Questions (Sunday Mar 2)
1. Win rate so far?
2. Are rejected trades actually bad? (Review them)
3. Any patterns in winners vs. losers?
4. System improvements needed?
5. Comfort level: 1-10?

### Expected Activity
- **Trades:** 3-5 cumulative (4-8 total)
- **Focus:** Trust the system, follow signals

---

## Week 3 (Mar 3-9): Refine Strategy

### Goals
- [ ] Hit 10 total trades milestone
- [ ] Calculate actual win rate and R-ratio
- [ ] Tune thresholds if needed (RS, Z-score, etc.)
- [ ] Test options income layer

### Checkpoint Questions (Sunday Mar 9)
1. Actual win rate vs. target (50%+)?
2. Average R-ratio vs. target (1.5+)?
3. Are signals too frequent or too rare?
4. Should we adjust filters?
5. Options income working? How many deployed?

### Expected Activity
- **Trades:** 10+ cumulative
- **Focus:** Performance vs. targets

---

## Week 4 (Mar 10-16): Validation Decision

### Goals
- [ ] Review all 30 days of data
- [ ] Calculate final metrics
- [ ] Decide: Proven? Not yet?
- [ ] If proven: Plan Phase 2 ramp-up

### Checkpoint Questions (Sunday Mar 16)
1. Did we hit all success criteria?
2. What worked better than expected?
3. What needs improvement?
4. Ready to add leverage? (Honest answer)
5. If not ready: What's blocking validation?

### Expected Activity
- **Trades:** 12-15+ cumulative
- **Focus:** Go/no-go decision

---

## Phase 1 Failure Modes (What to Watch For)

### Red Flags (Stop and Reassess)

| Issue | What It Means | Action |
|-------|---------------|--------|
| **Win rate <40%** | System edge questionable | Review screener/indicator logic |
| **Avg R-ratio <1.0** | Winners not big enough | Adjust targets or hold longer |
| **Max drawdown >15%** | Risk controls failing | Tighten stops or reduce size |
| **False signals >50%** | Filters too loose | Increase RS/volume thresholds |
| **You keep overriding** | Trust issue or system issue | Figure out why, fix it |

### What to Do If You Fail Validation

**Option 1: Extend Phase 1**
- Continue conservative for another 30 days
- Fix identified issues
- Re-validate

**Option 2: Pause and Debug**
- Use kill switch
- Review all trades in detail
- Rebuild confidence
- Resume when ready

**Option 3: Adjust Targets**
- Maybe 10 trades isn't enough (extend to 20)
- Maybe 50% win rate is too aggressive (accept 45%)
- Recalibrate based on actual market conditions

---

## Phase 2: Moderate Leverage (Days 31-60)

**Activate ONLY if Phase 1 proven.**

### Changes from Phase 1

| Setting | Phase 1 | Phase 2 |
|---------|---------|---------|
| **Position size** | $45k | $150k |
| **Leverage** | None | 0.75x ($50k margin) |
| **Risk per trade** | $450 (1%) | $1,000 (0.5% of $200k) |
| **Daily loss limit** | $1,350 | $3,000 |
| **Max positions** | 5 | 6 |

### Phase 2 Success Criteria (To reach Phase 3)

- ≥20 more trades (30+ total)
- Win rate maintained ≥50%
- Avg R-ratio maintained ≥1.5
- Max drawdown ≤8% (tighter with leverage)
- No margin issues
- Comfortable managing 6 concurrent positions

### Phase 2 Weekly Checkpoints

Same format as Phase 1, but with additional questions:
- Is leverage causing emotional stress?
- Are you sleeping well?
- Any margin warnings from IBKR?
- Performance degrading or maintaining?

---

## Phase 3: Full Leverage (Days 61+)

**Activate ONLY if Phase 2 proven.**

### Changes from Phase 2

| Setting | Phase 2 | Phase 3 |
|---------|---------|---------|
| **Position size** | $150k | $300k |
| **Leverage** | 0.75x | 1.5x ($100k margin) |
| **Risk per trade** | $1,000 | $1,500 (0.75% of $200k) |
| **Daily loss limit** | $3,000 | $4,000 |
| **Max positions** | 6 | 8 |

### Phase 3 Ongoing Monitoring

**Monthly reviews (not weekly):**
- Maintain all success criteria
- Track actual leverage used (should average 1.3-1.5x)
- Monitor correlation and sector exposure
- Review margin cushion (should stay >$75k)
- Calculate returns vs. unleveraged baseline

**Delever triggers:**
- Win rate drops below 45% for 2 consecutive months
- Max drawdown exceeds 12%
- Margin cushion falls below $50k
- Daily loss limit hit 2x in one month

---

## Tracking Tools

### Daily (Automated)
- Performance dashboard updates
- Daily P&L calculation
- Leverage ratio tracking
- Margin cushion check

### Weekly (Manual - Sunday 6PM)
- Run: `python3 scripts/performance_dashboard.py`
- Review: All trades executed this week
- Document: Lessons learned, patterns observed
- Update: Validation checklist (below)

### Monthly (Manual - Last Friday)
- Full performance review
- Options income analysis
- System health check
- Go/no-go for next phase

---

## Validation Checklist

Copy this to a new file each week and fill it out:

```markdown
# Week [N] Validation Checklist - [Date]

## Metrics
- Total trades: [ ]
- Wins: [ ] | Losses: [ ]
- Win rate: [ ]%
- Avg R-ratio: [ ]
- Max drawdown: [ ]%
- Daily loss limits hit: [ ]

## Qualitative
- System uptime issues? [ ]
- False signals? [ ] / [ ] total ([ ]%)
- Overrides (didn't follow system)? [ ]
- Comfort level (1-10): [ ]

## Lessons Learned
1. 
2. 
3. 

## Next Week Goals
1. 
2. 
3. 

## Phase 1 Progress
- [ ] ≥10 trades
- [ ] ≥50% win rate
- [ ] ≥1.5 avg R
- [ ] ≤10% max drawdown
- [ ] 0 daily loss limits hit
- [ ] >95% uptime
- [ ] <30% false signals

**Status:** ON TRACK | AT RISK | BEHIND
```

---

## The Psychology Part

### What "Proven" Really Means

It's not just about hitting the numbers. It's about:

1. **Trust:** Do you trust the signals?
2. **Discipline:** Do you follow the plan?
3. **Calm:** Can you sleep at night?
4. **Resilience:** Can you handle a 3-loss streak?

**If you're hitting the numbers but feel stressed → not ready for leverage yet.**

### Red Flags for Premature Scaling

- "Just one more big win and I'll scale up"
- "I can manage more risk, the numbers are conservative"
- "My friends are making more, I should use full leverage"
- "I'm bored, let me add more positions"

**If you catch yourself thinking these → pause and reassess.**

### Green Lights for Scaling

- "The system is working, results are predictable"
- "I'm following the plan without overriding"
- "Losses don't stress me, they're part of the system"
- "I want more capital deployed because the edge is proven"

---

## Commitment

By following this validation plan, you commit to:

✅ 30 days minimum before any leverage  
✅ Hit ALL success criteria, not just some  
✅ Weekly honest reviews (don't skip them)  
✅ Delever immediately if criteria fail  
✅ Prioritize learning over P&L in Phase 1  

**The system will be here in 30 days, 60 days, 6 months.**

**There is no rush.**

**Prove it works. Then scale.**

---

**Start Date:** Tomorrow (Feb 19, 2026)  
**First Checkpoint:** Sunday, Feb 23, 2026 at 6PM MT  
**Phase 1 Decision:** Sunday, Mar 16, 2026

Good luck! 🎯
