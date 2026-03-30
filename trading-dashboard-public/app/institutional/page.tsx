'use client';

import { use, useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { useSession } from 'next-auth/react';
import type { AnalyticsData } from '../api/analytics/route';
import type { StrategyAttribution } from '../api/strategy-attribution/route';
import AlertBanner from '../components/AlertBanner';
import DashboardNav from '../components/DashboardNav';
import DashboardAnalyticsContent from '../components/DashboardAnalyticsContent';
import EquityCurve from '../components/EquityCurve';
import RiskMetrics from '../components/RiskMetrics';
import StrategyBreakdown from '../components/StrategyBreakdown';
import TradeAnalytics from '../components/TradeAnalytics';
import BacktestComparison from '../components/BacktestComparison';
import Tooltip from '../components/Tooltip';
import SystemMonitor from '../components/SystemMonitor';
import CorrelationHeatMap from '../components/CorrelationHeatMap';
import IntelligencePanel from '../components/IntelligencePanel';
import { useTradingMode } from '../context/TradingModeContext';
import ErrorBoundary from '../components/ErrorBoundary';
import { exportPositionsCsv, exportPerformanceCsv } from '../utils/export';
import OnboardingTour from '../components/OnboardingTour';
import NotificationPrefsPanel from '../components/NotificationPrefs';
import { fetchWithAuth } from '@/lib/fetch-client';

type Tab = 'overview' | 'intelligence' | 'risk' | 'performance' | 'analytics' | 'positions';

/** Absolute `trading/` folder for Winzinvest (spaces in path — use quoted `cd` as shown). */
const MISSION_CONTROL_TRADING_ABSOLUTE =
  '/Users/ryanwinzenburg/Library/CloudStorage/GoogleDrive-ryanwinzenburg@gmail.com/My Drive/Projects/MIssion Control/trading';

const COMPREHENSIVE_BACKTEST_SAVE_CMD = `cd "${MISSION_CONTROL_TRADING_ABSOLUTE}" && python3 -m backtest.comprehensive_backtest --years 2 --enhanced-only --save`;

/** Used only when snapshot has no valid `equity_backtest_benchmark` (run comprehensive_backtest --save). */
const FALLBACK_BACKTEST_BENCHMARK = {
  sharpe: 4.03,
  win_rate: 47.1,
  max_drawdown: 12.6,
  avg_return: 1450,
  total_trades: 588,
} as const;

type BacktestBenchmarkMetrics = {
  sharpe: number;
  win_rate: number;
  max_drawdown: number;
  avg_return: number;
  total_trades: number;
};

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null;
}

/** Parse `equity_backtest_benchmark` from dashboard snapshot (written by comprehensive_backtest). */
function parseEquityBacktestBenchmark(raw: unknown): {
  metrics: BacktestBenchmarkMetrics;
  caption: string;
} | null {
  if (!isRecord(raw)) return null;
  const sharpe = raw.sharpe;
  const win_rate_pct = raw.win_rate_pct;
  const max_drawdown_pct = raw.max_drawdown_pct;
  const avg_pnl = raw.avg_pnl_per_trade_usd;
  const total_trades = raw.total_trades;
  if (typeof sharpe !== 'number' || !Number.isFinite(sharpe)) return null;
  if (typeof win_rate_pct !== 'number' || !Number.isFinite(win_rate_pct)) return null;
  if (typeof max_drawdown_pct !== 'number' || !Number.isFinite(max_drawdown_pct)) return null;
  if (typeof avg_pnl !== 'number' || !Number.isFinite(avg_pnl)) return null;
  if (typeof total_trades !== 'number' || !Number.isFinite(total_trades) || total_trades < 0) {
    return null;
  }
  const generated =
    typeof raw.generated_at === 'string' ? raw.generated_at.replace('T', ' ').slice(0, 19) : '';
  const years = typeof raw.years === 'number' && raw.years > 0 ? raw.years : null;
  const source =
    typeof raw.source === 'string' && raw.source.length > 0
      ? raw.source
      : 'comprehensive_backtest_enhanced';
  const caption = `Backtest: ${source}${years != null ? ` · ${years}y window` : ''}${generated ? ` · ${generated}` : ''}.`;
  return {
    metrics: {
      sharpe,
      win_rate: win_rate_pct,
      max_drawdown: max_drawdown_pct,
      avg_return: avg_pnl,
      total_trades: Math.round(total_trades),
    },
    caption,
  };
}

