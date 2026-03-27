/**
 * System Overview — formal investor memo format.
 *
 * Purpose:  A shareable, printable document-style page that presents the
 *           Winzinvest system as an institutional fund might present its
 *           strategy to prospective investors. Distinct from /methodology
 *           (process-focused) and /research (academic foundations).
 *
 * Design:   Clean white + slate. Serif-heavy. Document-like.
 *           Looks like something worth printing.
 */

import Link from 'next/link';
import { PublicNav } from '../components/PublicNav';

const PHILOSOPHY_PATTERNS = [
  {
    num: '01',
    title: 'Momentum persists across asset classes and time horizons',
    body: 'Securities that have outperformed recently tend to continue outperforming over intermediate periods. This pattern is one of the most replicated findings in financial research and is observable across equities, fixed income, currencies, and commodities.',
  },
  {
    num: '02',
    title: 'Options markets systematically overprice volatility',
    body: 'Implied volatility consistently exceeds realized volatility on average — a persistent gap that reflects the insurance premium investors pay for risk transfer. Disciplined systematic sellers capture this gap as recurring income.',
  },
  {
    num: '03',
    title: 'Short-term price dislocations revert toward equilibrium',
    body: 'Sharp short-term declines in structurally sound securities are often driven by liquidity flows rather than fundamental deterioration. These dislocations tend to correct quickly, creating systematic entry opportunities with defined risk.',
  },
  {
    num: '04',
    title: 'Market regimes influence which strategies perform best',
    body: 'Different market environments favor different approaches. Momentum performs best in trending markets; mean reversion in volatile, range-bound markets; options premium in stable or moderately volatile conditions. The system adapts to these environments rather than ignoring them.',
  },
];

const STRATEGIES = [
  {
    id: 'momentum',
    number: '1',
    title: 'Momentum Equity Engine',
    subtitle: 'Primary growth component',
    accentClass: 'border-l-sky-600',
    description: 'The core growth engine scans more than 200 equities daily and evaluates each candidate against a composite scoring model. Only securities exceeding a minimum threshold are eligible for entry. Each position carries defined profit targets, stop-losses, and a time limit — ensuring capital is not held in positions that are no longer performing.',
    factors: [
      'Price momentum and trend strength',
      'Relative strength versus the broad market',
      'Bollinger position and RSI dynamics',
      'Structural trend quality and volume characteristics',
    ],
    objective: 'Capture medium-term market trends while limiting exposure duration to weakening positions.',
  },
  {
    id: 'options',
    number: '2',
    title: 'Options Premium Income Overlay',
    subtitle: 'Systematic income generation',
    accentClass: 'border-l-green-600',
    description: 'Options strategies operate on top of the equity portfolio to generate income from two sources. Covered calls are sold against existing long positions when implied volatility and premium levels meet defined criteria. Cash-secured puts are sold on high-quality equity candidates to either collect premium or acquire shares at a discount. When premium decays to approximately 80% of its initial value, positions are closed and reopened at a new strike — maintaining continuous income generation.',
    factors: [
      'Delta-targeted strike selection',
      'Implied volatility rank filters',
      'Dividend and earnings event awareness',
      'Automatic profit-roll on premium decay',
    ],
    objective: 'Generate a recurring income stream that is largely independent of equity price appreciation.',
  },
  {
    id: 'mean-reversion',
    number: '3',
    title: 'Mean Reversion Module',
    subtitle: 'Short-term dislocation capture',
    accentClass: 'border-l-orange-500',
    description: 'Short-term pullbacks in established trends often reverse quickly as forced selling pressure exhausts itself. The system identifies these conditions using short-term momentum indicators and deviation from recent price averages, then enters positions with tight stop-losses and predefined profit targets. Positions are held briefly — days, not weeks.',
    factors: [
      'Short-term RSI at extreme oversold levels',
      'Deviation from recent price averages',
      'Structural support confirmation',
      'Long-term trend filter (position must be above 200-day average)',
    ],
    objective: 'Capture volatility-driven dislocations in structurally sound securities without extended capital exposure.',
  },
  {
    id: 'pairs',
    number: '4',
    title: 'Pairs Trading',
    subtitle: 'Market-neutral return stream',
    accentClass: 'border-l-purple-600',
    description: 'The pairs module introduces a market-neutral element by identifying historically correlated securities and monitoring their price relationship. When a spread diverges significantly from its historical norm, the system enters offsetting long and short positions. The trade exits once the spread reverts toward equilibrium.',
    factors: [
      'Historically correlated pairs within sectors',
      'Statistical divergence threshold for entry',
      'Defined stop-loss per leg',
      'Time-based exit to limit exposure duration',
    ],
    objective: 'Produce returns that are less dependent on overall market direction, reducing portfolio sensitivity to broad market moves.',
  },
];

