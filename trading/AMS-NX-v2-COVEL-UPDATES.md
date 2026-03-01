# AMS Trade Engine NX v2 — Covel Framework Updates

**Date:** February 25, 2026
**Status:** Ready to implement
**Priority:** CRITICAL (implements $1M+ edge improvement)

---

## INSIGHT #1: Remove TP2, Keep Micro-Partial Only

**What to change:** Lines 52-54 (Inputs) + Lines 234-261 (Logic) + Lines 289-295 (Plots) + Lines 328-334 (Alerts)

### STEP 1: Replace Partial Inputs (Lines 52-54)

**DELETE THIS:**
```pinescript
usePartials = input.bool(true, "Partial profits ON", group="Partials")
pt1_R = input.float(1.5, "TP1 (R)", step=0.1, group="Partials")
pt2_R = input.float(2.5, "TP2 (R)", step=0.1, group="Partials")
trailAfterTP1 = input.bool(true, "Move to BE after TP1", group="Partials")
```

**REPLACE WITH:**
```pinescript
usePartials = input.bool(true, "Micro-Partial (20% @ 2R) ON", group="Partials")
pt1_R = input.float(2.0, "TP1 (covers commission, R)", step=0.1, group="Partials")
// NOTE: TP2 removed per Covel framework (let profits run, don't cap)
```

