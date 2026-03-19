'use client';

import { use, useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { fetchWithAuth } from '@/lib/fetch-client';

interface JournalTrade {
  id: number | null;
  symbol: string;
  side: 'LONG' | 'SHORT';
  status: 'OPEN' | 'CLOSED';
  strategy: string;
  entry_timestamp: string;
  exit_timestamp: string | null;
  entry_price: number;
  exit_price: number | null;
  qty: number;
  pnl: number | null;
  pnl_pct: number | null;
  r_multiple: number | null;
  holding_days: number | null;
  exit_reason: string | null;
  reason: string | null;
  regime: string | null;
  conviction: number | null;
}

interface JournalData {
  generated_at?: string;
  closed: JournalTrade[];
  open: JournalTrade[];
  total_closed: number;
  total_open: number;
  error?: string;
}

type PageProps = {
  params?: Promise<Record<string, string | string[]>>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

const EMPTY = Promise.resolve({});

export default function JournalPage(props: PageProps) {
  use(props.params ?? EMPTY);
  use(props.searchParams ?? EMPTY);

  const [data, setData] = useState<JournalData | null>(null);
  const [filter, setFilter] = useState<'all' | 'open' | 'closed'>('all');
  const [sortBy, setSortBy] = useState<'date' | 'pnl' | 'return' | 'symbol'>('date');
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string>('');

  const fetchJournal = useCallback(async () => {
    try {
      const res = await fetch('/api/journal', { cache: 'no-store' });
      const json = (await res.json()) as JournalData;
      setData(json);
      if (json.generated_at) {
        setLastUpdated(new Date(json.generated_at).toLocaleTimeString());
      }
    } catch (err) {
      if (process.env.NODE_ENV === 'development') {
        console.error('Failed to load journal', err);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchJournal();
    const interval = setInterval(() => void fetchJournal(), 60_000);
    return () => clearInterval(interval);
  }, [fetchJournal]);

  const allTrades: JournalTrade[] = data
    ? [...data.open, ...data.closed]
    : [];

  const filtered = allTrades.filter(t => {
    if (filter === 'open') return t.status === 'OPEN';
    if (filter === 'closed') return t.status === 'CLOSED';
    return true;
  });

  const sorted = [...filtered].sort((a, b) => {
    if (sortBy === 'date') {
      const aTs = a.exit_timestamp || a.entry_timestamp;
      const bTs = b.exit_timestamp || b.entry_timestamp;
      return new Date(bTs).getTime() - new Date(aTs).getTime();
    }
    if (sortBy === 'pnl') return (b.pnl ?? 0) - (a.pnl ?? 0);
    if (sortBy === 'return') return (b.pnl_pct ?? 0) - (a.pnl_pct ?? 0);
    if (sortBy === 'symbol') return a.symbol.localeCompare(b.symbol);
    return 0;
  });

  const closedTrades = allTrades.filter(t => t.status === 'CLOSED');
  const totalPnL = closedTrades.reduce((s, t) => s + (t.pnl ?? 0), 0);
  const winners = closedTrades.filter(t => (t.pnl ?? 0) > 0).length;
  const losers = closedTrades.filter(t => (t.pnl ?? 0) < 0).length;
  const winRate = winners + losers > 0 ? ((winners / (winners + losers)) * 100).toFixed(1) : '—';
  const avgReturn =
    closedTrades.length > 0
      ? (closedTrades.reduce((s, t) => s + (t.pnl_pct ?? 0), 0) / closedTrades.length).toFixed(2)
      : '—';

  if (loading) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center">
        <div className="text-stone-400">Loading journal…</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-stone-50">
      <div className="max-w-7xl mx-auto px-8 py-12">
        {/* Header */}
        <header className="mb-12 pb-6 border-b border-stone-200">
          <Link href="/institutional" className="text-sm text-stone-500 hover:text-stone-600 mb-4 inline-block">
            ← Back to Dashboard
          </Link>
          <div className="flex items-end justify-between mt-4">
            <h1 className="font-serif text-5xl font-bold text-slate-900 tracking-tight">
              Trading Journal
            </h1>
            {lastUpdated && (
              <span className="text-xs text-stone-400 mb-1">Updated {lastUpdated}</span>
            )}
          </div>
          <p className="text-stone-500 mt-4 text-lg">
            Live trade history from <code className="text-xs bg-stone-100 px-1 py-0.5 rounded">trades.db</code>
          </p>
          {data?.error && (
            <div className="mt-4 px-4 py-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-700">
              {data.error}
            </div>
          )}
        </header>

        {/* Summary Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-8">
          <StatCard label="Realized P&L" value={formatCurrency(totalPnL)} colored pnl={totalPnL} />
          <StatCard
            label="Win Rate"
            value={winRate === '—' ? '—' : `${winRate}%`}
            sub={`${winners}W / ${losers}L`}
          />
          <StatCard
            label="Total Trades"
            value={String(allTrades.length)}
            sub={`${data?.total_open ?? 0} open`}
          />
          <StatCard
            label="Avg Return"
            value={avgReturn === '—' ? '—' : `${avgReturn}%`}
            sub="closed trades"
          />
        </div>

        {/* Filters */}
        <div className="bg-white border border-stone-200 rounded-xl p-5 mb-8 flex flex-wrap gap-4 items-center justify-between">
          <div className="flex gap-2">
            {(['all', 'open', 'closed'] as const).map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-4 py-2 rounded-lg text-sm font-semibold transition-colors capitalize ${
                  filter === f
                    ? 'bg-slate-900 text-white'
                    : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
                }`}
              >
                {f === 'all' ? 'All Trades' : f === 'open' ? 'Open' : 'Closed'}
              </button>
            ))}
          </div>
          <div className="flex gap-2 items-center">
            <span className="text-sm text-stone-500">Sort by:</span>
            <select
              value={sortBy}
              onChange={e => setSortBy(e.target.value as typeof sortBy)}
              className="px-3 py-2 bg-stone-100 border border-stone-200 rounded-lg text-sm text-stone-600 focus:outline-none focus:ring-2 focus:ring-sky-600"
            >
              <option value="date">Date</option>
              <option value="symbol">Symbol</option>
              <option value="pnl">P&L</option>
              <option value="return">Return %</option>
            </select>
          </div>
        </div>

        {/* Trades Table */}
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
          {sorted.length === 0 ? (
            <div className="py-16 text-center text-stone-400 text-sm">
              No trades found. Make sure <code className="bg-stone-100 px-1 rounded">dashboard_data_aggregator.py</code> has run at least once.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-stone-50 border-b border-stone-200">
                  <tr>
                    <th className="text-left py-4 px-4 font-semibold text-stone-600">Status</th>
                    <th className="text-left py-4 px-4 font-semibold text-stone-600">Symbol</th>
                    <th className="text-left py-4 px-4 font-semibold text-stone-600">Side</th>
                    <th className="text-left py-4 px-4 font-semibold text-stone-600">Strategy</th>
                    <th className="text-right py-4 px-4 font-semibold text-stone-600">Entry Date</th>
                    <th className="text-right py-4 px-4 font-semibold text-stone-600">Entry $</th>
                    <th className="text-right py-4 px-4 font-semibold text-stone-600">Exit $</th>
                    <th className="text-right py-4 px-4 font-semibold text-stone-600">Qty</th>
                    <th className="text-right py-4 px-4 font-semibold text-stone-600">P&L</th>
                    <th className="text-right py-4 px-4 font-semibold text-stone-600">Return</th>
                    <th className="text-right py-4 px-4 font-semibold text-stone-600">Days</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((trade, idx) => (
                    <tr key={trade.id ?? idx} className="border-b border-stone-100 hover:bg-stone-50">
                      <td className="py-3 px-4">
                        <span
                          className={`px-2 py-1 rounded-full text-xs font-semibold ${
                            trade.status === 'OPEN'
                              ? 'bg-blue-100 text-blue-700'
                              : 'bg-stone-100 text-stone-600'
                          }`}
                        >
                          {trade.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-bold text-slate-900">{trade.symbol}</td>
                      <td className="py-3 px-4">
                        <span
                          className={`px-2 py-1 rounded text-xs font-semibold ${
                            trade.side === 'LONG'
                              ? 'bg-green-100 text-green-700'
                              : 'bg-red-100 text-red-700'
                          }`}
                        >
                          {trade.side}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-stone-500 text-xs">{trade.strategy || '—'}</td>
                      <td className="py-3 px-4 text-right text-stone-600">
                        {formatDate(trade.entry_timestamp)}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-slate-900">
                        ${trade.entry_price.toFixed(2)}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-slate-900">
                        {trade.exit_price != null ? `$${trade.exit_price.toFixed(2)}` : '—'}
                      </td>
                      <td className="py-3 px-4 text-right text-stone-600">{trade.qty}</td>
                      <td
                        className={`py-3 px-4 text-right font-bold ${
                          trade.pnl == null
                            ? 'text-stone-400'
                            : trade.pnl >= 0
                              ? 'text-green-600'
                              : 'text-red-600'
                        }`}
                      >
                        {trade.pnl != null
                          ? `${trade.pnl >= 0 ? '+' : ''}${formatCurrency(trade.pnl)}`
                          : '—'}
                      </td>
                      <td
                        className={`py-3 px-4 text-right font-bold ${
                          trade.pnl_pct == null
                            ? 'text-stone-400'
                            : trade.pnl_pct >= 0
                              ? 'text-green-600'
                              : 'text-red-600'
                        }`}
                      >
                        {trade.pnl_pct != null
                          ? `${trade.pnl_pct >= 0 ? '+' : ''}${trade.pnl_pct.toFixed(2)}%`
                          : '—'}
                      </td>
                      <td className="py-3 px-4 text-right text-stone-500">
                        {trade.holding_days != null ? `${trade.holding_days}d` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Footer */}
        <footer className="mt-16 pt-8 border-t border-stone-200 text-center text-sm text-stone-400">
          <p>Winzinvest • Trading Journal</p>
          <p className="mt-2">All trades executed automatically via the NX execution system. Refreshes every 60 seconds.</p>
        </footer>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
  colored,
  pnl,
}: {
  label: string;
  value: string;
  sub?: string;
  colored?: boolean;
  pnl?: number;
}) {
  const valueColor = colored && pnl != null
    ? pnl >= 0 ? 'text-green-600' : 'text-red-600'
    : 'text-sky-600';
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-6">
      <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">{label}</div>
      <div className={`font-serif text-3xl font-bold ${valueColor}`}>{value}</div>
      {sub && <div className="text-xs text-stone-500 mt-1">{sub}</div>}
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

function formatDate(timestamp: string): string {
  if (!timestamp) return '—';
  return new Date(timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' });
}
