import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { isRemote, getSnapshot, remoteGet, TRADING_DIR, LOGS_DIR, readJson } from '../../../lib/data-access';

export const dynamic = 'force-dynamic';

interface Alert {
  id: string;
  severity: 'info' | 'warning' | 'critical';
  message: string;
  timestamp: string;
  category: string;
}

interface RiskConfig {
  portfolio?: {
    daily_loss_limit_pct?: number;
    max_sector_concentration_pct?: number;
  };
}

interface SnapshotData {
  account?: { net_liquidation?: number };
  performance?: { daily_pnl?: number };
  risk?: {
    margin_utilization_pct?: number;
    sector_exposure?: Record<string, number>;
  };
  system_health?: {
    status?: string;
    issues?: string[];
    data_freshness_minutes?: number;
  };
  unmapped_symbols?: string[];
  positions?: { list?: Array<Record<string, unknown>> };
}

function getRiskLimits(tradingDir: string): { dailyLossLimit: number; maxSectorPct: number } {
  let dailyLossLimit = 0.03;
  let maxSectorPct   = 30;
  try {
    const tradingMode = process.env.TRADING_MODE ?? 'paper';
    const riskFile    = tradingMode === 'live'
      ? path.join(tradingDir, 'risk.live.json')
      : path.join(tradingDir, 'risk.json');
    const fallback = path.join(tradingDir, 'risk.json');
    const risk = readJson<RiskConfig>(fs.existsSync(riskFile) ? riskFile : fallback);
    if (typeof risk?.portfolio?.daily_loss_limit_pct === 'number')        dailyLossLimit = risk.portfolio.daily_loss_limit_pct;
    if (typeof risk?.portfolio?.max_sector_concentration_pct === 'number') maxSectorPct = risk.portfolio.max_sector_concentration_pct * 100;
  } catch { /* use defaults */ }
  return { dailyLossLimit, maxSectorPct };
}

function buildAlerts(data: SnapshotData, riskLimits: { dailyLossLimit: number; maxSectorPct: number }, extraAlerts: Alert[]): Alert[] {
  const alerts: Alert[] = [];
  const now = new Date().toISOString();
  const { dailyLossLimit, maxSectorPct } = riskLimits;

  const nlv          = data.account?.net_liquidation ?? 1;
  const dailyLossPct = Math.abs(data.performance?.daily_pnl ?? 0) / nlv;

  if (dailyLossPct > dailyLossLimit * 0.8) {
    alerts.push({
      id: 'daily-loss-warning',
      severity: dailyLossPct > dailyLossLimit ? 'critical' : 'warning',
      message: `Daily loss at ${(dailyLossPct * 100).toFixed(1)}% (limit: ${(dailyLossLimit * 100).toFixed(1)}%)`,
      timestamp: now, category: 'risk',
    });
  }

  if ((data.risk?.margin_utilization_pct ?? 0) > 80) {
    alerts.push({
      id: 'margin-warning', severity: 'warning',
      message: `High margin utilization: ${data.risk!.margin_utilization_pct!.toFixed(1)}%`,
      timestamp: now, category: 'risk',
    });
  }

  if (data.risk?.sector_exposure) {
    const totalNotional = Object.entries(data.risk.sector_exposure)
      .filter(([s]) => s !== 'Unknown' && s !== 'Hedge')
      .reduce((sum, [, v]) => sum + (typeof v === 'number' ? Math.abs(v) : 0), 0);

    for (const [sector, dollarValue] of Object.entries(data.risk.sector_exposure)) {
      if (typeof dollarValue !== 'number' || sector === 'Unknown' || sector === 'Hedge') continue;
      const sectorPct = totalNotional > 0
        ? (Math.abs(dollarValue) / totalNotional) * 100
        : 0;
      if (sectorPct > maxSectorPct) {
        const excess = Math.abs(dollarValue) - totalNotional * (maxSectorPct / 100);
        alerts.push({
          id: `sector-${sector}`,
          severity: sectorPct > maxSectorPct * 1.2 ? 'critical' : 'warning',
          message: `${sector} at ${sectorPct.toFixed(1)}% (limit ${maxSectorPct.toFixed(0)}%) — reduce ~$${(excess / 1000).toFixed(1)}k to comply`,
          timestamp: now, category: 'concentration',
        });
      }
    }
  }

  const health = data.system_health;
  if (health?.status && health.status !== 'healthy') {
    alerts.push({
      id: 'system-health',
      severity: health.status === 'error' ? 'critical' : 'warning',
      message: health.issues?.join(', ') ?? 'System health check failed',
      timestamp: now, category: 'system',
    });
  }

  const nowDate = new Date();
  const mtHour  = ((nowDate.getUTCHours() - 6) + 24) % 24 + nowDate.getUTCMinutes() / 60;
  const isWeekday    = nowDate.getUTCDay() >= 1 && nowDate.getUTCDay() <= 5;
  const inMarketHours = isWeekday && mtHour >= 7.0 && mtHour < 14.0;
  if ((health?.data_freshness_minutes ?? 0) > 120 && inMarketHours) {
    alerts.push({
      id: 'stale-data', severity: 'info',
      message: `Data is ${health!.data_freshness_minutes} minutes old`,
      timestamp: now, category: 'system',
    });
  }

  if (Array.isArray(data.unmapped_symbols) && data.unmapped_symbols.length > 0) {
    alerts.push({
      id: 'unmapped-symbols', severity: 'warning',
      message: `${data.unmapped_symbols.length} unmapped sector symbol(s): ${data.unmapped_symbols.join(', ')}`,
      timestamp: now, category: 'system',
    });
  }

  if (data.positions?.list) {
    const positions = data.positions.list;
    const callSymbols = new Set<string>();
    for (const pos of positions) {
      if (pos.sec_type === 'OPT' && typeof pos.symbol === 'string' && (pos.quantity as number) < 0) {
        const sym = (pos.symbol as string).split(' ')[0];
        if ((pos.symbol as string).includes('C ')) callSymbols.add(sym);
      }
    }

    // Symbols excluded from the uncovered-call check.
    // Populated by trading/covered_call_exceptions.json — keyed by symbol, value is the reason.
    const ccExceptions = readJson<Record<string, string>>(
      path.join(TRADING_DIR, 'covered_call_exceptions.json'),
    ) ?? {};
    const hedgeEtfs = new Set(['VXX', 'VIXY', 'TZA', 'SQQQ', 'SPXS', 'UVXY']);

    const uncovered: string[] = [];
    for (const pos of positions) {
      if (
        pos.sec_type === 'STK' && pos.side === 'LONG' &&
        typeof pos.quantity === 'number' && pos.quantity >= 100 &&
        typeof pos.symbol === 'string' &&
        !callSymbols.has(pos.symbol) &&
        !hedgeEtfs.has(pos.symbol) &&
        !(pos.symbol in ccExceptions)
      ) {
        uncovered.push(pos.symbol as string);
      }
    }
    if (uncovered.length > 0) {
      alerts.push({
        id: 'uncovered-positions', severity: 'info',
        message: `${uncovered.length} long position(s) without covered calls: ${uncovered.join(', ')}`,
        timestamp: now, category: 'opportunity',
      });
    }
  }

  return [...alerts, ...extraAlerts];
}

