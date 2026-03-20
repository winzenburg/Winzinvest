import { NextResponse } from 'next/server';
import { requireAuth } from '../../../lib/auth';
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

interface MacroEvent {
  id: string;
  event: string;
  start_date: string;
  end_date: string | null;
  sector_boosts: Record<string, number>;
  sector_caps_override: Record<string, number>;
  size_multiplier_adjust: number;
  active: boolean;
}

function isMacroEvent(item: unknown): item is MacroEvent {
  if (typeof item !== 'object' || item === null) return false;
  const obj = item as Record<string, unknown>;
  return (
    typeof obj.id === 'string' &&
    typeof obj.event === 'string' &&
    typeof obj.active === 'boolean'
  );
}

function loadActiveMacroEvents(): MacroEvent[] {
  try {
    const eventsPath = path.join(TRADING_DIR, 'config', 'macro_events.json');
    if (!fs.existsSync(eventsPath)) return [];
    const raw: unknown = JSON.parse(fs.readFileSync(eventsPath, 'utf-8'));
    if (!Array.isArray(raw)) return [];
    const today = new Date().toISOString().slice(0, 10);
    return raw.filter(isMacroEvent).filter((ev) => {
      if (!ev.active) return false;
      if (ev.start_date && today < ev.start_date) return false;
      if (ev.end_date && today > ev.end_date) return false;
      return true;
    });
  } catch {
    return [];
  }
}

