'use client';

/**
 * Winzinvest Landing Page
 *
 * Brand Archetype:  The Disciplined Operator / The Risk Manager
 * Core Emotion:     Relief — handing the keys to a system that won't make emotional mistakes
 * Tone:             Calm, objective, institutional, restrained. No hype, no exclamation points.
 *
 * Section Order:
 *   1. Hero
 *   2. Pain (Sound familiar?)
 *   3. JTBD Pillars (3-col)
 *   4. Competitor Matrix
 *   5. Daily Operations Timeline
 *   6. Risk Gates / The Moat
 *   7. Pricing (Intelligence · Automation · Professional · Founding Member)
 *   8. What You Need (Brokerage Compatibility)
 *   9. FAQ
 *   10. Footer
 *
 * Colors:  primary-600 (#334FFF) for CTAs/accents
 *          secondary-500 (#F09006) for Founding Member gold
 *          neutral/stone/slate for all surfaces
 * Fonts:   font-serif (Playfair Display) for headlines
 *          font-sans (Inter) for body/UI
 *          font-mono (JetBrains Mono) for data/tickers
 */

import Image from 'next/image';
import Link from 'next/link';
import { use, useState } from 'react';
import { PublicNav } from '../components/PublicNav';
import { WaitlistForm } from '../components/WaitlistForm';

/* ── Data ─────────────────────────────────────────────────── */

const PAIN_QUOTES = [
  {
    quote: `"I really wish I had a bot that would call me up and say, 'you've given it all back. stop trading today.'"`,
    source: 'r/algotrading',
  },
  {
    quote: `"I have a great strategy on TradingView, but I keep overriding it when I get scared."`,
    source: 'r/Daytrading',
  },
  {
    quote: `"Selling covered calls is great until you forget an earnings date and get your shares called away."`,
    source: 'r/options',
  },
];

const JTBD_PILLARS = [
  {
    num: '01',
    title: 'The keyboard is the enemy.',
    body: `You know how to trade. The problem is you: overriding your own rules when you're down, doubling up when you're winning, talking yourself out of stops. Winzinvest removes the keyboard at the exact moment you're most likely to blow up.`,
    accent: 'border-t-danger-600',
    labelColor: 'text-danger-600',
    label: 'Protect capital from yourself',
    illustration: '/illustrations/protect-corridors.png',
    illustrationAlt: 'Layered geometric corridors converging on a keyhole — representing multiple protection layers',
  },
  {
    num: '02',
    title: `Bad trades don't make it to execution.`,
    body: `Anyone can build a screener. The trick is knowing which setups to skip. Marginal conviction? Kill it. Wrong regime? Don't enter. Too much sector exposure? Next. A bad morning stays bad, not catastrophic.`,
    accent: 'border-t-primary-600',
    labelColor: 'text-primary-600',
    label: 'Multiple layers of no',
    illustration: '/illustrations/precision-cube.png',
    illustrationAlt: 'Dark geometric cube with precise edges — representing systematic, mechanical execution',
  },
  {
    num: '03',
    title: 'Premium income without the spreadsheet.',
    body: `Managing covered calls across 20 positions is tedious. When do you roll? Which strike? Did you check the ex-dividend date? Winzinvest handles all of it. The position collects premium whether you're watching or not.`,
    accent: 'border-t-success-600',
    labelColor: 'text-success-600',
    label: 'Options on autopilot',
    illustration: '/illustrations/compound-yield.png',
    illustrationAlt: 'Warm staircase ascending toward a sun — representing compounding returns over time',
  },
];

const COMPETITORS = [
  { name: 'Wealth Managers', price: '1% of AUM (starting at $10K/year)', what: 'Discretionary portfolio management', gap: `Fee scales with portfolio size. $1M = $10K/year, $5M = $50K/year. You hand over control, no input on anything.` },
  { name: 'Trade Ideas',   price: '$89–178/mo',    what: 'AI screener, alerts only',         gap: `Manual execution required. You're still the one clicking when you're scared.` },
  { name: 'Composer',      price: '$32/mo',         what: 'Visual no-code automation',          gap: `No kill switch, no regime awareness, no margin monitoring. Keeps trading when it shouldn't.` },
  { name: 'QuantConnect',  price: 'Free–$8/mo',     what: 'Institutional algo platform',        gap: `Requires Python or C#. Most swing traders aren't writing code.` },
  { name: 'TastyTrade',    price: 'Commission only', what: 'Brokerage with great options UI',   gap: `Manual execution. Doesn't automate rolling, screening, or risk gates.` },
];