export async function GET() {
  try {
    // On Cloudflare, fetch pre-built alerts from the Python backend; they include all file-based checks
    if (isRemote) {
      const data = await remoteGet<Alert[]>('/api/alerts');
      return NextResponse.json(data ?? []);
    }

    const data = await getSnapshot() as SnapshotData | null;
    if (!data) return NextResponse.json([]);

    const riskLimits = getRiskLimits(TRADING_DIR);
    const extraAlerts: Alert[] = [];
    const now = new Date().toISOString();

    // Assignment risk
    const assignData = readJson<{ date?: string; alerted?: Record<string, string> }>(
      path.join(LOGS_DIR, 'assignment_alerts_today.json'),
    );
    if (assignData?.date === now.slice(0, 10) && assignData.alerted) {
      const itmKeys = Object.entries(assignData.alerted).filter(
        ([, level]) => level === 'ITM' || level === 'DEEP_ITM' || level === 'DIVIDEND',
      );
      if (itmKeys.length > 0) {
        const symbols = [...new Set(itmKeys.map(([k]) => k.split('_')[0]))];
        const hasDeep = itmKeys.some(([, level]) => level === 'DEEP_ITM' || level === 'DIVIDEND');
        extraAlerts.push({
          id: 'assignment-risk', severity: hasDeep ? 'critical' : 'warning',
          message: `${symbols.length} option(s) ITM — assignment risk: ${symbols.join(', ')}`,
          timestamp: now, category: 'risk',
        });
      }
    }

    // Drawdown circuit breaker
    const breaker = readJson<{ tier?: number; drawdown_pct?: number; last_checked?: string }>(
      path.join(LOGS_DIR, 'drawdown_breaker_state.json'),
    );
    if (breaker) {
      const tier = breaker.tier ?? 0;
      const dd   = breaker.drawdown_pct ?? 0;
      if (tier >= 3) {
        extraAlerts.push({ id: 'drawdown-breaker', severity: 'critical', message: `Drawdown breaker TIER 3 — kill switch activated (${dd.toFixed(1)}% daily loss)`, timestamp: breaker.last_checked ?? now, category: 'risk' });
      } else if (tier === 2) {
        extraAlerts.push({ id: 'drawdown-breaker', severity: 'critical', message: `Drawdown breaker TIER 2 — all new entries HALTED (${dd.toFixed(1)}% daily loss)`, timestamp: breaker.last_checked ?? now, category: 'risk' });
      } else if (tier === 1) {
        extraAlerts.push({ id: 'drawdown-breaker', severity: 'warning',  message: `Drawdown breaker TIER 1 — position sizes reduced 50% (${dd.toFixed(1)}% daily loss)`, timestamp: breaker.last_checked ?? now, category: 'risk' });
      }
    }

    // Kill switch active
    const ks = readJson<{ active?: boolean; reason?: string; timestamp?: string }>(
      path.join(TRADING_DIR, 'kill_switch.json'),
    );
    if (ks?.active) {
      extraAlerts.push({
        id: 'kill-switch', severity: 'critical',
        message: `Kill switch active: ${ks.reason ?? 'Manual trigger'}`,
        timestamp: ks.timestamp ?? now, category: 'risk',
      });
    }

    return NextResponse.json(buildAlerts(data, riskLimits, extraAlerts));
  } catch (error) {
    console.error('Error generating alerts:', error);
    return NextResponse.json([]);
  }
}
