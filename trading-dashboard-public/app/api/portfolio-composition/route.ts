import { NextResponse } from 'next/server';
import { requireAuth } from '@/lib/auth';
import { readJson, LOGS_DIR } from '@/lib/data-access';
import path from 'path';

/**
 * Portfolio Composition API
 * 
 * Returns sector mix, strategy breakdown, and long/short balance.
 * Built from current snapshot data.
 */

export async function GET() {
  const unauth = await requireAuth();
  if (unauth) return unauth;

  try {
    const snapshotPath = path.join(LOGS_DIR, 'dashboard_snapshot.json');
    const snapshot = readJson(snapshotPath) as any;

    if (!snapshot) {
      return NextResponse.json(
        { error: 'No snapshot data available' },
        { status: 404 }
      );
    }

    // Extract sector exposure
    const sectorExposure = snapshot.risk?.sector_exposure || {};
    const sectors = Object.entries(sectorExposure).map(([sector, data]: [string, any]) => ({
      sector,
      notional: data.notional || 0,
      pct: data.pct || 0,
      positionCount: data.count || 0,
    }));

    // Extract strategy breakdown
    const strategyData = snapshot.strategy_breakdown || {};
    const strategies = Object.entries(strategyData).map(([strategy, data]: [string, any]) => ({
      strategy: strategy.toUpperCase(),
      count: data.count || 0,
      pct: data.pct || 0,
      notional: data.notional || 0,
    }));

    // Calculate long/short balance
    const positions = snapshot.positions?.list || [];
    let longNotional = 0;
    let shortNotional = 0;

    for (const pos of positions) {
      if (pos.sec_type !== 'STK') continue;
      const notional = (pos.market_value || 0);
      if (pos.quantity > 0) {
        longNotional += notional;
      } else if (pos.quantity < 0) {
        shortNotional += notional;
      }
    }

    const totalNotional = longNotional + Math.abs(shortNotional);
    const netNotional = longNotional + shortNotional;  // Algebraic (short is negative)

    // Options premium (if available)
    const optionsPremium30d = snapshot.options_coverage?.premium_30d || 0;

    return NextResponse.json({
      sectors,
      strategies,
      longNotional,
      shortNotional,
      netNotional,
      totalNotional,
      optionsPremium30d,
    });
  } catch (error) {
    console.error('Error building portfolio composition:', error);
    return NextResponse.json(
      { error: 'Failed to load portfolio composition' },
      { status: 500 }
    );
  }
}
