# Tier 5 #12: Full NX Metrics — Step-by-Step Plan

Breakdown of the "Full NX metrics" roadmap item so you can implement incrementally. Reference: **NX_SCREENER_TECHNICAL_SPEC.md** (Component 1), **nx_screener_production.py**, and **TRADINGVIEW_AMS_NX_REFERENCE.md** (TradingView Engine + Screener).

---

## Current state

- **`calculate_nx_metrics()`** returns: `recent_return`, `rs_pct` (20d), `rvol` (20d log-vol ratio), `hl_ratio`, `price_vs_50ma`, `price_vs_100ma`, `ma50`, `ma100`.
- Spec wants: **Composite**, **252d RS**, **ATR-based RVol**, **Structure quality**, **HTF bias**.
- Short mode currently filters on `rs_pct`, `price_vs_100ma`, `failed_bounce`, `volume_confirms` only — not the five full metrics.

---

## How TradingView informs Tier 5

Your **AMS Trade Engine NX v2.1** and **AMS Pro Screener NX v2** use specific lookbacks and thresholds. Aligning Python with them keeps signals consistent whether they come from TradingView or from the Python screener.

| Area | TradingView (Engine / Screener) | NX spec (Python doc) | Recommendation for Tier 5 |
|------|---------------------------------|----------------------|----------------------------|
| **Momentum / ROC** | Short 21, Med 63, Long **126** | 20d momentum in Composite | Add **126d** (and optionally 21/63) for composite or a separate “TV-style” score; 20d remains for spec Composite. |
| **RS lookback** | **126** (RS percentile vs SPY) | **252d** return / SPY vol | Implement **252d** per spec (Step 3); add optional **126d RS percentile** (fraction of days stock beat SPY) to mirror Screener and use same threshold: short ≤ 0.35, long ≥ 0.65. |
| **Composite** | Screener: compMom (0.2×rocS + 0.3×rocM + 0.5×rocL) + HTF + volScore + structScore; **tier 2 ≥ 0.20, tier 3 ≥ 0.35** | Spec: momentum_norm + BB + RSI (0.4/0.3/0.3) | Keep spec Composite (Step 2) for “trend strength”; optionally add a **TV-style composite** (ROC blend + vol + structure) and use **tier thresholds 0.20 / 0.35** in short_opportunities so Python tiers match Screener. |
| **Structure** | Pivot high/low count; HH/HL (higher highs, higher lows) for Engine | Spec: BB squeeze + SMA alignment + RSI + volume | Implement spec Structure (Step 5) first; optionally add **pivot-based** or **HH/HL** structure so Python “structure” is closer to TV’s entry confirmation. |
| **HTF** | **Weekly + Monthly** ROC, squash, weight 0.30 W / 0.20 M | Spec: **4H** close vs 200 SMA | Implement 4H for spec (Step 6); optionally add **Weekly/Monthly** bias so Python can match Screener’s HTF component when you want TV alignment. |
| **RVol / ATR** | ATR(14), vol-normalized momentum (ATR% baseline) | ATR(14) for RVol ratio | Use **ATR(14)** in Step 4; same as TV. |
| **RSI** | 14 (Screener); 126 for Engine relMom | 14 in spec | Use **RSI(14)** everywhere in Tier 5; matches TV. |

**Practical takeaway:** Implement the five NX metrics per the spec steps first. Then, if you want Python and TradingView to agree on “tier” and “ready”:

- Use **tier thresholds 0.20 (Tier 2) and 0.35 (Tier 3)** in MODE_CONFIG for short_opportunities.
- Add **126d RS** (or 126d percentile) alongside 252d RS and gate shorts with rs_126 ≤ 0.35, longs with rs_126 ≥ 0.65.
- Consider a **TV-style composite** (ROC blend + vol + structure) in addition to the spec Composite, and optionally **Weekly/Monthly HTF** in addition to 4H.

Full TradingView logic and webhook payloads: **docs/TRADINGVIEW_AMS_NX_REFERENCE.md**.

---

## Step 1: Technical helpers (RSI, Bollinger Bands, ATR)

**Goal:** Add reusable helpers used by Composite, RVol, and Structure.

**Where:** New file `trading/scripts/nx_metrics_helpers.py` (or add to top of `nx_screener_production.py`).

**Add:**

