# Trading Setup — Hardening & Optimization Analysis

**Date:** March 2026  
**Scope:** Your technical architecture doc vs. actual codebase (NX screener, execute_candidates, direct_premium_executor, risk_config, position_filter).

---

## Overall structure

```
[Market Data] → [Screeners] → [Signal Filter] → [Risk Gates] → [IB Gateway] → [Positions]
```

- **Market Data:** yfinance, IB positions, regime/VIX.
- **Screeners:** NX multimode (sector_strength, premium_selling, short_opportunities) → watchlist_multimode.json.
- **Signal Filter:** Position filter (exclude current shorts), slots-left trim, optional strategy allowlist (options).
- **Risk Gates:** Max shorts, daily loss limit, options daily/monthly caps, (to add: sector cap, max new shorts/day).
- **IB Gateway:** ib_insync execution (paper DU4661622).
- **Positions:** Live shorts/options; sync back into current_short_symbols.json for next cycle.

---

## Executive Summary

| Priority | Area | Finding | Recommendation |
|----------|------|---------|----------------|
| **High** | Stop/TP for shorts | Formula is inverted and % values wrong | Fix direction and use 2% / 3% per your doc |
| **High** | Candidate pipeline | Executor reads `screener_candidates.json` (tier_2/tier_3); screener writes `watchlist_multimode.json` | Unify: executor reads multimode short lists or add converter |
| **High** | Current shorts sync | `current_short_symbols.json` is never written by any script | Add sync step (cron or post-execution) so position filter works |
| **Medium** | Sector concentration | Doc: max 30%; execute_candidates has no sector check | Add sector cap in executor or risk_config |
| **Medium** | Max new shorts/day | risk.json has key but null; doc says "max 10/day" | Set and enforce in execute_candidates |
| **Medium** | Position size | EXEC_PARAMS uses 1 share; doc says 100 | Move to risk.json or constant = 100 |
| **Low** | Notional cap | risk.json has max_short_notional_* (null) | Implement when IB position data available |
| **Low** | Regime filter | Doc: no new shorts in uptrend; executor doesn’t check | Optional regime gate before SELL |

---

## 1. Critical: Stop Loss / Take Profit for Shorts

**Your doc:** Stop 2% above entry, take profit 3% below entry (equity shorts).

**Current code** (`execute_candidates.py`):

```python
stop_price = entry_price * (1 - EXEC_PARAMS['stop_loss_pct'])   # 1 - 0.50 = 0.5 → 50% below
profit_price = entry_price * (1 + EXEC_PARAMS['take_profit_pct']) # 1 + 1.00 = 2 → 100% above
```

For a **short**, loss happens when price goes **up**, profit when price goes **down**. So:

- **Stop loss** (exit to cap loss) should be **above** entry: `entry * (1 + 0.02)`.
- **Take profit** should be **below** entry: `entry * (1 - 0.03)`.

Current logic assigns the opposite: `stop_price` is below entry and `profit_price` is above entry. So the **variable names and formulas are backwards for SELL**, and the percentages (0.50 / 1.00) don’t match your 2% / 3% spec.

**Recommendation:**

- For `action == 'SELL'`:
  - `stop_price = entry_price * (1 + stop_loss_pct)`  e.g. 2% above
  - `profit_price = entry_price * (1 - take_profit_pct)`  e.g. 3% below
- Set `stop_loss_pct = 0.02`, `take_profit_pct = 0.03` (or load from risk.json).
- For BUY, keep current convention (stop below, profit above) if you use the same executor for longs later.

---

## 2. Candidate File Mismatch (Screener ↔ Executor)

**Screener** (`nx_screener_production.py`):

- Writes **`watchlist_multimode.json`** with structure:
  - `modes.short_opportunities.short`, `modes.premium_selling.short`, etc.
  - Each candidate has `symbol`, `recent_return`, `rs_pct`, `reason`, etc.

**Executor** (`execute_candidates.py`):

- Reads **`screener_candidates.json`** (path: `WORKSPACE / "trading" / "screener_candidates.json"`).
- Expects `tier_2` and `tier_3` and fields: `symbol`, `score`, `momentum`, `price`.

