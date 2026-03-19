'use client';

import { use, useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import AlertBanner from '../components/AlertBanner';
import EquityCurve from '../components/EquityCurve';
import ModeToggle from '../components/ModeToggle';
import KillSwitchButton from '../components/KillSwitchButton';
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

type Tab = 'overview' | 'intelligence' | 'risk' | 'performance' | 'positions';

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
    regime: string;
    note: string;
    catalysts: string[];
    updated_at: string;
  };
  system_health: {
    status: string;
    issues: string[];
    data_freshness_minutes: number;
  };
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
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string>('');
  const [equityCurveData, setEquityCurveData] = useState<EquityPoint[]>([]);
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [showNotifPrefs, setShowNotifPrefs] = useState(false);

  type SortKey = 'symbol' | 'side' | 'quantity' | 'avg_cost' | 'market_price' | 'notional' | 'unrealized_pnl' | 'return_pct' | 'sector';
  type SortDir = 'asc' | 'desc';
  const [sortKey, setSortKey] = useState<SortKey>('notional');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir(key === 'symbol' || key === 'side' || key === 'sector' ? 'asc' : 'desc');
    }
  }

  function sortedPositions(list: PositionRow[]): PositionRow[] {
    return [...list].sort((a, b) => {
      const av = a[sortKey] ?? (typeof a[sortKey] === 'number' ? -Infinity : '');
      const bv = b[sortKey] ?? (typeof b[sortKey] === 'number' ? -Infinity : '');
      let cmp = 0;
      if (typeof av === 'string' && typeof bv === 'string') {
        cmp = av.localeCompare(bv);
      } else {
        cmp = (av as number) < (bv as number) ? -1 : (av as number) > (bv as number) ? 1 : 0;
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }
  const { viewMode } = useTradingMode();

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
      if (res.ok) {
        const json = await res.json() as { points?: EquityPoint[] };
        if (Array.isArray(json.points) && json.points.length > 0) {
          setEquityCurveData(json.points);
        }
      }
    } catch {
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
          <div className="text-red-600 font-semibold mb-2">Error Loading Dashboard</div>
          <div className="text-stone-500 text-sm">{error}</div>
          <div className="text-stone-400 text-xs mt-4">
            Make sure dashboard_data_aggregator.py is running
          </div>
        </div>
      </div>
    );
  }

  const isDataStale = data.system_health.data_freshness_minutes > 5;
  const isLive = viewMode === 'live';

  // Theme is always light — isLive only controls data source & warning banners
  const bg = 'dashboard-bg-light';
  const border = 'border-slate-200';
  const cardBg = 'bg-white border-slate-200';
  const textPrimary = 'text-slate-900';
  const textMuted = 'text-slate-600';   // slate-600 on white = 7:1 contrast (AA+)
  const textFaint = 'text-slate-500';   // slate-500 on white = 4.6:1 (AA for normal text)

  return (
    <div className={`min-h-screen ${bg}`}>
      {/* Brand stripe — sky-600 gradient top accent */}
      <div className="brand-stripe" />

      {/* Live mode banner */}
      {isLive && (
        <div className="bg-red-600 text-white text-center text-xs font-semibold py-1.5 tracking-wide">
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

        {/* ── Header ── */}
        <header className={`mb-6 pb-5 border-b ${border}`}>
          <div className="flex justify-between items-center">
            <div>
              <h1 className="font-serif text-4xl font-bold tracking-tight text-slate-900">
                Winz<span className="text-sky-600">invest</span>
              </h1>
              <p className="mt-1 text-sm text-slate-500">Institutional Dashboard</p>
            </div>

            <div className="flex flex-col items-end gap-2">
              <div className="flex items-start gap-2">
                <button
                  onClick={() => setShowNotifPrefs(true)}
                  className="p-1.5 rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50 transition-colors focus:outline-none focus:ring-2 focus:ring-sky-500 mt-0.5"
                  aria-label="Notification preferences"
                  title="Notification preferences"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                  </svg>
                </button>
                <div className="mt-0.5">
                  <KillSwitchButton />
                </div>
                <ModeToggle />
              </div>
              <div className="text-right" role="status" aria-live="polite">
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
            </div>
          </div>

          {/* Other views nav */}
          <nav className="flex items-center gap-2 mt-5" aria-label="Primary">
            {[
              { href: '/simple',   label: 'Simple View' },
              { href: '/methodology', label: 'Methodology' },
              { href: '/strategy', label: 'Strategy' },
              { href: '/journal',  label: 'Journal' },
            ].map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className="px-3 py-1.5 text-sm font-medium rounded-lg border border-slate-200 text-slate-600 hover:bg-white hover:border-slate-300 hover:shadow-sm transition-all"
              >
                {label}
              </Link>
            ))}
          </nav>
        </header>

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
                key={tab.id}
                role="tab"
                aria-selected={isActive}
                aria-controls={`tabpanel-${tab.id}`}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 py-2 px-3 text-sm font-medium rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-1 focus:ring-offset-slate-900 ${
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
                  color="text-sky-600"
                  subtitle={`Leverage: ${data.account.leverage_ratio.toFixed(2)}x`}
                  title="Total account value (cash + positions). From IBKR."
                />
                <MetricCard
                  label="Daily P&L"
                  value={formatCurrency(data.performance.daily_pnl)}
                  color={data.performance.daily_pnl >= 0 ? 'text-green-600' : 'text-red-600'}
                  subtitle={`${data.performance.daily_return_pct >= 0 ? '+' : ''}${data.performance.daily_return_pct.toFixed(2)}%`}
                  title="Realized + unrealized P&L for current session."
                />
                <MetricCard
                  label="30d P&L"
                  value={formatCurrency(data.performance.total_pnl_30d)}
                  color={data.performance.total_pnl_30d >= 0 ? 'text-green-600' : 'text-red-600'}
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
                const label = regime?.regime ?? 'UNKNOWN';
                const note = regime?.note ?? '';
                const catalysts = regime?.catalysts ?? [];
                const updatedAt = regime?.updated_at ? new Date(regime.updated_at).toLocaleString() : '';

                // Normalize to handle spaces, dashes, and case variants (e.g. "RISK ON" → "RISK_ON")
                const normalizeKey = (k: string) => k.toUpperCase().replace(/[\s-]+/g, '_');
                const nKey = normalizeKey(label);

                const colorMap: Record<string, string> = {
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
                  VOLATILE:      'bg-purple-50 border-purple-300 text-purple-800',
                };
                const dotMap: Record<string, string> = {
                  BULL: 'bg-emerald-500', BULL_QUIET: 'bg-emerald-500', BULL_MOMENTUM: 'bg-emerald-500', RISK_ON: 'bg-emerald-500',
                  NEUTRAL: 'bg-amber-500', RANGE_BOUND: 'bg-amber-500',
                  BEAR: 'bg-red-500', BEAR_VOLATILE: 'bg-red-500', RISK_OFF: 'bg-red-500',
                  DEFENSIVE: 'bg-orange-500',
                  VOLATILE: 'bg-purple-500',
                };
                const pingMap: Record<string, string> = {
                  BULL: 'bg-emerald-400', BULL_QUIET: 'bg-emerald-400', BULL_MOMENTUM: 'bg-emerald-400', RISK_ON: 'bg-emerald-400',
                  NEUTRAL: 'bg-amber-400', RANGE_BOUND: 'bg-amber-400',
                  BEAR: 'bg-red-400', BEAR_VOLATILE: 'bg-red-400', RISK_OFF: 'bg-red-400',
                  DEFENSIVE: 'bg-orange-400',
                  VOLATILE: 'bg-purple-400',
                };
                const colors = colorMap[nKey] ?? 'bg-slate-50 border-slate-300 text-slate-700';
                const dot    = dotMap[nKey]   ?? 'bg-slate-400';
                const ping   = pingMap[nKey]  ?? 'bg-slate-300';
                const displayLabel = label.replace(/_/g, ' ');

                return (
                  <div className={`regime-banner mb-6 flex items-center gap-3 border rounded-xl px-5 py-3 ${colors}`}>
                    {/* Pulsing live indicator */}
                    <span className="relative flex h-2.5 w-2.5 shrink-0">
                      <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${ping} opacity-60`} />
                      <span className={`relative inline-flex h-2.5 w-2.5 rounded-full ${dot}`} />
                    </span>

                    {/* Label + regime name */}
                    <div className="flex items-baseline gap-2 shrink-0">
                      <span className="text-[10px] font-semibold uppercase tracking-[0.14em] opacity-50">Market Regime</span>
                      <span className="text-sm font-bold tracking-wide uppercase">{displayLabel}</span>
                    </div>

                    {/* Divider — only when there is supplemental content */}
                    {(note || catalysts.length > 0) && (
                      <span className="h-3.5 w-px bg-current opacity-20 shrink-0 mx-1" />
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
                  <div className="font-mono text-2xl font-semibold text-green-600">
                    {formatCurrency(data.positions.long_notional)}
                  </div>
                  <div className={`text-xs mt-1 ${textFaint}`}>
                    {((data.positions.long_notional / data.account.net_liquidation) * 100).toFixed(1)}% of NLV
                  </div>
                </div>

                <div className={`${cardBg} border rounded-xl p-5`}>
                  <Tooltip text="Total market value of all short positions (notional)." placement="above">
                    <h3 className={`text-xs font-semibold uppercase tracking-wider ${textMuted} mb-3`}>Short Exposure</h3>
                  </Tooltip>
                  <div className="font-mono text-2xl font-semibold text-red-600">
                    {formatCurrency(data.positions.short_notional)}
                  </div>
                  <div className={`text-xs mt-1 ${textFaint}`}>
                    {((data.positions.short_notional / data.account.net_liquidation) * 100).toFixed(1)}% of NLV
                  </div>
                </div>

                <div className={`${cardBg} border rounded-xl p-5`}>
                  <h3
                    className={`text-xs font-semibold uppercase tracking-wider ${textMuted} mb-3 cursor-help`}
                    title="Long minus short exposure. Positive = net long."
                  >
                    Net Exposure
                  </h3>
                  <div className={`font-mono text-2xl font-semibold ${data.positions.net_exposure >= 0 ? 'text-green-600' : 'text-red-600'}`}>
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
                backtest={{
                  sharpe: 4.03,
                  win_rate: 47.1,
                  max_drawdown: 12.6,
                  avg_return: 1450,
                  total_trades: 588,
                }}
              />
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
                                  className={`inline-flex items-center gap-0.5 hover:text-slate-700 transition-colors focus:outline-none focus:ring-2 focus:ring-sky-400 rounded ${active ? 'text-sky-600' : ''}`}
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
                      {sortedPositions(data.positions.list).map((pos, idx) => (
                        <tr key={idx} className="border-b border-slate-100 hover:bg-sky-50/40 transition-colors">
                          <td className="py-3 px-2 font-bold text-slate-900">{pos.symbol}</td>
                          <td className="py-3 px-2">
                            <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                              pos.side === 'LONG' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
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
                          <td className={`py-3 px-2 text-right font-bold ${(pos.unrealized_pnl ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {pos.unrealized_pnl != null
                              ? `${pos.unrealized_pnl >= 0 ? '+' : ''}${formatCurrency(pos.unrealized_pnl)}`
                              : '—'}
                          </td>
                          <td className={`py-3 px-2 text-right font-bold ${(pos.return_pct ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {pos.return_pct != null
                              ? `${pos.return_pct >= 0 ? '+' : ''}${Number(pos.return_pct).toFixed(2)}%`
                              : '—'}
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
          <p>Winzinvest {isLive ? '• Live Account' : '• Paper Trading'}</p>
          <p className="mt-1">Real-time data from IBKR • All metrics calculated from {isLive ? 'live' : 'paper'} positions</p>
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
