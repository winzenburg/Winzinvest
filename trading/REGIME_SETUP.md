# Regime Monitoring System Setup

## Overview

The regime monitoring system tracks 5 macro indicators and adjusts trading parameters dynamically:

**Indicators (weighted by priority):**
1. VIX structure (+3) - Volatility regime
2. HY OAS (+3) - Credit stress
3. Real yields (+2) - Equity multiple compression
4. NFCI (+1) - Financial conditions
5. ISM Mfg (+1) - Growth signal

**Regime Bands:**
- **0-1**: 🟢 Risk-On (100% size, Z=2.0)
- **2-3**: ⚠️ Neutral (75% size, Z=2.25)
- **4-5**: 🟠 Tightening (50% size, Z=2.5)
- **6+**: 🔴 Defensive (25% size, Z=3.0)

---

## Setup Steps

### 1. Get FRED API Key (Required)

The system pulls macro data from the Federal Reserve Economic Data (FRED) API.

**Steps:**
1. Go to: https://fred.stlouisfed.org/docs/api/api_key.html
2. Click "Request API Key"
3. Sign in or create a free account
4. Copy your API key
5. Add to `trading/.env`:

```bash
# Add this line to trading/.env
FRED_API_KEY=your_api_key_here
```

**Note:** The API is completely free with no rate limits for these data series.

---

### 2. Test Installation

```bash
cd trading

# Test regime monitor (will show Risk-On by default without data)
python3 scripts/regime_monitor.py --brief

# With FRED key configured, this will show real data:
python3 scripts/regime_monitor.py
```

**Expected output:**
```
============================================================
MACRO REGIME CHECK
============================================================

Regime: 🟢 RISK_ON (Score 0/10)

✅ No active alerts

📋 AMS Parameters (RISK_ON):
• zEnter: 2.0
• Position size: 100%
• ATR multiplier: 1.0x
• Cooldown: 3 bars
```

---

### 3. Verify Webhook Integration

The webhook listener now automatically applies regime filters:

```bash
# Check that regime module loads
python3 -c "from scripts.get_regime_params import get_regime_params; print(get_regime_params())"
```

**Expected output:**
```json
{
  "score": 0,
  "regime": "RISK_ON",
  "emoji": "🟢",
  "zEnter": 2.0,
  "sizeMultiplier": 1.0,
  "atrMultiplier": 1.0,
  "cooldown": 3
}
```

---

## How It Works

### Automatic Signal Filtering

When a TradingView alert comes in, the webhook listener:

1. **Fetches current regime** → Gets score and parameters
2. **Applies Z-score threshold** → Requires `abs(zScore) >= regime.zEnter`
3. **Records regime context** → Saves with each trade intent
4. **Shows in approval message** → Telegram message includes regime info

**Example:**
- **Risk-On (score 0-1):** Requires Z ≥ 2.0
- **Tightening (score 4-5):** Requires Z ≥ 2.5
- **Defensive (score 6+):** Requires Z ≥ 3.0

This means **fewer signals pass in defensive regimes** (only the strongest setups).

---

### Position Sizing (Future Enhancement)

The `sizeMultiplier` is recorded with each intent but not yet applied to order execution. To enable:

1. Modify order execution in `webhook_listener.py`
2. Apply: `shares = base_shares * regime['sizeMultiplier']`

---

## Monitoring & Alerts

### Manual Check

```bash
# Full report
python3 scripts/regime_monitor.py

# Brief (no inactive indicators)
python3 scripts/regime_monitor.py --brief

# JSON output
python3 scripts/regime_monitor.py --json

# Check for regime changes
python3 scripts/regime_monitor.py --alert
```

---

### Scheduled Monitoring (via Cron)

Add to your system cron or OpenClaw cron:

```bash
# Every 30 minutes during market hours (9:30 AM - 4:00 PM ET)
*/30 9-16 * * 1-5 cd /path/to/trading && python3 scripts/regime_monitor.py --alert --brief

# Daily full scan at 6:00 PM ET
0 18 * * 1-5 cd /path/to/trading && python3 scripts/regime_monitor.py --alert
```

When regime changes (e.g., Risk-On → Tightening), it will output:

```
🚨 REGIME CHANGE: RISK_ON → TIGHTENING
```

You can pipe this to Telegram or email for notifications.

---

## Data Sources

| Indicator | FRED Series | Update Frequency |
|-----------|-------------|------------------|
| 10Y TIPS (Real Yield) | DFII10 | Daily |
| HY OAS | BAMLH0A0HYM2 | Daily |
| NFCI | NFCI | Weekly (Fridays) |
| ISM Mfg | MANEMP | Monthly (1st business day) |
| VIX / VIX3M | Yahoo Finance | Real-time |

**Latency:**
- VIX data: Real-time (15min delay on free tier)
- FRED data: 1-day lag typical
- NFCI: Published weekly with ~1 week lag

---

## Regime State Files

**Location:** `trading/logs/regime_state.json`

**Contents:**
```json
{
  "currentScore": 3,
  "previousScore": 1,
  "regime": "NEUTRAL",
  "previousRegime": "RISK_ON",
  "lastUpdate": "2026-02-19T08:15:00-07:00",
  "activeAlerts": [
    {
      "indicator": "VIX_STRUCTURE",
      "priority": 1,
      "weight": 3,
      "value": "VX1/VX2 = 1.04"
    }
  ],
  "parameters": {
    "zEnter": 2.25,
    "sizeMultiplier": 0.75,
    "atrMultiplier": 0.9,
    "cooldown": 5
  },
  "history": [
    {
      "timestamp": "2026-02-19T08:15:00",
      "score": 3,
      "regime": "NEUTRAL",
      "event": "RISK_ON → NEUTRAL"
    }
  ]
}
```

---

## Troubleshooting

### "WARNING: fredapi not available"

```bash
pip3 install fredapi
```

### "WARNING: Regime monitoring not available" (in webhook listener)

Make sure `get_regime_params.py` is in `trading/scripts/`:

```bash
ls trading/scripts/get_regime_params.py
```

### No data showing (all indicators inactive)

1. Verify FRED API key is set: `grep FRED_API_KEY trading/.env`
2. Test FRED access: `python3 -c "from fredapi import Fred; f=Fred('YOUR_KEY'); print(f.get_series('DFII10').tail())"`

---

## Next Steps

1. ✅ Get FRED API key
2. ✅ Test `regime_monitor.py`
3. ✅ Verify webhook integration
4. ⏳ Add to morning brief (6 AM)
5. ⏳ Set up cron monitoring
6. ⏳ Enable Telegram alerts on regime changes

---

**Questions?** Check logs in `trading/logs/` or test with `--json` flag for debugging.
