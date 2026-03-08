# VIX Circuit Breaker System

A comprehensive volatility-based position sizing and risk management system for automated trading. Dynamically adjusts position sizes, stop-loss levels, and entry rules based on real-time VIX data.

## ✨ Features

- **Real-time VIX Monitoring** - Fetches VIX every 30 minutes during market hours
- **5 Volatility Regimes** - Normal, Caution, Reduced, Panic, Emergency
- **Dynamic Position Sizing** - Automatically reduces size based on VIX levels
- **Stop Tightening** - Adjusts stops from 2.5% (normal) to 0.5% (emergency)
- **Entry Controls** - Blocks new entries during high volatility
- **Emergency Liquidation** - Automatically liquidates at VIX > 25
- **Telegram Alerts** - Real-time notifications of regime changes
- **Event Logging** - Complete audit trail of all circuit breaker events

## 📁 File Structure

```
trading/
├── vix_monitor.py              # VIX data fetching & regime tracking
├── circuit_breaker.py          # Core circuit breaker logic
├── vix_daemon.py               # Background monitoring daemon
├── test_circuit_breaker.py     # Testing & status script
├── stop_manager.py             # (PATCHED) Stop-loss with CB integration
├── webhook_listener.py         # (PATCHED) Alert handler with CB checks
└── VIX_CIRCUIT_BREAKER_README.md # This file
```

## 🎯 VIX Regimes

### Normal Mode (VIX < 15)
- **Position Size**: 100%
- **Stop Percentage**: 2.5%
- **Entry**: Allowed
- **Scaling**: Allowed

### Caution Mode (VIX 15-18)
- **Position Size**: 80%
- **Stop Percentage**: 1.8%
- **Entry**: Allowed
- **Scaling**: Allowed

### Reduced Mode (VIX 18-20)
- **Position Size**: 50%
- **Stop Percentage**: 1.0%
- **Entry**: Blocked (prevent new entries, hold existing)
- **Scaling**: Blocked
- **Action**: Close weakest 25% of positions

### Panic Mode (VIX 20-25)
- **Position Size**: 0% (pause new entries)
- **Stop Percentage**: 0.5%
- **Entry**: Blocked
- **Scaling**: Blocked
- **Action**: Close weakest 50% of positions

### Emergency Mode (VIX > 25)
- **Position Size**: 0%
- **Stop Percentage**: 0.5%
- **Entry**: Blocked
- **Scaling**: Blocked
- **Action**: Liquidate ALL positions immediately

## 📊 Position Sizing

When VIX > 18, position size is dynamically reduced:

```
Reduction % = (VIX - 18) × 5%

Examples:
- VIX 18: 0% reduction (100% sizing)
- VIX 19: 5% reduction (95% sizing)
- VIX 20: 10% reduction (90% sizing)
- VIX 22: 20% reduction (80% sizing)
- VIX 25: 35% reduction (65% sizing)
```

## 🚀 Getting Started

### 1. Install Dependencies

```bash
pip install yfinance requests pytz
```

### 2. Test the System

```bash
cd /Users/pinchy/.openclaw/workspace/trading
python3 test_circuit_breaker.py
```

Expected output shows:
- ✅ Current VIX level and regime
- ✅ Entry permission based on circuit breaker
- ✅ Weak position closeout triggers
- ✅ Emergency liquidation checks
- ✅ Position sizing adjustments
- ✅ Stop-loss tightening

### 3. Start the VIX Daemon

```bash
python3 vix_daemon.py &
```

The daemon will:
- Fetch VIX every 30 minutes during market hours
- Update circuit breaker status
- Send Telegram alerts on regime changes
- Log all events to `logs/vix_daemon.log`

### 4. Configure Telegram (Optional)

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
```

## 🔌 Integration Points

### webhook_listener.py

The webhook listener is patched to:
1. **Check circuit breaker** before entry
2. **Block entry** if VIX regime prevents it
3. **Adjust position size** if VIX > 18
4. **Apply stop tightening** to all orders
5. **Format alerts** with circuit breaker status

Example alert with circuit breaker:
```
⛔ CIRCUIT BREAKER: Entry BLOCKED - Volatility regime prevents new entries
   Regime: Reduced Mode (50% sizing) (VIX: 18.63)
