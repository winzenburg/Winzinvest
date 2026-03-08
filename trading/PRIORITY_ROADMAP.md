# Trading System — Priority Roadmap

**One-page view of what to fix/improve first.** Based on TRADING_SETUP_HARDENING_AND_OPTIMIZATION.md, NX_SCREENER_TECHNICAL_SPEC.md implementation status, and your execution-flow spec.

---

## Tier 1: Do first (safety & pipeline)

| # | Item | Why | Effort | Where |
|---|------|-----|--------|--------|
| **1** | **Fix stop/TP for shorts** | Right now stop is below entry and TP above — backwards. Values 0.50/1.00 are wrong; should be 2%/3%. Real risk to P&L. | Small | `execute_candidates.py`: SELL branch, use `stop = entry*(1+0.02)`, `tp = entry*(1-0.03)`; set EXEC_PARAMS to 0.02, 0.03 |
| **2** | **Unify screener → executor** | Screener writes `watchlist_multimode.json`; executor reads `screener_candidates.json` (tier_2/tier_3). They don’t connect. | Small–Medium | Either: (A) executor reads `watchlist_multimode.json` and maps short_candidates to symbol/score/momentum/price, or (B) add a step that writes `screener_candidates.json` from multimode output |
| **3** | **Current shorts sync** | Position filter only works if `current_short_symbols.json` exists; nothing writes it. Screener can re-signal names you’re already short. | Small | Add `sync_current_shorts.py`: connect to IB (or read executions), collect short symbols, write `trading/current_short_symbols.json`. Run before screener or on a schedule |

**Outcome:** Correct risk (stop/TP), a working signal pipeline, and no double-up on existing shorts.

---

## Tier 2: Hardening (risk & sizing)

| # | Item | Why | Effort | Where |
|---|------|-----|--------|--------|
| **4** | **Position size = 100** | Doc says 100 shares; code uses 1. | Trivial | `execute_candidates.py`: set `position_size` to 100 (or read from risk.json) |
| **5** | **Max new shorts per day** | You want “max 10/day”; key exists in risk.json but is null and not enforced. | Small | Set `max_new_shorts_per_day: 10` in risk.json; in execute_candidates, count new shorts today (from executions or state file), skip SELL if at limit |
| **6** | **Sector concentration cap** | Doc: max 30% per sector; executor has no check. You’re tech-heavy. | Medium | Add sector map (symbol → sector), compute notional by sector from IB positions, skip SELL if adding would push any sector > 30% (or load threshold from risk.json) |

**Outcome:** Sizing and daily/sector limits match your rules.

---

## Tier 3: Stops & gates (behavior match to spec)

| # | Item | Why | Effort | Where |
|---|------|-----|--------|--------|
| **7** | **Place stop/TP orders after short fill** | Today you only place the short; no protective stop or take-profit. Spec: 2% stop, 3% TP. | Medium | In execute_candidates after a filled SELL: place StopOrder(BUY, qty, entry*1.02) and LimitOrder(BUY, qty, entry*0.97). Or extract `place_short_with_stops()` and call it from executor |
| **8** | **Single “all gates” check** | Spec has 5 gates (daily limit, sector, gap risk, regime, position size). Executor doesn’t run them together. | Medium | Add `execute_with_all_gates(contract, order)` (or equivalent) that runs all five; call it before placeOrder in execute_candidates. Reuse or port the gate logic from NX_SCREENER_TECHNICAL_SPEC Component 3 |

**Outcome:** Every short has a stop and TP, and no order is placed unless all gates pass.

---

## Tier 4: Reporting & EOD (visibility)

| # | Item | Why | Effort | Where |
|---|------|-----|--------|--------|
| **9** | **Portfolio snapshot** | No single file with current positions and P&L. Spec has `save_portfolio_snapshot()` → `trading/portfolio.json`. | Small | Add script that calls `ib.portfolio()`, builds positions + summary (total short/long, unrealized P&L), writes JSON. Run at EOD or on demand |
| **10** | **Daily P&L report** | Compare today vs yesterday. Spec: `generate_daily_report()` using portfolio.json + portfolio_previous.json. | Small | Add script; depends on #9. Copy portfolio.json → portfolio_previous.json after report, or keep last snapshot by date |
| **11** | **EOD flow (optional)** | Spec: at close, cancel unfilled stop/TP, snapshot, daily report, commit, disconnect. | Medium | Single EOD script or cron that runs snapshot + daily report (and optionally git commit). Cancel-orders logic if you want automation |

**Outcome:** You can see daily P&L and position state without logging into IB.

---

## Tier 5: Screener quality (better signals)

| # | Item | Why | Effort | Where |
|---|------|-----|--------|--------|
| **12** | **Full NX metrics (optional)** | Spec has Composite, 252d RS, ATR-based RVol, Structure, HTF bias. Current code uses 20d RS, log-vol RVol, hl_ratio only. | Large | **Step-by-step:** See **docs/NX_TIER5_FULL_METRICS_STEPS.md** (8 steps: helpers → Composite → 252d RS → ATR RVol → Structure → thresholds in short_opportunities → optional HTF → optional screen_for_shorts). Spec: NX_SCREENER_TECHNICAL_SPEC.md |
| **13** | **Regime / gap / retry** ✅ | Regime filter (no short in uptrend); gap window (no trades near close); place_order_with_retry for options. | Small–Medium | Done: regime in execution_gates; gap in check_gap_risk_window; place_order_with_retry in direct_premium_executor (3 retries, 2s; no retry on security definition / buying power / duplicate). |

**Outcome:** Short list aligns with your full NX spec; fewer bad entries and more robust execution.

---

## Suggested order (next 1–2 weeks)

1. **Day 1:** #1 (stop/TP fix), #4 (position size 100).  
2. **Day 2:** #2 (pipeline: executor reads watchlist_multimode or converter).  
3. **Day 3:** #3 (sync_current_shorts.py + run it before screener).  
4. **Day 4:** #5 (max new shorts/day in risk.json + executor).  
5. **Day 5:** #7 (place stop + TP after short fill).  
6. **When you can:** #6 (sector cap), #8 (all gates), #9–11 (snapshot + daily report + EOD).

Tiers 4 and 5 can move in parallel or after Tier 2–3 depending on how much you want reporting vs. gate/screener improvements first.

---

## Quick reference

| Tier | Focus |
|------|--------|
| **1** | Safety & pipeline (stop/TP, screener↔executor, current shorts sync) |
| **2** | Hardening (position size, max new/day, sector cap) |
| **3** | Stops & gates (stop/TP orders, execute_with_all_gates) |
| **4** | Reporting & EOD (portfolio snapshot, daily P&L, EOD script) |
| **5** | Screener quality (full NX metrics, regime, gap, retry) |
