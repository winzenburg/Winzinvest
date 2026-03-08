# TradingView Broker Adapter Setup

## What You Have Now

✅ **TradingView Broker Adapter** running on `http://127.0.0.1:5002`
- Implements the full IBrokerTerminal API
- Accepts all trade requests from TradingView
- Routes execution to IBKR via ib_insync
- Paper trading account: DU4661622

✅ **AMS Screeners** running on your TradingView account
- Scans 2,600+ symbol universe daily
- Finds Tier 2 & Tier 3 candidates
- Ready to execute via Broker API

✅ **Extended Hours Support**
- Pre-market (4:00 AM ET)
- Regular Hours (9:30 AM - 4:00 PM ET)
- After-hours (4:00 PM - 8:00 PM ET)

## How to Connect TradingView to Me

### Option 1: Custom Broker Integration (Recommended)
1. In TradingView, use `setCurrentBrokerAccount` with adapter URL: `http://127.0.0.1:5002`
2. TradingView will start sending all orders/positions/executions to me
3. I execute via IBKR and return confirmations

### Option 2: API Integration
TradingView screeners can now call:
```
POST http://127.0.0.1:5002/api/v1/placeOrder
{
  "symbol": "AAPL",
  "side": "buy",
  "quantity": 1,
  "type": "market"
}
```

## Execution Flow

1. **TradingView Screener** finds candidate (e.g., AAPL)
2. **TradingView Chart** user clicks "Trade" or screener auto-executes
3. **TradingView Broker API** sends order to `http://127.0.0.1:5002`
4. **My Adapter** receives order, parses it
5. **ib_insync Executor** places order via IBKR
6. **IBKR** executes in paper trading account DU4661622
7. **My Adapter** returns confirmation to TradingView
8. **TradingView Account Manager** displays position/order

## Status

| Component | Status | Port |
|-----------|--------|------|
| TradingView Broker Adapter | ✅ Running | 5002 |
| IBKR Connection (ib_insync) | ✅ Ready | 4002 |
| Paper Trading Account | ✅ Connected | - |
| AMS Screeners | ✅ Active | TradingView |

## Testing

To test order placement:
```bash
curl -X POST http://127.0.0.1:5002/api/v1/placeOrder \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "side": "buy",
    "quantity": 1,
    "type": "market"
  }'
```

## Logs

Monitor execution in real-time:
```bash
tail -f ~/.openclaw/workspace/trading/logs/tv_broker_adapter.log
```

---

**This is the complete automated trading system.**
- TradingView = Screener + Interface
- Mr. Pinchy = Broker API + Executor
- IBKR = Clearing House