```

### stop_manager.py

The stop manager is patched to:
1. **Calculate base risk** (2% default or sector override)
2. **Query circuit breaker** for regime-based stops
3. **Apply tighter stop** if circuit breaker demands it
4. **Log circuit breaker** application in order metadata
5. **Track** original vs. applied risk percentage

Example in order metadata:
```json
{
  "risk_pct": 0.025,
  "applied_risk_pct": 0.01,
  "circuit_breaker_applied": true,
  "circuit_breaker_info": {
    "regime": "reduced",
    "stop_percent": 0.01,
    "vix": 18.63
  }
}
```

## 📝 API Reference

### VIXMonitor

```python
from vix_monitor import get_vix_monitor

monitor = get_vix_monitor()

# Fetch latest VIX
update = monitor.update()
# Returns: {
#   'vix': 18.63,
#   'previous_vix': 18.5,
#   'regime': 'reduced',
#   'trend': 'stable',
#   'regime_changed': False,
#   'alert_messages': [...]
# }

# Get current status
status = monitor.get_status()
# Returns: {
#   'current_vix': 18.63,
#   'regime': 'reduced',
#   'trend': 'stable',
#   'regime_info': 'Reduced Mode (50% sizing)'
# }
```

### CircuitBreaker

```python
from circuit_breaker import get_circuit_breaker

breaker = get_circuit_breaker()

# Check if entry allowed
can_enter, details = breaker.can_enter_position('AAPL')
# Returns: (False, {'allowed': False, 'regime': 'reduced', 'vix': 18.63, ...})

# Calculate position size adjustment
adjusted_size, details = breaker.calculate_position_size_multiplier(100)
# Returns: (97, {'multiplier': 0.97, 'reduction_pct': 3.1, ...})

# Calculate stop-loss percentage
stop_pct, details = breaker.calculate_stop_percent()
# Returns: (0.01, {'regime': 'reduced', 'stop_percent': 0.01, 'vix': 18.63})

# Get full entry adjustment
adjustment = breaker.get_entry_adjustment(100, 'AAPL')
# Returns: {
#   'allowed': False,
#   'adjusted_size': 0,
#   'stop_percent': 0.01,
#   'regime': 'reduced',
#   'vix': 18.63,
#   'regime_info': 'Reduced Mode (50% sizing)'
# }

# Check comprehensive status
status = breaker.check_circuit_breaker()
# Returns: {
#   'regime': 'reduced',
#   'vix': 18.63,
#   'can_enter': False,
#   'should_close_weak': True,
#   'should_liquidate': False,
#   'position_size_mult': 0.5,
#   'stop_percent': 0.01
# }
```

## 📊 Log Files

### VIX History
**Location**: `logs/vix_history.json`

Tracks last 100 VIX readings with timestamps and regimes.

### Circuit Breaker Events
**Location**: `logs/circuit_breaker_events.json`

Logs all circuit breaker events:
- Entry blocks
- Position size adjustments
- Stop tightening
- Weak position closeouts
- Emergency liquidations

### VIX State
**Location**: `logs/vix_state.json`

Current VIX state:
- Current VIX value
- Previous VIX value
- Current regime
- Previous regime
- Last fetch time

### Daemon Log
**Location**: `logs/vix_daemon.log`

Real-time daemon operations and alerts.

## 🧪 Testing

Run comprehensive system test:

```bash
python3 test_circuit_breaker.py
```

This tests:
- ✅ VIX fetching
- ✅ Regime detection
- ✅ Entry permission
- ✅ Weak position closeout
- ✅ Emergency liquidation
- ✅ Position sizing
- ✅ Stop tightening
- ✅ Full entry adjustment

## 🚨 Production Readiness

Before going live, verify:

1. **VIX Data**: Run `test_circuit_breaker.py` and confirm VIX fetches successfully
2. **Telegram**: Set environment variables and test alert delivery
3. **Integration**: Verify stop_manager and webhook_listener patches are loaded
4. **Daemon**: Start `vix_daemon.py` and monitor logs
5. **Backtesting**: Test with paper trading before live trading

## 🎮 Example Usage

### In Your Trading Application

```python
from circuit_breaker import get_circuit_breaker
from stop_manager import StopLossManager

# Initialize
breaker = get_circuit_breaker()
stop_manager = StopLossManager()