So the production NX screener does **not** feed the executor unless something else writes `screener_candidates.json` (e.g. another script or OpenClaw). If only the multimode screener runs, the executor has no input.

**Recommendation (pick one):**

- **Option A:** Add a small step that builds `screener_candidates.json` from `watchlist_multimode.json`: e.g. merge short lists from `short_opportunities` and `premium_selling`, map `symbol`/`recent_return`/`rs_pct` to `symbol`/`score`/`momentum`/`price` (with sensible defaults for missing fields), and write tier_2/tier_3.
- **Option B:** Change `execute_candidates.py` to read `watchlist_multimode.json`, iterate `results["modes"]["short_opportunities"]["short"]` (and optionally premium_selling short), and map each item to the candidate shape the executor expects (`symbol`, `score`, `momentum`, `price`).

Either way, document the single pipeline (screener output → executor input) so it’s clear which file is the source of truth.

---

## 3. Current Shorts: Sync Step Missing

Position filtering is **implemented** in code:

- **Screener:** Uses `load_current_short_symbols(WORKSPACE)` (file only, no IB) and excludes those symbols from short lists.
- **Executor:** Uses `load_current_short_symbols(TRADING_DIR, self.ib)` (file + IB) and skips SELL if symbol already short.

But **no script in the repo writes `current_short_symbols.json`**. The schema is documented in `position_filter.py`; the file must be maintained by an external “sync positions” step. If that never runs, the file is missing and the screener excludes nothing (executor still has defense via IB when connected).

**Recommendation:**

- Add a small script, e.g. **`sync_current_shorts.py`**, that:
  - Connects to IB (or reads from `executions.json` / execution log if you don’t want IB at sync time).
  - Collects all symbols with short stock positions (from IB or from “SELL” executions that weren’t closed).
  - Writes `trading/current_short_symbols.json` with `{"symbols": [...], "updated_at": "..."}`.
- Run it on a schedule (e.g. before the screener, or after market close) or from a cron that already runs in OpenClaw workspace. That way the screener’s exclude list stays in sync with reality and you avoid re-signaling names like YINN.

---

## 4. Sector Concentration (Doc vs Code)

**Doc:** Max 30% in one sector; you note tech is ~45%.

**Code:**

- `execute_candidates.py`: No sector logic.
- `auto_options_executor.py`: Uses `sector_concentration_manager` (optional import) for options only.

So equity shorts can concentrate in one sector with no cap.

**Recommendation:**

- Add a **sector cap** to the equity-shorts path:
  - Either in **risk.json** (e.g. `max_sector_pct: 0.30`) and a getter in `risk_config.py`, or as a constant.
  - In `execute_candidates.run()`, before the execution loop: get current positions from IB (or from a positions file), compute sector weights, and if adding this symbol would push any sector over the cap, skip and log “Skipping {symbol}: would exceed sector concentration.”
- Reuse sector mapping from `sector_concentration_manager` if it’s in the same environment; otherwise a simple symbol → sector map (e.g. from a small JSON or hardcoded for your universe) is enough for a first version.

---

## 5. Max New Shorts Per Day

**Doc:** Circuit breaker “max 10 positions/day.”

**Code:** `risk.json` has `max_new_shorts_per_day: null`; `risk_config.get_max_new_shorts_per_day()` returns `None` when null, and `execute_candidates` does not enforce a daily count.

**Recommendation:**

- Set **`max_new_shorts_per_day: 10`** (or your preferred number) in `risk.json` under `equity_shorts`.
- In `execute_candidates.run()`: at start, count “new shorts opened today” (e.g. from `executions.json` or a small `trading/logs/daily_shorts.json` with `date` + list of symbols). In `execute_candidate()`, when `action == 'SELL'`, if `new_shorts_today >= max_new_shorts_per_day`, skip and append a SKIPPED entry. On each successful SELL, increment the run-local counter and optionally append to the daily state file so the next run sees it.

---

## 6. Position Size and Risk Config

**Doc:** 100 shares per signal.

**Code:** `EXEC_PARAMS['position_size'] = 1`.

**Recommendation:**

- Use **100** for production (or make it configurable). Options:
  - Add to **risk.json** (e.g. `equity_shorts.default_position_size: 100`) and a getter in `risk_config.py`, and have `execute_candidates` read it with fallback 100; or
  - Change the constant in `execute_candidates.py` to 100 and document it.
