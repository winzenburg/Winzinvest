# Mission Control - TradingView Pine Scripts

Pine Script indicators and screeners that match Mission Control's trading strategy.

---

## 📊 Indicators

### 1. NX_Composite_Indicator.pine
**Purpose**: Visualize the NX Composite Score on any chart

**Components**:
- Momentum (40%): 20-day return normalized to [0, 1]
- BB Position (30%): Position within Bollinger Bands
- RSI Normalized (30%): RSI mapped to [0, 1]

**Thresholds**:
- **> 0.65**: Strong uptrend (long entry)
- **< 0.35**: Strong downtrend (short entry)
- **0.08**: Tier 2 minimum
- **0.25**: Tier 3 minimum

**How to use**:
1. Open TradingView chart
2. Click "Indicators" → "+" → "My Scripts"
3. Paste `NX_Composite_Indicator.pine`
4. Apply to chart
5. Indicator appears in separate pane below price

**What you see**:
- White line = Composite score
- Green zone = Long entry area (> 0.65)
- Red zone = Short entry area (< 0.35)
- Info table = Real-time breakdown of components

---

### 2. NX_Relative_Strength_Indicator.pine
**Purpose**: Measure stock performance vs SPY over 252 days

**Formula**:
```
RS = (Stock Return - SPY Return) / SPY Volatility
Normalized to [-1.0, 1.0]
```

**Interpretation**:
- **> 0.50**: Strong outperformance (top long candidate)
- **> 0.02**: Weak outperformance (long candidate)
- **< -0.50**: Strong underperformance (short candidate)

**How to use**:
1. Add to chart (same as Composite)
2. Compare multiple stocks to find relative strength leaders
3. Use with Stock Screener to filter by RS

---

### 3. NX_Complete_System_Indicator.pine
**Purpose**: All-in-one system with entry/exit signals on the chart

**Features**:
- Shows all 4 moving averages (20, 50, 100, 200)
- Bollinger Bands
- Entry signals (triangles on chart)
- Background color for trend state
- Complete info panel with all metrics

**Signals**:
- **Green triangle** = Long entry (composite > 0.65, structure > 0.50, HTF > 0.45)
- **Red triangle** = Short entry (composite < 0.35, structure < 0.50, HTF < 0.55)

**How to use**:
1. Add to chart (overlays on price)
2. Wait for triangle signals
3. Check info panel for confirmation
4. Set alerts for entry signals

---

## 🔍 Screeners

### 4. NX_Long_Screener.pine
**Purpose**: Scan for momentum long candidates

**Criteria**:
- Composite > 0.08 (Tier 1), 0.25 (Tier 2), 0.65 (Tier 3)
- Structure quality > 0.35 (at least 2 MAs below price)
- HTF Bias > 0.45 (uptrend)
- Liquidity: Price > $5, Volume > 500K, Dollar volume > $25M

**How to use**:
1. Add indicator to TradingView
2. Open **Stock Screener** (top menu)
3. Click "Filter" → "Indicator Values"
4. Add filter: `NX_Long_Signal = 1`
5. Sort by `NX_Tier` descending (Tier 3 first)
6. Additional filters:
   - Market Cap > 1B
   - Average Volume > 500K
   - Price > $5

**Output columns**:
- `NX_Composite`: Composite score
- `NX_Structure`: Structure quality
- `NX_HTF`: Higher timeframe bias
- `NX_RVol`: Relative volume
- `NX_Long_Signal`: 1 = qualified, 0 = not qualified
- `NX_Tier`: 3 = best, 2 = good, 1 = okay

---

### 5. NX_Short_Screener.pine
**Purpose**: Scan for short candidates

**Criteria**:
- Composite < 0.35 (weak/downtrend)
- Structure quality > 0.50 (at least 2 MAs above price)
- HTF Bias < 0.55 (downtrend or neutral)
- RS < 0.50 (underperforming SPY)
- RVol*ATR >= 1.0 (sufficient volatility)
- Optional: Failed bounce, below MA100

**How to use**:
1. Add indicator to TradingView
2. Open **Stock Screener**
3. Add filter: `NX_Short_Signal = 1`
4. Sort by `NX_Tier` descending
5. Focus on Technology sector for QQQ weakness plays

