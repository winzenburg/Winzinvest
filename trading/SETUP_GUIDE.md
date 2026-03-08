# TradingView → Interactive Brokers Setup Guide

## ✅ Completed
- [x] Python dependencies installed (ib_insync, flask, etc.)
- [x] `.env` file created with webhook secret
- [x] Startup script created

## 🔧 Next Steps

### 1. Install IB Gateway (Desktop App)

**Download:** https://www.interactivebrokers.com/en/trading/ibgateway-stable.php

**After installation:**
1. Launch IB Gateway from `/Applications/`
2. Log in with your **paper trading** credentials
3. In the API settings:
   - ✅ Enable ActiveX and Socket Clients
   - Port: **7497** (paper trading)
   - ✅ Allow connections from localhost
   - Socket port: 7497
   - ❌ Read-Only API (uncheck this)

**Test the connection:**
```bash
nc -z 127.0.0.1 7497 && echo "✅ IB Gateway reachable" || echo "❌ Not connected"
```

---

### 2. Start the Webhook Listener

Once IB Gateway is running:
```bash
cd ~/.openclaw/workspace/trading
./start_listener.sh
```

You should see:
```
🚀 Starting webhook listener on http://127.0.0.1:5001
📊 Webhook endpoint: http://127.0.0.1:5001/webhook
💓 Health check: http://127.0.0.1:5001/health
```

**Health check:**
```bash
curl http://127.0.0.1:5001/health
# Expected: {"ok":true,"service":"webhook-listener"}
```

---

### 3. Configure TradingView Alerts

In your TradingView Pine Script indicators:

**Alert message JSON:**
```json
{
  "secret": "yPLn-BfFFWVe1vkrXE7qgkUgRjlqGRlsQGBYsIquC80",
  "ticker": "{{ticker}}",
  "timeframe": "{{interval}}",
  "signal": "buy",
  "price": {{close}},
  "setup_type": "swing_trading_fast",
  "stop_loss": 150.00,
  "take_profit": 165.00
}
```

**Webhook URL:** `http://127.0.0.1:5001/webhook`

⚠️ **Note:** This only works if TradingView can reach your machine. For cloud alerts, you'll need:
- ngrok/Cloudflare Tunnel to expose the endpoint
- Update `BASE_URL` in `.env`

---

### 4. Test with a Mock Alert (Optional)

```bash
curl -X POST http://127.0.0.1:5001/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "secret": "yPLn-BfFFWVe1vkrXE7qgkUgRjlqGRlsQGBYsIquC80",
    "ticker": "AAPL",
    "timeframe": "15",
    "signal": "buy",
    "price": 175.50,
    "setup_type": "swing_trading_fast"
  }'
```

Expected response:
```json
{"status":"pending","id":"1708218234-abc123"}
```

Check pending orders:
```bash
ls trading/pending/
```

---

### 5. Approve Orders (Manual for Now)

**Approve via POST:**
```bash
curl -X POST http://127.0.0.1:5001/approve \
  -H "Content-Type: application/json" \
  -d '{
    "secret": "yPLn-BfFFWVe1vkrXE7qgkUgRjlqGRlsQGBYsIquC80",
    "id": "1708218234-abc123"
  }'
```

**Reject via POST:**
```bash
curl -X POST http://127.0.0.1:5001/reject \
  -H "Content-Type: application/json" \
  -d '{
    "secret": "yPLn-BfFFWVe1vkrXE7qgkUgRjlqGRlsQGBYsIquC80",
    "id": "1708218234-abc123"
  }'
```

---

## 🔐 Security Notes

1. **Never commit `.env` to git** (already in .gitignore)
2. **Webhook secret** is in `.env` - treat it like a password
3. **Localhost only** for now - no external access
4. **Paper trading only** until you've tested thoroughly

---

## 📊 What Happens When an Alert Fires

1. **TradingView** sends webhook → `POST /webhook`
2. **Filters check:**
   - Is ticker in watchlist?
   - Is RS ratio > threshold?
   - Is volume ratio > 1.3x?
   - Within trading hours?
   - Market regime allows this setup?
3. **If passed:** Intent saved to `trading/pending/`
4. **You approve/reject** (manual or Telegram)
5. **If approved:** Order sent to IB Gateway
6. **Result logged** to `trading/logs/`

---

## 🆘 Troubleshooting

**"Connection refused" to IB Gateway:**
- Make sure IB Gateway is running
- Check port 7497 is open: `lsof -i :7497`
- Verify API is enabled in IB Gateway settings

**"Module not found" errors:**
- Re-run: `pip3 install ib_insync flask jsonschema yfinance`

**Webhook returns 401:**
- Check the secret in your alert JSON matches `.env`

**Orders not executing:**
- Check `trading/pending/` for pending intents
- Check `trading/logs/` for execution logs
- Verify IB Gateway is connected and funded

---

## 🎯 Next: Telegram Integration (Optional)

To get approve/deny buttons in Telegram:

1. Create a bot via @BotFather
2. Get your chat ID
3. Add to `.env`:
   ```
   TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
   TELEGRAM_CHAT_ID=123456789
   BASE_URL=https://your-ngrok-url.ngrok.io
   ```

---

Ready to rock! 🚀
