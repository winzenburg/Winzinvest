'use client';

/**
 * Landing page — follows 010-mission-control-design-system.mdc
 *
 * Typography:  Playfair Display (serif) for headlines + metric values
 *              Inter (sans-serif) for body, labels, UI
 *              JetBrains Mono for precision data
 * Color:       bg-stone-50 page · bg-white cards · border-stone-200
 *              text-slate-900 primary · text-stone-600 secondary · text-stone-400 tertiary
 *              text-sky-600 primary accent (actions, highlights)
 *              green-600 = profit · red-600 = loss
 * Cards:       bg-white border border-stone-200 rounded-xl p-6 hover:shadow-lg
 * Metric vals: font-serif text-4xl font-bold (rule 118–119)
 * Section hdrs: text-xs font-semibold uppercase tracking-wider text-stone-500 (rule 118)
 */

import Link from 'next/link';
import { useState } from 'react';

const STATS = [
  { label: 'Annualized Return', value: '42.4%',  sub: '2-year backtest',    color: 'text-green-600' },
  { label: 'Sharpe Ratio',      value: '4.03',   sub: 'Risk-adjusted',      color: 'text-sky-600'   },
  { label: 'Max Drawdown',      value: '12.6%',  sub: 'Capital preserved',  color: 'text-orange-500'},
  { label: 'Options Run Rate',  value: '$8,600', sub: 'Monthly premium',    color: 'text-sky-600'   },
];

const FEATURES = [
  {
    accentClass: 'border-l-sky-600',
    title: 'Fully Automated Execution',
    body: 'Every entry, exit, roll, and reopen is formula-driven through IBKR. Zero discretionary override at the moment of trade — the leading cause of retail underperformance is architecturally impossible.',
  },
  {
    accentClass: 'border-l-green-600',
    title: 'Options Income Overlay',
    body: 'Covered calls and CSPs layer income on top of equity positions. At scale: $8–10K/month in premium income regardless of market direction. Additive to equity returns, running on autopilot.',
  },
  {
    accentClass: 'border-l-sky-600',
    title: 'Dual-Layer Regime Intelligence',
    body: 'Two classifiers run twice daily. The execution regime (SPY/VIX) gates which strategies run. The macro band (5-indicator score) adjusts position sizing. Together they kept max drawdown under 13%.',
  },
  {
    accentClass: 'border-l-green-600',
    title: 'PROFIT_ROLL — Continuous Compounding',
    body: 'At 80% premium decay, a position closes and immediately reopens at a fresh 35-day strike. Each position generates 1.2–1.5× the premium of a hold-to-expiry approach over a full year.',
  },
  {
    accentClass: 'border-l-orange-500',
    title: 'Institutional Risk Stack',
    body: 'Seven execution gates on every order. Three-tier drawdown circuit breaker. Dividend guards, earnings blackouts, 30% sector caps, correlation monitoring, PIN-protected kill switch.',
  },
  {
    accentClass: 'border-l-sky-600',
    title: 'Self-Optimizing Parameters',
    body: 'Every Friday: 80 parameter combinations tested across top 10 holdings, ranked by Sharpe. OTM%, DTE, and profit-take threshold update automatically. The system gets better each week.',
  },
];

const COMPARISON: [string, string, string, string, string, string][] = [
  ['Fully automated execution',                '✓', '✗ Alerts only', '✗ Visual drag', '✗ Manual',   '~ Code required'],
  ['Options income overlay',                   '✓', '✗',             '✗',             '✓ Manual',   '~ Limited'],
  ['Regime-aware strategy gating',             '✓', '~ Basic',       '✗',             '✗',          '~ Custom'],
  ['Multi-strategy (momentum + MR + options)', '✓', '✗',             '~ Limited',     '✗',          '✓'],
  ['Portfolio Margin aware',                   '✓', '✗',             '✗',             '✗',          '✗'],
  ['Dividend & earnings protection',           '✓', '✗',             '✗',             '~ Manual',   '~ Custom'],
  ['Automated tax-loss harvesting',            '✓', '✗',             '✗',             '✗',          '✗'],
  ['Self-optimizing parameters',               '✓', '✗',             '✗',             '✗',          '~ Manual'],
  ['Audit trail + kill switch',                '✓', '✗',             '~ Limited',     '✗',          '~ Custom'],
  ['Backtest Sharpe ratio',                    '4.03', 'N/A',         'N/A',           'N/A',        'Varies'],
];

