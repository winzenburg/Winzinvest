# Enhanced Emerging Markets Screener

**Status: ✅ BUILT & DEPLOYED** (Feb 28, 2026)

## Overview

Parallel screener that evaluates regional emerging market ETFs using your standard NX technical criteria, with slightly lowered thresholds to accommodate EM volatility patterns.

## Coverage

**Regional Focus (18 ETFs):**
- **South Africa**: EZA
- **Brazil**: EWZ, BRZU
- **China**: FXI, ASHR, CQQQ, GXC, YINN
- **South Korea**: EWY, KORU, KORE
- **Mexico**: EWW, MEXX
- **Broad EM**: EEM, VWO, IEMG, SCHE, VYMI

## NX Criteria (Adjusted for EM)

| Metric | Value | Notes |
|--------|-------|-------|
| Tier 2 Min | 0.05 | Lowered from 0.10 |
| Tier 3 Min | 0.20 | Lowered from 0.30 |
| RS Long Min | 0.40 | Lowered from 0.50 |
| RS Short Max | 0.60 | Raised from 0.50 |
| RVol Min | 0.80 | Lowered from 1.00 |
| Struct Q Min | 0.25 | Lowered from 0.35 |
| HTF Bias Long | 0.35 | Lowered from 0.45 |
| HTF Bias Short | 0.65 | Raised from 0.55 |

**Rationale**: EM markets are more volatile and choppy; relaxed thresholds allow legitimate opportunities to surface without being excluded by overly strict criteria.

## Automation

**Weekly Run Schedule:**
- **Cron Job ID**: `176b1363-8843-4d01-9548-eec7177a8531`
- **Schedule**: Every Friday at 2:00 PM MT
- **Output File**: `~/.openclaw/workspace/trading/watchlist_enhanced_em.json`
- **Log File**: `~/.openclaw/workspace/trading/logs/nx_screener_enhanced_em.log`

## Output Format

```json
{
  "generated_at": "ISO timestamp",
  "screener": "nx_screener_enhanced_em",
  "long_candidates": [...],  // EM ETFs passing long criteria
  "short_candidates": [...], // EM ETFs passing short criteria
  "summary": {
    "long_count": N,
    "short_count": N,
    "total_count": N,
    "symbols_scanned": 18
  }
}
```

## Usage

### Manual Run
```bash
cd ~/.openclaw/workspace/trading
python3 scripts/nx_screener_enhanced_em.py
```

### View Latest Results
```bash
cat ~/.openclaw/workspace/trading/watchlist_enhanced_em.json | jq '.'
```

### Monitor Logs
```bash
tail -50 ~/.openclaw/workspace/trading/logs/nx_screener_enhanced_em.log
```

## Integration with Main Strategy

- **NO overlap with primary screener** (separate universe, separate output)
- **Parallel operation**: Main screener keeps standard thresholds; EM screener has relaxed thresholds
- **Same technical framework**: Both use identical NX metrics, just different evaluation gates
- **No sector bias**: EM ETFs compete on pure technical merit, not macro overlay

## Current Status (as of Feb 28, 2026)

**Last Scan Results:**
- Long candidates: 0
- Short candidates: 4 (China-focused ETFs in weakness: FXI, CQQQ, YINN, GXC)

**Interpretation**: Macro thesis (Gave/Gromen) favors EM, but current technical picture shows EM weakness. Screen will signal when this reverses.

## Next Steps

1. **Monitor weekly**: Fridays at 2 PM, output auto-generated
2. **Alert trigger**: When EM long candidates appear, position for entry
3. **Coordination**: When EM signals align with main screener signals, consider scaling

---

**Built by**: Pinchy AI Partner  
**For**: Ryan Winzenburg  
**Part of**: Comprehensive Trading Strategy Integration (Gave/Gromen Macro Thesis)
