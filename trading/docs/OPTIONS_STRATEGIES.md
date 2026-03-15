# Options Strategies — Mission Control

> **Last updated:** March 2026  
> **Script:** `trading/scripts/auto_options_executor.py`  
> **Config:** `trading/risk.json`

---

## Overview

The system runs four options strategies as a premium-income and tail-risk layer on top of the equity long/short core. Three strategies **collect premium** (Covered Calls, Cash-Secured Puts, Iron Condors) and one **buys protection** (Protective Puts). All strategies share a unified entry pipeline with earnings blackouts, economic calendar checks, IV rank filtering, delta-targeted strikes, and dynamic position sizing.

---

## Portfolio-Level Limits (from `risk.json`)

| Parameter | Value |
|---|---|
| Max options trades per day | 10 |
| Max options trades per month | 50 |
| Max single option allocation (% of NLV) | 3% |
| Max total options exposure (% of NLV) | 8% |
| Max open Iron Condors simultaneously | 4 |
| Monthly Protective Put budget cap | $15,000 |

---

## Shared Entry Gates (all strategies)

Before any option is scanned or executed, the system checks:

1. **Economic Calendar Blackout** — `economic_calendar.py` blocks all options activity on high-impact macro days (FOMC, CPI, NFP, etc.).
2. **IV Rank Filter** — `iv_rank.py` requires IV Rank ≥ **0.45** (45th percentile of the trailing 52-week IV range) before selling premium. Fetched from IBKR first, yfinance HV proxy as fallback.
3. **Earnings Blackout** — `earnings_calendar.py` skips any ticker with earnings within **7 days**.
4. **Sector Concentration** — `sector_concentration_manager.py` rejects positions that would push a single sector over its cap.
5. **Regime Filter** — Each strategy has its own regime gate (see per-strategy details below). Regime is detected live via `regime_detector.py`.

---

## Strategy 1 — Covered Calls

**Goal:** Generate income on existing profitable long stock positions.

### Entry Criteria

| Check | Requirement |
|---|---|
| Position size | Must hold ≥ 100 shares of the underlying |
| Gain from entry | ≥ **0.5%** above average cost |
| IV Rank | ≥ 0.45 |
| Earnings blackout | Not within 7 days |

### Strike & Expiration

| Parameter | Value |
|---|---|
| Target delta | **0.20** (20 delta, ~80% OTM probability) |
| Fallback strike (no chain data) | Spot × 1.10 (+10% OTM) |
| Minimum room to strike | ≥ **4%** above current price |
| Strike rounding | $1 increments (price < $100), $2.50 (> $100), $5 (> $200) |
| DTE | **~35 days** (next monthly expiration / 3rd Friday) |

### Minimum Premium

| Parameter | Value |
|---|---|
| Min premium % of spot | **0.8%** |
| Estimated premium (fallback) | 1.5% of spot |

### Position Sizing

Contracts = position shares ÷ 100, capped by:

```
max_notional = NLV × 3% × composite_multiplier
adjusted_qty = min(position_contracts, floor(max_notional / (strike × 100)))
```

`composite_multiplier` is produced by `dynamic_position_sizing.py` and scales down near earnings, in high VIX environments, or after drawdowns.

### Regime Gate

No regime restriction — covered calls can be sold in any regime (you already own the stock).

---

## Strategy 2 — Cash-Secured Puts (CSPs)

**Goal:** Collect premium on stocks you want to own at a lower price. Acts as a discounted buy-limit order with income.

### Entry Criteria

| Check | Requirement |
|---|---|
| Candidate source | Long watchlist (`watchlist_longs.json`) + `sector_strength` / `premium_selling` modes in multimode watchlist |
| Pullback from 20-day high | Between **1.5% and 12%** |
| Near support | Within **3%** of 50-day EMA |
| Volume ratio | < 2.0× (not panic selling) |
| IV Rank | ≥ 0.45 |
| Earnings blackout | Not within 7 days |
| Regime | **Skipped entirely** in `STRONG_DOWNTREND` or `UNFAVORABLE` (assignment risk too high) |

### Strike & Expiration

| Parameter | Value |
|---|---|
| Target delta | **0.25** (25 delta, ~75% OTM probability) |
| Fallback strike (no chain data) | EMA50 × 0.98 |
| Max assignment risk per contract | **$50,000** (strike × 100 ≤ $50K) |
| DTE | **~35 days** |

### Minimum Premium

| Parameter | Value |
|---|---|
| Min premium % of spot | **0.8%** |

### Position Sizing

```
max_notional = NLV × 3% × composite_multiplier
qty = floor(max_notional / (strike × 100))   # minimum 1 contract
```

---

## Strategy 3 — Iron Condors

**Goal:** Sell a range of prices on SPY/QQQ when volatility is elevated but direction is unclear. Profit if price stays between the short strikes through expiration.

### Eligible Underlyings

`SPY` and `QQQ` only.

### Structure

```
Short OTM Put  @  spot × 0.90   ← sell this (collect premium)
Long  OTM Put  @  spot × 0.85   ← buy this  (limit downside wing)
Short OTM Call @  spot × 1.10   ← sell this (collect premium)
Long  OTM Call @  spot × 1.15   ← buy this  (limit upside wing)
```

