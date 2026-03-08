# Mission Control Dashboard

Real-time web dashboard for monitoring your automated trading system.

## Features

### Overview Tab
- **Account Summary**: Real-time account value, daily P&L, open positions
- **Performance Metrics**: Win rate, Sharpe ratio, total P&L (30-day)
- **Service Status**: All background services (webhook, agents, scheduler, IB Gateway)
- **Kill Switch Alerts**: Visual alerts when risk limits are breached

### Trading Tab
- **Portfolio Overview**: Account value, cash available, unrealized P&L
- **Active Positions**: Real-time table of all open positions with:
  - Symbol, type (stock/option), quantity
  - Average cost, market price, market value
  - Unrealized and realized P&L

### Screeners Tab
- **Candidate Counts**: Long, short, premium selling, mean reversion
- **Top Candidates**: Best-ranked symbols from each screener
- **Scoring Details**: Composite score, relative strength, volatility metrics

### Risk Tab
- **Daily Loss Monitor**: Current loss vs. limit with visual progress bar
- **Drawdown Monitor**: Current drawdown vs. max (10%) threshold
- **Risk Metrics**: Peak equity, current equity, daily loss percentage

### Logs Tab
- **Real-time Logs**: Live tail of webhook, agents, and scheduler logs
- **Color-coded**: Errors (red), warnings (yellow), info (blue)

## Access

The dashboard runs on **http://localhost:8002** when the system is started.

```bash
# Start the entire system (including dashboard)
./start.sh

# Check status
./start.sh status

# Stop everything
./start.sh stop
```

## Architecture

- **Backend**: FastAPI (Python) serving REST API endpoints
- **Frontend**: Vanilla JavaScript with real-time polling (5-second refresh)
- **Data Sources**:
  - IBKR API (via `ib_insync`) for portfolio and positions
  - Local JSON files for screener results and risk metrics
  - SQLite database for trade history and performance stats
  - Log files for system activity

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Dashboard HTML |
| `GET /api/status` | System status, services, kill switch, risk |
| `GET /api/portfolio` | Portfolio summary and positions |
| `GET /api/screeners` | Latest screener results |
| `GET /api/performance` | 30-day performance statistics |
| `GET /api/logs/{service}` | Recent logs for a service |
| `POST /api/kill-switch/clear` | Clear the kill switch |
| `WS /ws` | WebSocket for live updates (optional) |

## Design

The dashboard features a **bold, data-dense aesthetic** optimized for professional traders:

- **Dark theme** with high-contrast accent colors (green, red, blue, yellow)
- **Monospace fonts** (JetBrains Mono) for numbers and data
- **Display fonts** (Space Grotesk) for headings and emphasis
- **Real-time updates** every 5 seconds (no manual refresh needed)
- **Responsive layout** adapts to different screen sizes
- **Minimal chrome** — maximum information density

## Customization

Edit `index.html` to:
- Change refresh interval (default: 5 seconds)
- Modify color scheme (CSS variables at top of `<style>`)
- Add new tabs or metrics
- Adjust table columns

Edit `api.py` to:
- Add new API endpoints
- Change data sources
- Modify risk calculations
- Add custom alerts

## Troubleshooting

**Dashboard not loading?**
- Check that port 8002 is not in use: `lsof -i :8002`
- Verify dashboard service is running: `./start.sh status`
- Check logs: `tail -f logs/dashboard.log`

**No portfolio data?**
- Ensure IB Gateway is running on 127.0.0.1:4002
- Check that Read-Only API mode is **disabled** in IB Gateway settings
- Verify clientId 999 is not in use by another connection

**Screener results not showing?**
- Run the screeners manually to generate data:
  ```bash
  cd scripts
  python3 nx_screener_longs.py
  python3 nx_screener_production.py
  ```

**Performance stats missing?**
- Ensure the trade log database has been initialized
- Check that closed trades exist: `python3 -c "from trade_log_db import get_closed_trades; print(len(get_closed_trades(30)))"`
