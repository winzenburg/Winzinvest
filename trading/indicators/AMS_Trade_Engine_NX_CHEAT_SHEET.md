# AMS Trade Engine NX - Metrics Cheat Sheet

Quick reference for the indicator panel metrics.

---

## HTF (Higher Timeframe Confirm)

**What it shows**: Direction of momentum on the higher timeframe (default: Weekly)

| Symbol | Meaning | Interpretation |
|--------|---------|----------------|
| **▲** | Weekly momentum positive | Confirms long bias - higher timeframe is rising |
| **▼** | Weekly momentum negative | Confirms short bias - higher timeframe is falling |
| **→** | Weekly momentum neutral | No clear higher timeframe trend |

**How to use**: Look for alignment between HTF and daily signals. Long entries are stronger when HTF shows ▲, short entries stronger when HTF shows ▼.

---

## Z (Z-Score)

**What it shows**: How extreme current momentum is compared to recent history (252-day lookback)

| Range | Interpretation |
|-------|----------------|
| **+2.0 or higher** | Extremely overbought - momentum 2+ std devs above average |
| **+1.0 to +2.0** | Strong bullish momentum (entry threshold: ≥1.0) |
| **0 to +1.0** | Moderate bullish momentum |
| **0 to -1.0** | Moderate bearish momentum |
| **-1.0 to -2.0** | Strong bearish momentum (short entry: ≤-1.0) |
| **-2.0 or lower** | Extremely oversold - momentum 2+ std devs below average |

**Color coding**:
- 🟢 Green = Positive Z (bullish momentum)
- 🔴 Red = Negative Z (bearish momentum)

**Entry thresholds**:
- **Long**: Z ≥ 1.0 (default)
- **Short**: Z ≤ -1.0 (default)
- **Exit**: Z ≤ -0.5 (momentum fading)

**How to use**: Higher Z = stronger momentum. Look for Z ≥ 1.0 for long entries. Avoid entries when Z is near zero (weak momentum).

---

## RS pct (Relative Strength Percentile)

**What it shows**: How strong this stock is vs. SPY over the past 252 days, expressed as a percentile

| Range | Interpretation |
|-------|----------------|
| **80-100%** | Top 20% - extremely strong vs market |
| **60-79%** | Above average - outperforming (long threshold: ≥60%) |
| **40-59%** | Average - moving with market |
| **21-39%** | Below average - underperforming (short threshold: ≤40%) |
| **0-20%** | Bottom 20% - extremely weak vs market |

**Color coding**:
- 🟢 Green = Meets threshold (≥60% for longs, ≤40% for shorts)
- 🔴 Red = Does NOT meet threshold

**How to use**: 
- For **longs**: Want RS pct ≥ 60% (stock is outperforming SPY)
- For **shorts**: Want RS pct ≤ 40% (stock is underperforming SPY)
- Avoid stocks in the 40-60% range (moving with the market, no edge)

---

## Pos (Position)

**What it shows**: Current position state tracked by the indicator

| Display | Meaning |
|---------|---------|
| **LONG** 🟢 | In a long position |
| **SHORT** 🔴 | In a short position |
| **FLAT** ⚪ | No position - waiting for setup |

**How to use**: Shows whether the system is currently holding a position or waiting for entry conditions.

---

## Size (Position Size)

**What it shows**: Volatility-adjusted position sizing recommendation (as a multiplier)

| Range | Interpretation |
|-------|----------------|
| **2.0x** | Very low volatility - can size up to max leverage |
| **1.5-2.0x** | Below average volatility - size above normal |
| **1.0-1.5x** | Normal volatility - standard position size |
| **0.5-1.0x** | Elevated volatility - size down |
| **0.25-0.5x** | High volatility - minimal position size |

**Color coding**:
- 🟢 Green = Size > 1.0x (low vol, can size up)
- 🟠 Orange = Size < 1.0x (high vol, size down)

