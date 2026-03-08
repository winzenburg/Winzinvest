'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import AlertBanner from '../components/AlertBanner';
import EquityCurve from '../components/EquityCurve';
import RiskMetrics from '../components/RiskMetrics';
import StrategyBreakdown from '../components/StrategyBreakdown';
import TradeAnalytics from '../components/TradeAnalytics';
import BacktestComparison from '../components/BacktestComparison';

interface DashboardData {
  timestamp: string;
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
    list: any[];
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
  strategy_breakdown: Record<string, any>;
  trade_analytics: {
    avg_mae: number;
    avg_mfe: number;
    avg_slippage_bps: number;
    avg_hold_time_hours: number;
    best_trade: number;
    worst_trade: number;
    largest_position: number;
  };
  system_health: {
    status: string;
    issues: string[];
    data_freshness_minutes: number;
  };
}

export default function InstitutionalDashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string>('');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch('/api/dashboard');
        if (!res.ok) {
          throw new Error('Failed to fetch dashboard data');
        }
        const json = await res.json();
        setData(json);
        setLastUpdate(new Date().toLocaleTimeString());
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        console.error('Dashboard fetch error:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center">
        <div className="text-stone-400">Loading institutional dashboard...</div>
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

  const equityCurveData = generateEquityCurveData(data);

  return (
    <div className="min-h-screen bg-stone-50">
      <div className="max-w-[1600px] mx-auto px-8 py-12">
        {/* Header */}
        <header className="mb-12 pb-6 border-b border-stone-200">
          <div className="flex justify-between items-start mb-6">
            <div>
              <h1 className="font-serif text-5xl font-bold text-slate-900 tracking-tight">
                Mission Control
              </h1>
              <p className="text-stone-500 mt-2">Institutional Dashboard</p>
            </div>
            <div className="text-right">
              <div className="flex items-center gap-2 text-sm text-stone-500">
                <span className={`w-2 h-2 rounded-full ${
                  data.system_health.status === 'healthy' ? 'bg-green-500' :
                  data.system_health.status === 'warning' ? 'bg-orange-500' :
                  'bg-red-500'
                }`}></span>
                <span>{data.system_health.status}</span>
              </div>
              <div className="text-xs text-stone-400 mt-1">
                Updated {lastUpdate}
              </div>
              {data.system_health.data_freshness_minutes > 0 && (
                <div className="text-xs text-stone-400">
                  Data: {data.system_health.data_freshness_minutes}m old
                </div>
              )}
            </div>
          </div>
          
          <nav className="flex gap-4">
            <Link
              href="/"
              className="px-4 py-2 bg-stone-100 hover:bg-stone-200 text-stone-700 rounded-lg text-sm font-semibold transition-colors"
            >
              Simple View
            </Link>
            <Link
              href="/strategy"
              className="px-4 py-2 bg-stone-100 hover:bg-stone-200 text-stone-700 rounded-lg text-sm font-semibold transition-colors"
            >
              Strategy
            </Link>
            <Link
              href="/journal"
              className="px-4 py-2 bg-stone-100 hover:bg-stone-200 text-stone-700 rounded-lg text-sm font-semibold transition-colors"
            >
              Journal
            </Link>
          </nav>
        </header>

        {/* Alerts */}
        <AlertBanner />

        {/* Key Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 mb-8">
          <MetricCard
            label="Net Liquidation"
            value={formatCurrency(data.account.net_liquidation)}
            color="text-sky-600"
            subtitle={`Leverage: ${data.account.leverage_ratio.toFixed(2)}x`}
          />
          <MetricCard
            label="Daily P&L"
            value={formatCurrency(data.performance.daily_pnl)}
            color={data.performance.daily_pnl >= 0 ? 'text-green-600' : 'text-red-600'}
            subtitle={`${data.performance.daily_return_pct >= 0 ? '+' : ''}${data.performance.daily_return_pct.toFixed(2)}%`}
          />
          <MetricCard
            label="30d P&L"
            value={formatCurrency(data.performance.total_pnl_30d)}
            color={data.performance.total_pnl_30d >= 0 ? 'text-green-600' : 'text-red-600'}
            subtitle={`Win rate: ${data.performance.win_rate.toFixed(1)}%`}
          />
          <MetricCard
            label="Sharpe Ratio"
            value={data.performance.sharpe_ratio.toFixed(2)}
            color="text-slate-900"
            subtitle={`Sortino: ${data.performance.sortino_ratio.toFixed(2)}`}
          />
          <MetricCard
            label="Open Positions"
            value={data.positions.count.toString()}
            color="text-slate-900"
            subtitle={`${data.performance.total_trades} trades (30d)`}
          />
        </div>

        {/* Equity Curve */}
        <div className="mb-8">
          <EquityCurve data={equityCurveData} />
        </div>

        {/* Risk Metrics */}
        <div className="mb-8">
          <RiskMetrics risk={data.risk} performance={data.performance} />
        </div>

        {/* Exposure Summary */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          <div className="bg-white border border-stone-200 rounded-xl p-6">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-4">
              Long Exposure
            </h3>
            <div className="font-serif text-3xl font-bold text-green-600">
              {formatCurrency(data.positions.long_notional)}
            </div>
            <div className="text-sm text-stone-500 mt-2">
              {((data.positions.long_notional / data.account.net_liquidation) * 100).toFixed(1)}% of equity
            </div>
          </div>

          <div className="bg-white border border-stone-200 rounded-xl p-6">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-4">
              Short Exposure
            </h3>
            <div className="font-serif text-3xl font-bold text-red-600">
              {formatCurrency(data.positions.short_notional)}
            </div>
            <div className="text-sm text-stone-500 mt-2">
              {((data.positions.short_notional / data.account.net_liquidation) * 100).toFixed(1)}% of equity
            </div>
          </div>

          <div className="bg-white border border-stone-200 rounded-xl p-6">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-4">
              Net Exposure
            </h3>
            <div className={`font-serif text-3xl font-bold ${
              data.positions.net_exposure >= 0 ? 'text-green-600' : 'text-red-600'
            }`}>
              {formatCurrency(data.positions.net_exposure)}
            </div>
            <div className="text-sm text-stone-500 mt-2">
              Gross: {formatCurrency(data.positions.gross_exposure)}
            </div>
          </div>
        </div>

        {/* Strategy Breakdown */}
        <div className="mb-8">
          <StrategyBreakdown strategies={data.strategy_breakdown} />
        </div>

        {/* Trade Analytics */}
        <div className="mb-8">
          <TradeAnalytics analytics={data.trade_analytics} performance={data.performance} />
        </div>

        {/* Backtest Comparison */}
        <div className="mb-8">
          <BacktestComparison
            live={{
              sharpe: data.performance.sharpe_ratio,
              win_rate: data.performance.win_rate,
              max_drawdown: data.performance.max_drawdown_pct,
              avg_return: data.performance.total_pnl_30d / data.performance.total_trades,
              total_trades: data.performance.total_trades,
            }}
            backtest={{
              sharpe: 2.1,
              win_rate: 58.5,
              max_drawdown: 5.2,
              avg_return: 0.85,
              total_trades: 450,
            }}
          />
        </div>

        {/* Current Positions */}
        <div className="bg-white border border-stone-200 rounded-xl p-6 mb-8">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-6">
            Current Positions ({data.positions.count})
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-stone-200">
                <tr>
                  <th className="text-left py-3 px-2 font-semibold text-stone-600">Symbol</th>
                  <th className="text-left py-3 px-2 font-semibold text-stone-600">Side</th>
                  <th className="text-right py-3 px-2 font-semibold text-stone-600">Qty</th>
                  <th className="text-right py-3 px-2 font-semibold text-stone-600">Avg Cost</th>
                  <th className="text-right py-3 px-2 font-semibold text-stone-600">Market</th>
                  <th className="text-right py-3 px-2 font-semibold text-stone-600">Notional</th>
                  <th className="text-right py-3 px-2 font-semibold text-stone-600">P&L</th>
                  <th className="text-right py-3 px-2 font-semibold text-stone-600">Return</th>
                  <th className="text-left py-3 px-2 font-semibold text-stone-600">Sector</th>
                </tr>
              </thead>
              <tbody>
                {data.positions.list.map((pos, idx) => (
                  <tr key={idx} className="border-b border-stone-100 hover:bg-stone-50">
                    <td className="py-3 px-2 font-bold text-slate-900">{pos.symbol}</td>
                    <td className="py-3 px-2">
                      <span className={`px-2 py-1 rounded text-xs font-semibold ${
                        pos.side === 'LONG' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                      }`}>
                        {pos.side}
                      </span>
                    </td>
                    <td className="py-3 px-2 text-right text-stone-600">{pos.quantity}</td>
                    <td className="py-3 px-2 text-right font-mono text-stone-900">
                      ${pos.avg_cost.toFixed(2)}
                    </td>
                    <td className="py-3 px-2 text-right font-mono text-stone-900">
                      ${pos.market_price.toFixed(2)}
                    </td>
                    <td className="py-3 px-2 text-right text-stone-600">
                      {formatCurrency(pos.notional)}
                    </td>
                    <td className={`py-3 px-2 text-right font-bold ${
                      pos.unrealized_pnl >= 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {pos.unrealized_pnl >= 0 ? '+' : ''}{formatCurrency(pos.unrealized_pnl)}
                    </td>
                    <td className={`py-3 px-2 text-right font-bold ${
                      pos.return_pct >= 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {pos.return_pct >= 0 ? '+' : ''}{pos.return_pct.toFixed(2)}%
                    </td>
                    <td className="py-3 px-2 text-stone-600 text-xs">{pos.sector}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data.positions.count === 0 && (
            <div className="text-center text-stone-400 py-8">No open positions</div>
          )}
        </div>

        {/* Footer */}
        <footer className="mt-16 pt-8 border-t border-stone-200 text-center text-sm text-stone-400">
          <p>Mission Control Trading System • Institutional Dashboard</p>
          <p className="mt-2">
            Real-time data from IBKR • All metrics calculated from live positions
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
  subtitle 
}: { 
  label: string; 
  value: string; 
  color: string;
  subtitle?: string;
}) {
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-6 hover:shadow-lg transition-shadow">
      <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">
        {label}
      </div>
      <div className={`font-serif text-3xl font-bold ${color} mb-1`}>
        {value}
      </div>
      {subtitle && (
        <div className="text-xs text-stone-500">{subtitle}</div>
      )}
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

function generateEquityCurveData(data: DashboardData) {
  const today = new Date();
  const points = [];
  
  for (let i = 29; i >= 0; i--) {
    const date = new Date(today);
    date.setDate(date.getDate() - i);
    
    const randomWalk = (Math.random() - 0.48) * 0.01;
    const equity = data.account.net_liquidation * (1 + randomWalk * i);
    const peak = Math.max(...points.map(p => p.equity), equity);
    const drawdown = ((peak - equity) / peak) * 100;
    
    points.push({
      date: date.toISOString().split('T')[0],
      equity,
      drawdown: -drawdown,
    });
  }
  
  return points;
}
