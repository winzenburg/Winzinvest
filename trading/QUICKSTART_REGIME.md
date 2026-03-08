# Regime Monitoring - Quick Start

**You're all set!** The system is integrated and automated. Here's what to do next.

---

## 1️⃣ Get FRED API Key (5 minutes)

**Why:** Pulls real macro data (real yields, credit spreads, ISM, NFCI)

**Steps:**
1. Go to: **https://fred.stlouisfed.org/docs/api/api_key.html**
2. Click "Request API Key"
3. Sign in or create free account
4. Copy your API key
5. Add to `trading/.env`:

```bash
# Add this line to trading/.env
FRED_API_KEY=your_api_key_here
```

**Note:** Completely free, no rate limits for your usage.

---

## 2️⃣ Test the System (2 minutes)

```bash
cd trading

# Test regime monitor
python3 scripts/regime_monitor.py --brief

# Expected output:
# ============================================================
# MACRO REGIME CHECK
# ============================================================
#
# Regime: 🟢 RISK_ON (Score 0/10)
#
# ✅ No active alerts
#
# 📋 AMS Parameters (RISK_ON):
# • zEnter: 2.0
# • Position size: 100%
# • ATR multiplier: 1.0x
# • Cooldown: 3 bars
```

```bash
# Test webhook integration
python3 scripts/get_regime_params.py

# Expected output:
# {
#   "score": 0,
#   "regime": "RISK_ON",
#   "zEnter": 2.0,
#   "sizeMultiplier": 1.0,
#   ...
# }
```

✅ If both commands run successfully, you're ready!

---

## 3️⃣ What Happens Automatically

### Tomorrow Morning (6:00 AM)
Your morning brief will include:
- **Macro Regime Check** (score, alerts, AMS parameters)
- Weather
- Market pre-open (SPY/QQQ)
- Today's priorities

### During Trading (Every 30 min, 7:30 AM - 2:00 PM MT)
- System checks for regime changes
- **Silent if stable**
- **Alerts immediately if regime shifts**

### End of Day (6:00 PM)
- Daily regime summary
- Any regime changes today
- Current AMS parameters

### Every Sunday (6:00 PM)
- Weekly validation includes regime analysis
- How regime affected trade selection
- Signals rejected due to regime filters

---

## 4️⃣ How It Affects Your Trading

### Signal Filtering (Automatic)

**TradingView sends alert** → **Webhook checks regime** → **Applies Z-threshold**

| Regime | Score | Z Threshold | Effect |
|--------|-------|-------------|--------|
| 🟢 Risk-On | 0-1 | ≥ 2.0 | Standard filtering |
| ⚠️ Neutral | 2-3 | ≥ 2.25 | Slightly stricter |
| 🟠 Tightening | 4-5 | ≥ 2.5 | Much stricter |
| 🔴 Defensive | 6+ | ≥ 3.0 | Only strongest signals |

**Example:**
- Signal arrives: Z-score = 2.3
- Current regime: Tightening (Z threshold = 2.5)
- **Result:** Signal rejected ("zScore 2.3 < 2.5 regime threshold")

### Telegram Approval Messages

Now include regime context:
```
🚨 TRADE SIGNAL: AAPL (LONG)

📊 Signal:
├─ Entry: $150.25
├─ Z-Score: 2.8
└─ RS: 0.75

💰 Position:
├─ Qty: 1 (CANARY MODE)
└─ Regime: 🟠 TIGHTENING (50% sizing, score 4/10)

Approve this trade?
```

---

## 5️⃣ Manual Commands

**Check regime anytime:**
```bash
cd trading
python3 scripts/regime_monitor.py --brief
```

**Send test Telegram alert:**
```bash
python3 scripts/regime_alert.py --force
```

**View current parameters:**
```bash
python3 scripts/get_regime_params.py
```

---

## 6️⃣ What to Expect

### First Week
- System starts in Risk-On (score 0) until data loads
- After FRED key added, will track real indicators
- Watch for regime shifts during market hours
- Review weekly validation on Sunday

### First Regime Change
You'll get an alert like:
```
🚨 REGIME ALERT
RISK_ON → 🟠 TIGHTENING
Score: 4/10

Active Alerts:
#1 VIX Backwardation: VX1/VX2 = 1.04 (+3)
#5 ISM: 48.2 (below 50) (+1)

AMS Adjustments:
• Z-score threshold: 2.5
• Position size: 50%
• ATR multiplier: 0.8x
• Cooldown: 8 bars
```

**What this means:**
- New signals need Z ≥ 2.5 (was 2.0)
- Weaker signals will be auto-rejected
- You'll see regime context in every approval request

---

## 7️⃣ Validation Checklist

After 1 week, you should see:

- [ ] Morning brief includes regime check
- [ ] At least one regime scan ran during market hours
- [ ] Daily regime summary delivered at 6 PM
- [ ] Trade intents include regime context
- [ ] Telegram messages show regime info
- [ ] Some signals rejected with "regime threshold" reason (if any weak signals fired)

---

## 🎯 That's It!

**System is live and automated.**

**Next actions:**
1. ✅ Get FRED API key (5 min)
2. ✅ Test both commands above (2 min)
3. ✅ Wait for tomorrow's morning brief (automatic)
4. ✅ Review regime analysis in Sunday's validation checkpoint

---

## 📚 Full Documentation

- **REGIME_SETUP.md** - Detailed setup guide
- **BUILD_COMPLETE.md** - Technical build summary
- **REGIME_MONITORING_COMPLETE.md** - Full integration details
- **QUICKSTART_REGIME.md** - This file

---

**Questions?** Test the commands above. If they run without errors, you're good to go!
