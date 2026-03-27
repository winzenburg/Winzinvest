'use client';

import { use, useEffect, useState } from 'react';
import { fetchWithAuth } from '@/lib/fetch-client';
import DashboardNav from '../components/DashboardNav';
import NotificationPrefsPanel from '../components/NotificationPrefs';

interface AuditEntry {
  timestamp: string;
  event_type: string;
  symbol?: string;
  signal_type?: string;
  failed_gates?: string[];
  message?: string;
  severity?: string;
  context?: Record<string, unknown>;
}

interface AuditSummary {
  total: number;
  by_type: Record<string, number>;
  gate_rejections: {
    total: number;
    by_gate: Record<string, number>;
    by_symbol: Record<string, number>;
  };
}

type PageProps = {
  params?: Promise<Record<string, string | string[]>>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

const EMPTY = Promise.resolve({});

export default function AuditPage(props: PageProps) {
  use(props.params ?? EMPTY);
  use(props.searchParams ?? EMPTY);
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [summary, setSummary] = useState<AuditSummary | null>(null);
  const [filter, setFilter] = useState<string>('all');
  const [loading, setLoading] = useState(true);
  const [showNotifPrefs, setShowNotifPrefs] = useState(false);

  useEffect(() => {
    const fetchAudit = async () => {
      try {
        const res = await fetchWithAuth(
          `/api/audit?hours=24${filter !== 'all' ? `&type=${filter}` : ''}`,
        );
        if (res.ok) {
          const data = await res.json();
          setEntries(data.entries || []);
          setSummary(data.summary || null);
        }
      } catch (error) {
        if (process.env.NODE_ENV === 'development') {
          console.error('Failed to fetch audit trail:', error);
        }
      } finally {
        setLoading(false);
      }
    };

    fetchAudit();
    const interval = setInterval(fetchAudit, 60000);
    return () => clearInterval(interval);
  }, [filter]);

  if (loading) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center">
        <div className="text-stone-400">Loading audit trail...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-stone-50">
      <div className="max-w-7xl mx-auto px-6 lg:px-10 pt-8 pb-16">
        <DashboardNav onOpenNotificationPrefs={() => setShowNotifPrefs(true)} />

        <header className="mb-8 pb-4 border-b border-stone-200">
          <h1 className="font-serif text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">Audit Trail</h1>
          <p className="text-stone-500 mt-2 text-sm">
            System decisions, orders, and gate rejections (rolling window).
          </p>
        </header>

        {/* Summary Cards */}
        {summary && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            <div className="bg-white border border-stone-200 rounded-xl p-6">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">
                Total Events
              </div>
              <div className="font-serif text-4xl font-bold text-sky-600">
                {summary.total}
              </div>
            </div>

            <div className="bg-white border border-stone-200 rounded-xl p-6">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">
                Gate Rejections
              </div>
              <div className="font-serif text-4xl font-bold text-red-600">
                {summary.gate_rejections.total}
              </div>
            </div>

            <div className="bg-white border border-stone-200 rounded-xl p-6">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">
                Top Failed Gate
              </div>
              <div className="font-serif text-2xl font-bold text-sky-600">
                {Object.entries(summary.gate_rejections.by_gate)
                  .sort(([, a], [, b]) => b - a)[0]?.[0] || 'None'}
              </div>
              <div className="text-xs text-stone-500 mt-1">
                {Object.entries(summary.gate_rejections.by_gate)
                  .sort(([, a], [, b]) => b - a)[0]?.[1] || 0} times
              </div>
            </div>

            <div className="bg-white border border-stone-200 rounded-xl p-6">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">
                Most Rejected Symbol
              </div>
              <div className="font-serif text-2xl font-bold text-sky-600">
                {Object.entries(summary.gate_rejections.by_symbol)
                  .sort(([, a], [, b]) => b - a)[0]?.[0] || 'None'}
              </div>
              <div className="text-xs text-stone-500 mt-1">
                {Object.entries(summary.gate_rejections.by_symbol)
                  .sort(([, a], [, b]) => b - a)[0]?.[1] || 0} times
              </div>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="bg-white border border-stone-200 rounded-xl p-6 mb-8">
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setFilter('all')}
              className={`px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${
                filter === 'all'
                  ? 'bg-slate-900 text-white'
                  : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
              }`}
            >
              All Events
            </button>
            <button
              type="button"
              onClick={() => setFilter('gate_rejection')}
              className={`px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${
                filter === 'gate_rejection'
                  ? 'bg-slate-900 text-white'
                  : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
              }`}
            >
              Gate Rejections
            </button>
            <button
              type="button"
              onClick={() => setFilter('order_event')}
              className={`px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${
                filter === 'order_event'
                  ? 'bg-slate-900 text-white'
                  : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
              }`}
            >
              Orders
            </button>
            <button
              type="button"
              onClick={() => setFilter('system_event')}
              className={`px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${
                filter === 'system_event'
                  ? 'bg-slate-900 text-white'
                  : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
              }`}
            >
              System Events
            </button>
          </div>
        </div>

        {/* Audit Entries */}
        <div className="space-y-3">
          {entries.map((entry, idx) => (
            <div
              key={idx}
              className={`bg-white border rounded-xl p-6 ${
                entry.event_type === 'gate_rejection'
                  ? 'border-red-200'
                  : entry.severity === 'error' || entry.severity === 'critical'
                  ? 'border-orange-200'
                  : 'border-stone-200'
              }`}
            >
              <div className="flex justify-between items-start mb-3">
                <div className="flex items-center gap-3">
                  <span className={`px-2 py-1 rounded text-xs font-semibold ${
                    entry.event_type === 'gate_rejection'
                      ? 'bg-red-100 text-red-700'
                      : entry.event_type === 'order_event'
                      ? 'bg-blue-100 text-blue-700'
                      : 'bg-stone-100 text-stone-600'
                  }`}>
                    {entry.event_type.replace('_', ' ').toUpperCase()}
                  </span>
                  {entry.symbol && (
                    <span className="font-bold text-slate-900">{entry.symbol}</span>
                  )}
                  {entry.signal_type && (
                    <span className={`px-2 py-1 rounded text-xs ${
                      entry.signal_type === 'LONG'
                        ? 'bg-green-100 text-green-700'
                        : 'bg-red-100 text-red-700'
                    }`}>
                      {entry.signal_type}
                    </span>
                  )}
                </div>
                <div className="text-xs text-stone-500">
                  {new Date(entry.timestamp).toLocaleString()}
                </div>
              </div>

              {entry.failed_gates && entry.failed_gates.length > 0 && (
                <div className="mb-3">
                  <div className="text-sm font-semibold text-red-700 mb-2">
                    Failed Gates:
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {entry.failed_gates.map((gate, i) => (
                      <span
                        key={i}
                        className="px-2 py-1 bg-red-50 text-red-700 rounded text-xs font-mono"
                      >
                        {gate}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {entry.message && (
                <div className="text-sm text-stone-600 mb-3">
                  {entry.message}
                </div>
              )}

              {entry.context && Object.keys(entry.context).length > 0 && (
                <details className="text-xs">
                  <summary className="cursor-pointer text-stone-500 hover:text-stone-600">
                    View context
                  </summary>
                  <pre className="mt-2 p-3 bg-stone-50 rounded text-xs overflow-x-auto">
                    {JSON.stringify(entry.context, null, 2)}
                  </pre>
                </details>
              )}
            </div>
          ))}
        </div>

        {entries.length === 0 && (
          <div className="bg-white border border-stone-200 rounded-xl p-12 text-center">
            <div className="text-stone-400">No audit entries found</div>
          </div>
        )}

        {showNotifPrefs && <NotificationPrefsPanel onClose={() => setShowNotifPrefs(false)} />}

        <footer className="mt-12 pt-6 border-t border-stone-200 text-center text-xs text-stone-400" role="contentinfo">
          <p>Winzinvest</p>
          <p className="mt-2 max-w-xl mx-auto">
            Past performance does not guarantee future results. Trading involves risk of loss.
          </p>
        </footer>
      </div>
    </div>
  );
}
