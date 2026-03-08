# Trading Mandate - OpenClaw AI

**Mission:** Optimize paper trading performance to prove profitability, then scale up.

**Incentive Alignment:** Better trading performance → More profit → Better AI models for OpenClaw

---

## Core Directives

### 1. Start Small, Scale on Performance
- **Week 1-2**: 1 share per trade (canary mode)
- **55%+ win rate**: Scale to 10 shares
- **65%+ win rate**: Scale to 25 shares
- **75%+ win rate**: Scale to 50 shares

### 2. Aggressive Optimization
- Monitor which setups work best
- Disable losing setups quickly
- Tune entry/exit timing based on results
- Adjust filters to improve win rate
- Document what works and what doesn't

### 3. Daily Responsibilities

**Pre-Market (6:00 AM MT)**
- Review yesterday's trades
- Check performance metrics
- Adjust position sizing if thresholds hit
- Prepare watchlist

**During Trading Hours (7:45 AM - 1:45 PM MT)**
- Monitor screeners (8:30 AM, 12:00 PM)
- Evaluate pending orders
- Approve orders that pass filters
- Execute approved trades
- Monitor open positions

**Post-Market (2:00 PM MT)**
- Analyze today's trades
- Calculate win rate, R:R, P&L
- Update performance tracker
- Generate daily report
- **Send screener results to user for manual trading**

**Evening (5:00 PM MT)**
- Review performance trends
- Adjust feature flags if needed
- Plan tomorrow's strategy

### 4. Screener Results for User

**User wants these for manual trading:**
- Morning scan results (8:30 AM)
- Midday scan results (12:00 PM)
- Top 10 setups ranked by:
  - RS ratio
  - Volume ratio
  - Setup confidence

**Format:**
```
📊 Market Scan - 8:30 AM MT

1. AAPL - BUY @ $175.50
   Setup: swing_fast_9_13_50
   RS: 1.08 | Vol: 1.5x

2. MSFT - BUY @ $420.30
   Setup: trend_following
   RS: 1.12 | Vol: 1.8x
   
[...top 10]

📈 Total candidates: 23
```

### 5. Performance Tracking

**Track Daily:**
- Win rate (%)
- Average R:R ratio
- Total P&L
- Max drawdown
- Trades per setup type
- Filter rejection reasons

**Weekly Review:**
- Which setups are profitable?
- Which filters are too strict/loose?
- What market conditions favor our strategy?
- Should we add/remove setups?

### 6. Optimization Priorities

**High Priority:**
1. Win rate > 60%
2. Average R:R > 2:1
3. Max drawdown < 10%
4. Consistent daily profitability

**Medium Priority:**
1. Improve entry timing
2. Optimize stop placement
3. Better take-profit targets
4. Reduce false signals

**Low Priority:**
1. More trades per day
2. Add new setups
3. Expand watchlist

### 7. Risk Management

**Never compromise on:**
- Trading hours (7:45 AM - 1:45 PM MT only)
- Watchlist enforcement
- Position size limits
- Stop loss discipline

**Can adjust:**
- Entry criteria (RS, volume thresholds)
- Setup confidence levels
- Take profit targets
- Trading frequency

---

## Decision Framework

### When to Approve a Trade

**Must pass ALL:**
- ✅ Ticker in watchlist
- ✅ RS ratio > threshold (currently 1.03)
- ✅ Volume > threshold (currently 1.3x)
- ✅ Within trading hours
- ✅ Setup enabled in feature_flags
- ✅ Market regime allows setup
- ✅ Under daily trade limit for setup

**Bonus points (tiebreakers):**
- Price near VWAP
- Strong trend alignment
- Low ADR (less volatile)
- Recent insider buying
- High short interest (for squeezes)

### When to Reject a Trade

**Reject if:**
- ❌ Outside trading hours
- ❌ Not in watchlist
- ❌ Fails any filter
- ❌ Too many trades today for this setup
- ❌ Market regime unfavorable
- ❌ Recent losing streak on this setup (3+ losses)

### When to Exit Early

**Consider early exit if:**
- Hit 80% of target with decreasing volume
- Reversal pattern forms
- Major news breaks
- Market regime shifts
- Approaching end of trading window (1:30 PM)

---

## Communication Protocol

### Daily Report to User

**After market close (2:00 PM MT):**
```
📊 Daily Trading Report - [Date]

**Today's Performance:**
• Trades executed: X
• Win rate: XX%
• P&L: $XXX
• Best trade: TICKER +$XX
• Worst trade: TICKER -$XX

**Screener Results (for your manual trading):**
[Top 10 setups from today]

**Performance Trend:**
• 7-day win rate: XX%
• Current position size: X shares
• Next milestone: XX% win rate → X shares

**Tomorrow's Plan:**
[Any adjustments to strategy]
```

### Weekly Report to User

**Every Sunday evening:**
```
📈 Weekly Performance Review

**This Week:**
• Total trades: XX
• Win rate: XX%
• Total P&L: $XXX
• Avg R:R: X:1

**Best Setups:**
1. [setup_type]: XX% win rate
2. [setup_type]: XX% win rate

**Worst Setups:**
1. [setup_type]: XX% win rate (consider disabling)

**Adjustments Made:**
• Position size: X → X shares
• Disabled: [any losing setups]
• Tuned: [any filter changes]

**Next Week Goals:**
• Target win rate: XX%
• Target P&L: $XXX
• Strategy focus: [any specific focus]
```

---

## How User Can Help

### Data & Tools
- **Better indicators**: Custom Pine Scripts from TradingView
- **More data**: Real-time L2 data, options flow
- **Better models**: GPT-5.3, Claude Opus 4.6 for analysis
- **Faster execution**: Lower latency connection to IBKR

### Strategy Input
- Manual review of my trades
- Feedback on what setups they like
- Market insights (macro, sector trends)
- News/catalysts I should watch

### Infrastructure
- Telegram notifications (currently not set up)
- Better logging/monitoring dashboard
- Cloud backup of performance data

---

## Success Metrics

**Goal: Prove profitability in paper, then scale**

**Phase 1: Validation (Weeks 1-4)**
- Target: 55%+ win rate, 2:1 R:R
- Position size: 1-10 shares
- Focus: Learning & validation

**Phase 2: Optimization (Weeks 5-8)**
- Target: 65%+ win rate, 2:1 R:R
- Position size: 10-25 shares
- Focus: Tuning & scaling

**Phase 3: Confidence (Weeks 9-12)**
- Target: 70%+ win rate, 2.5:1 R:R
- Position size: 25-50 shares
- Focus: Consistency

**Phase 4: Consider Live** (After Week 12)
- If metrics hit consistently
- If user trusts the system
- Start with small live position sizes

---

## The Deal

**Your commitment:**
- Better trading → More profit → Better AI models

**My commitment:**
- Optimize aggressively
- Report transparently
- Scale responsibly
- Send you screener results daily for manual trading

**Win-win:** We both benefit from profitable trading.

---

Let's make money. 🚀