const WHY = [
  { num: '01', title: 'Two income streams that complement each other', body: 'Equity momentum profits from price trends. Options premium profits from time decay. In sideways markets where momentum slows, options income accelerates — they are natural complements.' },
  { num: '02', title: 'Graduated risk — not binary', body: 'The circuit breaker steps down: 50% size → halt entries → full stop. It stays operational through normal volatility rather than killing itself on a bad hour.' },
  { num: '03', title: 'Emotion is architecturally impossible', body: 'All entries, exits, rolls, and stops are formula-driven. No override at the moment of trade. This eliminates the #1 documented cause of retail underperformance.' },
  { num: '04', title: 'Premium compounds with scale, not effort', body: 'Each new position becomes a covered call candidate. Each call rolls itself at 80% decay. Adding capital increases income without adding management burden.' },
  { num: '05', title: 'Dividend yield is protected, not surrendered', body: 'The dividend guard prevents writing a call whose premium is less than the upcoming dividend — protecting yield from energy holdings like MPC, COP, OXY, VLO.' },
  { num: '06', title: 'The system gets smarter every week', body: 'The Friday backtest sweep tests 80 combinations against live holdings and updates optimal settings automatically. Longer runtime = better calibration.' },
];

export default function LandingPage() {
  const [tab, setTab] = useState<'2yr' | '3yr'>('2yr');
  const perf = tab === '2yr'
    ? { ret: '42.4%', sharpe: '4.03', dd: '12.6%', equity: '$152,326', trades: '588',   wr: '47.1%' }
    : { ret: '37.8%', sharpe: '4.01', dd: '7.1%',  equity: '$201,501', trades: '1,146', wr: '48.2%' };

  return (
    <div className="min-h-screen bg-stone-50">

      {/* Nav */}
      <nav className="sticky top-0 z-50 bg-white border-b border-stone-200">
        <div className="max-w-7xl mx-auto px-8 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-green-500" />
            <span className="font-serif font-bold text-slate-900 tracking-tight">Winz<span className="text-sky-600">invest</span></span>
          </div>
          <div className="hidden sm:flex items-center gap-8">
            <a href="#performance" className="text-sm text-stone-600 hover:text-slate-900 transition-colors">Performance</a>
            <a href="#how-it-works" className="text-sm text-stone-600 hover:text-slate-900 transition-colors">How It Works</a>
            <a href="#vs-alternatives" className="text-sm text-stone-600 hover:text-slate-900 transition-colors">Comparison</a>
            <Link
              href="/login"
              className="px-4 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-700 text-white text-sm font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-sky-600 focus:ring-offset-2"
            >
              Open Dashboard →
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-7xl mx-auto px-8 pt-20 pb-16">
        <div className="max-w-2xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-stone-200 bg-white text-xs font-semibold text-stone-500 uppercase tracking-wider mb-8">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
            Live Account · IBKR Portfolio Margin · Fully Automated
          </div>

          <h1 className="font-serif text-5xl font-bold text-slate-900 leading-tight tracking-tight mb-5">
            Institutional infrastructure.<br />
            <span className="text-sky-600">Retail simplicity.</span>
          </h1>

          <p className="text-base text-stone-600 leading-relaxed mb-8 max-w-xl">
            A fully automated, regime-aware trading system running equity momentum, options premium income,
            mean reversion, and pairs strategies in parallel — without a single discretionary trade.
          </p>

          <div className="flex gap-3 mb-16">
            <Link
              href="/login"
              className="px-6 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-700 text-white font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-sky-600 focus:ring-offset-2"
            >
              Open Dashboard →
            </Link>
            <Link
              href="/strategy"
              className="px-6 py-2.5 rounded-xl border border-stone-200 bg-white hover:bg-stone-50 text-slate-900 font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2"
            >
              Read the Strategy
            </Link>
          </div>

          {/* Stat cards — rule 118-119 metric card pattern */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {STATS.map(({ label, value, sub, color }) => (
              <div key={label} className="bg-white border border-stone-200 rounded-xl p-5 hover:shadow-lg transition-shadow">
                <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">{label}</div>
                <div className={`font-serif text-4xl font-bold ${color}`}>{value}</div>
                <div className="text-xs text-stone-400 mt-1">{sub}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="border-t border-stone-200" />

      {/* Performance */}
      <section id="performance" className="max-w-7xl mx-auto px-8 py-16">
        <div className="mb-8">
          <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">Backtest Performance</div>
          <h2 className="font-serif text-3xl font-bold text-slate-900 mb-1">Built on real data. No look-ahead.</h2>
          <p className="text-sm text-stone-500">200-symbol universe · Starting equity $100,000 · Hybrid screener + options income overlay</p>
        </div>

        <div className="flex gap-2 mb-6">
          {(['2yr', '3yr'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-1.5 rounded-lg text-xs font-semibold border transition-colors focus:outline-none focus:ring-2 focus:ring-sky-600 focus:ring-offset-2 ${
                tab === t
                  ? 'bg-slate-900 text-white border-slate-900'
                  : 'bg-white text-stone-600 border-stone-200 hover:bg-stone-50'
              }`}
            >
              {t === '2yr' ? '2-Year' : '3-Year (Robustness)'}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {[
            { label: 'Annualized Return', value: perf.ret,    color: 'text-green-600' },
            { label: 'Sharpe Ratio',      value: perf.sharpe, color: 'text-sky-600'   },
            { label: 'Max Drawdown',      value: perf.dd,     color: 'text-orange-500'},
            { label: 'Ending Equity',     value: perf.equity, color: 'text-slate-900' },
            { label: 'Total Trades',      value: perf.trades, color: 'text-slate-900' },
            { label: 'Win Rate',          value: perf.wr,     color: 'text-slate-900' },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-white border border-stone-200 rounded-xl p-5 hover:shadow-lg transition-shadow">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">{label}</div>
              <div className={`font-serif text-2xl font-bold ${color}`}>{value}</div>
            </div>
          ))}
        </div>
        <p className="text-xs text-stone-400 mt-4">Past performance does not guarantee future results. Backtest uses historical data with no look-ahead bias.</p>
      </section>

      <div className="border-t border-stone-200" />

      {/* How it works */}
      <section id="how-it-works" className="max-w-7xl mx-auto px-8 py-16">
        <div className="mb-10">
          <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">The Engine</div>
          <h2 className="font-serif text-3xl font-bold text-slate-900">Six strategies. One pipeline. Zero manual steps.</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 mb-12">
          {FEATURES.map(({ accentClass, title, body }) => (
            <div key={title} className={`bg-white border border-stone-200 rounded-xl p-6 border-l-4 ${accentClass} hover:shadow-lg transition-shadow`}>
              <h3 className="font-semibold text-slate-900 text-sm mb-2">{title}</h3>
              <p className="text-sm text-stone-600 leading-relaxed">{body}</p>
            </div>
          ))}
        </div>

        {/* Daily schedule */}
        <div className="bg-white border border-stone-200 rounded-xl p-6">
          <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-5">What happens every trading day — automatically</div>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
            {[
              { time: '7:00 AM', label: 'Pre-market',  desc: 'Screeners across 200+ symbols' },
              { time: '7:30 AM', label: 'Open',         desc: 'Execute screener signals' },
              { time: '7:45 AM', label: 'Regime',       desc: 'Both layers evaluated' },
              { time: '8:00 AM', label: 'Options',      desc: 'Covered calls + CSPs' },
              { time: 'Every 30m', label: 'Mgmt loop',  desc: 'Profit-take, roll, alerts' },
              { time: '2:00 PM', label: 'Pre-close',    desc: 'Snapshot + daily report' },
              { time: 'Fri 3PM', label: 'Optimizer',    desc: '80-combo parameter sweep' },
            ].map(({ time, label, desc }, i) => (
              <div key={i} className="bg-stone-50 border border-stone-200 rounded-lg p-3 text-center">
                <div className="font-mono text-xs font-bold text-sky-600 mb-1">{time}</div>
                <div className="text-xs font-semibold text-slate-900 mb-1">{label}</div>
                <div className="text-xs text-stone-500 leading-tight">{desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="border-t border-stone-200" />

      {/* Why it works */}
      <section className="max-w-7xl mx-auto px-8 py-16 bg-stone-50">
        <div className="mb-10">
          <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">The Edge</div>
          <h2 className="font-serif text-3xl font-bold text-slate-900">Why this approach works</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {WHY.map(({ num, title, body }) => (
            <div key={num} className="flex gap-5">
              <span className="font-serif text-3xl font-bold text-stone-200 shrink-0 w-10 leading-none tabular-nums">{num}</span>
              <div>
                <div className="font-semibold text-sm text-slate-900 mb-1.5">{title}</div>
                <p className="text-sm text-stone-600 leading-relaxed">{body}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <div className="border-t border-stone-200" />

      {/* Comparison table */}
      <section id="vs-alternatives" className="max-w-7xl mx-auto px-8 py-16">
        <div className="mb-8">
          <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">Competitive Comparison</div>
          <h2 className="font-serif text-3xl font-bold text-slate-900 mb-2">What retail platforms can&apos;t give you</h2>
          <p className="text-sm text-stone-500 max-w-xl">
            Trade Ideas gives you alerts. Composer gives you visual automation. TastyTrade gives you a platform.
            QuantConnect gives you code. None give you all of this, running live, without manual work each day.
          </p>
        </div>

        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-stone-200">
              <tr>
                <th className="text-left py-3 px-4 font-semibold text-stone-600 w-[35%]">Feature</th>
                <th className="py-3 px-3 text-center font-semibold text-sky-600">Winzinvest</th>
                <th className="py-3 px-3 text-center font-semibold text-stone-500 text-xs">Trade Ideas</th>
                <th className="py-3 px-3 text-center font-semibold text-stone-500 text-xs">Composer</th>
                <th className="py-3 px-3 text-center font-semibold text-stone-500 text-xs">TastyTrade</th>
                <th className="py-3 px-3 text-center font-semibold text-stone-500 text-xs">QuantConnect</th>
              </tr>
            </thead>
            <tbody>
              {COMPARISON.map(([feature, mc, ti, comp, tt, qc], i) => (
                <tr key={feature} className={`border-b border-stone-100 hover:bg-stone-50 ${i % 2 === 1 ? 'bg-stone-50/40' : ''}`}>
                  <td className="py-3 px-4 text-slate-900">{feature}</td>
                  {[mc, ti, comp, tt, qc].map((val, j) => (
                    <td key={j} className="py-3 px-3 text-center">
                      <span className={
                        val === '✓' ? 'text-green-600 font-bold text-base'
                      : val === '✗' ? 'text-stone-300 font-bold text-base'
                      : val.startsWith('~') ? 'text-orange-500 text-xs font-semibold'
                      : j === 0 ? 'text-sky-600 font-bold text-sm'
                      : 'text-stone-500 text-xs font-semibold'
                      }>
                        {val}
                      </span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-stone-400 mt-3">✓ native support · ~ partial or with effort · ✗ not available</p>
      </section>

      <div className="border-t border-stone-200" />

      {/* Risk stack */}
      <section className="max-w-7xl mx-auto px-8 py-16">
        <div className="mb-8">
          <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">Risk Management</div>
          <h2 className="font-serif text-3xl font-bold text-slate-900">Institutional-grade protection, built-in</h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {[
            { borderClass: 'border-l-red-600',    title: 'Kill Switch',               desc: 'One-click halt from the dashboard. PIN-protected. Auto-activates at -8% daily drawdown. Blocks all executors until manually cleared.' },
            { borderClass: 'border-l-sky-600',    title: '7-Gate Execution',           desc: 'Every order passes: daily loss · portfolio heat · 6% NLV position cap · 30% sector cap · market hours · symbol validation · per-position concentration.' },
            { borderClass: 'border-l-orange-500', title: 'Graduated Drawdown',         desc: '-3% daily → 50% size reduction. -5% → halt new entries. -8% → kill switch auto-fires. Steps down rather than shuts off entirely.' },
            { borderClass: 'border-l-sky-600',    title: 'Portfolio Margin',           desc: '6–7× risk-based leverage vs 2× Reg T. Meaningfully expands covered call and position capacity without proportionally more risk.' },
            { borderClass: 'border-l-green-600',  title: 'Earnings & Dividend Guards', desc: 'No options within 7 days of earnings. Skips covered calls when dividend > 70% of premium or ex-div is within 5 days of expiry.' },
            { borderClass: 'border-l-sky-600',    title: 'Correlation Monitoring',     desc: 'Live 60-day matrix for top 15 holdings. Average correlation >0.6 flags concentrated risk. Portfolio Margin penalizes correlated books.' },
          ].map(({ borderClass, title, desc }) => (
            <div key={title} className={`bg-white border border-stone-200 rounded-xl p-6 border-l-4 ${borderClass} hover:shadow-lg transition-shadow`}>
              <h3 className="font-semibold text-sm text-slate-900 mb-2">{title}</h3>
              <p className="text-xs text-stone-500 leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      <div className="border-t border-stone-200" />

      {/* CTA */}
      <section className="max-w-7xl mx-auto px-8 py-20">
        <div className="bg-slate-900 rounded-xl p-12 text-center">
          <h2 className="font-serif text-4xl font-bold text-white mb-4">
            Your portfolio.<br />
            <span className="text-sky-400">On autopilot.</span>
          </h2>
          <p className="text-stone-400 text-base leading-relaxed mb-8 max-w-lg mx-auto">
            Institutional infrastructure. Options income compounding daily.
            No discretionary trades. No watching charts. No second-guessing entries.
          </p>
          <Link
            href="/login"
            className="inline-block px-8 py-3 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-bold text-base transition-colors focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-offset-2 focus:ring-offset-slate-900"
          >
            Open Winzinvest →
          </Link>
          <p className="text-stone-600 text-xs mt-6">
            Live IBKR account required · Past performance does not guarantee future results
          </p>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-stone-200 py-8 px-8 max-w-7xl mx-auto">
        <div className="flex items-center justify-between">
          <span className="font-serif font-bold text-stone-500 text-sm">Winzinvest</span>
          <div className="flex gap-6">
            <Link href="/strategy" className="text-sm text-stone-400 hover:text-stone-600 transition-colors">Strategy</Link>
            <Link href="/login"    className="text-sm text-stone-400 hover:text-stone-600 transition-colors">Dashboard</Link>
          </div>
          <p className="text-xs text-stone-400">Not investment advice. Trading involves risk of loss.</p>
        </div>
      </footer>
    </div>
  );
}