- Optionally move **stop_loss_pct** and **take_profit_pct** into risk.json so you can tune 2% / 3% without code edits.

---

## 7. Notional Cap (Optional Follow-Up)

**Doc:** Max notional short $500K (or % of equity).

**Code:** `risk.json` has `max_short_notional_dollars` and `max_short_notional_pct_of_equity` (null). Executor does not enforce them.

**Recommendation:**

- When you’re ready: in `execute_candidates.run()`, fetch positions from IB (you already have `account_equity`), compute current short notional (sum of `|position| * price` for short stocks). Before placing a SELL, estimate new notional; if it would exceed `get_max_short_notional_dollars()` or `account_equity * get_max_short_notional_pct_of_equity()`, skip and log. This requires reliable position/price data from IB in the same run.

---

## 8. Regime Filter (Optional)

**Doc:** “Regime filter: don’t short in uptrend.”

**Code:** No regime check in `execute_candidates`. `auto_options_executor` uses `RegimeDetector` for options only.

**Recommendation:**

- Optional: before executing any SELL, call a small regime check (e.g. SPY trend or VIX/term-structure). If regime is “bullish” or “no short”, skip all new shorts and log “Regime filter: no new shorts in current regime.” You can reuse logic from `regime_detector` if it’s in the same environment; otherwise a simple SPY vs 50/200 MA check is enough to start.

---

## 9. Options Path (Already Addressed)

From your earlier work:

- **direct_premium_executor:** Rejection detail logging, listed expirations, `qualifyContracts`, and `ALLOWED_STRATEGIES` are in place.
- **risk_config:** Options limits (max per day/month) are in risk.json and enforced in direct and auto_options executors.
- **Account level:** You moved to Level 3; if rejections persist, the new rejection_detail field in the execution log will show whether it’s still permissions or something else.

No further change required here unless you add a webhook path, in which case that path should use the same risk_config options limits.

---

## 10. EM Shorts (Strategy 3)

You mentioned EM uses “same NX thresholds but lowered” and a separate universe. The current `nx_screener_production.py` has three modes (sector_strength, premium_selling, short_opportunities); EM is not a separate mode. If EM is driven by another screener or manual list, ensure:

- That output is also filtered by `load_current_short_symbols` (and slots_left if it goes through the same watchlist/executor).
- If you add a dedicated EM executor, it should use the same `position_filter` and `risk_config` (max shorts, max new per day).

---

## 11. Prioritized Action List

| # | Action | Effort | Impact |
|---|--------|--------|--------|
| 1 | Fix stop/TP formula and values for SELL in execute_candidates (2% stop, 3% TP) | Low | High |
| 2 | Unify pipeline: executor reads watchlist_multimode.json or add converter to screener_candidates.json | Medium | High |
| 3 | Add sync_current_shorts.py and run it before screener / on schedule | Low | High |
| 4 | Set max_new_shorts_per_day in risk.json and enforce in execute_candidates | Low | Medium |
| 5 | Set position_size to 100 (or from risk.json) | Low | Medium |
| 6 | Add sector concentration check to execute_candidates (max 30%) | Medium | Medium |
| 7 | Move stop_loss_pct / take_profit_pct to risk.json (optional) | Low | Low |
| 8 | Add notional cap enforcement when IB position data is available (optional) | Medium | Low |
| 9 | Add optional regime gate for new shorts (optional) | Medium | Low |

---

## 12. Summary

- **Harden:** Fix short stop/TP logic, ensure current-shorts sync runs, unify screener → executor data flow, enforce max new shorts per day and (optionally) sector cap. That aligns behavior with your doc and removes double-up and over-concentration risk.
- **Optimize:** Single risk config (you have it), position size 100, and optional notional/regime gates give you one place to tune and a path to scale. After that, the main lever is screener thresholds (e.g. Mode 2 `recent_weakness_pct`, which you already made configurable) and EM integration if you want it in the same pipeline.

If you want, next step can be concrete code changes for (1) stop/TP for shorts, (2) executor reading watchlist_multimode.json, and (3) sync_current_shorts.py.