const RISK_LAYERS = [
  {
    title: 'Drawdown circuit breaker',
    desc: 'A three-tier graduated response reduces portfolio activity as drawdowns develop. Moderate losses trigger reduced position sizes. Larger losses halt new entries. Severe losses activate a full system pause. This progressive mechanism allows the portfolio to remain operational through normal volatility while providing meaningful protection during genuine distress.',
    accent: 'border-t-red-500',
  },
  {
    title: 'Execution gates',
    desc: 'Every order must pass a set of pre-execution checks: portfolio heat limits, position size constraints (no single position exceeds a defined percentage of the portfolio), sector concentration limits, symbol validation, and market hours restrictions. A position that would violate any constraint is not executed, regardless of the opportunity.',
    accent: 'border-t-sky-600',
  },
  {
    title: 'Event-based protection',
    desc: 'Before initiating options positions, the system checks for upcoming earnings announcements and ex-dividend dates that could introduce material assignment risk. Positions are avoided when these events could adversely affect trade outcomes.',
    accent: 'border-t-amber-500',
  },
  {
    title: 'Portfolio diversification monitoring',
    desc: 'Sector exposure and rolling correlations between holdings are continuously evaluated. When correlations rise above acceptable thresholds, the system reduces concentration risk to maintain portfolio resilience across different market scenarios.',
    accent: 'border-t-green-600',
  },
];

