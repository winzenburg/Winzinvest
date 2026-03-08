# Leverage Strategy for Swing Trading

**Your Setup:**
- Actual Capital: $200,000
- Reg T Margin: $400,000 (2x)
- Recommended Use: $300,000 (1.5x leverage)

---

## The Opportunity

With your $200k account, you have access to $400k in overnight buying power (Reg T margin). This means you can hold **$400k worth of stocks overnight** for swing trading.

**But should you max it out? No.**

---

## Conservative Leverage Strategy

### Target: 1.5x Leverage ($300k positions)

**Why 1.5x instead of 2x?**
- **Margin cushion:** Leaves $100k breathing room
- **Volatility buffer:** A 10% drawdown won't trigger margin call
- **Sleep insurance:** Not stressed about overnight gaps

### The Math

| Scenario | Conservative ($45k) | Leveraged 1.5x ($300k) | Max 2x ($400k) |
|----------|---------------------|------------------------|----------------|
| **Capital** | $45,000 | $200,000 cash | $200,000 cash |
| **Positions** | $45,000 | $300,000 | $400,000 |
| **Leverage** | None | +$100k margin | +$200k margin |
| **Risk/trade** | $450 (1%) | $1,500 (0.75%) | $2,000 (1%) |
| **Max daily loss** | $1,350 (3%) | $4,000 (2%) | $6,000 (3%) |
| **Positions** | 5 concurrent | 8 concurrent | 10 concurrent |

---

## Key Differences in Leveraged Profile

### Stricter Limits

| Metric | Conservative | Leveraged | Why Stricter? |
|--------|--------------|-----------|---------------|
| **Daily loss** | 3% ($1,350) | 2% ($4,000) | Faster drawdowns with leverage |
| **Correlation** | 0.70 | 0.65 | More diversification needed |
| **Sector exposure** | 40% | 30% | Avoid concentration risk |
| **Min volume** | 1M shares | 2M shares | Need more liquidity |

### Safety Features

1. **Auto-delever trigger:** If portfolio leverage exceeds 1.8x, system warns you
2. **Margin buffer:** Always maintain 25% ($100k) cushion
3. **Circuit breaker:** Still active, but with tighter thresholds
4. **Position limits:** 8 concurrent positions (vs. 5) for diversification

---

## Expected Returns with Leverage

### Conservative Projection (30% annual unleveraged)

**Without leverage ($45k):**
- 30% return = $13,500/year
- Monthly: ~$1,125

**With 1.5x leverage ($300k):**
- 30% return on $300k = $90,000/year
- Monthly: ~$7,500
- **But that's 45% ROI on your $200k actual capital**

### The Catch: Losses Scale Too

**Bad month (-5% unleveraged):**
- Without leverage: -$2,250
- With 1.5x leverage: -$15,000 (7.5% of actual capital)

**This is why we have:**
- Daily loss limits ($4k vs. $1,350)
- Tighter correlation controls
- Auto-delever triggers

---

## Ramp-Up Plan (Recommended)

### Phase 1: Validation (30 days)

**Use conservative profile (`risk.json`):**
- $45k position sizing
- No leverage
- Prove the system works
- Goal: 10+ trades, >50% win rate

### Phase 2: Modest Leverage (Days 31-60)

**Switch to intermediate profile:**
- $150k position sizing (0.75x leverage)
- Risk: 0.5% per trade ($1,000)
- Goal: Maintain performance with more capital

### Phase 3: Full Leverage (Days 61+)

**Switch to leveraged profile (`risk_leveraged.json`):**
- $300k position sizing (1.5x leverage)
- Risk: 0.75% per trade ($1,500)
- Full suite of leverage controls active

---

## How to Switch Profiles

**Currently active:**
```bash
/Users/pinchy/.openclaw/workspace/trading/risk.json  # Conservative $45k
```

**To use leveraged profile:**
```bash
cd /Users/pinchy/.openclaw/workspace/trading
cp risk.json risk_conservative_backup.json  # Backup
cp risk_leveraged.json risk.json  # Activate leverage
# Restart webhook listener to load new config
```

**To revert:**
```bash
cp risk_conservative_backup.json risk.json
```

