# AMS Pro Screener NX — Daily Cheat Sheet

Purpose: Surface ~20–60 high‑quality swing candidates across the whole market + ETFs. Non‑repainting, daily timeframe. Outputs Tier, CompScore, RS percentile, RVol, Structure, HTF bias, Regime, and Long/Short readiness flags.

---

## Recommended Starting Settings (Inputs)

Momentum
- Short ROC: 21
- Med ROC: 63
- Long ROC: 126

Scoring
- Min Score for Tier 2: 0.20
- Min Score for Tier 3: 0.35

Volatility (normalization)
- Normalize Momentum by ATR%: ON
- ATR Length: 14
- ATR% Baseline: 2.0

HTF (Higher Timeframe Bias)
- Use HTF Bias (W+M): ON
- Weekly weight: 0.30
- Monthly weight: 0.20

RS vs SPY (Percentiles)
- RS Lookback: 252
- RS pct ≥ (Long): 0.60
- RS pct ≤ (Short): 0.40

Volume/Liquidity
- RVol Lookback: 50
- Min $ Volume (20d median, $M): 25.0
- Min Price: 5.0

RSI/Correlation
- RSI Len: 14
- Min RSI (Long): 45
- Max RSI (Long): 75
- Max |Corr| vs SPY: 0.85

Earnings (Optional)
- Earnings Blackout (5D pre / 2D post): OFF (enable later when earnings data is wired)

---

## What the Columns Mean
- CompScore (0–1): Composite momentum quality (normalized), higher is better
- Tier: 1=passable, 2=good, 3=excellent (thresholds above)
- RSPct (0–1): Relative strength vs SPY by rolling percentile
- RVol: Relative volume (smoothed + capped)
- StructQ (0–1): Structure/pivot clarity
- HTFBias (0–1): Weekly/Monthly trend bias (tanh‑mapped)
- Regime: 0=squeeze, 1=normal, 2=breakout
- LongReady / ShortReady: Directional pass flags

---

## Quick Thresholds (Just Use These)
- Signal: 1 = Pass (eligible), 0 = Fail (ignore)
- CompScore: ≥ 0.35 = Tier 3 (excellent); 0.20–0.34 = Tier 2 (good); < 0.20 = Tier 1 (skip)
- RSPct: Longs ≥ 0.60; Shorts ≤ 0.40 (0.50 ≈ neutral)
- RVol: ≥ 1.50 strong; 1.20–1.49 supportive; 1.00–1.19 marginal; < 1.00 weak (avoid)
- StructQ: ≥ 0.60 clean; 0.40–0.59 acceptable; < 0.40 noisy (avoid)
- HTFBias: ≥ 0.60 bullish; 0.40–0.59 neutral; ≤ 0.40 bearish
- Tier: 3 prioritize; 2 consider; 1 skip
- LongReady / ShortReady: 1 = direction is ready; only trade that direction
- Regime: 0 squeeze; 1 normal; 2 breakout (chase only if RVol strong and HTFBias aligned)

Green‑light rules
- Long candidates: Signal=1, Tier≥2, RSPct≥0.60, RVol≥1.20, StructQ≥0.50, HTFBias≥0.50, LongReady=1
- Short candidates: Signal=1, Tier≥2, RSPct≤0.40, RVol≥1.20, StructQ≥0.50, HTFBias≤0.50, ShortReady=1

Fast filter when in doubt
- Keep: Tier 3 OR (Tier 2 with RSPct/StructQ/HTFBias in “good” zones)
- Skip: RVol < 1.0 or StructQ < 0.4 even if other stats look decent

---

## How To Tune List Size (Target 20–60 names)
- Too many names:
  - Raise Tier 2 to 0.22–0.25 (and Tier 3 to 0.38–0.42)
  - Tighten RS pct (Long 0.65, Short 0.35)
  - Raise Min $ Volume to 35–50M
- Too few names:
  - Lower Tier 2 to 0.18 (Tier 3 to 0.32)
  - Loosen RS pct (Long 0.55, Short 0.45)
  - Reduce Min $ Volume to 20M (keep Price ≥ $5)

When to prefer Tier 3 vs Tier 2
- Tier 3: prioritize in choppy markets or when you want a shorter list
- Tier 2: use for discovery and a broader universe

---

## Regime Cues
- 0 (Squeeze): prime for breakout scouting; look for rising RVol
- 1 (Normal): swing‑friendly; focus Tier 2–3
- 2 (Breakout): chase only with RVol confirmation and strong HTFBias

---

## Daily Workflow
1) Run screener; sort by Tier desc → CompScore desc; keep ~60
2) Use LongReady/ShortReady + Regime for context
3) On charts, use AMS Trade Engine NX for timing/risk; enable "Require Ready in last N days" in the indicator for alignment

---

## Alert Setup (TradingView)
- Create alert with: "Any alert() function call"
- Webhook URL: your listener endpoint
- The script sends JSON via alert() on a new match (includes secret/symbol/timeframe/source/ts)
- In the script Inputs, set "Webhook Secret" to match MOLT_WEBHOOK_SECRET

---

## Preset Templates

Balanced (default)
- Tier 2: 0.20, Tier 3: 0.35
- RS pct Long ≥ 0.60; Short ≤ 0.40
- Min $ Vol: 25M; Min Price: 5
- Max |Corr|: 0.85

Aggressive (more names, faster rotation)
- Tier 2: 0.18, Tier 3: 0.32
- RS pct Long ≥ 0.55; Short ≤ 0.45
- Min $ Vol: 20M; Min Price: 5
- Max |Corr|: 0.90

Conservative (fewer, higher conviction)
- Tier 2: 0.25, Tier 3: 0.42
- RS pct Long ≥ 0.65; Short ≤ 0.35
- Min $ Vol: 40M; Min Price: 10
- Max |Corr|: 0.80

---

## Troubleshooting
- Empty list: lower Tier 2 and/or loosen RS percentiles; confirm alert type is "Any alert() function call"
- Too many small caps/borrow issues: increase Min $ Volume to 35–50M and keep Min Price ≥ $5
- Over‑correlated results: reduce Max |Corr| to 0.80 or manually de‑dupe by sector (we can add quotas later)

---

## Notes
- Earnings blackout is provided as a toggle but disabled by default pending a robust data feed
- If you want per‑sector RS bands, we can calibrate thresholds after a week of data

