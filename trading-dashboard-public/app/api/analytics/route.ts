import { NextResponse } from 'next/server';
import path from 'path';
import { requireAuth } from '../../../lib/auth';
import { readJson, LOGS_DIR, isRemote, remoteGet } from '../../../lib/data-access';

interface AnalyticsSummary {
  total_closed: number;
  with_r_data?: number;
  win_rate_pct?: number | null;
  avg_r_multiple?: number | null;
  total_realized_pnl?: number | null;
  wins?: number;
  losses?: number;
  breakeven?: number;
}

interface ByGroup {
  label: string;
  count: number;
  win_rate_pct: number | null;
  avg_r_multiple: number | null;
  total_pnl: number | null;
}

interface HoldTime {
  avg_hold_days_winners: number | null;
  avg_hold_days_losers: number | null;
  winner_count: number;
  loser_count: number;
}

interface ExitReason {
  reason: string;
  count: number;
  pct: number;
}

interface MonthlyPnl {
  month: string;
  pnl: number;
}

interface TopTrade {
  symbol: string;
  strategy: string | null;
  r_multiple: number;
  pnl: number;
  hold_days: number | null;
  regime: string | null;
  exit_date: string;
}

interface ConvictionBin {
  tier: string;
  count: number;
  avg_r: number | null;
  win_rate: number | null;
}

export interface AnalyticsData {
  generated_at: string;
  error?: string;
  note?: string;
  summary: AnalyticsSummary;
  by_strategy?: ByGroup[];
  by_regime?: ByGroup[];
  hold_time?: HoldTime;
  exit_reasons?: ExitReason[];
  monthly_pnl?: MonthlyPnl[];
  top_trades?: { best: TopTrade[]; worst: TopTrade[] };
  conviction_vs_r?: ConvictionBin[];
}

export async function GET() {
  const unauth = await requireAuth();
  if (unauth) return unauth;

  if (isRemote) {
    const data = await remoteGet<AnalyticsData>('/api/analytics');
    if (data) return NextResponse.json(data);
    return NextResponse.json(
      { error: 'Analytics not available from remote backend', summary: { total_closed: 0 } },
      { status: 503 },
    );
  }

  const filePath = path.join(LOGS_DIR, 'trade_analytics.json');
  const data = readJson<AnalyticsData>(filePath);

  if (!data) {
    return NextResponse.json({
      generated_at: new Date().toISOString(),
      note: 'Analytics file not yet generated. Run trade_analytics.py to produce it.',
      summary: { total_closed: 0 },
    });
  }

  return NextResponse.json(data);
}
