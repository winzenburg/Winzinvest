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

function readRiskLimits(tradingDir: string): { dailyLossLimit: number; maxSectorPct: number } {
  // Defaults (matches base risk.json)
  let dailyLossLimit = 0.03;
  let maxSectorPct = 30;

  try {
    const tradingMode = process.env.TRADING_MODE || 'paper';
    // Use live override when in live mode
    const riskFile = tradingMode === 'live'
      ? path.join(tradingDir, 'risk.live.json')
      : path.join(tradingDir, 'risk.json');
    const fallbackFile = path.join(tradingDir, 'risk.json');

    const fileToRead = fs.existsSync(riskFile) ? riskFile : fallbackFile;
    if (fs.existsSync(fileToRead)) {
      const risk = JSON.parse(fs.readFileSync(fileToRead, 'utf-8'));
      if (typeof risk?.portfolio?.daily_loss_limit_pct === 'number') {
        dailyLossLimit = risk.portfolio.daily_loss_limit_pct;
      }
      if (typeof risk?.portfolio?.max_sector_concentration_pct === 'number') {
        maxSectorPct = risk.portfolio.max_sector_concentration_pct * 100;
      }
    }
  } catch {
    // Use defaults if risk files can't be read
  }

  return { dailyLossLimit, maxSectorPct };
}

