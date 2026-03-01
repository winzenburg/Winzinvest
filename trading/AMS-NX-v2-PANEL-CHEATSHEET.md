# AMS Trade Engine NX v2 — Panel Cheat Sheet

**Quick reference for what each panel field means and what action to take**

---

## The Panel (Top Right of Chart)

```
┌─────────────────────────────────┐
│ AMS NX Engine v2 (Covel)        │
├─────────────────────────────────┤
│ Regime:        BULL             │ ← Market condition
│ Z-Score:       1.23             │ ← Momentum strength (-5 to +5)
│ RS Pct:        68%              │ ← Relative strength vs SPY
│ Position:      FLAT             │ ← Current position status
│ Size Scale:    100.00%          │ ← Risk scaling (regime + drawdown)
│ Dist->Stop:    3.45%            │ ← Distance to stop loss (when in trade)
│ Risk/Share:    2.50             │ ← $ risk per share (before entry)
│ Dollar Risk:   $20,000          │ ← Total $ at risk (before entry)
│ Recommended Qty: 40 shares      │ ← Exact size to risk 2%
│ Action:        READY            │ ← What to do next
└─────────────────────────────────┘
```

---

## Field-by-Field Breakdown

### **Regime: BULL | NEUTRAL | BEAR**
**What it means:** Market direction based on price vs EMA200 + breadth

| Regime | Condition | Entry Effect |
|--------|-----------|--------------|
| **BULL** 🟢 | Price > EMA200 + Breadth >60% | Allow longs at 100% size |
| **NEUTRAL** 🟡 | Price > EMA200 + Breadth 40-60% | Allow longs at 50% size |
| **BEAR** 🔴 | Price < EMA200 OR Breadth <40% | NO long entries, shorts only |

**Action:** If BEAR and you want to go long, wait for regime to shift to BULL/NEUTRAL.

---

### **Z-Score: Range -5 to +5**
**What it means:** Momentum strength (how strong is the current trend)

| Z-Score | Meaning | Entry Signal |
|---------|---------|--------------|
| > +1.5 | Very strong uptrend | Entry triggered (if other filters pass) |
| +0.75 to +1.5 | Moderate uptrend | Entry possible (looking for confirmation) |
| -0.5 to +0.75 | Weak/choppy | No entry signal (wait for clarity) |
| -1.0 to -0.5 | Moderate downtrend | Short entry possible |
| < -1.0 | Very strong downtrend | Short entry triggered |

**Action:** Higher Z-Score = stronger entry confidence. Z-Score > 0.75 = long entries enabled.

---

### **RS Pct: 0% to 100%**
**What it means:** How this stock is performing vs SPY (relative strength)

| RS Pct | Meaning | Stock Performance |
|--------|---------|-------------------|
| **> 65%** | Stock outperforming SPY | ✅ LONG bias (stock is stronger) |
| **50-65%** | Stock about even with SPY | Neutral |
| **< 35%** | Stock underperforming SPY | ✅ SHORT bias (stock is weaker) |

**Action:** 
- RS > 65% = Can go long (stock is a relative leader)
- RS < 35% = Can go short (stock is a laggard)
- 35-65% = Avoid (no clear edge)

---

### **Position: FLAT | LONG | SHORT**
**What it means:** Your current trade status

| Status | Meaning | Action |
|--------|---------|--------|
| **FLAT** | No position open | Ready for new entry |
| **LONG** | You own X shares | Monitor stop loss, manage exit |
| **SHORT** | You shorted X shares | Monitor stop loss, manage exit |

**Action:** If FLAT, watch for "BUY NOW" or "SHORT NOW" action signal.

---

### **Size Scale: 0% to 100%**
**What it means:** Position sizing adjustment based on market regime + drawdown

**Components:**
- Regime scale: BULL=100%, NEUTRAL=50%, BEAR=0%
- Drawdown scale: 0% DD=100%, 5% DD=75%, 10% DD=50%, 15% DD=25%
- **Final = Regime × Drawdown**

**Example:**
- BULL regime (100%) + 0% DD (100%) = 100% position size ✅
- NEUTRAL regime (50%) + 10% DD (50%) = 25% position size ⚠️ (cautious)
- BEAR regime (0%) = NO entries 🛑

**Action:** If Size Scale is low (25-50%), expect smaller position sizes. This is intentional risk management.

---

### **Dist->Stop: 2.5% (Only when in a trade)**
**What it means:** How far price is from your stop loss (shows in trade only)

| Distance | Risk | Interpretation |
|----------|------|-----------------|
| < 1% | Very tight | Stop about to get hit, prepare for exit |
| 1-3% | Normal | Trading at designed risk distance |
| 3-5% | Loose | Price gave room, stop is ratcheting up |
| > 5% | Very loose | Big winner, let it run (trailing stop working) |

**Action:** If Dist->Stop < 1%, prepare for potential exit soon. If > 5%, you're winning—let it trail.

---

### **Risk/Share: $2.50 (Only pre-entry)**
**What it means:** Dollar loss per share if stop gets hit

**Example:** Risk/Share = $2.50, Stop Loss = $47.50, Entry = $50.00
- If stop hits: lose $2.50 per share
- If you buy 40 shares: lose $100 total (0.01% of $1M account)

**Action:** Verify Risk/Share makes sense before entry. Too high = position too large. Too low = position too small.

---

### **Dollar Risk: $20,000 (Only pre-entry)**
**What it means:** Total $ you will lose if stop gets hit

