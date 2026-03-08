# TradingView AMS NX — Reference & Python Alignment

Your **indicator** (Trade Engine) and **screener** (Pro Screener) live in TradingView. This doc summarizes their logic, webhook payloads, and how they align with the Python trading system (signal validator, executors, NX metrics).

**Tier 5 (full NX metrics):** This reference directly informs **NX_TIER5_FULL_METRICS_STEPS.md**. That doc now includes a “How TradingView informs Tier 5” section (lookbacks 21/63/126, RS 126 vs 252, tier thresholds 0.20/0.35, composite and structure flavors, HTF W/M vs 4H) so Python can stay in sync with your TV scripts.

**Scripts (in TradingView):**
- **AMS Trade Engine NX v2.1** (overlay) — Continuous sizing (Covel), regime filter, Z-score, RS, Chandelier exit, webhook on entry/exit/tp1.
- **AMS Pro Screener NX v2** (non-overlay) — Tier 2/3 score, long/short “ready”, RS/RSI/structure/HTF/sector, webhook on new match.

---

## 1. Trade Engine NX v2.1 — Summary

### Purpose
Chart indicator: generates **long** and **short** entry/exit signals with regime filtering, volatility‑targeted Chandelier stop, Covel-style micro-partial at 2R, and position sizing (2% rule). Sends webhook alerts on entry, exit, and TP1.

### Key inputs (aligned with Screener v2)
| Input | Default | Role |
|-------|---------|------|
| Short ROC | 21 | Short-term momentum |
| Med ROC | 63 | Medium momentum |
| Long ROC | 126 | Long momentum (aligns with RS lookback) |
| Z-Score Lookback | 252 | Z-score of adaptive ROC |
| RS Lookback | 126 | RS vs SPY (percentile) |
| RS Long pct / Short pct | 0.65 / 0.35 | Long ready ≥ 65%, Short ready ≤ 35% |
| HTF | Weekly, weight 0.30 | Higher-timeframe confirmation |
| Chandelier | 22 bars, ATR mult 3.0 | Exit stop (vol-targeted) |
| Min Vol Ratio | 0.75 | Today vol ≥ 75% of 50d avg |
| Min $ Volume | 25 M | 20d median dollar volume |
| Require Screener Ready | true | Only fire when Screener said “ready” in last 5 days |

### Regime (three-state)
- **BULL:** close > EMA200 and breadth ($SPXA50R) > 60.
- **NEUTRAL:** close > EMA200 and breadth 40–60.
- **BEAR:** close < EMA200 or breadth < 40.

**Size scale (v2.1 continuous 0–1):** Z-score strength (25%), EMA200 proximity (25%), breadth strength (25%), momentum strength (25%). Final size = size scale × drawdown scale (DD ≥ 15% → 0.25, etc.).

### Entry logic (short)
- `absMom < 0`, RSI(126) < 50, Z ≤ zShortEnter (-1.0), vol OK, **regimeBear**, Screener short-ready in window, not in earnings proxy, not in momentum crash.

### Webhook payload (Engine)
JSON with one `alert()` call per event (entry/exit/tp1). Example shape:

```json
{
  "secret": "YOUR_SECRET_KEY",
  "symbol": "AAPL",
  "side": "long" | "short",
  "event": "entry" | "exit" | "tp1",
  "price": 123.45,
  "stop": 120.0,
  "tp1": 126.0,
  "zScore": -0.5,
  "rsPct": 0.42,
  "posSize": 0.75,
  "riskPerShare": 2.5,
  "recommendedShares": 560,
  "dollarRisk": 14000,
  "ts": 1234567890000
}
```

**Python alignment:**  
- **Signal Validator** expects `symbol` (or `ticker`), `side` (or `action`), optional `secret`, optional `ts`/`timestamp`. Engine sends these.  
- **execute_candidates** / **execute_dual_mode** consume validated payloads; they use `symbol` and `side` (e.g. `short` → SELL).  
- Optional: pass `stop`, `tp1`, `recommendedShares` through to executor for order sizing and bracket logic if you want TradingView to drive exact levels.

---

## 2. Pro Screener NX v2 — Summary

### Purpose
Screener: flags symbols that are **long ready** or **short ready** (tier ≥ 2) with RS, RSI, structure, HTF, sector RS, and V2 filters. Sends webhook on **new match** (barstate.isconfirmed).

### Key inputs
| Input | Default | Role |
|-------|---------|------|
| Short/Med/Long ROC | 21 / 63 / 126 | Momentum (aligned with Engine) |
| Min Score Tier 2 / 3 | 0.20 / 0.35 | Composite tier threshold |
| RS Lookback | 126 | RS vs SPY |
| RS Long pct / Short pct | 0.65 / 0.35 | Long ≥ 65%, Short ≤ 35% |
| RSI Len | 14 | RSI for relMom / short gate |
| Min RSI (Long) / Max RSI | 50 / 75 | Long: RSI > 50 |
| Max \|Corr\| vs SPY | 0.80 | Low correlation filter |
| RVol Lookback | 50 | Volume ratio |
| Min $ Volume | 25 M, Min Price 5 | Liquidity |
| HTF | Weekly 0.30, Monthly 0.20 | HTF bias in composite |
| Sector RS | optional (e.g. XLK) | Sector ETF outperforming SPY |
| Earnings proxy | ATR ratio > 1.5 | Blackout filter |
| Momentum crash guard | rocS > 2*rocM and rocS > 20 | Parabolic filter |

