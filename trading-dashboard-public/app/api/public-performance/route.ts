import { NextResponse } from 'next/server';
import * as fs from 'fs';
import * as path from 'path';

/**
 * Public performance API endpoint.
 * Returns ONLY aggregate performance metrics - no positions, trades, or account details.
 * This endpoint is intentionally unauthenticated to support the public /performance page.
 */
export async function GET() {
  try {
    const snapshotPath = path.join(
      process.cwd(),
      '../trading/logs/dashboard_snapshot.json',
    );

    if (!fs.existsSync(snapshotPath)) {
      return NextResponse.json(
        { error: 'Performance data unavailable' },
        { status: 503 },
      );
    }

    const raw = fs.readFileSync(snapshotPath, 'utf-8');
    const snapshot = JSON.parse(raw);

    // Return ONLY public-safe performance metrics
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
      },
      market_regime: {
        regime: snapshot.market_regime?.regime ?? null,
        macro_regime: snapshot.market_regime?.macro_regime ?? null,
      },
    };

    return NextResponse.json(publicData);
  } catch (err) {
    console.error('Error reading public performance data:', err);
    return NextResponse.json(
      { error: 'Performance data unavailable' },
      { status: 503 },
    );
  }
}