export async function GET() {
  try {
    const tradingDir = path.join(process.cwd(), '..', 'trading');
    const snapshotPath = path.join(tradingDir, 'logs', 'dashboard_snapshot.json');

    if (!fs.existsSync(snapshotPath)) {
      return NextResponse.json([]);
    }

    const data = JSON.parse(fs.readFileSync(snapshotPath, 'utf-8'));
    const alerts: Alert[] = [];
    const now = new Date().toISOString();

    const { dailyLossLimit, maxSectorPct } = readRiskLimits(tradingDir);

    const nlv = data.account?.net_liquidation || 1;
    const dailyLossPct = Math.abs(data.performance?.daily_pnl || 0) / nlv;

    if (dailyLossPct > dailyLossLimit * 0.8) {
      alerts.push({
        id: 'daily-loss-warning',
        severity: dailyLossPct > dailyLossLimit ? 'critical' : 'warning',
        message: `Daily loss at ${(dailyLossPct * 100).toFixed(1)}% (limit: ${(dailyLossLimit * 100).toFixed(1)}%)`,
        timestamp: now,
        category: 'risk',
      });
    }

    if (data.risk?.margin_utilization_pct > 80) {
      alerts.push({
        id: 'margin-warning',
        severity: 'warning',
        message: `High margin utilization: ${data.risk.margin_utilization_pct.toFixed(1)}%`,
        timestamp: now,
        category: 'risk',
      });
    }

    if (data.risk?.sector_exposure) {
      // sector_exposure values are in dollars — convert to % of NLV for comparison
      const totalNlv = data.account?.net_liquidation || 1;
      for (const [sector, dollarValue] of Object.entries(data.risk.sector_exposure)) {
        if (typeof dollarValue === 'number' && sector !== 'Unknown') {
          const sectorPct = (Math.abs(dollarValue) / totalNlv) * 100;
          if (sectorPct > maxSectorPct) {
            alerts.push({
              id: `sector-${sector}`,
              severity: 'warning',
              message: `${sector} concentration at ${sectorPct.toFixed(1)}% of NLV (limit: ${maxSectorPct.toFixed(0)}%)`,
              timestamp: now,
              category: 'concentration',
            });
          }
        }
      }
    }

    if (data.system_health?.status && data.system_health.status !== 'healthy') {
      alerts.push({
        id: 'system-health',
        severity: data.system_health.status === 'error' ? 'critical' : 'warning',
        message: data.system_health.issues?.join(', ') || 'System health check failed',
        timestamp: now,
        category: 'system',
      });
    }

    // Only alert on stale screener data during market hours (7:00–14:00 MT / 9:00–16:00 ET).
    // After market close the last screener run is expected to be several hours old.
    const nowForStaleness = new Date();
    const mtHour = ((nowForStaleness.getUTCHours() - 6) + 24) % 24 + nowForStaleness.getUTCMinutes() / 60;
    const isWeekday = nowForStaleness.getUTCDay() >= 1 && nowForStaleness.getUTCDay() <= 5;
    const inMarketHours = isWeekday && mtHour >= 7.0 && mtHour < 14.0;
    if ((data.system_health?.data_freshness_minutes ?? 0) > 120 && inMarketHours) {
      alerts.push({
        id: 'stale-data',
        severity: 'info',
        message: `Data is ${data.system_health.data_freshness_minutes} minutes old`,
        timestamp: now,
        category: 'system',
      });
    }

    // Unmapped sector symbols alert
    if (Array.isArray(data.unmapped_symbols) && data.unmapped_symbols.length > 0) {
      alerts.push({
        id: 'unmapped-symbols',
        severity: 'warning',
        message: `${data.unmapped_symbols.length} unmapped sector symbol(s): ${data.unmapped_symbols.join(', ')}`,
        timestamp: now,
        category: 'system',
      });
    }

    // Uncovered long positions alert (stocks with ≥100 shares but no matching covered call)
    if (data.positions?.list) {
      const positions = data.positions.list as Array<Record<string, unknown>>;
      const callSymbols = new Set<string>();
      for (const pos of positions) {
        if (pos.sec_type === 'OPT' && typeof pos.symbol === 'string' && (pos.quantity as number) < 0) {
          const sym = (pos.symbol as string).split(' ')[0];
          if ((pos.symbol as string).includes('C ')) {
            callSymbols.add(sym);
          }
        }
      }
      const hedgeEtfs = new Set(['VXX', 'VIXY', 'TZA', 'SQQQ', 'SPXS', 'UVXY']);
      const uncovered: string[] = [];
      for (const pos of positions) {
        if (
          pos.sec_type === 'STK' &&
          pos.side === 'LONG' &&
          typeof pos.quantity === 'number' &&
          pos.quantity >= 100 &&
          typeof pos.symbol === 'string' &&
          !callSymbols.has(pos.symbol) &&
          !hedgeEtfs.has(pos.symbol)
        ) {
          uncovered.push(pos.symbol);
        }
      }
      if (uncovered.length > 0) {
        alerts.push({
          id: 'uncovered-positions',
          severity: 'info',
          message: `${uncovered.length} long position(s) without covered calls: ${uncovered.join(', ')}`,
          timestamp: now,
          category: 'opportunity',
        });
      }
    }

    // Assignment risk alert (ITM short options)
    const assignAlertPath = path.join(tradingDir, 'logs', 'assignment_alerts_today.json');
    if (fs.existsSync(assignAlertPath)) {
      try {
        const assignData = JSON.parse(fs.readFileSync(assignAlertPath, 'utf-8'));
        const today = new Date().toISOString().slice(0, 10);
        if (assignData.date === today) {
          const alerted = assignData.alerted || {};
          const itmKeys = Object.entries(alerted).filter(
            ([, level]) => level === 'ITM' || level === 'DEEP_ITM' || level === 'DIVIDEND',
          );
          if (itmKeys.length > 0) {
            const symbols = itmKeys.map(([k]) => k.split('_')[0]);
            const uniqueSymbols = [...new Set(symbols)];
            const hasDeep = itmKeys.some(([, level]) => level === 'DEEP_ITM' || level === 'DIVIDEND');
            alerts.push({
              id: 'assignment-risk',
              severity: hasDeep ? 'critical' : 'warning',
              message: `${uniqueSymbols.length} option(s) ITM — assignment risk: ${uniqueSymbols.join(', ')}`,
              timestamp: now,
              category: 'risk',
            });
          }
        }
      } catch {
        // ignore
      }
    }

    // Drawdown circuit breaker alert
    const breakerStatePath = path.join(tradingDir, 'logs', 'drawdown_breaker_state.json');
    if (fs.existsSync(breakerStatePath)) {
      try {
        const breaker = JSON.parse(fs.readFileSync(breakerStatePath, 'utf-8'));
        const tier = typeof breaker.tier === 'number' ? breaker.tier : 0;
        const dd = typeof breaker.drawdown_pct === 'number' ? breaker.drawdown_pct : 0;
        if (tier >= 3) {
          alerts.push({
            id: 'drawdown-breaker',
            severity: 'critical',
            message: `Drawdown breaker TIER 3 — kill switch activated (${dd.toFixed(1)}% daily loss)`,
            timestamp: breaker.last_checked || now,
            category: 'risk',
          });
        } else if (tier === 2) {
          alerts.push({
            id: 'drawdown-breaker',
            severity: 'critical',
            message: `Drawdown breaker TIER 2 — all new entries HALTED (${dd.toFixed(1)}% daily loss)`,
            timestamp: breaker.last_checked || now,
            category: 'risk',
          });
        } else if (tier === 1) {
          alerts.push({
            id: 'drawdown-breaker',
            severity: 'warning',
            message: `Drawdown breaker TIER 1 — position sizes reduced 50% (${dd.toFixed(1)}% daily loss)`,
            timestamp: breaker.last_checked || now,
            category: 'risk',
          });
        }
      } catch {
        // ignore
      }
    }

    // Kill switch active alert
    const killSwitchPath = path.join(tradingDir, 'kill_switch.json');
    if (fs.existsSync(killSwitchPath)) {
      try {
        const ks = JSON.parse(fs.readFileSync(killSwitchPath, 'utf-8'));
        if (ks.active) {
          alerts.push({
            id: 'kill-switch',
            severity: 'critical',
            message: `Kill switch active: ${ks.reason || 'Manual trigger'}`,
            timestamp: ks.timestamp || now,
            category: 'risk',
          });
        }
      } catch {
        // ignore
      }
    }

    return NextResponse.json(alerts);
  } catch (error) {
    console.error('Error generating alerts:', error);
    return NextResponse.json([]);
  }
}
