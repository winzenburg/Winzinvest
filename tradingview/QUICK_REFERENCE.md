# TradingView Pine Scripts - Quick Reference

## 🎯 Signal Cheat Sheet

### Long Entry (Momentum)
```
✅ Composite > 0.65
✅ Structure > 0.50 (price above at least 2 MAs)
✅ HTF Bias > 0.45 (uptrend)
✅ Price > $5, Volume > 500K, Dollar Vol > $25M
```

### Short Entry (Momentum)
```
✅ Composite < 0.35
✅ Structure < 0.50 (price below at least 2 MAs)
✅ HTF Bias < 0.55 (downtrend)
✅ RS < 0.50 (underperforming SPY)
✅ RVol*ATR >= 1.0
```

### Mean Reversion Entry
```
✅ Price > SMA200 (uptrend)
✅ RSI(2) < 10 (oversold)
✅ Structure >= 0.67 (at least 2 of 3 MAs)
```

---

## 📊 Composite Score Interpretation

| Score | Meaning | Action |
|-------|---------|--------|
| 0.0-0.2 | Dead/choppy | ⚪ Skip |
| 0.2-0.5 | Weak trend | ⚠️ Watch |
| 0.5-0.8 | Strong trend | ✅ Trade |
| 0.8-1.0 | Extreme | ⚠️ Reversal risk |

**For Longs**: > 0.65  
**For Shorts**: < 0.35

---

## 🎚️ Tier System

### Tier 3 (Best)
- **Longs**: Composite >= 0.65, Structure >= 0.75, HTF >= 0.60, RVol >= 1.2
- **Shorts**: Composite <= 0.35, Structure >= 0.75, HTF <= 0.45, Failed Bounce, RVol*ATR >= 1.5

### Tier 2 (Good)
- **Longs**: Composite >= 0.25, Structure >= 0.50, HTF >= 0.50
- **Shorts**: Composite <= 0.35, Structure >= 0.50, HTF <= 0.55, Below MA100

### Tier 1 (Okay)
- **Longs**: Composite >= 0.08, Structure >= 0.35, HTF >= 0.45
- **Shorts**: Composite <= 0.35, Structure >= 0.50, HTF <= 0.55

---

## 🚪 Exit Signals

### Long Exits
- Price < SMA20 (trend break)
- RSI < 40 (momentum fading)
- Composite < 0.50 (losing strength)

### Short Exits
- Price > SMA20 (trend break)
- RSI > 60 (momentum reversing)
- Composite > 0.50 (gaining strength)

### Mean Reversion Exits
- RSI(2) > 70 (overbought)
- Price > SMA20 (back to trend)

---

## 🔍 Stock Screener Setup

### 1. Add Indicator
```
Indicators → Pine Editor → Paste script → Add to Chart
```

### 2. Open Stock Screener
```
Top menu → Stock Screener → All Stocks
```

### 3. Add Filters
```
Filters → Indicator Values → [Your Indicator Name]
```

### 4. Long Screener Filters
```
NX_Long_Signal = 1
Market Cap > 1B
Average Volume > 500K
Price > $5
Sort by: NX_Tier (descending)
```

### 5. Short Screener Filters
```
NX_Short_Signal = 1
Market Cap > 1B
Average Volume > 500K
Price > $5
Sector = Technology (optional, for QQQ plays)
Sort by: NX_Tier (descending)
```

### 6. Mean Reversion Filters
```
NX_MR_Entry = 1
Price > SMA(200)
Market Cap > 1B
Average Volume > 500K
Sort by: NX_RSI2 (ascending - most oversold first)
```

---

## 📈 Indicator Columns

### Long Screener Output
- `NX_Composite`: Composite score (higher = stronger)
- `NX_Structure`: Structure quality (0-1)
- `NX_HTF`: HTF bias (higher = uptrend)
- `NX_RVol`: Relative volume (1.0 = average)
- `NX_Long_Signal`: 1 = qualified, 0 = not
- `NX_Tier`: 3 = best, 2 = good, 1 = okay

