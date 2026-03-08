# Paper → Live Trading Transition Guide

**Current Setup:** Paper trading account (simulated)  
**Target:** Live trading account ($200,000 actual capital)

---

## ⚠️ CRITICAL: Do NOT Switch Until Phase 1 Complete

**You are currently in Phase 1 validation (30 days paper trading).**

**Switch to live ONLY after:**
- ✅ 30 days of paper trading complete
- ✅ ≥10 completed trades
- ✅ ≥50% win rate proven
- ✅ ≥1.5 avg R-ratio achieved
- ✅ System reliability validated (>95% uptime)
- ✅ You are comfortable with workflow
- ✅ Zero emotional stress with paper losses

**Target date to consider switching:** March 20, 2026 (after Phase 1 validation)

---

## Technical Differences: Paper vs. Live

### Interactive Brokers Setup

| Setting | Paper Trading | Live Trading |
|---------|---------------|--------------|
| **TWS/Gateway** | Paper Trading mode | Live Trading mode |
| **Port** | 7497 | 7496 |
| **Account** | DU4661622 (simulated) | U4XXXXXX (your real account) |
| **Capital** | Unlimited fake money | $200,000 real money |
| **Order fills** | Instant, ideal | Real slippage, delays |
| **Risk** | Zero | 100% real |

### Key Behavioral Differences

**Paper trading:**
- Every order fills instantly at mid-price
- No slippage, no partial fills
- Can test recklessly without consequence
- Emotions are minimal (not real money)

**Live trading:**
- Orders may not fill immediately
- Slippage on market orders (especially illiquid stocks)
- Partial fills possible
- **Emotions intensify** (real money at stake)
- Need to respect liquidity

---

## Step-by-Step Transition Process

### Phase 1: Final Paper Trading Checks (Before Switching)

**Week before go-live:**

1. **Review all Phase 1 metrics:**
   ```bash
   cd /Users/pinchy/.openclaw/workspace/trading
   python3 scripts/performance_dashboard.py
   ```
   
   Verify:
   - [ ] Win rate ≥50%
   - [ ] Avg R-ratio ≥1.5
   - [ ] Max drawdown ≤10%
   - [ ] All safety features working

2. **Test every scenario in paper:**
   - [ ] Approve trade → executes correctly
   - [ ] Reject trade → logs correctly
   - [ ] Daily loss limit → blocks new trades
   - [ ] Kill switch → stops all trading
   - [ ] Earnings blackout → rejects correctly

3. **Psychological check:**
   - [ ] Can you handle a 3-loss streak?
   - [ ] Are you sleeping well?
   - [ ] Trust the system's signals?
   - [ ] Ready to risk real money?

**If any answer is "no" → extend Phase 1, don't switch yet.**

---

### Phase 2: Prepare Live Environment

**1. Update IBKR Connection Settings**

Edit `.env` file:

```bash
cd /Users/pinchy/.openclaw/workspace/trading
nano .env
```

Change:
```
# OLD (Paper Trading)
IB_HOST=127.0.0.1
IB_PORT=7497           # Paper trading port
IB_CLIENT_ID=101

# NEW (Live Trading)
IB_HOST=127.0.0.1
IB_PORT=7496           # Live trading port
IB_CLIENT_ID=102       # Different client ID
```

**2. Start Live TWS/IB Gateway**

- Log into IB Gateway or TWS
- **Select LIVE TRADING mode** (not paper)
- Enable API connections (same as paper setup)
- Note your live account number (U4XXXXXX format)

**3. Update Risk Profile (Stay Conservative)**

Even in live trading, start with conservative profile:

```bash
# Verify you're using conservative risk.json (not leveraged)
cat risk.json | jq '.account.trading_capital'
# Should show: 45000 (NOT 300000)
```

**DO NOT switch to leveraged profile immediately.** Stay conservative for first 30 days of live trading.

---

### Phase 3: First Live Test (Canary Mode)

**Goal:** Verify connection and execution with MINIMAL risk.

**Day 1 of live trading:**

1. **Restart webhook listener with live settings:**
   ```bash
   cd /Users/pinchy/.openclaw/workspace/trading
   # Kill old process
   pkill -f webhook_listener.py
   
   # Start with live settings
   export $(cat .env | grep -v '^#' | xargs)
   python3 scripts/webhook_listener.py &
   ```

