# Premium Selling Strategy

**Status: ✅ BUILT & TESTED (March 5, 2026)**

## Overview

A volatility-aware premium selling system that adapts to market conditions. Designed for choppy/downtrend markets where trend-following struggles and elevated VIX creates fat option premiums.

## Strategy Logic

### Market Regime Detection
- **DOWNTREND**: SPY below 100-day MA → Focus on selling puts on defensive names
- **UPTREND**: SPY above 21-day MA → Sell calls on strong performers
- **CHOPPY**: SPY in middle → Balanced approach

### Position Sizing
- Base size: 1 contract per signal
- **VIX Multiplier**: Higher VIX = larger positions (up to 2x at VIX >30)
- **Regime Multiplier**: Downtrend = 0.75x (defensive), Uptrend = 1.25x (aggressive)

### Premium Thresholds
- **High VIX (>25)**: Accept >0.8% premium
- **Normal VIX (20-25)**: Accept >1.0% premium
- **Low VIX (<20)**: Accept >1.5% premium

## Current Market Setup (as of March 5, 2026)

- **Regime**: CHOPPY (SPY at 681.31, between MA21 686 and MA100 680)
- **VIX**: 23.75
- **Position Size**: 1 contract (1.5x VIX multiplier × 1.0x regime multiplier)

## Files

### Screener
- **File**: `trading/scripts/premium_seller_volatility_aware.py`
- **Output**: `trading/premium_signals.json`
- **Function**: Identifies premium selling candidates based on regime and VIX
- **Run**: `python3 trading/scripts/premium_seller_volatility_aware.py`

### Executor
- **File**: `trading/scripts/premium_executor.py`
- **Input**: `trading/premium_signals.json`
- **Output**: `trading/premium_execution_log.json`
- **Function**: Converts signals to IBKR webhook orders
- **Run**: `python3 trading/scripts/premium_executor.py --execute`

### Log Files
- **Screener Log**: `trading/logs/premium_seller_volatility.log`
- **Executor Log**: `trading/logs/premium_executor.log`

## Sample Output (March 5 Run)

Generated 11 signals:
- **9 Puts**: PG, JNJ, MSFT, PEP, COST, KO, JPM, MCD, TMO
- **2 Calls**: MSFT, AAPL

Premium range: 1.4% - 2.4%

## Usage

### Screener Only (Preview)
```bash
python3 trading/scripts/premium_seller_volatility_aware.py
```
Outputs: `premium_signals.json`

### Full Execution Pipeline
```bash
# 1. Run screener
python3 trading/scripts/premium_seller_volatility_aware.py

# 2. Review signals
cat trading/premium_signals.json

# 3. Execute (with IBKR webhook listener running)
python3 trading/scripts/premium_executor.py --execute
```

### Cron Integration
Add to cron for daily screening:
```bash
# Daily at 8:30 AM
30 8 * * * /usr/bin/python3 ~/.openclaw/workspace/trading/scripts/premium_seller_volatility_aware.py
```

## Integration with Main System

The premium selling signals flow through the same webhook listener as trend-following signals:
1. Screener generates puts/calls based on regime
2. Executor converts to webhook payloads
3. Webhook listener applies universal safety filters (circuit breaker, regime check, etc.)
4. IBKR executes if all gates pass

## Safety Guards

- **Regime-appropriate**: Skips calls entirely in downtrend
- **VIX-aware**: Adjusts sizing based on volatility environment
- **Premium minimum**: Only takes trades where premium justifies the risk
- **Quality names only**: Restricted universe of dividend payers and quality stocks

## Performance Expectations

- **Expected premium capture**: 1-2% per 45 DTE contract (fat environment)
- **Win rate**: 60-70% (premium decay works in our favor)
- **Max loss per contract**: Strike × 100 (fully collateralized)
- **Return on risk**: 2-5% per trade depending on premium size

## Next Steps

1. Monitor first week of execution for feasibility
2. Adjust premium thresholds based on actual fills
3. Consider adding sector rotation (oil/chemicals breakout focus)
4. Add profit-taking automation (close at 50% max profit)

---

**Last Updated**: March 5, 2026 @ 5:10 PM MT
**Built By**: Mr. Pinchy + Ryan
**Status**: Ready for testing against live market conditions