function getMergedSectorCaps(events: MacroEvent[]): Record<string, number> {
  const caps: Record<string, number> = {};
  for (const ev of events) {
    if (ev.sector_caps_override && typeof ev.sector_caps_override === 'object') {
      for (const [sector, cap] of Object.entries(ev.sector_caps_override)) {
        if (typeof cap === 'number') {
          caps[sector] = Math.max(caps[sector] ?? 0, cap);
        }
      }
    }
  }
  return caps;
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

function buildAlerts(
  data: SnapshotData,
  riskLimits: { dailyLossLimit: number; maxSectorPct: number },
  extraAlerts: Alert[],
  sectorCapOverrides: Record<string, number> = {},
): Alert[] {
  const alerts: Alert[] = [];
  const now = new Date().toISOString();
  const { dailyLossLimit, maxSectorPct } = riskLimits;

  const nlv      = data.account?.net_liquidation || 1;
  const rawPnl   = data.performance?.daily_pnl ?? 0;
  const dailyLossPct = rawPnl < 0 ? Math.abs(rawPnl) / nlv : 0;

  if (dailyLossPct > dailyLossLimit * 0.8) {
    alerts.push({
      id: 'daily-loss-warning',
      severity: dailyLossPct > dailyLossLimit ? 'critical' : 'warning',
      message: `Daily loss at ${(dailyLossPct * 100).toFixed(1)}% (limit: ${(dailyLossLimit * 100).toFixed(1)}%)`,
      timestamp: now, category: 'risk',
    });
  }

  const marginPct = Number(data.risk?.margin_utilization_pct ?? 0);
  if (marginPct > 80) {
    alerts.push({
      id: 'margin-warning', severity: 'warning',
      message: `High margin utilization: ${marginPct.toFixed(1)}%`,
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

      const effectiveCapPct = typeof sectorCapOverrides[sector] === 'number'
        ? sectorCapOverrides[sector] * 100
        : maxSectorPct;

      if (sectorPct > effectiveCapPct) {
        const excess = Math.abs(dollarValue) - totalNotional * (effectiveCapPct / 100);
        alerts.push({
          id: `sector-${sector}`,
          severity: sectorPct > effectiveCapPct * 1.2 ? 'critical' : 'warning',
          message: `${sector} at ${sectorPct.toFixed(1)}% (limit ${effectiveCapPct.toFixed(0)}%) — reduce ~$${(excess / 1000).toFixed(1)}k to comply`,
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
  const freshnessMinutes = health?.data_freshness_minutes;
  if (typeof freshnessMinutes === 'number' && freshnessMinutes > 120 && inMarketHours) {
    alerts.push({
      id: 'stale-data', severity: 'info',
      message: `Data is ${freshnessMinutes} minutes old`,
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
  const unauth = await requireAuth();
  if (unauth) return unauth;
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

    const activeMacroEvents = loadActiveMacroEvents();
    const sectorCapOverrides = getMergedSectorCaps(activeMacroEvents);

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

    // Macro event info banners
    for (const ev of activeMacroEvents) {
      const capInfo = ev.sector_caps_override
        ? Object.entries(ev.sector_caps_override)
            .map(([s, c]) => `${s} cap → ${(Number(c) * 100).toFixed(0)}%`)
            .join(', ')
        : '';
      extraAlerts.push({
        id: `macro-event-${ev.id}`,
        severity: 'info',
        message: `Active macro event: ${ev.event}${capInfo ? ` — ${capInfo}` : ''}`,
        timestamp: now,
        category: 'macro',
      });
    }

    // Commodity trigger info banners
    interface CommodityTriggers {
      oil_30d_pct?: number;       oil_level?: string;      energy_multiplier?: number;
      wheat_30d_pct?: number;     wheat_level?: string;
      natgas_30d_pct?: number;    natgas_level?: string;
      copper_30d_pct?: number;    copper_level?: string;   copper_multiplier?: number;
      corn_30d_pct?: number;      corn_level?: string;
      soybean_30d_pct?: number;   soybean_level?: string;
      usd_30d_pct?: number;       usd_level?: string;      usd_multiplier?: number;
      food_chain_alert?: boolean;
      livestock_chain_alert?: boolean;
      checked_at?: string;
    }
    const regimeState = readJson<{ commodity_triggers?: CommodityTriggers }>(
      path.join(LOGS_DIR, 'regime_state.json'),
    );
    const ct = regimeState?.commodity_triggers;

    // Helper: emit a commodity banner when a level is not NORMAL
    function ctBanner(
      id: string,
      level: string | undefined,
      pct: number | undefined,
      label: string,
      note: string,
    ) {
      if (!level || level === 'NORMAL') return;
      const pctStr = typeof pct === 'number' ? pct.toFixed(1) : '?';
      extraAlerts.push({
        id: `commodity-trigger-${id}`,
        severity: level === 'CRISIS' || level === 'COLLAPSE' ? 'warning' : 'info',
        message: `${label} ${pctStr}% 30d (${level}) — ${note}`,
        timestamp: ct?.checked_at ?? now,
        category: 'macro',
      });
    }

    if (ct) {
      ctBanner('oil',      ct.oil_level,     ct.oil_30d_pct,     'Oil',         `Energy sector boost ${(ct.energy_multiplier ?? 1).toFixed(2)}x`);
      ctBanner('wheat',    ct.wheat_level,   ct.wheat_30d_pct,   'Wheat',       'food cost inflation signal');
      ctBanner('natgas',   ct.natgas_level,  ct.natgas_30d_pct,  'Natural Gas', 'fertilizer feedstock proxy');
      ctBanner('copper',   ct.copper_level,  ct.copper_30d_pct,  'Copper',      ct.copper_level === 'SURGE' ? 'construction/industrial boom' : 'industrial demand warning');
      ctBanner('corn',     ct.corn_level,    ct.corn_30d_pct,    'Corn',        'animal feed / ethanol cost pressure');
      ctBanner('soybean',  ct.soybean_level, ct.soybean_30d_pct, 'Soybeans',   'Crush margin pressure on ag processors');
      ctBanner('usd',      ct.usd_level,     ct.usd_30d_pct,     'USD Index',   ct.usd_level === 'SURGE' ? 'strong dollar suppresses commodity prices' : 'weak dollar inflates commodity prices');

      if (ct.food_chain_alert) {
        extraAlerts.push({
          id: 'food-chain-alert', severity: 'warning',
          message: 'Oil-to-food supply chain stress — oil, wheat, and/or natgas elevated simultaneously → Consumer Staples margin penalty active',
          timestamp: ct.checked_at ?? now, category: 'macro',
        });
      }
      if (ct.livestock_chain_alert) {
        extraAlerts.push({
          id: 'livestock-chain-alert', severity: 'warning',
          message: 'Livestock chain alert — corn and/or soy elevated → feed margins under pressure (Consumer Staples ag processors)',
          timestamp: ct.checked_at ?? now, category: 'macro',
        });
      }
    }

    // News sentiment banners
    interface NewsSentiment {
      timestamp?: string;
      portfolio_sentiment?: number;
      macro_sentiment?: number;
      worst_headlines?: Array<{ title?: string; sentiment?: number; symbols?: string[] }>;
      articles_analyzed?: number;
    }
    const newsSent = readJson<NewsSentiment>(path.join(LOGS_DIR, 'news_sentiment.json'));
    if (newsSent) {
      const macroSent = newsSent.macro_sentiment;
      if (typeof macroSent === 'number' && macroSent <= -0.5) {
        extraAlerts.push({
          id: 'news-macro-sentiment',
          severity: macroSent <= -0.7 ? 'warning' : 'info',
          message: `Macro news sentiment ${macroSent.toFixed(3)} — ${newsSent.articles_analyzed ?? 0} articles analyzed`,
          timestamp: newsSent.timestamp ?? now,
          category: 'macro',
        });
      }
      const headlines = newsSent.worst_headlines;
      if (Array.isArray(headlines) && headlines.length > 0) {
        const top = headlines[0];
        if (top && typeof top.sentiment === 'number' && top.sentiment <= -0.5) {
          const syms = Array.isArray(top.symbols) ? top.symbols.join(', ') : '';
          extraAlerts.push({
            id: 'news-worst-headline',
            severity: 'info',
            message: `News alert${syms ? ` (${syms})` : ''}: "${(top.title ?? '').slice(0, 100)}" — sentiment ${top.sentiment.toFixed(2)}`,
            timestamp: newsSent.timestamp ?? now,
            category: 'macro',
          });
        }
      }
    }

    return NextResponse.json(buildAlerts(data, riskLimits, extraAlerts, sectorCapOverrides));
  } catch (error) {
    if (process.env.NODE_ENV === 'development') console.error('Error generating alerts:', error);
    return NextResponse.json([]);
  }
}
