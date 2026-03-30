/**
 * Methodology page — single deep-dive for the full system.
 *
 * Absorbs content from the retired /strategy, /research, and /overview pages.
 * Voice: investor-letter from a systematic fund. Principle FIRST, then mechanics.
 * No code references, file names, script names, or trader attributions on public pages.
 */

import type { Metadata } from 'next';
import Image from 'next/image';
import Link from 'next/link';
import { PublicNav } from '../components/PublicNav';

export const metadata: Metadata = {
  title: 'How it works – the full methodology',
  description:
    'Portfolio framework, position selection, options automation, regime detection, and risk controls. The principles behind the system and how they work together. No shortcuts, no hype.',
};

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
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-700 mb-4">On this page</div>
              <nav className="space-y-1.5">
                {SECTIONS.map(({ id, label }) => (
                  <a
                    key={id}
                    href={`#${id}`}
                    className="block text-sm text-stone-600 hover:text-sky-600 transition-colors py-1"
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
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-700 mb-3">Investment Methodology</div>
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
                How the system works
              </h1>
              <p className="text-base text-stone-600 leading-relaxed max-w-2xl mb-4">
                Most retail traders don't lose because they picked the wrong strategy.
                They lose because they can't stick to it. They override stops, double up on losers,
                skip entries when scared, and abandon their process exactly when it matters most.
              </p>
              <p className="text-base text-stone-600 leading-relaxed max-w-2xl mb-8">
                This page explains how Winzinvest solves that: a systematic framework that runs 
                multiple strategies in parallel, adapts to market conditions, and enforces risk controls 
                you can't override. The principles first, then the mechanics.
              </p>
              <div className="border-l-4 border-sky-600 pl-5 py-1">
                <p className="font-serif text-lg font-semibold text-slate-800 leading-snug italic">
                  &ldquo;We're not trying to predict markets. We're trying to participate in them 
                  systematically — the same way, every day, without exceptions.&rdquo;
                </p>
              </div>
            </header>

            {/* ───────────────────────────────────────────────────── */}
            {/* 01 · Investment Thesis                               */}
            {/* ───────────────────────────────────────────────────── */}
            <section id="thesis" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-700 mb-2">01</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">Investment thesis</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  Behavioral finance has been documenting the same pattern for decades: retail traders 
                  underperform not because of bad ideas, but bad execution. They buy late into rallies,
                  panic-sell drawdowns, freeze when they should act, and hold losers far too long. 
                  Everyone knows not to do these things. Almost everyone does them anyway.
                </p>
                <p>
                  Institutional investors figured this out a long time ago. They separate strategy design 
                  from execution. The PM writes the rules. A systematic process follows them — 
                  every session, no emotional override. That separation is the foundation of every 
                  serious systematic fund.
                </p>
                <p>
                  Winzinvest just applies that same principle to retail accounts. It's not trying to 
                  predict markets or find novel alpha. It's infrastructure. The job is simple: 
                  follow your rules with the kind of consistency you probably can't sustain on your own.
                </p>
                <p>
                  The thesis: <strong>a decent process executed with discipline beats a brilliant 
                  process executed inconsistently</strong>. Everything else follows from that.
                </p>
              </div>
            </section>

            <div className="border-t border-stone-200 mb-16" />

            {/* ───────────────────────────────────────────────────── */}
            {/* 02 · Portfolio Framework                             */}
            {/* ───────────────────────────────────────────────────── */}
            <section id="framework" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-700 mb-2">02</div>
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
                  Markets have structural patterns you can trade systematically. Momentum persists. 
                  Vol is consistently overpriced. Short-term dislocations revert. Different regimes 
                  favor different approaches. These aren't secrets — they're well-documented and 
                  backed by decades of research.
                </p>
                <p>
                  The framework runs multiple strategies in parallel: 
                  <strong>returns from uncorrelated sources</strong>. A portfolio that depends on 
                  one strategy or one market condition is fragile. When momentum dies, vol selling 
                  keeps working. When vol collapses, mean reversion picks up. That's the design.
                </p>
              </div>

              <div className="space-y-0 border border-stone-200 rounded-xl overflow-hidden mt-8">
                {[
                  { num: '01', title: 'Momentum persists (and everyone still forgets)', body: `Securities that outperformed recently tend to keep outperforming. This is one of the most replicated findings in finance. Works across equities, bonds, currencies, commodities. The challenge isn't knowing this — it's executing it consistently without emotional override.` },
                  { num: '02', title: 'Options markets overprice volatility', body: `Implied vol consistently exceeds realized vol on average. That gap is the insurance premium people pay to hedge risk. Systematic vol sellers capture it. The edge isn't complicated — it's just boring and requires discipline most people can't sustain.` },
                  { num: '03', title: 'Sharp declines revert faster than you think', body: `A stock drops 8% in a day on no news? Often it's just liquidity, not fundamentals. These dislocations correct quickly. The trick is distinguishing genuine deterioration from temporary supply imbalances. That's what the screener filters are for.` },
                  { num: '04', title: 'Regime matters more than people admit', body: `Momentum works in trending markets, dies in chop. Mean reversion works in range-bound conditions, kills you in trends. Vol selling works when realized vol is stable. Ignoring regime is expensive. The system adjusts continuously.` },
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
                  <strong>Why this matters:</strong> Each strategy captures a different structural pattern. 
                  They're not assembled for completeness — they're assembled because they make money at 
                  different times. When one stops working, another takes over. That's the point.
                </p>
              </div>
            </section>

            <div className="border-t border-stone-200 mb-16" />

            {/* ───────────────────────────────────────────────────── */}
            {/* 03 · How Positions Are Selected                      */}
            {/* ───────────────────────────────────────────────────── */}
            <section id="system" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-700 mb-2">03</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">How positions are selected</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  The equity engine is the main return driver. Target: 40%+ annually through concentrated 
                  momentum trading. <strong>15–20 high-conviction positions</strong>, rotated actively. 
                  Enter on breakouts, cut losers fast, target 3:1 reward-to-risk. Not every screener hit 
                  deserves capital.
                </p>
                <p>
                  The system runs multiple confirmation layers before allocating. A weak setup that barely 
                  passes the screener gets sized down or killed. A strong setup with multi-timeframe alignment, 
                  earnings catalyst, and top-sector momentum gets full size or better. Quality matters more than quantity.
                </p>
              </div>

              {/* Quality gate */}
              <div className="mt-8 bg-white border border-stone-200 rounded-xl overflow-hidden">
                <div className="p-5 border-b border-stone-200 bg-stone-50">
                  <div className="font-semibold text-sm text-slate-900">Quality gate — conviction hard block</div>
                  <p className="text-xs text-stone-600 mt-1 leading-relaxed">
                    The most important filter: minimum quality threshold. Below it, the trade doesn't happen.
                  </p>
                </div>
                <div className="p-5 text-sm text-stone-600 leading-relaxed space-y-3">
                  <p>
                    Every candidate gets a conviction score. Below the floor? Killed. Not sized down, not 
                    flagged for review — just removed. This forces the system to surface only the best 
                    setups, not every mediocre one that technically meets the criteria.
                  </p>
                  <p>
                    Above the floor, a three-tier multiplier kicks in. Marginal trade: smaller position. 
                    Strong setup: standard size. Exceptional setup: bigger. A daily trade budget caps how 
                    much capital gets deployed when the screener lights up with 15 candidates — only the 
                    top-ranked ones get filled.
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
                <div className="text-xs font-semibold uppercase tracking-wider text-stone-700 mb-4">Strategy types</div>
                <div className="space-y-3">
                  {[
                    { label: 'Momentum longs', desc: `Primary return driver. Screens hundreds of symbols daily — price momentum, vol structure, relative strength, volume quality. Enters on confirmed breakouts when multiple timeframes align. Cuts fast if it fails.` },
                    { label: 'Bearish shorts', desc: `Activated in downtrends. Dedicated screener finds stocks below their long-term averages with negative relative strength and weak volume. Makes money during declines — not just a hedge, an actual income source.` },
                    { label: 'Mean reversion', desc: `Buys oversold dips in stocks still in uptrends. Held for days, tight stops. Captures a different pattern than momentum — works when momentum doesn't.` },
                    { label: 'Episodic pivots', desc: `The beginning of a new trend, not the middle. Gap up on volume, consolidate near the high, then break out. Finds stocks right after a catalyst reshapes expectations. Distinct from momentum, which finds established trends.` },
                    { label: 'Pairs trading', desc: `Long/short on correlated stocks that diverged. Market-neutral — returns don't depend on whether the market goes up or down. Just mean reversion on spreads.` },
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
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-700 mb-2">04</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">How positions are managed</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  Entry is the easy part. The hard part is what you do next. How stops are set, when 
                  profits are taken, whether you add to winners or cut losers — that's what determines 
                  whether your theoretical edge shows up in your account or gets eroded by bad decisions.
                </p>
                <p>
                  Every position follows the same structural rules. No discretionary override at the exit. 
                  The rules are calibrated from the portfolio's own history and executed automatically. 
                  You don't get to change your mind when you're down.
                </p>
              </div>

              <div className="space-y-4 mt-8">
                {[
                  {
                    title: 'Vol-based position sizing',
                    body: `Each position sized so a stop hit costs < 1% of equity. Volatile stock = smaller position. Low-vol stock = bigger position. Size also adjusts for conviction, regime, and sector exposure. Never over-concentrated in a single risk.`,
                    accent: 'border-l-sky-600',
                  },
                  {
                    title: 'ATR stops on everything',
                    body: `Every position gets a hard stop from entry, calculated as a multiple of ATR. Placed at the broker immediately — doesn't depend on the system being online. Stops ratchet up every morning as positions gain. Never move down.`,
                    accent: 'border-l-red-600',
                  },
                  {
                    title: 'Trailing stops kick in when profitable',
                    body: `Once a position hits a profit threshold, trailing stop activates. Locks in gains, gives the trade room to run. Placed as a native order with the broker — executes even if the system is offline.`,
                    accent: 'border-l-orange-500',
                  },
                  {
                    title: 'Profit targets from your own history',
                    body: `No fixed targets. System derives them from its own completed trades. Each week it computes max favorable excursion by strategy. Strategies with short typical moves get tight targets (higher win rate). Strategies with longer moves get room to run.`,
                    accent: 'border-l-green-600',
                  },
                  {
                    title: 'Scale out when profitable',
                    body: `Hit intermediate profit? Half the position gets closed, proceeds go back to the cash pool. Other half keeps running with a tighter trail. Improves win rate, reduces variance, doesn't abandon winners too early.`,
                    accent: 'border-l-amber-500',
                  },
                  {
                    title: 'Build into confirmed winners',
                    body: `Don't take full size at entry. Build into confirmation. First add: if the position works within two days, add 50% and move stop to breakeven. Second add: when unrealized gain > 2× ATR, use 30% of open profit as collateral. Initial entry takes modest risk; additional risk only when the trade is working.`,
                    accent: 'border-l-emerald-600',
                  },
                  {
                    title: 'Kill failed setups fast',
                    body: `A good setup should work within two days. Still below entry after that window? Close it. Don't wait for the hard stop. Frees up capital for better ideas. This is how you avoid tying up cash in positions that aren't working.`,
                    accent: 'border-l-red-600',
                  },
                  {
                    title: 'Time limits prevent dead capital',
                    body: `Positions that haven't hit target or stop within the holding period get closed. In strong trends, the window extends — let winners run. Otherwise, the time limit makes sure capital doesn't sit in stale ideas.`,
                    accent: 'border-l-sky-600',
                  },
                  {
                    title: 'Gap-down grace period',
                    body: `Stop triggered by an overnight gap? System checks the size. Small gap: brief grace period to see if it recovers (often does). Large gap: treated as a real breakdown, close immediately. Distinguishes shakeouts from actual failures.`,
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
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-700 mb-2">05</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">Options income engine</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  The income engine writes options against the equity portfolio. Covered calls on holdings, 
                  cash-secured puts on names you want to own cheaper. Pension funds and endowments do this 
                  at scale. Winzinvest just automates it at the position level.
                </p>
                <p>
                  The goal isn't to replace equity returns with options income. It's to layer a second 
                  return stream that compounds alongside momentum — partially uncorrelated, generates 
                  income whether the market goes up or sideways.
                </p>
              </div>

              <div className="space-y-4 mt-8">
                {[
                  {
                    title: 'Covered calls',
                    body: `Primary income source. System checks vol, earnings calendar, dividend dates. Writes calls far enough OTM to let the stock appreciate. When a call hits 80% profit, it's closed and reopened at a fresh duration — compounding income within the same hold. Boring, repetitive, profitable.`,
                    accent: 'border-l-green-600',
                  },
                  {
                    title: 'Cash-secured puts',
                    body: `Write puts below current price on stocks you'd own at a discount. Stock falls? You acquire it cheaper. Stock doesn't fall? Keep the premium. Only active in favorable or neutral regimes — turned off in downtrends where assignment is too expensive.`,
                    accent: 'border-l-purple-600',
                  },
                  {
                    title: 'Iron condors',
                    body: `In range-bound markets where equity momentum generates less, the system sells defined-risk iron condors on broad indices. The strategy profits when the market stays within a wide range — exactly the conditions where momentum strategies underperform, creating a natural complement.`,
                    accent: 'border-l-blue-600',
                  },
                  {
                    title: 'Protective puts',
                    body: `During uncertain or declining regimes, the system purchases protective put options on broad indices as portfolio insurance. The cost is budgeted as a fixed percentage of equity per month — a structural insurance policy rather than a speculative bet.`,
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
                    <p className="text-xs text-stone-600 leading-relaxed">{body}</p>
                  </div>
                ))}
              </div>
            </section>

            <div className="border-t border-stone-200 mb-16" />

            {/* ───────────────────────────────────────────────────── */}
            {/* 06 · Market Regime Detection                         */}
            {/* ───────────────────────────────────────────────────── */}
            <section id="regime" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-700 mb-2">06</div>
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
                  Markets change. Momentum works in trends, dies in chop. Options income thrives when 
                  vol is stable, suffers when it spikes. Ignoring regime is expensive. The system 
                  evaluates conditions daily and adjusts accordingly.
                </p>
                <p>
                  <strong>Two layers</strong>: Layer one classifies the equity trend and vol environment — 
                  determines which strategies are active. Momentum runs full in strong uptrends, gets dialed 
                  back in downturns. Layer two is macro stress: vol term structure, credit spreads, real yields, 
                  financial conditions, commodity signals, news sentiment. This layer adjusts position sizing 
                  and aggressiveness, not strategy on/off.
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
                      <p className="text-sm text-stone-200 leading-relaxed">{text}</p>
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
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-700 mb-2">07</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">Risk management framework</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  Risk management isn't a feature — it's the foundation. Every order passes through 
                  multiple constraint layers before it fires. These constraints are structural. 
                  You can't override them when you're down and convinced the next trade is different.
                </p>
                <p>
                  The philosophy: <strong>graduated response</strong>. The system doesn't flip from 
                  "full on" to "full off" like a circuit breaker. It steps down progressively as 
                  conditions deteriorate. Stay operational through normal chop, but protect capital 
                  during real distress. That's the balance.
                </p>
              </div>

              <div className="space-y-4 mt-8">
                {[
                  {
                    title: 'Five-tier drawdown ladder',
                    body: `Down 1%? Position sizes cut to 50%. Down 2%? 25%. Down 3%? Kill switch. Each morning it resets. This is how you make sure a bad morning stays bad — not catastrophic. The tiers are automatic. You don't get to negotiate when you're losing.`,
                    accent: 'border-l-red-600',
                  },
                  {
                    title: 'Thirteen ways to say no',
                    body: `Every order runs through thirteen safety checks before it fires. Kill switch, daily loss limit, sector concentration, gap-risk windows, regime gates, position sizing caps, margin, leverage, notional exposure, portfolio heat, recent losing streaks, correlation. Fail any one, the order dies. You need one reason to place a trade. The system has thirteen reasons to refuse it.`,
                    accent: 'border-l-sky-600',
                  },
                  {
                    title: 'Tail hedge (cheap insurance)',
                    body: `Once a month, if vol is low enough and the portfolio has no downside protection, the system buys a broad market put spread. Funded by options income. Costs a fraction of equity. If the market tanks, the spread pays out asymmetrically and offsets losses. If nothing happens, it expires worthless. That's insurance.`,
                    accent: 'border-l-red-600',
                  },
                  {
                    title: 'Sector concentration caps',
                    body: `No sector above 30% of portfolio equity. A rolling correlation matrix catches hidden concentration — nominally diversified positions that actually move together. When a sector gets too heavy, the weakest position gets closed automatically.`,
                    accent: 'border-l-sky-600',
                  },
                  {
                    title: 'Sector ETF hedging',
                    body: `In declining or choppy regimes, over-concentrated sectors receive automatic inverse ETF hedges sized proportionally to sector exposure. Hedges are closed automatically when the regime recovers — protecting capital during downturns without creating permanent drag in recoveries.`,
                    accent: 'border-l-orange-500',
                  },
                  {
                    title: 'Emergency halt',
                    body: `A PIN-protected kill switch is accessible from the dashboard at all times. It can be activated manually or triggered automatically by the drawdown ladder. When active, all portfolio activity stops immediately and remains halted until explicitly cleared.`,
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
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-700 mb-2">08</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">Analytics and self-correction</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  Systematic strategies need systematic feedback. Without a structured review process, 
                  even good systems drift. The platform processes every closed trade and surfaces patterns 
                  you'd miss in a raw trade log.
                </p>
                <p>
                  This isn't a reporting dashboard — it's a calibration tool. Closes the loop between 
                  what the strategy is supposed to do and what it's actually doing. If something's broken, 
                  you'll see it.
                </p>
              </div>

              <div className="space-y-0 border border-stone-200 rounded-xl overflow-hidden mt-8">
                {[
                  { num: '01', title: 'Strategy-level attribution', body: `Win rate, R-multiple, P&L, profit factor — by strategy. Each one gets a recommendation: scale up, reduce, or pause. Makes it obvious which parts of the portfolio are working and which aren't.` },
                  { num: '02', title: 'Regime-conditional performance', body: `Same attribution, broken out by market regime. A strategy that looks weak overall might be working fine in its intended conditions and failing only when deployed outside them. Most strategy "failures" are actually misapplied strategies.` },
                  { num: '03', title: 'Hold time analysis', body: `Average hold time for winners vs. losers, by strategy. Holding winners too short or losers too long is invisible in aggregate returns but obvious in hold time comparison.` },
                  { num: '04', title: 'Exit reason distribution', body: `How positions actually close: trailing stop, hard stop, profit target, time stop, manual override. If the trail is the primary exit but profit targets are never hit, your R:R ratio is getting truncated.` },
                  { num: '05', title: 'Historically calibrated profit targets', body: `Each week, system calculates max favorable excursion for winners. That becomes next week's TP — empirically derived from your own trades, not static theory.` },
                  { num: '06', title: 'Systematic vs. override comparison', body: `Every trade classified as systematic exit or discretionary override. System compares average R-multiples. If systematic exits consistently beat overrides, you get a recommendation to stop interfering. Quantifies the cost of breaking your own rules.` },
                  { num: '07', title: 'Strategy diversity check', body: `Flags when one strategy is > 55% of active trades. Prevents the portfolio from accidentally becoming a single-strategy bet when one approach is hot.` },
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
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-700 mb-2">09</div>
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
                  { phase: 'Market open', time: 'At the open', desc: `Prepared orders are executed. New equity positions are entered based on overnight screening results. Sector hedges are evaluated and opened or closed based on the current regime. Pending stop and take-profit orders are checked against live prices.` },
                  { phase: 'Gap scan', time: 'Shortly after open', desc: `Every position is scanned for an opening gap against the prior close. Significant gaps trigger immediate alerts or a brief grace period. Gap-up on covered-call positions flags potential early assignment risk.` },
                  { phase: 'Stop ratchet', time: 'Shortly after open', desc: `Stop prices are recalculated from current volatility data for every open position. Stops only ever move up. Any position opened since the last run that lacks a stop gets one created automatically.` },
                  { phase: 'Options management', time: 'Shortly after open', desc: `The options engine evaluates each holding for covered call and put opportunities. New income positions are opened where criteria are met. Existing positions are checked against profit targets and risk limits. The monthly crash hedge is evaluated.` },
                  { phase: 'Continuous monitoring', time: 'Throughout the day', desc: `All open positions are monitored against their defined risk parameters — profit targets, partial exits, stop losses, and time limits. Options positions are evaluated for rolling opportunities. The winner pyramid runs to build into confirmed positions. Failed setups are identified and closed early. Drawdown levels are tracked continuously.` },
                  { phase: 'Midday regime check', time: 'Early afternoon', desc: `Both regime layers are re-evaluated with current market data. If conditions have changed since the morning, strategy allocation and position sizing adjust for the remainder of the session.` },
                  { phase: 'End of day', time: 'At the close', desc: `A complete portfolio snapshot is taken. The daily performance report is generated. Trade analytics are updated. All positions, risk metrics, and system events are logged to the permanent audit trail.` },
                  { phase: 'Weekly calibration', time: 'Friday after close', desc: `The optimization engine runs its full parameter sweep. The strategy attribution report is generated with the full week's data. Take-profit targets are recalibrated from recent trade history. Tax-loss harvesting opportunities are identified.` },
                ].map(({ phase, time, desc }) => (
                  <div key={phase} className="bg-white border border-stone-200 rounded-xl p-5">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="font-semibold text-sm text-slate-900">{phase}</span>
                      <span className="text-xs text-stone-600">{time}</span>
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
              <p className="text-stone-600 text-sm leading-relaxed mb-6 max-w-md mx-auto">
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
                  className="px-6 py-2.5 rounded-xl border border-stone-500 bg-transparent hover:bg-stone-800 text-stone-200 font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-stone-500 focus:ring-offset-2 focus:ring-offset-slate-900"
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
            <Link href="/"         className="text-sm text-stone-600 hover:text-stone-900 transition-colors">Home</Link>
            <Link href="/methodology"     className="text-sm text-stone-600 hover:text-stone-900 transition-colors">How It Works</Link>
            <Link href="/performance"     className="text-sm text-stone-600 hover:text-stone-900 transition-colors">Performance</Link>
            <Link href="/#pricing" className="text-sm text-stone-600 hover:text-stone-900 transition-colors">Pricing</Link>
            <Link href="/login"           className="text-sm text-stone-600 hover:text-stone-900 transition-colors">Log In</Link>
          </div>
        </div>
        <p className="text-xs text-stone-600 leading-relaxed max-w-3xl">
          Winzinvest is systematic portfolio automation software. It automates rule-based execution,
          options position management, and risk monitoring. It does not provide investment advice,
          recommendations, or asset management services. Investing in equities and options involves
          substantial risk of loss. Past performance does not guarantee future results.
        </p>
      </footer>
    </div>
  );
}
