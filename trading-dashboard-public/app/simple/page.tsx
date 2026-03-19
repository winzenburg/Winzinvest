'use client';

import { use, useEffect, useState } from 'react';
import Link from 'next/link';
import { fetchWithAuth } from '@/lib/fetch-client';
import ModeToggle from '../components/ModeToggle';

interface PerformanceData {
  accountValue: number;
  dailyPnL: number;
  totalPnL: number;
  winRate: number;
  sharpeRatio: number;
  maxDrawdown: number;
  totalTrades: number;
  openPositions: number;
}

interface AllocationData {
  longPct: number;
  shortPct: number;
  optionsPct: number;
  cashPct: number;
}

interface RecentTrade {
  date: string;
  symbol: string;
  type: string;
  entry: number;
  exit: number;
  pnl: number;
  pnl_pct: number;
}

interface Candidate {
  symbol: string;
  score: number;
  rs: number;
  vol: number;
  reason?: string;
}

type PageProps = {
  params?: Promise<Record<string, string | string[]>>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

const EMPTY = Promise.resolve({});

export default function SimpleDashboard(props: PageProps) {
  use(props.params ?? EMPTY);
  use(props.searchParams ?? EMPTY);
  const [data, setData] = useState<PerformanceData | null>(null);
  const [allocation, setAllocation] = useState<AllocationData>({ longPct: 0, shortPct: 0, optionsPct: 0, cashPct: 0 });
  const [recentTrades, setRecentTrades] = useState<RecentTrade[]>([]);
  const [lastUpdate, setLastUpdate] = useState<string>('');
  const [showFullList, setShowFullList] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<{
    longs: Candidate[];
    shorts: Candidate[];
  }>({
    longs: [],
    shorts: [],
  });

  useEffect(() => {
    const parseSnapshot = (json: Record<string, unknown>) => {
      setData({
        accountValue: (json?.account as Record<string, number>)?.net_liquidation ?? 0,
        dailyPnL: (json?.performance as Record<string, number>)?.daily_pnl ?? 0,
        totalPnL: (json?.performance as Record<string, number>)?.total_pnl_30d ?? 0,
        winRate: (json?.performance as Record<string, number>)?.win_rate ?? 0,
        sharpeRatio: (json?.performance as Record<string, number>)?.sharpe_ratio ?? 0,
        maxDrawdown: (json?.performance as Record<string, number>)?.max_drawdown_pct ?? 0,
        totalTrades: (json?.performance as Record<string, number>)?.total_trades ?? 0,
        openPositions: (json?.positions as Record<string, number>)?.count ?? 0,
      });

      // Compute live allocation from positions + account
      const nlv = (json?.account as Record<string, number>)?.net_liquidation ?? 1;
      const totalCash = (json?.account as Record<string, number>)?.total_cash ?? 0;
      const longNotional = (json?.positions as Record<string, number>)?.long_notional ?? 0;
      const shortNotional = Math.abs((json?.positions as Record<string, number>)?.short_notional ?? 0);
      const allPositions = ((json?.positions as Record<string, unknown>)?.list ?? []) as Array<Record<string, unknown>>;
      const optionsNotional = allPositions
        .filter((p) => p.type === 'OPT' || p.sector === 'Options')
        .reduce((acc, p) => acc + Math.abs(Number(p.notional ?? 0)), 0);
      const equityLong = longNotional - optionsNotional;
      const safeNlv = nlv > 0 ? nlv : 1;
      setAllocation({
        longPct: Math.round((equityLong / safeNlv) * 100),
        shortPct: Math.round((shortNotional / safeNlv) * 100),
        optionsPct: Math.round((optionsNotional / safeNlv) * 100),
        cashPct: Math.round((totalCash / safeNlv) * 100),
      });

      // Recent trades from snapshot
      const trades = (json?.recent_trades ?? []) as RecentTrade[];
      setRecentTrades(trades);

      setLastUpdate(new Date().toLocaleTimeString());
    };

    const loadDashboard = async () => {
      try {
        const r = await fetchWithAuth('/api/dashboard');
        if (r.ok) {
          const json = (await r.json()) as Record<string, unknown>;
          parseSnapshot(json);
        }
      } catch {
        setData({
          accountValue: 0,
          dailyPnL: 0,
          totalPnL: 0,
          winRate: 0,
          sharpeRatio: 0,
          maxDrawdown: 0,
          totalTrades: 0,
          openPositions: 0,
        });
      }
    };

    const loadScreeners = async () => {
      try {
        const r = await fetchWithAuth('/api/screeners');
        if (!r.ok) return;
        const s = (await r.json()) as { longs?: unknown[]; shorts?: unknown[] };
        const isRec = (c: unknown): c is Record<string, unknown> =>
          typeof c === 'object' && c !== null;
        const longs = (s?.longs ?? [])
          .filter(isRec)
          .slice(0, 10)
          .map((c) => ({
            symbol: c.symbol as string,
            score: Number(c.hybrid_score ?? c.score ?? 0),
            rs: Number(c.rs_pct_252d ?? c.rs ?? 0),
            vol: Number(c.rvol ?? c.vol ?? 0),
            reason: c.reason as string | undefined,
          }));
        const shorts = (s?.shorts ?? [])
          .filter(isRec)
          .slice(0, 5)
          .map((c) => ({
            symbol: c.symbol as string,
            score: Number(c.hybrid_score ?? c.score ?? 0),
            rs: Number(c.rs_pct_252d ?? c.rs ?? 0),
            vol: Number(c.rvol ?? c.vol ?? 0),
            reason: c.reason as string | undefined,
          }));
        setCandidates({ longs, shorts });
      } catch {
        /* non-fatal */
      }
    };

    void loadDashboard();
    void loadScreeners();

    const interval = setInterval(() => {
      void loadDashboard();
      void loadScreeners();
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  if (!data) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center">
        <div className="text-stone-400">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-stone-50">
      <div className="max-w-7xl mx-auto px-8 py-12">
        {/* Header */}
        <header className="mb-16 pb-8 border-b border-stone-200">
          <div className="flex justify-between items-start mb-6">
            <h1 className="font-serif text-5xl font-bold text-slate-900 tracking-tight">
              Winzinvest
            </h1>
            <div className="flex flex-col items-end gap-3">
              <ModeToggle />
              <div className="text-xs text-stone-400">
                Updated {lastUpdate}
              </div>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex gap-4" aria-label="Primary">
            <Link
              href="/institutional"
              className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-sm font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2"
            >
              Dashboard (Institutional)
            </Link>
            <Link
              href="/strategy"
              className="px-4 py-2 bg-stone-100 hover:bg-stone-200 text-stone-600 rounded-lg text-sm font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2"
            >
              Trading Strategy
            </Link>
            <Link
              href="/journal"
              className="px-4 py-2 bg-stone-100 hover:bg-stone-200 text-stone-600 rounded-lg text-sm font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2"
            >
              Trading Journal
            </Link>
            <Link
              href="/audit"
              className="px-4 py-2 bg-stone-100 hover:bg-stone-200 text-stone-600 rounded-lg text-sm font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2"
            >
              Audit Trail
            </Link>
          </nav>
        </header>

        {/* Key Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
          <MetricCard
            label="Account Value"
            value={formatCurrency(data.accountValue)}
            color="text-sky-600"
          />
          <MetricCard
            label="Daily P&L"
            value={formatCurrency(data.dailyPnL)}
            color={data.dailyPnL >= 0 ? 'text-green-600' : 'text-red-600'}
          />
          <MetricCard
            label="Total P&L (30d)"
            value={formatCurrency(data.totalPnL)}
            color={data.totalPnL >= 0 ? 'text-green-600' : 'text-red-600'}
          />
          <MetricCard
            label="Win Rate"
            value={`${data.winRate.toFixed(1)}%`}
            color="text-green-600"
          />
        </div>

        {/* Performance Stats */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-12">
          <div className="bg-white border border-stone-200 rounded-xl p-8">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-6">
              Performance (30 Days)
            </h2>
            <div className="grid grid-cols-2 gap-6">
              <StatItem label="Sharpe Ratio" value={data.sharpeRatio.toFixed(2)} />
              <StatItem label="Max Drawdown" value={`${data.maxDrawdown.toFixed(1)}%`} />
              <StatItem label="Total Trades" value={data.totalTrades.toString()} />
              <StatItem label="Open Positions" value={data.openPositions.toString()} />
            </div>
          </div>

          <div className="bg-white border border-stone-200 rounded-xl p-8">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-6">
              Strategy Allocation
            </h2>
            <div className="space-y-4">
              <AllocationBar label="Long Equity" percentage={allocation.longPct} color="bg-green-500" />
              <AllocationBar label="Short Equity" percentage={allocation.shortPct} color="bg-red-500" />
              <AllocationBar label="Options Premium" percentage={allocation.optionsPct} color="bg-orange-500" />
              <AllocationBar label="Cash" percentage={allocation.cashPct} color="bg-stone-300" />
            </div>
          </div>
        </div>

        {/* Screener Candidates */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-12">
          <div
            className="bg-white border border-stone-200 rounded-xl p-8 cursor-pointer hover:shadow-lg hover:border-stone-300 transition-all"
            onClick={() => setShowFullList('longs')}
            onKeyDown={(e) => e.key === 'Enter' && setShowFullList('longs')}
            role="button"
            tabIndex={0}
          >
            <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-4">
              Long Candidates
            </h2>
            <div className="font-serif text-4xl font-bold text-green-600 mb-2">
              {candidates.longs.length}
            </div>
            <div className="text-sm text-stone-500">Click to view all →</div>
          </div>

          <div
            className="bg-white border border-stone-200 rounded-xl p-8 cursor-pointer hover:shadow-lg hover:border-stone-300 transition-all"
            onClick={() => setShowFullList('shorts')}
            onKeyDown={(e) => e.key === 'Enter' && setShowFullList('shorts')}
            role="button"
            tabIndex={0}
          >
            <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-4">
              Short Candidates
            </h2>
            <div className="font-serif text-4xl font-bold text-red-600 mb-2">
              {candidates.shorts.length}
            </div>
            <div className="text-sm text-stone-500">Click to view all →</div>
          </div>
        </div>

        {/* Full List Modal */}
        {showFullList && (
          <div
            className="fixed inset-0 bg-slate-900/60 flex items-center justify-center p-4 z-50"
            onClick={() => setShowFullList(null)}
          >
            <div
              className="bg-white rounded-xl max-w-4xl w-full max-h-[80vh] overflow-hidden"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="p-8 border-b border-stone-200 flex justify-between items-center">
                <h2 className="text-xl font-serif font-bold text-slate-900">
                  {showFullList === 'longs' ? 'All Long Candidates' : 'All Short Candidates'}
                  ({showFullList === 'longs' ? candidates.longs.length : candidates.shorts.length})
                </h2>
                <button
                  onClick={() => setShowFullList(null)}
                  className="text-stone-400 hover:text-stone-600 text-2xl focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2 rounded"
                  aria-label="Close"
                >
                  ×
                </button>
              </div>
              <div className="overflow-y-auto max-h-[60vh] p-8">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-stone-50">
                    <tr className="border-b border-stone-200">
                      <th className="text-left py-3 px-2 font-semibold text-stone-600">Symbol</th>
                      <th className="text-right py-3 px-2 font-semibold text-stone-600">Score</th>
                      <th className="text-right py-3 px-2 font-semibold text-stone-600">RS</th>
                      <th className="text-right py-3 px-2 font-semibold text-stone-600">Vol</th>
                      <th className="text-left py-3 px-2 font-semibold text-stone-600">Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(showFullList === 'longs' ? candidates.longs : candidates.shorts).map((c, i) => (
                      <tr key={i} className="border-b border-stone-100 hover:bg-stone-50">
                        <td className="py-3 px-2 font-semibold text-slate-900">{c.symbol}</td>
                        <td className="py-3 px-2 text-right text-stone-600">{c.score.toFixed(2)}</td>
                        <td className="py-3 px-2 text-right text-stone-600">{c.rs.toFixed(2)}</td>
                        <td className="py-3 px-2 text-right text-stone-600">{c.vol.toFixed(2)}</td>
                        <td className="py-3 px-2 text-stone-600 text-sm">{c.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Recent Trades */}
        <div className="bg-white border border-stone-200 rounded-xl p-8 mb-12">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-6">
            Recent Closed Trades (Last 10)
          </h2>
          <div className="overflow-x-auto">
            {recentTrades.length === 0 ? (
              <p className="text-sm text-stone-400 italic">No closed trades on record yet.</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-stone-200">
                    <th className="text-left py-3 px-2 font-semibold text-stone-600">Date</th>
                    <th className="text-left py-3 px-2 font-semibold text-stone-600">Symbol</th>
                    <th className="text-left py-3 px-2 font-semibold text-stone-600">Type</th>
                    <th className="text-right py-3 px-2 font-semibold text-stone-600">Entry</th>
                    <th className="text-right py-3 px-2 font-semibold text-stone-600">Exit</th>
                    <th className="text-right py-3 px-2 font-semibold text-stone-600">P&amp;L</th>
                    <th className="text-right py-3 px-2 font-semibold text-stone-600">Return</th>
                  </tr>
                </thead>
                <tbody>
                  {recentTrades.map((t, i) => (
                    <TradeRow
                      key={i}
                      date={t.date}
                      symbol={t.symbol}
                      type={t.type}
                      entry={t.entry}
                      exit={t.exit}
                      pnl={t.pnl}
                      returnPct={t.pnl_pct}
                    />
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* About */}
        <div className="bg-white border border-stone-200 rounded-xl p-8">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-4">
            About This System
          </h2>
          <p className="text-stone-600 leading-relaxed">
            Automated trading system with multi-strategy execution, real-time risk management,
            and adaptive learning. Integrates with Interactive Brokers and TradingView for
            comprehensive market coverage. All data shown is historical and for informational
            purposes only.
          </p>
        </div>

        {/* Footer */}
        <footer className="mt-16 pt-8 border-t border-stone-200 text-center text-sm text-stone-400" role="contentinfo">
          <p>Winzinvest • Public View</p>
          <p className="mt-2">
            Past performance does not guarantee future results. Trading involves risk of loss.
          </p>
        </footer>
      </div>
    </div>
  );
}

function MetricCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-6 hover:shadow-lg transition-shadow">
      <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">
        {label}
      </div>
      <div className={`font-serif text-4xl font-bold ${color}`}>
        {value}
      </div>
    </div>
  );
}

function StatItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-stone-500 mb-1">{label}</div>
      <div className="font-serif text-2xl font-bold text-slate-900">{value}</div>
    </div>
  );
}

function AllocationBar({ label, percentage, color }: { label: string; percentage: number; color: string }) {
  return (
    <div>
      <div className="flex justify-between text-sm mb-2">
        <span className="text-stone-600">{label}</span>
        <span className="font-semibold text-slate-900">{percentage}%</span>
      </div>
      <div className="w-full h-2 bg-stone-100 rounded-full overflow-hidden">
        <div
          className={`h-full ${color} transition-all duration-500`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

function TradeRow({ date, symbol, type, entry, exit, pnl, returnPct }: {
  date: string;
  symbol: string;
  type: string;
  entry: number;
  exit: number;
  pnl: number;
  returnPct: number;
}) {
  const isProfit = pnl >= 0;
  const displayDate = date
    ? new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    : '—';

  return (
    <tr className="border-b border-stone-100 hover:bg-stone-50">
      <td className="py-3 px-2 text-stone-600">{displayDate}</td>
      <td className="py-3 px-2 font-semibold text-slate-900">{symbol}</td>
      <td className="py-3 px-2">
        <span className={`px-2 py-1 rounded text-xs ${
          type === 'Long' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
        }`}>
          {type}
        </span>
      </td>
      <td className="py-3 px-2 text-right text-stone-600 font-mono">
        {entry > 0 ? `$${entry.toFixed(2)}` : '—'}
      </td>
      <td className="py-3 px-2 text-right text-stone-600 font-mono">
        {exit > 0 ? `$${exit.toFixed(2)}` : '—'}
      </td>
      <td className={`py-3 px-2 text-right font-semibold ${isProfit ? 'text-green-600' : 'text-red-600'}`}>
        {isProfit ? '+' : ''}{formatCurrency(pnl)}
      </td>
      <td className={`py-3 px-2 text-right font-semibold ${isProfit ? 'text-green-600' : 'text-red-600'}`}>
        {isProfit ? '+' : ''}{returnPct.toFixed(2)}%
      </td>
    </tr>
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
