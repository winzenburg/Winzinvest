'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { fetchWithAuth } from '@/lib/fetch-client';
import type { AnalyticsData } from '../api/analytics/route';

// ── helpers ──────────────────────────────────────────────────────────────────

function fmt(n: number | null | undefined, decimals = 1): string {
  if (n == null) return '—';
  return n.toFixed(decimals);
}

function fmtPct(n: number | null | undefined): string {
  if (n == null) return '—';
  return `${n.toFixed(1)}%`;
}

function fmtPnl(n: number | null | undefined): string {
  if (n == null) return '—';
  const abs = Math.abs(n).toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
  return n >= 0 ? abs : `(${abs.slice(1)})`;
}

function rColor(r: number | null | undefined): string {
  if (r == null) return 'text-stone-500';
  if (r >= 2)   return 'text-emerald-600 font-semibold';
  if (r > 0)    return 'text-emerald-500';
  if (r === 0)  return 'text-stone-500';
  if (r > -1)   return 'text-amber-600';
  return 'text-red-600';
}

function wrColor(wr: number | null | undefined): string {
  if (wr == null) return 'text-stone-500';
  if (wr >= 55) return 'text-emerald-600 font-semibold';
  if (wr >= 45) return 'text-sky-600';
  if (wr >= 35) return 'text-amber-600';
  return 'text-red-600';
}

// ── sub-components ────────────────────────────────────────────────────────────

function StatCard({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-5">
      <p className="text-xs font-semibold uppercase tracking-wider text-stone-400 mb-1">{label}</p>
      <p className="text-2xl font-serif font-bold text-slate-900">{value}</p>
      {sub && <p className="text-xs text-stone-500 mt-1">{sub}</p>}
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-lg font-serif font-bold text-slate-900 mb-3">{children}</h2>
  );
}

