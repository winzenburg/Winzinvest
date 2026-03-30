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
  market_regime?: { regime?: string; macro_regime?: string };
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
  isBaseline?: boolean;
}> = [
  {
    month: 'Mar 2026 (transition, Mar 12–16)',
    return_pct: null,
    options_income_pct: null,
    max_drawdown_pct: null,
    regime_summary: 'RISK_ON → CHOPPY',
    notes:
      'Pre-system transition period — not included in performance tracking. ' +
      'SOD equity capture began Mar 12 to establish a baseline. NLV decline during ' +
      'this window reflects deliberate wind-down of oversized legacy positions flagged ' +
      'for exit, not active-signal performance. Active-signal equity P&L Mar 12–16: +$1,513.',
  },
  {
    month: 'Mar 2026 (live system, Mar 17+)',
    return_pct: null,
    options_income_pct: null,
    max_drawdown_pct: null,
    regime_summary: 'CHOPPY',
    isBaseline: true,
    notes:
      'Official system start — baseline NLV set at $161,884 on Mar 17, 2026. ' +
      'All performance tracking, portfolio return metrics, and attribution begin here. ' +
      'Month not yet closed — return will be reported when March 2026 closes. ' +
      '18 covered calls and 5 CSPs active. Options rolls on APA, CHRD, CE (Apr → Jun expiry) ' +
      'completed during the week of Mar 17.',
  },
];

