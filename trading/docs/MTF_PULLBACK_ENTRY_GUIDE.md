# Hybrid + MTF Pullback Entry Strategy

## Performance (Backtested 2024-03 to 2026-03)

| Metric | Value |
|--------|-------|
| P&L | $419,381 |
| Sharpe Ratio | 3.78 |
| Win Rate | 51.8% |
| Profit Factor | 1.60 |
| Max Drawdown | 5.2% |
| Annualized Return | 34.1% |

## How It Works

The strategy combines NX daily screening with intraday 1H pullback entries
for 0.2–0.5 ATR better entries than market-open fills.

```
[Daily Screener] → [Export Candidates] → [TradingView 1H Monitor]
                                                ↓
                    [IBKR Execution] ← [Webhook Server] ← [Pullback Alert]
```

### Phase 1: Daily Screening (7:30 AM MT)

The NX Long Screener (`nx_screener_longs.py`) runs daily:

1. Builds universe of ~1,500 liquid US equities
2. Applies NX quality filters (RS > SPY, price above MAs, structure quality)
3. Ranks by Hybrid score (NX quality × AMS volume/HTF momentum)
4. Exports top candidates to `watchlist_longs.json`
5. **Automatically exports to TradingView format** (`export_tv_watchlist.py`)

### Phase 2: TradingView Monitoring (All Day)

The MTF Pullback Entry Pine Script (`mtf_pullback_entry.pine`) runs on 1H charts:

1. Applied to each screened candidate on a TradingView 1H chart
2. Monitors for pullbacks to key support levels:
   - **VWAP** — intraday value area
   - **20 EMA** — short-term trend support
   - **Prior day's close** — psychological level
3. Requires bounce confirmation (close above support + minimum bounce distance)
4. Volume must be at least 70% of 20-bar average
5. Daily trend filter ensures the stock is above its daily 50 SMA
6. 8-bar cooldown between signals prevents overtrading

### Phase 3: Webhook Execution

When TV fires a pullback alert:

1. JSON payload hits `POST /webhook/tradingview` on the webhook server
2. `entry_type: "pullback"` routes to specialized handler
3. `execute_webhook_signal.py` processes with **tighter stops**:
   - Standard entry: 1.5 ATR stop, 2.5 ATR TP
   - **Pullback entry: 1.0 ATR stop, 2.5 ATR TP** (better R:R since entry is cheaper)
4. Trailing stop (1.5 ATR) replaces hard stop for longs — locks in gains
5. All standard risk gates still enforced (daily limit, sector cap, regime, notional)

## Setup Instructions

### 1. Run the Daily Screener

```bash
cd trading/scripts
python3 nx_screener_longs.py
```

This automatically calls `export_tv_watchlist.py`, which creates:
- `trading/tradingview_exports/mtf_pullback_candidates.txt` — TradingView importable
- `trading/tradingview_exports/mtf_pullback_candidates.json` — API format

### 2. Import Watchlist into TradingView

**Option A: Manual Import**
1. Open TradingView → Watchlist
2. Import from file → select `mtf_pullback_candidates.txt`
3. The file has one `EXCHANGE:SYMBOL` per line

**Option B: API Endpoint**
```bash
curl http://your-server:8001/candidates/pullback
```
Returns JSON with all candidates, scores, and metadata.

### 3. Add the Pine Script Indicator

1. Open TradingView → Pine Editor
2. Paste contents of `trading/tradingview/mtf_pullback_entry.pine`
3. Add to chart (1H timeframe)
4. Configure inputs:
   - **Webhook Secret**: Your `TV_WEBHOOK_SECRET` value
   - **Pullback EMA Length**: 20 (default)
   - **Max Pullback Depth**: 0.5 ATR (default)
   - **Bounce Confirmation**: 0.15 ATR (default)

### 4. Create TradingView Alerts

For each candidate symbol:
1. Switch to 1H chart for that symbol
2. Right-click → Add Alert
3. Condition: "MTF Pullback Entry" → "MTF Pullback Entry"
4. Action: Webhook URL → `https://your-server:8001/webhook/tradingview`
5. Message: Leave as-is (auto-populated by Pine Script with JSON payload)
6. Expiration: Set to end of week (re-create after weekly screener run)

**Batch Alert Creation (Pro+ required):**
TradingView Pro+ supports alerts on multiple symbols. Apply the indicator
to a watchlist and create alerts for all matching symbols at once.

### 5. Start the Webhook Server

```bash
cd trading/scripts/agents
python3 webhook_server.py
# Or via the agent runner:
python3 -m agents.run_all
```

### 6. Verify the Pipeline

```bash
# Check candidates are exported
cat trading/tradingview_exports/mtf_pullback_candidates.json | python3 -m json.tool

# Check webhook server health
curl http://localhost:8001/webhook/health

# Check candidate endpoint
curl http://localhost:8001/candidates/pullback

# Test a pullback alert (dry run)
curl -X POST http://localhost:8001/webhook/tradingview \
  -H "Content-Type: application/json" \
  -d '{"entry_type":"pullback","symbol":"AAPL","action":"BUY","price":230.50,"timeframe":"1H","support":"VWAP","secret":"YOUR_SECRET"}'
```

## Configuration

### Pine Script Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| Pullback EMA Length | 20 | EMA used as support level |
| ATR Length | 14 | ATR for measuring pullback depth |
| Max Pullback Depth | 0.5 ATR | How far price must dip to trigger |
| Bounce Confirmation | 0.15 ATR | Minimum bounce from low to confirm |
| Require Daily Uptrend | true | Price must be above daily 50 SMA |
| Max Bars in Pullback | 3 | Timeout for pullback zone |
| Cooldown After Signal | 8 bars | Prevents rapid-fire alerts |

### Executor Parameters

| Parameter | Standard Entry | Pullback Entry |
|-----------|---------------|----------------|
| Stop Distance | 1.5× ATR | 1.0× ATR |
| Take Profit | 2.5× ATR | 2.5× ATR |
| Trailing Stop | 2.0× ATR | 1.5× ATR |
| Order Type | Stop + Limit | Trail + Limit |

### Risk Controls

All standard gates still apply:
- Daily trade limit
- Sector concentration cap
- Total notional cap (% of equity)
- Regime alignment check
- Kill switch / daily loss limit
- Max long positions limit

## Automation Schedule

| Time (MT) | Action |
|-----------|--------|
| 7:00 AM | Daily screener runs → exports TV watchlist |
| 7:30 AM | Market open; TV alerts active on 1H charts |
| 7:30 AM–2:00 PM | TV monitors for pullback entries |
| 2:00 PM | Stop accepting new entries (gap risk gate) |
| 2:30 PM | EOD reconciliation |

## Monitoring

Check the execution log for pullback entries:
```bash
grep "mtf_pullback" trading/logs/executions.json | python3 -m json.tool
```

The enriched trade records include:
- `strategy: "mtf_pullback"` — identifies pullback entries
- `entry_type: "pullback"` — vs "standard" for market-open entries
- `support_level: "VWAP" | "EMA20" | "PREV_CLOSE"` — which level triggered
- `timeframe: "1H"` — confirms intraday entry