function GroupTable({
  rows,
  valueLabel = 'Avg R',
}: {
  rows: AnalyticsData['by_strategy'];
  valueLabel?: string;
}) {
  if (!rows?.length) return <p className="text-sm text-stone-400">No data yet.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-stone-200 text-xs uppercase tracking-wider text-stone-500">
            <th className="text-left py-2 pr-4">Label</th>
            <th className="text-right py-2 pr-4">Trades</th>
            <th className="text-right py-2 pr-4">Win Rate</th>
            <th className="text-right py-2 pr-4">{valueLabel}</th>
            <th className="text-right py-2">PnL</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.label} className="border-b border-stone-100 last:border-0">
              <td className="py-2 pr-4 font-medium text-slate-700">{r.label}</td>
              <td className="py-2 pr-4 text-right text-stone-600">{r.count}</td>
              <td className={`py-2 pr-4 text-right ${wrColor(r.win_rate_pct)}`}>{fmtPct(r.win_rate_pct)}</td>
              <td className={`py-2 pr-4 text-right ${rColor(r.avg_r_multiple)}`}>{fmt(r.avg_r_multiple, 2)}R</td>
              <td className={`py-2 text-right ${r.total_pnl != null && r.total_pnl >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                {fmtPnl(r.total_pnl)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── page ─────────────────────────────────────────────────────────────────────

export default function AnalyticsPage() {
  const [data, setData]     = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState<string | null>(null);

  useEffect(() => {
    fetchWithAuth('/api/analytics')
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<AnalyticsData>;
      })
      .then(setData)
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center">
        <p className="text-stone-500 text-sm">Loading analytics…</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-500 text-sm mb-2">{error ?? 'Analytics unavailable'}</p>
          <Link href="/" className="text-sky-600 text-sm underline">← Dashboard</Link>
        </div>
      </div>
    );
  }

  const { summary, by_strategy, by_regime, hold_time, exit_reasons, monthly_pnl, top_trades, conviction_vs_r } = data;

  const noTrades = !summary || summary.total_closed === 0;

  return (
    <div className="min-h-screen bg-stone-50">
      {/* Header */}
      <div className="bg-white border-b border-stone-200 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div>
            <Link href="/" className="text-xs text-stone-400 hover:text-stone-600 mb-1 block">← Dashboard</Link>
            <h1 className="text-2xl font-serif font-bold text-slate-900">Trade Analytics</h1>
            <p className="text-xs text-stone-500 mt-0.5">
              {data.generated_at
                ? `Updated ${new Date(data.generated_at).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })}`
                : 'Run trade_analytics.py to generate'}
            </p>
          </div>
          <div className="flex gap-3">
            <Link href="/journal" className="text-xs bg-stone-100 hover:bg-stone-200 text-stone-700 px-3 py-1.5 rounded-lg transition-colors">
              Trade Journal
            </Link>
            <Link href="/performance" className="text-xs bg-stone-100 hover:bg-stone-200 text-stone-700 px-3 py-1.5 rounded-lg transition-colors">
              Performance
            </Link>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-8 space-y-8">

        {(data.note || noTrades) && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 text-sm text-amber-800">
            {data.note ?? 'No closed trades yet. Analytics will populate as trades complete.'}
          </div>
        )}

        {/* ── Summary stats ── */}
        {!noTrades && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard
                label="Closed Trades"
                value={summary.total_closed}
                sub={`${summary.wins ?? 0}W / ${summary.losses ?? 0}L / ${summary.breakeven ?? 0}B`}
              />
              <StatCard
                label="Win Rate"
                value={<span className={wrColor(summary.win_rate_pct)}>{fmtPct(summary.win_rate_pct)}</span>}
                sub="on closed positions"
              />
              <StatCard
                label="Avg R-Multiple"
                value={<span className={rColor(summary.avg_r_multiple)}>{fmt(summary.avg_r_multiple, 2)}R</span>}
                sub="expectancy per trade"
              />
              <StatCard
                label="Total PnL"
                value={
                  <span className={summary.total_realized_pnl != null && summary.total_realized_pnl >= 0 ? 'text-emerald-600' : 'text-red-600'}>
                    {fmtPnl(summary.total_realized_pnl)}
                  </span>
                }
                sub="realized only"
              />
            </div>

            {/* ── By Strategy + By Regime ── */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-white border border-stone-200 rounded-xl p-6">
                <SectionTitle>Performance by Strategy</SectionTitle>
                <GroupTable rows={by_strategy} valueLabel="Avg R" />
              </div>
              <div className="bg-white border border-stone-200 rounded-xl p-6">
                <SectionTitle>Performance by Regime at Entry</SectionTitle>
                <GroupTable rows={by_regime} valueLabel="Avg R" />
              </div>
            </div>

            {/* ── Hold time + Exit reasons ── */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-white border border-stone-200 rounded-xl p-6">
                <SectionTitle>Hold Time: Winners vs Losers</SectionTitle>
                {hold_time ? (
                  <div className="space-y-3 text-sm">
                    <div className="flex justify-between py-2 border-b border-stone-100">
                      <span className="text-stone-500">Avg hold — winners</span>
                      <span className="font-medium text-emerald-600">
                        {hold_time.avg_hold_days_winners != null ? `${fmt(hold_time.avg_hold_days_winners, 1)} days` : '—'}
                        <span className="text-stone-400 font-normal ml-1">({hold_time.winner_count} trades)</span>
                      </span>
                    </div>
                    <div className="flex justify-between py-2">
                      <span className="text-stone-500">Avg hold — losers</span>
                      <span className="font-medium text-red-600">
                        {hold_time.avg_hold_days_losers != null ? `${fmt(hold_time.avg_hold_days_losers, 1)} days` : '—'}
                        <span className="text-stone-400 font-normal ml-1">({hold_time.loser_count} trades)</span>
                      </span>
                    </div>
                    {hold_time.avg_hold_days_winners != null && hold_time.avg_hold_days_losers != null && (
                      <p className="text-xs text-stone-400 pt-2">
                        {hold_time.avg_hold_days_winners < hold_time.avg_hold_days_losers
                          ? '⚠ Winners close faster than losers — consider tighter time stops on losing positions'
                          : '✓ Winners held longer than losers — consistent with letting profits run'}
                      </p>
                    )}
                  </div>
                ) : <p className="text-sm text-stone-400">No data yet.</p>}
              </div>

              <div className="bg-white border border-stone-200 rounded-xl p-6">
                <SectionTitle>Exit Reason Distribution</SectionTitle>
                {exit_reasons?.length ? (
                  <div className="space-y-2">
                    {exit_reasons.map(e => (
                      <div key={e.reason} className="flex items-center gap-3">
                        <div className="w-28 text-xs text-stone-600 shrink-0">{e.reason.replace('_', ' ')}</div>
                        <div className="flex-1 bg-stone-100 rounded-full h-2">
                          <div
                            className="bg-slate-600 h-2 rounded-full"
                            style={{ width: `${e.pct}%` }}
                          />
                        </div>
                        <div className="text-xs text-stone-500 w-16 text-right">{e.count} ({e.pct}%)</div>
                      </div>
                    ))}
                  </div>
                ) : <p className="text-sm text-stone-400">No data yet.</p>}
              </div>
            </div>

            {/* ── Monthly PnL ── */}
            {monthly_pnl && monthly_pnl.length > 0 && (
              <div className="bg-white border border-stone-200 rounded-xl p-6">
                <SectionTitle>Monthly Realized PnL</SectionTitle>
                <div className="flex items-end gap-2 h-32 mt-4">
                  {monthly_pnl.map(m => {
                    const maxAbs = Math.max(...monthly_pnl.map(x => Math.abs(x.pnl)), 1);
                    const heightPct = Math.abs(m.pnl) / maxAbs * 100;
                    return (
                      <div key={m.month} className="flex-1 flex flex-col items-center gap-1">
                        <span className={`text-xs font-medium ${m.pnl >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                          {m.pnl >= 0 ? '+' : ''}{(m.pnl / 1000).toFixed(1)}k
                        </span>
                        <div className="w-full flex items-end justify-center" style={{ height: '80px' }}>
                          <div
                            className={`w-full rounded-t ${m.pnl >= 0 ? 'bg-emerald-400' : 'bg-red-400'}`}
                            style={{ height: `${heightPct}%`, minHeight: '4px' }}
                          />
                        </div>
                        <span className="text-[10px] text-stone-400">{m.month.slice(5)}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ── Conviction vs R ── */}
            {conviction_vs_r && conviction_vs_r.length > 0 && (
              <div className="bg-white border border-stone-200 rounded-xl p-6">
                <SectionTitle>Conviction Score vs R-Multiple</SectionTitle>
                <p className="text-xs text-stone-500 mb-4">
                  Does higher conviction at entry translate to better outcomes?
                </p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {conviction_vs_r.map(b => (
                    <div key={b.tier} className="bg-stone-50 rounded-lg p-4">
                      <p className="text-xs font-semibold uppercase tracking-wider text-stone-400 mb-2">
                        {b.tier}
                      </p>
                      <p className={`text-xl font-bold ${rColor(b.avg_r)}`}>{fmt(b.avg_r, 2)}R</p>
                      <p className={`text-sm ${wrColor(b.win_rate)}`}>{fmtPct(b.win_rate)} WR</p>
                      <p className="text-xs text-stone-400 mt-1">{b.count} trades</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ── Best / worst trades ── */}
            {top_trades && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {(['best', 'worst'] as const).map(side => (
                  <div key={side} className="bg-white border border-stone-200 rounded-xl p-6">
                    <SectionTitle>{side === 'best' ? '🏆 Best 5 Trades' : '📉 Worst 5 Trades'}</SectionTitle>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-stone-200 text-xs uppercase tracking-wider text-stone-500">
                          <th className="text-left py-2 pr-3">Symbol</th>
                          <th className="text-right py-2 pr-3">R</th>
                          <th className="text-right py-2 pr-3">PnL</th>
                          <th className="text-right py-2">Days</th>
                        </tr>
                      </thead>
                      <tbody>
                        {top_trades[side].map((t, i) => (
                          <tr key={i} className="border-b border-stone-100 last:border-0">
                            <td className="py-1.5 pr-3">
                              <span className="font-semibold text-slate-700">{t.symbol}</span>
                              <span className="ml-1.5 text-[10px] text-stone-400">{t.strategy}</span>
                            </td>
                            <td className={`py-1.5 pr-3 text-right font-medium ${rColor(t.r_multiple)}`}>
                              {fmt(t.r_multiple, 2)}R
                            </td>
                            <td className={`py-1.5 pr-3 text-right text-xs ${t.pnl >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                              {fmtPnl(t.pnl)}
                            </td>
                            <td className="py-1.5 text-right text-xs text-stone-400">
                              {t.hold_days ?? '—'}d
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* Footer note */}
        <p className="text-xs text-stone-400 text-center pb-4">
          Data sourced from trades.db · Refreshed daily at post-close (4:30 PM ET)
        </p>
      </div>
    </div>
  );
}