const REPORTING_FRAMEWORK = [
  {
    label: 'Monthly return',
    desc: 'Total portfolio return: equity moves plus options premium, net of costs. The number that matters.',
    accent: 'border-l-sky-600',
  },
  {
    label: 'Options income',
    desc: 'Premium collected from covered calls and cash-secured puts, as a percentage of portfolio. Reported before buybacks or rolls (gross income, not net).',
    accent: 'border-l-green-600',
  },
  {
    label: 'Maximum drawdown',
    desc: 'Worst peak-to-trough decline during the month. Reported separately so you know how much pain the return required.',
    accent: 'border-l-red-500',
  },
  {
    label: 'Strategy attribution',
    desc: `Which strategies made money and which didn't. Momentum, mean reversion, options, pairs, broken out so you can see what's actually working.`,
    accent: 'border-l-orange-500',
  },
  {
    label: 'Regime context',
    desc: 'What the market was doing and how the system responded. Bad months get explained, not buried.',
    accent: 'border-l-sky-600',
  },
  {
    label: 'System notes',
    desc: 'Parameter changes, optimization tweaks, anything that affected performance. Same transparency subscribers get.',
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
      {sub && <div className="text-xs text-stone-600">{sub}</div>}
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
        // Public endpoint - no auth required
        const r = await fetch('/api/public-performance');
        if (!r.ok || cancelled) return;
        const d = await r.json();
        if (!cancelled) setSnapshot(d as SnapshotData);
      } catch {
        /* Network or parsing error */
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
          <div className="text-xs font-semibold uppercase tracking-wider text-stone-700 mb-3">Performance &amp; Track Record</div>
          <h1 className="font-serif text-4xl font-bold text-slate-900 leading-tight tracking-tight mb-5">
            The live track record
          </h1>
          <p className="text-base text-stone-600 leading-relaxed max-w-2xl mb-4">
            This page publishes performance from the live system: monthly returns, options income, 
            max drawdown, and strategy attribution. No dollar amounts, just percentages. 
            You can see what's working and what isn't.
          </p>
          <p className="text-sm text-stone-600 leading-relaxed max-w-2xl mb-3">
            We report bad months alongside good ones. Drawdowns included. A track record that only 
            shows wins isn't a track record but a sales pitch.
          </p>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-sky-50 border border-sky-200 text-xs text-sky-700 font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-sky-500 shrink-0" />
            Live system tracking began <strong className="ml-1">March 17, 2026</strong>
          </div>
        </header>

        {/* Live system snapshot — pulls from dashboard API */}
        <section className="mb-16">
          <div className="flex items-center gap-3 mb-5">
            <div className="text-xs font-semibold uppercase tracking-wider text-stone-700">Live System Status</div>
            {liveAvailable && (
              <span className="flex items-center gap-1.5 text-xs text-green-700 font-semibold">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                Connected
              </span>
            )}
            {loading && (
              <span className="text-xs text-stone-600">Loading…</span>
            )}
            {!loading && !liveAvailable && (
              <span className="text-xs text-stone-600">Dashboard offline</span>
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
                const isBaseline = since === '2026-03-17';
                const subLabel = has30d
                  ? '30-day (NLV change)'
                  : since
                    ? `Since ${new Date(since + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}${isBaseline ? ' · system baseline' : ' (NLV change)'}`
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
                  <div className="text-xs text-stone-600 uppercase tracking-wider mb-2">{label}</div>
                  <div className="h-6 w-16 bg-stone-100 rounded animate-pulse" />
                </div>
              ))}
            </div>
          )}

          {liveAvailable && snapshot?.market_regime && (
            <div className="flex gap-3">
              <div className="bg-white border border-stone-200 rounded-lg px-4 py-2.5 flex items-center gap-2">
                <span className="text-xs text-stone-600 uppercase tracking-wider">Execution regime</span>
                <span className="font-mono text-xs font-bold text-slate-800">{snapshot.market_regime.regime ?? '—'}</span>
              </div>
              <div className="bg-white border border-stone-200 rounded-lg px-4 py-2.5 flex items-center gap-2">
                <span className="text-xs text-stone-600 uppercase tracking-wider">Macro band</span>
                <span className="font-mono text-xs font-bold text-slate-800">{snapshot.market_regime.macro_regime ?? '—'}</span>
              </div>
              {snapshot?.performance?.max_drawdown_pct !== undefined && (
                <div className="bg-white border border-stone-200 rounded-lg px-4 py-2.5 flex items-center gap-2">
                  <span className="text-xs text-stone-600 uppercase tracking-wider">Max drawdown</span>
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
            <div className="text-xs font-semibold uppercase tracking-wider text-stone-700">Monthly Track Record</div>
            <span className="text-xs text-stone-600">
              {hasMonthlyData ? `${MONTHLY_RECORDS.length} month${MONTHLY_RECORDS.length !== 1 ? 's' : ''} reported` : 'Building track record'}
            </span>
          </div>

          {hasMonthlyData ? (
            <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
              <div className="grid grid-cols-[160px_100px_130px_120px_1fr] text-xs font-semibold uppercase tracking-wider text-stone-600 px-5 py-3 border-b border-stone-100 bg-stone-50">
                <span>Month</span>
                <span>Return</span>
                <span>Options Income</span>
                <span>Max Drawdown</span>
                <span>Notes</span>
              </div>
              {MONTHLY_RECORDS.map((r, i) => (
                <div
                  key={r.month}
                  className={`grid grid-cols-[160px_100px_130px_120px_1fr] items-start px-5 py-4 text-sm ${
                    i < MONTHLY_RECORDS.length - 1 ? 'border-b border-stone-100' : ''
                  } ${r.isBaseline ? 'bg-sky-50/40' : ''}`}
                >
                  <span className={`font-semibold ${r.isBaseline ? 'text-sky-800' : 'text-stone-600'}`}>
                    {r.month}
                    {r.isBaseline && (
                      <span className="ml-1.5 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-sky-100 text-sky-600 align-middle">
                        BASELINE
                      </span>
                    )}
                  </span>
                  <span className={`font-mono font-bold ${r.return_pct === null ? 'text-stone-600' : r.return_pct >= 0 ? 'text-green-700' : 'text-red-600'}`}>
                    {r.return_pct === null ? (r.isBaseline ? 'in progress' : '—') : `${r.return_pct >= 0 ? '+' : ''}${r.return_pct.toFixed(2)}%`}
                  </span>
                  <span className={`font-mono text-sm ${r.options_income_pct === null ? 'text-stone-600' : 'text-green-700'}`}>
                    {r.options_income_pct === null ? '—' : `+${r.options_income_pct.toFixed(2)}%`}
                  </span>
                  <span className={`font-mono text-sm ${r.max_drawdown_pct === null ? 'text-stone-600' : 'text-amber-700'}`}>
                    {r.max_drawdown_pct === null ? '—' : `${r.max_drawdown_pct.toFixed(2)}%`}
                  </span>
                  <span className="text-stone-600 text-xs leading-relaxed">{r.notes}</span>
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
                    The system is live. Monthly reports get published here when each period closes. 
                    Return, options income, drawdown, attribution, regime context. The first full 
                    calendar month closes at end of March 2026.
                  </p>
                  <p className="text-sm text-stone-600 leading-relaxed">
                    We're not publishing projected returns or backtests as substitutes. 
                    A track record starts when real money is at risk. Everything before that is fiction.
                  </p>
                </div>
              </div>
            </div>
          )}
        </section>

        <div className="border-t border-stone-200 mb-16" />

        {/* What will be reported — the framework */}
        <section className="mb-16">
          <div className="text-xs font-semibold uppercase tracking-wider text-stone-700 mb-2">Reporting Framework</div>
          <h2 className="font-serif text-2xl font-bold text-slate-900 mb-2">What gets reported and why</h2>
          <p className="text-sm text-stone-600 max-w-2xl mb-8">
            Each monthly report covers six dimensions. The framework is here in advance 
            so you know what you're getting — and what to hold us accountable for.
          </p>

          <div className="space-y-3">
            {REPORTING_FRAMEWORK.map(({ label, desc, accent }) => (
              <div key={label} className={`bg-white border border-stone-200 rounded-xl p-5 border-l-4 ${accent}`}>
                <div className="font-semibold text-sm text-slate-900 mb-1">{label}</div>
                <p className="text-sm text-stone-600 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </section>

        <div className="border-t border-stone-200 mb-16" />

        {/* How to read performance */}
        <section className="mb-16">
          <div className="text-xs font-semibold uppercase tracking-wider text-stone-700 mb-2">Context</div>
          <h2 className="font-serif text-2xl font-bold text-slate-900 mb-6">How to read systematic performance</h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              {
                title: 'Drawdowns happen',
                body: `Every strategy draws down eventually. The question isn't whether it happens (it will) but whether the drawdown is proportionate to the risk taken and whether the system recovers. A 5–8% decline in a month isn't a failure. It's the cost of being invested.`,
              },
              {
                title: 'Slow months get explained',
                body: `Options income dries up when vol collapses. Momentum dies in chop. The regime context explains what the market did and how the portfolio responded. That's the difference between understanding performance and just reacting to it.`,
              },
              {
                title: 'Attribution > total return',
                body: `A 2% month where options made 3% and equities lost 1% is very different from a 2% month driven by one lucky leveraged position. Attribution shows whether the system is working as designed or just getting lucky.`,
              },
              {
                title: 'Compounding beats home runs',
                body: `The goal isn't spectacular single-month returns. It's consistent, compounding gains with controlled risk. 2–3% per month with low drawdowns beats 8% one month and -6% the next, even if the latter sounds more exciting.`,
              },
            ].map(({ title, body }) => (
              <div key={title} className="bg-white border border-stone-200 rounded-xl p-5">
                <div className="font-semibold text-sm text-slate-900 mb-2">{title}</div>
                <p className="text-xs text-stone-600 leading-relaxed">{body}</p>
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
            <p className="text-stone-600 text-sm leading-relaxed mb-6 max-w-xl">
              Subscribers get the full picture: real-time portfolio metrics, trade history, 
              strategy attribution, options income, optimization changes. All of it, updated 
              continuously during market hours.
            </p>
            <div className="flex gap-3">
              <Link
                href="/login"
                className="px-6 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-offset-2 focus:ring-offset-slate-900"
              >
                Open Dashboard
              </Link>
              <Link
                href="/#pricing"
                className="px-6 py-2.5 rounded-xl border border-stone-500 hover:bg-stone-800 text-stone-200 font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-stone-500 focus:ring-offset-2 focus:ring-offset-slate-900"
              >
                View Plans
              </Link>
            </div>
          </div>
        </section>

        {/* Disclaimer */}
        <section>
          <div className="bg-stone-100 border border-stone-200 rounded-xl p-6">
            <div className="text-xs font-semibold uppercase tracking-wider text-stone-700 mb-3">Disclaimer</div>
            <p className="text-xs text-stone-600 leading-relaxed">
              Performance figures represent live system results and are not audited by a third party.
              Past performance does not guarantee future results. Systematic strategies can and do
              underperform. All performance data is reported in good faith and reflects actual
              portfolio activity, including losing periods. Winzinvest is systematic portfolio
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
            <Link href="/"         className="text-sm text-stone-600 hover:text-stone-900 transition-colors">Home</Link>
            <Link href="/methodology"     className="text-sm text-stone-600 hover:text-stone-900 transition-colors">How It Works</Link>
            <Link href="/performance"     className="text-sm text-stone-600 hover:text-stone-900 transition-colors">Performance</Link>
            <Link href="/#pricing" className="text-sm text-stone-600 hover:text-stone-900 transition-colors">Pricing</Link>
            <Link href="/login"           className="text-sm text-stone-600 hover:text-stone-900 transition-colors">Log In</Link>
          </div>
        </div>
        <p className="text-xs text-stone-600 leading-relaxed max-w-3xl">
          Winzinvest is systematic portfolio automation software. It does not provide investment advice.
          Past performance does not guarantee future results. Investing involves substantial risk of loss.
        </p>
      </footer>
    </div>
  );
}
