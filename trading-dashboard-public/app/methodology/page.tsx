/**
 * Methodology page — Bridgewater-style investment thesis + system transparency.
 *
 * Structure: Leads with the *investment thesis* (why systematic approaches
 *            outperform discretionary ones), then explains the system as the
 *            implementation of that thesis.
 *
 * Voice:     Reads like an investor letter from a systematic fund, not a
 *            product marketing page. Assumes an intelligent reader who may
 *            not be a quant. Explains concepts without dumbing them down.
 *
 * Category:  "Systematic portfolio automation" — never "trading bot,"
 *            "signal service," or "AI trading."
 */

import Link from 'next/link';
import { PublicNav } from '../components/PublicNav';

const SECTIONS = [
  { id: 'thesis',           label: 'Investment Thesis' },
  { id: 'framework',        label: 'Portfolio Framework' },
  { id: 'equity',           label: 'Equity Management' },
  { id: 'signal-edges',     label: 'Signal Confirmation' },
  { id: 'options-income',   label: 'Options Income' },
  { id: 'advanced-income',  label: 'Advanced Income' },
  { id: 'regime',           label: 'Regime Detection' },
  { id: 'risk',             label: 'Risk Management' },
  { id: 'analytics',        label: 'Trade Analytics' },
  { id: 'optimization',     label: 'Optimization' },
  { id: 'operations',       label: 'Daily Operations' },
];

