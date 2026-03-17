'use client';

/**
 * Landing page — follows 010-mission-control-design-system.mdc
 *
 * Typography:  Playfair Display (serif) for headlines
 *              Inter (sans-serif) for body, labels, UI
 *              JetBrains Mono for precision data
 * Color:       bg-stone-50 page · bg-white cards · border-stone-200
 *              text-slate-900 primary · text-stone-600 secondary · text-stone-400 tertiary
 *              text-sky-600 primary accent
 *
 * Positioning: Institutional-style portfolio automation for self-directed investors.
 *              Not a trading bot. Not a signal service. Not a retail charting tool.
 *
 * Category:   "Systematic portfolio automation" — the canonical category term.
 *              In body copy, "automated portfolio management" is acceptable.
 *              Never: "trading bot," "trading system," "signal service," "AI trading."
 */

import Link from 'next/link';
import { use, useState } from 'react';
import { PublicNav } from '../components/PublicNav';

const THREE_PILLARS = [
  {
    accent: 'border-t-sky-600',
    label: 'Growth',
    title: 'Systematic equity portfolio management',
    body: 'The platform evaluates hundreds of securities on a continuous basis and manages equity positions according to defined momentum and mean reversion criteria. Entries, exits, and position sizing are handled automatically — the investor sets the parameters, the system manages the portfolio.',
  },
  {
    accent: 'border-t-green-600',
    label: 'Income',
    title: 'Automated options income generation',
    body: 'Covered calls and cash-secured puts are written systematically against portfolio holdings to generate recurring premium income. Each position is opened, monitored, rolled, and closed according to predefined rules — no daily management required from the investor.',
  },
  {
    accent: 'border-t-orange-500',
    label: 'Protection',
    title: 'Regime-aware risk management',
    body: 'The system continuously evaluates market conditions and adjusts portfolio exposure accordingly. When conditions deteriorate, the platform reduces activity automatically. Risk limits, drawdown controls, and sector constraints are enforced at every step.',
  },
];

const DAILY_CYCLE = [
  { time: '09:00 ET', label: 'Pre-market',   desc: 'Portfolio review and opportunity screening' },
  { time: '09:30 ET', label: 'Open',         desc: 'Automated portfolio adjustments' },
  { time: '10:00 ET', label: 'Options',      desc: 'Income positions managed' },
  { time: 'Ongoing',  label: 'Monitoring',   desc: 'Positions and risk limits tracked' },
  { time: '12:45 ET', label: 'Regime check', desc: 'Market conditions re-evaluated' },
  { time: '16:00 ET', label: 'Close',        desc: 'Daily portfolio report generated' },
  { time: 'Weekly',   label: 'Optimization', desc: 'Strategy parameters recalibrated' },
];

const RISK_CONTROLS = [
  { borderClass: 'border-l-red-600',    title: 'Drawdown protection',    body: 'A graduated response system automatically reduces portfolio activity as drawdowns develop. Position sizes decrease first, then new investments pause, then the system halts entirely. Protection scales with severity.' },
  { borderClass: 'border-l-sky-600',    title: 'Position limits',        body: 'Every investment must pass concentration checks, sector caps, and portfolio-level exposure limits before it can be executed. These constraints are structural — they cannot be overridden in the moment.' },
  { borderClass: 'border-l-orange-500', title: 'Emergency halt',         body: 'A PIN-protected kill switch is always accessible from the dashboard. It can also activate automatically when drawdown thresholds are reached. All portfolio activity stops immediately until the investor clears it.' },
  { borderClass: 'border-l-sky-600',    title: 'Diversification monitoring', body: 'The platform maintains a rolling correlation analysis across portfolio holdings. When positions that appear diversified begin moving together, the system flags the concentration risk.' },
  { borderClass: 'border-l-green-600',  title: 'Event awareness',        body: 'Options activity is automatically paused around earnings announcements and ex-dividend dates where assignment risk would create unfavorable outcomes for the investor.' },
  { borderClass: 'border-l-sky-600',    title: 'Full audit trail',       body: 'Every portfolio action, parameter change, and risk event is logged. Investors have a complete record of what happened, when it happened, and why — for review, attribution, and tax reporting.' },
];

const PLATFORM_HANDLES = [
  'Portfolio construction and rebalancing',
  'Options income management and position rolling',
  'Risk monitoring and drawdown protection',
  'Market regime detection and exposure adjustment',
  'Performance reporting and attribution',
];

const REPLACES = [
  'Manually entering and managing trades throughout the day',
  'Tracking options positions in spreadsheets',
  'Watching markets to decide when to act',
  'Interpreting market conditions to adjust exposure',
  'Assembling performance reports from multiple sources',
  'Reviewing and updating strategy parameters by hand',
];

const INVESTOR_PROFILE = [
  'Manage meaningful self-directed portfolios',
  'Want systematic options income on their holdings',
  'Value consistent process over individual trade decisions',
  'Prefer automated management without building custom technology',
  'Have or are willing to open an Interactive Brokers account',
];

/**
 * Pricing is based on portfolio size, not feature restrictions.
 * All plans include the same core system and the same full feature set.
 * extras[] = service-level differences only (onboarding style, support tier, account count).
 */
