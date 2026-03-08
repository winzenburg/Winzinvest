# TradingView Alert Configuration

**Status:** Needs verification/setup before Monday  
**Critical:** No trades without this

---

## 🎯 WHAT YOU NEED

1. **TradingView Premium Account** ✅ (you have)
2. **AMS Trade Engine NX Indicator** ✅ (deployed)
3. **Cloudflare Tunnel Running** ⚠️ (verify)
4. **Alert Configured in TradingView** ⚠️ (needs setup)

---

## INFRASTRUCTURE

### Webhook Listener
- **Status:** ✅ Running (PID 92140)
- **Port:** 5001 (localhost)
- **Endpoint:** `/webhook`

### Cloudflare Tunnel
- **Public URL:** `https://describing-achievements-mercy-resorts.trycloudflare.com`
- **Maps to:** `http://127.0.0.1:5001` (localhost)
- **Status:** ⚠️ **NEEDS VERIFICATION**

### Flow
```
TradingView
   ↓
Cloudflare Tunnel
   ↓
Webhook Listener (5001)
   ↓
IB Gateway (execute order)
   ↓
Telegram (notify)
```

---

## STEP 1: VERIFY CLOUDFLARE TUNNEL

**Check if tunnel is running:**
```bash
# List active cloudflare tunnels
cloudflared tunnel list

# If not running, start it
cloudflared tunnel run --url http://localhost:5001 describing-achievements-mercy-resorts
```

**Test tunnel:**
```bash
curl https://describing-achievements-mercy-resorts.trycloudflare.com/health
# Should return: {"ok":true,"service":"webhook-listener"}
```

**If tunnel is down:**
- The tunnel URL was created but may have expired
- Run: `cloudflared tunnel run --url http://localhost:5001 [tunnel-name]`
- Get a new public URL from Cloudflare dashboard
- Update BASE_URL in `.env`

---

## STEP 2: SET UP TRADINGVIEW ALERT

### Location in TradingView

1. **Open your chart** with AMS Trade Engine NX indicator applied
2. **Click the bell icon** (Alerts) in top toolbar
3. **Create Alert** (or edit existing)

### Alert Configuration

**Alert Name:**
```
AMS Trade Signal
```

**Condition:**
```
AMS Trade Engine NX → Entry Signal → Entry is true
```

**Message (Webhook payload):**
```json
{
  "symbol": "{{ticker}}",
  "price": "{{close}}",
  "direction": "{{strategy.order.action}}",
  "time": "{{timenow}}",
  "entry_z": "2.0",
  "stop_atr": "1.5"
}
```

**Notifications Tab:**
- Uncheck: Email, SMS, popup
- Check: **Webhook URL**
  
**Webhook URL:**
```
https://describing-achievements-mercy-resorts.trycloudflare.com/webhook
```

**Note:** You need to set the MOLT_WEBHOOK_SECRET in your webhook listener if using authentication.

---

## STEP 3: TEST THE ALERT

### Manual Test (No Market Data)

```bash
# Test webhook directly
curl -X POST https://describing-achievements-mercy-resorts.trycloudflare.com/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "price": "180.50",
    "direction": "long",
    "time": "2026-02-21 10:30:00",
    "entry_z": "2.0",
    "stop_atr": "1.5"
  }'
```

**Expected response:**
```json
{
  "status": "pending",
  "order_id": "[UUID]",
  "message": "Trade pending approval. Check Telegram."
}
```

### Check Telegram

After test above:
- You should get a Telegram message from @pinchy_trading_bot
- Message shows: Symbol, direction, price, stop, target
- Two buttons: ✅ APPROVE or ❌ REJECT

**If you don't get Telegram message:**
- Check TELEGRAM_BOT_TOKEN in `.env`
- Check TELEGRAM_CHAT_ID in `.env`
- Verify bot is active: https://t.me/pinchy_trading_bot

### Check Logs

```bash
tail -50 ~/.openclaw/workspace/trading/logs/webhook_listener.log
```

Look for:
- `POST /webhook` received
- `Pending order created`
- `Telegram alert sent`

---

