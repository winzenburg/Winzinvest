# TradingView Pine Scripts - File Index

## 📁 Directory Structure

```
tradingview/
├── INDEX.md                              ← You are here
├── TRADINGVIEW_SUMMARY.md                ← Start here (overview)
├── README.md                             ← Full documentation
├── QUICK_REFERENCE.md                    ← Cheat sheet
│
├── NX_Composite_Indicator.pine           ← Composite score visualization
├── NX_Relative_Strength_Indicator.pine   ← RS vs SPY
├── NX_Complete_System_Indicator.pine     ← All-in-one system
│
├── NX_Long_Screener.pine                 ← Long candidate scanner
├── NX_Short_Screener.pine                ← Short candidate scanner
└── NX_Mean_Reversion_Screener.pine       ← RSI(2) pullback scanner
```

---

## 🚀 Quick Start

1. **New to TradingView?**  
   → Read `TRADINGVIEW_SUMMARY.md` first

2. **Need setup instructions?**  
   → Read `README.md` sections 1-3

3. **Need a quick reference?**  
   → Use `QUICK_REFERENCE.md`

4. **Ready to add indicators?**  
   → Copy `.pine` files to TradingView Pine Editor

---

## 📄 File Descriptions

### Documentation Files

| File | Purpose | Read Time |
|------|---------|-----------|
| `TRADINGVIEW_SUMMARY.md` | Overview, what was created, how it matches Mission Control | 5 min |
| `README.md` | Complete guide with setup, usage, troubleshooting | 15 min |
| `QUICK_REFERENCE.md` | Cheat sheet for signals, thresholds, daily workflow | 3 min |
| `INDEX.md` | This file - directory structure and quick links | 1 min |

### Indicator Files (Add to Charts)

| File | Type | Purpose | Overlay |
|------|------|---------|---------|
| `NX_Composite_Indicator.pine` | Indicator | Visualize composite score | No (separate pane) |
| `NX_Relative_Strength_Indicator.pine` | Indicator | Visualize RS vs SPY | No (separate pane) |
| `NX_Complete_System_Indicator.pine` | Indicator | All-in-one with signals | Yes (on price chart) |

### Screener Files (Use with Stock Screener)

| File | Type | Purpose | Output Columns |
|------|------|---------|----------------|
| `NX_Long_Screener.pine` | Screener | Find long candidates | Composite, Structure, HTF, RVol, Signal, Tier |
| `NX_Short_Screener.pine` | Screener | Find short candidates | Composite, Structure, HTF, RS, RVolATR, Signal, Tier |
| `NX_Mean_Reversion_Screener.pine` | Screener | Find RSI(2) pullbacks | RSI2, Structure, Above200, Entry, Exit |

---

## 🎯 Use Cases

### "I want to visualize the composite score on a chart"
→ Use `NX_Composite_Indicator.pine`

### "I want to see all signals and MAs on one chart"
→ Use `NX_Complete_System_Indicator.pine`

### "I want to scan for long candidates"
→ Use `NX_Long_Screener.pine` with Stock Screener

### "I want to scan for short candidates"
→ Use `NX_Short_Screener.pine` with Stock Screener

### "I want to find RSI(2) pullbacks"
→ Use `NX_Mean_Reversion_Screener.pine` with Stock Screener

### "I want to compare a stock to SPY"
→ Use `NX_Relative_Strength_Indicator.pine`

### "I need a quick reminder of the signals"
→ Use `QUICK_REFERENCE.md`

### "I need full setup instructions"
→ Use `README.md`

---

## 📊 Strategy Overview

### Momentum Longs
- **Entry**: Composite > 0.65, Structure > 0.50, HTF > 0.45
- **Exit**: Price < SMA20 or RSI < 40
- **Screener**: `NX_Long_Screener.pine`

### Momentum Shorts
- **Entry**: Composite < 0.35, Structure < 0.50, HTF < 0.55, RS < 0.50
- **Exit**: Price > SMA20 or RSI > 60
- **Screener**: `NX_Short_Screener.pine`

### Mean Reversion
- **Entry**: RSI(2) < 10, Price > SMA200, Structure >= 0.67
- **Exit**: RSI(2) > 70 or Price > SMA20
- **Screener**: `NX_Mean_Reversion_Screener.pine`

---

## 🔗 Related Files

### Mission Control Python Scripts
- `trading/scripts/nx_screener_production.py` - Python version of screener
- `trading/scripts/mr_screener.py` - Python mean reversion screener
- `trading/docs/NX_SCREENER_TECHNICAL_SPEC.md` - Technical specification