**Output columns**:
- `NX_Composite`: Composite score (lower is better for shorts)
- `NX_Structure`: Structure quality (higher = more MAs above)
- `NX_HTF`: HTF bias (lower is better for shorts)
- `NX_RS`: Relative strength vs SPY (negative = underperforming)
- `NX_RVolATR`: Volume * volatility
- `NX_Short_Signal`: 1 = qualified, 0 = not
- `NX_Tier`: 3 = best, 2 = good, 1 = okay
- `NX_FailedBounce`: 1 = yes, 0 = no

---

### 6. NX_Mean_Reversion_Screener.pine
**Purpose**: Find RSI(2) pullbacks in uptrends

**Criteria**:
- Price > SMA200 (uptrend)
- RSI(2) < 10 (oversold)
- Structure quality >= 0.67 (at least 2 of 3 MAs)
- Liquidity gates pass

**How to use**:
1. Add indicator to TradingView
2. Open **Stock Screener**
3. Add filter: `NX_MR_Entry = 1`
4. Sort by `NX_RSI2` ascending (most oversold first)

**Exit signal**:
- RSI(2) > 70 (overbought)
- OR price crosses above SMA20

**Output columns**:
- `NX_RSI2`: RSI(2) value
- `NX_Structure`: Structure quality
- `NX_Above200`: % above SMA200
- `NX_MR_Entry`: 1 = entry signal
- `NX_MR_Exit`: 1 = exit signal

---

## 🚀 Quick Start

### Step 1: Add Indicators to TradingView

1. Go to TradingView.com
2. Open a chart (e.g., SPY)
3. Click "Indicators" button (top toolbar)
4. Click "Pine Editor" tab (bottom of screen)
5. Copy one of the `.pine` files
6. Paste into Pine Editor
7. Click "Add to Chart"
8. Repeat for other indicators

### Step 2: Set Up Stock Screener

1. Click "Stock Screener" (top menu)
2. Select "All Stocks" or your watchlist
3. Click "Filters" → "Indicator Values"
4. Find your indicator (e.g., "NX Long Screener")
5. Add filter: `NX_Long_Signal = 1`
6. Sort by `NX_Tier` descending
7. Click on stocks to see charts

### Step 3: Set Up Alerts

1. Open a chart with NX indicator
2. Right-click on indicator → "Add Alert"
3. Condition: "NX Long Entry" or "NX Short Entry"
4. Set alert actions (notification, email, webhook)
5. Click "Create"

---

## 📋 Strategy Summary

### Momentum Longs (NX_Long_Screener)
- **Entry**: Composite > 0.65, Structure > 0.50, HTF > 0.45
- **Exit**: Price < SMA20 or RSI < 40
- **Target**: Strong uptrends with quality structure
- **Hold time**: 3-10 days typically

### Momentum Shorts (NX_Short_Screener)
- **Entry**: Composite < 0.35, Structure < 0.50, HTF < 0.55, RS < 0.50
- **Exit**: Price > SMA20 or RSI > 60
- **Target**: Failed bounces, QQQ weakness, downtrends
- **Hold time**: 2-7 days typically

### Mean Reversion (NX_Mean_Reversion_Screener)
- **Entry**: RSI(2) < 10, Price > SMA200, Structure >= 0.67
- **Exit**: RSI(2) > 70 or Price > SMA20
- **Target**: Pullbacks in strong uptrends
- **Hold time**: 1-5 days typically

---

## 🎯 Recommended Workflow

### Daily Routine

**Morning (9:00 AM ET)**:
1. Run NX Long Screener → Get Tier 3 and Tier 2 candidates
2. Run NX Short Screener → Get Tier 3 and Tier 2 candidates
3. Run NX Mean Reversion Screener → Get RSI(2) < 10 candidates
4. Review charts manually for each candidate
5. Check Mission Control for position limits and risk gates
6. Place orders

**Midday (12:00 PM ET)**:
1. Re-run screeners for new setups
2. Check existing positions for exit signals
3. Adjust stops if needed

**End of Day (3:30 PM ET)**:
1. Review all open positions
2. Check for exit signals (RSI, MA crosses)
3. Prepare for next day

---

## 🔧 Customization

### Adjust Thresholds

Edit the input parameters in each script:

```pine
// Make it more aggressive (more signals)
long_threshold = 0.55  // Instead of 0.65

// Make it more conservative (fewer signals)
long_threshold = 0.75  // Instead of 0.65
```

### Add Your Own Filters

Add additional conditions:

```pine
// Only trade stocks above $50
price_filter = close > 50

// Only trade high volume stocks
volume_filter = avg_volume_20 > 1_000_000

// Update signal
long_candidate = liquidity_pass and tier_1_pass and price_filter and volume_filter
```

---

## 📊 Comparing to Mission Control

### What Matches
✅ Composite score formula (momentum + BB + RSI)  
✅ Structure quality (MAs above/below)  
✅ HTF bias calculation  
✅ Liquidity gates ($5, 500K vol, $25M dollar vol)  
✅ Entry/exit thresholds  

### What's Different
⚠️ **RS calculation**: TradingView's `request.security` may have slight differences from Python's yfinance  
⚠️ **Volume data**: TradingView volume may differ from yfinance  
⚠️ **Sector data**: TradingView doesn't have sector concentration limits  

### Recommendation
Use TradingView for **discovery and visualization**, but run final screening through Mission Control's Python scripts for exact matching and risk gate enforcement.

---

## 🎓 Learning Resources

### Understanding the Indicators

**Composite Score**:
- Combines 3 momentum measures
- Range: 0.0 (weak) to 1.0 (strong)
- > 0.65 = strong uptrend
- < 0.35 = strong downtrend

**Structure Quality**:
- Counts how many MAs price is above/below
- Range: 0.0 (below all) to 1.0 (above all)
- > 0.50 = bullish structure
- < 0.50 = bearish structure

**HTF Bias**:
- 50-day momentum normalized
- > 0.55 = uptrend
- < 0.45 = downtrend
- 0.45-0.55 = neutral

**Relative Strength**:
- Outperformance vs SPY
- Normalized by SPY volatility
- > 0.50 = strong outperformance
- < -0.50 = strong underperformance

---

## 🐛 Troubleshooting

### Indicator doesn't appear
- Check Pine Editor for syntax errors (red underlines)
- Make sure you clicked "Add to Chart"
- Try refreshing the page

### Screener shows no results
- Check filter values (e.g., `NX_Long_Signal = 1`)
- Expand universe (try "All Stocks" instead of watchlist)
- Lower thresholds temporarily to see if any stocks qualify

### Signals don't match Mission Control
- TradingView data may differ slightly from yfinance
- Check that you're using daily timeframe (not intraday)
- Verify liquidity filters match

### Too many signals
- Increase thresholds (e.g., long_threshold = 0.75)
- Add additional filters (market cap, sector, etc.)
- Focus on Tier 3 only

### Too few signals
- Decrease thresholds (e.g., long_threshold = 0.55)
- Include Tier 1 and Tier 2 candidates
- Expand universe

---

## 📁 File Summary

| File | Type | Purpose |
|------|------|---------|
| `NX_Composite_Indicator.pine` | Indicator | Visualize composite score |
| `NX_Relative_Strength_Indicator.pine` | Indicator | Visualize RS vs SPY |
| `NX_Complete_System_Indicator.pine` | Indicator | All-in-one with signals |
| `NX_Long_Screener.pine` | Screener | Find momentum long candidates |
| `NX_Short_Screener.pine` | Screener | Find short candidates |
| `NX_Mean_Reversion_Screener.pine` | Screener | Find RSI(2) pullbacks |

---

## 🎯 Next Steps

1. **Add all indicators to TradingView**
2. **Test on known stocks** (AAPL, NVDA, SPY) to verify calculations
3. **Set up Stock Screener** with filters
4. **Create alerts** for entry signals
5. **Compare results** with Mission Control's Python screeners
6. **Adjust thresholds** based on your preferences

---

## 📞 Support

**Questions about formulas?**  
→ See `trading/docs/NX_SCREENER_TECHNICAL_SPEC.md`

**Questions about strategy?**  
→ See `trading-dashboard-public/app/strategy/page.tsx`

**Questions about Pine Script syntax?**  
→ See TradingView Pine Script documentation

---

**Last Updated**: March 7, 2026  
**Version**: 1.0.0  
**Matches**: Mission Control NX Screener v2.0