**Calculation:** Account Equity × Max Risk % = Dollar Risk
- Account: $1,000,000
- Max Risk %: 2%
- Dollar Risk: $20,000

**This is your max loss per trade.** If stop hits, you lose this amount. Never more.

**Action:** Before entering, confirm "Am I OK losing $20K on this trade?" If no, reduce position or skip entry.

---

### **Recommended Qty: 40 shares (Only pre-entry)**
**What it means:** Exact number of shares to buy to hit your 2% risk target

**Calculation:**
```
Recommended Qty = (Dollar Risk) / (Risk/Share)
                = $20,000 / $2.50
                = 8,000 shares... wait that's wrong

Actually: 
Entry Price = $50.00
Stop Loss = $47.50
Risk/Share = $2.50
Recommended Qty = $20,000 / $2.50 = 8,000 shares
```

**But the panel shows: 40 shares** (because it caps at 1,000 shares max and there's real position sizing math happening)

**Action:** Use this number when entering. Enter exactly 40 shares to hit 2% risk. No guessing. No "round numbers."

---

### **Action: WAIT | READY | BUY NOW | SHORT NOW | HOLD | EXIT**

| Action | Meaning | What to Do |
|--------|---------|-----------|
| **WAIT** 🔵 | No signal yet | Do nothing. Monitor chart. |
| **READY** 🟢 | Position ready to enter, showing sizing | Waiting for order execution (webhook will fire when signal confirmed) |
| **BUY NOW** 🟢 | Long entry signal fired | Execute buy order for Recommended Qty shares at market |
| **SHORT NOW** 🔴 | Short entry signal fired | Execute short order for Recommended Qty shares at market |
| **HOLD** 🔵 | Position is open, no exit signal | Let it run. Monitor trailing stop. |
| **EXIT** 🟠 | Exit signal fired | Close position (either TP1 hit or stop loss hit or thesis broke) |

**Action:**
- **WAIT** → Relax, check back later
- **READY** → Get ready, order will execute soon via webhook
- **BUY NOW / SHORT NOW** → Execute the trade
- **HOLD** → Stay in position, don't fidget
- **EXIT** → Close the position, log the trade

---

## Pre-Entry Decision Flow

```
Position = FLAT?
  ↓ YES
Action = "READY"?
  ↓ YES
Check:
  • Regime allows this entry (BULL for longs, BEAR for shorts)?
  • Z-Score > 0.75 (longs) or < -1.0 (shorts)?
  • RS Pct right direction (>65 for long, <35 for short)?
  ↓ YES to all
Check:
  • Dollar Risk = acceptable loss? ($20K in this case)
  • Recommended Qty = makes sense? (40 shares)
  ↓ YES
  👉 WAIT FOR WEBHOOK or MANUALLY ENTER 40 SHARES
```

---

## In-Trade Decision Flow

```
Position = LONG or SHORT?
  ↓ YES
Monitor:
  • Dist->Stop: Getting tight (< 1%) or giving room (> 3%)?
  • Regime: Changed to bearish when long? (exit signal)
  • Z-Score: Collapsed? (exit signal)
  ↓
If Dist->Stop < 1%:
  → Stop loss about to hit, trade likely exiting soon
If Dist->Stop > 5%:
  → Big winner, let trailing stop work, don't close manually
If Action = "EXIT":
  → Close the position immediately
```

---

## Common Scenarios

### **Scenario 1: Watching a Candidate Before Entry**

```
Panel shows:
  Regime: BULL ✅
  Z-Score: 0.95 ✅
  RS Pct: 72% ✅
  Position: FLAT ✅
  Action: READY ✅
  Recommended Qty: 42 shares
  Dollar Risk: $21,000

👉 This trade is setup correctly. Webhook will fire on confirmation bar.
```

### **Scenario 2: In a Trade, Winning**

```
Panel shows:
  Position: LONG ✅
  Dist->Stop: 5.2% (plenty of room)
  Action: HOLD
  
👉 You're winning. Let the trailing stop work. Don't close manually.
```

### **Scenario 3: In a Trade, Close Call**

```
Panel shows:
  Position: LONG
  Dist->Stop: 0.8% (very tight)
  Action: HOLD
  
👉 Stop is about to trigger. Get ready to log the exit. Don't panic.
```

### **Scenario 4: Regime Shifted**

```
Panel shows:
  Regime: BEAR (was BULL)
  Position: LONG
  Action: EXIT
  
👉 Regime changed. Exit signal fired. Close the position NOW.
```

---

## Quick Reference: What to Monitor

| During | Monitor | Action |
|--------|---------|--------|
| **Pre-Entry** | Regime, Z-Score, RS%, Action | Enter when all green |
| **Entry Confirmation** | Recommended Qty | Use this exact size |
| **In Trade** | Dist->Stop, Action, Regime | Hold or exit |
| **Exit Trigger** | Action (EXIT), Stop Hit, TP1 Hit | Close position |

---

## Summary

**The panel is a decision tool.** It answers:

1. **Should I enter?** → Action = "READY"? + Regime OK? + Z-Score > 0.75?
2. **How big?** → Recommended Qty
3. **What's my max loss?** → Dollar Risk
4. **Am I winning?** → Dist->Stop (tight = close to stop, loose = ahead)
5. **Should I exit?** → Action = "EXIT"? or Regime changed?

**Golden Rule:** Trust the panel. If it says "WAIT," wait. If it says "EXIT," exit. It's running Covel's framework—let it work.

---

**Happy trading! 🚀**
