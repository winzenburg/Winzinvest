import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { requireAuth } from '../../../lib/auth';
import { LOGS_DIR, isRemote, remoteGet } from '../../../lib/data-access';

export interface StrategyAttribution {
  generated_at: string;
  lookback_days: number;
  current_regime: string;
  total_trades: number;
  overall: {
    win_rate: number | null;
    avg_pnl_pct: number | null;
    profit_factor: number | null;
    expectancy: number | null;
    sharpe: number | null;
    stop_hit_pct: number | null;
  };
  by_strategy: Record<
    string,
    {
      count: number;
      win_rate: number | null;
      avg_pnl_pct: number | null;
      profit_factor: number | null;
      expectancy: number | null;
      avg_hold_days: number | null;
    }
  >;
  by_strategy_regime: Record<
    string,
    Record<
      string,
      {
        count: number;
        win_rate: number | null;
        avg_pnl_pct: number | null;
        profit_factor: number | null;
      }
    >
  >;
  recommendations: Array<{
    strategy: string;
    /** May be missing in older or hand-edited JSON — UI defaults to HOLD. */
    action?: 'SCALE_UP' | 'REDUCE' | 'PAUSE' | 'HOLD';
    reason?: string;
  }>;
}

/** Finds the most recent strategy_attribution_YYYYMMDD.json in the logs dir. */
function findLatestAttributionFile(): string | null {
  try {
    const files = fs.readdirSync(LOGS_DIR);
    const matches = files
      .filter(f => /^strategy_attribution_\d{8}\.json$/.test(f))
      .sort()
      .reverse();
    return matches.length > 0 ? path.join(LOGS_DIR, matches[0]) : null;
  } catch {
    return null;
  }
}

export async function GET() {
  const unauth = await requireAuth();
  if (unauth) return unauth;

  if (isRemote) {
    const data = await remoteGet<StrategyAttribution>('/api/strategy-attribution');
    if (data) return NextResponse.json(data);
    return NextResponse.json({ error: 'Not available from remote backend' }, { status: 503 });
  }

  const filePath = findLatestAttributionFile();
  if (!filePath) {
    return NextResponse.json(
      { error: 'No attribution report found. Run strategy_performance_report.py (or wait for Friday automated run).' },
      { status: 404 },
    );
  }

  try {
    const raw = fs.readFileSync(filePath, 'utf8');
    const data = JSON.parse(raw) as StrategyAttribution;
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: 'Failed to parse attribution file.' }, { status: 500 });
  }
}