const RISK_PRINCIPLES = [
  {
    borderClass: 'border-l-danger-600',
    title: 'Position sizes shrink as losses pile up',
    body: `The system doesn't wait for you to hit a wall. Down 1%? Positions cut to 50%. Down 2%? 25%. A bad morning stays bad, not catastrophic. If it gets ugly, the kill switch shuts everything down. No heroics.`,
  },
  {
    borderClass: 'border-l-primary-600',
    title: 'Thirteen ways to say no',
    body: `Every order runs through thirteen checks before it fires. Wrong regime? No. Too much sector exposure? No. Marginal conviction? No. The system has thirteen ways to refuse a trade. You only need one reason to place it. The asymmetry is intentional.`,
  },
  {
    borderClass: 'border-l-success-600',
    title: 'Vol and credit markets lead equities',
    body: `Credit spreads widen before stocks fall. Vol spikes before drawdowns show up in your P&L. The system watches both continuously and starts pulling back exposure before the damage appears in your account. Not after.`,
  },
  {
    borderClass: 'border-l-warning-600',
    title: 'Every decision is logged',
    body: `Every trade, rejected setup, regime shift, and parameter change is timestamped and visible on the dashboard. You'll know exactly what happened and why. No black boxes.`,
  },
];

const PRICING_TIERS = [
  {
    id: 'intelligence' as const,
    name: 'Intelligence',
    price: '$49',
    period: '/mo',
    tagline: 'Signals without the automation.',
    description: 'See what the system would do: live regime, screener signals, options candidates. Execute manually or just watch. You stay in control.',
    features: [
      'Daily regime status (Expansion, Choppy, Tightening)',
      'Pre-market screener signals (longs & mean reversion)',
      'Options income candidates (covered calls & CSPs)',
      'Portfolio risk dashboard (drawdown, sector concentration)',
      'Daily positions email with stop-price column',
    ],
    note: 'Manual execution required',
    cta: 'Join Intelligence Waitlist',
    ctaVariant: 'outline' as const,
    accent: 'border-t-stone-300',
    popular: false,
  },
  {
    id: 'automation' as const,
    name: 'Automation',
    price: '$149',
    period: '/mo',
    tagline: 'Brokerage-connected, fully automated.',
    description: 'Connect your brokerage API. Winzinvest handles entries, exits, stops, options rolls, and risk gates. Every session. You watch the dashboard, the system does the work.',
    features: [
      'Everything in Intelligence',
      'Direct brokerage API integration (IBKR, Tastytrade)',
      'Fully automated entry, exit, and options rolling',
      '13-layer execution risk gates',
      'PIN-protected kill switch',
      'ATR-based stops auto-set on every position',
      'Earnings and dividend blackouts',
      'Catalyst-driven entry screener (gap + volume + consolidation)',
      'Automatic position building into confirmed winners',
      'Early exit for failed setups (capital redeployed to better ideas)',
      'Weekly options parameter backtester',
    ],
    note: 'For accounts under $1M',
    cta: 'Join Automation Waitlist',
    ctaVariant: 'primary' as const,
    accent: 'border-t-primary-600',
    popular: true,
  },
  {
    id: 'professional' as const,
    name: 'Professional',
    price: '$399',
    period: '/mo',
    tagline: 'For portfolios over $1M.',
    description: 'Automation tier, priced for serious accounts. A wealth manager charging 1% on $1M costs $10K/year. This is $4,788/year. Same execution, 52% cheaper, and you keep control.',
    features: [
      'Everything in Automation',
      'Designed for accounts $1M+',
      'Same 13-layer execution risk gates',
      'Full options automation and rolling',
      'Appropriate risk scaling for larger positions',
    ],
    note: '0.48% of $1M annually vs 1% for wealth managers',
    cta: 'Join Professional Waitlist',
    ctaVariant: 'primary' as const,
    accent: 'border-t-slate-900',
    popular: false,
  },
];

const FAQ_ITEMS = [
  {
    q: 'What is Winzinvest?',
    a: `Execution software that connects to your brokerage (Interactive Brokers now; Tastytrade coming Q2) and automates your strategy. You set the rules. Winzinvest follows them and stops you from breaking them when you're down 2% and convinced the next trade is different. It's not a robo-advisor, not a signal service, not investment advice. Just mechanical execution of your own rules.`,
  },
  {
    q: 'How is this different from Trade Ideas or Composer?',
    a: `Trade Ideas sends alerts. You still have to click the button, which means you're back in the decision chain. Composer automates execution but has no kill switch, no regime awareness, no drawdown tiers. Winzinvest will refuse to trade when conditions turn. That's the difference.`,
  },
  {
    q: 'Which brokerages are supported?',
    a: `Winzinvest currently supports Interactive Brokers (full feature set including equity shorts, options strategies, portfolio margin, and trailing stops). Tastytrade integration is coming soon for options-focused portfolios. Schwab support planned for Q3 2026 pending their unified API launch. Requirements: margin account with Level 2+ options approval, API access enabled, and $25,000+ account value (PDT rule). Winzinvest connects via your own API credentials and never holds your funds.`,
  },
  {
    q: 'Is this investment advice?',
    a: `No. Winzinvest executes your rules. It doesn't pick stocks, suggest allocations, or tell you what to trade. That's all you. The system's job is to follow your rules and stop you from breaking them when you shouldn't.`,
  },
  {
    q: 'What is the Founding Member offer?',
    a: `Automation tier at $79/month for life instead of $149. Limited to 50 people. The system trades a live IBKR account today. You're pre-ordering the hosted version. Founding Members get early access and direct input on the roadmap. It's a bet on version one. If that sounds interesting, the slot is yours.`,
  },
  {
    q: 'When will multi-account access be available?',
    a: `The engine is built and trading live. Next phase: multi-tenant architecture so it works for everyone. Pre-orders fund that migration. Timeline: 8–12 weeks once we hit critical mass. Could be faster, could be slower. We'll keep you posted.`,
  },
  {
    q: 'What are the risks?',
    a: `Trading is risky. Strategies that work in one regime fail in another. The risk gates reduce exposure during drawdowns but don't eliminate losses. Past results don't predict future ones. If you lose money, that's on you. The system just makes sure you follow your own rules while it happens.`,
  },
];