type PageProps = {
  params?: Promise<Record<string, string | string[]>>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default function MethodologyPage(_props: PageProps) {
  return (
    <div className="min-h-screen bg-stone-50">

      <PublicNav />

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

            {/* Page header — leads with the thesis, not the product */}
            <header className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-3">Investment Methodology</div>
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

            {/* 1. Investment Thesis */}
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

            {/* 2. Portfolio Framework */}
            <section id="framework" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">02</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">Portfolio framework</h2>

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

            {/* 3. Equity Management */}
            <section id="equity" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">03</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">Equity portfolio management</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  The equity engine is the primary return driver, targeting 40%+ annual returns through
                  concentrated momentum trading. Rather than passively holding a diversified basket,
                  the system actively rotates through <strong>15–20 high-conviction positions</strong>,
                  entering on breakouts and cutting losers quickly — targeting a 3:1 reward-to-risk ratio
                  on each trade with 1.5% of equity risked per entry.
                </p>
                <p>
                  At a 45% win rate and 3:1 R/R across ~120 annual trades, the math alone supports
                  40%+ returns. The discipline to hold winners and cut losers consistently — without
                  emotional override — is what the automation provides.
                </p>
                <p>
                  <strong>Momentum strategies</strong> seek to own securities that are already trending upward
                  with strong relative strength compared to the broader market. The thesis is well-established
                  in academic research: securities that have outperformed recently tend to continue outperforming
                  over intermediate time horizons. The system screens for this pattern using a composite scoring
                  model that combines price momentum, volatility structure, relative strength, and volume characteristics —
                  then confirms each signal across multiple timeframes, boosts conviction for earnings catalysts,
                  and tilts capital toward the strongest sectors. These additional confirmation layers are
                  described in the next section.
                </p>
                <p>
                  <strong>Mean reversion strategies</strong> take the opposite approach — buying securities that
                  have experienced sharp short-term pullbacks while remaining in a longer-term uptrend. The thesis
                  is that short-term oversold conditions in structurally sound securities tend to correct quickly.
                  These positions are held for days, not weeks, with tight risk controls.
                </p>
                <p>
                  <strong>Pairs strategies</strong> identify historically correlated securities within the same
                  sector whose prices have diverged beyond a statistical threshold. The system goes long the
                  underperformer and short the outperformer, profiting when the spread reverts to its historical mean.
                  This is a market-neutral approach — returns are independent of overall market direction.
                </p>
              </div>

              <div className="bg-white border border-stone-200 rounded-xl p-6 mt-8">
                <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-4">How positions are managed</div>
                <div className="space-y-3">
                  {[
                    { label: 'Entry', desc: 'Positions are entered only when the quantitative screening criteria are fully satisfied. There is no discretionary override — if the score doesn\'t meet the threshold, the position is not taken.' },
                    { label: 'Position sizing', desc: 'Each position is sized based on the security\'s volatility (measured by Average True Range) and the portfolio\'s current risk budget. More volatile securities receive smaller positions. Sizing also adjusts based on the current market regime.' },
                    { label: 'Profit targets', desc: 'Each position has a defined profit target expressed as a multiple of its volatility. When the target is reached, the position is closed automatically. This removes the temptation to hold for more.' },
                    { label: 'Stop losses', desc: 'Every position has a hard stop-loss from the moment it is entered, plus a trailing stop that activates once the position reaches a defined profit threshold. The trailing stop locks in gains while allowing the position room to develop.' },
                    { label: 'Time limits', desc: 'Positions that have not reached their target or stop within a defined holding period are closed. This prevents capital from being tied up in ideas that aren\'t working.' },
                  ].map(({ label, desc }) => (
                    <div key={label} className="flex items-start gap-4 pb-3 border-b border-stone-100 last:border-0 last:pb-0">
                      <span className="text-xs font-semibold text-sky-600 uppercase tracking-wider w-24 shrink-0 pt-0.5">{label}</span>
                      <p className="text-sm text-stone-600 leading-relaxed">{desc}</p>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            <div className="border-t border-stone-200 mb-16" />

            {/* 3b. Signal Confirmation & Edge Enhancement */}
            <section id="signal-edges" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">03b</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">Signal confirmation and edge enhancement</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  Identifying momentum is necessary but not sufficient. A stock can show strong daily
                  momentum while its weekly trend is deteriorating — or its sector may be in structural
                  decline even as the individual name temporarily outperforms. Acting on a single-timeframe
                  signal without checking the broader context leads to entries that quickly reverse.
                </p>
                <p>
                  The platform addresses this through three additive confirmation layers that operate
                  on top of the core momentum screening. Each layer is grounded in well-documented
                  market structure research, and together they meaningfully improve the quality of
                  entries without changing the fundamental strategy.
                </p>
              </div>

              <div className="space-y-0 border border-stone-200 rounded-xl overflow-hidden mt-8">
                {[
                  {
                    num: '01',
                    title: 'Multi-timeframe confirmation',
                    body: 'Every candidate is scored across three timeframes: the weekly trend (65-day rate of change and price relative to the 50-day moving average), the daily trend (20-day momentum and price relative to the 20-day average), and an intraday proxy (5-day momentum slope). When all three timeframes align, the probability of a sustained move is significantly higher. When they conflict, the signal is downweighted or rejected. This is the same principle institutional trend-following funds use — they call it "timeframe convergence" — and it measurably reduces false entries.',
                  },
                  {
                    num: '02',
                    title: 'Post-earnings announcement drift',
                    body: 'Academic research has documented that stocks experiencing strong earnings surprises tend to drift in the direction of the surprise for days or weeks after the announcement. This is one of the most persistent anomalies in equity markets — driven by institutional investors who cannot fully rebalance on the announcement day. The system detects recent earnings events, measures the overnight gap and subsequent follow-through, and adds a conviction boost for entries that align with the drift direction. The boost decays linearly over ten days as the informational advantage fades.',
                  },
                  {
                    num: '03',
                    title: 'Sector relative strength overlay',
                    body: 'Not all sectors perform equally at any given time. Academic research on sector momentum shows that the top-performing sectors over a trailing quarter tend to continue outperforming in the near term. Rather than applying equal capital allocation across sectors, the platform ranks all eleven GICS sectors by 63-day relative strength and applies a sizing multiplier: top-ranked sectors receive 25% larger positions, bottom-ranked sectors receive 25% smaller positions. This transforms the sector framework from a passive cap into an active tilt toward where momentum is strongest — the same concept institutional allocators use when they "overweight" and "underweight" sectors.',
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
                  <strong>Design implication:</strong> These three layers are additive, not gating.
                  They do not prevent a trade from being taken — they modulate how much conviction and
                  capital the system allocates to it. A momentum setup with weekly, daily, and intraday
                  alignment, a recent earnings catalyst, and a top-ranked sector will receive substantially
                  more capital than the same momentum setup without those confirmations. The core strategy
                  remains unchanged; the edges improve its calibration.
                </p>
              </div>
            </section>

            <div className="border-t border-stone-200 mb-16" />

            {/* 4. Options Income */}
            <section id="options-income" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">04</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">Options income generation</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  The income engine generates recurring premium by writing options against the equity
                  portfolio. This is the same approach used by pension funds, endowments, and institutional
                  covered call strategies — but automated at the individual position level.
                </p>
                <p>
                  <strong>Covered calls</strong> are the primary income source. When the portfolio holds 100 or
                  more shares of a security, the system evaluates whether a covered call is appropriate based
                  on the implied volatility environment, the distance from nearby earnings or dividend dates,
                  and the portfolio&apos;s current options exposure. Calls are written at strikes far enough from the
                  current price to give the underlying room to appreciate, while still capturing meaningful premium.
                </p>
                <p>
                  <strong>Cash-secured puts</strong> are used to generate income on securities the portfolio
                  would like to own at a lower price. The system writes puts at prices below the current
                  market level — if the stock falls to that price, the portfolio acquires it at a discount;
                  if it doesn&apos;t, the premium is kept as income.
                </p>
                <p>
                  A distinctive feature of the platform is <strong>automatic position rolling</strong>.
                  When an option reaches a high percentage of its maximum profit before expiration, the system
                  closes it and immediately opens a new position at a fresh duration. This means the portfolio
                  is continuously generating income from the same holdings rather than waiting for expiration
                  and restarting the process manually.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-8">
                {[
                  { title: 'Why this works', body: 'Options premium is compensation for accepting short-term risk. The portfolio collects this premium systematically, on every eligible holding, on a continuous basis. Over time, this adds a meaningful second return stream that is partially independent of market direction.' },
                  { title: 'Dividend protection', body: 'Before writing any covered call, the system checks whether an ex-dividend date falls within the option\'s window. If the dividend exceeds a threshold percentage of the call premium, the call is skipped — protecting the investor\'s dividend income.' },
                  { title: 'Earnings awareness', body: 'Options activity is automatically paused around earnings announcements. The implied volatility expansion before earnings can make options seem attractive, but the binary risk of a large post-earnings move makes the risk-reward unfavorable for the premium seller.' },
                ].map(({ title, body }) => (
                  <div key={title} className="bg-white border border-stone-200 rounded-xl p-5">
                    <div className="font-semibold text-sm text-slate-900 mb-2">{title}</div>
                    <p className="text-xs text-stone-500 leading-relaxed">{body}</p>
                  </div>
                ))}
              </div>
            </section>

            <div className="border-t border-stone-200 mb-16" />

            {/* 4b. Advanced Income Strategies */}
            <section id="advanced-income" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">04b</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">Advanced income strategies</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  Beyond the core covered call and cash-secured put engine, the platform deploys several
                  advanced techniques to maximize income across different market environments and to manage
                  existing positions more precisely.
                </p>
              </div>

              <div className="space-y-4 mt-8">
                {[
                  {
                    title: 'VIX-responsive contract sizing',
                    body: 'When implied volatility is elevated (IV rank ≥ 0.70), the platform automatically scales contract size upward — selling more premium during the exact windows when premium is richest. When volatility is subdued, contract size contracts to reduce risk. This captures the volatility risk premium more aggressively during spikes rather than treating every session equally.',
                    accent: 'border-l-sky-600',
                  },
                  {
                    title: 'Calendar and diagonal spread rolling',
                    body: 'When a short covered call reaches its profit target, the system evaluates three roll strategies before reopening. If the stock has rallied significantly above the strike (>5%), a diagonal roll is executed — the new position is placed at a higher, more out-of-the-money strike using a farther expiration to reduce delta and collect additional credit. If the stock is near ATM with significant time remaining, a calendar spread captures additional time decay. In all other cases, a standard same-strike roll is applied.',
                    accent: 'border-l-green-600',
                  },
                  {
                    title: 'Delta drift monitoring',
                    body: 'Short call positions are continuously monitored for delta creep. When a covered call\'s delta exceeds 0.50 — indicating the position has moved deep in-the-money — an urgent alert fires immediately. This is the earliest warning that assignment risk is elevated. The alert includes the specific delta, days to expiration, and a suggested roll action, giving the investor time to act before assignment becomes likely.',
                    accent: 'border-l-red-600',
                  },
                  {
                    title: 'Partial profit scaling',
                    body: 'Rather than holding every equity position to the full take-profit target, the platform allows partial exits at intermediate thresholds. When a position reaches 2× ATR in profit, half the position is closed and the proceeds are returned to the cash pool for redeployment. The remaining half continues to run with a tightened trailing stop. This improves realized win rates and reduces variance without abandoning good positions prematurely.',
                    accent: 'border-l-amber-500',
                  },
                  {
                    title: 'Dividend capture screening',
                    body: 'The platform continuously scans a universe of high-yield equities for upcoming ex-dividend dates. Stocks meeting defined filters — yield threshold, sufficient volume, confirmed uptrend, and adequate distance from earnings — are flagged as dividend capture candidates with calculated entry prices, stop-loss levels, and expected capture rates. This creates a systematic process for what would otherwise be a manual, calendar-driven activity.',
                    accent: 'border-l-green-600',
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

            {/* 5. Regime Detection */}
            <section id="regime" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">05</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">Market regime detection</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  Not all market environments are the same, and a strategy that works well in a trending
                  market may underperform in a volatile or directionless one. The platform addresses this
                  through a regime detection system that evaluates current market conditions and adjusts
                  portfolio behavior accordingly.
                </p>
                <p>
                  The system operates <strong>two independent classification layers</strong>. The first evaluates
                  the broad equity market trend and volatility environment using price-based and volatility-based
                  indicators. This determines which strategies are active at any given time — for example,
                  momentum strategies may be fully active in a strong uptrend but partially or fully paused
                  during a downturn.
                </p>
                <p>
                  The second layer evaluates macro-level stress using a scored composite of independently
                  sourced indicators: <strong>VIX term structure</strong> (contango vs.
                  backwardation), <strong>HY credit spreads</strong> (BAMLH0A0HYM2 via FRED),{' '}
                  <strong>real yields</strong> (10-year TIPS via FRED), <strong>financial conditions</strong>{' '}
                  (Chicago Fed NFCI via FRED), and <strong>industrial production</strong> (IPMAN via FRED as a
                  manufacturing health proxy). This layer doesn&apos;t turn strategies on or off — instead, it
                  adjusts how aggressively the portfolio takes new positions. In benign conditions, the system
                  invests at full capacity. As stress indicators rise, position sizes shrink and entry criteria
                  tighten.
                </p>
                <p>
                  <strong>Commodity supply-chain tracking</strong> extends the macro layer across seven futures and
                  indices — each representing a distinct economic transmission chain:
                </p>
                <ul className="list-disc list-inside text-sm space-y-1 my-2 text-stone-600 ml-4">
                  <li><strong>Oil (CL=F)</strong> → petrochemicals, shipping costs, Energy sector multiplier (0.80×–1.35×)</li>
                  <li><strong>Wheat (ZW=F) + Natural Gas (NG=F)</strong> → fertilizer feedstock → food costs → <em>food_chain_alert</em> (Consumer Staples 0.85× penalty)</li>
                  <li><strong>Copper (HG=F)</strong> → construction &amp; industrial activity; surge boosts Materials/Industrials, collapse is a demand warning</li>
                  <li><strong>Corn (ZC=F) + Soybeans (ZS=F)</strong> → animal feed margins → <em>livestock_chain_alert</em> (Consumer Staples 0.88×, Consumer Discretionary 0.92×)</li>
                  <li><strong>USD Index (DX-Y.NYB)</strong> → strong dollar suppresses commodity prices (Materials/Energy 0.90×); weak dollar inflates them (1.10×)</li>
                </ul>
                <p>
                  Two compound alerts fire when multiple chains are stressed simultaneously: <em>food_chain_alert</em> (oil + grain)
                  and <em>livestock_chain_alert</em> (corn/soy). When both are active, Consumer Staples receives a combined 0.80× penalty.
                </p>
                <p>
                  <strong>Real-time news sentiment</strong> (via the Marketaux API) monitors headlines for portfolio
                  holdings and macro keywords — oil, tariffs, war, sanctions, wheat, fertilizer, and more. Strongly
                  negative sentiment feeds into the regime score, and the worst headlines are surfaced as dashboard
                  alerts so nothing is missed between check-ins.
                </p>
                <p>
                  Both layers are evaluated multiple times per trading day. When conditions change, the
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
                    'Many investors attempt to time markets manually, which introduces exactly the kind of emotional decision-making that hurts performance. The regime system provides the same kind of adaptive behavior through a rule-based process.',
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

            {/* 6. Risk Management */}
            <section id="risk" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">06</div>
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
                    title: 'Drawdown circuit breaker',
                    body: 'The system monitors portfolio performance throughout the day. As losses accumulate, it moves through graduated response tiers: first reducing position sizes, then pausing new entries, and finally halting all activity. Each tier is defined by a specific drawdown threshold. The system resets at the start of each trading day.',
                    accent: 'border-l-red-600',
                  },
                  {
                    title: 'Position and concentration limits',
                    body: 'No single position can exceed a defined percentage of the portfolio. No sector can exceed a defined concentration limit. These constraints are checked before every order. A position that would violate either limit is simply not taken, regardless of how attractive the opportunity appears.',
                    accent: 'border-l-sky-600',
                  },
                  {
                    title: 'Correlation monitoring',
                    body: 'Diversification is only valuable if positions actually behave independently. The system maintains a rolling correlation matrix across portfolio holdings and flags situations where nominally diversified positions are moving together — creating hidden concentration risk.',
                    accent: 'border-l-orange-500',
                  },
                  {
                    title: 'Emergency halt',
                    body: 'A PIN-protected kill switch is accessible from the dashboard at all times. It can be activated manually or triggered automatically by the drawdown circuit breaker. When active, all portfolio activity stops immediately. The system remains halted until the investor explicitly clears it.',
                    accent: 'border-l-red-600',
                  },
                  {
                    title: 'Event-based protection',
                    body: 'Earnings announcements and ex-dividend dates create periods of elevated risk for options positions. The system automatically identifies these windows and suspends options activity around them, preventing the portfolio from taking positions where the risk-reward is temporarily distorted.',
                    accent: 'border-l-green-600',
                  },
                  {
                    title: 'Commodity supply-chain monitoring',
                    body: 'Seven futures and indices are tracked across distinct economic transmission chains: oil (energy/shipping), wheat + natural gas (fertilizer-to-food), copper (construction/industrial health), corn + soybeans (livestock feed margins), and the USD index (commodity price inflation/deflation). Each drives specific sector multipliers, and two compound signals fire when multiple chains are stressed simultaneously — food_chain_alert and livestock_chain_alert.',
                    accent: 'border-l-orange-500',
                  },
                  {
                    title: 'Real-time news sentiment',
                    body: 'The Marketaux API provides continuous headline monitoring across 5,000+ news sources. The system analyzes sentiment for portfolio holdings and macro-relevant keywords (oil, tariffs, war, wheat, fertilizer). Strongly negative sentiment automatically feeds into the regime score, and the worst headlines appear as dashboard alerts.',
                    accent: 'border-l-sky-600',
                  },
                  {
                    title: 'Opening gap monitor',
                    body: 'Two minutes after each open, the system scans every long position for an opening gap against the prior close. Gaps of 3% or more trigger an immediate CRITICAL alert — these moves are rarely intraday reversals and warrant prompt action. Gaps between 1.5–3% generate a WARNING. Gaps up of 2%+ send an informational alert, since a gap up on a covered call position may suddenly increase assignment risk before the options engine runs.',
                    accent: 'border-l-red-600',
                  },
                  {
                    title: 'Ratcheting ATR stops',
                    body: 'Every morning at 9:35 ET, the system recalculates stop prices for all open positions using the current 14-period Average True Range. Stops only ever move up — a winning position\'s stop ratchets upward as the stock climbs, locking in gains. A losing position\'s stop stays where it was set. The system also automatically creates stop entries for any new position that does not yet have one, ensuring no position is ever unprotected.',
                    accent: 'border-l-orange-500',
                  },
                  {
                    title: 'Gap grace period',
                    body: 'When a stop-loss is triggered at the open, the system distinguishes between a genuine breakdown and a temporary shakeout. For gaps smaller than 3% below the prior close, the system starts a 15-minute grace period instead of executing immediately — giving the position time to recover back above the stop. For gaps of 3% or more, the system treats the move as a real directional break and executes the exit without delay. This prevents selling at the exact low of an opening fake-out while still protecting against true breakdowns.',
                    accent: 'border-l-orange-500',
                  },
                  {
                    title: 'Macro-adaptive cash management',
                    body: 'The cash deployment threshold adjusts automatically based on the macro environment. In normal conditions, the system deploys idle cash when it exceeds 15% of portfolio value. When a defensive macro event is active — such as SPY trading below its 200-day moving average — the threshold automatically rises to 50%, keeping more capital in reserve. This means the system stops pushing for full deployment when conditions are genuinely uncertain, without any manual override required.',
                    accent: 'border-l-sky-600',
                  },
                  {
                    title: 'Sector ETF hedging',
                    body: 'In STRONG_DOWNTREND and CHOPPY regimes, the system evaluates sector-level exposure against the portfolio. When a sector is over-concentrated and the macro regime is defensive, the platform automatically purchases a partial inverse ETF hedge for that sector (e.g., DRIP for Energy, SRS for Real Estate). As the regime recovers to MIXED or RISK_ON, existing hedges are automatically closed — protecting capital during downturns without permanent drag in recoveries.',
                    accent: 'border-l-red-600',
                  },
                  {
                    title: 'Re-entry watchlist',
                    body: 'After any position is stopped out, the system continues monitoring the symbol for up to 30 days. Re-entry conditions are checked daily: price must have recovered above the stop-loss exit price with at least a 2% buffer, the stock must be trading above its 20-day SMA, and RSI must be above 50 — confirming bullish momentum has genuinely returned. When all three conditions are met simultaneously, an alert fires. This prevents re-entering a recovered name too early (catching a dead-cat bounce) while ensuring genuine recoveries are not missed.',
                    accent: 'border-l-green-600',
                  },
                  {
                    title: 'Complete operational record',
                    body: 'Every action the system takes — every trade, parameter update, regime transition, and risk event — is logged in a permanent audit trail. This record is available through the dashboard for review, performance attribution, and tax reporting.',
                    accent: 'border-l-sky-600',
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

            {/* 7. Trade Analytics */}
            <section id="analytics" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">07</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">Trade analytics and feedback loop</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  Systematic strategies require systematic feedback. Without a structured way to review
                  what is and isn&apos;t working, even a good process drifts. The platform includes a
                  dedicated analytics layer that processes every completed trade and surfaces patterns
                  that would be invisible in a raw trade log.
                </p>
                <p>
                  The analytics engine queries the live trade database after each session and computes a
                  standardized performance summary. The output covers five dimensions:
                </p>
              </div>

              <div className="space-y-0 border border-stone-200 rounded-xl overflow-hidden mt-8">
                {[
                  { num: '01', title: 'Strategy-level attribution', body: 'Win rate, average R-multiple, and total PnL broken down by strategy type — momentum longs, shorts, mean reversion, pairs, covered calls, CSPs, and others. This makes it immediately clear which components of the portfolio are contributing and which are underperforming.' },
                  { num: '02', title: 'Regime-conditional performance', body: 'The same attribution broken out by the market regime that was active when each trade was entered. This reveals whether a strategy that appears weak overall is actually performing fine in its intended regime and struggling only when deployed outside it.' },
                  { num: '03', title: 'Hold time analysis', body: 'Average hold time for winners versus losers, by strategy type. A pattern of winners being held too short or losers being held too long is often invisible in aggregate returns but shows clearly in hold time comparison. This informs time-stop calibration.' },
                  { num: '04', title: 'Exit reason distribution', body: 'How positions actually exit — profit target, stop loss, time stop, manual, or roll — and whether winners and losers are exiting through the expected mechanism. If most winners are hitting time stops rather than profit targets, the take-profit level may be set too far.' },
                  { num: '05', title: 'Monthly PnL and R-multiple distribution', body: 'A month-by-month view of realized gains and losses, plus a histogram of trade outcomes expressed as R-multiples. The R-multiple distribution is the most important diagnostic — it shows directly whether the theoretical 3:1 reward-to-risk ratio is being realized in practice.' },
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
                  <strong>Design implication:</strong> The analytics dashboard is not a reporting tool — it is a
                  calibration tool. It closes the feedback loop between what the strategy is designed to do and
                  what it is actually doing. The Friday weekly optimization cycle uses this data as an input:
                  when the R-multiple distribution has drifted from target, parameter adjustments are informed
                  by evidence, not intuition.
                </p>
              </div>
            </section>

            <div className="border-t border-stone-200 mb-16" />

            {/* 9. Optimization */}
            <section id="optimization" className="mb-16">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">08</div>
              <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">Continuous optimization</h2>

              <div className="space-y-4 text-sm text-stone-600 leading-relaxed">
                <p>
                  Markets change. What worked well six months ago may not be optimal today.
                  The platform addresses this through a weekly optimization cycle that recalibrates
                  strategy parameters based on recent portfolio performance.
                </p>
                <p>
                  Each week, the system evaluates multiple parameter combinations across the current
                  portfolio holdings. It tests different strike distances for options, different holding
                  periods, and different profit targets — then ranks the results by risk-adjusted
                  performance. The top-performing combinations are surfaced in the dashboard for review,
                  giving the investor data-backed recommendations rather than requiring manual analysis.
                </p>
                <p>
                  This is not prediction. The system does not try to forecast which parameters will
                  work best in the future. It identifies which parameters have been producing the
                  best risk-adjusted results recently. Over time, this creates a natural adaptation
                  to changing market conditions guided by evidence rather than intuition.
                </p>
                <p>
                  The backtester runs automatically after market hours each Friday and the results
                  are available on the Strategy page by Monday. Parameter changes are applied manually
                  after reviewing the recommendations — the investor retains final authority over any
                  configuration change.
                </p>
              </div>
            </section>

            <div className="border-t border-stone-200 mb-16" />

            {/* 10. Daily Operations */}
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
                  { phase: 'Pre-market', time: 'Before the open', desc: 'The system reviews the portfolio, runs momentum and bearish screeners, runs the PEAD screener for post-earnings drift setups, runs the dividend capture screener for upcoming ex-dividend opportunities, and prepares orders for the session. Regime conditions from the previous close are re-evaluated.' },
                  { phase: 'Market open', time: 'At the open', desc: 'Prepared orders are executed. New equity positions are entered based on overnight screening results. Portfolio adjustments from the previous session\'s analysis are applied. Stop-loss triggers are checked against current prices. The sector hedge executor evaluates whether any hedges need to be opened or closed based on the current regime.' },
                  { phase: 'Gap scan', time: '2 min after open', desc: 'Every long position is scanned for an opening gap against the prior close. Significant gaps down trigger immediate alerts (≥3%) or warnings (≥1.5%). Gap ups on covered-call positions flag potential early assignment risk. For small gap-down stops, a 15-minute grace period allows the position time to recover before the exit fires.' },
                  { phase: 'Stop ratchet', time: '5 min after open', desc: 'Stop prices are recalculated from current ATR data for every open position. Stops only ever move up — a winning position\'s stop trails the stock higher each morning. Any position opened since the last run that lacks a stop gets one created automatically.' },
                  { phase: 'Options management', time: 'Shortly after open', desc: 'The options engine evaluates each holding for covered call and put opportunities. New income positions are opened where criteria are met. Existing positions are checked against profit targets and risk limits.' },
                  { phase: 'VWAP reclaim scan', time: '10:00–12:00 ET', desc: 'The VWAP reclaim scanner identifies stocks that gapped down at the open but have since reclaimed their session VWAP with volume confirmation. These setups represent potential intraday reversals in strong names where the gap was exaggerated by opening order flow rather than fundamental deterioration.' },
                  { phase: 'Continuous monitoring', time: 'Throughout the day', desc: 'The system monitors all open positions against their defined risk parameters — profit targets, partial exits at 2× ATR, stop losses, and time limits. Options positions are evaluated for rolling opportunities. Delta drift is monitored every 30 minutes for short calls. Drawdown levels are tracked. The daily email report includes a stop-price column for every position, colour-coded by distance from the current price.' },
                  { phase: 'Midday regime check', time: 'Early afternoon', desc: 'Both regime layers are re-evaluated with current market data. If conditions have changed since the morning, strategy allocation and position sizing adjust for the remainder of the session.' },
                  { phase: 'Re-entry scan', time: 'Daily after ATR ratchet', desc: 'The re-entry watchlist is evaluated for all stopped-out positions from the last 30 days. Recovery conditions are checked: price above exit level plus buffer, above 20-day SMA, and RSI above 50. When all three align, an alert is sent. Entries that have expired beyond the 30-day lookback are pruned automatically.' },
                  { phase: 'End of day', time: 'At the close', desc: 'A complete portfolio snapshot is taken. The daily performance report is generated. The trade analytics engine updates win rates, R-multiples, and attribution data for the analytics dashboard. All positions, risk metrics, and system events are logged.' },
                  { phase: 'Weekly calibration', time: 'Friday after close', desc: 'The optimization engine runs its full parameter sweep across the top holdings. The trade analytics report is regenerated with the full week\'s data. Results are surfaced on the Strategy and Analytics pages. Parameter changes are applied manually after review.' },
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

            {/* Closing / Disclaimer */}
            <section className="mb-16">
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
                  href="/landing#pricing"
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
            <Link href="/landing"         className="text-sm text-stone-400 hover:text-stone-600 transition-colors">Home</Link>
            <Link href="/research"        className="text-sm text-stone-400 hover:text-stone-600 transition-colors">Research</Link>
            <Link href="/performance"     className="text-sm text-stone-400 hover:text-stone-600 transition-colors">Performance</Link>
            <Link href="/landing#pricing" className="text-sm text-stone-400 hover:text-stone-600 transition-colors">Pricing</Link>
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
