'use client';

/**
 * Performance & Track Record page.
 *
 * Purpose:  The social proof asset. Addresses the "black box trust" and "lack of
 *           social proof" failure modes. Designed to fill over time as the system
 *           accumulates a live record.
 *
 * Design principles (from strategic positioning brief):
 *  - Transparency over marketing: show actual numbers, drawdowns, attribution
 *  - "Track record building" state is explicit and confident, not apologetic
 *  - Framework established now so the data has structure when it arrives
 *  - Attracts investors who value consistency, not gamblers seeking quick profits
 *
 * Live data: connects to /api/dashboard when available; falls back to structure.
 * Monthly updates: each month appended to MONTHLY_RECORDS below.
 */

import Link from 'next/link';
import { use, useEffect, useState } from 'react';
import { fetchWithAuth } from '@/lib/fetch-client';
import { PublicNav } from '../components/PublicNav';

interface SnapshotData {
  portfolio?: {
    daily_pnl_pct?: number;
  };
  performance?: {
    total_return_pct?: number | null;
    total_return_30d_pct?: number | null;
    portfolio_return_pct?: number | null;
    portfolio_return_since?: string | null;
    sharpe?: number;
    sharpe_ratio?: number;
    max_drawdown_pct?: number;
    daily_return_pct?: number;
  };
  regime?: { execution?: string; macro_band?: string };
}

/**
 * Monthly performance record — append one entry per month as the track record builds.
 * All values are percentages — no dollar amounts are published publicly.
 *   options_income_pct  — options premium collected as % of portfolio for the period
 */
const MONTHLY_RECORDS: Array<{
  month: string;
  return_pct: number | null;
  options_income_pct: number | null;
  max_drawdown_pct: number | null;
  regime_summary: string;
  notes: string;
}> = [
  {
    month: 'Mar 2026 (partial — thru Mar 17)',
    return_pct: -4.2,
    options_income_pct: null,
    max_drawdown_pct: 6.8,
    regime_summary: 'RISK_ON → CHOPPY',
    notes:
      'First 6 trading days of tracked live history (SOD tracking began Mar 12). ' +
      'The early NLV decline reflects the wind-down of oversized legacy positions ' +
      'from Mar 10–13 that were flagged and excluded from PnL metrics — not active ' +
      'signal performance. Active-signal equity P&L (Mar 12–17): +$1,513. ' +
      'Options rolls executed on APA, CHRD, CE (Apr → Jun expiry). ' +
      'Tuesday Phase 1 restructure exited USO. 18 covered calls and 5 CSPs active at month-to-date close.',
  },
];

const REPORTING_FRAMEWORK = [
  {
    label: 'Monthly return',
    desc: 'Total portfolio return including equity appreciation and options premium, net of any trading costs.',
    accent: 'border-l-sky-600',
  },
  {
    label: 'Options income',
    desc: 'Premium collected from covered calls and cash-secured puts during the period, expressed as a percentage of portfolio value. Reported before accounting for any buybacks or rolls.',
    accent: 'border-l-green-600',
  },
  {
    label: 'Maximum drawdown',
    desc: 'The largest peak-to-trough decline during the month. Reported separately from return to give a complete picture of risk taken.',
    accent: 'border-l-red-500',
  },
  {
    label: 'Strategy attribution',
    desc: 'Breakdown of return contribution by subsystem — equity momentum, mean reversion, options income, and pairs — so performance can be understood, not just observed.',
    accent: 'border-l-orange-500',
  },
  {
    label: 'Regime context',
    desc: 'The market regimes active during the period and how they influenced portfolio behavior. Drawdowns and slow months are explained, not hidden.',
    accent: 'border-l-sky-600',
  },
  {
    label: 'System notes',
    desc: 'Any parameter updates, optimization changes, or notable system events during the period — maintaining the same audit transparency available to active subscribers.',
    accent: 'border-l-stone-400',
  },
];

function LiveMetricCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent: string;
}) {
  return (
    <div className={`bg-white border border-stone-200 rounded-xl p-5 border-t-4 ${accent}`}>
      <div className="text-xs text-stone-400 uppercase tracking-wider mb-2">{label}</div>
      <div className="font-serif text-2xl font-bold text-slate-900 leading-none mb-1">{value}</div>
      {sub && <div className="text-xs text-stone-400">{sub}</div>}
    </div>
  );
}

type PageProps = {
  params?: Promise<Record<string, string | string[]>>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

const EMPTY = Promise.resolve({});

export default function PerformancePage(props: PageProps) {
  use(props.params ?? EMPTY);
  use(props.searchParams ?? EMPTY);
  const [snapshot, setSnapshot] = useState<SnapshotData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetchWithAuth('/api/dashboard');
        if (!r.ok || cancelled) return;
        const d = await r.json();
        if (!cancelled) setSnapshot(d as SnapshotData);
      } catch {
        /* 401 handled by fetchWithAuth */
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const liveAvailable = !loading && snapshot !== null;
  const hasMonthlyData = MONTHLY_RECORDS.length > 0;

  const fmt = (n: number | undefined, decimals = 2) =>
    n !== undefined ? n.toFixed(decimals) : '—';
  const fmtPct = (n: number | undefined, decimals = 2) =>
    n !== undefined ? `${n >= 0 ? '+' : ''}${n.toFixed(decimals)}%` : '—';

  return (
    <div className="min-h-screen bg-stone-50">

      {/* Nav */}
      <PublicNav />

      <div className="max-w-5xl mx-auto px-8 py-16">

        {/* Header */}
        <header className="mb-14">
          <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-3">Performance &amp; Track Record</div>
          <h1 className="font-serif text-4xl font-bold text-slate-900 leading-tight tracking-tight mb-5">
            Live system performance
          </h1>
          <p className="text-base text-stone-600 leading-relaxed max-w-2xl mb-4">
            This page publishes percentage-based performance data from the live Winzinvest system.
            Results are reported monthly with full attribution — return by strategy,
            options income as a percentage of portfolio, maximum drawdown, and regime context —
            so performance can be understood, not just observed.
          </p>
          <p className="text-sm text-stone-500 leading-relaxed max-w-2xl">
            We report drawdowns and difficult periods alongside strong ones. A track
            record that only shows wins is not a track record — it is marketing.
          </p>
        </header>

        {/* Live system snapshot — pulls from dashboard API */}
        <section className="mb-16">
          <div className="flex items-center gap-3 mb-5">
            <div className="text-xs font-semibold uppercase tracking-wider text-stone-500">Live System Status</div>
            {liveAvailable && (
              <span className="flex items-center gap-1.5 text-xs text-green-700 font-semibold">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                Connected
              </span>
            )}
            {loading && (
              <span className="text-xs text-stone-400">Loading…</span>
            )}
            {!loading && !liveAvailable && (
              <span className="text-xs text-stone-400">Dashboard offline</span>
            )}
          </div>

          {liveAvailable ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
              {(() => {
                const returnPct =
                  snapshot?.performance?.total_return_30d_pct ??
                  snapshot?.performance?.portfolio_return_pct ??
                  null;
                const since = snapshot?.performance?.portfolio_return_since;
                const has30d = snapshot?.performance?.total_return_30d_pct != null;
                const subLabel = has30d
                  ? '30-day (NLV change)'
                  : since
                    ? `Since ${new Date(since).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} (NLV change)`
                    : 'Insufficient history';
                return (
                  <LiveMetricCard
                    label="Portfolio Return"
                    value={returnPct != null ? fmtPct(returnPct) : '—'}
                    sub={subLabel}
                    accent={
                      returnPct == null ? 'border-t-stone-300' :
                      returnPct >= 0 ? 'border-t-green-600' : 'border-t-red-500'
                    }
                  />
                );
              })()}
              <LiveMetricCard
                label="Daily Return"
                value={fmtPct(snapshot?.performance?.daily_return_pct ?? snapshot?.portfolio?.daily_pnl_pct)}
                sub="Today"
                accent={
                  (snapshot?.performance?.daily_return_pct ?? snapshot?.portfolio?.daily_pnl_pct ?? 0) >= 0
                    ? 'border-t-green-600'
                    : 'border-t-red-500'
                }
              />
              <LiveMetricCard
                label="Max Drawdown"
                value={snapshot?.performance?.max_drawdown_pct !== undefined ? `${snapshot.performance.max_drawdown_pct.toFixed(2)}%` : '—'}
                sub="Peak to trough"
                accent="border-t-amber-500"
              />
              <LiveMetricCard
                label="Sharpe Ratio"
                value={fmt(snapshot?.performance?.sharpe_ratio ?? snapshot?.performance?.sharpe)}
                sub="Risk-adjusted return"
                accent="border-t-sky-600"
              />
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
              {['Total Return', 'Daily Return', 'Max Drawdown', 'Sharpe Ratio'].map((label) => (
                <div key={label} className="bg-white border border-stone-200 rounded-xl p-5 border-t-4 border-t-stone-200">
                  <div className="text-xs text-stone-400 uppercase tracking-wider mb-2">{label}</div>
                  <div className="h-6 w-16 bg-stone-100 rounded animate-pulse" />
                </div>
              ))}
            </div>
          )}

          {liveAvailable && snapshot?.regime && (
            <div className="flex gap-3">
              <div className="bg-white border border-stone-200 rounded-lg px-4 py-2.5 flex items-center gap-2">
                <span className="text-xs text-stone-400 uppercase tracking-wider">Execution regime</span>
                <span className="font-mono text-xs font-bold text-slate-800">{snapshot.regime.execution ?? '—'}</span>
              </div>
              <div className="bg-white border border-stone-200 rounded-lg px-4 py-2.5 flex items-center gap-2">
                <span className="text-xs text-stone-400 uppercase tracking-wider">Macro band</span>
                <span className="font-mono text-xs font-bold text-slate-800">{snapshot.regime.macro_band ?? '—'}</span>
              </div>
              {snapshot?.performance?.max_drawdown_pct !== undefined && (
                <div className="bg-white border border-stone-200 rounded-lg px-4 py-2.5 flex items-center gap-2">
                  <span className="text-xs text-stone-400 uppercase tracking-wider">Max drawdown</span>
                  <span className="font-mono text-xs font-bold text-slate-800">
                    {fmtPct(snapshot.performance.max_drawdown_pct)}
                  </span>
                </div>
              )}
            </div>
          )}
        </section>

        <div className="border-t border-stone-200 mb-16" />

        {/* Monthly track record */}
        <section className="mb-16">
          <div className="flex items-center justify-between mb-5">
            <div className="text-xs font-semibold uppercase tracking-wider text-stone-500">Monthly Track Record</div>
            <span className="text-xs text-stone-400">
              {hasMonthlyData ? `${MONTHLY_RECORDS.length} month${MONTHLY_RECORDS.length !== 1 ? 's' : ''} reported` : 'Building track record'}
            </span>
          </div>

          {hasMonthlyData ? (
            <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
              <div className="grid grid-cols-[160px_100px_130px_120px_1fr] text-xs font-semibold uppercase tracking-wider text-stone-400 px-5 py-3 border-b border-stone-100 bg-stone-50">
                <span>Month</span>
                <span>Return</span>
                <span>Options Income</span>
                <span>Max Drawdown</span>
                <span>Notes</span>
              </div>
              {MONTHLY_RECORDS.map((r, i) => (
                <div
                  key={r.month}
                  className={`grid grid-cols-[160px_100px_130px_120px_1fr] items-start px-5 py-4 text-sm ${i < MONTHLY_RECORDS.length - 1 ? 'border-b border-stone-100' : ''}`}
                >
                  <span className="font-semibold text-slate-900">{r.month}</span>
                  <span className={`font-mono font-bold ${r.return_pct === null ? 'text-stone-400' : r.return_pct >= 0 ? 'text-green-700' : 'text-red-600'}`}>
                    {r.return_pct === null ? '—' : `${r.return_pct >= 0 ? '+' : ''}${r.return_pct.toFixed(2)}%`}
                  </span>
                  <span className={`font-mono text-sm ${r.options_income_pct === null ? 'text-stone-400' : 'text-green-700'}`}>
                    {r.options_income_pct === null ? '—' : `+${r.options_income_pct.toFixed(2)}%`}
                  </span>
                  <span className={`font-mono text-sm ${r.max_drawdown_pct === null ? 'text-stone-400' : 'text-amber-700'}`}>
                    {r.max_drawdown_pct === null ? '—' : `${r.max_drawdown_pct.toFixed(2)}%`}
                  </span>
                  <span className="text-stone-500 text-xs leading-relaxed">{r.notes}</span>
                </div>
              ))}
            </div>
          ) : (
            /* Track record building state */
            <div className="bg-white border border-stone-200 rounded-xl p-8">
              <div className="flex items-start gap-5">
                <div className="w-10 h-10 rounded-full bg-sky-50 border border-sky-200 flex items-center justify-center shrink-0 mt-0.5">
                  <span className="text-sky-600 font-bold text-sm">01</span>
                </div>
                <div>
                  <div className="font-semibold text-slate-900 mb-2">Track record in progress</div>
                  <p className="text-sm text-stone-600 leading-relaxed mb-4">
                    The system is live and operating. Monthly performance reports will be published
                    here as each period closes — starting with the first complete calendar month
                    of live operation. Each report will include return, options income, maximum
                    drawdown, strategy attribution, and regime context.
                  </p>
                  <p className="text-sm text-stone-500 leading-relaxed">
                    We are not publishing estimated or projected figures in their place.
                    A track record starts when the system starts — not before.
                  </p>
                </div>
              </div>
            </div>
          )}
        </section>

        <div className="border-t border-stone-200 mb-16" />

        {/* What will be reported — the framework */}
        <section className="mb-16">
          <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">Reporting Framework</div>
          <h2 className="font-serif text-2xl font-bold text-slate-900 mb-2">What gets reported and why</h2>
          <p className="text-sm text-stone-500 max-w-2xl mb-8">
            Each monthly report covers six dimensions. The framework is published here
            in advance so investors know exactly what to expect — and what to scrutinize.
          </p>

          <div className="space-y-3">
            {REPORTING_FRAMEWORK.map(({ label, desc, accent }) => (
              <div key={label} className={`bg-white border border-stone-200 rounded-xl p-5 border-l-4 ${accent}`}>
                <div className="font-semibold text-sm text-slate-900 mb-1">{label}</div>
                <p className="text-sm text-stone-500 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </section>

        <div className="border-t border-stone-200 mb-16" />

        {/* How to read performance */}
        <section className="mb-16">
          <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">Context</div>
          <h2 className="font-serif text-2xl font-bold text-slate-900 mb-6">How to read systematic performance</h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              {
                title: 'Drawdowns are expected',
                body: 'Every systematic strategy experiences drawdown periods. The question is not whether drawdowns occur — they will — but whether they are proportionate to the risk being taken and whether the system recovers in a reasonable time. A drawdown of 5–8% in a given month is not a system failure. It is the expected cost of being invested.',
              },
              {
                title: 'Slow months have explanations',
                body: 'Options income strategies slow when implied volatility is low. Momentum strategies produce less in sideways or choppy markets. The regime context column in each monthly report explains which conditions the portfolio faced. This is the difference between understanding performance and simply reacting to it.',
              },
              {
                title: 'Attribution matters more than total return',
                body: 'A month with a 2% total return where options income was 3% and equity positions lost 1% is fundamentally different from a 2% return driven entirely by a single leveraged position. Attribution is what allows investors to assess whether the system is working as designed.',
              },
              {
                title: 'Compounding is the goal',
                body: 'The system is not designed to produce spectacular single-month returns. It is designed to produce consistent, compounding returns with controlled risk. A portfolio that returns 2–3% per month with low drawdowns outperforms one that returns 8% in one month and loses 6% the next — even though the latter sounds more exciting.',
              },
            ].map(({ title, body }) => (
              <div key={title} className="bg-white border border-stone-200 rounded-xl p-5">
                <div className="font-semibold text-sm text-slate-900 mb-2">{title}</div>
                <p className="text-xs text-stone-500 leading-relaxed">{body}</p>
              </div>
            ))}
          </div>
        </section>

        <div className="border-t border-stone-200 mb-16" />

        {/* For subscribers */}
        <section className="mb-16">
          <div className="bg-slate-900 rounded-xl p-8 md:p-10">
            <div className="text-xs font-semibold uppercase tracking-wider text-sky-400 mb-3">For Subscribers</div>
            <h2 className="font-serif text-2xl font-bold text-white mb-4">
              Full performance data is available in the dashboard
            </h2>
            <p className="text-stone-400 text-sm leading-relaxed mb-6 max-w-xl">
              Active subscribers have access to real-time portfolio metrics, the full trade history,
              strategy-level attribution, options income tracking, and the complete optimization audit trail —
              updated continuously throughout each trading session.
            </p>
            <div className="flex gap-3">
              <Link
                href="/login"
                className="px-6 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-offset-2 focus:ring-offset-slate-900"
              >
                Open Dashboard
              </Link>
              <Link
                href="/landing#pricing"
                className="px-6 py-2.5 rounded-xl border border-stone-600 hover:bg-stone-800 text-stone-300 font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-stone-500 focus:ring-offset-2 focus:ring-offset-slate-900"
              >
                View Plans
              </Link>
            </div>
          </div>
        </section>

        {/* Disclaimer */}
        <section>
          <div className="bg-stone-100 border border-stone-200 rounded-xl p-6">
            <div className="text-xs font-semibold uppercase tracking-wider text-stone-400 mb-3">Disclaimer</div>
            <p className="text-xs text-stone-500 leading-relaxed">
              Performance figures represent live system results and are not audited by a third party.
              Past performance does not guarantee future results. Systematic strategies can and do
              underperform. All performance data is reported in good faith and reflects actual
              portfolio activity — including losing periods. Winzinvest is systematic portfolio
              automation software and does not provide investment advice. Investing in equities and
              options involves substantial risk of loss.
            </p>
          </div>
        </section>

      </div>

      {/* Footer */}
      <footer className="border-t border-stone-200 py-10 px-8 max-w-5xl mx-auto mt-8">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 mb-6">
          <span className="font-serif font-bold text-stone-500 text-sm">Winzinvest</span>
          <div className="flex gap-6">
            <Link href="/overview"    className="text-sm text-stone-400 hover:text-stone-600 transition-colors">Overview</Link>
            <Link href="/methodology" className="text-sm text-stone-400 hover:text-stone-600 transition-colors">Methodology</Link>
            <Link href="/research"    className="text-sm text-stone-400 hover:text-stone-600 transition-colors">Research</Link>
            <Link href="/landing#pricing" className="text-sm text-stone-400 hover:text-stone-600 transition-colors">Pricing</Link>
            <Link href="/login"       className="text-sm text-stone-400 hover:text-stone-600 transition-colors">Dashboard</Link>
          </div>
        </div>
        <p className="text-xs text-stone-400 leading-relaxed max-w-3xl">
          Winzinvest is systematic portfolio automation software. It does not provide investment advice.
          Past performance does not guarantee future results. Investing involves substantial risk of loss.
        </p>
      </footer>
    </div>
  );
}