### Composite score (Screener)
- `compMom` = 0.2×rocS + 0.3×rocM + 0.5×rocL (vol-normalized by ATR% if enabled).
- `htfBias` = weekly + monthly ROC squash.
- `volScore` = RVol (capped) + volume trend.
- `structScore` = pivot high/low structure.
- **compFinal** = 0.40×scoreRaw + 0.20×htfAdj + 0.20×volScore + 0.20×structScore.
- **Tier:** compFinal ≥ 0.35 → 3, ≥ 0.20 → 2, else 1.

### Long ready
- liqOK, lowCorr, absMom (close > close[126]), relMom (RSI > 50), rsP ≥ rsLongPct, tier ≥ 2, momCrashGuard, structOK, sectorRS_OK, not earningsProxy.

### Short ready
- liqOK, lowCorr, not absMom, RSI < 50, rsP ≤ rsShortPct, tier ≥ 2, not earningsProxy (structure/sector not required for short in screener).

### Webhook payload (Screener)
On **new match** (passAll and not passAll[1]):

```json
{
  "secret": "P1nchy",
  "symbol": "AAPL",
  "timeframe": "D",
  "source": "AMS-NX-Screener-v2",
  "event": "screener_new_match",
  "ts": 1234567890000
}
```

**Python alignment:**  
- **Signal Validator** can accept `event: "screener_new_match"` as a “candidate” signal; you may treat it as “add to watchlist” or “run Python screener for this symbol” rather than immediate order.  
- If the **Engine** is the only source of order signals, Screener webhook can be used to trigger a Python screener run or to log/watchlist only; validator can require `event: "entry"` for execution path.

---

## 3. Lookback & threshold alignment (Python ↔ TradingView)

Use these when implementing or tuning the Python NX stack (e.g. **NX_TIER5_FULL_METRICS_STEPS.md**, **nx_screener_production.py**):

| Concept | TradingView (Engine / Screener) | Python (current or target) |
|--------|----------------------------------|----------------------------|
| RS lookback | 126 | NX spec 252d; TV uses 126 for RS percentile. Consider 126 vs 252 in Python. |
| Short/Med/Long ROC | 21 / 63 / 126 | Mirror in Python composite/momentum if you want same behavior. |
| RSI | 14 (Screener), 126 for relMom (Engine) | RSI(14) in NX spec Composite/Structure. |
| Regime | EMA200 + breadth (MMFI) | Python regime_detector: SPY vs 200 SMA (+ VIX). Breadth not in Python yet. |
| HTF | Weekly + Monthly (Screener); Weekly (Engine) | NX spec: 4H 200 SMA. TV uses W/M for bias. |
| Vol / RVol | 50d vol ratio; ATR 14 | NX spec: ATR RVol; Python: add ATR(14). |
| Structure | Pivot H/L (Screener); HH/HL (Engine) | NX spec: BB squeeze, SMA alignment, RSI, volume. |
| Z-Score | 252d, adaptive ROC | Optional in Python for sizing/regime. |

---

## 4. Webhook secret and validator

- **Engine** and **Screener** each have a webhook secret input (`webhookSecret`).  
- **Signal Validator** (`agents.signal_validator.validate_signal`) uses `TV_WEBHOOK_SECRET` (or equivalent) to check `signal.get("secret")`.  
- Use the same secret in TradingView and in `.env` / `.cursor/.env.local` (e.g. `TV_WEBHOOK_SECRET=your_secret`) so only your alerts pass validation.

---

## 5. End-to-end flow (TradingView → Python)

1. **Screener** fires `screener_new_match` → optional: Python logs or adds symbol to a “screener hits” list; no order yet.  
2. **Engine** fires `entry` (long/short) → webhook hits your endpoint → **Signal Validator** (schema, secret, dedup, market hours, portfolio) → if allowed, queue for **execute_candidates** or **execute_dual_mode**.  
3. **Engine** fires `exit` or `tp1` → optional: log only, or future “exit manager” could close/trim position.  
4. **Executors** use shared **execution_gates** (regime, gap, sector, daily limit, position size); **Risk Monitor** can trigger kill switch independent of TV.

Keeping **lookbacks (21/63/126, RS 126)** and **thresholds (RS 0.65/0.35, tier 0.20/0.35)** in sync between TradingView and Python (e.g. in `risk.json` or a small `nx_config.py`) will keep signals and filters aligned.
