# Trading Automation — Deep Quality Analysis

**Repo:** [winzenburg/MissionControl](https://github.com/winzenburg/MissionControl)  
**Scope:** NX screener, options executor, equity shorts, position filtering, risk, Mode 2 tuning  
**Date:** March 7, 2026

**Overall structure:** `[Market Data] → [Screeners] → [Signal Filter] → [Risk Gates] → [IB Gateway] → [Positions]`

---

## Executive Summary

| Area | Finding | Severity |
|------|---------|----------|
| **Position filtering** | Screener does **not** filter out existing positions → double-up risk on current 11 shorts | **High** |
| **Options execution** | 21 rejections driven by **account permissions** (naked/sell-to-open); contract format may also need hardening | **High** |
| **Portfolio sizing / risk** | Sizing is fragmented (executor vs auto_options vs risk.json); no single source of truth for max shorts or notional | **Medium** |
| **Mode 2 (premium)** | Thresholds are strict (e.g. `recent_return < -0.05` only); no IV data used in screener; can be relaxed and enriched | **Medium** |

**Current state (your summary):** 11 equity/EM shorts live, 21 options rejected, screener not excluding positions, P&L -$1,533 (-0.49%).

---

## 1. Position Filtering — Prevent Re-Signaling Existing Shorts

### 1.1 What the code does today

**`nx_screener_production.py`** (main trend screener):

- Builds a **static universe per mode** from `MODE_CONFIG` (and optionally `full_market_2600.csv` for `load_full_universe()`).
- Fetches price data, computes NX metrics (RS, RVol, price vs 50/100 MA, etc.).
- Applies mode-specific filters and writes **all** passing symbols to `watchlist_multimode.json` under `modes.short_opportunities.short` (and other modes).
- **There is no:**
  - Call to IB (or any API) to fetch current positions.
  - Load of a “current positions” JSON/file.
  - Filter that excludes symbols you already have as shorts.

So the screener can (and likely does) repeatedly signal **AAPL, MSFT, NVDA, GOOGL, META, TSLA, AMZN, ADBE, QCOM, AVGO, YINN** for Mode 3 short_opportunities, even though those are already in the account. Downstream executors that consume `watchlist_multimode.json` or `execution_log.json` can therefore add size to existing shorts instead of only opening new names.

### 1.2 Where filtering should live

Two defensible designs:

- **Option A — In the screener:** Before writing `watchlist_multimode.json`, load “current short symbols” (from IB or a positions file) and exclude them from each mode’s `short` (and optionally `long`) lists. Pros: one place, downstream scripts only see “actionable” names. Cons: screener needs IB connection or a shared positions file.
- **Option B — In the executor(s):** Each script that places short/equity orders (e.g. equity-shorts executor, `execute_candidates.py`, or any script that reads `short_opportunities`) loads current positions and skips any symbol already short. Pros: no change to screener; works even if positions are updated by other tools. Cons: every executor must implement the same rule.

**Recommendation:** Do **both** for defense in depth:

1. **Screener:** Add an optional “exclude list” of symbols (e.g. from a file `~/.openclaw/workspace/trading/current_short_symbols.json` or from IB). If the file exists (or IB is available), strip those symbols from `short_opportunities.short` (and any other list used for shorts) before writing the watchlist. Document that this file can be updated by a separate “sync positions” step (cron or post-execution).
2. **Executors:** In the script that executes equity shorts (you mentioned `execute_equity_shorts.py` — not present in the public repo; likely under `~/.openclaw/workspace`), and in `execute_candidates.py` when `action == 'SELL'`, load current short positions (IB or same JSON) and skip if the symbol is already short. Same for any options executor that sells calls (short delta) if you add that later.

### 1.3 Concrete implementation sketch (screener)

- Add a helper, e.g. `load_current_short_symbols() -> set[str]`:
  - Prefer: read from `WORKSPACE / "current_short_symbols.json"` (format: `{"symbols": ["AAPL", ...], "updated_at": "..."}`).
  - Optional: if IB connection is configured, call `ib.positions()`, keep symbols with `position < 0` (short).
- In `run_mode_short_opportunities` (and any other mode that produces shorts), after building `short_candidates`, filter:  
  `short_candidates = [c for c in short_candidates if c["symbol"] not in load_current_short_symbols()]`.
- Same for `run_mode_premium_selling` if “short” side is used for call-selling and you already hold short in that name.
- Log: “Excluded N symbols already in current shorts.”

This removes double-up risk at the source while keeping the rest of the pipeline unchanged.

### 1.4 Implementation

Position filtering is implemented as follows: shared helper in `trading/scripts/position_filter.py` (`load_current_short_symbols(workspace, ib)`); screener `trading/scripts/nx_screener_production.py` excludes current shorts from `short_opportunities` and `premium_selling` short lists before writing `watchlist_multimode.json`; executor `trading/scripts/execute_candidates.py` loads current shorts (file + IB when connected) and skips SELL orders for symbols already short, and adds the symbol to the in-memory set after a successful SELL in the same run.

---

## 2. Options Execution Blocker — Account Permissions vs Contract Specs

### 2.1 What’s in the repo

- **`direct_premium_executor.py`** connects to IB Gateway (e.g. `127.0.0.1:4002`), reads `premium_signals_filtered.json`, builds an option contract with `ib_insync.Contract`, and places **MarketOrder("SELL", contracts)**. So every order is **sell-to-open** (short options).
- **`execute_filtered_premium.py`** posts to a webhook; the actual submission to IB is elsewhere (webhook handler). Rejections can still be due to the same permission/contract issues when the handler places the order.

You reported **21 options orders rejected by IBKR**. That points to two main possibilities:

1. **Account permissions (most likely)**  
   - Sell-to-open puts without owning stock = cash-secured or naked puts.  
   - Sell-to-open calls without stock = naked calls.  
   - IBKR options levels (see [Options Level Trading Permissions](https://www.ibkrguides.com/orgportal/optionstradingpermissions.htm)): Level 1 = buy options, covered calls; Level 2+ = cash-secured puts; **Level 4** = naked calls, straddles, strangles, etc.  
   - If your account is only Level 1 (or not approved for the strategy you’re sending), IBKR will reject sell-to-open orders regardless of contract details.

2. **Contract specification**  
   - `direct_premium_executor.create_options_contract()` uses `lastTradeDateOrContractMonth=exp_str` with `exp_str = (now + timedelta(days=dte)).strftime("%Y%m%d")`. That gives a **specific date**. IB expects **monthly** expirations in the form `YYYYMM` for standard listed options in many cases; weekly expirations can be `YYYYMMDD`. So depending on how `dte` is set and what IB expects for that symbol, the contract might be invalid or not match a listed series.  
   - Also: no explicit `multiplier` or `exchange` beyond `"SMART"`; that’s usually fine, but if you have rejections with a message like “No security definition found,” the expiration format or symbol is the first thing to check.

### 2.2 How to confirm and fix

**Step 1 — Confirm it’s permissions**

- In IBKR: **Account Settings → Trading → Trading Permissions → Update Options Level.**  
- Check current level and which strategies are allowed (e.g. “Sell cash-secured puts” vs “Naked calls”).  
- If you’re only Level 1, you will need at least Level 2 for cash-secured puts; for any naked call selling, Level 4.  
- If your Financial Profile is incomplete or conservative, IB may deny higher levels; update it and re-request.

**Step 2 — Inspect rejection messages**

- In `direct_premium_executor.py`, the code only checks `trade.orderStatus.status`. It doesn’t log the **rejection reason** (e.g. “Insufficient permissions” vs “No security definition found”).  
- **Recommendation:** Log the full status and any message, e.g. `trade.log` or IB’s text in `orderStatus`/`order_state`, and persist it in `execution_log` (e.g. under each execution’s `"error"` or `"reject_reason"`). That will tell you definitively whether the blocker is permissions vs contract.

**Step 3 — Harden contract building**

- Use IB’s **next Friday** or **next monthly expiration** logic (like `auto_options_executor.get_option_contract`) so `lastTradeDateOrContractMonth` matches a listed expiration.  
- Optionally **qualify** the contract with `ib.qualifyContracts(contract)` before placing the order; if qualification fails, log the error and skip (avoids sending invalid contracts and clarifies “no contract” vs “permission” errors).

**Step 4 — Align strategy with permissions**

- If you only have Level 2: restrict automation to **cash-secured puts** (and/or covered calls). Do not send naked calls or other Level 4 strategies until approved.  
- You can add a config flag in the executor, e.g. `allowed_strategies: ["SELL_PUT"]`, and skip any signal whose `type` is not in that list.

Summary: treat the 21 rejections as **account permissions first**; add logging of rejection reason and robust expiration/qualify logic so you can distinguish permissions from contract issues and avoid invalid orders.

---

## 3. Portfolio Sizing and Risk Management

### 3.1 Current state

- **Screener:** No notion of account size, current notional, or number of positions; it only outputs ranked candidates.
- **`automated_trade_executor.py`:** Hard-caps **top 2** for Mode 2 (CSP) and **top 1** for Mode 3 (put). No dollar or notional limits.
- **`direct_premium_executor.py`:** No daily/max-order or notional checks; it executes all signals in `premium_signals_filtered.json`.
- **`auto_options_executor.py`:** Has `MAX_OPTIONS_PER_DAY`, `MAX_OPTIONS_PER_MONTH`, `MIN_PREMIUM_PERCENT`, `MAX_RISK_PER_CONTRACT`, and uses `dynamic_position_sizing` and `sector_concentration_manager` when available. So **options** have some risk layer; **equity shorts** path does not share a single config.
- **`execute_candidates.py`:** Uses `EXEC_PARAMS` (e.g. 1 share, daily loss limit 3%); no cap on number of shorts or total short notional.
- **`AUTOMATION_GUIDE.md`** references `risk.json` (max position $10k, max portfolio $50k, sector 30%); it’s unclear whether the equity-shorts or NX-driven flow enforces it.

So: **portfolio sizing is fragmented.** Equity shorts (11 names) can grow without a single “max shorts” or “max short notional” gate; options have more structure but still depend on which script runs and whether strategy modules load.

### 3.2 Recommendations

- **Single risk config:** Use one place (e.g. `trading/risk.json` or `.env`) for:
  - Max number of **equity short** positions.
  - Max **total short notional** (or max % of equity).
  - Max new shorts per day (optional).
- **Screener/executor:** Either:
  - In the screener: after position filtering, **trim** `short_opportunities.short` to the top N by score (e.g. N = max_short_positions - current_short_count), or  
  - In the executor: load current shorts and risk config, and only execute until you’d hit the cap (so you never exceed N shorts or X notional).
- **Options:** Keep and reuse the daily/monthly and per-contract limits; ensure `direct_premium_executor` (and any webhook path) either calls the same limits or reads from the same config so you don’t bypass them when switching execution path.
- **Logging:** Log “would exceed max shorts / notional” as a skip reason so you can see when risk gates are acting.

This gives you one place to tune risk and consistent behavior across NX screener → equity shorts and options.

---

## 4. Screener Threshold Tuning — Mode 2 (Premium Selling)

### 4.1 Current Mode 2 logic

In **`nx_screener_production.py`**:

- **`run_mode_premium_selling`** uses `MODE_CONFIG["premium_selling"]`:
  - Universe: large-cap tech (QQQ-style).
  - **Documented** filters: `iv_rank_min: 0.70`, `recent_weakness: True`, `identify_support: True`.
  - **Implemented** filter: only `metrics['recent_return'] < -0.05` (down 5%+). There is **no** IV rank, support, or volatility in the code; `calculate_nx_metrics` does not fetch or compute IV.

So Mode 2 is currently “recent 20-day return &lt; -5%” only. That’s a low bar for “weakness” but a **high** bar for “premium opportunity” if you want more names (you asked to “lower” Mode 2 to capture more premium plays).

### 4.2 Lowering the bar and enriching

- **Lower the weakness threshold:**  
  - Change `-0.05` to e.g. `-0.03` (down 3%+) or make it configurable (e.g. `premium_selling.weakness_pct_min` in a config or constant). That will increase the number of symbols that qualify as “recent weakness.”
- **Add real IV (optional but valuable):**  
  - `yfinance` can provide optional IV-related data; or use another source. If you add IV rank/percentile, you can:
  - Keep a minimum IV rank (e.g. 0.50+) so you’re selling premium where it’s meaningful, and  
  - Optionally cap extreme IV (e.g. skip earnings-level IV) to avoid tail risk.  
  That would align the implementation with the documented “high-IV tech” idea.
- **Structure score / support:**  
  - You already have `hl_ratio` (structure) in NX metrics. You could filter or rank Mode 2 by “near support” (e.g. `hl_ratio` in a band) so you’re selling puts where there’s a plausible support level.
- **Cap list size:**  
  - To avoid a huge list, keep taking the top N by a composite (e.g. `-recent_return + iv_rank`) or just the first K names after filters; the executor already limits (e.g. top 2 in `automated_trade_executor`), but the watchlist will be cleaner if the screener does it.

### 4.3 Concrete change (minimal)

In `nx_screener_production.py`, in `run_mode_premium_selling`, replace:

```python
if metrics['recent_return'] < -0.05:  # Down 5%+
```

with a configurable threshold, e.g.:

```python
weakness_min = mode_cfg['filters'].get('recent_weakness_pct', -0.05)  # default -5%
if metrics['recent_return'] < weakness_min:
```

and in `MODE_CONFIG["premium_selling"]["filters"]` add `"recent_weakness_pct": -0.03` (or -0.02) to capture more names. Tune based on how many candidates you want and how noisy they are.

---

## 5. Code Quality Notes (from your Code Guardian rules)

- **Type safety:** The Python scripts use minimal type hints and some `dict`/untyped JSON. Adding type hints and small dataclasses for “candidate,” “signal,” “execution” would align with your strict TypeScript rules and reduce bugs when changing pipelines.
- **Error handling:** API/IB calls are often wrapped in broad `except`; logging the exception and re-raising (or returning a structured error) would make debugging and logging rejection reasons easier.
- **Console/logging:** Some scripts use `print()`; standardizing on `logging` and avoiding `print()` for operational output would help with log aggregation and the “no console.log” style rule.
- **Docs/comments:** Screener and executors have docstrings; adding a short comment at the top of each script describing “inputs → outputs → side effects” would help the next person (or OpenClaw) reason about the pipeline.

---

## 6. File and Script Reference

| Item | Location (repo or your env) | Note |
|------|-----------------------------|------|
| Main trend screener | `trading/scripts/nx_screener_production.py` | No position filter; Mode 2 only uses `recent_return < -0.05`. |
| Options executor (direct IB) | `trading/scripts/direct_premium_executor.py` | Sell-to-open; no rejection-reason logging; expiration from `dte` only. |
| Equity shorts executor | You mentioned `execute_equity_shorts.py` | Not in public repo; likely under `~/.openclaw/workspace`. Should apply position filter. |
| Trade generator | `trading/scripts/automated_trade_executor.py` | Reads screener output; top 2 CSP, top 1 put; no position or risk config. |
| Options (full automation) | `trading/scripts/auto_options_executor.py` | Has daily/monthly limits, sector and VIX-based sizing; different code path than direct_premium. |
| Execution logs | `trading/logs/` | Use these to confirm rejections and add rejection-reason logging. |
| Watchlists | `trading/watchlist_*.json`, `watchlist_multimode.json` | Screener output; add “current shorts” exclusion before or when writing. |

---

## 7. Prioritized Action List

1. **High — Position filtering**  
   - Add `load_current_short_symbols()` and exclude those symbols from `short_opportunities` (and any other short list) in the screener.  
   - In the equity-shorts executor (and `execute_candidates` for SELL), skip symbols already short.

2. **High — Options rejections**  
   - Confirm IBKR options level and enable at least Level 2 for CSP (or Level 4 if you intend naked calls).  
   - Log full rejection reason in `direct_premium_executor` and, if needed, fix expiration/qualify logic so contracts match listed series.

3. **Medium — Risk and sizing**  
   - Introduce a single risk config (max equity shorts, max short notional or %, optional max new per day).  
   - Enforce it in the screener (trim list) and/or in the executor (refuse to open new shorts past the cap).

4. **Medium — Mode 2 tuning**  
   - Make `recent_weakness_pct` configurable and lower it (e.g. -3% or -2%) to get more premium candidates.  
   - Optionally add IV and structure so Mode 2 matches the “high-IV premium” design.

5. **Lower — Quality**  
   - Add rejection-reason and error logging; type hints and small data classes; replace `print` with `logging` where appropriate.

---

*End of analysis. If you want, next step can be concrete patches for position filtering in the screener and rejection logging in the options executor.*
