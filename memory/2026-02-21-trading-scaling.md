# February 21, 2026 - Trading Performance Tracking & Scaling Plan

## Strategy: Test → Validate → Scale

**Core Principle:** Only increase trade size/frequency when data proves profitability.

---

## Three-Tier Scaling Model

### TIER 1: Conservative (Weeks 1-2)
- Trade frequency: 2-4/month (opportunistic only)
- Position sizes: Current (1-share canary)
- Capital allocation: <10% of buying power
- Success metric: Positive P&L for 2 consecutive weeks
- Win rate target: 50%+

### TIER 2: Moderate (Weeks 3-4)
- Trade frequency: 4-6/month
- Position sizes: +50% increase
- Capital allocation: 10-20% of buying power
- Success metric: Positive P&L for 2 consecutive weeks + 55%+ win rate
- Win rate target: 55%+

### TIER 3: Aggressive (Month 2+)
- Trade frequency: 8-12/month
- Position sizes: Full allocation based on risk rules
- Capital allocation: 30-50% of buying power
- Success metric: Monthly P&L > $1,000 + 60%+ win rate
- Win rate target: 60%+

---

## Weekly Reporting Schedule

**Every Friday at 5:00 PM MT:**
- P&L calculation (wins vs losses)
- Win rate analysis
- Covered call performance
- Cash-secured put performance
- Daily loss limit compliance
- Scaling recommendation

**Email delivered:** Weekly performance review with actionable insights

---

## Strategy Modification Rules

### Pause If:
- 2 consecutive weeks of negative P&L
- Daily loss limit breached more than once per week
- Win rate drops below 50% for 2 weeks

### Scale Up If:
- 2 consecutive weeks of positive P&L
- Win rate > target for current tier
- Daily loss limit never breached

### Modify Strategy If:
- Premium collected is too low
- Market regime changes (bull → bear)
- Win rate plateaus below 60%

**Process:** Test modification in paper trading first, then implement

---

## Automated Tracking

### Daily
- Portfolio email at 4:00 PM MT (P&L summary)
- Options scan at 3:00 PM MT (opportunity identification)
- Daily loss limit enforcement

### Weekly (Friday 5 PM)
- Performance review email
- Win rate calculation
- Scaling tier assessment
- Trade opportunity summary

### Monthly
- 30-day P&L analysis
- Strategy effectiveness review
- Scaling decision for next tier
- Modification recommendations

---

## Files Created

- `PERFORMANCE_TRACKING.md` — Full tracking framework
- `weekly_performance_review.py` — Automated weekly report
- `com.pinchy.trading.weekly-review.plist` — Friday 5 PM LaunchAgent

---

## Starting Position (Monday Feb 24)

**Portfolio Status:**
- Current: 75 positions queued for closure (executes Monday 9:30 AM)
- Next: Build new positions via swing trading strategy
- Options: Begin covered call + put scanning once positions established

**Profitability Gates:**
1. Week 1-2: Must be profitable (positive P&L) → Continue
2. Week 3-4: Must show 55%+ win rate → Scale to TIER 2
3. Month 2+: Must achieve $1,000+/month → Scale to TIER 3

**No scaling without proof.** Numbers drive decisions.

---

## Success Definition

✅ **Week 1-2 Success:** Positive P&L two weeks running
✅ **Week 3-4 Success:** 55%+ win rate, continue scaling
✅ **Month 2 Success:** $1,000+/month at TIER 3

❌ **Failure:** Negative P&L two weeks → Pause and modify strategy

---

## Next Actions (Monday)

1. Portfolio liquidates at market open (9:30 AM)
2. Begin swing trading (identify new long positions)
3. Start options scanning at 3 PM (covered call candidates)
4. Daily portfolio email at 4 PM (shows zero positions initially)
5. First weekly review Friday Feb 28 at 5 PM (preliminary data)
6. Make tier decision for Week 3 based on Friday report

---

**Philosophy:** We're not guessing. We measure, we validate, then we scale.

Every tier progression requires proof. Every strategy change gets tested. This is how we turn profitability from hope into certainty.
