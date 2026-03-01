# AMS NX v2.1 Panel Cheatsheet

Quick reference for everything displayed in the indicator panel.

---

## **PANEL LAYOUT (12 Rows)**

### **Row 0: Header**
| Label | Meaning |
|-------|---------|
| **AMS NX Engine v2 (Covel)** | Indicator name (Covel trend-following framework) |
| **Values** | Column header for metric values |

---

### **Row 1: Regime**
| Value | Color | Meaning | Action |
|-------|-------|---------|--------|
| **BULL** | 🟢 Green | Strong uptrend (price > EMA200 + breadth > 60) | Open to LONG entries |
| **NEUTRAL** | 🟠 Orange | Weak trend (price > EMA200 but breadth 40-60) | Smaller LONG positions, higher risk |
| **BEAR** | 🔴 Red | Downtrend (price < EMA200 or breadth < 40) | Focus on SHORTS or flat |

**Key:** Regime is the foundation of all position sizing. Size Scale multiplies based on this.

---

### **Row 2: Z-Score**
| Range | Meaning | Signal |
|-------|---------|--------|
| **≥ +0.75** | Strong upward momentum | LONG bias, entry zone |
| **+0.50 to +0.75** | Moderate upward momentum | Mild LONG bias |
| **0 to +0.50** | Weak upward momentum | Neutral to slightly bullish |
| **-0.50 to 0** | Weak downward momentum | Neutral to slightly bearish |
| **-0.50 to -1.0** | Moderate downward momentum | Mild SHORT bias |
| **≤ -1.0** | Strong downward momentum | SHORT bias, entry zone |

**How to read:**
- Green = positive momentum
- Red = negative momentum
- Magnitude = confidence level

**Use:** Confirms trend direction. Higher magnitude = stronger signal.

---

### **Row 3: RS Pct (Relative Strength %)**
| Value | Meaning | Signal |
|-------|---------|--------|
| **≥ 65%** | Stock outperforming SPY significantly | Strong LONG signal, momentum with you |
| **50-65%** | Stock outperforming SPY moderately | Good LONG environment |
| **40-50%** | Stock roughly in line with SPY | Neutral, be careful with entries |
| **≤ 40%** | Stock underperforming SPY | Weak for LONG, watch for reversal |
| **≤ 35%** | Stock significantly weak vs market | SHORT signal, market working against you |

**What it measures:** How the stock performs vs the S&P 500 over the past 126 days.

**Use:** Make sure you're trading with the market, not against it. Strong RS increases odds.

---

### **Row 4: Position**
| Value | Color | Meaning |
|-------|-------|---------|
| **LONG** | 🟢 Green | You are long (own shares) |
| **SHORT** | 🔴 Red | You are short (borrowed shares, betting down) |
| **FLAT** | ⚫ Gray | No position (cash or neutral) |

**Use:** Quick status check. Are you in a position? Which direction?

---

### **Row 5: Size Scale**
| Value | Color | Meaning | Position Sizing |
|-------|-------|---------|-----------------|
| **0.90-1.00** | 🟢 Green | Peak bull regime | 100% of max position size |
| **0.75-0.90** | 🟢 Light Green | Strong bull regime | 75-90% position size |
| **0.50-0.75** | 🟠 Orange | Neutral/uncertain | 50-75% position size |
| **0.25-0.50** | 🟡 Yellow | Weak regime | 25-50% position size |
| **0.00-0.25** | 🔴 Red | Bear regime or no setup | Micro positions only or flat |

**What it measures:** Continuous blend of:
- Z-Score strength (25%)
- EMA200 proximity (25%)
- Market breadth (25%)
- Momentum strength (25%)

**Use:** THIS IS YOUR POSITION SIZING GUIDE. Higher Size Scale = bigger positions allowed.

**Example:**
- Size Scale = 0.82 → Can take 82% of your normal max position
- Size Scale = 0.35 → Only 35% of normal max position, or skip entry

---

### **Row 6: Final Size (w/ DD)**
| Value | Meaning |
|-------|---------|
| **[Size Scale] × [DD Adjustment]** | Your ACTUAL max position size after portfolio drawdown penalty |

**How it works:**
- If portfolio drawdown is 0%: Final Size = Size Scale (no penalty)
- If portfolio drawdown is 5%: Final Size = Size Scale × 0.75 (reduce by 25%)
- If portfolio drawdown is 10%: Final Size = Size Scale × 0.50 (reduce by 50%)
- If portfolio drawdown is 15%+: Final Size = Size Scale × 0.25 (reduce by 75%)

**Use:** When deciding how many shares to buy. This is the FINAL number after all adjustments.