### Mission Control Dashboard
- `trading-dashboard-public/app/page.tsx` - Main dashboard
- `trading-dashboard-public/app/strategy/page.tsx` - Strategy explanation
- `trading-dashboard-public/app/institutional/page.tsx` - Institutional dashboard

### Risk Configuration
- `trading/risk.json` - Risk parameters
- `trading/scripts/risk_config.py` - Risk calculation helpers
- `trading/scripts/execution_gates.py` - Gate enforcement

---

## 📈 Integration Flow

```
┌─────────────────┐
│   TradingView   │  ← Discovery & Visualization
│   Pine Scripts  │
└────────┬────────┘
         │
         │ Candidates
         ↓
┌─────────────────┐
│ Mission Control │  ← Verification & Execution
│ Python Screener │
└────────┬────────┘
         │
         │ Verified Trades
         ↓
┌─────────────────┐
│  IBKR Execution │  ← Order Placement
│   + Dashboard   │
└─────────────────┘
```

---

## 🎓 Learning Path

### Beginner
1. Read `TRADINGVIEW_SUMMARY.md`
2. Add `NX_Complete_System_Indicator.pine` to a chart
3. Watch for entry signals (triangles)
4. Use `QUICK_REFERENCE.md` for signal interpretation

### Intermediate
1. Read `README.md` sections 1-6
2. Add all 3 indicators to charts
3. Set up Stock Screener with `NX_Long_Screener.pine`
4. Create alerts for entry signals

### Advanced
1. Read full `README.md`
2. Set up all 3 screeners
3. Customize thresholds for your preferences
4. Integrate with Mission Control Python scripts
5. Track performance by tier

---

## 🔧 Customization Guide

### Adjust Signal Thresholds
Edit input parameters in each `.pine` file:
```pine
long_threshold = 0.65  // Change to 0.55 for more signals, 0.75 for fewer
short_threshold = 0.35  // Change to 0.45 for more signals, 0.25 for fewer
```

### Add Custom Filters
Add conditions in the screener files:
```pine
// Only trade stocks above $50
price_filter = close > 50

// Update signal
long_candidate = liquidity_pass and tier_1_pass and price_filter
```

### Change Timeframes
All indicators work on any timeframe:
- Daily (default)
- Weekly (for longer-term trends)
- 4-hour (for intraday)

---

## 📞 Support & Resources

### Documentation
- **This Directory**: All `.md` files
- **Mission Control Docs**: `trading/docs/`
- **Dashboard Docs**: `trading-dashboard-public/README.md`

### TradingView Resources
- Pine Script Reference: https://www.tradingview.com/pine-script-reference/
- Stock Screener Guide: https://www.tradingview.com/screener/
- Community Scripts: https://www.tradingview.com/scripts/

### Mission Control Resources
- Main README: `README.md` (project root)
- Strategy Guide: `trading-dashboard-public/app/strategy/page.tsx`
- Technical Spec: `trading/docs/NX_SCREENER_TECHNICAL_SPEC.md`

---

## ✅ Checklist

### Setup
- [ ] Read `TRADINGVIEW_SUMMARY.md`
- [ ] Add `NX_Complete_System_Indicator.pine` to TradingView
- [ ] Test on known stocks (AAPL, NVDA, SPY)
- [ ] Set up Stock Screener with `NX_Long_Screener.pine`
- [ ] Create alerts for entry signals

### Daily Use
- [ ] Run Long Screener (9:00 AM ET)
- [ ] Run Short Screener (9:00 AM ET)
- [ ] Run MR Screener (9:00 AM ET)
- [ ] Review charts manually
- [ ] Cross-check with Mission Control
- [ ] Place orders

### Optimization
- [ ] Track results by tier
- [ ] Adjust thresholds based on performance
- [ ] Add custom filters for your style
- [ ] Integrate with Mission Control workflow

---

## 🎯 Next Steps

1. **Start Here**: Read `TRADINGVIEW_SUMMARY.md`
2. **Then**: Follow setup in `README.md`
3. **Reference**: Use `QUICK_REFERENCE.md` daily
4. **Customize**: Adjust thresholds in `.pine` files
5. **Integrate**: Connect with Mission Control Python scripts

---

**Last Updated**: March 7, 2026  
**Version**: 1.0.0  
**Files**: 9 total (3 docs, 3 indicators, 3 screeners)