const PRICING_PLANS = [
  {
    name: 'Investor',
    price: '$149',
    period: '/month',
    portfolioRange: 'Up to $250K portfolio',
    annualEquiv: '$1,788 / year',
    tagline: 'Full automation for serious self-directed investors starting to automate their portfolio.',
    cta: 'Get Started',
    ctaStyle: 'border border-stone-200 bg-white hover:bg-stone-50 text-slate-900',
    popular: false,
    accent: 'border-t-stone-300',
    accounts: '1 brokerage account',
    extras: [
      'Standard onboarding',
      'Standard support',
    ],
  },
  {
    name: 'Professional',
    price: '$349',
    period: '/month',
    portfolioRange: '$250K – $1M portfolio',
    annualEquiv: '$4,188 / year',
    tagline: 'For larger portfolios where automation significantly reduces operational complexity.',
    cta: 'Get Started',
    ctaStyle: 'bg-sky-600 hover:bg-sky-700 text-white',
    popular: true,
    accent: 'border-t-sky-600',
    accounts: 'Up to 2 brokerage accounts',
    extras: [
      'Guided onboarding',
      'Priority support',
    ],
  },
  {
    name: 'Private Client',
    price: '$799',
    period: '/month',
    portfolioRange: '$1M – $5M portfolio',
    annualEquiv: '$9,588 / year',
    tagline: 'For high-net-worth investors running significant capital through automated strategies.',
    cta: 'Get Started',
    ctaStyle: 'border border-stone-200 bg-white hover:bg-stone-50 text-slate-900',
    popular: false,
    accent: 'border-t-slate-700',
    accounts: 'Up to 5 brokerage accounts',
    extras: [
      'Concierge onboarding',
      'Priority support',
    ],
  },
  {
    name: 'Institutional',
    price: 'Custom',
    period: 'pricing',
    portfolioRange: '$5M+ portfolio',
    annualEquiv: 'Contact us',
    tagline: 'For family offices, RIAs, and institutional-style deployments requiring custom configuration.',
    cta: 'Inquire',
    ctaStyle: 'border border-stone-200 bg-white hover:bg-stone-50 text-slate-900',
    popular: false,
    accent: 'border-t-stone-200',
    accounts: 'Multi-account deployments',
    extras: [
      'Bespoke onboarding',
      'Dedicated support with SLA',
    ],
  },
];

/** Core capabilities included in every plan — differentiation is portfolio scale, not feature gates. */
const INCLUDED_IN_ALL = [
  'Automated portfolio execution via IBKR',
  'Momentum equity strategies (long & short)',
  'Options income automation (covered calls + CSPs)',
  'Regime-aware risk management',
  'Drawdown circuit breaker and kill switch',
  'Position limits and sector concentration controls',
  'Automated options roll management',
  'Full analytics, attribution, and performance history',
  'Daily portfolio reporting and audit trail',
  'Tax-loss harvesting workflow',
];

const FAQ_ITEMS = [
  {
    q: 'Why is pricing based on portfolio size?',
    a: 'The system manages a live portfolio. As portfolio size grows, the operational complexity and the value of disciplined automation both increase. Pricing aligned with portfolio scale reflects the value delivered — not arbitrary feature restrictions. All plans include the same core system.',
  },
  {
    q: 'Are features restricted by plan?',
    a: 'No. Every plan includes the full automation engine — equity strategies, options income, regime detection, risk controls, analytics, and reporting. The difference between plans is portfolio scale, number of brokerage accounts, onboarding style, and support level. No capabilities are gated by tier.',
  },
  {
    q: 'Which plan should I choose?',
    a: 'Select the tier aligned with the size of the portfolio you plan to automate. Investor is designed for portfolios up to $250K. Professional for $250K to $1M. Private Client for $1M to $5M. If you manage multiple accounts or portfolios above $5M, contact us about Institutional pricing.',
  },
  {
    q: 'How does this compare to hiring a wealth manager?',
    a: 'A traditional wealth manager typically charges around 1% of assets annually. On a $500K portfolio that is approximately $5,000 per year — and the investor gives up control of day-to-day decisions. Winzinvest provides automated portfolio infrastructure at a fraction of that cost, while the investor retains full ownership and control of their brokerage account.',
  },
  {
    q: 'What is Winzinvest?',
    a: 'Winzinvest is a systematic portfolio automation platform for self-directed investors. It manages equity positions, generates options income, enforces risk controls, and adapts to market conditions — all running automatically through your brokerage account. It is not a signal service, and it does not provide investment advice.',
  },
  {
    q: 'How is this different from a robo-advisor?',
    a: 'Robo-advisors typically manage passive index allocations. Winzinvest automates active portfolio strategies — including systematic equity selection, options income generation, and regime-aware risk management — while the investor retains full ownership and control of their brokerage account.',
  },
  {
    q: 'Does Winzinvest provide investment advice?',
    a: 'No. Winzinvest is software that automates the execution of investor-defined portfolio rules. It does not recommend securities, allocations, or strategies. All investment decisions and risk parameters are determined by the investor.',
  },
  {
    q: 'What brokerage account do I need?',
    a: 'An Interactive Brokers account is required for automated execution. Portfolio Margin access is recommended for the full capability set but is not required to get started.',
  },
  {
    q: 'How does the platform protect my portfolio in a downturn?',
    a: 'The drawdown protection system operates on a graduated basis. As losses develop, the platform first reduces position sizes, then pauses new investments, and finally halts all activity. This progressive response is designed to preserve capital without abrupt, all-or-nothing behavior.',
  },
  {
    q: 'What are the risks?',
    a: 'Investing in equities and options involves substantial risk of loss. Systematic strategies can and do underperform. Past results do not indicate future performance. Winzinvest is systematic portfolio automation software — outcomes depend on market conditions, strategy parameters, and capital invested.',
  },
];