## STEP 4: VERIFY WORKFLOW (LIVE ALERT TEST)

**Do this Friday afternoon (after market close):**

1. **Manually trigger alert in TradingView**
   - Right-click on chart
   - "Trigger alert for this symbol"

2. **Verify webhook receives it**
   - Check logs: `tail -f ~/.openclaw/workspace/trading/logs/webhook_listener.log`
   - Should see: `POST /webhook received`

3. **Verify Telegram notifies**
   - Should get message within 10 seconds
   - Buttons show: ✅ APPROVE / ❌ REJECT

4. **Test approval flow**
   - Click ✅ APPROVE in Telegram
   - Verify order placed in IB paper account
   - Check IB Gateway logs

---

## TROUBLESHOOTING

### Problem: "Webhook URL not found" (404)

**Cause:** Wrong URL or tunnel down

**Fix:**
```bash
# Verify tunnel is running
cloudflared tunnel list

# Test endpoint
curl https://describing-achievements-mercy-resorts.trycloudflare.com/health
# Should return: {"ok":true,"service":"webhook-listener"}

# If 404, restart tunnel
pkill cloudflared
cloudflared tunnel run --url http://localhost:5001 [tunnel-name]
```

### Problem: Alert fires but no Telegram message

**Cause:** Telegram bot token/chat ID wrong

**Fix:**
```bash
# Check .env
grep TELEGRAM ~/.openclaw/workspace/trading/.env

# Test Telegram manually
curl -s -X POST \
  -d "chat_id=5316436116&text=Test" \
  "https://api.telegram.org/bot8565359157:AAE3cA0Tn2OE62K2eaXiXYr1SFqAFkNtzMQ/sendMessage"
# Should return: {"ok":true...}

# If fails, regenerate bot token at @BotFather on Telegram
```

### Problem: Alert fires but no order placed

**Cause:** IB Gateway not connected on port 4002

**Fix:**
```bash
# Verify IB Gateway running
nc -zv 127.0.0.1 4002
# Should say: succeeded

# If fails, restart IB Gateway and check port
# From IB Gateway UI: Configure → Socket Port → set to 4002
```

### Problem: Cloudflare Tunnel URL keeps changing

**Cause:** Using temporary tunnel, not persistent tunnel

**Fix:**
1. Create **named tunnel** in Cloudflare dashboard
2. Use persistent URL: `https://[your-permanent-name].trycloudflare.com`
3. Update `.env` BASE_URL with permanent URL
4. Update TradingView webhook URL

---

## CHECKLIST FOR MONDAY

- [ ] Cloudflare tunnel running (`cloudflared tunnel list` shows active)
- [ ] Webhook listener running (`ps aux | grep webhook_listener`)
- [ ] Health check passes (`curl http://127.0.0.1:5001/health`)
- [ ] IB Gateway connected on port 4002
- [ ] TradingView alert created with correct webhook URL
- [ ] Test alert sent (manual trigger Friday)
- [ ] Telegram message received
- [ ] Approval flow tested (order shows in IB)
- [ ] Logs show no errors

---

## PRODUCTION CHECKLIST

Once live (after first 3 trades):

- [ ] Monitor webhook logs continuously
- [ ] Verify every alert reaches Telegram within 10 seconds
- [ ] Verify every approval executes order within 5 seconds
- [ ] Monitor for any missed alerts (none should be lost)

---

## IMPORTANT NOTES

### AUTO_APPROVE=false (Current Setting)
- Alerts come to Telegram, require manual approval
- Safety: You decide before order executes
- Latency: Extra 30 seconds for human approval

### To Enable AUTO_EXECUTE (Week 3+)
- Change `AUTO_APPROVE=true` in `.env`
- Orders execute immediately, no Telegram approval needed
- Risk: Faster execution, but no human review
- Only after proving strategy works (Week 1-2 testing)

### Canary Mode (Current Setting)
- All orders start at 1 share (CANARY=1)
- Once position validates (3+ days, profitable), can scale
- Safety: Minimal loss if thesis wrong

---

**CRITICAL:** TradingView alert must be working before 9:30 AM Monday.

If you need help setting up before Monday, message now.
