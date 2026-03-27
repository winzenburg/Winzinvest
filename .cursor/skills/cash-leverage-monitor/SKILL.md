---
name: cash-leverage-monitor
description: Monitor and tune the cash & leverage auto-deploy system. Use when the user asks about cash drag, leverage utilization, idle cash thresholds, premium selling automation, or tuning cash_monitor.py settings.
---

# Cash & Leverage Monitor

The `cash_monitor.py` script runs every 30 minutes during market hours via the scheduler. It detects idle cash and under-leveraging, then automatically triggers premium selling or equity deployment.

## Architecture

```
scheduler.py (every 30 min, 7:45–13:30 MT)
  └─ cash_monitor.py
       ├─ Condition 1: Cash > threshold → nx_screener_production.py → auto_options_executor.py
       └─ Condition 2: Leverage < floor → screeners → execute_longs.py → execute_dual_mode.py
```

## Configuration (risk.json → `cash_monitor`)

| Key | Current value | Description |
|---|---|---|
| `cash_idle_threshold_pct` | 0.15 | Fire premium selling when cash > 15% of NLV |
| `leverage_target_pct` | **2.50** | Target gross leverage (GPV / NLV) — Portfolio Margin account |
| `leverage_floor_pct` | **2.00** | Alert/deploy when leverage drops below 2.0× |
| `min_premium_trigger_usd` | **20000** | Only fire if idle cash above this dollar amount |
| `cooldown_minutes` | 90 | Don't re-trigger the same action within this window |

To change thresholds, edit `trading/risk.json`:
```json
{
  "cash_monitor": {
    "cash_idle_threshold_pct": 0.15,
    "leverage_target_pct": 2.50,
    "leverage_floor_pct": 2.00,
    "min_premium_trigger_usd": 20000,
    "cooldown_minutes": 90
  }
}
```

## Trigger Conditions

### Condition 1 — Cash Drag (sell premium)

All three must be true:
1. `cash / NLV > cash_idle_threshold_pct`
2. `idle_cash > min_premium_trigger_usd` (where idle = cash − NLV × threshold)
3. Not within cooldown window

**Actions:** Run production screener → run auto_options_executor

### Condition 2 — Leverage Gap (deploy equity)

All four must be true:
1. `GPV / NLV < leverage_floor_pct`
2. Leverage gap > 10% (at least 0.10× below target)
3. Available funds > $50k
4. Not within cooldown window

**Actions:** Run longs screener → production screener → execute_longs → execute_dual_mode

## State File

`trading/config/cash_monitor_state.json` — tracks last trigger times:
```json
{
  "last_premium": "2026-03-12T08:57:03",
  "last_equity": "2026-03-11T10:15:22"
}
```

## Related Systems

The cash monitor works alongside two other automated options systems:
- **`options_position_manager.py`** (clientId 194) — manages existing positions (profit-take, roll, stop-loss)
- **`daily_options_email.py`** (clientId 197) — sends styled HTML report at 4 PM ET via Resend API

## Diagnostics

Run manually to check current state:
```bash
cd trading && python3 scripts/cash_monitor.py
```

Quick account check without triggering actions:
```python
from ib_insync import IB
ib = IB()
ib.connect('127.0.0.1', 4002, clientId=195, timeout=10)
vals = {v.tag: float(v.value) for v in ib.accountSummary()
        if v.tag in {"NetLiquidation","TotalCashValue","GrossPositionValue"}}
nlv, cash, gpv = vals["NetLiquidation"], vals["TotalCashValue"], vals["GrossPositionValue"]
print(f"Leverage: {gpv/nlv:.2f}x  Cash: {cash/nlv:.1%}  Idle: ${cash - nlv*0.15:,.0f}")
ib.disconnect()
```

## Common Tuning Scenarios

| Goal | Change |
|---|---|
| Deploy cash more aggressively | Lower `cash_idle_threshold_pct` to 0.10 |
| Be more conservative with leverage | Raise `leverage_floor_pct` to 2.20 |
| Reduce how often it fires | Increase `cooldown_minutes` to 120 |
| Require more idle cash before acting | Raise `min_premium_trigger_usd` to 75000 |
