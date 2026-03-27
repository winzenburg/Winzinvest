# Winzinvest Trading Dashboard

Institutional-grade trading dashboard with real-time risk metrics, performance attribution, and audit trails.

## Features

### Simple Dashboard (`/`)
- Key metrics overview
- Screener candidates
- Recent trades
- Quick navigation

### Dashboard (`/dashboard`)
- **Real-time data** from your brokerage via API (Interactive Brokers supported; Tastytrade coming soon)
- **Risk metrics**: VaR (95%, 99%), CVaR, beta, correlation, sector exposure
- **Performance attribution** by strategy (momentum long/short, mean reversion, pairs, options)
- **Trade analytics**: MAE, MFE, slippage, hold times, profit factor
- **Interactive equity curve** with drawdown overlay
- **Live positions** with P&L and sector breakdown
- **Margin monitoring**: Utilization, buying power, leverage ratio
- **Alerts**: Daily loss warnings, margin alerts, sector concentration
- **Backtest comparison**: Live vs historical performance

### Trading Strategy (`/strategy`)
- 8th grade level explanation of trading system
- Strategy descriptions
- Risk management approach

### Trading Journal (`/journal`)
- Complete trade history
- Filters and sorting
- Detailed trade cards

### Audit Trail (`/audit`)
- Gate rejection log
- Order lifecycle events
- System health events
- Searchable and filterable

## Setup

### 1. Install Dependencies

```bash
npm install
```

### 2. Run Data Aggregator

The institutional dashboard requires real-time data from your trading system:

```bash
cd ../trading/scripts
PYTHONPATH="." python3 dashboard_data_aggregator.py
```

This connects to your brokerage (currently IBKR) and generates `trading/logs/dashboard_snapshot.json`.

### 3. Run Trading Health Agent (Optional, for System Monitor)

The **System Monitor** on the dashboard can show brokerage connection and kill-switch status. To bring "Trading health" up:

```bash
cd ../trading/scripts
pip install fastapi uvicorn   # if not already installed
uvicorn agents.health_check:app --host 0.0.0.0 --port 8000
```

Leave this running in a separate terminal. If the agent runs on another host/port, set `TRADING_HEALTH_URL` in the dashboard environment (e.g. in `.env.local`).

### 4. Automate Data Collection (Optional)

Add to crontab to run every 5 minutes:

```bash
*/5 * * * * cd /path/to/trading/scripts && ./run_dashboard_aggregator.sh
```

### 5. Configure authentication

This project now uses **NextAuth + Prisma** with a PostgreSQL database.

Add a `DATABASE_URL` to `.env.local` pointing at your Postgres instance:

```bash
DATABASE_URL="postgres://user:password@host:5432/winzinvest"
NEXTAUTH_URL="http://localhost:3000"
NEXTAUTH_SECRET="generate-a-long-random-string"

# Optional social login providers
GOOGLE_CLIENT_ID=""
GOOGLE_CLIENT_SECRET=""
FACEBOOK_CLIENT_ID=""
FACEBOOK_CLIENT_SECRET=""
APPLE_CLIENT_ID=""
APPLE_CLIENT_SECRET=""
```

Then generate the Prisma client and apply migrations (once your database exists):

```bash
npm run prisma:generate
npm run prisma:migrate -- --name init-auth
```

This creates the tables NextAuth needs (`User`, `Account`, `Session`, `VerificationToken`) plus a `passwordHash` column for email/password logins.

### 6. Start Development Server

```bash
npm run dev
```

**If the project lives on Google Drive**, sync can corrupt the `.next` folder and you’ll see errors like `Cannot find module './611.js'`. Fix:

1. **Pause Google Drive sync** for this folder while developing (recommended), **or**
2. Start with a clean cache and **Turbopack** (different bundler, fewer chunk issues):

```bash
npm run dev:clean:turbo
```

**Correct path** (folder name uses a capital **I**: `MIssion`):

```bash
cd ~/Library/CloudStorage/GoogleDrive-*/My\ Drive/Projects/MIssion\ Control/trading-dashboard-public
```

Or run from repo root: `./scripts/start-dashboard.sh`

Visit:
- http://localhost:3000 - Public landing page
- http://localhost:3000/dashboard - Trading dashboard (authenticated)
- http://localhost:3000/strategy - Strategy explanation
- http://localhost:3000/journal - Trade history (authenticated)
- http://localhost:3000/audit - Audit trail (authenticated)

## Authentication model

- Users can **sign up** with email + password on `/login` (\"Create a Winzinvest account\").
- Passwords are hashed with `bcrypt` and stored in the `User.passwordHash` field via Prisma.
- Users can also sign in with:
  - **Google**
  - **Facebook**
  - **Apple**
- All identity providers link to a single `User` record via NextAuth's Prisma adapter. Make sure each provider uses the same email address for a unified account.

Protected pages (`/dashboard`, `/journal`, `/audit`, etc.) are guarded by `next-auth` middleware. API routes use `requireAuth()` from `lib/auth.ts` and expect a valid session with `session.user.id` set.

## Production Deployment

### Build Static Site

```bash
npm run build
```

Generates static HTML in `out/` directory.

### Deploy to Vercel

1. Push to GitHub
2. Import project in Vercel
3. Set root directory: `trading-dashboard-public`
4. Deploy

See `DEPLOY.md` for detailed instructions.

## API Endpoints

- `GET /api/dashboard` - Complete dashboard snapshot
- `GET /api/alerts` - Active alerts and warnings
- `GET /api/audit?hours=24&type=gate_rejection` - Audit trail entries
- `GET /api/performance` - Legacy performance endpoint

## Architecture

```
Trading System (Python)
  ├─ Screeners → watchlist_*.json
  ├─ Executors → executions.json, positions
  ├─ Risk Gates → audit_trail.json
  └─ Data Aggregator → dashboard_snapshot.json
       ↓
Dashboard (Next.js)
  ├─ API Routes → Read JSON files
  └─ React Components → Display data
```

## Institutional Features

### Risk Management
- **VaR/CVaR**: Quantify tail risk at 95% and 99% confidence
- **Sector exposure**: Real-time concentration monitoring
- **Margin utilization**: Track leverage and buying power usage
- **Beta/correlation**: Portfolio sensitivity to market moves

### Performance Attribution
- **Strategy breakdown**: P&L by strategy type
- **Win rate by strategy**: Which strategies perform best?
- **Trade quality**: MAE/MFE analysis

### Audit & Compliance
- **Gate rejection log**: Every blocked trade with full context
- **Order lifecycle**: Complete order history
- **System health**: Data freshness, connection status
- **Searchable audit trail**: Filter by type, symbol, time

### Analytics
- **Slippage tracking**: Monitor execution quality
- **Hold time analysis**: Optimize entry/exit timing
- **Profit factor**: Risk/reward ratio
- **Best/worst trades**: Learn from extremes

## Data Requirements

The institutional dashboard requires these files in `trading/logs/`:
- `dashboard_snapshot.json` - Main data (generated by aggregator)
- `audit_trail.json` - Gate rejections and events
- `daily_loss.json` - Daily P&L tracking
- `peak_equity.json` - Drawdown calculation
- `sod_equity.json` - Start of day equity

Plus watchlists in `trading/`:
- `watchlist_longs.json` - Long candidates
- `watchlist_multimode.json` - Short candidates

## Notes

- Static export configured (`output: 'export'` in `next.config.js`)
- API routes work in dev mode but return 404 in static export
- For production with real data, deploy with Node.js runtime (remove `output: 'export'`)
- Or use a separate API service to serve the JSON files

## License

Private - Internal Use Only
