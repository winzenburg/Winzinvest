# Screener Long Position Setup — Quick Reference

**When manually reviewing candidates on TradingView, use this checklist**

---

## The Ideal LONG Setup (Tier 3)

### Core Metrics ✅

| Metric | Ideal Range | What It Means | Red Flag |
|--------|-------------|---------------|----------|
| **CompScore** | ≥ 0.35 | Overall momentum + structure quality | < 0.35 = weak momentum |
| **Tier** | 3 (or 2) | Tier 3 is best, Tier 2 is acceptable | Tier 1 = skip |
| **RSPct** | ≥ 0.65 | Outperforming SPY (stronger stock) | < 0.60 = underperformer |
| **RVol** | ≥ 1.2 | At least 20% above average volume | < 1.0 = thin volume |
| **Z-Score** | ≥ 0.75 | Momentum strength (from Engine) | < 0.5 = weak entry |

### Price Structure ✅

| Check | Good | Bad |
|-------|------|-----|
| **Higher Highs** | Price > High[10] and High[10] > High[20] | Declining peaks (trend breaking) |
| **Higher Lows** | Low > Low[10] and Low[10] > Low[20] | Lower lows (weakness) |
| **Trend** | Consistent uptrend over 20+ bars | Choppy/sideways action |
| **Distance from 200 EMA** | Price well above EMA200 | Price at or below EMA200 |

### Risk Checks ✅

| Check | Good | Bad |
|-------|------|-----|
| **Volatility** | Normal ATR range (not spiking) | ATR > 1.5x 20-day avg (earnings nearby) |
| **Correlation to SPY** | |Corr| ≤ 0.80 | |Corr| > 0.80 (too correlated) |
| **Sector** | Sector outperforming SPY | Sector underperforming SPY |
| **Liquidity** | 20-day median $ vol ≥ $25M | Below $25M (hard to exit) |

---

## Visual Checklist (Look at Chart Directly)

**When you eyeball the candidate on TradingView:**

```
✅ IDEAL LONG SETUP:
┌─────────────────────────────────────────┐
│ Price well above 200 EMA (bullish)      │ ← Price > EMA200
├─────────────────────────────────────────┤
│ Clear uptrend, higher highs & lows      │ ← HH/HL pattern
├─────────────────────────────────────────┤
│ Volume bars above average, not spiking  │ ← RVol 1.2-2.0x
├─────────────────────────────────────────┤
│ No massive gaps or drops (clean trend)  │ ← No recent shocks
├─────────────────────────────────────────┤
│ RS Pct > 0.65 (beating SPY)             │ ← Leader, not laggard
└─────────────────────────────────────────┘

❌ AVOID (THESE ARE RED FLAGS):
─ Price below or at EMA200 (downtrend)
─ Lower highs OR lower lows (momentum failing)
─ Volume well below average (thin)
─ Massive ATR spike (earnings or event)
─ RS Pct < 0.60 (underperforming)
─ Choppy sideways (no clear direction)
```

---

## Quick Scoring (Manual Estimation)

**When you don't have the indicator, estimate CompScore:**

```
Score = (0.40 × momentum) + (0.20 × HTF bias) + (0.20 × volume) + (0.20 × structure)

Where:
  Momentum (0-1):
    • 0.0 = Down trend
    • 0.5 = Flat/choppy
    • 1.0 = Strong uptrend
  
  HTF Bias (0-1):
    • Weekly & monthly trending up = 0.8-1.0
    • Mixed = 0.5
    • Both down = 0.0-0.2
  
  Volume (-0-1):
    • RVol > 1.5x = 0.8-1.0
    • RVol 1.2-1.5x = 0.6-0.8
    • RVol < 1.0 = 0.2
  
  Structure (0-1):
    • Clear HH/HL + clean trend = 0.8-1.0
    • Partial HH/HL + some noise = 0.5
    • Choppy/reversals = 0.0-0.3

TARGET: CompScore ≥ 0.35 (Tier 3)
```

---

## Tier Breakdown

### Tier 3 (🌟 BEST)
**CompScore ≥ 0.35**
- Strongest momentum + structure + volume
- Best entry confidence
- Trade at full position size (100%)
- Example: Clean uptrend, RS 0.72, RVol 1.8x

### Tier 2 (⭐ GOOD)
**CompScore 0.20-0.34**
- Decent momentum + okay structure
- Acceptable entry
- Trade at 70-80% position size
- Example: Uptrend, RS 0.68, RVol 1.3x, some choppy action

### Tier 1 (❌ WEAK)
**CompScore < 0.20**
- Weak momentum, structure issues
- Skip these (wait for T3/T2)
- Example: Sideways action, RS 0.55, low volume

---

## Real-World Examples

