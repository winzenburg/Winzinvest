import { NextResponse } from 'next/server';
import { requireAuth } from '@/lib/auth';
import { readJson, LOGS_DIR } from '@/lib/data-access';
import path from 'path';

/**
 * System Benchmarks API
 * 
 * Returns aggregate performance stats across all users.
 * Enables "Your X vs system avg Y" comparative context.
 * 
 * Privacy: Only aggregates, no individual user data.
 */

export async function GET() {
  const unauth = await requireAuth();
  if (unauth) return unauth;

  try {
    const benchmarksPath = path.join(LOGS_DIR, 'system_benchmarks.json');
    const data = readJson(benchmarksPath) as any;

    if (!data || !data.benchmarks) {
      return NextResponse.json({
        benchmarks: {
          total_trades: 0,
          win_rate: 0,
          avg_pnl: 0,
          avg_return_pct: 0,
          avg_r_multiple: 0,
          best_trade: 0,
          worst_trade: 0,
          strategies: {},
        },
      });
    }

    return NextResponse.json(data);
  } catch (error) {
    console.error('Error loading system benchmarks:', error);
    return NextResponse.json(
      { error: 'Failed to load benchmarks' },
      { status: 500 }
    );
  }
}
