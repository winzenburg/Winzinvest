'use client';

/**
 * Research page — QuantConnect-style transparency + Option Alpha-style education.
 *
 * Purpose:  Show the academic and empirical foundations behind each subsystem.
 *           Builds trust by explaining *why* each approach was chosen, grounding
 *           claims in published research and institutional practice rather than
 *           marketing language.
 *
 * Voice:    Educational. Cites concepts, not specific papers (to avoid going
 *           stale). Assumes the reader is intelligent but may not be a quant.
 *
 * Category: "Systematic portfolio automation" throughout.
 */

import Link from 'next/link';
import { use } from 'react';
import { PublicNav } from '../components/PublicNav';

const SECTIONS = [
  { id: 'momentum',     label: 'Momentum Factor' },
  { id: 'mean-rev',     label: 'Mean Reversion' },
  { id: 'options',      label: 'Options Premium' },
  { id: 'regime',       label: 'Regime Classification' },
  { id: 'optimization', label: 'Parameter Optimization' },
  { id: 'behavior',     label: 'Behavioral Foundation' },
  { id: 'transparency', label: 'System Transparency' },
];

type PageProps = {
  params?: Promise<Record<string, string | string[]>>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

const EMPTY = Promise.resolve({});

export default function ResearchPage(props: PageProps) {
  use(props.params ?? EMPTY);
  use(props.searchParams ?? EMPTY);
  return (
    <div className="min-h-screen bg-stone-50">

      <PublicNav />

      <div className="max-w-7xl mx-auto px-8 py-16">
        <div className="grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-12">

          {/* Sidebar */}
          <aside className="hidden lg:block">
            <div className="sticky top-24">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-4">Research Topics</div>
              <nav className="space-y-1.5">
                {SECTIONS.map(({ id, label }) => (
                  <a
                    key={id}
                    href={`#${id}`}
                    className="block text-sm text-stone-500 hover:text-sky-600 transition-colors py-1"
                  >
                    {label}
                  </a>
                ))}
              </nav>
            </div>
          </aside>

          {/* Main content */}
          <main className="max-w-3xl">

            {/* Header */}
            <header className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-3">Research &amp; System Design</div>
              <h1 className="font-serif text-4xl font-bold text-slate-900 leading-tight tracking-tight mb-5">
                The foundations behind the system
              </h1>
              <p className="text-base text-stone-600 leading-relaxed max-w-2xl mb-4">
                Every component of Winzinvest is grounded in established financial research and
                institutional practice. This page explains the academic and empirical basis for
                each subsystem — not to prove the system is infallible, but to demonstrate that
                the approach is thoughtful, well-founded, and transparent.
              </p>
              <p className="text-sm text-stone-500 leading-relaxed max-w-2xl">
                We believe investors make better decisions when they understand how their
                portfolio is being managed and why. This is our contribution to that understanding.
              </p>
            </header>

            {/* 1. Momentum Factor */}
            <section id="momentum" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">Equity Strategies</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">The momentum factor</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  The momentum factor is one of the most robust and well-documented anomalies in
                  financial markets. Securities that have performed well over the past 3 to 12 months
                  tend to continue outperforming over subsequent periods. This pattern has been
                  observed across asset classes, geographies, and time periods spanning more than
                  a century of market data.
                </p>
                <p>
                  The academic literature on momentum is extensive. Jegadeesh and Titman&apos;s
                  foundational work in the early 1990s documented cross-sectional momentum
                  in U.S. equities. Subsequent research by Asness, Moskowitz, and Pedersen
                  demonstrated that momentum exists in global equities, fixed income,
                  currencies, and commodities. The factor has survived multiple market cycles,
                  including periods that challenged other well-known anomalies.
                </p>
                <p>
                  The behavioral explanation is straightforward: investors tend to underreact
                  to new information initially, then overreact as trends become obvious.
                  Momentum strategies capture this intermediate phase — after the initial
                  underreaction but before the eventual overreaction.
                </p>
              </div>

              <div className="bg-white border border-stone-200 rounded-xl p-6 mt-8">
                <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-4">How Winzinvest implements momentum</div>
                <div className="space-y-3 text-sm text-stone-600 leading-relaxed">
                  <p>
                    The platform uses a composite scoring model that evaluates multiple dimensions
                    of momentum simultaneously: price trend strength, relative performance versus
                    the broad market, volatility structure, and volume characteristics. This
                    multi-factor approach is more robust than single-indicator momentum because
                    it reduces the probability of false signals.
                  </p>
                  <p>
                    Positions are sized based on each security&apos;s volatility, ensuring that
                    higher-risk opportunities receive proportionally smaller allocations. Every
                    position includes a defined profit target and stop-loss from entry, removing
                    the subjectivity that typically degrades momentum strategy performance in
                    practice.
                  </p>
                </div>
              </div>
            </section>

            <div className="border-t border-stone-200 mb-16" />

            {/* 2. Mean Reversion */}
            <section id="mean-rev" className="mb-16">
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">Short-term mean reversion</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  While momentum captures intermediate-term trends, mean reversion captures
                  the opposite pattern at shorter time horizons. Securities that experience
                  sharp short-term declines while remaining in a longer-term uptrend tend
                  to recover quickly. This pattern is driven by liquidity-driven overselling,
                  institutional rebalancing flows, and the gap between short-term price impact
                  and underlying value.
                </p>
                <p>
                  Research by Connors and others has documented the effectiveness of
                  short-term mean reversion strategies, particularly using RSI-based indicators
                  at very short lookback periods. The key insight is that oversold conditions
                  in structurally sound securities represent forced selling rather than fundamental
                  deterioration — and forced selling creates opportunities for systematic buyers.
                </p>
                <p>
                  The platform applies this research through a strategy that identifies
                  deeply oversold conditions in securities that remain above their long-term
                  trend. Positions are held for days, not weeks, with tight risk parameters.
                  This short holding period limits exposure to fundamental risk while capturing
                  the statistical tendency toward recovery.
                </p>
              </div>

              <div className="bg-slate-900 rounded-xl p-6 mt-8">
                <div className="text-xs font-semibold uppercase tracking-wider text-sky-400 mb-4">
                  Why momentum and mean reversion complement each other
                </div>
                <div className="space-y-3">
                  {[
                    'Momentum captures intermediate-term trends (weeks to months). Mean reversion captures short-term dislocations (days). They operate on different time horizons and rarely compete for the same positions.',
                    'Momentum tends to perform best in trending markets. Mean reversion tends to perform best in volatile, range-bound markets. Running both strategies together provides returns across a wider range of market conditions.',
                    'The combination reduces the portfolio\'s dependence on any single market environment — a core principle of institutional portfolio construction.',
                  ].map((text, i) => (
                    <div key={i} className="flex items-start gap-3">
                      <span className="w-1 h-1 rounded-full bg-sky-400 shrink-0 mt-2" />
                      <p className="text-sm text-stone-300 leading-relaxed">{text}</p>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            <div className="border-t border-stone-200 mb-16" />

            {/* 3. Options Premium */}
            <section id="options" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">Income Strategies</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">The mechanics of options premium</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  Options premium exists because investors are willing to pay for risk transfer.
                  The buyer of a call option pays a premium in exchange for the right to participate
                  in upside above a defined price. The seller collects that premium in exchange
                  for accepting the obligation. This transfer of risk creates a persistent income
                  stream for the seller — provided the risk is managed appropriately.
                </p>
                <p>
                  The academic basis for systematic options selling is grounded in the
                  <strong> volatility risk premium</strong>: the well-documented tendency for
                  implied volatility to exceed realized volatility over time. In practical terms,
                  options tend to be priced slightly higher than the risk they actually represent.
                  This gap is the structural source of income for disciplined premium sellers.
                </p>
                <p>
                  CBOE research on the BXM (Buy-Write) and PUT (PutWrite) indices has demonstrated
                  that systematic covered call and cash-secured put strategies have produced
                  equity-like returns with meaningfully lower volatility over multi-decade periods.
                  These are not exotic strategies — they are used by pension funds, endowments,
                  and insurance companies as core allocation components.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-8">
                {[
                  {
                    title: 'Covered call mechanics',
                    body: 'When the portfolio owns 100+ shares, writing a call at a strike above the current price generates premium income. If the stock stays below the strike, the premium is kept. If the stock rises above, shares may be called away at a profitable price. The trade-off is capped upside in exchange for immediate income.',
                  },
                  {
                    title: 'Cash-secured put mechanics',
                    body: 'Writing a put at a price below the current market generates premium income for the willingness to buy at that lower price. If the stock stays above the strike, the premium is kept. If it falls below, the portfolio acquires shares at a discount to where they were when the put was written.',
                  },
                  {
                    title: 'Time decay as income',
                    body: 'Options lose value as they approach expiration — a mathematical certainty known as theta decay. The rate of decay accelerates in the final weeks. Systematic sellers capture this decay as recurring income. The platform\'s auto-rolling feature maximizes exposure to the steepest part of the decay curve.',
                  },
                  {
                    title: 'Volatility risk premium',
                    body: 'Implied volatility consistently exceeds realized volatility on average. This gap represents the "insurance premium" that option buyers pay and sellers collect. The premium tends to be largest when fear is elevated — exactly when systematic sellers are compensated most for providing liquidity.',
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

            {/* 4. Regime Classification */}
            <section id="regime" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">Adaptive Framework</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">Regime classification and adaptive allocation</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  Financial markets exhibit distinct behavioral regimes — periods of trending
                  behavior, periods of high volatility, periods of compression, and periods of
                  dislocation. Research by Hamilton, Ang, and others has formalized this observation
                  through regime-switching models that identify transitions between market states.
                </p>
                <p>
                  The practical implication is significant: strategies that perform well in one
                  regime often underperform or increase risk in another. Momentum strategies
                  generate their best returns during trending markets but can produce excessive
                  turnover during choppy conditions. Options premium selling benefits from
                  elevated volatility but faces greater assignment risk during sharp moves.
                </p>
                <p>
                  Winzinvest addresses this through a two-layer regime classification system.
                  The first layer evaluates the broad market trend and volatility environment
                  to determine which strategies should be active. The second layer evaluates
                  a scored composite of five macro stress indicators — VIX term structure, high-yield
                  credit spreads (FRED: BAMLH0A0HYM2), 10-year real yields (FRED: DFII10), the
                  Chicago Fed National Financial Conditions Index (FRED: NFCI), and industrial
                  production as a manufacturing health proxy (FRED: IPMAN) — to adjust position
                  sizing aggressiveness. Together, these layers create an adaptive framework that
                  responds to changing conditions without requiring the investor to interpret market
                  signals manually.
                </p>
              </div>

              <div className="bg-white border border-stone-200 rounded-xl p-6 mt-8">
                <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-4">Design principles for regime detection</div>
                <div className="space-y-3">
                  {[
                    { label: 'Simplicity', desc: 'The regime system uses observable, well-understood indicators — price relative to moving averages, VIX term structure, HY credit spreads, real yields, financial conditions, and industrial production — all sourced from public data (Yahoo Finance and the Federal Reserve FRED API). Complex machine learning models were deliberately avoided because they tend to overfit to recent conditions and fail during novel market events.' },
                    { label: 'Graduated response', desc: 'The system does not operate as a binary switch. It adjusts behavior progressively as conditions change. This avoids the whipsaw problem where rapid regime transitions cause excessive portfolio turnover.' },
                    { label: 'Multiple evaluation points', desc: 'Regimes are evaluated multiple times per trading day rather than once. This allows the portfolio to adapt to intraday shifts in market conditions rather than waiting for end-of-day data.' },
                    { label: 'Independence', desc: 'The two classification layers operate independently. The market trend layer (which strategies are active) and the macro stress layer (how aggressively to invest) can move in different directions, creating a more nuanced response than either layer alone.' },
                  ].map(({ label, desc }) => (
                    <div key={label} className="flex items-start gap-4 pb-3 border-b border-stone-100 last:border-0 last:pb-0">
                      <span className="text-xs font-semibold text-sky-600 uppercase tracking-wider w-28 shrink-0 pt-0.5">{label}</span>
                      <p className="text-sm text-stone-600 leading-relaxed">{desc}</p>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            <div className="border-t border-stone-200 mb-16" />

            {/* 5. Parameter Optimization */}
            <section id="optimization" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">Continuous Improvement</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">Parameter optimization methodology</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  A common criticism of systematic strategies is that they are static — the
                  parameters that worked in backtesting may not work in live markets as
                  conditions evolve. This is a legitimate concern. Markets are non-stationary,
                  and any fixed parameter set will eventually drift from optimality.
                </p>
                <p>
                  Winzinvest addresses this through a weekly recalibration process that
                  evaluates multiple parameter combinations against recent portfolio performance.
                  The system tests different strike distances, holding periods, and profit
                  targets across current holdings, then ranks the results by risk-adjusted
                  performance (Sharpe ratio). The best-performing parameters are adopted for
                  the following week.
                </p>
                <p>
                  This approach is deliberately conservative. The system does not attempt to
                  predict which parameters will work best in the future. It identifies which
                  parameters have been producing the best risk-adjusted results recently and
                  shifts toward them. This is the same kind of rolling parameter review that
                  any professional portfolio management team conducts — the difference is that
                  it happens automatically and without cognitive bias.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-8">
                {[
                  { title: 'Overfitting protection', body: 'The optimization window is deliberately limited to recent months rather than long history. Parameters that only work over very long backtests but fail in recent conditions are not adopted. The system optimizes for recent robustness, not historical perfection.' },
                  { title: 'Risk-adjusted ranking', body: 'Parameters are ranked by Sharpe ratio — return per unit of risk — not by absolute return. This prevents the system from chasing high returns that come with disproportionate risk. A parameter set with modest returns and low drawdowns is preferred over one with high returns and high volatility.' },
                  { title: 'Transparent updates', body: 'Every parameter change is logged with the reasoning: what was tested, what performed best, and what changed. Investors can review the full optimization history through the dashboard audit trail. Nothing happens in a black box.' },
                ].map(({ title, body }) => (
                  <div key={title} className="bg-white border border-stone-200 rounded-xl p-5">
                    <div className="font-semibold text-sm text-slate-900 mb-2">{title}</div>
                    <p className="text-xs text-stone-500 leading-relaxed">{body}</p>
                  </div>
                ))}
              </div>
            </section>

            <div className="border-t border-stone-200 mb-16" />

            {/* 6. Behavioral Foundation */}
            <section id="behavior" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">Core Thesis</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">The behavioral case for automation</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  The strongest argument for systematic portfolio automation is not that
                  algorithms are smarter than humans. It is that they are more consistent.
                </p>
                <p>
                  Behavioral finance research — beginning with Kahneman and Tversky&apos;s work
                  on prospect theory and continuing through decades of subsequent studies — has
                  established that human decision-making under uncertainty is systematically
                  biased. Loss aversion causes investors to hold losing positions too long.
                  Recency bias causes them to chase recent winners. Overconfidence causes them
                  to overtrade. Fear causes them to sell at exactly the wrong time.
                </p>
                <p>
                  These are not character flaws. They are hardwired cognitive patterns that
                  evolved for survival, not for portfolio management. Even experienced investors
                  who understand these biases fall prey to them — intellectual knowledge does not
                  reliably override emotional response when capital is at risk.
                </p>
                <p>
                  Dalbar&apos;s annual Quantitative Analysis of Investor Behavior consistently shows
                  that the average investor underperforms the very funds they invest in by
                  significant margins. The underperformance is not caused by poor fund selection —
                  it is caused by poor timing of entries and exits. Investors buy after rallies
                  and sell after declines, systematically destroying value through behavioral
                  inconsistency.
                </p>
                <p>
                  Automation solves this problem structurally. Once the strategy rules are defined,
                  they are followed with complete consistency regardless of how the investor feels
                  about current market conditions. The system cannot panic during a drawdown,
                  hesitate during an opportunity, or override its own rules out of frustration.
                  This consistency is not a feature of the software — it is the primary source
                  of its value.
                </p>
              </div>
            </section>

            <div className="border-t border-stone-200 mb-16" />

            {/* 7. System Transparency */}
            <section id="transparency" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">Open Architecture</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">System transparency</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  Most portfolio management platforms operate as black boxes. Investors see
                  their returns but have limited visibility into how decisions are made,
                  why specific trades are taken, or how risk is being managed at any given moment.
                  This opacity makes it difficult to evaluate the system, identify problems,
                  or build confidence in the process.
                </p>
                <p>
                  Winzinvest takes the opposite approach. Every aspect of the system is
                  visible to the investor through the dashboard:
                </p>
              </div>

              <div className="space-y-4 mt-8">
                {[
                  {
                    title: 'Complete trade record',
                    body: 'Every position entry, exit, adjustment, and option roll is logged with the timestamp, price, reasoning, and strategy that generated it. The investor can review the complete history of portfolio decisions at any time.',
                    accent: 'border-l-sky-600',
                  },
                  {
                    title: 'Regime status and transitions',
                    body: 'The current market regime classification and every historical transition are visible on the dashboard. Investors can see exactly how the system is interpreting current market conditions and how that interpretation affects portfolio behavior.',
                    accent: 'border-l-sky-600',
                  },
                  {
                    title: 'Risk metrics in real time',
                    body: 'Drawdown levels, sector exposures, position concentrations, and correlation matrices are updated continuously. The investor always knows where the portfolio stands relative to its defined risk limits.',
                    accent: 'border-l-orange-500',
                  },
                  {
                    title: 'Optimization history',
                    body: 'Every parameter update from the weekly optimization process is logged with the full set of tested combinations and results. Investors can see exactly which parameters were changed, why they ranked higher, and how the system arrived at its current configuration.',
                    accent: 'border-l-green-600',
                  },
                  {
                    title: 'System health monitoring',
                    body: 'The platform monitors its own operational health — brokerage connectivity, data feed status, execution latency, and scheduled job completion. Any issue is surfaced immediately through the dashboard and alert system.',
                    accent: 'border-l-sky-600',
                  },
                ].map(({ title, body, accent }) => (
                  <div key={title} className={`bg-white border border-stone-200 rounded-xl p-6 border-l-4 ${accent}`}>
                    <h3 className="font-semibold text-sm text-slate-900 mb-2">{title}</h3>
                    <p className="text-sm text-stone-600 leading-relaxed">{body}</p>
                  </div>
                ))}
              </div>

              <div className="bg-stone-100 border border-stone-200 rounded-xl p-6 mt-8">
                <p className="text-sm text-stone-600 leading-relaxed italic">
                  &ldquo;Here is the machine. You can inspect every part.&rdquo;
                </p>
                <p className="text-xs text-stone-400 mt-3">
                  We believe that transparency is the most effective way to build trust in an
                  automated system. When investors understand exactly how their portfolio is being
                  managed, they can make informed decisions about whether the approach aligns with
                  their goals — and they can monitor the system&apos;s behavior over time with confidence.
                </p>
              </div>
            </section>

            <div className="border-t border-stone-200 mb-16" />

            {/* Disclaimer */}
            <section className="mb-16">
              <div className="bg-white border border-stone-200 rounded-xl p-8">
                <h2 className="font-serif text-xl font-bold text-slate-900 mb-4">Important disclosures</h2>
                <div className="space-y-3 text-sm text-stone-600 leading-relaxed">
                  <p>
                    The research cited on this page is intended to explain the intellectual
                    foundations of the platform&apos;s approach. It does not constitute a guarantee
                    that these strategies will produce positive returns. Academic findings describe
                    historical tendencies, not certainties.
                  </p>
                  <p>
                    Winzinvest is systematic portfolio automation software that executes
                    investor-defined rules. It does not provide investment advice, recommend
                    securities, or manage assets on behalf of investors. All strategy parameters
                    and risk tolerances are determined by the investor.
                  </p>
                  <p>
                    Investing in equities and options involves substantial risk of loss.
                    Systematic strategies can and do underperform. Past performance — whether
                    from backtesting, academic research, or live operation — does not guarantee
                    future results. Options can expire worthless or result in assignment;
                    losses can exceed the premium collected.
                  </p>
                </div>
              </div>
            </section>

            {/* CTA */}
            <div className="bg-slate-900 rounded-xl p-10 text-center">
              <h2 className="font-serif text-2xl font-bold text-white mb-3">
                See the methodology in practice
              </h2>
              <p className="text-stone-400 text-sm leading-relaxed mb-6 max-w-lg mx-auto">
                The methodology page explains how these research foundations are implemented
                in practice — the specific subsystems, risk controls, and daily operations.
              </p>
              <div className="flex justify-center gap-3">
                <Link
                  href="/methodology"
                  className="px-6 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-offset-2 focus:ring-offset-slate-900"
                >
                  Read Methodology
                </Link>
                <Link
                  href="/#pricing"
                  className="px-6 py-2.5 rounded-xl border border-stone-600 bg-transparent hover:bg-stone-800 text-stone-300 font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-stone-500 focus:ring-offset-2 focus:ring-offset-slate-900"
                >
                  View Pricing
                </Link>
              </div>
            </div>
          </main>
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-stone-200 py-10 px-8 max-w-7xl mx-auto mt-8">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 mb-6">
          <span className="font-serif font-bold text-stone-500 text-sm">Winzinvest</span>
          <div className="flex gap-6">
            <Link href="/"         className="text-sm text-stone-400 hover:text-stone-600 transition-colors">Home</Link>
            <Link href="/methodology"     className="text-sm text-stone-400 hover:text-stone-600 transition-colors">Methodology</Link>
            <Link href="/performance"     className="text-sm text-stone-400 hover:text-stone-600 transition-colors">Performance</Link>
            <Link href="/#pricing" className="text-sm text-stone-400 hover:text-stone-600 transition-colors">Pricing</Link>
            <Link href="/login"           className="text-sm text-stone-400 hover:text-stone-600 transition-colors">Dashboard</Link>
          </div>
        </div>
        <p className="text-xs text-stone-400 leading-relaxed max-w-3xl">
          Winzinvest is systematic portfolio automation software. It automates rule-based execution,
          options position management, and risk monitoring. It does not provide investment advice,
          recommendations, or asset management services. Investing in equities and options involves
          substantial risk of loss. Past performance does not guarantee future results.
        </p>
      </footer>
    </div>
  );
}
