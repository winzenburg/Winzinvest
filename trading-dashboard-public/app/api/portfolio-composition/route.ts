import { NextResponse } from 'next/server';
import { requireAuth } from '@/lib/auth';
import { readJson, remoteGet, isRemote, LOGS_DIR } from '@/lib/data-access';
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
    // Dual-mode: fetch from Python API if remote, else read local file
    let snapshot: any;
    
    if (isRemote) {
      snapshot = await remoteGet('/api/snapshot');
    } else {
      const snapshotPath = path.join(LOGS_DIR, 'dashboard_snapshot.json');
      snapshot = readJson(snapshotPath);
    }

    if (!snapshot) {
      return NextResponse.json(
        { error: 'No snapshot data available' },
        { status: 404 }
      );
    }

    // Extract sector exposure (raw signed market values)
    const sectorExposure = snapshot.risk?.sector_exposure || {};
    const positions = snapshot.positions?.list || [];
    const totalNotional = snapshot.positions?.total_notional || 0;
    
    // Count positions per sector (stocks only)
    const sectorCounts: Record<string, number> = {};
    for (const pos of positions) {
      if (pos.sec_type !== 'STK') continue;
      const sector = pos.sector || 'Unknown';
      sectorCounts[sector] = (sectorCounts[sector] || 0) + 1;
    }
    
    const sectors = Object.entries(sectorExposure).map(([sector, notional]: [string, any]) => {
      const absNotional = Math.abs(notional);
      return {
        sector,
        notional: absNotional,
        pct: totalNotional > 0 ? (absNotional / totalNotional) * 100 : 0,
        positionCount: sectorCounts[sector] || 0,
      };
    });

    // Extract strategy breakdown
    const strategyData = snapshot.strategy_breakdown || {};
    const strategies = Object.entries(strategyData).map(([strategy, data]: [string, any]) => {
      const notional = Math.abs(data.notional || 0);
      return {
        strategy: strategy.toUpperCase(),
        count: data.count || 0,
        pct: totalNotional > 0 ? (notional / totalNotional) * 100 : 0,
        notional,
      };
    });

    // Get long/short notionals from snapshot (already calculated)
    const longNotional = snapshot.positions?.long_notional || 0;
    const shortNotional = Math.abs(snapshot.positions?.short_notional || 0);
    const netNotional = longNotional - shortNotional;

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