interface DashboardData {
  timestamp: string;
  trading_mode?: string;
  live_allocation_pct?: number;
  account: {
    net_liquidation: number;
    buying_power: number;
    excess_liquidity: number;
    leverage_ratio: number;
  };
  performance: {
    daily_pnl: number;
    daily_return_pct: number;
    total_pnl_30d: number;
    sharpe_ratio: number;
    sortino_ratio: number;
    max_drawdown_pct: number;
    win_rate: number;
    profit_factor: number;
    avg_win: number;
    avg_loss: number;
    total_trades: number;
    var_95: number;
    cvar_95: number;
    var_99: number;
    cvar_99: number;
  };
  positions: {
    list: PositionRow[];
    count: number;
    long_notional: number;
    short_notional: number;
    net_exposure: number;
    gross_exposure: number;
  };
  risk: {
    sector_exposure: Record<string, number>;
    beta: number;
    correlation_spy: number;
    margin_utilization_pct: number;
    buying_power_used_pct: number;
  };
  strategy_breakdown: Record<string, StrategyData>;
  trade_analytics: {
    avg_mae: number;
    avg_mfe: number;
    avg_slippage_bps: number;
    avg_hold_time_hours: number;
    best_trade: number;
    worst_trade: number;
    largest_position: number;
  };
  correlation_matrix?: {
    symbols: string[];
    matrix: number[][];
  };
  market_regime?: {
    regime: string;           // Layer 1: execution gating (CHOPPY | MIXED | STRONG_UPTREND | STRONG_DOWNTREND | UNFAVORABLE)
    note: string;
    catalysts: string[];
    updated_at: string;
    macro_regime: string;     // Layer 2: macro stress band (RISK_ON | NEUTRAL | TIGHTENING | DEFENSIVE)
    macro_score: number;
    macro_updated_at: string;
    macro_alerts: string[];
    macro_parameters?: {
      size_multiplier: number;
      z_enter: number;
      atr_multiplier: number;
      cooldown_days: number;
    };
  };
  system_health: {
    status: string;
    issues: string[];
    data_freshness_minutes: number;
  };
  /** From trading/logs/equity_backtest_benchmark.json via dashboard_data_aggregator. */
  equity_backtest_benchmark?: unknown;
}

interface PositionRow {
  symbol: string;
  side: string;
  quantity: number;
  avg_cost: number | null;
  market_price: number | null;
  notional: number;
  unrealized_pnl: number | null;
  return_pct: number | null;
  sector: string;
  stop_price: number | null;
  stop_side: 'LONG' | 'SHORT' | null;
}

interface StrategyData {
  trades: number;
  pnl: number;
  wins: number;
  losses: number;
  win_rate: number;
}

interface EquityPoint {
  date: string;
  equity: number;
  drawdown: number;
}

const TABS: { id: Tab; label: string; description: string }[] = [
  { id: 'overview',      label: 'Overview',      description: 'P&L, equity curve, account summary' },
  { id: 'intelligence',  label: 'Intelligence',   description: 'AI recommendations and portfolio decisions' },
  { id: 'risk',          label: 'Risk',           description: 'Exposure, VaR, margins, sector concentrations' },
  { id: 'performance',   label: 'Performance',    description: 'Strategy breakdown, trade analytics, backtest' },
  { id: 'analytics',     label: 'Analytics',      description: 'R-multiples, attribution, exit mix, conviction tiers' },
  { id: 'positions',     label: 'Positions',      description: `Open positions table` },
];

