import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export const dynamic = 'force-dynamic';

interface Alert {
  id: string;
  severity: 'info' | 'warning' | 'critical';
  message: string;
  timestamp: string;
  category: string;
}

export async function GET() {
  try {
    const snapshotPath = path.join(
      process.cwd(),
      '..',
      'trading',
      'logs',
      'dashboard_snapshot.json'
    );

    if (!fs.existsSync(snapshotPath)) {
      return NextResponse.json([]);
    }

    const data = JSON.parse(fs.readFileSync(snapshotPath, 'utf-8'));
    const alerts: Alert[] = [];

    const dailyLossLimit = 0.03;
    const dailyLossPct = Math.abs(data.performance?.daily_pnl || 0) / (data.account?.net_liquidation || 1);
    
    if (dailyLossPct > dailyLossLimit * 0.8) {
      alerts.push({
        id: 'daily-loss-warning',
        severity: dailyLossPct > dailyLossLimit ? 'critical' : 'warning',
        message: `Daily loss at ${(dailyLossPct * 100).toFixed(1)}% (limit: ${(dailyLossLimit * 100).toFixed(0)}%)`,
        timestamp: new Date().toISOString(),
        category: 'risk',
      });
    }

    if (data.risk?.margin_utilization_pct > 80) {
      alerts.push({
        id: 'margin-warning',
        severity: 'warning',
        message: `High margin utilization: ${data.risk.margin_utilization_pct.toFixed(1)}%`,
        timestamp: new Date().toISOString(),
        category: 'risk',
      });
    }

    const maxSectorPct = 30;
    if (data.risk?.sector_exposure) {
      for (const [sector, pct] of Object.entries(data.risk.sector_exposure)) {
        if (typeof pct === 'number' && pct > maxSectorPct) {
          alerts.push({
            id: `sector-${sector}`,
            severity: 'warning',
            message: `${sector} concentration at ${pct.toFixed(1)}% (limit: ${maxSectorPct}%)`,
            timestamp: new Date().toISOString(),
            category: 'concentration',
          });
        }
      }
    }

    if (data.system_health?.status !== 'healthy') {
      alerts.push({
        id: 'system-health',
        severity: data.system_health.status === 'error' ? 'critical' : 'warning',
        message: data.system_health.issues?.join(', ') || 'System health check failed',
        timestamp: new Date().toISOString(),
        category: 'system',
      });
    }

    if (data.system_health?.data_freshness_minutes > 60) {
      alerts.push({
        id: 'stale-data',
        severity: 'info',
        message: `Data is ${data.system_health.data_freshness_minutes} minutes old`,
        timestamp: new Date().toISOString(),
        category: 'system',
      });
    }

    return NextResponse.json(alerts);
  } catch (error) {
    console.error('Error generating alerts:', error);
    return NextResponse.json([]);
  }
}
