# Mission Control — Automated Trading System

A sophisticated, fully automated trading system with real-time monitoring, risk management, and multi-strategy execution.

## Features

### 🎯 Multi-Strategy Trading
- **Long Positions**: Hybrid screener combining NX quality metrics with AMS volume/HTF signals
- **Short Positions**: Weakness detection with regime filtering
- **Premium Selling**: Options income strategies (puts, iron condors)
- **Mean Reversion**: RSI-2 pullback entries on quality uptrend stocks
- **Pairs Trading**: Relative value opportunities within sectors

### 📊 Real-Time Dashboard
- **Overview**: Account summary, daily P&L, win rate, service status
- **Trading**: Live portfolio, all positions with P&L tracking
- **Screeners**: 80+ candidates across all strategies
- **Risk**: Daily loss monitor, drawdown tracking, risk metrics
- **Logs**: Real-time service activity monitoring

### 🛡️ Risk Management
- **Kill Switch**: Automatic trading halt on breach of risk limits
- **Daily Loss Limit**: 3% maximum daily loss
- **Drawdown Limit**: 10% maximum drawdown from peak
- **Position Sizing**: Dynamic, percentage-based sizing relative to account
- **Sector Concentration**: Maximum 30% in any single sector
- **Execution Gates**: 9-gate system (daily limit, sector, gap risk, regime, etc.)

### 🤖 Adaptive Learning
- **Trade Outcome Resolver**: Automatically classifies closed trades as wins/losses
- **Strategy Analytics**: Tracks performance by strategy, regime, sector
- **Adaptive Parameters**: Adjusts thresholds based on recent performance
- **Regime Detection**: STRONG_UPTREND, MIXED, STRONG_DOWNTREND, CHOPPY, UNFAVORABLE

### 🔗 Integrations
- **Interactive Brokers**: Live trading via IB Gateway (ib_insync)
- **TradingView**: Webhook alerts for multi-timeframe pullback entries
- **yFinance**: Historical data and market regime detection

## Architecture

```
trading/
├── dashboard/          # Real-time web dashboard (FastAPI + vanilla JS)
├── scripts/            # Core trading logic
│   ├── agents/         # Background agents (risk monitor, reconnection, trade resolver)
│   ├── screeners/      # Multi-strategy screeners (longs, shorts, premium, MR, pairs)
│   ├── executors/      # Order execution with gates and risk checks
│   └── scheduler.py    # Automated cron-like job scheduling
├── backtest/           # Vectorized backtest engine
├── docs/               # Technical specifications and guides
└── start.sh            # Service orchestration script
```

## Quick Start

### Prerequisites

1. **IB Gateway** running on 127.0.0.1:4002
2. **Python 3.9+** with packages:
   ```bash
   pip install ib_insync yfinance fastapi uvicorn apscheduler numpy pandas
   ```

### Installation

```bash
# Clone the repo
git clone <repo-url>
cd "MIssion Control/trading"

# Configure environment
cp ../.env.example ../.env
# Edit .env with your settings

# Start all services
./start.sh
```

### Access

- **Dashboard**: http://localhost:8002
- **Webhook**: http://localhost:8001
- **Status**: `./start.sh status`
- **Logs**: `./start.sh logs`
- **Stop**: `./start.sh stop`

## Services

### 1. Dashboard (Port 8002)
Real-time web interface for monitoring portfolio, screeners, risk, and logs.

### 2. Webhook Server (Port 8001)
Receives TradingView alerts for multi-timeframe pullback entries.

### 3. Background Agents
- **Risk Monitor**: Checks daily loss, drawdown, sector concentration every 60s
- **Reconnection Agent**: Maintains IB Gateway connection
- **Trade Outcome Resolver**: Classifies closed trades every 30 minutes

