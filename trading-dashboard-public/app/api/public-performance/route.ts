import { NextResponse } from 'next/server';
import * as fs from 'fs';
import * as path from 'path';

/**
 * Public performance API endpoint.
 * Returns ONLY aggregate performance metrics - no positions, trades, or account details.
 * This endpoint is intentionally unauthenticated to support the public /performance page.
 * 
 * Data sources (in order of preference):
 * 1. Local trading system snapshot (for authenticated dashboard on localhost)
 * 2. Static public performance data (for Vercel deployment)
 */
export async function GET() {
  try {
    // Try local snapshot first (for dashboard on localhost with live trading system)
    const localSnapshotPath = path.join(
      process.cwd(),
      '../trading/logs/dashboard_snapshot.json',
    );

    if (fs.existsSync(localSnapshotPath)) {
      const raw = fs.readFileSync(localSnapshotPath, 'utf-8');
      const snapshot = JSON.parse(raw);

      const publicData = {
        portfolio: {
          daily_pnl_pct: snapshot.portfolio?.daily_pnl_pct ?? null,
        },
        performance: {
          total_return_pct: snapshot.performance?.total_return_pct ?? null,
          total_return_30d_pct: snapshot.performance?.total_return_30d_pct ?? null,
          portfolio_return_pct: snapshot.performance?.portfolio_return_pct ?? null,
          portfolio_return_since: snapshot.performance?.portfolio_return_since ?? null,
          sharpe: snapshot.performance?.sharpe ?? null,
          sharpe_ratio: snapshot.performance?.sharpe_ratio ?? null,
          max_drawdown_pct: snapshot.performance?.max_drawdown_pct ?? null,
          daily_return_pct: snapshot.performance?.daily_return_pct ?? null,
          win_rate: snapshot.performance?.win_rate ?? null,
          profit_factor: snapshot.performance?.profit_factor ?? null,
          total_trades: snapshot.performance?.total_trades ?? null,
        },
        market_regime: {
          regime: snapshot.market_regime?.regime ?? null,
          macro_regime: snapshot.market_regime?.macro_regime ?? null,
        },
        last_updated: snapshot.timestamp ?? null,
      };

      return NextResponse.json(publicData);
    }

    // Fallback to static public data (for Vercel deployment)
    const publicDataPath = path.join(process.cwd(), 'public/performance-data.json');

    if (fs.existsSync(publicDataPath)) {
      const raw = fs.readFileSync(publicDataPath, 'utf-8');
      const publicData = JSON.parse(raw);
      return NextResponse.json(publicData);
    }

    return NextResponse.json(
      { error: 'Performance data unavailable' },
      { status: 503 },
    );
  } catch (err) {
    console.error('Error reading public performance data:', err);
    return NextResponse.json(
      { error: 'Performance data unavailable' },
      { status: 503 },
    );
  }
}