2. **Verify connection to live IBKR:**
   ```bash
   # Check logs for successful connection
   tail -f /path/to/logs
   # Should see: "Connected to IB on port 7496"
   ```

3. **First live trade: VERY SMALL SIZE**
   - Wait for a high-quality signal (Z ≥1.5, RS ≥0.70)
   - Approve it
   - **Verify it executes in your LIVE IBKR account**
   - Watch the order fill (may take seconds, not instant)
   - Check: entry, stop, target all placed correctly

4. **If first trade successful:**
   - Continue with normal trading
   - Still use conservative position sizing ($45k)
   - Monitor for any differences vs. paper

5. **If first trade has issues:**
   - Hit kill switch immediately
   - Debug the problem
   - Fix before continuing

---

### Phase 4: Live Trading Adjustments

**Differences you'll notice:**

#### Order Fills

**Paper:**
- Instant fill at mid-price
- Always 100% filled

**Live:**
- May take seconds to fill
- Slippage on market orders
- Use **LIMIT orders** for entries (better control)

**Solution:** Adjust order types in risk.json:
```json
"execution": {
  "default_order_type": "LIMIT"  // Already set in your config
}
```

#### Stop Loss Behavior

**Paper:**
- Stops always trigger at exact price

**Live:**
- Stop may trigger but fill slightly worse (slippage)
- Fast markets = more slippage

**Solution:** Use **STOP LIMIT orders** (already configured) with limit 0.5% below stop.

#### Emotions

**Paper:**
- Easy to follow system
- Losses don't hurt

**Live:**
- Harder to follow system
- Losses feel real (they are!)
- May be tempted to override

**Solution:** 
- Journal every trade (why approved/rejected)
- Stick to the plan rigidly
- Use kill switch if emotional

---

### Phase 5: Live Trading Validation (30 More Days)

**Even after switching to live, stay conservative for 30 days.**

**Live Phase 1 (Days 1-30 live):**
- Same conservative profile ($45k, no leverage)
- Same success criteria as paper Phase 1
- Goal: Prove paper results translate to live

**Success criteria for live Phase 1:**
- ≥10 completed trades
- Win rate ≥50% (same as paper)
- Avg R-ratio ≥1.5 (same as paper)
- Max drawdown ≤10%
- Emotions under control (sleeping well)

**Only after live Phase 1 validated:**
- **THEN** consider Phase 2 (moderate leverage $150k)

---

## Complete Timeline

| Phase | Environment | Size | Leverage | Duration | Goal |
|-------|-------------|------|----------|----------|------|
| **Phase 1 (Paper)** | Paper TWS | $45k | None | 30 days | Prove system works |
| **Live Canary** | Live TWS | $45k | None | 1-3 days | Test connection |
| **Live Phase 1** | Live TWS | $45k | None | 30 days | Prove live results match paper |
| **Live Phase 2** | Live TWS | $150k | 0.75x | 30 days | Moderate leverage validation |
| **Live Phase 3** | Live TWS | $300k | 1.5x | Ongoing | Full leverage deployment |

**Total time to full leverage: ~120 days (4 months)**

**This is the right pace. Don't rush it.**

---

## Checklist: Ready to Switch?

Before switching from paper to live, verify ALL of these:

### Technical Readiness
- [ ] Paper Phase 1 complete (30 days, ≥10 trades)
- [ ] Win rate ≥50% in paper
- [ ] Avg R-ratio ≥1.5 in paper
- [ ] All safety features tested and working
- [ ] Kill switch tested
- [ ] Circuit breakers tested
- [ ] Webhook listener stable (>95% uptime)