- **`calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series`**  
  Standard RSI: `delta = close.diff()`, `gain = delta.where(delta > 0, 0)`, `loss = (-delta).where(delta < 0, 0)`, `rs = gain.rolling(period).mean() / loss.rolling(period).mean()`, `rsi = 100 - (100 / (1 + rs))`. Return series; callers use `.iloc[-1]`.

- **`bollinger_bands(close: pd.Series, window: int = 20, num_std: float = 2) -> tuple`**  
  `middle = close.rolling(window).mean()`, `std = close.rolling(window).std()`, `upper = middle + num_std * std`, `lower = middle - num_std * std`. Return `(upper, middle, lower)`.

- **`calculate_true_range(high, low, close_prev)`**  
  `max(high - low, abs(high - close_prev), abs(low - close_prev))`.

- **`calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series`**  
  TR per row (using prior close); `ATR = TR.rolling(period).mean()`. Return ATR series.

**Done when:** Helpers exist and can be unit-tested or spot-checked on one symbol.

---

## Step 2: Metric 1 — Composite score

**Goal:** Implement Composite (trend strength) per spec: momentum_20d (normalized), BB position, RSI (normalized); weighted average; clamp [0, 1].

**Where:** `nx_metrics_helpers.py` or `nx_screener_production.py`.

**Add:** `calculate_composite_score(df: pd.DataFrame) -> float`  
- Momentum 20d: `(Close[-1] - Close[-20]) / Close[-20]`; normalize to [0,1] via clamp(-0.15, 0.15) then `(x/0.15+1)/2`.  
- BB position: `(Close[-1] - BB_lower) / (BB_upper - BB_lower)`, clamp [0,1].  
- RSI norm: `(RSI[-1] - 30) / 40`, clamp [0,1].  
- `composite = 0.4 * momentum_norm + 0.3 * bb_pos + 0.3 * rsi_norm`, then `clamp(composite, 0, 1)`.

**Wire:** In `calculate_nx_metrics()` (or a new `calculate_nx_metrics_full()`), compute and add `"composite": round(calculate_composite_score(ohlcv), 3)`.

**Done when:** Composite is in the metrics dict and looks sensible (e.g. 0.2–0.5 for choppy, higher for strong trend).

---

## Step 3: Metric 2 — 252d Relative Strength

**Goal:** Replace or supplement 20d RS with 252d RS normalized by SPY volatility.

**Where:** Same as above.

**Add:** `calculate_rs_252d(stock_data: pd.DataFrame, spy_data: pd.DataFrame) -> float`  
- `stock_return_252 = (Close[-1] - Close[-252]) / Close[-252]` (guard len >= 252).  
- `spy_return_252 = same for SPY`.  
- `spy_vol = spy_data['Close'].pct_change().std()` (252d period).  
- `rs_pct = (stock_return_252 - spy_return_252) / spy_vol` if spy_vol > 0 else 0.  
- `rs_pct = clamp(rs_pct / 0.5, -1.0, 1.0)`.

**Wire:** Add `"rs_252d": round(calculate_rs_252d(ohlcv, spy_data), 3)` to metrics. Keep `rs_pct` (20d) for backward compatibility if other modes use it.

**Done when:** 252d RS is in metrics; short threshold will use rs_252d < 0.50.

---

## Step 4: Metric 3 — ATR-based RVol

**Goal:** Replace log-vol RVol with ATR(14) ratio.

**Where:** Same.

**Add:** `calculate_rvol_atr(stock_data: pd.DataFrame, spy_data: pd.DataFrame) -> float`  
- `stock_atr = calculate_atr(stock_data, 14).iloc[-1]`  
- `spy_atr = calculate_atr(spy_data, 14).iloc[-1]`  
- `rvol = stock_atr / spy_atr` if spy_atr > 0 else 1.0.

**Wire:** Add `"rvol_atr": round(calculate_rvol_atr(ohlcv, spy_data), 3)` to metrics. Keep existing `rvol` as `rvol_20d` if you still use it elsewhere.

**Done when:** RVol in short logic uses ATR-based value; spec threshold rvol > 1.0.

---

## Step 5: Metric 4 — Structure quality

**Goal:** Implement structure (BB squeeze, SMA alignment, RSI divergence, volume confirmation).

**Where:** Same.

