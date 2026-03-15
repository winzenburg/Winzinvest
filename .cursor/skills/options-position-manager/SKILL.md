---
name: options-position-manager
description: Manage active options positions — profit-taking, stop-losses, rolling, and expiry handling. Use when the user asks about managing options, rolling positions, closing options early, setting profit targets, or adjusting options management thresholds.
---

# Options Position Manager

`options_position_manager.py` actively manages all short options (covered calls and CSPs) every 30 minutes during market hours.

## What It Does

1. **Profit-take** at 50% premium decay → buy-to-close
2. **Stop-loss** at 2× collected premium → buy-to-close
3. **Roll** at ≤7 DTE or when ITM ≥2% → close + reopen at ~35 DTE, 10% OTM
4. **Expiry close** at ≤1 DTE → force buy-to-close

## Configuration (`risk.json` → `options_management`)

| Key | Default | What it controls |
|---|---|---|
| `profit_take_pct` | 0.50 | Close when premium decayed this much |
| `stop_loss_multiplier` | 2.0 | Close when loss exceeds this × premium |
| `roll_dte_threshold` | 7 | Roll when DTE falls to this |
| `roll_itm_threshold_pct` | -2.0 | Roll when position goes this % ITM |
| `roll_target_dte` | 35 | New position targets this DTE |
| `roll_target_otm_pct` | 10.0 | New position targets this % OTM |
| `max_rolls_per_day` | 5 | Safety cap on daily rolls |

## Common Tuning Scenarios

| Goal | Change |
|---|---|
| Take profits earlier | Lower `profit_take_pct` to 0.40 |
| Let winners run longer | Raise `profit_take_pct` to 0.65 |
| Tighter stop-loss | Lower `stop_loss_multiplier` to 1.5 |
| Roll earlier before expiry | Raise `roll_dte_threshold` to 10 or 14 |
| More conservative rolls | Raise `roll_target_otm_pct` to 12 or 15 |

## Manual Commands

```bash
# Dry run — see what actions it would take
python3 scripts/options_position_manager.py --dry-run

# Live execution
python3 scripts/options_position_manager.py
```

## Architecture

```
scheduler.py (every 30 min, 10:00–15:30 ET)
  └─ options_position_manager.py (clientId 194)
       ├─ Fetch short option positions from IB
       ├─ Fetch spot prices via yfinance
       ├─ Analyze each position (DTE, moneyness, P&L)
       ├─ Fetch live option mid-prices for profit/stop checks
       └─ Execute: CLOSE, ROLL, or HOLD
            └─ Telegram notification on every action
```

## Notifications

Every close and roll sends a Telegram message. Format:
- `✅ Closed MRNA C60 20260417: Profit-take: 52% decay`
- `🔄 Rolled MRVL C96 20260402 → C98 20260417`
- `⚠️ Roll partial: closed X, new leg not found`