type PageProps = {
  params?: Promise<Record<string, string | string[]>>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default function OverviewPage(_props: PageProps) {
  const today = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

  return (
    <div className="min-h-screen bg-white">

      <PublicNav />

      {/* Document body */}
      <div className="max-w-4xl mx-auto px-8 py-16 print:py-8 print:px-0">

        {/* Document header — memo style */}
        <header className="mb-16 pb-8 border-b border-stone-300">
          <div className="flex items-start justify-between mb-8">
            <div>
              <div className="font-serif font-bold text-slate-900 text-lg tracking-tight mb-1">
                Winz<span className="text-sky-600">invest</span>
              </div>
              <div className="text-xs text-stone-400 uppercase tracking-widest">Systematic Portfolio Automation</div>
            </div>
            <div className="text-right hidden sm:block">
              <div className="text-xs text-stone-400 uppercase tracking-widest mb-1">System Overview</div>
              <div className="text-xs text-stone-400">{today}</div>
            </div>
          </div>

          <h1 className="font-serif text-5xl font-bold text-slate-900 leading-tight tracking-tight mb-6">
            Automated Portfolio Infrastructure<br />
            <span className="text-sky-600">for Self-Directed Investors</span>
          </h1>

          <p className="text-base text-stone-600 leading-relaxed max-w-2xl mb-5">
            Winzinvest is a systematic portfolio automation platform designed to manage
            three complementary return streams — momentum-driven equity exposure, options
            premium income, and regime-aware risk management — within a single automated framework.
          </p>

          <p className="text-sm text-stone-500 leading-relaxed max-w-2xl border-l-4 border-stone-200 pl-4 italic">
            The objective is not to forecast markets, but to systematically participate in them
            with consistency, transparency, and discipline.
          </p>

          {/* Quick reference strip */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-10">
            {[
              { label: 'Strategy count', value: '4 coordinated' },
              { label: 'Regime layers',  value: '2 independent' },
              { label: 'Risk tiers',     value: '3 graduated' },
              { label: 'Execution',      value: 'Fully automated' },
            ].map(({ label, value }) => (
              <div key={label} className="bg-stone-50 border border-stone-200 rounded-lg p-4">
                <div className="text-xs text-stone-400 uppercase tracking-wider mb-1">{label}</div>
                <div className="font-semibold text-sm text-slate-900">{value}</div>
              </div>
            ))}
          </div>
        </header>

        {/* Section 1: Investment Philosophy */}
        <section className="mb-16">
          <h2 className="font-serif text-2xl font-bold text-slate-900 mb-2">Investment Philosophy</h2>
          <div className="w-10 h-0.5 bg-sky-600 mb-6" />

          <p className="text-sm text-stone-600 leading-relaxed mb-8">
            Markets exhibit several structural patterns that can be systematically captured.
            Winzinvest is built around four of these characteristics, selecting strategies
            that exploit each while remaining complementary under different market conditions.
          </p>

          <div className="space-y-0 border border-stone-200 rounded-xl overflow-hidden">
            {PHILOSOPHY_PATTERNS.map(({ num, title, body }, i) => (
              <div
                key={num}
                className={`p-6 flex gap-6 ${i < PHILOSOPHY_PATTERNS.length - 1 ? 'border-b border-stone-200' : ''}`}
              >
                <span className="font-serif text-2xl font-bold text-stone-200 shrink-0 w-8 leading-none tabular-nums pt-0.5">
                  {num}
                </span>
                <div>
                  <div className="font-semibold text-sm text-slate-900 mb-1.5">{title}</div>
                  <p className="text-sm text-stone-600 leading-relaxed">{body}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 bg-stone-50 border border-stone-200 rounded-xl p-5">
            <p className="text-sm text-stone-700 leading-relaxed">
              <strong>Core portfolio design principle:</strong> A portfolio with multiple independent
              return drivers can achieve more stable performance than any single strategy alone.
              Winzinvest integrates strategies that tend to perform well under different market
              conditions, reducing dependence on any single environment.
            </p>
          </div>
        </section>

        <div className="border-t border-stone-200 mb-16" />

        {/* Section 2: Strategy Architecture */}
        <section className="mb-16">
          <h2 className="font-serif text-2xl font-bold text-slate-900 mb-2">Strategy Architecture</h2>
          <div className="w-10 h-0.5 bg-sky-600 mb-6" />
          <p className="text-sm text-stone-600 leading-relaxed mb-8">
            Four rule-based strategies operate within a single coordinated automation framework.
            Each strategy has its own logic, entry criteria, and exit rules — but they share a
            common risk framework and respond to the same regime classification system.
          </p>

          <div className="space-y-6">
            {STRATEGIES.map((s) => (
              <div key={s.id} className={`bg-white border border-stone-200 rounded-xl overflow-hidden border-l-4 ${s.accentClass}`}>
                <div className="p-6">
                  <div className="flex items-center gap-3 mb-3">
                    <span className="font-serif text-lg font-bold text-stone-300 tabular-nums">{s.number}</span>
                    <div>
                      <div className="font-semibold text-slate-900 text-sm">{s.title}</div>
                      <div className="text-xs text-stone-400 uppercase tracking-wider">{s.subtitle}</div>
                    </div>
                  </div>

                  <p className="text-sm text-stone-600 leading-relaxed mb-4">{s.description}</p>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-wider text-stone-400 mb-2">Evaluation factors</div>
                      <ul className="space-y-1">
                        {s.factors.map((f) => (
                          <li key={f} className="flex items-start gap-2 text-xs text-stone-500">
                            <span className="shrink-0 mt-1 w-1 h-1 rounded-full bg-stone-300" />
                            {f}
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div className="bg-stone-50 border border-stone-200 rounded-lg p-3">
                      <div className="text-xs font-semibold uppercase tracking-wider text-stone-400 mb-1">Objective</div>
                      <p className="text-xs text-stone-600 leading-relaxed">{s.objective}</p>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        <div className="border-t border-stone-200 mb-16" />

        {/* Section 3: Regime Detection */}
        <section className="mb-16">
          <h2 className="font-serif text-2xl font-bold text-slate-900 mb-2">Regime Detection</h2>
          <div className="w-10 h-0.5 bg-sky-600 mb-6" />

          <p className="text-sm text-stone-600 leading-relaxed mb-8">
            Different strategies perform differently under various market conditions. Winzinvest
            employs two independent regime classification layers that operate simultaneously,
            each serving a distinct purpose.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {[
              {
                title: 'Execution Regime',
                tag: 'Layer 1',
                accent: 'border-t-sky-600',
                desc: 'Determines which strategies are permitted to operate. Evaluated using the market\'s position relative to long-term moving averages, current volatility conditions, and structural trend indicators. When the regime changes, strategy activation and allocation adjust automatically.',
                states: ['Strong uptrend', 'Choppy market', 'Mixed conditions', 'Downtrend', 'Unfavorable'],
                stateLabel: 'Possible states',
              },
              {
                title: 'Macro Regime Band',
                tag: 'Layer 2',
                accent: 'border-t-orange-500',
                desc: 'Does not gate strategies — instead adjusts position sizing and entry thresholds. Evaluates broader market stress using credit spreads, volatility structure, real yields, and financial conditions indices. As stress rises, the system gradually reduces exposure and tightens criteria.',
                states: ['Risk-on (full size)', 'Neutral (reduced)', 'Tightening (cautious)', 'Defensive (minimal)'],
                stateLabel: 'Sizing bands',
              },
            ].map(({ title, tag, accent, desc, states, stateLabel }) => (
              <div key={title} className={`bg-white border border-stone-200 rounded-xl p-6 border-t-4 ${accent}`}>
                <div className="flex items-center gap-2 mb-4">
                  <span className="text-xs font-semibold uppercase tracking-wider text-stone-400 bg-stone-100 px-2 py-0.5 rounded">{tag}</span>
                  <span className="font-semibold text-sm text-slate-900">{title}</span>
                </div>
                <p className="text-sm text-stone-600 leading-relaxed mb-4">{desc}</p>
                <div className="text-xs font-semibold uppercase tracking-wider text-stone-400 mb-2">{stateLabel}</div>
                <div className="space-y-1">
                  {states.map((s) => (
                    <div key={s} className="flex items-center gap-2 text-xs text-stone-500">
                      <span className="w-1 h-1 rounded-full bg-stone-300 shrink-0" />
                      {s}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        <div className="border-t border-stone-200 mb-16" />

        {/* Section 4: Risk Management */}
        <section className="mb-16">
          <h2 className="font-serif text-2xl font-bold text-slate-900 mb-2">Risk Management Framework</h2>
          <div className="w-10 h-0.5 bg-sky-600 mb-6" />

          <p className="text-sm text-stone-600 leading-relaxed mb-8">
            Risk control is central to the design of the system. Every portfolio decision passes
            through multiple layers of constraints before it reaches the brokerage account. These
            constraints are structural — they cannot be bypassed at the moment of execution.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {RISK_LAYERS.map(({ title, desc, accent }) => (
              <div key={title} className={`bg-white border border-stone-200 rounded-xl p-5 border-t-4 ${accent}`}>
                <div className="font-semibold text-sm text-slate-900 mb-2">{title}</div>
                <p className="text-xs text-stone-500 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </section>

        <div className="border-t border-stone-200 mb-16" />

        {/* Section 5: Daily Operations */}
        <section className="mb-16">
          <h2 className="font-serif text-2xl font-bold text-slate-900 mb-2">Automation Infrastructure</h2>
          <div className="w-10 h-0.5 bg-sky-600 mb-6" />

          <p className="text-sm text-stone-600 leading-relaxed mb-8">
            All system operations follow a structured daily schedule. The platform operates
            consistently without requiring manual oversight — every process runs automatically,
            at defined times, following defined rules.
          </p>

          <div className="border border-stone-200 rounded-xl overflow-hidden">
            {[
              { phase: 'Pre-market',           desc: 'Equity universe screening, signal generation, portfolio review' },
              { phase: 'Market open',           desc: 'Execution of prepared equity signals, portfolio adjustments' },
              { phase: 'Options management',    desc: 'Income position scanning, new positions opened where criteria are met' },
              { phase: 'Continuous monitoring', desc: 'Open positions tracked against profit targets, stops, and time limits' },
              { phase: 'Midday regime check',   desc: 'Both classification layers re-evaluated with current market data' },
              { phase: 'End of day',            desc: 'Portfolio snapshot, daily reporting, risk metric logging' },
              { phase: 'Weekly (Friday)',        desc: 'Parameter optimization sweep across current holdings, Sharpe-ranked results' },
            ].map(({ phase, desc }, i, arr) => (
              <div
                key={phase}
                className={`flex items-start gap-5 px-5 py-3.5 ${i < arr.length - 1 ? 'border-b border-stone-100' : ''} ${i % 2 === 0 ? 'bg-white' : 'bg-stone-50'}`}
              >
                <span className="text-xs font-semibold text-sky-600 w-36 shrink-0 pt-0.5 uppercase tracking-wide">{phase}</span>
                <span className="text-sm text-stone-600">{desc}</span>
              </div>
            ))}
          </div>
        </section>

        <div className="border-t border-stone-200 mb-16" />

        {/* Section 6: Intended Users */}
        <section className="mb-16">
          <h2 className="font-serif text-2xl font-bold text-slate-900 mb-2">Intended Users</h2>
          <div className="w-10 h-0.5 bg-sky-600 mb-6" />

          <p className="text-sm text-stone-600 leading-relaxed mb-6">
            Winzinvest is designed for experienced self-directed investors who want to automate
            disciplined portfolio management. The platform may be particularly relevant for:
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[
              { title: 'Portfolio scale', body: 'Investors managing six- or seven-figure portfolios where systematic options income generates meaningful, recurring returns.' },
              { title: 'Options traders', body: 'Investors already running covered calls or cash-secured puts manually who want systematic execution, discipline, and scale.' },
              { title: 'Professionals seeking automation', body: 'Investors who have sound portfolio instincts but lack the bandwidth for consistent daily execution.' },
              { title: 'Systematic-minded investors', body: 'Investors interested in rules-based approaches but without the engineering resources to build and maintain the infrastructure themselves.' },
            ].map(({ title, body }) => (
              <div key={title} className="flex gap-4 bg-stone-50 border border-stone-200 rounded-xl p-4">
                <span className="text-sky-600 font-bold shrink-0 mt-0.5 text-sm">—</span>
                <div>
                  <div className="font-semibold text-sm text-slate-900 mb-1">{title}</div>
                  <p className="text-xs text-stone-500 leading-relaxed">{body}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        <div className="border-t border-stone-200 mb-16" />

        {/* Conclusion */}
        <section className="mb-16">
          <h2 className="font-serif text-2xl font-bold text-slate-900 mb-2">Conclusion</h2>
          <div className="w-10 h-0.5 bg-sky-600 mb-6" />

          <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
            <p>
              Winzinvest is designed as an automated portfolio operating system rather than a
              traditional trading tool. By integrating momentum strategies, options income,
              mean reversion, and regime-aware risk management within a single automated framework,
              the platform provides a disciplined and scalable approach to portfolio management.
            </p>
            <p>
              While no strategy can eliminate risk, the structured design of the system seeks to
              combine multiple independent return drivers with robust risk controls. The portfolio
              is designed to remain resilient across changing market environments rather than
              depending on any single condition for its performance.
            </p>
          </div>

          {/* Conclusion pull quote */}
          <div className="mt-8 bg-slate-900 rounded-xl p-8">
            <p className="font-serif text-xl font-bold text-white leading-snug mb-3">
              &ldquo;The objective is not to forecast markets, but to systematically participate
              in them with consistency, transparency, and discipline.&rdquo;
            </p>
            <p className="text-xs text-stone-400 uppercase tracking-wider">Winzinvest System Design Principle</p>
          </div>
        </section>

        {/* Disclaimer */}
        <section className="mb-12">
          <div className="border border-stone-200 rounded-xl p-6 bg-stone-50">
            <div className="text-xs font-semibold uppercase tracking-wider text-stone-400 mb-3">Important Disclaimer</div>
            <div className="space-y-2 text-xs text-stone-500 leading-relaxed">
              <p>
                Trading equities and options involves substantial risk of loss. Past performance,
                including backtested results, does not guarantee future outcomes. Systematic strategies
                can and do underperform — in some market environments, losses may be material.
              </p>
              <p>
                Winzinvest provides systematic portfolio automation software and analytical tools.
                It does not provide investment advice, portfolio management services, or
                recommendations of any kind. All strategy parameters and risk tolerances are
                determined by the investor. Investors should carefully evaluate their own financial
                circumstances and risk tolerance before using any automated investment system.
              </p>
              <p>
                Brokerage account required for automated execution (Interactive Brokers supported today; Tastytrade coming Q2 2026).
                Portfolio Margin access is available but not required.
              </p>
            </div>
          </div>
        </section>

        {/* Footer navigation — not shown when printing */}
        <div className="border-t border-stone-200 pt-10 print:hidden">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-5">
            <div>
              <div className="font-serif font-bold text-slate-900 text-sm mb-1">
                Winz<span className="text-sky-600">invest</span>
              </div>
              <p className="text-xs text-stone-400">Systematic portfolio automation software.</p>
            </div>
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              <Link href="/"         className="text-sm text-stone-400 hover:text-slate-900 transition-colors">Home</Link>
              <Link href="/methodology"     className="text-sm text-stone-400 hover:text-slate-900 transition-colors">How It Works</Link>
              <Link href="/performance"     className="text-sm text-stone-400 hover:text-slate-900 transition-colors">Performance</Link>
              <Link href="/#pricing" className="text-sm text-stone-400 hover:text-slate-900 transition-colors">Pricing</Link>
              <Link href="/login"           className="text-sm text-stone-400 hover:text-slate-900 transition-colors">Log In</Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