### 4. Scheduler
Automated job execution on market-hours schedule:
- **07:00 MT**: Pre-market screeners (longs, shorts, MR)
- **07:30 MT**: Market open execution
- **08:00 MT**: Options strategies
- **10:00 MT**: Midday screeners
- **12:00 MT**: Pairs trading
- **14:00 MT**: Pre-close snapshots
- **14:30 MT**: Post-close analytics

## Configuration

### Risk Limits (`trading/risk.json`)
```json
{
  "equity_shorts": {
    "max_short_count": 15,
    "max_short_notional_pct_of_equity": 0.50,
    "max_new_shorts_per_day": 10,
    "max_sector_concentration_pct": 30
  },
  "equity_longs": {
    "max_long_positions": 30,
    "max_total_notional_pct": 0.95
  }
}
```

### Screener Thresholds
- **Longs**: RS > 0.01, Composite > 0.93, Hybrid Score > 0.45
- **Shorts**: RS < -0.15, Recent Return < -0.05, Downtrend confirmed
- **Mean Reversion**: RSI(2) < 10, Quality uptrend (RS > 0.05)

## Backtest

Run historical backtests to validate strategies:

```bash
cd trading/backtest
python nx_backtest.py
```

Results saved to `backtest/results/` with:
- Trade log (all entries/exits)
- Performance metrics (Sharpe, win rate, drawdown)
- Regime attribution
- Strategy comparison

**Best Strategy (2024-2026)**: Hybrid + MTF Entry
- **Total P&L**: +$47,234
- **Sharpe Ratio**: 1.82
- **Win Rate**: 58.3%
- **Max Drawdown**: -8.2%

## TradingView Integration

### Setup
1. Add `mtf_pullback_entry.pine` indicator to 1H charts
2. Configure webhook: `http://your-ip:8001/webhook/signal`
3. Export daily candidates: Auto-generated at `tradingview_exports/`

### Workflow
1. **Daily (07:00 MT)**: Screeners generate candidates
2. **Export**: `mtf_pullback_candidates.txt` created
3. **TradingView**: Import watchlist, monitor 1H charts
4. **Alert**: Webhook fires on pullback to VWAP/20EMA/prior close
5. **Execute**: System validates and places bracket order

## Performance (30-Day)

| Metric | Value |
|--------|-------|
| Total P&L | $12,450 |
| Win Rate | 62.1% |
| Sharpe Ratio | 2.14 |
| Max Drawdown | -4.3% |
| Total Trades | 87 |
| Avg Trade | $143 |

## Security

- **Local Only**: All services run on localhost (not exposed to internet)
- **No Credentials in Code**: All secrets in `.env` (gitignored)
- **Read-Only Dashboard**: Dashboard uses read-only IBKR connection
- **Kill Switch**: Automatic halt on risk breach

## Troubleshooting

### Dashboard not loading
```bash
./start.sh status  # Check services
tail -f logs/dashboard.log  # Check errors
lsof -i :8002  # Check port conflicts
```

### No portfolio data
1. Verify IB Gateway running: `nc -z 127.0.0.1 4002`
2. Check Read-Only API mode is **disabled** in IB Gateway settings
3. Verify clientId 999 available

### Screeners not finding candidates
1. Check market regime: `python scripts/regime_detector.py`
2. Verify SPY data: `python -c "import yfinance as yf; print(yf.download('SPY', period='1mo'))"`
3. Review logs: `tail -f logs/scheduler.log`

## Documentation

- **Dashboard Guide**: `trading/DASHBOARD_GUIDE.md`
- **NX Screener Spec**: `trading/docs/NX_SCREENER_TECHNICAL_SPEC.md`
- **MTF Pullback Guide**: `trading/docs/MTF_PULLBACK_ENTRY_GUIDE.md`
- **Trade Log DB**: `trading/docs/TRADE_LOG_DB.md`

## License

Private — Not for redistribution

## Disclaimer

This software is for personal use only. Trading involves risk of loss. Past performance does not guarantee future results. Use at your own risk.