**Add:** `calculate_structure_quality(df: pd.DataFrame) -> float`  
- BB squeeze: width = `(2*std_20)/mean_20`, normalize to [0,1] (e.g. min(width/0.1, 1)).  
- SMA alignment (downtrend): 20 < 50 < 200 and price < 20 → 1.0; else 0.6 or 0.  
- RSI: <30 → 0.8, <40 → 0.6, else 0.2.  
- Volume: today vol > 1.2 * avg(20) and price down → 1.0, else 0.5.  
- `structure = 0.25*bb + 0.35*sma_align + 0.25*rsi_div + 0.15*vol`, clamp [0,1].

**Wire:** Add `"structure": round(calculate_structure_quality(ohlcv), 3)` to metrics.

**Done when:** Structure is in metrics; short threshold structure < 0.35.

---

## Step 6: Metric 5 — HTF bias (optional) ✅

**Goal:** 4H trend: price vs 200 SMA on 4H bars.

**Done:** `calculate_htf_bias(ticker, period_4h="250d")` in **nx_metrics_helpers.py** — fetches 4H via yfinance, 200 SMA, returns 1.0 (uptrend), 0.0 (downtrend), or 0.5 (neutral). **run_mode_short_opportunities** uses a second pass: for each candidate that passed other filters, fetches HTF and filters by `htf_bias_max` (0.50). Threshold in MODE_CONFIG short_opportunities filters.

---

## Step 7: Thresholds and filter in short_opportunities

**Goal:** Use all five metrics in the short-opportunities mode.

**Where:** `nx_screener_production.py` — `MODE_CONFIG["short_opportunities"]["filters"]` and `run_mode_short_opportunities()`.

**Add to MODE_CONFIG (example):**

```python
"short_opportunities": {
    ...
    "filters": {
        "composite_max": 0.35,    # composite < 0.35 (downtrend)
        "rs_252_max": 0.50,      # rs_252d < 0.50 (underperforming)
        "rvol_atr_min": 1.0,     # rvol_atr > 1.0 (swing room)
        "structure_max": 0.35,    # structure < 0.35 (clean downtrend)
        "htf_bias_max": 0.50,    # htf_bias < 0.50 (4H not uptrend)
        # keep existing if desired:
        "price_below_100ma": True,
        "failed_bounce": True,
        "volume_confirms": True,
    },
}
```

**In `run_mode_short_opportunities()`:**  
For each candidate, after computing full metrics (composite, rs_252d, rvol_atr, structure, optional htf_bias), apply:

- `composite <= filters.get("composite_max", 0.35)`
- `rs_252d <= filters.get("rs_252_max", 0.50)`
- `rvol_atr >= filters.get("rvol_atr_min", 1.0)`
- `structure <= filters.get("structure_max", 0.35)`
- `htf_bias <= filters.get("htf_bias_max", 0.50)` (if htf_bias present)

**Done when:** Short list is driven by the five NX metrics plus any legacy filters you keep.

---

## Step 8: Optional — single `screen_for_shorts(ticker)` entry point ✅

**Goal:** One function that fetches data, computes all five metrics, applies thresholds, returns candidate dict or None.

**Done:** **`screen_for_shorts(ticker, spy_data, thresholds, spy_ohlcv=None, include_htf=True)`** in **nx_screener_production.py**. Fetches 1y daily for ticker, calls `calculate_nx_metrics`, applies all short thresholds (price_vs_50/100ma, rs_pct, composite_max, rs_252_max, rvol_atr_min, structure_max, htf_bias_max), optionally fetches HTF and filters. Returns full metrics dict with `reason` if pass, else None. Use for testing or webhook-triggered single-symbol checks.

---

## Suggested order

1. **Step 1** — Helpers (RSI, BB, ATR).  
2. **Step 2** — Composite.  
3. **Step 3** — 252d RS.  
4. **Step 4** — ATR RVol.  
5. **Step 5** — Structure.  
6. **Step 7** — Wire thresholds and filter in short_opportunities (without HTF first).  
7. **Step 6** — HTF bias (optional), then add to filters.  
8. **Step 8** — Optional `screen_for_shorts()` refactor.

After Step 7 (without HTF), the screener is spec-aligned for Composite, 252d RS, ATR RVol, and Structure. HTF and the single-entry refactor can follow when you want 4H confirmation and cleaner structure.
