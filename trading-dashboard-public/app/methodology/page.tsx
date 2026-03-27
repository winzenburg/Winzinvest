/**
 * Methodology page — single deep-dive for the full system.
 *
 * Absorbs content from the retired /strategy, /research, and /overview pages.
 * Voice: investor-letter from a systematic fund. Principle FIRST, then mechanics.
 * No code references, file names, script names, or trader attributions on public pages.
 */

import Image from 'next/image';
import Link from 'next/link';
import { PublicNav } from '../components/PublicNav';

const SECTIONS = [
  { id: 'thesis',      label: '01 · Investment Thesis' },
  { id: 'framework',   label: '02 · Portfolio Framework' },
  { id: 'system',      label: '03 · How Positions Are Selected' },
  { id: 'management',  label: '04 · How Positions Are Managed' },
  { id: 'options',     label: '05 · Options Income Engine' },
  { id: 'regime',      label: '06 · Market Regime Detection' },
  { id: 'risk',        label: '07 · Risk Framework' },
  { id: 'analytics',   label: '08 · Analytics & Self-Correction' },
  { id: 'operations',  label: '09 · Daily Operations' },
  { id: 'disclosures', label: '10 · Disclosures' },
];

type PageProps = {
  params?: Promise<Record<string, string | string[]>>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default function MethodologyPage(_props: PageProps) {
  return (
    <div className="min-h-screen bg-stone-50">

      <PublicNav />

      {/* Hero banner */}
      <div className="w-full relative h-40 md:h-48 overflow-hidden">
        <Image
          src="/illustrations/methodology-hero.png"
          alt="Geometric pathway with filtered decision gates — representing systematic filtering and risk controls"
          fill
          className="object-cover object-center"
          priority
          sizes="100vw"
        />
        <div className="absolute inset-0 bg-gradient-to-b from-stone-50/10 via-transparent to-stone-50/90" />
      </div>

      <div className="max-w-7xl mx-auto px-8 py-16">
        <div className="grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-12">

          {/* Sidebar nav */}
          <aside className="hidden lg:block">
            <div className="sticky top-24">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-4">On this page</div>
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

            {/* Page header */}
            <header className="mb-16 relative">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-3">Investment Methodology</div>
              <a
                href="/api/download-methodology-pdf"
                download="Winzinvest-Methodology.pdf"
                className="absolute top-0 right-0 inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-stone-300 bg-white hover:bg-stone-50 text-sm text-stone-700 transition-colors"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
                Download PDF
              </a>
              <h1 className="font-serif text-4xl font-bold text-slate-900 leading-tight tracking-tight mb-5">
                A systematic framework for portfolio management
              </h1>
              <p className="text-base text-stone-600 leading-relaxed max-w-2xl mb-4">
                Most portfolio underperformance is not caused by poor strategy selection.
                It is caused by inconsistent execution. Investors override their own rules,
                react emotionally to volatility, and abandon discipline at precisely the moments
                it matters most.
              </p>
              <p className="text-base text-stone-600 leading-relaxed max-w-2xl mb-8">
                This document describes a framework for addressing that problem: a systematic
                approach to portfolio management that generates complementary return streams
                across different market regimes while enforcing structural risk controls —
                and the principles behind each component.
              </p>
              <div className="border-l-4 border-sky-600 pl-5 py-1">
                <p className="font-serif text-lg font-semibold text-slate-800 leading-snug italic">
                  &ldquo;The objective is not to forecast markets, but to systematically participate
                  in them with consistency, transparency, and discipline.&rdquo;
                </p>
              </div>
            </header>

            {/* ───────────────────────────────────────────────────── */}
            {/* 01 · Investment Thesis                               */}
            {/* ───────────────────────────────────────────────────── */}
            <section id="thesis" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">01</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">Investment thesis</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  Decades of behavioral finance research have established a consistent finding:
                  the primary driver of portfolio underperformance among self-directed investors is not
                  what they choose to invest in — it is how they execute. They buy late into rallies,
                  sell during drawdowns, skip entries when afraid, and hold losing positions hoping
                  for recovery. These patterns are well-documented and remarkably persistent.
                </p>
                <p>
                  Institutional investors solved this problem long ago by separating strategy design
                  from strategy execution. The portfolio manager defines the rules. A systematic
                  process executes them — consistently, without emotional interference, every day.
                  This separation of design and execution is the foundation of every major
                  systematic fund, from macro to statistical arbitrage.
                </p>
                <p>
                  Winzinvest applies this same principle to self-directed investing. It is not
                  an attempt to predict markets or discover alpha through novel models. It is
                  infrastructure that ensures a defined investment process is followed with
                  the consistency and discipline that most individuals cannot sustain on their own.
                </p>
                <p>
                  The thesis is simple: <strong>a good process executed consistently will
                  outperform a better process executed inconsistently</strong>. Everything that
                  follows in this document is built on that foundation.
                </p>
              </div>
            </section>

            <div className="border-t border-stone-200 mb-16" />

            {/* ───────────────────────────────────────────────────── */}
            {/* 02 · Portfolio Framework                             */}
            {/* ───────────────────────────────────────────────────── */}
            <section id="framework" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">02</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">Portfolio framework</h2>
              <div className="rounded-xl overflow-hidden mb-6 shadow-sm">
                <Image
                  src="/illustrations/portfolio-framework-waves.png"
                  alt="Layered waves in vibrant colors flowing horizontally — representing multiple uncorrelated return streams working in concert"
                  width={1200}
                  height={500}
                  className="w-full h-auto"
                />
              </div>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  Markets exhibit several structural patterns that can be systematically captured.
                  The portfolio framework is designed to exploit four of these characteristics
                  simultaneously — selecting strategies that are each grounded in well-documented
                  market behavior and tend to complement each other across different environments.
                </p>
                <p>
                  The design principle borrowed from institutional portfolio construction is this:
                  <strong> returns should come from multiple uncorrelated sources</strong>.
                  A portfolio that depends on a single strategy or a single market condition is
                  fragile. A portfolio that generates returns through independent mechanisms is
                  more resilient — and more likely to perform across the full range of market cycles.
                </p>
              </div>

              <div className="space-y-0 border border-stone-200 rounded-xl overflow-hidden mt-8">
                {[
                  { num: '01', title: 'Momentum persists across asset classes and time horizons', body: 'Securities that have outperformed recently tend to continue outperforming over intermediate periods. This pattern is one of the most replicated findings in financial research, observable across equities, fixed income, currencies, and commodities.' },
                  { num: '02', title: 'Options markets systematically overprice volatility', body: 'Implied volatility consistently exceeds realized volatility on average — a persistent gap that reflects the insurance premium investors pay for risk transfer. Disciplined systematic sellers capture this gap as recurring income.' },
                  { num: '03', title: 'Short-term price dislocations revert toward equilibrium', body: 'Sharp short-term declines in structurally sound securities are often driven by liquidity flows rather than fundamental deterioration. These dislocations tend to correct quickly, creating systematic entry opportunities with defined risk.' },
                  { num: '04', title: 'Market regimes influence which strategies perform best', body: 'Different environments favor different approaches. Momentum performs best in trending markets; mean reversion in volatile, range-bound conditions; options premium in stable or moderately volatile environments. The system adapts continuously rather than ignoring this reality.' },
                ].map(({ num, title, body }, i, arr) => (
                  <div key={num} className={`p-6 flex gap-5 bg-white ${i < arr.length - 1 ? 'border-b border-stone-200' : ''}`}>
                    <span className="font-serif text-2xl font-bold text-stone-200 shrink-0 w-7 leading-none tabular-nums pt-0.5">{num}</span>
                    <div>
                      <div className="font-semibold text-sm text-slate-900 mb-1.5">{title}</div>
                      <p className="text-sm text-stone-600 leading-relaxed">{body}</p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-4 bg-stone-50 border border-stone-200 rounded-xl p-5">
                <p className="text-sm text-stone-600 leading-relaxed">
                  <strong>Design implication:</strong> Each strategy in the platform is selected because
                  it captures one of these structural patterns. They are not assembled for completeness —
                  they are assembled because they tend to generate returns at different times, in different
                  conditions, creating a portfolio that is more consistent than any individual component.
                </p>
              </div>
            </section>

            <div className="border-t border-stone-200 mb-16" />

            {/* ───────────────────────────────────────────────────── */}
            {/* 03 · How Positions Are Selected                      */}
            {/* ───────────────────────────────────────────────────── */}
            <section id="system" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">03</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">How positions are selected</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  The equity engine is the primary return driver, targeting 40%+ annual returns through
                  concentrated momentum trading. Rather than passively holding a diversified basket,
                  the system actively rotates through <strong>15–20 high-conviction positions</strong>,
                  entering on breakouts and cutting losers quickly — targeting a 3:1 reward-to-risk ratio
                  on each trade.
                </p>
                <p>
                  Not every candidate that appears on a screener deserves capital. The system applies
                  multiple layers of confirmation and filtering to ensure that only the highest-quality
                  setups receive allocation.
                </p>
              </div>

              {/* Quality gate */}
              <div className="mt-8 bg-white border border-stone-200 rounded-xl overflow-hidden">
                <div className="p-5 border-b border-stone-200 bg-stone-50">
                  <div className="font-semibold text-sm text-slate-900">Quality gate — conviction hard block</div>
                  <p className="text-xs text-stone-500 mt-1 leading-relaxed">
                    The most important filter: a minimum quality threshold below which no trade is taken, regardless of market conditions.
                  </p>
                </div>
                <div className="p-5 text-sm text-stone-600 leading-relaxed space-y-3">
                  <p>
                    Every candidate must achieve a minimum conviction score before reaching execution. Below
                    this floor, the candidate is eliminated — not sized down, not flagged for manual review,
                    but removed from the pipeline entirely. This forces the system to surface only the
                    highest-ranked setups each session.
                  </p>
                  <p>
                    Above the floor, a three-tier multiplier applies to position sizing: acceptable-quality
                    trades receive slightly less than standard size; strong trades receive above-standard;
                    exceptional trades receive significantly more. A daily trade budget ensures that on days
                    when the screener surfaces many candidates, only the top-ranked ones consume capital.
                  </p>
                </div>
              </div>

              {/* Signal confirmation layers */}
              <div className="space-y-0 border border-stone-200 rounded-xl overflow-hidden mt-8">
                {[
                  {
                    num: '01',
                    title: 'Multi-timeframe confirmation',
                    body: 'Every candidate is scored across three timeframes: the weekly trend, the daily trend, and an intraday proxy. When all three align, the probability of a sustained move is significantly higher. When they conflict, the signal is downweighted or rejected. This is the same principle institutional trend-following funds use — they call it "timeframe convergence" — and it measurably reduces false entries.',
                  },
                  {
                    num: '02',
                    title: 'Post-earnings announcement drift',
                    body: 'Stocks experiencing strong earnings surprises tend to drift in the direction of the surprise for days or weeks after the announcement. This is one of the most persistent anomalies in equity markets — driven by institutional investors who cannot fully rebalance on the announcement day. The system detects recent earnings events, measures the overnight gap and subsequent follow-through, and adds a conviction boost for entries that align with the drift direction. The boost decays linearly as the informational advantage fades.',
                  },
                  {
                    num: '03',
                    title: 'Sector relative strength overlay',
                    body: 'Not all sectors perform equally at any given time. The platform ranks all eleven GICS sectors by trailing relative strength and applies a sizing multiplier: top-ranked sectors receive larger positions, bottom-ranked sectors receive smaller positions. This transforms the sector framework from a passive cap into an active tilt toward where momentum is strongest.',
                  },
                  {
                    num: '04',
                    title: 'Catalyst-driven entry screening',
                    body: 'When a stock gaps up significantly on exceptionally high volume due to a genuine fundamental catalyst — earnings beat, guidance raise, product launch, regulatory approval — and then consolidates near the gap high for several days, it has likely attracted institutional attention that has not yet been fully expressed in price. The gap reveals the catalyst. The consolidation reveals controlled distribution. The subsequent breakout, confirmed by a relative volume surge, is the entry signal.',
                  },
                  {
                    num: '05',
                    title: 'Sentiment overlay',
                    body: 'The system monitors the equity put/call ratio daily. When the ratio reaches extreme levels — either complacency or fear — conviction scores are adjusted. Extreme complacency slightly reduces long conviction; elevated fear can provide a contrarian boost. Historical profit factors by strategy and market regime also feed into candidate ranking, penalizing strategies that have underperformed recently in the current environment.',
                  },
                ].map(({ num, title, body }, i, arr) => (
                  <div key={num} className={`p-6 flex gap-5 bg-white ${i < arr.length - 1 ? 'border-b border-stone-200' : ''}`}>
                    <span className="font-serif text-2xl font-bold text-stone-200 shrink-0 w-7 leading-none tabular-nums pt-0.5">{num}</span>
                    <div>
                      <div className="font-semibold text-sm text-slate-900 mb-1.5">{title}</div>
                      <p className="text-sm text-stone-600 leading-relaxed">{body}</p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-4 bg-stone-50 border border-stone-200 rounded-xl p-5">
                <p className="text-sm text-stone-600 leading-relaxed">
                  <strong>Design implication:</strong> These layers are additive, not gating.
                  They do not prevent a trade from being taken — they modulate how much conviction and
                  capital the system allocates to it. A momentum setup with multi-timeframe alignment,
                  a recent earnings catalyst, and a top-ranked sector will receive substantially
                  more capital than the same setup without those confirmations.
                </p>
              </div>

              {/* Strategy types */}
              <div className="mt-8 bg-white border border-stone-200 rounded-xl p-6">
                <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-4">Strategy types</div>
                <div className="space-y-3">
                  {[
                    { label: 'Momentum longs', desc: 'The primary return driver. Screens hundreds of symbols daily using a composite scoring model that combines price momentum, volatility structure, relative strength, and volume quality. Enters on confirmed breakouts with multi-timeframe alignment.' },
                    { label: 'Bearish shorts', desc: 'Activated during downtrending regimes. A dedicated screener identifies stocks below long-term moving averages with negative relative strength and poor volume quality. Functions as a primary income source during extended declines, not just a hedge overlay.' },
                    { label: 'Mean reversion', desc: 'Buys short-term oversold pullbacks in securities that remain in a longer-term uptrend. Held for days with tight risk controls. These positions capture a different return pattern than the momentum strategy.' },
                    { label: 'Episodic pivots', desc: 'Identifies stocks at the beginning of a new trend — the moment a fundamental catalyst reshapes expectations. Distinct from the momentum screener, which finds stocks already in established trends.' },
                    { label: 'Pairs trading', desc: 'Market-neutral long/short on historically correlated securities whose prices have diverged beyond a statistical threshold. Returns are independent of overall market direction.' },
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

            {/* ───────────────────────────────────────────────────── */}
            {/* 04 · How Positions Are Managed                       */}
            {/* ───────────────────────────────────────────────────── */}
            <section id="management" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">04</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">How positions are managed</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  Entering a position is only half the discipline. How a position is managed after entry
                  — how stops are set, when profits are taken, how winners are built into and losers are
                  cut — determines whether a strategy&apos;s theoretical edge is captured in practice.
                </p>
                <p>
                  Every position in the portfolio is subject to the same structural management rules.
                  There is no discretionary override at the moment of exit. The rules are defined in
                  advance, calibrated from the portfolio&apos;s own trade history, and executed automatically.
                </p>
              </div>

              <div className="space-y-4 mt-8">
                {[
                  {
                    title: 'Volatility-based position sizing',
                    body: 'Each position is sized so that a stop-loss hit costs less than 1% of equity. More volatile securities receive smaller positions; less volatile ones receive more. Size also adjusts based on conviction level, market regime, and sector conditions — ensuring the portfolio is never over-concentrated in a single risk factor.',
                    accent: 'border-l-sky-600',
                  },
                  {
                    title: 'ATR-based stop losses',
                    body: 'Every position has a hard stop-loss from the moment of entry, calculated as a multiple of the security\'s Average True Range. The stop is placed at the broker immediately — it does not depend on the system being online. Every morning, stops are recalculated and ratcheted upward as positions gain value. Stops never move down.',
                    accent: 'border-l-red-600',
                  },
                  {
                    title: 'Trailing stops',
                    body: 'Once a position reaches a defined profit threshold, a trailing stop activates. The trail locks in gains while giving the position room to develop. This is placed directly with the broker as a native trailing order — it executes even if the system is offline.',
                    accent: 'border-l-orange-500',
                  },
                  {
                    title: 'Historically calibrated profit targets',
                    body: 'Rather than using a fixed take-profit target, the system derives targets from its own trade history. Each week, it computes the maximum favorable excursion for winning trades by strategy type. The resulting target is empirically grounded — strategies with shorter typical moves get tighter targets that improve win rates; strategies with longer moves get extended targets that let winners run further.',
                    accent: 'border-l-green-600',
                  },
                  {
                    title: 'Partial profit scaling',
                    body: 'When a position reaches an intermediate profit threshold, half is closed and the proceeds are returned to the cash pool for redeployment. The remaining half continues to run with a tightened trailing stop. This improves realized win rates and reduces variance without abandoning good positions prematurely.',
                    accent: 'border-l-amber-500',
                  },
                  {
                    title: 'Building into confirmed winners',
                    body: 'Rather than taking full position size at entry, the system builds into confirmed winners in two stages. First, if a new position shows immediate confirmation within the first two days, a partial add is made and the stop is moved to breakeven. Second, when a position\'s unrealized gain exceeds a defined multiple of its volatility, a further add is funded from open-profit collateral. This means the initial entry takes the full entry risk at modest size; additional risk is only added when the position is already confirmed.',
                    accent: 'border-l-emerald-600',
                  },
                  {
                    title: 'Early exit for failed setups',
                    body: 'A properly-entered trade should show confirmation within two trading days. If a position is still below entry price after this window and has drifted down meaningfully, the system closes it at market rather than waiting for the hard stop. This early exit preserves capital for higher-conviction setups entering that same session.',
                    accent: 'border-l-red-600',
                  },
                  {
                    title: 'Time limits',
                    body: 'Positions that have not reached their target or stop within a defined holding period are closed. In strongly trending markets, the holding period extends automatically — letting winners run when conditions support it. In all cases, the time limit prevents capital from being tied up in ideas that aren\'t working.',
                    accent: 'border-l-sky-600',
                  },
                  {
                    title: 'Gap protection',
                    body: 'When a stop-loss is triggered at the open due to an overnight gap, the system distinguishes between a genuine breakdown and a temporary shakeout. For small gaps, a brief grace period allows the position time to recover. For large gaps, the system treats the move as a real directional break and executes immediately.',
                    accent: 'border-l-orange-500',
                  },
                ].map(({ title, body, accent }) => (
                  <div key={title} className={`bg-white border border-stone-200 rounded-xl p-6 border-l-4 ${accent}`}>
                    <h3 className="font-semibold text-sm text-slate-900 mb-2">{title}</h3>
                    <p className="text-sm text-stone-600 leading-relaxed">{body}</p>
                  </div>
                ))}
              </div>
            </section>

            <div className="border-t border-stone-200 mb-16" />

            {/* ───────────────────────────────────────────────────── */}
            {/* 05 · Options Income Engine                           */}
            {/* ───────────────────────────────────────────────────── */}
            <section id="options" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">05</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">Options income engine</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  The income engine generates recurring premium by writing options against the equity
                  portfolio. This is the same approach used by pension funds, endowments, and institutional
                  covered call strategies — but automated at the individual position level.
                </p>
                <p>
                  The objective is not to replace equity returns with options income. It is to add a
                  second return stream that is partially independent of market direction, compounding
                  alongside the primary momentum engine.
                </p>
              </div>

              <div className="space-y-4 mt-8">
                {[
                  {
                    title: 'Covered calls',
                    body: 'The primary income source. When the portfolio holds sufficient shares, the system evaluates whether a covered call is appropriate based on implied volatility, distance from earnings and dividend dates, and portfolio options exposure. Calls are written far enough from the current price to give the underlying room to appreciate while capturing meaningful premium. When a call reaches 80% of its maximum profit, it is automatically closed and immediately reopened at a fresh duration — compounding income within the same holding period.',
                    accent: 'border-l-green-600',
                  },
                  {
                    title: 'Cash-secured puts',
                    body: 'Used to generate income on securities the portfolio would like to own at a lower price. The system writes puts below the current market — if the stock falls, the portfolio acquires it at a discount; if it doesn\'t, the premium is kept as income. Active only in favorable or neutral market regimes; blocked during downtrends where assignment losses are too costly.',
                    accent: 'border-l-purple-600',
                  },
                  {
                    title: 'Iron condors',
                    body: 'In range-bound markets where equity momentum generates less, the system sells defined-risk iron condors on broad indices. The strategy profits when the market stays within a wide range — exactly the conditions where momentum strategies underperform, creating a natural complement.',
                    accent: 'border-l-blue-600',
                  },
                  {
                    title: 'Protective puts',
                    body: 'During uncertain or declining regimes, the system purchases protective put options on broad indices as portfolio insurance. The cost is budgeted as a fixed percentage of equity per month — a structural insurance policy rather than a speculative bet.',
                    accent: 'border-l-amber-500',
                  },
                  {
                    title: 'Adaptive roll strategies',
                    body: 'When a short option reaches its profit target, the system evaluates three roll strategies before reopening. If the underlying has rallied significantly above the strike, a diagonal roll is executed at a higher, more out-of-the-money strike. If the stock is near the money with time remaining, a calendar spread captures additional time decay. In all other cases, a standard same-strike roll is applied.',
                    accent: 'border-l-sky-600',
                  },
                ].map(({ title, body, accent }) => (
                  <div key={title} className={`bg-white border border-stone-200 rounded-xl p-6 border-l-4 ${accent}`}>
                    <h3 className="font-semibold text-sm text-slate-900 mb-2">{title}</h3>
                    <p className="text-sm text-stone-600 leading-relaxed">{body}</p>
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-8">
                {[
                  { title: 'Dividend protection', body: 'Before writing any covered call, the system checks whether an ex-dividend date falls within the option window. If the dividend would exceed a meaningful fraction of the call premium, the call is skipped — protecting dividend income from early assignment.' },
                  { title: 'Earnings awareness', body: 'Options activity is automatically paused around earnings announcements. The implied volatility expansion before earnings can make options seem attractive, but the binary risk of a large post-earnings move makes the risk-reward unfavorable for the premium seller.' },
                  { title: 'Delta drift monitoring', body: 'Short call positions are continuously monitored. When a call drifts deep in-the-money, an urgent alert fires immediately with the specific position details and a recommended action — giving time to respond before assignment becomes likely.' },
                ].map(({ title, body }) => (
                  <div key={title} className="bg-white border border-stone-200 rounded-xl p-5">
                    <div className="font-semibold text-sm text-slate-900 mb-2">{title}</div>
                    <p className="text-xs text-stone-500 leading-relaxed">{body}</p>
                  </div>
                ))}
              </div>
            </section>

            <div className="border-t border-stone-200 mb-16" />

            {/* ───────────────────────────────────────────────────── */}
            {/* 06 · Market Regime Detection                         */}
            {/* ───────────────────────────────────────────────────── */}
            <section id="regime" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">06</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">Market regime detection</h2>
              <div className="rounded-xl overflow-hidden mb-6 shadow-sm">
                <Image
                  src="/illustrations/regime-landscape.png"
                  alt="Four distinct atmospheric landscapes side by side — representing different market regime states and systematic adaptation"
                  width={1200}
                  height={500}
                  className="w-full h-auto"
                />
              </div>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  Not all market environments are the same, and a strategy that works well in a trending
                  market may underperform in a volatile or directionless one. The platform addresses this
                  through a regime detection system that evaluates current market conditions and adjusts
                  portfolio behavior accordingly.
                </p>
                <p>
                  The system operates <strong>two independent classification layers</strong>. The first evaluates
                  the broad equity market trend and volatility environment. This determines which strategies
                  are active — momentum strategies may be fully active in a strong uptrend but partially
                  or fully paused during a downturn. The second layer evaluates macro-level stress using a scored
                  composite of independently sourced indicators: volatility term structure, credit spreads, real
                  yields, financial conditions, industrial production, seven commodity supply-chain signals,
                  and real-time news sentiment. This layer adjusts how aggressively the portfolio takes new
                  positions rather than turning strategies on or off.
                </p>
                <p>
                  A third layer — <strong>leading indicators</strong> — sits upstream of both. The VIX
                  term structure, credit spread proxies, large-cap market breadth, and the equity put/call
                  ratio are composited into a daily stress score. When this score crosses defined thresholds,
                  the execution regime is preemptively downgraded before lagging price-based signals catch up.
                  Credit and volatility markets historically lead equity markets by one to three weeks — this
                  layer captures that lead time and begins reducing exposure before a drawdown shows up in the portfolio.
                </p>
                <p>
                  Both primary layers are evaluated multiple times per trading day. When conditions change, the
                  portfolio&apos;s behavior adjusts within the same session. This is not a monthly rebalancing
                  process — it is a continuous adaptive framework.
                </p>
              </div>

              <div className="bg-slate-900 rounded-xl p-6 mt-8">
                <div className="text-xs font-semibold uppercase tracking-wider text-sky-400 mb-4">
                  Why regime awareness matters
                </div>
                <div className="space-y-4">
                  {[
                    'Momentum strategies generate most of their returns during trending markets. Running them at full capacity during volatile sideways markets increases turnover and drawdowns without proportional benefit.',
                    'Options premium selling is most attractive when implied volatility is elevated — but the same conditions that create high premiums also increase the probability of adverse outcomes. The regime system balances this trade-off.',
                    'Many investors attempt to time markets manually, which introduces exactly the kind of emotional decision-making that hurts performance. The regime system provides the same adaptive behavior through a rule-based process.',
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

            {/* ───────────────────────────────────────────────────── */}
            {/* 07 · Risk Framework                                  */}
            {/* ───────────────────────────────────────────────────── */}
            <section id="risk" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">07</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">Risk management framework</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  Risk management is not a feature of the platform — it is the foundation.
                  Every decision the system makes passes through multiple layers of constraints
                  before it reaches the brokerage account. These constraints are structural; they
                  cannot be bypassed in the moment of execution.
                </p>
                <p>
                  The philosophy behind the risk framework is <strong>graduated response</strong>.
                  Rather than operating as a binary switch — either fully on or fully off — the system
                  reduces activity progressively as conditions deteriorate. This allows the portfolio
                  to remain operational through normal volatility while providing meaningful protection
                  during genuine distress.
                </p>
              </div>

              <div className="space-y-4 mt-8">
                {[
                  {
                    title: 'Five-tier drawdown ladder',
                    body: 'As intra-day losses accumulate, the system steps down automatically. The first two tiers reduce new position sizes. The third tier cuts all sizes further. The fourth halts new entries entirely. The fifth activates the kill switch. Each morning, the system resets. This graduated approach ensures a bad morning stays a bad morning — it does not compound into a bad month.',
                    accent: 'border-l-red-600',
                  },
                  {
                    title: 'Thirteen pre-trade execution checks',
                    body: 'Every order passes through thirteen independent safety checks before it reaches the broker: covering the kill switch, daily loss limits, sector concentration, gap-risk windows, regime conditions, position sizing caps, margin requirements, leverage limits, notional exposure, per-position concentration, total portfolio heat, recent losing streaks, and cross-holding correlation. Fail any one and the order does not fire.',
                    accent: 'border-l-sky-600',
                  },
                  {
                    title: 'Structural crash hedge',
                    body: 'Once per month, if the portfolio carries no existing downside protection and volatility is low enough for cheap premium, the system places a broad market put spread. The spread is funded by options income and costs a small fraction of equity per month. If a large market drawdown occurs, the spread provides asymmetric payoff that partially offsets losses across the portfolio.',
                    accent: 'border-l-red-600',
                  },
                  {
                    title: 'Sector concentration and correlation',
                    body: 'No sector can exceed 30% of portfolio equity. A rolling correlation matrix monitors whether nominally diversified positions are behaving similarly — creating hidden concentration risk. When sector limits are breached, the weakest position is closed automatically.',
                    accent: 'border-l-sky-600',
                  },
                  {
                    title: 'Sector ETF hedging',
                    body: 'In declining or choppy regimes, over-concentrated sectors receive automatic inverse ETF hedges sized proportionally to sector exposure. Hedges are closed automatically when the regime recovers — protecting capital during downturns without creating permanent drag in recoveries.',
                    accent: 'border-l-orange-500',
                  },
                  {
                    title: 'Emergency halt',
                    body: 'A PIN-protected kill switch is accessible from the dashboard at all times. It can be activated manually or triggered automatically by the drawdown ladder. When active, all portfolio activity stops immediately and remains halted until explicitly cleared.',
                    accent: 'border-l-red-600',
                  },
                  {
                    title: 'Earnings and dividend protection',
                    body: 'Earnings announcements and ex-dividend dates create periods of elevated risk for options positions. The system automatically identifies these windows and suspends options activity around them, preventing the portfolio from taking positions where the risk-reward is temporarily distorted.',
                    accent: 'border-l-green-600',
                  },
                  {
                    title: 'Opening gap monitor',
                    body: 'Shortly after each open, every position is scanned for an opening gap against the prior close. Significant gaps trigger immediate alerts. Gap-up on covered call positions flags potential early assignment risk. Gap-down stops use a grace period to distinguish genuine breakdowns from temporary shakeouts.',
                    accent: 'border-l-orange-500',
                  },
                  {
                    title: 'Re-entry watchlist',
                    body: 'After any position is stopped out, the system continues monitoring the symbol for up to 30 days. When price, trend, and momentum conditions all confirm a genuine recovery, an alert fires. This ensures recoveries are not missed while preventing re-entry into false bounces.',
                    accent: 'border-l-green-600',
                  },
                  {
                    title: 'Macro-adaptive cash management',
                    body: 'The cash deployment threshold adjusts automatically based on the macro environment. In normal conditions, the system deploys idle cash aggressively. When defensive signals are active, the threshold rises — keeping more capital in reserve without requiring manual intervention.',
                    accent: 'border-l-sky-600',
                  },
                  {
                    title: 'Complete audit trail',
                    body: 'Every action the system takes — every trade, parameter update, regime transition, and risk event — is logged in a permanent audit trail. This record is available through the dashboard for review, performance attribution, and tax reporting.',
                    accent: 'border-l-stone-400',
                  },
                ].map(({ title, body, accent }) => (
                  <div key={title} className={`bg-white border border-stone-200 rounded-xl p-6 border-l-4 ${accent}`}>
                    <h3 className="font-semibold text-sm text-slate-900 mb-2">{title}</h3>
                    <p className="text-sm text-stone-600 leading-relaxed">{body}</p>
                  </div>
                ))}
              </div>
            </section>

            <div className="border-t border-stone-200 mb-16" />

            {/* ───────────────────────────────────────────────────── */}
            {/* 08 · Analytics & Self-Correction                     */}
            {/* ───────────────────────────────────────────────────── */}
            <section id="analytics" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">08</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">Analytics and self-correction</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  Systematic strategies require systematic feedback. Without a structured way to review
                  what is and isn&apos;t working, even a good process drifts. The platform includes a
                  dedicated analytics layer that processes every completed trade and surfaces patterns
                  that would be invisible in a raw trade log.
                </p>
                <p>
                  This is not a reporting dashboard — it is a calibration tool. It closes the feedback
                  loop between what the strategy is designed to do and what it is actually doing.
                </p>
              </div>

              <div className="space-y-0 border border-stone-200 rounded-xl overflow-hidden mt-8">
                {[
                  { num: '01', title: 'Strategy-level attribution', body: 'Win rate, average R-multiple, total P&L, and profit factor broken down by strategy type. Each strategy receives a recommendation — scale up, reduce, or pause — based on profit factor and expectancy thresholds. This makes it immediately clear which components of the portfolio are contributing and which need attention.' },
                  { num: '02', title: 'Regime-conditional performance', body: 'The same attribution broken out by the market regime that was active when each trade was entered. This reveals whether a strategy that appears weak overall is actually performing fine in its intended regime and struggling only when deployed outside it — the most common source of misdiagnosed strategy failures.' },
                  { num: '03', title: 'Hold time analysis', body: 'Average hold time for winners versus losers, by strategy type. A pattern of winners being held too short or losers too long is often invisible in aggregate returns but shows clearly in hold time comparison.' },
                  { num: '04', title: 'Exit reason distribution', body: 'How positions actually exit — trailing stop, hard stop, profit target, time stop, manual, or roll — and whether winners and losers are exiting through the expected mechanism. If the trailing stop is the primary exit but the profit target is never reached, the reward-to-risk ratio is being truncated.' },
                  { num: '05', title: 'Historically calibrated profit targets', body: 'Each week, the system computes the maximum favorable excursion for winning trades by strategy. This becomes the take-profit target for the following week — replacing static targets with empirically derived ones from the portfolio\'s own trade history.' },
                  { num: '06', title: 'Systematic vs. discretionary exit comparison', body: 'Every closed trade is classified as a systematic exit or a discretionary override. The system compares average R-multiples for each group. If systematic exits consistently outperform overrides, a recommendation fires to reduce discretionary intervention. This data quantifies the cost of breaking your own rules.' },
                  { num: '07', title: 'Strategy diversity monitoring', body: 'A concentration score flags when a single strategy dominates too large a share of active trades. This prevents the portfolio from inadvertently becoming a single-strategy bet during periods when one approach is outperforming.' },
                ].map(({ num, title, body }, i, arr) => (
                  <div key={num} className={`p-6 flex gap-5 bg-white ${i < arr.length - 1 ? 'border-b border-stone-200' : ''}`}>
                    <span className="font-serif text-2xl font-bold text-stone-200 shrink-0 w-7 leading-none tabular-nums pt-0.5">{num}</span>
                    <div>
                      <div className="font-semibold text-sm text-slate-900 mb-1.5">{title}</div>
                      <p className="text-sm text-stone-600 leading-relaxed">{body}</p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-4 bg-stone-50 border border-stone-200 rounded-xl p-5">
                <p className="text-sm text-stone-600 leading-relaxed">
                  <strong>Continuous optimization:</strong> Each week, the system also evaluates multiple
                  parameter combinations across current holdings — testing different strike distances,
                  holding periods, and profit targets. The top-performing combinations are surfaced as
                  recommendations. Parameter changes are informed by evidence, not intuition, and applied
                  after human review.
                </p>
              </div>
            </section>

            <div className="border-t border-stone-200 mb-16" />

            {/* ───────────────────────────────────────────────────── */}
            {/* 09 · Daily Operations                                */}
            {/* ───────────────────────────────────────────────────── */}
            <section id="operations" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">09</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">Daily operations</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed mb-8">
                <p>
                  The platform follows a structured daily cycle. Each phase happens automatically,
                  in the same order, every trading day. The investor can observe the process through
                  the dashboard but does not need to intervene at any point.
                </p>
              </div>

              <div className="space-y-3">
                {[
                  { phase: 'Pre-market', time: 'Before the open', desc: 'The system reviews the portfolio, runs momentum, mean reversion, post-earnings drift, dividend capture, and catalyst-driven screeners. Orders are prepared for the session. Regime conditions from the previous close are re-evaluated.' },
                  { phase: 'Market open', time: 'At the open', desc: 'Prepared orders are executed. New equity positions are entered based on overnight screening results. Sector hedges are evaluated and opened or closed based on the current regime. Pending stop and take-profit orders are checked against live prices.' },
                  { phase: 'Gap scan', time: 'Shortly after open', desc: 'Every position is scanned for an opening gap against the prior close. Significant gaps trigger immediate alerts or a brief grace period. Gap-up on covered-call positions flags potential early assignment risk.' },
                  { phase: 'Stop ratchet', time: 'Shortly after open', desc: 'Stop prices are recalculated from current volatility data for every open position. Stops only ever move up. Any position opened since the last run that lacks a stop gets one created automatically.' },
                  { phase: 'Options management', time: 'Shortly after open', desc: 'The options engine evaluates each holding for covered call and put opportunities. New income positions are opened where criteria are met. Existing positions are checked against profit targets and risk limits. The monthly crash hedge is evaluated.' },
                  { phase: 'Continuous monitoring', time: 'Throughout the day', desc: 'All open positions are monitored against their defined risk parameters — profit targets, partial exits, stop losses, and time limits. Options positions are evaluated for rolling opportunities. The winner pyramid runs to build into confirmed positions. Failed setups are identified and closed early. Drawdown levels are tracked continuously.' },
                  { phase: 'Midday regime check', time: 'Early afternoon', desc: 'Both regime layers are re-evaluated with current market data. If conditions have changed since the morning, strategy allocation and position sizing adjust for the remainder of the session.' },
                  { phase: 'End of day', time: 'At the close', desc: 'A complete portfolio snapshot is taken. The daily performance report is generated. Trade analytics are updated. All positions, risk metrics, and system events are logged to the permanent audit trail.' },
                  { phase: 'Weekly calibration', time: 'Friday after close', desc: 'The optimization engine runs its full parameter sweep. The strategy attribution report is generated with the full week\'s data. Take-profit targets are recalibrated from recent trade history. Tax-loss harvesting opportunities are identified.' },
                ].map(({ phase, time, desc }) => (
                  <div key={phase} className="bg-white border border-stone-200 rounded-xl p-5">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="font-semibold text-sm text-slate-900">{phase}</span>
                      <span className="text-xs text-stone-400">{time}</span>
                    </div>
                    <p className="text-sm text-stone-600 leading-relaxed">{desc}</p>
                  </div>
                ))}
              </div>
            </section>

            <div className="border-t border-stone-200 mb-16" />

            {/* ───────────────────────────────────────────────────── */}
            {/* 10 · Disclosures                                     */}
            {/* ───────────────────────────────────────────────────── */}
            <section id="disclosures" className="mb-16">
              <div className="bg-white border border-stone-200 rounded-xl p-8">
                <h2 className="font-serif text-xl font-bold text-slate-900 mb-4">Important disclosures</h2>
                <div className="space-y-3 text-sm text-stone-600 leading-relaxed">
                  <p>
                    Winzinvest is portfolio management software that automates the execution of investor-defined
                    rules. It does not provide investment advice, recommend securities, or manage assets on
                    behalf of investors. All strategy parameters and risk tolerances are determined by the investor.
                  </p>
                  <p>
                    Investing in equities and options involves substantial risk of loss, including the potential
                    loss of the entire invested amount. Systematic strategies can and do underperform.
                    Past performance — whether from backtesting or live operation — does not guarantee future results.
                    Options can expire worthless or result in assignment; losses can exceed the premium collected.
                  </p>
                  <p>
                    The risk controls described on this page are designed to enforce portfolio discipline.
                    They do not eliminate the risk of loss. Market conditions, execution quality, and
                    unforeseen events can all lead to outcomes that differ materially from expectations.
                  </p>
                </div>
              </div>
            </section>

            {/* CTA */}
            <div className="bg-slate-900 rounded-xl p-10 text-center">
              <h2 className="font-serif text-2xl font-bold text-white mb-3">
                Ready to see it in action?
              </h2>
              <p className="text-stone-400 text-sm leading-relaxed mb-6 max-w-md mx-auto">
                The dashboard provides real-time visibility into every aspect of the system
                described on this page — positions, risk metrics, regime status, and the full audit trail.
              </p>
              <div className="flex justify-center gap-3">
                <Link
                  href="/login"
                  className="px-6 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-offset-2 focus:ring-offset-slate-900"
                >
                  Open Dashboard
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
            <Link href="/methodology"     className="text-sm text-stone-400 hover:text-stone-600 transition-colors">How It Works</Link>
            <Link href="/performance"     className="text-sm text-stone-400 hover:text-stone-600 transition-colors">Performance</Link>
            <Link href="/#pricing" className="text-sm text-stone-400 hover:text-stone-600 transition-colors">Pricing</Link>
            <Link href="/login"           className="text-sm text-stone-400 hover:text-stone-600 transition-colors">Log In</Link>
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