---

## Margin Call Prevention

### What Triggers a Margin Call?

**IBKR Maintenance Margin:**
- Stocks: 25% of position value
- If your equity falls below this, you get a margin call

**Example:**
- You have $300k in positions
- Maintenance requirement: $75k (25%)
- Your equity (account value): $200k
- **Buffer: $125k** ✅ Safe

**Danger zone:**
- Positions drop 20% → Now worth $240k
- Your equity: $160k ($200k - $40k loss)
- Maintenance req: $60k (25% of $240k)
- **Buffer: $100k** ✅ Still safe

**Margin call:**
- Positions drop 40% → Now worth $180k
- Your equity: $80k ($200k - $120k loss)
- Maintenance req: $45k (25% of $180k)
- **Buffer: $35k** ⚠️ Getting close

### System Protection

**Auto-delever trigger at 1.8x:**
- If your leverage exceeds 1.8x (from losses compounding), system alerts you
- Suggests closing lowest-conviction positions
- Goal: Get back to 1.3-1.5x range

---

## Risk Scenarios

### Scenario 1: Normal Volatility

**Portfolio: $300k (1.5x leverage), 8 positions @ $37.5k each**

**One position stopped out (-5%):**
- Loss: $1,875
- Well within daily limit ($4,000)
- System continues normally

### Scenario 2: Overnight Gap Down

**Market gaps down 3% overnight, all 8 positions affected:**

**Loss:**
- $300k × 3% = $9,000
- **That's 4.5% of your actual capital**
- Exceeds daily loss limit ($4,000)
- **Circuit breaker triggers** → No new trades today

**Recovery:**
- Review positions
- Consider closing weakest ones
- Resume tomorrow with fewer positions

### Scenario 3: Flash Crash

**Market drops 10% in an hour:**

**Immediate action:**
1. **Hit kill switch:** `./scripts/pause_trading.sh`
2. **Check margin:** Ensure not near maintenance req
3. **Evaluate positions:** Close any at risk of margin call
4. **Resume when stable:** `./scripts/resume_trading.sh`

---

## Leverage Best Practices

### DO:
✅ Start with Phase 1 (no leverage) for 30 days  
✅ Ramp up gradually (0.75x → 1.0x → 1.5x)  
✅ Maintain 25%+ margin cushion  
✅ Diversify across 6-8 positions  
✅ Use limit orders (better fills)  
✅ Monitor daily leverage ratio  
✅ Hit kill switch during volatility spikes  

### DON'T:
❌ Jump straight to 2x leverage  
❌ Concentrate in one sector  
❌ Ignore margin warnings  
❌ Trade through FOMC/earnings  
❌ Average down on losing positions  
❌ Override daily loss limits  

---

## Monthly Monitoring

**Every month, check:**
1. **Actual leverage used:** Track average (should be 1.3-1.5x)
2. **Margin calls:** Should be ZERO
3. **Win rate:** Should maintain >50%
4. **Max drawdown:** Should stay <10% of actual capital
5. **Sharpe ratio:** Should improve with more capital

**If any degrade → reduce leverage temporarily**

---

## The Bottom Line

**Conservative:** $45k → 30% annual → $13.5k profit  
**Leveraged 1.5x:** $300k → 30% annual → $90k profit (45% ROI on actual capital)

**The multiplier works both ways:**
- Good months are 6x better
- Bad months are 6x worse

**Your new safety features make this viable:**
- Daily loss circuit breaker
- Earnings blackout
- Correlation monitoring
- Kill switch
- Auto-delever triggers

**Start small, prove it works, then scale.**

---

## Activation Checklist

Before switching to leveraged profile:

- [ ] Run conservative profile for 30 days minimum
- [ ] Achieve >50% win rate on 10+ trades
- [ ] Zero margin calls (shouldn't have any with conservative)
- [ ] Comfortable with swing trading workflow
- [ ] Read this entire document
- [ ] Back up `risk.json` before switching
- [ ] Set calendar reminder to review monthly

**Once ready:**
```bash
cp risk_leveraged.json risk.json
```

**Not ready?** Keep using conservative profile. There's no rush. Prove the system first.