### Example 1: IDEAL LONG (Tier 3)
```
Symbol: NVDA
CompScore: 0.58 (T3) ✅
RSPct: 0.74 ✅ (outperforming SPY)
RVol: 1.9x ✅ (strong volume)
Z-Score: 1.45 ✅ (strong momentum)
Price: $875 (well above 200 EMA at $820)
Structure: Clear HH/HL, uptrend intact
Sector: Tech outperforming
Volume: $3.2B+ ✅

ACTION: BUY
Recommended Qty: 45 shares (2% risk)
Entry: $875, Stop: $850, TP1: $900
```

### Example 2: GOOD LONG (Tier 2)
```
Symbol: JPM
CompScore: 0.31 (T2) ✅
RSPct: 0.68 ✅ (okay relative strength)
RVol: 1.2x ✅ (just above threshold)
Z-Score: 0.92 ⚠️ (moderate momentum)
Price: $215 (above 200 EMA at $195)
Structure: HH/HL but some consolidation
Sector: Financials flat vs SPY
Volume: Okay ($1.8B+)

ACTION: BUY (reduced size)
Recommended Qty: 32 shares (2% risk, 70% sizing)
Entry: $215, Stop: $208, TP1: $225
```

### Example 3: SKIP (Tier 1)
```
Symbol: GE
CompScore: 0.18 (T1) ❌
RSPct: 0.42 ❌ (underperforming SPY)
RVol: 0.8x ❌ (below volume threshold)
Z-Score: -0.15 ❌ (weak/downtrend)
Price: $145 (below 200 EMA at $150)
Structure: Lower lows, downtrend
Sector: Industrials underperforming
Volume: Thin

ACTION: SKIP
Wait for better setup
```

---

## Decision Flow (Manual Screening)

```
Found a candidate? Start here:

1. CHECK TIER
   CompScore ≥ 0.35? YES → Continue
   NO → Skip, wait for T3/T2

2. CHECK PRICE STRUCTURE
   Price > 200 EMA? YES → Continue
   NO → Skip (downtrend)

3. CHECK RELATIVE STRENGTH
   RSPct ≥ 0.65? YES → Continue
   NO → Skip (underperformer)

4. CHECK VOLUME
   RVol ≥ 1.2x? YES → Continue
   NO → Skip (thin liquidity)

5. CHECK VOLATILITY
   ATR normal (not spiking)? YES → Continue
   NO → Skip (earnings coming)

6. CHECK CHART PATTERN
   Clear HH/HL uptrend? YES → Continue
   NO → Skip (choppy/reversing)

7. CHECK SECTOR
   Sector > SPY performance? YES → Continue
   NO → Skip (sector headwind)

✅ PASS ALL CHECKS → READY TO ENTER
Entry: Current price
Stop: 1.5x ATR below entry (or recent low)
TP1: Entry + 2R (2 × stop distance)
Trail: 80% of position with Chandelier stop
```

---

## Quick Mental Math for Position Sizing

**Your 2% risk formula:**

```
Risk/Share = Entry Price - Stop Loss
Dollar Risk = $1,000,000 (account) × 2% = $20,000
Recommended Qty = $20,000 / Risk/Share

Examples:
  Entry $100, Stop $95 → Risk/Share = $5 → Qty = 4,000 shares (oops, too big!)
  Entry $150, Stop $147 → Risk/Share = $3 → Qty = 6,667 shares (still too big!)
  Entry $200, Stop $195 → Risk/Share = $5 → Qty = 4,000 shares (capped at 1,000 max!)
  
Reality: Most positions will be 30-150 shares due to stock price × stop distance
```

---

## Screener Metrics (Copy-Paste Reference)

**If you're looking at TradingView indicator output, here are the plots:**

- **Signal** = 1 means "screener match" (ready to check manually)
- **CompScore** = Composite score 0-1.0 (higher is better)
- **Tier** = 1, 2, or 3 (3 is best)
- **RSPct** = 0-1.0 where 0.65+ is good for longs
- **RVol** = Relative volume 1.0-3.0+ (1.2+ is acceptable)
- **StructQ** = Structure score 0-1.0 (0.5+ is good)
- **HTFBias** = -1 to +1 (0.5+ is bullish)
- **LongReady** = 1 means "ready for long entry"
- **Regime** = 0=squeeze, 1=normal, 2=breakout (2 is best for longs)

---

## Summary: The Ideal Long Position

**In one sentence:**
> A Tier 3 candidate with RS > 0.65, RVol > 1.2x, price above EMA200, clear higher highs/lows, and no earnings volatility nearby.

**Quick checklist before entering:**
- ✅ CompScore ≥ 0.35
- ✅ RSPct ≥ 0.65
- ✅ RVol ≥ 1.2x
- ✅ Price > 200 EMA
- ✅ Higher Highs & Lows
- ✅ ATR normal (not spiking)
- ✅ No earnings blackout
- ✅ Stop loss makes sense (1.5x ATR from entry)

**Then:**
- Calculate position size: `$20,000 / risk per share`
- Set buy order for that quantity
- Set stop loss
- Set TP1 alert at 2R
- Let trailing stop run the 80%

---

**Happy screening! 🚀**