### Psychological Readiness
- [ ] Comfortable with paper losses (didn't stress over them)
- [ ] Can follow the system without overriding
- [ ] Sleep well after paper losing days
- [ ] Trust the signals
- [ ] Not emotionally attached to individual trades
- [ ] Can handle 3-loss streaks

### Infrastructure Readiness
- [ ] Backup of all configs
- [ ] Live TWS/Gateway installed
- [ ] .env file updated for live (port 7496)
- [ ] Risk profile confirmed conservative ($45k, no leverage)
- [ ] Weekly review process working

### Financial Readiness
- [ ] $200k account funded and accessible
- [ ] Understand real slippage will occur
- [ ] Accept that first live month may underperform paper
- [ ] Prepared for emotional difference
- [ ] Not using rent money or bill money

**If ANY checkbox is unchecked → not ready, stay in paper.**

---

## What Could Go Wrong?

### Common Issues When Switching to Live

**1. Connection failures**
- **Symptom:** Orders not executing
- **Fix:** Check TWS is in live mode, API enabled, port 7496 open

**2. Order rejections**
- **Symptom:** "Order rejected" messages
- **Possible causes:** 
  - Insufficient buying power
  - Stock not available for shorting
  - Odd lot restrictions
- **Fix:** Check IBKR messages, adjust position size

**3. Slippage shocks**
- **Symptom:** Fills 0.5-1% worse than expected
- **Cause:** Normal in live trading, especially illiquid stocks
- **Fix:** Use limit orders, increase min liquidity threshold

**4. Emotional override**
- **Symptom:** You start rejecting good signals or approving bad ones
- **Cause:** Real money anxiety
- **Fix:** Journal why you're overriding, hit kill switch if needed, talk it through

**5. Performance degradation**
- **Symptom:** Win rate drops from 55% in paper to 45% in live
- **Cause:** Fill quality, emotions, or paper was lucky
- **Fix:** Extend validation period, analyze losing trades

---

## Emergency Procedures

### If Something Goes Wrong

**1. Hit kill switch immediately:**
```bash
cd /Users/pinchy/.openclaw/workspace/trading
./scripts/pause_trading.sh
```

**2. Close any open positions manually in TWS**

**3. Switch back to paper trading:**
```bash
# Edit .env
nano .env
# Change IB_PORT=7496 back to IB_PORT=7497

# Restart TWS in paper mode
# Restart webhook listener
```

**4. Debug the issue before resuming**

**5. Only resume live when confident in fix**

---

## Day 1 Live Trading Checklist

**Morning (before market open):**
- [ ] Live TWS/Gateway running
- [ ] Connected to port 7496
- [ ] Webhook listener restarted with live settings
- [ ] Kill switch tested (pause/resume)
- [ ] Telegram notifications working
- [ ] Phone charged, notifications enabled
- [ ] Calm and ready

**During trading:**
- [ ] Wait for high-quality signal (don't force trades)
- [ ] Approve first trade, watch execution closely
- [ ] Verify order appears in TWS
- [ ] Confirm fill price is reasonable
- [ ] Check stop and target placed correctly
- [ ] Journal how you feel (emotions)

**After market close:**
- [ ] Run performance dashboard
- [ ] Review first live trade
- [ ] Check P&L (it's real now!)
- [ ] Assess emotional state
- [ ] Document any issues
- [ ] Plan for tomorrow

---

## FAQ

**Q: Can I switch back to paper after going live?**  
A: Yes, anytime. Change port back to 7497, restart in paper mode.

**Q: Should I tell the system it's live vs. paper?**  
A: The system doesn't know the difference. It just executes orders. You know it's real money—that's what matters.

**Q: What if my first live trade is a loser?**  
A: Expected. ~50% of trades lose. Don't panic. Follow the system.

**Q: Can I run paper and live simultaneously?**  
A: Not recommended. Pick one to avoid confusion. But technically possible with two separate TWS instances and different client IDs.

**Q: Should I paper trade options income too?**  
A: Yes. Test covered calls and CSPs in paper first. Switch to live when swing trades are proven.

**Q: What if I'm too nervous to switch?**  
A: Stay in paper longer. There's no deadline. Better to be ready than rush.

---

## Summary: The Right Way to Transition

1. ✅ **Complete paper Phase 1** (30 days, ≥10 trades, ≥50% win rate)
2. ✅ **Verify all checklist items** (technical + psychological readiness)
3. ✅ **Update .env for live** (port 7496, client ID 102)
4. ✅ **Start live TWS, restart webhook listener**
5. ✅ **First canary trade** (watch closely, verify execution)
6. ✅ **Live Phase 1** (30 more days at $45k, no leverage)
7. ✅ **Only then: moderate leverage** ($150k, 0.75x)
8. ✅ **Finally: full leverage** ($300k, 1.5x)

**Total time: ~4 months to full leverage.**

**This is how professionals do it. Be patient.**

---

**Current Status:** Paper trading Phase 1 (Day 0)  
**Next Milestone:** Paper Phase 1 validation (March 20, 2026)  
**Earliest live switch:** March 20, 2026 (if validated)  
**Earliest leverage:** May 20, 2026 (if live validated)

**Don't rush. Prove it works. Then scale.**