**Example:**
- Size Scale = 0.80, Portfolio DD = 0%, Final Size = 80%
- Size Scale = 0.80, Portfolio DD = 10%, Final Size = 40% (0.80 × 0.50)

---

### **Row 7: Dist→Stop**
| Value | Meaning | Risk Assessment |
|-------|---------|-----------------|
| **< 1%** | Stop loss is very close to current price | ⚠️ High risk of getting stopped out |
| **1-2%** | Stop loss is within normal distance | ✅ Good risk/reward zone |
| **2-3%** | Stop loss is giving you breathing room | ✅ Comfortable trade setup |
| **> 3%** | Stop loss is far away | ⚠️ Risk/reward may be poor (too much risk) |

**What it measures:** Percentage distance from current price to your stop loss.

**Use:** Make sure your stop makes sense. 
- Too close (< 1%) = likely to get shaken out
- Too far (> 3%) = risking too much per trade

---

### **Row 8: Risk/Share**
| Value | Meaning |
|-------|---------|
| **$X.XX per share** | How much you lose per share if stop is hit |

**Example:**
- Entry: $50, Stop: $49, Risk/Share = $1.00
- If you buy 100 shares and hit stop, you lose $100

**Use:** Confirms your stop loss is reasonable. Shouldn't exceed 2-3% of entry price normally.

---

### **Row 9: Dollar Risk**
| Value | Meaning |
|-------|---------|
| **$X,XXX** | Total $ amount you're willing to risk on this trade |

**How it's calculated:**
- Account Equity × Max Risk % (default 2%)
- Example: $100,000 account × 2% = $2,000 max risk per trade

**Use:** This is your max loss per trade. Don't exceed it. If a setup requires more risk than this, skip it.

---

### **Row 10: Recommended Qty**
| Value | Meaning |
|-------|---------|
| **XXX shares** | How many shares to buy based on your risk parameters |

**How it's calculated:**
```
Recommended Shares = Dollar Risk / Risk per Share
Example: $2,000 / $1.00 = 2,000 shares
```

**Use:** BUY THIS MANY SHARES. This respects your 2% risk rule and stop loss distance.

---

### **Row 11: Action**
| Value | Color | Meaning | What to Do |
|-------|-------|---------|-----------|
| **READY** | 🟢 Green | All filters pass, position sizing calculated | BUY the Recommended Qty at market |
| **BUY NOW** | 🟢 Green | Long entry signal triggered | Execute LONG order immediately |
| **SHORT NOW** | 🔴 Red | Short entry signal triggered | Execute SHORT order immediately |
| **EXIT** | 🟠 Orange | Exit signal triggered (stop hit or signal broke) | Close position immediately |
| **HOLD** | 🔵 Blue | You're in a position, no exit signal yet | Stay in trade, watch stop loss |
| **WAIT** | ⚫ Gray | No setup, no position | Do nothing, wait for next signal |

**Use:** Follow this. It's your action guide.

---

## **TRADING WORKFLOW**

### **Step 1: Check Regime (Row 1)**
```
Is it BULL? ✅ OK to take LONG entries
Is it BEAR? ✅ OK to take SHORT entries, avoid LONG
Is it NEUTRAL? ⚠️ Be cautious, smaller positions
```

### **Step 2: Check Size Scale (Row 5)**
```
Size Scale = 0.82? → Can take ~80% of max position
Size Scale = 0.35? → Only take ~35% of max position, or skip
Size Scale = 0.05? → Don't trade, regime is weak
```

### **Step 3: Check Z-Score (Row 2) + RS Pct (Row 3)**
```
Z-Score ≥ +0.75 AND RS Pct ≥ 65%? → Strong LONG signal
Z-Score ≤ -1.0 AND RS Pct ≤ 35%? → Strong SHORT signal
Mixed signals? → Wait for clarity
```

### **Step 4: Check Action (Row 11)**
```
Action = "READY" or "BUY NOW"? → Execute
Action = "SHORT NOW"? → Execute short
Action = "WAIT"? → Do nothing
Action = "HOLD"? → You're in a trade, respect your stop
Action = "EXIT"? → Close position now
```

### **Step 5: If Ready to Trade, Check Recommended Qty (Row 10)**
```
BUY or SHORT exactly the Recommended Qty
Don't modify position size—it's already calculated for your risk
```

### **Step 6: Monitor Stop Loss (Row 7)**
```
Is Dist→Stop reasonable (1-3%)? ✅ Good
Is Dist→Stop too close (< 1%)? ⚠️ Likely to be shaken out
Is Dist→Stop too far (> 3%)? ⚠️ Risk is too high for this stock
```

---

## **QUICK DECISION MATRIX**

### **Should I Enter a LONG?**