type PageProps = {
  params?: Promise<Record<string, string | string[]>>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

const EMPTY = Promise.resolve({});

export default function InstitutionalDashboard(props: PageProps) {
  use(props.params ?? EMPTY);
  use(props.searchParams ?? EMPTY);
  
  // All hooks MUST be called before any conditional returns (Rules of Hooks).
  const { data: session, status } = useSession();
  const { viewMode } = useTradingMode();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string>('');
  const [equityCurveData, setEquityCurveData] = useState<EquityPoint[]>([]);
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [showNotifPrefs, setShowNotifPrefs] = useState(false);
  const [analyticsData, setAnalyticsData] = useState<AnalyticsData | null>(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsError, setAnalyticsError] = useState<string | null>(null);
  const [strategyAttribution, setStrategyAttribution] = useState<StrategyAttribution | null>(null);

  type SortKey = 'symbol' | 'side' | 'quantity' | 'avg_cost' | 'market_price' | 'notional' | 'unrealized_pnl' | 'return_pct' | 'sector' | 'stop_price';
  type SortDir = 'asc' | 'desc';
  const [sortKey, setSortKey] = useState<SortKey>('notional');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const fetchData = useCallback(async () => {
    try {
      const res = await fetchWithAuth(`/api/dashboard?mode=${viewMode}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as { error?: string }).error ?? 'Failed to fetch dashboard data');
      }
      const json = await res.json() as DashboardData;
      setData(json);
      setLastUpdate(new Date().toLocaleTimeString());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [viewMode]);

  const fetchEquityHistory = useCallback(async () => {
    try {
      const res = await fetchWithAuth('/api/equity-history');
      console.log('[fetchEquityHistory] response status:', res.status, 'ok:', res.ok);
      if (res.ok) {
        const json = await res.json() as { points?: EquityPoint[]; _debug?: unknown };
        console.log('[fetchEquityHistory] received:', {
          hasPoints: 'points' in json,
          isArray: Array.isArray(json.points),
          length: json.points?.length ?? 0,
          debug: json._debug
        });
        if (Array.isArray(json.points) && json.points.length > 0) {
          console.log('[fetchEquityHistory] setting data with', json.points.length, 'points');
          setEquityCurveData(json.points);
        } else {
          console.warn('[fetchEquityHistory] data check failed - not setting state');
        }
      }
    } catch (err) {
      console.error('[fetchEquityHistory] error:', err);
      // equity history is best-effort
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchData();
    fetchEquityHistory();
    const interval = setInterval(fetchData, 30000);
    const historyInterval = setInterval(fetchEquityHistory, 300000);
    return () => {
      clearInterval(interval);
      clearInterval(historyInterval);
    };
  }, [fetchData, fetchEquityHistory]);

  useEffect(() => {
    if (activeTab !== 'analytics') return;
    let cancelled = false;
    setAnalyticsLoading(true);
    setAnalyticsError(null);
    void (async () => {
      try {
        const res = await fetchWithAuth('/api/analytics');
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error((body as { error?: string }).error ?? `HTTP ${res.status}`);
        }
        const json = (await res.json()) as AnalyticsData;
        if (!cancelled) setAnalyticsData(json);
      } catch (e) {
        if (!cancelled) {
          setAnalyticsData(null);
          setAnalyticsError(e instanceof Error ? e.message : 'Failed to load analytics');
        }
      } finally {
        if (!cancelled) setAnalyticsLoading(false);
      }
    })();
    void fetchWithAuth('/api/strategy-attribution')
      .then((res) => (res.ok ? (res.json() as Promise<StrategyAttribution>) : null))
      .then((d) => {
        if (!cancelled && d) setStrategyAttribution(d);
      })
      .catch(() => {
        /* optional report — non-fatal */
      });
    return () => {
      cancelled = true;
    };
  }, [activeTab]);

  // Helper functions (not hooks, can be anywhere)
  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir(key === 'symbol' || key === 'side' || key === 'sector' ? 'asc' : 'desc');
    }
  }

  const numericSortKeys = new Set(['quantity', 'avg_cost', 'market_price', 'notional', 'unrealized_pnl', 'return_pct', 'stop_price']);

  function sortedPositions(list: PositionRow[]): PositionRow[] {
    return [...list].sort((a, b) => {
      const rawA = a[sortKey];
      const rawB = b[sortKey];
      const isNumeric = numericSortKeys.has(sortKey);
      const av = rawA ?? (isNumeric ? -Infinity : '');
      const bv = rawB ?? (isNumeric ? -Infinity : '');
      let cmp = 0;
      if (typeof av === 'string' && typeof bv === 'string') {
        cmp = av.localeCompare(bv);
      } else {
        const na = typeof av === 'number' ? av : -Infinity;
        const nb = typeof bv === 'number' ? bv : -Infinity;
        cmp = na < nb ? -1 : na > nb ? 1 : 0;
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }

  // NOW conditional returns can happen after all hooks are called.
  if (status === 'loading') {
    return (
      <div className="min-h-screen bg-slate-900 text-white flex items-center justify-center">
        <p className="text-sm text-white/70">Checking access…</p>
      </div>
    );
  }

  if (session && (session.user as { role?: string }).role !== 'admin') {
    return (
      <div className="min-h-screen bg-slate-900 text-white flex items-center justify-center px-4">
        <div className="max-w-md text-center">
          <h1 className="font-serif text-2xl font-bold mb-3">
            Trading dashboard is restricted
          </h1>
          <p className="text-sm text-white/70 mb-4">
            This account does not have access to the full Winzinvest trading dashboard.
            Please contact the account owner if you believe this is a mistake.
          </p>
          <Link
            href="/"
            className="inline-flex items-center justify-center px-4 py-2.5 rounded-xl bg-white text-slate-900 text-sm font-semibold"
          >
            Back to landing page
          </Link>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center">
        <div className="text-stone-400">Loading dashboard…</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center">
        <div className="text-center">
          <div className="text-danger-600 font-semibold mb-2">Error Loading Dashboard</div>
          <div className="text-stone-500 text-sm">{error}</div>
          <div className="text-stone-400 text-xs mt-4">
            Confirm the portfolio snapshot job is running and you are signed in.
          </div>
        </div>
      </div>
    );
  }

  const isDataStale = data.system_health.data_freshness_minutes > 5;
  const isLive = viewMode === 'live';

  const equityBenchParsed = parseEquityBacktestBenchmark(data.equity_backtest_benchmark);
  const backtestBenchmarkMetrics = equityBenchParsed?.metrics ?? FALLBACK_BACKTEST_BENCHMARK;
  const backtestBenchmarkCaption =
    equityBenchParsed?.caption ??
    `Backtest: placeholder values (not synced). Run: ${COMPREHENSIVE_BACKTEST_SAVE_CMD} — then refresh the dashboard snapshot.`;

  // Theme is always light — isLive only controls data source & warning banners
  const bg = 'dashboard-bg-light';
  const border = 'border-slate-200';
  const cardBg = 'bg-white border-slate-200';
  const textMuted = 'text-slate-600';   // slate-600 on white = 7:1 contrast (AA+)
  const textFaint = 'text-slate-500';   // slate-500 on white = 4.6:1 (AA for normal text)

  return (
    <div className={`min-h-screen ${bg}`}>
      {/* Brand stripe — sky-600 gradient top accent */}
      <div className="brand-stripe" />

      {/* Live mode banner */}
      {isLive && (
        <div className="bg-danger-600 text-white text-center text-xs font-semibold py-1.5 tracking-wide">
          LIVE TRADING
          {data.live_allocation_pct != null && (
            <span className="ml-2 font-normal opacity-80">
              {(data.live_allocation_pct * 100).toFixed(0)}% allocation — real money at risk
            </span>
          )}
        </div>
      )}

      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-white focus:border focus:border-stone-200 focus:rounded-lg focus:text-slate-900 focus:font-semibold"
      >
        Skip to main content
      </a>

      <div className="max-w-[1600px] mx-auto px-6 lg:px-10 pt-8 pb-16">

        <DashboardNav
          onOpenNotificationPrefs={() => setShowNotifPrefs(true)}
          extraLinks={
            <Link
              href="/docs/guide"
              className="px-3 py-1.5 text-sm font-medium rounded-lg border border-slate-200 text-slate-600 hover:bg-white hover:border-slate-300 hover:shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-primary-600 focus:ring-offset-1"
            >
              Guide
            </Link>
          }
          statusSlot={
            <div className="text-right w-full sm:w-auto" role="status" aria-live="polite">
              <p className="text-sm text-slate-500 text-left sm:text-right mb-0.5">Institutional Dashboard</p>
              <div className={`flex items-center justify-end gap-2 text-sm ${textMuted}`}>
                <span
                  className={`w-2 h-2 rounded-full ${
                    data.system_health.status === 'healthy' ? 'bg-green-500' :
                    data.system_health.status === 'warning' ? 'bg-orange-500' :
                    'bg-red-500'
                  }`}
                  aria-hidden
                />
                <span>{data.system_health.status}</span>
              </div>
              <div className={`text-xs mt-0.5 ${textFaint}`}>Updated {lastUpdate}</div>
              {data.system_health.data_freshness_minutes > 0 && (
                <div className={`text-xs mt-0.5 ${isDataStale ? 'text-orange-500 font-medium' : textFaint}`}>
                  Data: {data.system_health.data_freshness_minutes}m old
                  {isDataStale && ' — may be delayed'}
                </div>
              )}
            </div>
          }
        />

        {/* ── Always-visible: Alerts ── */}
        <ErrorBoundary section="Alert Banner" compact>
          <AlertBanner />
        </ErrorBoundary>

        {/* ── Tab bar — inverted dark pill for premium institutional look ── */}
        <div className="flex gap-1 mb-6 p-1 rounded-xl bg-slate-900" role="tablist" aria-label="Dashboard sections">
          {TABS.map(tab => {
            const isActive = activeTab === tab.id;
            const label = tab.id === 'positions'
              ? `${tab.label} (${data.positions.count})`
              : tab.label;
            return (
              <button
                type="button"
                key={tab.id}
                role="tab"
                aria-selected={isActive}
                aria-controls={`tabpanel-${tab.id}`}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 py-2 px-3 text-sm font-medium rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-primary-600 focus:ring-offset-1 focus:ring-offset-slate-900 ${
                  isActive
                    ? 'bg-white text-slate-900 tab-active-light'
                    : 'text-slate-300 hover:text-white hover:bg-slate-700'
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>

        {/* ── Tab panels ── */}
        <main id="main-content">

          {/* Overview */}
          {activeTab === 'overview' && (
            <div role="tabpanel" id="tabpanel-overview" aria-labelledby="tab-overview">
              {/* Key metrics */}
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
                <MetricCard
                  label="Net Liquidation"
                  value={formatCurrency(data.account.net_liquidation)}
                  color="text-primary-600"
                  subtitle={`Leverage: ${data.account.leverage_ratio.toFixed(2)}x`}
                  title="Total account value (cash + positions). From IBKR."
                />
                <MetricCard
                  label="Daily P&L"
                  value={formatCurrency(data.performance.daily_pnl)}
                  color={data.performance.daily_pnl >= 0 ? 'text-success-600' : 'text-danger-600'}
                  subtitle={`${data.performance.daily_return_pct >= 0 ? '+' : ''}${data.performance.daily_return_pct.toFixed(2)}%`}
                  title="Realized + unrealized P&L for current session."
                />
                <MetricCard
                  label="30d P&L"
                  value={formatCurrency(data.performance.total_pnl_30d)}
                  color={data.performance.total_pnl_30d >= 0 ? 'text-success-600' : 'text-danger-600'}
                  subtitle={`Win rate: ${data.performance.win_rate.toFixed(1)}%`}
                  title="Cumulative P&L over trailing 30 days from closed trades."
                />
                <MetricCard
                  label="Sharpe Ratio"
                  value={data.performance.sharpe_ratio.toFixed(2)}
                  color="text-slate-900"
                  subtitle={`Sortino: ${data.performance.sortino_ratio.toFixed(2)}`}
                  title="Risk-adjusted return (30d). Excess return per unit of volatility."
                />
                <MetricCard
                  label="Open Positions"
                  value={data.positions.count.toString()}
                  color="text-slate-900"
                  subtitle={`${data.performance.total_trades} closed trades (30d)`}
                  title="Current open positions. Trade count is trailing 30 days closed."
                />
              </div>

              {/* Market Regime */}
              {(() => {
                const regime = data.market_regime;

                // Layer 1: execution regime (CHOPPY | MIXED | STRONG_UPTREND | STRONG_DOWNTREND | UNFAVORABLE)
                const execLabel = regime?.regime ?? 'UNKNOWN';
                const note = regime?.note ?? '';
                const catalysts = regime?.catalysts ?? [];
                const updatedAt = regime?.updated_at ? new Date(regime.updated_at).toLocaleString() : '';

                // Layer 2: macro stress band (RISK_ON | NEUTRAL | TIGHTENING | DEFENSIVE)
                const macroLabel = regime?.macro_regime ?? '';
                const macroScore = regime?.macro_score ?? 0;
                const macroSizeMult = regime?.macro_parameters?.size_multiplier ?? 1.0;

                // Normalize to handle spaces, dashes, and case variants
                const normalizeKey = (k: string) => k.toUpperCase().replace(/[\s-]+/g, '_');
                const nKey = normalizeKey(execLabel);

                // Color map covers both Layer 1 and Layer 2 labels
                const colorMap: Record<string, string> = {
                  // Layer 1 — execution regime
                  STRONG_UPTREND:   'bg-emerald-50 border-emerald-300 text-emerald-800',
                  CHOPPY:           'bg-blue-50 border-blue-300 text-blue-800',
                  MIXED:            'bg-amber-50 border-amber-300 text-amber-800',
                  STRONG_DOWNTREND: 'bg-red-50 border-red-300 text-red-800',
                  UNFAVORABLE:      'bg-stone-100 border-stone-300 text-stone-700',
                  // Layer 2 — macro band (legacy / fallback)
                  BULL:          'bg-emerald-50 border-emerald-300 text-emerald-800',
                  BULL_QUIET:    'bg-emerald-50 border-emerald-300 text-emerald-800',
                  BULL_MOMENTUM: 'bg-emerald-50 border-emerald-300 text-emerald-800',
                  RISK_ON:       'bg-emerald-50 border-emerald-300 text-emerald-800',
                  NEUTRAL:       'bg-amber-50 border-amber-300 text-amber-800',
                  RANGE_BOUND:   'bg-amber-50 border-amber-300 text-amber-800',
                  BEAR:          'bg-red-50 border-red-300 text-red-800',
                  BEAR_VOLATILE: 'bg-red-50 border-red-300 text-red-800',
                  RISK_OFF:      'bg-red-50 border-red-300 text-red-800',
                  DEFENSIVE:     'bg-orange-50 border-orange-300 text-orange-800',
                  TIGHTENING:    'bg-orange-50 border-orange-300 text-orange-800',
                  VOLATILE:      'bg-purple-50 border-purple-300 text-purple-800',
                };
                const dotMap: Record<string, string> = {
                  STRONG_UPTREND: 'bg-emerald-500', CHOPPY: 'bg-blue-500',
                  MIXED: 'bg-amber-500', STRONG_DOWNTREND: 'bg-red-500', UNFAVORABLE: 'bg-stone-400',
                  BULL: 'bg-emerald-500', BULL_QUIET: 'bg-emerald-500', BULL_MOMENTUM: 'bg-emerald-500', RISK_ON: 'bg-emerald-500',
                  NEUTRAL: 'bg-amber-500', RANGE_BOUND: 'bg-amber-500',
                  BEAR: 'bg-red-500', BEAR_VOLATILE: 'bg-red-500', RISK_OFF: 'bg-red-500',
                  DEFENSIVE: 'bg-orange-500', TIGHTENING: 'bg-orange-500',
                  VOLATILE: 'bg-purple-500',
                };
                const pingMap: Record<string, string> = {
                  STRONG_UPTREND: 'bg-emerald-400', CHOPPY: 'bg-blue-400',
                  MIXED: 'bg-amber-400', STRONG_DOWNTREND: 'bg-red-400', UNFAVORABLE: 'bg-stone-300',
                  BULL: 'bg-emerald-400', BULL_QUIET: 'bg-emerald-400', BULL_MOMENTUM: 'bg-emerald-400', RISK_ON: 'bg-emerald-400',
                  NEUTRAL: 'bg-amber-400', RANGE_BOUND: 'bg-amber-400',
                  BEAR: 'bg-red-400', BEAR_VOLATILE: 'bg-red-400', RISK_OFF: 'bg-red-400',
                  DEFENSIVE: 'bg-orange-400', TIGHTENING: 'bg-orange-400',
                  VOLATILE: 'bg-purple-400',
                };

                // Macro band pill colors
                const macroPillMap: Record<string, string> = {
                  RISK_ON:    'bg-emerald-100 text-emerald-800 border-emerald-200',
                  NEUTRAL:    'bg-amber-100 text-amber-800 border-amber-200',
                  TIGHTENING: 'bg-orange-100 text-orange-800 border-orange-200',
                  DEFENSIVE:  'bg-red-100 text-red-800 border-red-200',
                };

                const colors = colorMap[nKey] ?? 'bg-slate-50 border-slate-300 text-slate-700';
                const dot    = dotMap[nKey]   ?? 'bg-slate-400';
                const ping   = pingMap[nKey]  ?? 'bg-slate-300';
                const displayLabel = execLabel.replace(/_/g, ' ');

                const macroPillClass = macroPillMap[normalizeKey(macroLabel)] ?? 'bg-slate-100 text-slate-700 border-slate-200';

                return (
                  <div className={`regime-banner mb-6 border rounded-xl px-5 py-3 ${colors}`}>
                    <div className="flex items-center gap-3 flex-wrap">
                      {/* Pulsing live indicator */}
                      <span className="relative flex h-2.5 w-2.5 shrink-0">
                        <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${ping} opacity-60`} />
                        <span className={`relative inline-flex h-2.5 w-2.5 rounded-full ${dot}`} />
                      </span>

                      {/* Layer 1: Execution regime — primary display */}
                      <div className="flex items-baseline gap-2 shrink-0">
                        <span className="text-[10px] font-semibold uppercase tracking-[0.14em] opacity-50">Execution Regime</span>
                        <span className="text-sm font-bold tracking-wide uppercase">{displayLabel}</span>
                      </div>

                      {/* Layer 2: Macro band pill — secondary display */}
                      {macroLabel && (
                        <>
                          <span className="h-3.5 w-px bg-current opacity-20 shrink-0" />
                          <div className="flex items-baseline gap-1.5 shrink-0">
                            <span className="text-[10px] font-semibold uppercase tracking-[0.14em] opacity-50">Macro Band</span>
                            <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full border uppercase tracking-wide ${macroPillClass}`}>
                              {macroLabel.replace(/_/g, ' ')}
                            </span>
                            {macroScore > 0 && (
                              <span className="text-[10px] opacity-50 tabular-nums">score {macroScore}</span>
                            )}
                          </div>
                        </>
                      )}

                      {/* Size multiplier warning when not 1× */}
                      {macroSizeMult < 1.0 && (
                        <>
                          <span className="h-3.5 w-px bg-current opacity-20 shrink-0" />
                          <span className="text-[11px] font-semibold opacity-70">
                            Size {macroSizeMult.toFixed(2)}×
                          </span>
                        </>
                      )}

                      {/* Divider before note/catalysts */}
                      {(note || catalysts.length > 0) && (
                        <span className="h-3.5 w-px bg-current opacity-20 shrink-0" />
                      )}

                      {note && (
                        <span className="text-xs opacity-65 truncate min-w-0">{note}</span>
                      )}

                      {catalysts.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 min-w-0">
                          {catalysts.map((c: string) => (
                            <span key={c} className="text-[11px] px-2 py-0.5 rounded-full font-medium bg-white/50 border border-current/25 whitespace-nowrap">{c}</span>
                          ))}
                        </div>
                      )}

                      {updatedAt && (
                        <span className="ml-auto text-[11px] opacity-35 shrink-0 tabular-nums pl-4">Updated {updatedAt}</span>
                      )}
                    </div>
                  </div>
                );
              })()}

              {/* Equity curve */}
              <ErrorBoundary section="Equity Curve">
                <EquityCurve data={equityCurveData} />
              </ErrorBoundary>
            </div>
          )}

          {/* Intelligence */}
          {activeTab === 'intelligence' && (
            <div role="tabpanel" id="tabpanel-intelligence" aria-labelledby="tab-intelligence">
              <ErrorBoundary section="Intelligence Panel">
                <IntelligencePanel />
              </ErrorBoundary>
            </div>
          )}

          {/* Risk */}
          {activeTab === 'risk' && (
            <div role="tabpanel" id="tabpanel-risk" aria-labelledby="tab-risk" className="space-y-6">
              {/* Exposure summary */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className={`${cardBg} border rounded-xl p-5`}>
                  <Tooltip text="Total market value of all long positions (shares × price)." placement="above">
                    <h3 className={`text-xs font-semibold uppercase tracking-wider ${textMuted} mb-3`}>Long Exposure</h3>
                  </Tooltip>
                  <div className="font-mono text-2xl font-semibold text-success-600">
                    {formatCurrency(data.positions.long_notional)}
                  </div>
                  <div className={`text-xs mt-1 ${textFaint}`}>
                    {((data.positions.long_notional / (data.account.net_liquidation || 1)) * 100).toFixed(1)}% of NLV
                  </div>
                </div>

                <div className={`${cardBg} border rounded-xl p-5`}>
                  <Tooltip text="Total market value of all short positions (notional)." placement="above">
                    <h3 className={`text-xs font-semibold uppercase tracking-wider ${textMuted} mb-3`}>Short Exposure</h3>
                  </Tooltip>
                  <div className="font-mono text-2xl font-semibold text-danger-600">
                    {formatCurrency(data.positions.short_notional)}
                  </div>
                  <div className={`text-xs mt-1 ${textFaint}`}>
                    {((data.positions.short_notional / (data.account.net_liquidation || 1)) * 100).toFixed(1)}% of NLV
                  </div>
                </div>

                <div className={`${cardBg} border rounded-xl p-5`}>
                  <h3
                    className={`text-xs font-semibold uppercase tracking-wider ${textMuted} mb-3 cursor-help`}
                    title="Long minus short exposure. Positive = net long."
                  >
                    Net Exposure
                  </h3>
                  <div className={`font-mono text-2xl font-semibold ${data.positions.net_exposure >= 0 ? 'text-success-600' : 'text-danger-600'}`}>
                    {formatCurrency(data.positions.net_exposure)}
                  </div>
                  <div className={`text-xs mt-1 ${textFaint}`}>
                    Gross: {formatCurrency(data.positions.gross_exposure)}
                  </div>
                </div>
              </div>

              {/* VaR, margins, sector */}
              <ErrorBoundary section="Risk Metrics">
                <RiskMetrics risk={data.risk} performance={data.performance} nlv={data.account.net_liquidation} />
              </ErrorBoundary>

              {/* Correlation matrix */}
              <ErrorBoundary section="Correlation Heat Map">
                <CorrelationHeatMap data={data.correlation_matrix ?? null} />
              </ErrorBoundary>
            </div>
          )}

          {/* Performance */}
          {activeTab === 'performance' && (
            <div role="tabpanel" id="tabpanel-performance" aria-labelledby="tab-performance" className="space-y-6">
              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={() => exportPerformanceCsv({
                    period: '30 days',
                    total_pnl: data.performance.total_pnl_30d,
                    win_rate: data.performance.win_rate,
                    sharpe: data.performance.sharpe_ratio,
                    sortino: data.performance.sortino_ratio,
                    max_drawdown: data.performance.max_drawdown_pct,
                    total_trades: data.performance.total_trades,
                    profit_factor: data.performance.profit_factor,
                    avg_win: data.performance.avg_win,
                    avg_loss: data.performance.avg_loss,
                    best_trade: data.trade_analytics.best_trade,
                    worst_trade: data.trade_analytics.worst_trade,
                  })}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors"
                >
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Export Performance CSV
                </button>
              </div>
              <ErrorBoundary section="Strategy Breakdown">
                <StrategyBreakdown strategies={data.strategy_breakdown} />
              </ErrorBoundary>
              <ErrorBoundary section="Trade Analytics">
                <TradeAnalytics analytics={data.trade_analytics} performance={data.performance} />
              </ErrorBoundary>
              <BacktestComparison
                live={{
                  sharpe: data.performance.sharpe_ratio,
                  win_rate: data.performance.win_rate,
                  max_drawdown: data.performance.max_drawdown_pct,
                  avg_return: data.performance.total_trades > 0
                    ? data.performance.total_pnl_30d / data.performance.total_trades
                    : 0,
                  total_trades: data.performance.total_trades,
                }}
                backtest={{ ...backtestBenchmarkMetrics }}
                benchmarkCaption={backtestBenchmarkCaption}
              />
            </div>
          )}

          {/* Analytics (deep trade stats — same data as former /analytics page) */}
          {activeTab === 'analytics' && (
            <div role="tabpanel" id="tabpanel-analytics" aria-labelledby="tab-analytics">
              <ErrorBoundary section="Trade Analytics">
                <DashboardAnalyticsContent
                  data={analyticsData}
                  attribution={strategyAttribution}
                  loading={analyticsLoading}
                  error={analyticsError}
                />
              </ErrorBoundary>
            </div>
          )}

          {/* Positions */}
          {activeTab === 'positions' && (
            <div role="tabpanel" id="tabpanel-positions" aria-labelledby="tab-positions">
              <div className={`${cardBg} border rounded-xl p-6`}>
                <div className="flex items-center justify-between mb-6">
                  <Tooltip text="All open positions from IBKR. Real-time marks and unrealized P&L." placement="above">
                    <h2 className={`text-xs font-semibold uppercase tracking-wider ${textMuted}`}>
                      Current Positions ({data.positions.count})
                    </h2>
                  </Tooltip>
                  {data.positions.count > 0 && (
                    <button
                      type="button"
                      onClick={() => exportPositionsCsv(data.positions.list)}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 transition-colors"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                      </svg>
                      Export CSV
                    </button>
                  )}
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className={`border-b ${border}`}>
                      <tr>
                        {(
                          [
                            ['Symbol',   'symbol',        'left',  'Ticker symbol'],
                            ['Side',     'side',          'left',  'Long or short position'],
                            ['Qty',      'quantity',      'right', 'Number of shares or contracts'],
                            ['Avg Cost', 'avg_cost',      'right', 'Average cost per share (entry)'],
                            ['Market',   'market_price',  'right', 'Current market price'],
                            ['Notional', 'notional',      'right', 'Position size: |qty × market price|'],
                            ['P&L',      'unrealized_pnl','right', 'Unrealized profit or loss'],
                            ['Return',   'return_pct',    'right', 'Percent return from avg cost to market'],
                            ['Stop',     'stop_price',    'right', 'ATR-based stop from pending_trades.json. Longs: exit if price falls below. Shorts: cover if price rises above.'],
                            ['Sector',   'sector',        'left',  'Sector or industry classification'],
                          ] as [string, SortKey, string, string][]
                        ).map(([col, key, align, tip]) => {
                          const active = sortKey === key;
                          const arrow = active ? (sortDir === 'asc' ? ' ↑' : ' ↓') : '';
                          return (
                            <th
                              key={key}
                              className={`text-${align} py-3 px-2 font-semibold ${textMuted} select-none`}
                            >
                              <Tooltip text={tip} placement="below">
                                <button
                                  type="button"
                                  onClick={() => handleSort(key)}
                                  className={`inline-flex items-center gap-0.5 hover:text-slate-700 transition-colors focus:outline-none focus:ring-2 focus:ring-primary-600 rounded ${active ? 'text-primary-600' : ''}`}
                                  aria-label={`Sort by ${col}${active ? (sortDir === 'asc' ? ', ascending' : ', descending') : ''}`}
                                >
                                  {col}
                                  <span className="text-xs opacity-70 w-3 inline-block">{arrow}</span>
                                </button>
                              </Tooltip>
                            </th>
                          );
                        })}
                      </tr>
                    </thead>
                    <tbody>
                      {sortedPositions(data.positions.list).map((pos) => (
                        <tr key={`${pos.symbol}-${pos.side}-${pos.quantity}-${pos.avg_cost ?? pos.market_price ?? ''}`} className="border-b border-slate-100 hover:bg-primary-50/40 transition-colors">
                          <td className="py-3 px-2 font-bold text-slate-900">{pos.symbol}</td>
                          <td className="py-3 px-2">
                            <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                              pos.side === 'LONG' ? 'bg-success-100 text-success-700' : 'bg-danger-100 text-danger-700'
                            }`}>
                              {pos.side}
                            </span>
                          </td>
                          <td className="py-3 px-2 text-right text-slate-500">{pos.quantity}</td>
                          <td className="py-3 px-2 text-right font-mono text-slate-900">
                            {pos.avg_cost != null ? `$${Number(pos.avg_cost).toFixed(2)}` : '—'}
                          </td>
                          <td className="py-3 px-2 text-right font-mono text-slate-900">
                            {pos.market_price != null ? `$${Number(pos.market_price).toFixed(2)}` : '—'}
                          </td>
                          <td className="py-3 px-2 text-right text-slate-500">{formatCurrency(pos.notional)}</td>
                          <td className={`py-3 px-2 text-right font-bold ${(pos.unrealized_pnl ?? 0) >= 0 ? 'text-success-600' : 'text-danger-600'}`}>
                            {pos.unrealized_pnl != null
                              ? `${pos.unrealized_pnl >= 0 ? '+' : ''}${formatCurrency(pos.unrealized_pnl)}`
                              : '—'}
                          </td>
                          <td className={`py-3 px-2 text-right font-bold ${(pos.return_pct ?? 0) >= 0 ? 'text-success-600' : 'text-danger-600'}`}>
                            {pos.return_pct != null
                              ? `${pos.return_pct >= 0 ? '+' : ''}${Number(pos.return_pct).toFixed(2)}%`
                              : '—'}
                          </td>
                          <td className="py-3 px-2 text-right">
                            {pos.stop_price != null ? (() => {
                              const isShortStop = pos.stop_side === 'SHORT';
                              const stopNum = Number(pos.stop_price);
                              const distPct = pos.avg_cost
                                ? (((stopNum - Number(pos.avg_cost)) / Number(pos.avg_cost)) * 100)
                                : null;
                              const distStr = distPct != null
                                ? ` (${distPct >= 0 ? '+' : ''}${distPct.toFixed(1)}% from cost)`
                                : '';
                              const tooltipText = isShortStop
                                ? `Short stop: cover if price ≥ $${stopNum.toFixed(2)}${distStr}`
                                : `Long stop: exit if price ≤ $${stopNum.toFixed(2)}${distStr}`;
                              // Colour: shorts show blue (cover above), longs show orange (exit below)
                              const colour = isShortStop ? 'text-blue-600' : 'text-orange-600';
                              const arrow  = isShortStop ? '▲' : '▼';
                              return (
                                <Tooltip text={tooltipText} placement="above">
                                  <span className={`font-mono text-sm ${colour} font-semibold cursor-help`}>
                                    <span className="text-xs mr-0.5 opacity-60">{arrow}</span>
                                    ${stopNum.toFixed(2)}
                                  </span>
                                </Tooltip>
                              );
                            })() : (
                              <span className="text-slate-300 text-xs">—</span>
                            )}
                          </td>
                          <td className="py-3 px-2 text-xs text-slate-400">{pos.sector}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {data.positions.count === 0 && (
                  <div className={`text-center py-8 ${textFaint}`}>No open positions</div>
                )}
              </div>
            </div>
          )}

        </main>

        {/* ── System monitor (collapsible at bottom) ── */}
        <div className="mt-8">
          <ErrorBoundary section="System Monitor" compact>
            <SystemMonitor systemHealth={data.system_health} dashboardUp={true} />
          </ErrorBoundary>
        </div>

        {/* Onboarding tour — shown on first visit, floating help button thereafter */}
      <OnboardingTour onTabChange={(tab) => setActiveTab(tab as Tab)} />

      {/* Notification preferences modal */}
      {showNotifPrefs && <NotificationPrefsPanel onClose={() => setShowNotifPrefs(false)} />}

      <footer className="mt-8 pt-6 border-t border-slate-200 text-center text-xs text-slate-400" role="contentinfo">
          <p>Winzinvest</p>
          <p className="mt-1">
            {isLive ? 'Live account' : 'Paper trading'} · Data from IBKR · Metrics reflect {isLive ? 'live' : 'paper'}{' '}
            positions
          </p>
          <p className="mt-2 max-w-xl mx-auto">
            Past performance does not guarantee future results. Trading involves risk of loss.
          </p>
        </footer>
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  color,
  subtitle,
  title,
}: {
  label: string;
  value: string;
  color: string;
  subtitle?: string;
  title?: string;
}) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5">
      {title ? (
        <Tooltip text={title} placement="above">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">{label}</div>
        </Tooltip>
      ) : (
        <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">{label}</div>
      )}
      <div className={`font-serif text-3xl font-bold ${color} mb-1`}>{value}</div>
      {subtitle && <div className="text-xs text-slate-400">{subtitle}</div>}
    </div>
  );
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}
