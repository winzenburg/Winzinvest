---
name: options-positions-report
description: Generate a markdown report of all current options positions from Interactive Brokers. Use when the user asks for an options report, positions summary, premium income breakdown, or compliance check on options holdings.
---

# Options Positions Report

Generate a comprehensive markdown report at `trading/docs/OPTIONS_POSITIONS.md` from live IB data.

## Workflow

1. **Connect to IB** (clientId 196–199, port 4002)
2. **Fetch all option positions** from `ib.positions()` where `secType == "OPT"` and `position != 0`
3. **Fetch account summary** — NLV, cash, GPV
4. **Fetch spot prices** via `yfinance` (NOT IB market data — avoids Error 10197)
5. **Enrich each position** with calculated fields
6. **Write the report** to `trading/docs/OPTIONS_POSITIONS.md`

## Calculated Fields per Position

| Field | Formula |
|---|---|
| DTE | `(expiry_date - today).days` |
| Moneyness | Calls: `(strike - spot) / spot × 100` · Puts: `(spot - strike) / spot × 100` |
| OTM/ITM | Positive = OTM, negative = ITM |
| Premium per contract | `abs(pos.avgCost)` — already per-contract from IB |
| Total premium | `premium_per_contract × abs(qty)` |
| Assignment risk (CSPs) | `abs(qty) × strike × 100` |

**IMPORTANT:** `pos.avgCost` for options is already multiplied by the 100 contract multiplier. Do NOT divide by 100 again.

## Report Sections

1. **Portfolio Summary** — NLV, cash, leverage, total premium, annual run-rate
2. **Covered Calls table** — sorted by symbol, with compliance flags
3. **CSPs table** — sorted by symbol, with assignment risk and compliance flags
4. **Long Options** — protective puts, expiring options
5. **Risk & Compliance** — ITM check, DTE check, OTM% flags, cash coverage
6. **Expiration Calendar** — grouped by expiry date
7. **Income Projection** — cycle / monthly / quarterly / annual run-rate
8. **Action Items** — prioritized by severity (High / Med / Low)

## Compliance Rules

Flag with ⚠️ or 🔴 per `trading-options-strategy` rule:
- ✅ ≥10% OTM
- ⚠️ < 10% OTM
- 🔴 ITM, naked, or DTE outside 21–45

## Example Output Format

```markdown
| Symbol | Strike | Expiry | DTE | Spot | Moneyness | Contracts | $/Contract | Total Premium | Compliance |
|---|---|---|---|---|---|---|---|---|---|
| **MRNA** | $60 C | Apr 17, 2026 | 36d | $53.80 | OTM 11.5% | ×16 | $277.44 | $4,439 | ✅ |
```
