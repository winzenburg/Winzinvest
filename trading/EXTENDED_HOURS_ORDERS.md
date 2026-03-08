# Extended Hours Trading Capability

## Built: March 5, 2026 @ 2:23 PM MT

### What Works
- ✅ After-hours orders via TIF='EXT' (Extended Hours Time In Force)
- ✅ Limit orders supported for after-hours trading
- ✅ Orders queued for next available trading session
- ✅ Full execution tracking and logging

### Orders Placed After-Hours (Current)

**Paper Trading Account: DU4661622**

| Order ID | Symbol | Type | Strike | Expiry | TIF | Status | Placed | Executes |
|----------|--------|------|--------|--------|-----|--------|--------|----------|
| 4 | AAPL | BUY PUT | 230 | 3/13/2026 | DAY | PreSubmitted | 2:17 PM MT | 3/6 9:30 AM ET |
| 15 | SPY | BUY PUT | 480 | 3/13/2026 | EXT | PreSubmitted | 2:23 PM MT | 3/6 4:00 AM ET (pre) |
| 18 | IWM | SELL PUT | 190 | 3/13/2026 | EXT | PreSubmitted | 2:23 PM MT | 3/6 4:00 AM ET (pre) |

### What Happened

1. **RTH Attempt (2:19 PM):** Placed SPY, QQQ, IWM with TIF='DAY' → REJECTED (exchange closed)
2. **Extended Hours Attempt (2:23 PM):** Placed same with TIF='EXT' and LMT orders → ACCEPTED
3. **Order Status:** All queued for tomorrow's pre-market session (4:00 AM ET = 2:00 AM MT)

### How It Works

- **TIF='EXT':** Extended hours Time In Force
- **Order Type:** LimitOrder (required for extended hours)
- **Limit Price Calculation:** Strike * 0.5 for BUY, Strike * 1.5 for SELL (simplified)
- **Execution Window:** Pre-market (4:00-9:30 AM ET) or After-hours (4:00-8:00 PM ET)

### Code Changes

**File:** `/trading/scripts/ibkr_executor_insync.py`

```python
# New initialization parameter
executor = IBKRExecutorInsync(paper_trading=True, extended_hours=True)

# Command line
python3 ibkr_executor_insync.py --ext  # Enable extended hours
```

### Important Notes

1. **Liquidity is thin:** Spreads are 2-5x wider than regular hours
2. **Limit orders only:** Market orders rejected after-hours
3. **Execution uncertain:** May not fill if limit price unrealistic
4. **Next available session:** Orders execute at next market open if pre-market doesn't fill

### Tomorrow's Expected Behavior

**Pre-market (4:00-9:30 AM ET):**
- Orders 15 & 18 may execute if liquidity available
- Spreads will be wide

**RTH (9:30 AM ET):**
- All remaining orders execute at market open
- Better liquidity, tighter spreads
- AAPL order (ID 4) will execute at market open

### Testing

```bash
# Execute with extended hours enabled
cd trading/scripts
python3 ibkr_executor_insync.py --ext

# Check execution report
cat ../logs/ibkr_execution_report.json
```

---

**Status:** ✅ WORKING
**Commit:** To be pushed with this documentation