| Regime | Z-Score | RS Pct | Size Scale | Action |
|--------|---------|--------|-----------|--------|
| BULL | ≥ +0.75 | ≥ 65% | ≥ 0.50 | ✅ YES, full position |
| BULL | +0.50 | ≥ 55% | ≥ 0.50 | ✅ YES, 75% position |
| NEUTRAL | ≥ +0.75 | ≥ 65% | 0.40-0.50 | ⚠️ MAYBE, 50% position |
| NEUTRAL | +0.50 | ≥ 50% | < 0.40 | ❌ NO, regime too weak |
| BEAR | Any | Any | < 0.30 | ❌ NO, market against you |

---

### **Should I Enter a SHORT?**

| Regime | Z-Score | RS Pct | Size Scale | Action |
|--------|---------|--------|-----------|--------|
| BEAR | ≤ -1.0 | ≤ 35% | ≥ 0.50 | ✅ YES, full position |
| BEAR | -0.75 | ≤ 40% | ≥ 0.50 | ✅ YES, 75% position |
| NEUTRAL | ≤ -1.0 | ≤ 35% | 0.40-0.50 | ⚠️ MAYBE, 50% position |
| NEUTRAL | -0.75 | ≤ 40% | < 0.40 | ❌ NO, regime too weak |
| BULL | Any | Any | < 0.30 | ❌ NO, market against you |

---

## **COLOR LEGEND**

| Color | Meaning |
|-------|---------|
| 🟢 Green | BULLISH / LONG-friendly / Good signal |
| 🟠 Orange | NEUTRAL / CAUTIOUS / Mixed signal |
| 🟡 Yellow | WEAK / RISKY / Low confidence |
| 🔴 Red | BEARISH / SHORT-friendly / Avoid LONG |
| ⚫ Gray | FLAT / NEUTRAL / No position |
| 🔵 Blue | HOLDING / In a trade |

---

## **COMMON MISTAKES TO AVOID**

❌ **Ignoring Regime**: Trading LONG when Regime is BEAR  
❌ **Ignoring Size Scale**: Taking full position when Size Scale is 0.30  
❌ **Ignoring RS Pct**: Shorting a stock with RS > 65% (market momentum with upside)  
❌ **Wrong Z-Score**: Taking LONG on Z-Score = -0.5 (already weak)  
❌ **Ignoring Stop Distance**: Putting stop > 3% away (too much risk)  
❌ **Not following Recommended Qty**: Sizing too big or too small (breaks 2% risk rule)  
❌ **Trading WAIT state**: If Action = "WAIT", don't trade—regime isn't ready  

---

## **QUICK REFERENCE: VALUES AT A GLANCE**

```
Regime: BULL/NEUTRAL/BEAR
Z-Score: -5 to +5 (higher = stronger momentum)
RS Pct: 0-100% (higher = outperforming market)
Size Scale: 0.00-1.00 (higher = stronger regime)
Final Size: 0-100% (your actual max position, after DD adjustment)
Dist→Stop: % (should be 1-3%, not < 1% or > 3%)
Risk/Share: $ (confirms your stop loss makes sense)
Dollar Risk: $ (your max loss per trade, usually 2% of account)
Recommended Qty: shares (BUY THIS MANY)
Action: READY/BUY NOW/SHORT NOW/EXIT/HOLD/WAIT (FOLLOW THIS)
```

---

## **EXAMPLES**

### **Example 1: Strong LONG Setup**
```
Regime: BULL (🟢)
Z-Score: +1.2
RS Pct: 72%
Size Scale: 0.88 (🟢)
Final Size: 88%
Dist→Stop: 2.1%
Recommended Qty: 880 shares
Action: BUY NOW

DECISION: ✅ LONG 880 shares, this is a great setup
```

### **Example 2: Weak Setup (Ignore)**
```
Regime: NEUTRAL (🟠)
Z-Score: +0.3
RS Pct: 48%
Size Scale: 0.35 (🟡)
Final Size: 35%
Dist→Stop: 4.2%
Recommended Qty: 350 shares
Action: WAIT

DECISION: ❌ SKIP, regime is weak and risk/reward is poor (4.2% stop)
```

### **Example 3: Strong SHORT Setup**
```
Regime: BEAR (🔴)
Z-Score: -1.5
RS Pct: 28%
Size Scale: 0.72
Final Size: 72%
Dist→Stop: 2.3%
Recommended Qty: 720 shares
Action: SHORT NOW

DECISION: ✅ SHORT 720 shares, this is a strong SHORT signal
```

---

**Last Updated:** March 1, 2026 v2.1  
**Framework:** Covel Trend Following + Risk Management  
**Risk Rule:** 2% max loss per trade  
**Position Sizing:** Dynamic based on regime strength