# Check entry signals
signal = screener.get_buy_signal()
if signal:
    symbol = signal['symbol']
    entry_price = signal['price']
    base_qty = signal['quantity']
    
    # Check circuit breaker
    adjustment = breaker.get_entry_adjustment(base_qty, symbol)
    
    if adjustment['allowed']:
        # Enter position with adjusted size
        actual_qty = adjustment['adjusted_size']
        entry_order = broker.buy(symbol, actual_qty, entry_price)
        
        # Place stop with circuit breaker stops
        stop_manager.connect()
        stop_manager.place_stop(
            symbol,
            entry_price,
            actual_qty,
            risk_pct=adjustment['stop_percent']
        )
        stop_manager.disconnect()
    else:
        print(f"Circuit breaker blocked: {adjustment['regime_info']} (VIX={adjustment['vix']})")
```

### Monitoring Regime Changes

```python
from vix_monitor import get_vix_monitor

monitor = get_vix_monitor()

# Check for regime changes
update = monitor.update()

if update['regime_changed']:
    # Trigger position adjustments
    for alert in update['alert_messages']:
        print(f"[ALERT] {alert}")
        send_to_telegram(alert)
    
    # If entering Panic or Emergency, close positions
    breaker = get_circuit_breaker(monitor)
    if breaker.should_liquidate_all()[0]:
        close_all_positions()
    elif breaker.should_close_weak_positions()[0]:
        close_weakest_50_percent()
```

## 📈 Configuration

### Modify Regimes (optional)

Edit `circuit_breaker.py` `CIRCUIT_BREAKER_CONFIG`:

```python
CIRCUIT_BREAKER_CONFIG = {
    'normal': {
        'position_size_mult': 1.0,
        'stop_percent': 0.025,
        'allow_entries': True,
        'allow_scaling': True,
    },
    # ... etc
}
```

### Modify VIX Thresholds (optional)

Edit `vix_monitor.py` `VIX_THRESHOLDS`:

```python
VIX_THRESHOLDS = {
    'normal': (0, 15),
    'caution': (15, 18),
    'reduced': (18, 20),
    'panic': (20, 25),
    'emergency': (25, 100),
}
```

### Modify Fetch Interval (optional)

Edit `vix_daemon.py` `FETCH_INTERVAL`:

```python
FETCH_INTERVAL = 1800  # 30 minutes in seconds
```

## ⚠️ Important Notes

1. **VIX Fetching**: Uses yfinance which is rate-limited. Fetches every 30 minutes to avoid throttling.

2. **Market Hours**: Only fetches during 9:30 AM - 4:00 PM ET, Monday-Friday

3. **Telegram Optional**: If Telegram credentials not set, alerts are logged only

4. **IB Gateway Required**: Stop manager needs IB Gateway running for actual order placement

5. **Paper Trading**: Test thoroughly in paper trading before enabling live trading

6. **Emergency Mode**: When VIX > 25, positions WILL be liquidated. Ensure this is acceptable.

## 🐛 Troubleshooting

### VIX Fetch Fails
- Check internet connection
- Verify yfinance can reach Yahoo Finance
- Check for rate limiting (wait 1 hour)

### Circuit Breaker Not Activating
- Verify VIX daemon is running: `ps aux | grep vix_daemon`
- Check VIX state file: `cat logs/vix_state.json`
- Manually test: `python3 test_circuit_breaker.py`

### Telegram Alerts Not Sending
- Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set
- Test with: `curl -X POST https://api.telegram.org/bot<TOKEN>/sendMessage -d "chat_id=<ID>&text=test"`

### Orders Not Using Circuit Breaker Stops
- Verify stop_manager.py patch is applied
- Check order metadata includes `circuit_breaker_info`
- Review stop_manager logs for errors

## 📞 Support

For issues or questions:
1. Check logs in `logs/` directory
2. Run `test_circuit_breaker.py` for diagnostics
3. Review this README for configuration options

## 🎯 Success Metrics

System is working correctly when:
- ✅ VIX updates every 30 minutes during market hours
- ✅ Regime changes trigger alerts on Telegram
- ✅ Entry is blocked when VIX > 18
- ✅ Position sizes are reduced when VIX > 18
- ✅ Stops are tightened based on VIX regime
- ✅ Weak positions are closed in Reduced/Panic modes
- ✅ All positions liquidate at VIX > 25
- ✅ All events are logged with timestamps

---

**Version**: 1.0  
**Last Updated**: 2026-02-26  
**Status**: Production Ready