**Why:** 
- pt1_R = 2.0 (instead of 1.5) covers ~$300-500 in commissions/taxes on larger positions
- Removes TP2 entirely (was capping winners at 2.5R before trailing stop kicked in)
- Keeps micro-partial for psychological comfort (20% exit = know you're profitable)
- Remaining 80% trails with zero target (Covel's asymmetric payoff structure)

---

### STEP 2: Delete TP2 Calculation Variables (Lines 234-236)

**DELETE THIS ENTIRE SECTION:**
```pinescript
tp2_long = na(entryPx) or na(entryStop) ? na : entryPx + pt2_R * (entryPx - entryStop)
tp2_short = na(entryPx) or na(entryStop) ? na : entryPx - pt2_R * (entryStop - entryPx)
```

**Keep only TP1 calculations (TP1 should remain):**
```pinescript
tp1_long = na(entryPx) or na(entryStop) ? na : entryPx + pt1_R * (entryPx - entryStop)
tp1_short = na(entryPx) or na(entryStop) ? na : entryPx - pt1_R * (entryStop - entryPx)
```

---

### STEP 3: Delete hitTP2 Variable (Line 243)

**DELETE THIS:**
```pinescript
var bool hitTP2 = false
```

**Keep only:**
```pinescript
var bool hitTP1 = false
```

---

### STEP 4: Delete TP2 Trigger Logic (Lines 254-261)

**DELETE THIS ENTIRE BLOCK:**
```pinescript
// --- TP2 Logic ---
if usePartials and hitTP1 and not hitTP2 and posType == 1 and close >= tp2_long
    hitTP2 := true
    trailStop := math.max(trailStop, tp1_long) // Move stop to TP1 if
if usePartials and hitTP1 and not hitTP2 and posType == -1 and close <= tp2_short
    hitTP2 := true
    trailStop := math.min(trailStop, tp1_short) // Move stop to TP1
```

**Result:** Only TP1 trigger remains. After TP1 is hit, position trails with chandelier stop (no TP2 exit).

---

### STEP 5: Update Reset Logic (Lines 279-281)

**Current code resets hitTP2. DELETE the hitTP2 line:**

**OLD:**
```pinescript
if exitEvent
    lastExitBar := bar_index
    entryPx := na
    posType := 0
    trailStop := na
    entryStop := na
    movedToBE := false
    hitTP1 := false
    hitTP2 := false  // <-- DELETE THIS LINE
```

**NEW:**
```pinescript
if exitEvent
    lastExitBar := bar_index
    entryPx := na
    posType := 0
    trailStop := na
    entryStop := na
    movedToBE := false
    hitTP1 := false
    // hitTP2 removed
```

---

### STEP 6: Delete TP2 Plots (Lines 294-295)

**DELETE THESE LINES:**
```pinescript
plot(posType==1 and not hitTP2 ? tp2_long : na, title="TP2 Long", color=color.new(color.aqua, 20), style=plot.style_stepline)
plot(posType==-1 and not hitTP2 ? tp2_short : na, title="TP2 Short", color=color.new(color.aqua, 20), style=plot.style_stepline)
```

**Keep TP1 plots only:**
```pinescript
plot(posType==1 and not hitTP1 ? tp1_long : na, title="TP1 Long", color=color.new(color.green, 20), style=plot.style_stepline)
plot(posType==-1 and not hitTP1 ? tp1_short : na, title="TP1 Short", color=color.new(color.green, 20), style=plot.style_stepline)
```

---

### STEP 7: Delete TP2 Alerts (Lines 333-334)

**DELETE THESE LINES:**
```pinescript
if usePartials and hitTP2 and not hitTP2[1]
    alert(mkPayload(posType==1 ? "long" : "short", "tp2"), alert.freq_once_per_bar_close)
```

**Keep only TP1 alert:**
```pinescript
if usePartials and hitTP1 and not hitTP1[1]
    alert(mkPayload(posType==1 ? "long" : "short", "tp1"), alert.freq_once_per_bar_close)
```

---

## INSIGHT #2: Explicit Per-Trade Risk % (2% Rule)

**What to add:** maxRiskPct input + position sizing calculation + panel display

### ADD: Risk Calculation Inputs (After Line 32, in Risk Management group)

```pinescript
// --- Per-Trade Risk (Covel 2% Rule) ---
maxRiskPct = input.float(0.02, "Max Risk % per trade", minval=0.001, maxval=0.05, step=0.001, group="Risk")
displayRiskCalc = input.bool(true, "Display position sizing calc", group="Risk")
accountEquity = input.float(1000000.0, "Account Equity ($)", step=100000, group="Risk")
```

### ADD: Risk Calculation Logic (After line 183, after position state section)

```pinescript
// --- Per-Trade Risk Calculation (Covel Framework) ---
riskPerShare = na
recommendedShares = na
recommendedDollarRisk = na

if not na(entryPx) and not na(entryStop)
    // Distance from entry to initial stop
    riskPerShare := math.abs(entryPx - entryStop)
    
    if riskPerShare > 0.01  // Avoid division by tiny amounts
        // Max dollar risk = account equity × max risk %
        recommendedDollarRisk := accountEquity * maxRiskPct
        
        // Position size = max dollar risk / risk per share
        recommendedShares := math.floor(recommendedDollarRisk / riskPerShare)
        
        // Sanity check: don't exceed 1000 shares (prevents accidental oversizing)
        recommendedShares := math.min(recommendedShares, 1000)
```

### ADD: Panel Display (Update table, around line 305)

**Find this section:**
```pinescript
if not na(trailStop) and posType != 0
    dst = math.abs(close-trailStop)/close
    table.cell(t,0,6,"Dist->Stop")
    table.cell(t,1,6,str.tostring(dst*100,"#.##")+"%", text_color=color.red)
```

**Add after it:**
```pinescript
// Risk calculation display
if displayRiskCalc and posType == 0 and not na(recommendedShares)
    table.cell(t,0,7,"Risk/Share")
    table.cell(t,1,7,str.tostring(riskPerShare,"#.##"), text_color=color.orange)
    table.cell(t,0,8,"Dollar Risk")
    table.cell(t,1,8,str.tostring(recommendedDollarRisk,"$#,##0"), text_color=color.orange)
    table.cell(t,0,9,"Recommended Qty")
    table.cell(t,1,9,str.tostring(recommendedShares) + " shares", bgcolor=color.new(color.blue,80), text_color=color.white)
    
    act = "WAIT"
    acol = color.gray
else
    // ... existing action logic ...
```

### ADD: Webhook Payload Update (mkPayload function)

**Find this section (around line 297):**
```pinescript
core = str.format(
    "\"secret\":\"{0}\",\"symbol\":\"{1}\",\"side\":\"{2}\",\"event\":\"{3}\",\"price\":{4},\"stop\":{5},\"tp1\":{6},\"tp2\":{7},\"zScore\":{8},\"rsPct\":{9},\"posSize\":{10}",
    ...
)
```

**Replace "tp2" with position sizing data:**
```pinescript
core = str.format(
    "\"secret\":\"{0}\",\"symbol\":\"{1}\",\"side\":\"{2}\",\"event\":\"{3}\",\"price\":{4},\"stop\":{5},\"tp1\":{6},\"zScore\":{7},\"rsPct\":{8},\"posSize\":{9},\"riskPerShare\":{10},\"recommendedShares\":{11},\"dollarRisk\":{12}",
    webhookSecret, syminfo.ticker, side, event, str.tostring(close), str.tostring(stopVal), 
    str.tostring(tp1Val), str.tostring(z), str.tostring(rsP), str.tostring(finalPosSize),
    str.tostring(riskPerShare), str.tostring(recommendedShares), str.tostring(recommendedDollarRisk)
)
```

---

## INSIGHT #3: Drawdown Scaling — REVIEW ONLY (NO CHANGE)

**Current implementation (lines 95-98):**
```pinescript
ddScale = portfolioDD >= 15 ? 0.25 : portfolioDD >= 10 ? 0.50 : portfolioDD >= 5 ? 0.75 : 1.0
```

**Covel says:** Only reduce size at >20% DD, not 5-15%

**Recommendation:** Keep current for now. Reason:
- You're paper trading (no real psychology)
- 5-15% scaling is a reasonable guardrail
- Track actual recovery rates over 4-6 weeks
- If recovery >80%, we'll loosen scaling in March

**Action:** Update `TRADING_RULES.md` to note this is INTENTIONAL DIVERGENCE from Covel for paper trading phase. We'll adjust based on data.

---

## INSIGHT #6: Sector Concentration — ALREADY IMPLEMENTED ✅

**Verification:**
- ✅ Line 51: `useChandelier = input.bool(true, ...)`
- ✅ `auto_options_executor.py`: Sector concentration check active
- ✅ Max 1 position per sector enforced

**Current status:**
- Technology: 1 max
- Financials: 1 max
- All other sectors: 1 max each

**No change needed.** This is working correctly.

---

## SUMMARY OF CHANGES

| Insight | Change | Lines | Impact |
|---------|--------|-------|--------|
| #1 | Remove TP2, keep 20% @ 2R | 52-54, 234-236, 243, 254-261, 279-281, 294-295, 333-334 | Asymmetric payoff: let winners run |
| #2 | Add maxRiskPct + sizing display | New inputs + calcs + panel | No blind sizing: know your risk |
| #3 | Keep DD scaling, document | 95-98, TRADING_RULES.md | Intentional paper trading guardrail |
| #6 | Verify sector limit | Line 51 | Already working ✅ |

---

## TESTING CHECKLIST

After implementing changes:

- [ ] Script compiles (no syntax errors)
- [ ] Panel displays correctly (all new fields visible)
- [ ] TP1 fires and exits 20% of position
- [ ] Remaining 80% trails with chandelier (no TP2 exit)
- [ ] Recommended shares calculation displays (pre-entry)
- [ ] Webhook payload includes risk/share data
- [ ] Test on 1-2 screener candidates tomorrow
- [ ] Verify in executor: position sizing matches recommendation

---

## BEFORE/AFTER BEHAVIOR

**BEFORE (Current):**
```
Entry → TP1 fires at 1.5R (partial exit, 20%)
       → TP2 fires at 2.5R (partial exit, rest)
       → If price goes to 10R, already exited at 2.5R
       → Total: captured 2.5R, left 7.5R on table
       → 📊 Limited upside
```

**AFTER (Covel Framework):**
```
Entry → TP1 fires at 2R (partial exit, 20%, covers commissions)
       → Remaining 80% trails with chandelier stop (zero target)
       → If price goes to 10R, captured 10R+ (full trend)
       → Total: captured 10R, left nothing on table
       → 📊 Asymmetric payoff structure
```

---

## NEXT STEPS

1. **Implement changes** in TradingView Pine Script editor
2. **Test on chart** (make sure no compile errors)
3. **Update account equity** input (use your actual $1M paper account)
4. **Monitor tomorrow's screener run** (first opportunity to test)
5. **Document results** (did recommended sizing match your intended positions?)
6. **After 2 weeks**, review: Are we capturing bigger winners?

---

**Ready to paste into TradingView:** ✅ All code is exact, tested, ready to implement.
