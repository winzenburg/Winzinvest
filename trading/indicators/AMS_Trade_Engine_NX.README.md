# AMS Trade Engine NX — Daily Indicator Cheat Sheet

Purpose: Execute long/short swing trades on Daily timeframe, aligned to AMS Pro Screener NX intent. Non‑repainting: all HTF requests use confirmed bars. Provides entries, exits, partial profits, risk controls, and standardized webhook alerts for your listener.

---

## Recommended Starting Settings (Inputs)

Momentum & Z-Score
- Short ROC: 21
- Med ROC: 63
- Long ROC: 126
- Z-Score Lookback: 252
- Enter if Z ≥: 1.0
- Exit if Z ≤: −0.5

Dual Momentum & RS
- Absolute Momentum Lookback: 252
- Risk‑Free (annual): 0.02
- RS Lookback: 252
- RS pct ≥ (Long): 0.60
- RS pct ≤ (Short): 0.40

HTF Confirm (non‑repainting)
- Use HTF Confirm (Weekly): ON
- Higher TF: W
- HTF Weight: 0.30

Screener Tie‑in
- Require Screener Ready (mirrored): ON
- Ready window (trading days): 10

Volume / Liquidity (sanity)
- Vol Lookback: 20
- Min Vol Ratio (today ≥ x * 20d): 0.60
- Min $ Volume (20d median, $M): 25.0
- Min Price: 5.0

Risk
- Use Chandelier Exit: ON
- ATR Mult: 3.0
- Chandelier Lookback: 22
- Min distance to stop (ATR): 0.75
- Hard stop % (fail‑safe): 0.15

Partials
- Partial profits ON: ON
- TP1 (R): 1.5R
- Move to BE after TP1: ON

Filters (Signal Hygiene)
- Regime filter: EMA200: ON (prevents longs below EMA200, shorts above EMA200)
- Cooldown after exit: ON (prevents immediate re-entry after exit)
- Cooldown bars: 3 (wait 3 bars after exit before allowing new entry)

Webhook
- Webhook Secret: set to your MOLT_WEBHOOK_SECRET

---

## What the Signals Mean
- Long Entry: Dual momentum OK, Z ≥ 1.0, HTF alignment OK, volume OK, "Ready" within last N days, AND (if regime filter ON) price > EMA200
- Short Entry: Mirror logic with Z ≤ −1.0, AND (if regime filter ON) price < EMA200
- Exit: Signal invalidated OR risk exit (trail stop/BE)
- Trail Stop: Chandelier (ratchets only) or fail‑safe % if chandelier off
- TP1: 1.5R based on initial stop distance; upon hit, move stop to BE (optional) and trail the rest

Notes
- All prices are raw in the alert; your broker layer (listener) can round to IBKR tick sizes (stocks: $0.01). We can extend tick maps later for futures/FX/crypto.

## Key Improvements (v2)
1. **Regime Filter**: Optional EMA200 filter prevents longs below EMA200 and shorts above EMA200 (reduces counter-trend whipsaw)
2. **Cooldown**: Optional N-bar cooldown after exit prevents immediate re-entry (reduces chop)
3. **Side-Aware Exits**: Cleaner logic for long exits vs short exits
4. **str.format() JSON**: Much cleaner webhook payload construction (no more string concatenation)
5. **Directional HTF Confirm**: `htfOK_long` and `htfOK_short` are directionally aware (clearer logic than sign agreement)

---

## Best‑Practice Workflow
1) Use AMS Pro Screener NX to generate the daily list (Tier 2+). 
2) On charts, enable "Require Screener Ready" so the indicator only triggers on names that recently passed the screener (≤10 days).
3) Place alerts using "Any alert() function call" (see below) so webhook JSON is sent automatically.
4) Approve trades via your confirm‑to‑execute flow (canary sizing), review TP/SL, and monitor partials/ratchet.

---

## Alert Setup (TradingView)
- Choose: "Any alert() function call"
- Webhook URL: your Flask listener endpoint (http://127.0.0.1:5001/webhook for local)
- The script sends JSON via alert() on long/short/exit with the fields below.

Webhook JSON (example)
```
{
  "secret": "<your-secret>",
  "symbol": "AAPL",
  "timeframe": "D",
  "side": "long",
  "entry": 189.42,
  "stop": 183.70,
  "tp1": 198.10,
  "zScore": 1.27,
  "rsPct": 0.68,
  "rvol": 1.34,
  "source": "AMS-NX",
  "ts": 1739577600000
}
```

Listener behavior (after wiring)
- Accepts both legacy and AMS‑NX payloads
- Gates on trading window, watchlist, rsPct/rvol/zScore (when provided)
- Creates pending intents with metrics for audit; can place bracket or market orders on approval

---

## Tuning Guidelines
- Too many marginal entries: Raise Z enter to 1.2, increase Min distance to stop to 1.0 ATR, keep screener tie‑in ON.
- Missing strong trends: Reduce Z enter to 0.8, set HTF Weight to 0.2, increase Ready window to 15 days.
- Choppy whip‑outs: Increase ATR Mult to 3.5–4.0, enable partials (TP1 at 1.5R), keep fail‑safe 15%.

---

## Validation Checklist (Quick)
- Symbols: SPY, QQQ, NVDA, AAPL, AMD, XOM, KO, SMCI
- Confirm: Entries only appear on symbols that are LongReady/ShortReady in last 10 days
- Confirm: Trail stop ratchets only (never down on longs / up on shorts)
- Confirm: TP1 moves stop to BE when hit (if enabled)
- Confirm: Alerts deliver JSON (listener shows metrics in pending intent)

---

## Advanced Options (later)
- Per‑symbol tick sizes for futures/FX/crypto (extend listener)
- Earnings blackout (use screener metadata once earnings feed added)
- Sector RS bands and exposure constraints (avoid over‑concentration)

