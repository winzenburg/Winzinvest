# Trading Dashboard (Public / Read-Only)

A deployable, read-only dashboard for displaying trading system performance. Built with Next.js 14 and designed to match the Cultivate aesthetic.

## Features

- ✅ **Vercel Deployable**: Static site generation for fast, global CDN delivery
- ✅ **Read-Only**: No trading execution, only performance display
- ✅ **Cultivate Design**: Elegant, editorial aesthetic with Playfair Display + Inter
- ✅ **Responsive**: Works on desktop, tablet, and mobile
- ✅ **Real-time Updates**: Auto-refreshes every 30 seconds
- ✅ **API Ready**: Built-in API routes for data integration

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Styling**: Tailwind CSS
- **Fonts**: Playfair Display (serif) + Inter (sans-serif)
- **Deployment**: Vercel
- **Data**: Mock data (ready for API integration)

## Quick Start

### Development

```bash
cd trading-dashboard-public

# Install dependencies
npm install

# Run development server
npm run dev

# Open http://localhost:3000
```

### Production Build

```bash
npm run build
npm start
```

## Deploy to Vercel

### Option 1: Via GitHub (Recommended)

1. Push this folder to a GitHub repo
2. Connect repo to Vercel
3. Vercel auto-deploys on every push

```bash
# From this directory
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/winzenburg/trading-dashboard-public.git
git push -u origin main
```

Then in Vercel:
- Import project from GitHub
- Select `trading-dashboard-public` folder
- Deploy

### Option 2: Via Vercel CLI

```bash
npm install -g vercel
vercel
```

## Data Integration

Currently using **mock data**. To connect to real data:

### Step 1: Set Up Database

Choose one:
- **Supabase** (recommended, free tier)
- **Vercel Postgres**
- **PlanetScale**
- **MongoDB Atlas**

### Step 2: Create Sync Script

On your local machine (where trading system runs):

```python
# trading/scripts/sync_to_cloud.py
import psycopg2  # or your DB client
from trade_log_db import get_closed_trades
from portfolio_snapshot import get_latest_snapshot

def sync_performance_data():
    # Get data from local system
    trades = get_closed_trades(days=30)
    snapshot = get_latest_snapshot()
    
    # Calculate metrics
    win_rate = calculate_win_rate(trades)
    sharpe = calculate_sharpe(trades)
    
    # Push to cloud database
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO performance_snapshots 
        (account_value, daily_pnl, total_pnl, win_rate, sharpe_ratio, ...)
        VALUES (%s, %s, %s, %s, %s, ...)
    """, (snapshot['value'], ...))
    conn.commit()
```

Run this script every 5-15 minutes via cron or scheduler.

### Step 3: Update API Route

Edit `app/api/performance/route.ts`:

```typescript
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_ANON_KEY!
);

export async function GET() {
  const { data } = await supabase
    .from('performance_snapshots')
    .select('*')
    .order('created_at', { ascending: false })
    .limit(1)
    .single();

  return NextResponse.json(data);
}
```

### Step 4: Update Frontend

Edit `app/page.tsx` to fetch from API:

```typescript
useEffect(() => {
  const fetchData = async () => {
    const res = await fetch('/api/performance');
    const data = await res.json();
    setData(data);
  };

  fetchData();
  const interval = setInterval(fetchData, 30000);
  return () => clearInterval(interval);
}, []);
```

## Environment Variables

Create `.env.local`:

```bash
# Database (Supabase example)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key

# Optional: Authentication
NEXT_PUBLIC_AUTH_ENABLED=false
```

## Customization

### Colors

Edit `app/page.tsx` color classes:
- `text-sky-600` → Account value
- `text-green-600` → Positive P&L
- `text-red-600` → Negative P&L

### Fonts

Edit `app/layout.tsx` to change fonts:
```typescript
import { YourFont } from 'next/font/google';
```

### Layout

Edit `app/page.tsx` grid layouts:
- `grid-cols-4` → Number of metric cards
- `lg:grid-cols-2` → Responsive breakpoints

## Architecture

```
Local Machine                Cloud (Vercel)
├── Trading System           ├── Next.js App
├── IB Gateway              ├── API Routes
├── SQLite/Logs             └── Static Pages
└── Sync Script ─────────> Database (Supabase)
    (every 5-15 min)         └── Performance Data
```

## Security

- ✅ **Read-Only**: No trading execution possible
- ✅ **No Credentials**: No IBKR API keys in code
- ✅ **Public Safe**: Only shows aggregated performance data
- ✅ **No PII**: No account numbers or personal info

Optional: Add authentication via NextAuth.js or Clerk.

## Performance

- **Build Time**: ~30 seconds
- **Page Load**: <1 second (static)
- **Data Refresh**: 30 seconds (configurable)
- **Hosting**: Free on Vercel (Hobby plan)

## Roadmap

Future enhancements:
- [ ] Historical charts (Chart.js or Recharts)
- [ ] Trade history table
- [ ] Strategy breakdown
- [ ] Sector allocation pie chart
- [ ] Authentication (NextAuth.js)
- [ ] Mobile app (React Native)
- [ ] Email alerts (Resend)
- [ ] Export to CSV

## Differences from Local Dashboard

| Feature | Local Dashboard | Public Dashboard |
|---------|----------------|------------------|
| **Deployment** | localhost:8002 | Vercel (public URL) |
| **Data Source** | Direct IBKR API | Cloud database |
| **Real-time** | Yes (live) | Near real-time (5-15 min delay) |
| **Positions** | Live positions | Historical only |
| **Screeners** | Live candidates | Not shown |
| **Risk Monitor** | Live gates | Historical metrics |
| **Logs** | Live tail | Not shown |
| **Purpose** | Trading control | Performance display |

## Support

For issues or questions:
1. Check Next.js docs: https://nextjs.org/docs
2. Check Vercel docs: https://vercel.com/docs
3. Check Tailwind docs: https://tailwindcss.com/docs

## License

Private - Not for redistribution