**How to use**: This is an **advisory sizing multiplier** based on realized volatility. Higher volatility = smaller position size to maintain consistent risk. The system targets 12% annualized portfolio volatility.

**Example**: 
- If your standard position is $10,000
- Size shows **1.5x** → Consider $15,000 position
- Size shows **0.5x** → Consider $5,000 position

---

## Dist->Stop (Distance to Stop)

**What it shows**: Percentage distance from current price to the stop loss

| Range | Interpretation |
|-------|----------------|
| **> 5%** | Wide stop - more breathing room, larger R |
| **3-5%** | Normal swing trade stop |
| **< 3%** | Tight stop - less room, but smaller R |

**How to use**: Tells you how much price can move against you before hitting the stop. Helps calculate position sizing and understand your risk per share.

---

## Action (Trading Action)

**What it shows**: Current recommended action based on all conditions

| Display | Meaning | What to Do |
|---------|---------|------------|
| **BUY NOW** 🟢 | Long entry triggered | Enter long position at market |
| **SHORT NOW** 🔴 | Short entry triggered | Enter short position at market |
| **EXIT** 🟠 | Exit signal triggered | Close current position immediately |
| **HOLD** 🔵 | In position, no exit signal | Maintain current position, trail stop |
| **WAIT** ⚪ | No setup | Stay flat, wait for entry conditions |

**How to use**: The most actionable metric. When **BUY NOW** or **SHORT NOW** appears and an alert fires, that's your entry signal. When **EXIT** appears, close the position.

---

## Quick Decision Matrix

### For LONG entries, you want to see:
- HTF: **▲** (weekly rising)
- Z: **≥ 1.0** (strong bullish momentum)
- RS pct: **≥ 60%** 🟢 (outperforming SPY)
- Pos: **FLAT** (no current position)
- Action: **BUY NOW** 🟢

### For SHORT entries, you want to see:
- HTF: **▼** (weekly falling)
- Z: **≤ -1.0** (strong bearish momentum)
- RS pct: **≤ 40%** 🔴 (underperforming SPY)
- Pos: **FLAT** (no current position)
- Action: **SHORT NOW** 🔴

### For position management:
- Watch **Dist->Stop** to understand your risk
- Use **Size** to adjust position based on volatility
- Exit when **Action** shows **EXIT** 🟠

---

## Risk Management Reminders

1. **Partial Profits**: System targets 1.5R for TP1 (taking partial profits)
2. **Breakeven Move**: After TP1 is hit, stop moves to breakeven
3. **Chandelier Stop**: Trailing stop that ratchets up (longs) or down (shorts) as price moves favorably
4. **Fail-Safe**: Hard stop at 15% loss if chandelier hasn't triggered
5. **Tie-In Enforcement**: Symbol must have been "Ready" in screener within past 10 days

## Optional Filters (Signal Hygiene)

### Regime Filter (EMA200)
- **ON**: Only allows longs above EMA200, shorts below EMA200
- **OFF**: Allows entries regardless of EMA200 position
- **Why it helps**: Reduces counter-trend whipsaw by aligning with major trend

### Cooldown After Exit
- **ON**: Waits N bars (default: 3) after exit before allowing new entry
- **OFF**: Can re-enter immediately if signal triggers
- **Why it helps**: Prevents chop by avoiding immediate re-entry after stop-out

**Best Practice**: Enable both filters for cleaner signals, especially in choppy markets.

---

## Color Legend

| Color | Context | Meaning |
|-------|---------|---------|
| 🟢 **Green** | Z > 0, RS meets threshold, Long signals | Bullish / Favorable |
| 🔴 **Red** | Z < 0, RS below threshold, Short signals | Bearish / Unfavorable |
| 🟠 **Orange** | Exit signals, warnings | Caution / Action Required |
| 🔵 **Blue** | Hold state | Maintain position |
| ⚪ **Gray** | Flat, waiting | Neutral / No position |

---

*Generated for AMS Trade Engine NX (Non-Repainting Daily)*