/** Tier lookup for the pricing calculator. */
const CALCULATOR_TIERS: Array<{ maxAum: number; name: string; monthly: number }> = [
  { maxAum: 250_000,   name: 'Investor',       monthly: 149 },
  { maxAum: 1_000_000, name: 'Professional',   monthly: 349 },
  { maxAum: 5_000_000, name: 'Private Client', monthly: 799 },
  { maxAum: Infinity,  name: 'Institutional',  monthly: 0   },
];

function getCalcTier(aum: number) {
  return CALCULATOR_TIERS.find((t) => aum <= t.maxAum) ?? CALCULATOR_TIERS[CALCULATOR_TIERS.length - 1];
}

function fmt$(n: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);
}

function PricingCalculator() {
  const [aum, setAum] = useState(500_000);
  const tier = getCalcTier(aum);
  const wmAnnual = Math.round(aum * 0.01);
  const winzAnnual = tier.monthly * 12;
  const savings = wmAnnual - winzAnnual;
  const pctSaved = wmAnnual > 0 ? Math.round((savings / wmAnnual) * 100) : 0;
  const isInstitutional = tier.monthly === 0;

  const STEPS = [50_000, 100_000, 250_000, 500_000, 750_000, 1_000_000, 2_000_000, 5_000_000];
  const sliderIdx = STEPS.findIndex((s) => s >= aum);
  const resolvedIdx = sliderIdx === -1 ? STEPS.length - 1 : sliderIdx;

  return (
    <div className="border border-stone-200 rounded-xl bg-white p-7">
      <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-1">Portfolio cost calculator</div>
      <p className="text-sm text-stone-600 leading-relaxed mb-6">
        See how Winzinvest compares to traditional wealth management fees for your portfolio size.
      </p>

      {/* Slider */}
      <div className="mb-6">
        <div className="flex items-baseline justify-between mb-2">
          <label className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Portfolio size</label>
          <span className="font-serif text-2xl font-bold text-slate-900">{fmt$(aum)}</span>
        </div>
        <input
          type="range"
          min={0}
          max={STEPS.length - 1}
          step={1}
          value={resolvedIdx}
          onChange={(e) => setAum(STEPS[parseInt(e.target.value, 10)])}
          className="w-full h-1.5 rounded-full bg-stone-200 appearance-none cursor-pointer accent-sky-600"
          aria-label="Portfolio size slider"
        />
        <div className="flex justify-between text-xs text-stone-400 mt-1.5">
          <span>$50K</span>
          <span>$1M</span>
          <span>$5M+</span>
        </div>
      </div>

      {/* Results */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-xl border border-stone-200 bg-stone-50 p-5">
          <div className="text-xs font-semibold uppercase tracking-wider text-stone-400 mb-1">Wealth manager</div>
          <div className="font-serif text-2xl font-bold text-slate-900 mb-0.5">{fmt$(wmAnnual)}</div>
          <div className="text-xs text-stone-400">≈ 1% AUM annually</div>
        </div>
        <div className={`rounded-xl border p-5 ${isInstitutional ? 'border-stone-200 bg-stone-50' : 'border-sky-200 bg-sky-50'}`}>
          <div className="text-xs font-semibold uppercase tracking-wider text-sky-600 mb-1">
            Winzinvest · {tier.name}
          </div>
          {isInstitutional ? (
            <>
              <div className="font-serif text-2xl font-bold text-slate-900 mb-0.5">Custom</div>
              <div className="text-xs text-stone-400">Contact us for Institutional pricing</div>
            </>
          ) : (
            <>
              <div className="font-serif text-2xl font-bold text-sky-700 mb-0.5">{fmt$(winzAnnual)}</div>
              <div className="text-xs text-stone-400">{fmt$(tier.monthly)} / month · flat fee</div>
            </>
          )}
        </div>
        {!isInstitutional && (
          <div className={`rounded-xl border p-5 ${savings > 0 ? 'border-green-200 bg-green-50' : 'border-stone-200 bg-stone-50'}`}>
            <div className="text-xs font-semibold uppercase tracking-wider text-green-600 mb-1">Annual savings</div>
            <div className={`font-serif text-2xl font-bold mb-0.5 ${savings > 0 ? 'text-green-700' : 'text-slate-900'}`}>
              {savings >= 0 ? fmt$(savings) : '—'}
            </div>
            <div className="text-xs text-stone-400">{savings > 0 ? `${pctSaved}% less than wealth mgmt` : 'Custom pricing at this scale'}</div>
          </div>
        )}
        {isInstitutional && (
          <div className="rounded-xl border border-stone-200 bg-stone-50 p-5">
            <div className="text-xs font-semibold uppercase tracking-wider text-stone-400 mb-1">Annual savings</div>
            <div className="font-serif text-2xl font-bold text-slate-900 mb-0.5">Significant</div>
            <div className="text-xs text-stone-400">Contact us to discuss Institutional pricing</div>
          </div>
        )}
      </div>

      <p className="text-xs text-stone-400 mt-4 leading-relaxed">
        Wealth manager estimate based on an industry-standard 1% annual AUM fee. Actual fees vary.
        Winzinvest is software, not asset management — fees are fixed and do not scale with portfolio returns.
      </p>
    </div>
  );
}

type PageProps = {
  params?: Promise<Record<string, string | string[]>>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

const EMPTY = Promise.resolve({});

export default function LandingPage(props: PageProps) {
  use(props.params ?? EMPTY);
  use(props.searchParams ?? EMPTY);
  const [faqOpen, setFaqOpen] = useState<Set<number>>(new Set([0]));

  return (
    <div className="min-h-screen bg-stone-50">

      <PublicNav />

      {/* Hero */}
      <section className="max-w-7xl mx-auto px-8 pt-24 pb-20">
        <div className="max-w-2xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-stone-200 bg-white text-xs font-semibold text-stone-500 uppercase tracking-wider mb-8">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
            Systematic Portfolio Automation
          </div>

          <h1 className="font-serif text-5xl font-bold text-slate-900 leading-tight tracking-tight mb-6">
            Institutional-style portfolio automation<br />
            <span className="text-sky-600">for self-directed investors.</span>
          </h1>

          <p className="text-base text-stone-600 leading-relaxed mb-5 max-w-xl">
            Winzinvest manages your portfolio automatically — equity positions, options income,
            and risk controls — running directly through your brokerage account.
            The same kind of systematic, disciplined approach used by institutional investors,
            available as software.
          </p>
          <p className="text-sm text-stone-500 leading-relaxed mb-10 max-w-xl">
            You define the strategy. Winzinvest manages the portfolio.
            Every day, without exception, without emotional interference.
          </p>

          <div className="flex gap-3 mb-8">
            <Link
              href="/login"
              className="px-6 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-700 text-white font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-sky-600 focus:ring-offset-2"
            >
              Open Dashboard
            </Link>
            <Link
              href="/methodology"
              className="px-6 py-2.5 rounded-xl border border-stone-200 bg-white hover:bg-stone-50 text-slate-900 font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2"
            >
              How It Works
            </Link>
          </div>

          {/* Transparency callout — earns the click before the user scrolls */}
          <div className="bg-white border border-stone-200 rounded-xl p-4 mb-10 flex items-start gap-4 max-w-xl">
            <div className="w-8 h-8 rounded-lg bg-sky-50 border border-sky-200 flex items-center justify-center shrink-0">
              <svg className="w-4 h-4 text-sky-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div>
              <div className="font-semibold text-sm text-slate-900 mb-0.5">The system is fully documented</div>
              <p className="text-xs text-stone-500 leading-relaxed">
                Strategy architecture, execution schedule, regime logic, risk gates, and circuit breakers are
                all publicly documented.{' '}
                <Link href="/methodology" className="text-sky-600 hover:text-sky-700 font-medium">Read the methodology</Link>
                {' '}or{' '}
                <Link href="/research" className="text-sky-600 hover:text-sky-700 font-medium">explore the research foundations.</Link>
              </p>
            </div>
          </div>

          {/* Trust bar */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              { label: 'Systematic portfolio automation', desc: 'Equity positions, options income, and rebalancing are managed automatically through your brokerage account.',           accent: 'border-l-sky-600' },
              { label: 'Systematic income generation',   desc: 'Options strategies run continuously on your holdings, generating premium income without manual position management.',  accent: 'border-l-green-600' },
              { label: 'Built-in portfolio protection',  desc: 'Drawdown controls, position limits, and market regime awareness protect the portfolio at every step.',                accent: 'border-l-orange-500' },
            ].map(({ label, desc, accent }) => (
              <div key={label} className={`bg-white border border-stone-200 rounded-xl p-5 border-l-4 ${accent}`}>
                <div className="font-semibold text-sm text-slate-900 mb-1.5">{label}</div>
                <p className="text-xs text-stone-500 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>

          <p className="text-xs text-stone-400 mt-6">
            Interactive Brokers account required. Winzinvest is systematic portfolio automation software. It does not provide investment advice.
          </p>
        </div>
      </section>

      <div className="border-t border-stone-200" />

      {/* What Winzinvest Does */}
      <section className="max-w-7xl mx-auto px-8 py-16">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-start">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">What Winzinvest Does</div>
            <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">
              Your portfolio, managed automatically
            </h2>
            <p className="text-sm text-stone-600 leading-relaxed mb-4">
              Winzinvest is a systematic portfolio automation platform.
              It handles the day-to-day work of running a systematic investment strategy —
              the screening, the execution, the options management, the risk monitoring,
              and the reporting — so the investor doesn&apos;t have to.
            </p>
            <p className="text-sm text-stone-600 leading-relaxed mb-6">
              The investor sets the strategy and risk parameters.
              Winzinvest runs the portfolio according to those rules,
              consistently, every market day.
            </p>
            <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-3">The platform handles</div>
            <ul className="space-y-2">
              {PLATFORM_HANDLES.map((item) => (
                <li key={item} className="flex items-start gap-2.5">
                  <span className="text-sky-600 font-bold text-sm leading-5 shrink-0">—</span>
                  <span className="text-sm text-stone-600">{item}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="bg-white border border-stone-200 rounded-xl p-7">
            <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-4">What investors stop doing</div>
            <p className="text-sm text-stone-600 leading-relaxed mb-5">
              Most self-directed investors spend hours each week on tasks that can be fully automated.
              Winzinvest replaces these manual workflows with a single managed process.
            </p>
            <ul className="space-y-3">
              {REPLACES.map((item) => (
                <li key={item} className="flex items-start gap-3 pb-3 border-b border-stone-100 last:border-0 last:pb-0">
                  <span className="w-1.5 h-1.5 rounded-full bg-stone-300 shrink-0 mt-2" />
                  <span className="text-sm text-stone-600">{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <div className="border-t border-stone-200" />

      {/* Three Pillars */}
      <section id="how-it-works" className="max-w-7xl mx-auto px-8 py-16 bg-stone-50">
        <div className="mb-10">
          <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">How It Works</div>
          <h2 className="font-serif text-3xl font-bold text-slate-900 mb-2">Three pillars of systematic portfolio automation</h2>
          <p className="text-sm text-stone-500 max-w-xl">
            Winzinvest manages your portfolio across three coordinated dimensions —
            growing capital, generating income, and protecting against downside — all
            running through a single automated system.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {THREE_PILLARS.map(({ accent, label, title, body }) => (
            <div key={label} className={`bg-white border border-stone-200 rounded-xl p-7 border-t-4 ${accent}`}>
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-3">{label}</div>
              <h3 className="font-semibold text-slate-900 text-sm mb-3">{title}</h3>
              <p className="text-sm text-stone-600 leading-relaxed">{body}</p>
            </div>
          ))}
        </div>

        {/* Regime-strategy matrix — addresses strategy fragility concern */}
        <div className="bg-white border border-stone-200 rounded-xl p-6 mb-8">
          <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-1">Why this matters</div>
          <div className="font-semibold text-sm text-slate-900 mb-4">The portfolio has something working in every market environment</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {[
              { regime: 'Trending markets',    driver: 'Equity momentum leads',       color: 'bg-sky-50 border-sky-200 text-sky-800',     dot: 'bg-sky-500' },
              { regime: 'Sideways markets',    driver: 'Options income dominates',    color: 'bg-green-50 border-green-200 text-green-800', dot: 'bg-green-500' },
              { regime: 'Volatile pullbacks',  driver: 'Mean reversion activates',    color: 'bg-amber-50 border-amber-200 text-amber-800', dot: 'bg-amber-500' },
              { regime: 'All environments',    driver: 'Risk controls protect capital', color: 'bg-stone-50 border-stone-200 text-stone-700', dot: 'bg-stone-400' },
            ].map(({ regime, driver, color, dot }) => (
              <div key={regime} className={`rounded-lg border p-4 ${color}`}>
                <div className="flex items-center gap-2 mb-2">
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dot}`} />
                  <span className="text-xs font-semibold uppercase tracking-wide">{regime}</span>
                </div>
                <p className="text-sm font-medium leading-snug">{driver}</p>
              </div>
            ))}
          </div>
          <p className="text-xs text-stone-400 mt-4">
            A single-strategy system depends on one market condition to perform. Winzinvest is
            designed so that when one pillar slows, others compensate — reducing reliance on any
            single environment for portfolio results.
          </p>
        </div>

        {/* Daily cycle */}
        <div className="bg-white border border-stone-200 rounded-xl p-6">
          <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-5">
            A typical day — runs automatically, every market session
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
            {DAILY_CYCLE.map(({ time, label, desc }, i) => (
              <div key={i} className="bg-stone-50 border border-stone-200 rounded-lg p-3 text-center">
                <div className="font-mono text-xs font-bold text-sky-600 mb-1">{time}</div>
                <div className="text-xs font-semibold text-slate-900 mb-1">{label}</div>
                <div className="text-xs text-stone-500 leading-tight">{desc}</div>
              </div>
            ))}
          </div>
          <p className="text-xs text-stone-400 mt-4">
            The investor monitors progress through the dashboard. No manual intervention is needed at any step.
          </p>
        </div>
      </section>

      <div className="border-t border-stone-200" />

      {/* Why automation */}
      <section className="max-w-7xl mx-auto px-8 py-16">
        <div className="mb-10">
          <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">Why Automation</div>
          <h2 className="font-serif text-3xl font-bold text-slate-900">The advantage of removing yourself from the process</h2>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 items-start">
          <div>
            <p className="text-sm text-stone-600 leading-relaxed mb-5">
              Research consistently shows that the biggest drag on portfolio performance is not
              strategy selection — it is inconsistent execution. Investors override their own
              plans during drawdowns, hesitate during opportunities, and react emotionally to
              short-term volatility.
            </p>
            <p className="text-sm text-stone-600 leading-relaxed mb-8">
              Winzinvest removes the investor from the execution loop entirely.
              The strategy runs the same way whether markets are calm or volatile,
              whether the portfolio is up or down. That consistency is the core value of automation.
            </p>
            <div className="bg-slate-900 rounded-xl p-6">
              <div className="text-xs font-semibold uppercase tracking-wider text-sky-400 mb-4">Managed automatically</div>
              <div className="grid grid-cols-2 gap-2">
                {['Portfolio adjustments', 'Profit-taking', 'Options management', 'Risk enforcement', 'Regime adaptation', 'Daily reporting'].map((item) => (
                  <div key={item} className="flex items-center gap-2">
                    <span className="w-1 h-1 rounded-full bg-sky-400 shrink-0" />
                    <span className="text-sm text-stone-300">{item}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="space-y-4">
            {[
              { num: '01', title: 'Growth and income work together', body: 'Equity momentum captures price appreciation. Options premium captures time decay. These two income sources complement each other — when markets trend, equities lead; when markets consolidate, options income tends to accelerate.' },
              { num: '02', title: 'Protection scales with risk', body: 'The drawdown system doesn\'t panic. It reduces exposure gradually as conditions worsen — smaller positions first, then paused entries, then a full halt. The portfolio stays operational through normal volatility.' },
              { num: '03', title: 'The system improves over time', body: 'Each week, strategy parameters are recalibrated against recent portfolio performance. Strike selection, holding periods, and profit thresholds are updated automatically based on what\'s actually working.' },
              { num: '04', title: 'Dividends and events are protected', body: 'The platform automatically avoids writing options when it would jeopardize dividend income or create assignment risk around earnings. This kind of detail is easy to miss manually — and expensive when you do.' },
            ].map(({ num, title, body }) => (
              <div key={num} className="flex gap-5 bg-white border border-stone-200 rounded-xl p-5">
                <span className="font-serif text-2xl font-bold text-stone-200 shrink-0 w-8 leading-none tabular-nums">{num}</span>
                <div>
                  <div className="font-semibold text-sm text-slate-900 mb-1.5">{title}</div>
                  <p className="text-sm text-stone-600 leading-relaxed">{body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="border-t border-stone-200" />

      {/* Portfolio Protection */}
      <section id="protection" className="max-w-7xl mx-auto px-8 py-16 bg-stone-50">
        <div className="mb-8">
          <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">Portfolio Protection</div>
          <h2 className="font-serif text-3xl font-bold text-slate-900 mb-2">Risk management built into every decision</h2>
          <p className="text-sm text-stone-500 max-w-xl">
            Protection is not an add-on. It is built into how the portfolio is managed.
            Every investment decision passes through multiple layers of risk controls
            before it reaches your brokerage account.
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {RISK_CONTROLS.map(({ borderClass, title, body }) => (
            <div key={title} className={`bg-white border border-stone-200 rounded-xl p-6 border-l-4 ${borderClass}`}>
              <h3 className="font-semibold text-sm text-slate-900 mb-2">{title}</h3>
              <p className="text-xs text-stone-500 leading-relaxed">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <div className="border-t border-stone-200" />

      {/* Who it's for */}
      <section className="max-w-7xl mx-auto px-8 py-16">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">Who It&apos;s For</div>
            <h2 className="font-serif text-3xl font-bold text-slate-900 mb-5">Built for investors who take their portfolio seriously</h2>
            <p className="text-sm text-stone-600 leading-relaxed mb-6">
              Winzinvest is designed for self-directed investors who want the discipline
              and consistency of institutional portfolio management — without hiring
              a team or building custom technology. It is typically used by investors who:
            </p>
            <ul className="space-y-3 mb-8">
              {INVESTOR_PROFILE.map((item) => (
                <li key={item} className="flex items-start gap-3">
                  <span className="text-sky-600 font-bold text-sm leading-5 shrink-0">—</span>
                  <span className="text-sm text-stone-600">{item}</span>
                </li>
              ))}
            </ul>
            {/* Wrong-user filter — signals seriousness to right users by naming the wrong ones */}
            <div className="bg-stone-100 border border-stone-200 rounded-xl p-5">
              <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-3">This platform is not for everyone</div>
              <p className="text-sm text-stone-600 leading-relaxed mb-3">
                Winzinvest is not designed for investors seeking daily active trading,
                short-term speculation, or guaranteed returns in every market condition.
              </p>
              <p className="text-sm text-stone-500 leading-relaxed">
                Systematic strategies experience drawdown periods. Options income slows when volatility
                is low. Momentum strategies underperform in sideways markets. If you are looking
                for a system that produces consistent profits regardless of market conditions,
                that system does not exist — and any platform that claims otherwise should be
                approached with significant skepticism.
              </p>
            </div>
          </div>

          <div className="bg-white border border-stone-200 rounded-xl p-8">
            <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-5">Pricing aligned with portfolio scale</div>
            <p className="text-sm text-stone-600 leading-relaxed mb-5">
              Pricing is based on the size of the portfolio you plan to automate — not on
              which features you get access to. All plans include the same core system.
            </p>
            <div className="space-y-2 mb-6">
              {[
                { tier: 'Investor',       range: 'Up to $250K',   price: '$149 / mo' },
                { tier: 'Professional',   range: '$250K – $1M',   price: '$349 / mo', popular: true },
                { tier: 'Private Client', range: '$1M – $5M',     price: '$799 / mo' },
                { tier: 'Institutional',  range: '$5M+',          price: 'Custom' },
              ].map(({ tier, range, price, popular }) => (
                <div key={tier} className={`flex items-center justify-between rounded-lg px-3 py-2 ${popular ? 'bg-sky-50 border border-sky-200' : 'bg-stone-50 border border-stone-200'}`}>
                  <div>
                    <span className={`text-xs font-semibold ${popular ? 'text-sky-700' : 'text-stone-700'}`}>{tier}</span>
                    <span className="text-xs text-stone-400 ml-2">{range}</span>
                    {popular && <span className="ml-2 inline-block text-xs font-bold text-sky-600 bg-sky-100 rounded-full px-1.5 py-0.5">Popular</span>}
                  </div>
                  <span className={`text-xs font-bold tabular-nums ${popular ? 'text-sky-700' : 'text-slate-900'}`}>{price}</span>
                </div>
              ))}
            </div>
            <a
              href="#pricing"
              className="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-700 text-white font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-sky-600 focus:ring-offset-2"
            >
              View Full Pricing
            </a>
          </div>
        </div>
      </section>

      <div className="border-t border-stone-200" />

      {/* Pricing */}
      <section id="pricing" className="max-w-7xl mx-auto px-8 py-16">

        {/* Section header */}
        <div className="mb-10">
          <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">Pricing</div>
          <h2 className="font-serif text-3xl font-bold text-slate-900 mb-2">
            Pricing aligned with portfolio scale
          </h2>
          <p className="text-sm text-stone-500 max-w-2xl leading-relaxed">
            Winzinvest is portfolio infrastructure. The value of disciplined automation increases as
            the amount of capital being managed grows. Pricing is therefore aligned with portfolio size
            rather than feature restrictions. All plans include the same core system.
          </p>
        </div>

        {/* AUM psychology anchor */}
        <div className="bg-stone-50 border border-stone-200 rounded-xl p-6 mb-10 max-w-3xl">
          <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-3">Why portfolio-based pricing</div>
          <p className="text-sm text-stone-600 leading-relaxed mb-3">
            Traditional wealth managers often charge around 1% of assets annually. On a $500K portfolio,
            that is approximately <strong className="text-slate-900">$5,000 per year</strong> — paid to a firm that retains discretion
            over your capital.
          </p>
          <p className="text-sm text-stone-600 leading-relaxed">
            Winzinvest provides automated portfolio execution and risk infrastructure for a fraction of
            that cost, while keeping you fully in control of your own brokerage account. Pricing scales
            with portfolio size to reflect the value delivered — not to restrict access to the system.
          </p>
        </div>

        {/* Pricing cards — 4 tiers */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 mb-12">
          {PRICING_PLANS.map((plan) => (
            <div
              key={plan.name}
              className={`relative bg-white border border-stone-200 rounded-xl overflow-hidden flex flex-col border-t-4 ${plan.accent} ${plan.popular ? 'shadow-lg ring-1 ring-sky-600/20' : ''}`}
            >
              {plan.popular && (
                <div className="absolute top-3 right-3">
                  <span className="inline-block px-2 py-0.5 rounded-full bg-sky-600 text-white text-xs font-bold tracking-wide">
                    Most Popular
                  </span>
                </div>
              )}
              <div className="p-6 pb-4">
                <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">{plan.name}</div>
                <div className="flex items-end gap-1 mb-1">
                  <span className="font-serif text-3xl font-bold text-slate-900 leading-none">{plan.price}</span>
                  <span className="text-stone-400 text-sm pb-0.5">{plan.period}</span>
                </div>
                <div className="text-xs text-stone-400 mb-3">{plan.annualEquiv}</div>
                {/* Portfolio size band — the primary differentiator */}
                <div className="inline-flex items-center gap-1.5 bg-stone-50 border border-stone-200 rounded-lg px-2.5 py-1 mb-4">
                  <span className="w-1.5 h-1.5 rounded-full bg-sky-500 shrink-0" />
                  <span className="text-xs font-semibold text-stone-700">{plan.portfolioRange}</span>
                </div>
                <p className="text-xs text-stone-500 leading-relaxed mb-5">{plan.tagline}</p>
                <a
                  href={plan.price === 'Custom' ? 'mailto:hello@winzinvest.com' : '/login'}
                  className={`block w-full text-center px-4 py-2 rounded-xl font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-sky-600 focus:ring-offset-2 ${plan.ctaStyle}`}
                >
                  {plan.cta}
                </a>
              </div>
              <div className="border-t border-stone-100 px-6 py-4 flex-1">
                <div className="text-xs font-semibold uppercase tracking-wider text-stone-400 mb-2">{plan.accounts}</div>
                {plan.extras.length > 0 && (
                  <>
                    <div className="text-xs text-stone-400 mb-2 mt-3">Service level:</div>
                    <ul className="space-y-1.5">
                      {plan.extras.map((feat) => (
                        <li key={feat} className="flex items-start gap-2">
                          <span className="text-stone-400 font-bold text-xs leading-4 shrink-0 mt-0.5">—</span>
                          <span className="text-xs text-stone-600 leading-relaxed">{feat}</span>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Included in every plan */}
        <div className="border border-stone-200 rounded-xl bg-white p-7 mb-12">
          <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-1">Included in every plan — no exceptions</div>
          <p className="text-sm text-stone-600 leading-relaxed mb-6">
            Every Winzinvest subscriber receives the full system. Plans differ by portfolio size,
            number of brokerage accounts, and service level — not by which features you can access.
            An Investor subscriber and a Private Client subscriber run the exact same automation engine.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-2.5">
            {INCLUDED_IN_ALL.map((item) => (
              <div key={item} className="flex items-start gap-2.5">
                <span className="text-sky-600 font-bold text-sm leading-5 shrink-0">—</span>
                <span className="text-sm text-stone-700 leading-snug">{item}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Portfolio savings calculator */}
        <PricingCalculator />

        {/* Comparison context */}
        <div className="bg-slate-900 rounded-xl p-8 md:p-10 mt-12">
          <div className="text-xs font-semibold uppercase tracking-wider text-sky-400 mb-3">Compared with the alternatives</div>
          <h3 className="font-serif text-2xl font-bold text-white mb-4">
            Portfolio infrastructure at a fraction of traditional management costs.
          </h3>
          <p className="text-stone-400 text-sm leading-relaxed mb-8 max-w-2xl">
            Most tools either charge regardless of capital scale, or charge a percentage of assets that
            compounds against returns over time. Winzinvest charges a flat software fee aligned with
            portfolio size — keeping infrastructure costs transparent and proportionate.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            {[
              { label: 'vs. Wealth managers',    body: 'Traditional wealth management typically costs 1% of AUM annually — plus the investor cedes day-to-day discretion. Winzinvest costs a fixed monthly fee and the investor retains full control.' },
              { label: 'vs. Other platforms',    body: 'Most platforms charge a flat fee regardless of portfolio size, leaving significant value uncaptured for larger investors. Winzinvest scales pricing with capital to reflect what the system actually delivers.' },
              { label: 'vs. Doing it yourself',  body: 'Manual portfolio management takes hours each day and introduces emotional override at exactly the moments consistency matters most. The platform applies the same disciplined process every session.' },
            ].map(({ label, body }) => (
              <div key={label} className="border-t border-stone-700 pt-5">
                <div className="text-xs font-semibold text-stone-400 uppercase tracking-wider mb-2">{label}</div>
                <p className="text-sm text-stone-300 leading-relaxed">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="border-t border-stone-200" />

      {/* FAQ */}
      <section id="faq" className="max-w-7xl mx-auto px-8 py-16">
        <div className="mb-10">
          <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">FAQ</div>
          <h2 className="font-serif text-3xl font-bold text-slate-900">Common questions</h2>
        </div>
        <div className="max-w-3xl space-y-2">
          {FAQ_ITEMS.map((item, i) => {
            const open = faqOpen.has(i);
            return (
              <div key={i} className="bg-white border border-stone-200 rounded-xl overflow-hidden">
                <button
                  onClick={() => {
                    setFaqOpen((prev) => {
                      const next = new Set(prev);
                      next.has(i) ? next.delete(i) : next.add(i);
                      return next;
                    });
                  }}
                  className="w-full flex items-center justify-between px-6 py-4 text-left focus:outline-none focus:ring-2 focus:ring-inset focus:ring-sky-600 group"
                  aria-expanded={open}
                >
                  <span className="font-semibold text-sm text-slate-900 group-hover:text-sky-600 transition-colors">{item.q}</span>
                  <span className={`shrink-0 ml-4 text-stone-400 font-bold text-lg leading-none transition-transform duration-200 ${open ? 'rotate-45' : ''}`}>+</span>
                </button>
                {open && (
                  <div className="px-6 pb-5">
                    <p className="text-sm text-stone-600 leading-relaxed">{item.a}</p>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      <div className="border-t border-stone-200" />

      {/* CTA */}
      <section className="max-w-7xl mx-auto px-8 py-20">
        <div className="bg-slate-900 rounded-xl p-12 text-center">
          <p className="text-sky-400 text-xs font-semibold uppercase tracking-widest mb-6">
            Winzinvest · System Design Principle
          </p>
          <h2 className="font-serif text-3xl font-bold text-white mb-6 max-w-2xl mx-auto leading-snug">
            &ldquo;The objective is not to forecast markets, but to systematically participate
            in them with consistency, transparency, and discipline.&rdquo;
          </h2>
          <p className="text-stone-400 text-sm leading-relaxed mb-8 max-w-lg mx-auto">
            Systematic equity management. Options income. Built-in risk controls.
            Daily reporting. All running through your brokerage account.
          </p>
          <div className="flex justify-center gap-3">
            <Link
              href="/login"
              className="inline-block px-8 py-3 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-bold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-offset-2 focus:ring-offset-slate-900"
            >
              Open Dashboard
            </Link>
            <Link
              href="/overview"
              className="inline-block px-8 py-3 rounded-xl border border-stone-600 hover:bg-stone-800 text-stone-300 font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-stone-500 focus:ring-offset-2 focus:ring-offset-slate-900"
            >
              System Overview
            </Link>
          </div>
          <p className="text-stone-600 text-xs mt-6">
            Interactive Brokers account required. Systematic portfolio automation software. Not investment advice.
          </p>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-stone-200 py-10 px-8 max-w-7xl mx-auto">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 mb-6">
          <span className="font-serif font-bold text-stone-500 text-sm">Winzinvest</span>
          <div className="flex gap-6">
            <Link href="/overview"    className="text-sm text-stone-400 hover:text-stone-600 transition-colors">Overview</Link>
            <Link href="/methodology" className="text-sm text-stone-400 hover:text-stone-600 transition-colors">Methodology</Link>
            <Link href="/performance" className="text-sm text-stone-400 hover:text-stone-600 transition-colors">Performance</Link>
            <a href="#pricing"        className="text-sm text-stone-400 hover:text-stone-600 transition-colors">Pricing</a>
            <Link href="/login"       className="text-sm text-stone-400 hover:text-stone-600 transition-colors">Dashboard</Link>
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
