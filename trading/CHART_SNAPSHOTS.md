# Chart Snapshots for Trade Journaling

## Why Capture Charts?

When reviewing trades later, you want to see **exactly what the chart looked like** when you made the decision. Memory fades, but screenshots don't.

---

## How to Add Chart URLs to Alerts

### Option 1: Manual Screenshot (Current)

When you receive an alert in Telegram:
1. Click the TradingView link (if your alert includes one)
2. Take a screenshot of the chart
3. Save to `trading/charts/{ticker}_{date}.png`

### Option 2: TradingView Chart URL (Future Enhancement)

TradingView doesn't provide automatic chart snapshots in webhook payloads, but you can:

1. **Take snapshot in TradingView**:
   - Right-click chart → "Take Snapshot"
   - Get public snapshot URL

2. **Add to alert message**:
   ```json
   {
     "chart_url": "https://www.tradingview.com/x/ABC123/"
   }
   ```

3. **System saves it**: Webhook listener logs the URL with the trade

### Option 3: Automated Screenshots (Advanced)

Use TradingView's screenshot API (requires paid plan):
- Capture chart at alert time
- Upload to cloud storage (S3, Imgur, etc.)
- Include URL in webhook payload

---

## Viewing Historical Charts

All chart URLs are saved in trade logs:

```bash
# View chart for a specific trade
cat trading/logs/{trade-id}.json | jq '.intent.chart_url'

# List all trades with chart URLs
for f in trading/logs/*.json; do 
  echo "$f: $(jq -r '.intent.chart_url // "no chart"' $f)"
done
```

---

## Future: Browser Automation

Could add Playwright/Puppeteer to:
1. Receive alert with ticker + timeframe
2. Open TradingView programmatically
3. Navigate to chart
4. Take screenshot
5. Save to `trading/charts/` directory

**Trade-off**: Adds complexity vs. manual screenshots when needed.

---

## Current Setup

Charts are **optional but recommended** for:
- Reviewing losing trades (what did I miss?)
- Pattern recognition (what setups work best?)
- Training (show others your best trades)
- Auditing (prove you saw what you thought you saw)

The system logs chart URLs if provided, but doesn't require them.