| Parameter | Value |
|---|---|
| Put short strike | Spot × 0.90 (-10% OTM) |
| Put wing | Spot × 0.85 (-15% OTM) |
| Call short strike | Spot × 1.10 (+10% OTM) |
| Call wing | Spot × 1.15 (+15% OTM) |
| Wing width | 5% of spot per side |
| Max risk per condor | (put_strike − put_wing) × 100 |
| Target credit | ~30% of max risk |
| Min credit threshold | $50 |
| DTE | **~35 days** |
| Max open condors | **4** simultaneously |

### Regime Gate

| Regime | Iron Condor Eligible? |
|---|---|
| `CHOPPY` | ✅ Yes |
| `MIXED` | ✅ Yes |
| `STRONG_UPTREND` | ✅ Yes, **only if IV Rank > 30%** on SPY |
| `STRONG_DOWNTREND` | ❌ No |
| `UNFAVORABLE` | ❌ No |

> **Note:** Iron Condors are currently identified and logged but not auto-executed. They are printed to the log as candidates for manual or future automated execution.

---

## Strategy 4 — Protective Puts

**Goal:** Tail-risk hedge. Buy SPY puts to limit portfolio downside during adverse regimes.

### Structure

| Parameter | Value |
|---|---|
| Underlying | `SPY` only |
| Strike | Spot × 0.93 (-7% OTM) |
| DTE | **~30 days** |
| Estimated cost | ~2% of SPY price × 100 per contract |
| Max open protective puts | **2** at a time |

### Regime Gate

Only enters when regime is:
- `MIXED`
- `UNFAVORABLE`
- `STRONG_DOWNTREND`

### Budget Limit

```
monthly_budget = min($15,000, NLV × 0.75%)
```

A new put is only purchased if `estimated_cost ≤ monthly_budget` and fewer than 2 protective puts are already open.

> **Note:** Protective Puts are currently identified and logged but not auto-executed. Execute manually or enable in `auto_options_executor.py`.

---

## Execution Flow

```
Start
  │
  ├─ Economic calendar blackout? → EXIT
  ├─ Daily limit reached (10/day)? → EXIT
  ├─ Monthly limit reached (50/month)? → EXIT
  │
  ├─ Connect to IB Gateway (Client ID 105, port 4002)
  ├─ Fetch account NLV
  ├─ Detect market regime
  │
  ├─ Scan Covered Calls  (from live IB positions)
  ├─ Scan CSPs           (from long watchlist + multimode watchlist)
  ├─ Scan Iron Condors   (SPY/QQQ, regime-gated)
  ├─ Scan Protective Puts (SPY, regime-gated)
  │
  ├─ Filter CC + CSP candidates:
  │     → Earnings blackout check (skip if < 7 days)
  │     → Sector concentration check
  │
  ├─ For each valid CC/CSP candidate (up to daily remaining limit):
  │     → Calculate composite position size (VIX, earnings, drawdown)
  │     → Fetch live bid/ask from IB (fallback to last → close → estimate)
  │     → Verify premium ≥ 0.8%
  │     → Place SELL market order
  │     → Log to logs/options_TIMESTAMP.json
  │     → Send Telegram notification
  │
  └─ Report IC + PP candidates to log (not auto-executed)
```

---

## Delta & Strike Selection

The `delta_strike_selector.py` module queries the live IB option chain and finds the strike whose model delta is closest to the target:

| Strategy | Target Delta |
|---|---|
| Covered Call | **0.20** (20Δ) |
| Cash-Secured Put | **0.25** (25Δ) |

If IB chain data is unavailable, falls back to:
- Covered Call: spot × 1.10
- CSP: EMA50 × 0.98

---

## IV Rank Calculation

`iv_rank.py` calculates:

```
IV Rank = (current_IV − 52w_low_IV) / (52w_high_IV − 52w_low_IV)
```

- **Source priority:** IBKR generic tick 106 → yfinance historical volatility proxy
- **Minimum threshold:** IV Rank ≥ **0.45** to sell premium
- **Rationale:** Selling when IV is elevated (above median) means collecting richer premium and benefiting from mean-reversion in volatility

---

## Monthly Target Tracking

`check_monthly_options_target.py` runs on the last Friday of each month:

| Trades Deployed | Status |
|---|---|
| ≥ 4 | Target exceeded |
| 2–3 | Minimum met |
| < 2 | Below minimum — alert sent |

Telegram alert is sent with monthly summary and, in the last week, a nudge to force-deploy if below minimum.

---

## Key Files

| File | Purpose |
|---|---|
| `scripts/auto_options_executor.py` | Main executor — all 4 strategies |
| `scripts/options_monitor.py` | Passive monitor + Telegram alerts (legacy) |
| `scripts/check_monthly_options_target.py` | Monthly cadence checker |
| `scripts/delta_strike_selector.py` | IB chain delta targeting |
| `scripts/iv_rank.py` | IV rank fetch (IBKR + yfinance) |
| `scripts/economic_calendar.py` | Macro blackout dates |
| `scripts/earnings_calendar.py` | Per-ticker earnings blackout |
| `scripts/sector_concentration_manager.py` | Sector cap enforcement |
| `scripts/dynamic_position_sizing.py` | Composite size multiplier |
| `risk.json` | All limit parameters |
| `logs/options_*.json` | Per-trade execution logs |