/* ── Component ──────────────────────────────────────────────── */

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

      {/* ── 1. Hero ─────────────────────────────────────────── */}
      {/*
        Full-bleed illustration hero. Two images available — swap src to compare:
          /illustrations/hero-v2-orange-circle.png  (blue + amber, figure in chair)
          /illustrations/hero-v3-desk.png            (red/blue geometric blocks, figure at desk)
        Gradient overlay ensures text readability on the left without obscuring the illustration on the right.
      */}
      <section className="relative w-full min-h-[90vh] flex items-center overflow-hidden bg-slate-900">

        {/* Background illustration */}
        <Image
          src="/illustrations/hero-l-amber-path.png"
          alt="A figure standing on a winding path between blue and amber fields under a calm dark sky — representing steady forward progress through systematic discipline"
          fill
          className="object-cover object-center"
          priority
        />

        {/* Left-to-right gradient overlay — dark on left for text, transparent on right */}
        <div
          className="absolute inset-0"
          style={{
            background: 'linear-gradient(to right, rgba(15,23,42,0.88) 0%, rgba(15,23,42,0.75) 38%, rgba(15,23,42,0.25) 62%, rgba(15,23,42,0.0) 80%)',
          }}
        />

        {/* Content — left-aligned, sits above gradient */}
        <div className="relative z-10 w-full max-w-7xl mx-auto px-8 pt-32 pb-24">
        <div className="max-w-xl">

          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/20 bg-white/10 backdrop-blur-sm text-xs font-semibold text-white/90 uppercase tracking-widest mb-8">
            <span className="w-1.5 h-1.5 rounded-full bg-success-400 regime-dot" />
            Running live · IBKR Portfolio Margin · Fully Automated
          </div>

          <h1 className="font-serif text-5xl font-bold text-white leading-tight tracking-tight mb-6">
            You know how to trade.<br />
            <span className="text-primary-400">Staying disciplined is the hard part.</span>
          </h1>

          <p className="text-lg text-white/90 leading-relaxed mb-8">
            You've got the edge. Winzinvest just makes sure you don't override it at exactly the wrong moment.
            Your rules, executed without exception. No judgment calls when you're down 2%.
          </p>

          <div className="flex gap-3 mb-10">
            <a
              href="#pricing"
              className="px-6 py-2.5 rounded-xl bg-primary-600 hover:bg-primary-500 text-white font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-primary-400 focus:ring-offset-2 focus:ring-offset-slate-900"
            >
              Join the Waitlist
            </a>
            <Link
              href="/methodology"
              className="px-6 py-2.5 rounded-xl border border-white/25 bg-white/10 backdrop-blur-sm hover:bg-white/20 text-white font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-white/40 focus:ring-offset-2 focus:ring-offset-slate-900"
            >
              See How It Works
            </Link>
          </div>

          {/* Trust bar */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {[
              { label: 'Execution without emotion',  desc: '13 pre-trade checks on every order: regime, drawdown, concentration, margin, correlation, and more.', accent: 'border-l-primary-400' },
              { label: 'Options income on autopilot', desc: 'Covered calls written, rolled at 80% decay, and closed — across every eligible position.', accent: 'border-l-secondary-500' },
              { label: 'Your account, your rules',    desc: 'Connect your own brokerage credentials (IBKR or Tastytrade). Winzinvest executes your strategy. It never holds your funds.', accent: 'border-l-success-400' },
            ].map(({ label, desc, accent }) => (
              <div key={label} className={`bg-white/8 backdrop-blur-sm border border-white/12 rounded-xl p-4 border-l-4 ${accent}`}>
                <div className="font-semibold text-sm text-white mb-1">{label}</div>
                <p className="text-xs text-white/90 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>

          <p className="text-xs text-white/70 mt-6">
            Brokerage account required (Interactive Brokers or Tastytrade). Self-directed execution software — not investment advice.
          </p>

        </div>
        </div>
      </section>

      {/* ── 2. Pain ─────────────────────────────────────────── */}
      <section className="w-full bg-white border-t border-stone-200">
        <div className="max-w-7xl mx-auto px-8 py-16">
        <div className="max-w-2xl mx-auto text-center mb-10">
          <div className="text-xs font-semibold uppercase tracking-widest text-stone-600 mb-2">Sound familiar?</div>
          <h2 className="font-serif text-4xl font-bold text-slate-900 mb-4">
            You're not alone.
          </h2>
          <p className="text-sm text-stone-500 leading-relaxed">
            Discipline is hard. Everyone knows what to do. Almost no one actually does it.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
          {PAIN_QUOTES.map(({ quote, source }) => (
            <div key={source} className="bg-white border border-stone-200 rounded-xl p-6 card-elevated">
              <p className="text-sm text-stone-700 leading-relaxed italic mb-4">{quote}</p>
              <div className="text-xs text-stone-500 font-mono">{source}</div>
            </div>
          ))}
        </div>
        <div className="bg-slate-900 rounded-xl px-6 py-5">
          <p className="text-stone-200 text-sm leading-relaxed text-center">
            <span className="text-primary-400 font-semibold">&ldquo;</span>The leading cause of retail underperformance
            isn't bad analysis. It's discretionary override at the moment of execution.<span className="text-primary-400 font-semibold">&rdquo;</span>
          </p>
        </div>
        </div>
      </section>

      {/* ── 3. JTBD Pillars ─────────────────────────────────── */}
      <section className="w-full bg-stone-50 border-t border-stone-200">
        <div className="max-w-7xl mx-auto px-8 py-16">
        <div className="mb-10">
          <div className="text-xs font-semibold uppercase tracking-widest text-stone-600 mb-2">What Winzinvest Does</div>
          <h2 className="font-serif text-4xl font-bold text-slate-900 mb-2">Three problems. One system.</h2>
          <p className="text-sm text-stone-500 max-w-xl">
            The things that kill retail traders: emotion, marginal setups, and tedious execution. 
            Winzinvest addresses all three.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {JTBD_PILLARS.map(({ num, title, body, accent, label, labelColor, illustration, illustrationAlt }) => (
            <div key={num} className={`bg-white border border-stone-200 rounded-xl overflow-hidden border-t-4 ${accent} card-elevated`}>
              <div className="relative w-full aspect-[16/9] overflow-hidden">
                <Image
                  src={illustration}
                  alt={illustrationAlt}
                  fill
                  className="object-cover"
                  sizes="(max-width: 768px) 100vw, 33vw"
                />
              </div>
              <div className="p-7">
                <div className={`text-xs font-semibold uppercase tracking-widest mb-3 ${labelColor}`}>{label}</div>
                <div className="font-mono text-xs text-stone-600 mb-2">{num}</div>
                <h3 className="font-serif text-xl font-bold text-slate-900 mb-3 leading-snug">{title}</h3>
                <p className="text-sm text-stone-600 leading-relaxed">{body}</p>
              </div>
            </div>
          ))}
        </div>
        </div>
      </section>

      {/* ── 4. Competitor Matrix ────────────────────────────── */}
      <section className="w-full bg-white border-t border-stone-200">
        <div className="max-w-7xl mx-auto px-8 py-16">
        <div className="mb-10">
          <div className="text-xs font-semibold uppercase tracking-widest text-stone-600 mb-2">How It Compares</div>
          <h2 className="font-serif text-4xl font-bold text-slate-900 mb-2">Every other tool still needs you to press the button.</h2>
          <p className="text-sm text-stone-500 max-w-xl">
            Alert services require manual execution, so you're back in the loop. No-code platforms skip the risk gates.
            Winzinvest is the only retail system that will actually refuse to trade when conditions turn against you.
          </p>
        </div>

        <div className="overflow-x-auto rounded-xl border border-stone-200">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-stone-50 border-b border-stone-200">
                <th className="text-left py-3 px-5 text-xs font-semibold text-stone-500 uppercase tracking-wider">Platform</th>
                <th className="text-left py-3 px-5 text-xs font-semibold text-stone-500 uppercase tracking-wider">Price</th>
                <th className="text-left py-3 px-5 text-xs font-semibold text-stone-500 uppercase tracking-wider">What it does</th>
                <th className="text-left py-3 px-5 text-xs font-semibold text-danger-600 uppercase tracking-wider">Where it fails</th>
              </tr>
            </thead>
            <tbody>
              {COMPETITORS.map(({ name, price, what, gap }) => (
                <tr key={name} className="border-b border-stone-100 bg-white hover:bg-stone-50 transition-colors">
                  <td className="py-3 px-5 font-semibold text-slate-800">{name}</td>
                  <td className="py-3 px-5 text-stone-500 font-mono text-xs">{price}</td>
                  <td className="py-3 px-5 text-stone-600">{what}</td>
                  <td className="py-3 px-5 text-stone-600">{gap}</td>
                </tr>
              ))}
              <tr className="bg-primary-50 border-b border-primary-100">
                <td className="py-3 px-5 font-bold text-primary-700">Winzinvest</td>
                <td className="py-3 px-5 text-primary-600 font-mono text-xs font-semibold">Starting at $49/mo</td>
                <td className="py-3 px-5 text-primary-700 font-semibold">Full execution automation + 13-layer risk gate (Professional: $399/mo, 52% less than WMs for $1M+)</td>
                <td className="py-3 px-5">
                  <span className="inline-block px-2 py-0.5 rounded-full bg-success-100 text-success-700 text-xs font-semibold">None identified</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="mt-6 bg-slate-900 rounded-xl p-6">
          <div className="text-xs font-semibold uppercase tracking-widest text-primary-400 mb-3">The Professional tier advantage</div>
          <p className="text-white font-semibold text-base mb-2">
            Wealth managers charge 1% annually ($10K/year for $1M). Professional: $399/mo = $4,788/year. 52% cheaper.
          </p>
          <p className="text-stone-300 text-sm leading-relaxed">
            You keep control over strategy, rules, and risk gates. 
            Flat monthly fee. Doesn't scale with portfolio size.
          </p>
        </div>
        </div>
      </section>

      {/* ── 5. Daily Operations Summary ─────────────────────── */}
      <section className="w-full bg-stone-50 border-t border-stone-200">
        <div className="max-w-7xl mx-auto px-8 py-16">
        <div className="mb-8">
          <div className="text-xs font-semibold uppercase tracking-widest text-stone-600 mb-2">Daily Operations</div>
          <h2 className="font-serif text-4xl font-bold text-slate-900 mb-2">What actually happens each day.</h2>
        </div>
        <div className="bg-white border border-stone-200 rounded-xl p-8">
          <p className="text-sm text-stone-600 leading-relaxed mb-4">
            Pre-market: screen hundreds of candidates, eliminate marginal setups, queue orders.
            At the open: execute what survived the filters, set stops on everything.
            Throughout the day: monitor positions, roll options at 80% decay, adjust to regime shifts.
            You don't touch anything unless you want to.
          </p>
          <p className="text-sm text-stone-600 leading-relaxed mb-6">
            The dashboard shows you everything. The system does the work.
          </p>
          <Link
            href="/methodology#operations"
            className="text-sm font-semibold text-primary-600 hover:text-primary-700 transition-colors"
          >
            See the full daily schedule &rarr;
          </Link>
        </div>
        </div>
      </section>

      {/* ── 6. Risk Principles / The Moat ─────────────────────── */}
      <section id="risk" className="relative w-full border-t border-stone-200 overflow-hidden">

        {/* Full-bleed illustration background */}
        <div className="relative w-full h-[480px] lg:h-[560px]">
          <Image
            src="/illustrations/moat-rings.png"
            alt="Aerial view of concentric rings with figures moving through protective layers — representing institutional-grade risk gates around retail accounts"
            fill
            className="object-cover object-center"
          />
          <div
            className="absolute inset-0"
            style={{ background: 'linear-gradient(to bottom, rgba(0,0,0,0) 40%, rgba(15,23,42,0.85) 100%)' }}
          />
          <div className="absolute bottom-0 left-0 right-0 max-w-7xl mx-auto px-8 pb-10">
            <div className="text-xs font-semibold uppercase tracking-widest text-white/90 mb-2">The Moat</div>
            <h2 className="font-serif text-4xl font-bold text-white mb-2">The kind of risk controls prop desks take for granted.</h2>
            <p className="text-sm text-white/90 max-w-xl leading-relaxed">
              Drawdown tiers, regime gates, vol overlays, correlation checks. 
              The things institutional traders assume exist. Retail platforms usually skip them. We don't.
            </p>
          </div>
        </div>

        {/* Principle cards — high-level, linking to methodology for details */}
        <div className="bg-slate-900 w-full">
        <div className="max-w-7xl mx-auto px-8 py-10">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {RISK_PRINCIPLES.map(({ borderClass, title, body }) => (
            <div key={title} className={`bg-white/6 border border-white/10 rounded-xl p-6 border-l-4 ${borderClass}`}>
              <h3 className="font-semibold text-sm text-white mb-2">{title}</h3>
              <p className="text-xs text-white/90 leading-relaxed">{body}</p>
            </div>
          ))}
        </div>
        <div className="mt-6 text-center">
          <Link
            href="/methodology#risk"
            className="text-sm font-semibold text-primary-400 hover:text-primary-300 transition-colors"
          >
            See the full risk framework &rarr;
          </Link>
        </div>
        </div>
        </div>
      </section>

      {/* ── 7. Pricing ──────────────────────────────────────── */}
      <section id="pricing" className="w-full bg-stone-50 border-t border-stone-200">
        <div className="max-w-7xl mx-auto px-8 py-16">
        <div className="mb-10">
          <div className="text-xs font-semibold uppercase tracking-widest text-stone-600 mb-2">Pricing</div>
          <h2 className="font-serif text-4xl font-bold text-slate-900 mb-2">Three tiers. Pick the one that fits.</h2>
          <p className="text-sm text-stone-500 max-w-2xl leading-relaxed">
            Intelligence gives you the signals and the dashboard. Automation and Professional tiers connect to your brokerage account
            and handle everything from there. Pick the tier that matches your portfolio size.
          </p>
        </div>

        {/* Three standard tiers */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {PRICING_TIERS.map((tier) => (
            <div
              key={tier.name}
              className={`relative bg-white border border-stone-200 rounded-xl overflow-hidden flex flex-col border-t-4 ${tier.accent} ${tier.popular ? 'shadow-lg ring-1 ring-primary-600/20' : ''}`}
            >
              {tier.popular && (
                <div className="absolute top-3 right-3">
                  <span className="inline-block px-2 py-0.5 rounded-full bg-primary-600 text-white text-xs font-bold tracking-wide">
                    Recommended
                  </span>
                </div>
              )}
              <div className="p-6 pb-4">
                <div className="text-xs font-semibold uppercase tracking-widest text-stone-700 mb-2">{tier.name}</div>
                <div className="flex items-end gap-1 mb-1">
                  <span className="font-serif text-4xl font-bold text-slate-900 leading-none">{tier.price}</span>
                  <span className="text-stone-600 text-sm pb-1">{tier.period}</span>
                </div>
                <p className="text-xs font-semibold text-slate-800 mt-2 mb-1">{tier.tagline}</p>
                <p className="text-xs text-stone-500 leading-relaxed mb-5">{tier.description}</p>
                <WaitlistForm
                  tier={tier.id}
                  ctaLabel={tier.cta}
                  className="mb-1"
                />
                {tier.note && (
                  <p className="text-xs text-stone-600 mt-2">{tier.note}</p>
                )}
              </div>
              <div className="border-t border-stone-100 px-6 py-4 flex-1">
                <ul className="space-y-2">
                  {tier.features.map((feat) => (
                    <li key={feat} className="flex items-start gap-2">
                      <span className="text-primary-600 font-bold text-xs leading-4 shrink-0 mt-0.5">—</span>
                      <span className="text-xs text-stone-600 leading-relaxed">{feat}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ))}
        </div>

        {/* Founding Member — gold accent */}
        <div className="bg-slate-900 rounded-xl overflow-hidden">
          <div className="relative w-full h-48 overflow-hidden">
            <Image
              src="/illustrations/founding-member-circle.png"
              alt="Diverse community gathered in a welcoming circle — representing the collaborative founding member group building together"
              fill
              className="object-cover object-center"
              sizes="(max-width: 768px) 100vw, 768px"
            />
            <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-slate-900/80" />
            <div className="absolute bottom-3 left-6">
              <span className="text-xs font-semibold uppercase tracking-widest text-secondary-400">Founding Member</span>
            </div>
          </div>
          <div className="p-8 flex flex-col sm:flex-row gap-6 items-start">
            <div className="w-12 h-12 rounded-full bg-secondary-500/20 border border-secondary-500/40 flex items-center justify-center shrink-0">
              <span className="text-secondary-400 font-bold text-lg">★</span>
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 mb-1">
                <span className="inline-block px-2 py-0.5 rounded-full bg-secondary-500/20 border border-secondary-500/40 text-secondary-300 text-xs font-bold">
                  Limited to 50 spots
                </span>
              </div>
              <div className="flex items-end gap-2 mb-2">
                <span className="font-serif text-4xl font-bold text-white leading-none">$79</span>
                <span className="text-stone-300 text-sm pb-1">/mo · lifetime</span>
                <span className="text-stone-400 text-xs pb-1 line-through ml-1">$149</span>
              </div>
              <p className="text-stone-300 text-sm leading-relaxed mb-5">
                Automation tier, locked at $79/month for life. The system trades a live IBKR account 
                right now. You're pre-ordering the hosted version. Founding Members get early access 
                and direct input on the roadmap. It's a bet on V1. If that sounds good, the slot is yours.
              </p>
              <WaitlistForm
                tier="founding"
                ctaLabel="Pre-Order Now"
                className="max-w-md"
              />
              <p className="text-stone-300 text-xs mt-3">
                System is live, trading real money today. You're pre-ordering the hosted version. 
                Timeline: 8–12 weeks once we hit critical mass. Could be faster. We'll keep you posted.
              </p>
            </div>
          </div>
        </div>
        </div>
      </section>

      {/* ── 8. What You Need ────────────────────────────────── */}
      <section id="requirements" className="w-full bg-white border-t border-stone-200">
        <div className="max-w-7xl mx-auto px-8 py-16">
        <div className="mb-10">
          <div className="text-xs font-semibold uppercase tracking-widest text-stone-600 mb-2">Requirements</div>
          <h2 className="font-serif text-4xl font-bold text-slate-900 mb-2">What you need</h2>
          <p className="text-sm text-stone-500 max-w-2xl leading-relaxed">
            Winzinvest connects via your brokerage's API. You keep full control. 
            We never hold funds, never have discretionary authority. Just execution.
          </p>
        </div>

        {/* Supported Brokerages */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-10">
          {/* Interactive Brokers — Available Now */}
          <div className="bg-stone-50 border border-stone-200 rounded-xl p-6 border-l-4 border-l-success-500">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900 mb-1">Interactive Brokers</h3>
                <p className="text-xs font-semibold text-success-600 uppercase tracking-wide">Available Now</p>
              </div>
              <span className="inline-block px-2 py-0.5 rounded-full bg-success-100 text-success-700 text-xs font-bold">
                Recommended
              </span>
            </div>
            <p className="text-sm text-slate-700 leading-relaxed mb-4">
              Full support: equity shorts, multi-leg options, portfolio margin, ATR trailing stops. Everything works.
            </p>
            <ul className="space-y-2 text-xs text-stone-600">
              <li className="flex items-start gap-2">
                <span className="text-success-500 mt-0.5">✓</span>
                <span>Equity shorts + margin</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success-500 mt-0.5">✓</span>
                <span>Multi-leg options (spreads, combos, bag orders)</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success-500 mt-0.5">✓</span>
                <span>Portfolio margin (up to 6× leverage)</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success-500 mt-0.5">✓</span>
                <span>Native trailing stops</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success-500 mt-0.5">✓</span>
                <span>Paper trading environment</span>
              </li>
            </ul>
          </div>

          {/* Tastytrade — Coming Soon */}
          <div className="bg-stone-50 border border-stone-200 rounded-xl p-6 border-l-4 border-l-primary-500">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900 mb-1">Tastytrade</h3>
                <p className="text-xs font-semibold text-primary-600 uppercase tracking-wide">Coming Q2 2026</p>
              </div>
            </div>
            <p className="text-sm text-slate-700 leading-relaxed mb-4">
              Great for options-focused portfolios. Lower commissions than IBKR. Trailing stops managed client-side, but you won't notice the difference.
            </p>
            <ul className="space-y-2 text-xs text-stone-600">
              <li className="flex items-start gap-2">
                <span className="text-success-500 mt-0.5">✓</span>
                <span>Multi-leg options (full support)</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success-500 mt-0.5">✓</span>
                <span>Equity shorts + margin</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success-500 mt-0.5">✓</span>
                <span>$0 stock commissions, $1/contract options</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-primary-500 mt-0.5">→</span>
                <span>Trailing stops managed client-side*</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-success-500 mt-0.5">✓</span>
                <span>Paper trading sandbox</span>
              </li>
            </ul>
            <p className="text-xs text-stone-600 mt-4 italic">
              *Risk management identical to native stops.
            </p>
          </div>
        </div>

        {/* Requirements Box */}
        <div className="bg-slate-900 rounded-xl p-8 mb-6">
          <h3 className="text-base font-bold text-white mb-4">Account Requirements</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            <div>
              <div className="text-xs font-semibold uppercase tracking-widest text-primary-400 mb-1">Margin</div>
              <p className="text-sm text-white leading-relaxed">
                Margin account with Level 2+ options approval
              </p>
            </div>
            <div>
              <div className="text-xs font-semibold uppercase tracking-widest text-primary-400 mb-1">API Access</div>
              <p className="text-sm text-white leading-relaxed">
                API access enabled in your brokerage account
              </p>
            </div>
            <div>
              <div className="text-xs font-semibold uppercase tracking-widest text-primary-400 mb-1">Account Size</div>
              <p className="text-sm text-white leading-relaxed">
                $25,000+ account value (pattern day trader rule)
              </p>
            </div>
          </div>
        </div>

        {/* Not Compatible */}
        <div className="bg-stone-100 border border-stone-200 rounded-lg p-5">
          <p className="text-xs text-stone-600 leading-relaxed">
            <strong className="text-stone-700">Not compatible:</strong> Alpaca (no options support), Robinhood (no official API).
            Additional brokerages available on request. <a href="#faq" className="text-primary-600 hover:text-primary-700 font-semibold">See FAQ</a>.
          </p>
        </div>
        </div>
      </section>

      {/* ── 9. FAQ ──────────────────────────────────────────── */}
      <section id="faq" className="w-full bg-stone-50 border-t border-stone-200">
        <div className="max-w-7xl mx-auto px-8 py-16">
        <div className="mb-10">
          <div className="text-xs font-semibold uppercase tracking-widest text-stone-600 mb-2">FAQ</div>
          <h2 className="font-serif text-4xl font-bold text-slate-900">Common questions</h2>
        </div>
        <div className="space-y-2">
          {FAQ_ITEMS.map((item, i) => {
            const open = faqOpen.has(i);
            return (
              <div key={i} className="bg-white border border-stone-200 rounded-xl overflow-hidden">
                <button
                  type="button"
                  onClick={() => {
                    setFaqOpen((prev) => {
                      const next = new Set(prev);
                      next.has(i) ? next.delete(i) : next.add(i);
                      return next;
                    });
                  }}
                  className="w-full flex items-center justify-between px-6 py-4 text-left focus:outline-none focus:ring-2 focus:ring-inset focus:ring-primary-600 group"
                  aria-expanded={open}
                >
                  <span className="font-semibold text-sm text-slate-900 group-hover:text-primary-600 transition-colors">{item.q}</span>
                  <span className={`shrink-0 ml-4 text-stone-600 font-bold text-lg leading-none transition-transform duration-200 ${open ? 'rotate-45' : ''}`}>+</span>
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
        </div>
      </section>

      {/* ── CTA Banner ──────────────────────────────────────── */}
      <section className="w-full bg-stone-50 border-t border-stone-200">
        <div className="max-w-7xl mx-auto px-8 py-20">
        <div className="bg-slate-900 rounded-2xl overflow-hidden relative">
          {/* background illustration */}
          <div className="absolute inset-0 opacity-20">
            <Image
              src="/illustrations/cta-banner.png"
              alt=""
              fill
              className="object-cover object-center"
              aria-hidden="true"
              sizes="100vw"
            />
          </div>
          <div className="relative z-10 p-12 text-center">
          <p className="text-primary-400 text-xs font-semibold uppercase tracking-widest mb-6">
            Winzinvest · System Design Principle
          </p>
          <h2 className="font-serif text-3xl font-bold text-white mb-6 max-w-2xl mx-auto leading-snug">
            &ldquo;Most traders lose not because they can't find an edge.
            They lose because they override it at the worst possible time.
            That's the only problem we solve.&rdquo;
          </h2>
          <p className="text-stone-300 text-sm leading-relaxed mb-8 max-w-lg mx-auto">
            Join the waitlist. We'll let you know when your slot opens.
          </p>
          <div className="flex justify-center gap-3">
            <a
              href="#pricing"
              className="inline-block px-8 py-3 rounded-xl bg-primary-600 hover:bg-primary-500 text-white font-bold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-primary-400 focus:ring-offset-2 focus:ring-offset-slate-900"
            >
              Join the Waitlist
            </a>
            <Link
              href="/methodology"
              className="inline-block px-8 py-3 rounded-xl border border-stone-500 hover:bg-stone-800 text-stone-200 font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-stone-500 focus:ring-offset-2 focus:ring-offset-slate-900"
            >
              Read the Methodology
            </Link>
          </div>
          <p className="text-stone-300 text-xs mt-6">
            Works with Interactive Brokers (full support). Tastytrade support coming soon. Self-directed execution software. Not investment advice.
          </p>
          </div>
        </div>
        </div>
      </section>

      {/* ── Footer ──────────────────────────────────────────── */}
      <footer className="w-full border-t border-stone-200 bg-white">
        <div className="max-w-7xl mx-auto py-10 px-8">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 mb-6">
          <span className="font-serif font-bold text-stone-500 text-sm tracking-tight">
            Winz<span className="text-primary-600">invest</span>
          </span>
          <div className="flex gap-6">
            <Link href="/methodology"    className="text-sm text-stone-600 hover:text-stone-900 transition-colors">How It Works</Link>
            <Link href="/performance"    className="text-sm text-stone-600 hover:text-stone-900 transition-colors">Performance</Link>
            <a href="#pricing"           className="text-sm text-stone-600 hover:text-stone-900 transition-colors">Pricing</a>
            <a href="#faq"               className="text-sm text-stone-600 hover:text-stone-900 transition-colors">FAQ</a>
            <Link href="/login"          className="text-sm text-stone-600 hover:text-stone-900 transition-colors">Log In</Link>
          </div>
        </div>
        <p className="text-xs text-stone-600 leading-relaxed max-w-3xl">
          Winzinvest is self-directed execution software. You connect your own brokerage API (Interactive Brokers now; Tastytrade and Schwab coming soon) and set your own risk parameters. 
          We don't hold funds, provide investment advice, or manage assets. Trading involves substantial 
          risk of loss. Past performance doesn't predict future results. If you lose money, that's on you.
        </p>
        </div>
      </footer>
    </div>
  );
}