### Short Screener Output
- `NX_Composite`: Composite score (lower = weaker)
- `NX_Structure`: Structure quality (higher = more MAs above)
- `NX_HTF`: HTF bias (lower = downtrend)
- `NX_RS`: Relative strength vs SPY (negative = underperforming)
- `NX_RVolATR`: Volume * volatility
- `NX_Short_Signal`: 1 = qualified, 0 = not
- `NX_Tier`: 3 = best, 2 = good, 1 = okay
- `NX_FailedBounce`: 1 = yes, 0 = no

### Mean Reversion Output
- `NX_RSI2`: RSI(2) value (lower = more oversold)
- `NX_Structure`: Structure quality (0-1)
- `NX_Above200`: % above SMA200
- `NX_MR_Entry`: 1 = entry signal
- `NX_MR_Exit`: 1 = exit signal

---

## ⚙️ Quick Customization

### Make More Aggressive (More Signals)
```pine
// In the script inputs
long_threshold = 0.55  // Instead of 0.65
short_threshold = 0.45  // Instead of 0.35
rsi2_oversold = 15     // Instead of 10
```

### Make More Conservative (Fewer Signals)
```pine
// In the script inputs
long_threshold = 0.75  // Instead of 0.65
short_threshold = 0.25  // Instead of 0.35
rsi2_oversold = 5      // Instead of 10
```

---

## 🔔 Alert Setup

### 1. Right-click indicator on chart
### 2. Select "Add Alert"
### 3. Choose condition:
- `Long Entry` / `Short Entry` / `MR Entry`
### 4. Set alert actions:
- ✅ Notify on App
- ✅ Send Email
- ✅ Show Popup
- ✅ Play Sound
### 5. Click "Create"

---

## 📅 Daily Workflow

### Morning (9:00 AM ET)
1. Run Long Screener → Sort by Tier → Review Tier 3 & 2
2. Run Short Screener → Sort by Tier → Review Tier 3 & 2
3. Run MR Screener → Sort by RSI2 → Review RSI < 5
4. Check charts manually
5. Place orders in Mission Control

### Midday (12:00 PM ET)
1. Re-run screeners for new setups
2. Check existing positions for exit signals
3. Adjust stops if needed

### End of Day (3:30 PM ET)
1. Review all open positions
2. Check for exit signals
3. Prepare watchlist for next day

---

## 🎓 Key Concepts

### Composite Score
**Formula**: (Momentum × 0.4) + (BB Position × 0.3) + (RSI Norm × 0.3)  
**Range**: 0.0 (weak) to 1.0 (strong)  
**Purpose**: Single number for trend strength

### Structure Quality
**Formula**: Count of MAs price is above / Total MAs  
**Range**: 0.0 (below all) to 1.0 (above all)  
**Purpose**: Measure trend quality

### HTF Bias
**Formula**: 50-day momentum normalized  
**Range**: 0.0 (downtrend) to 1.0 (uptrend)  
**Purpose**: Higher timeframe context

### Relative Strength
**Formula**: (Stock Return - SPY Return) / SPY Volatility  
**Range**: -1.0 (underperforming) to 1.0 (outperforming)  
**Purpose**: Find leaders and laggards

---

## 🐛 Common Issues

### No results in screener
→ Lower thresholds or expand universe

### Too many results
→ Raise thresholds or focus on Tier 3 only

### Signals don't match Mission Control
→ TradingView data may differ slightly from yfinance

### Indicator doesn't appear
→ Check Pine Editor for errors (red underlines)

---

## 📞 Quick Links

**Full Documentation**: `tradingview/README.md`  
**Strategy Details**: `trading/docs/NX_SCREENER_TECHNICAL_SPEC.md`  
**Mission Control Dashboard**: `trading-dashboard-public/`  

---

**Last Updated**: March 7, 2026  
**Version**: 1.0.0
