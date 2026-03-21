'use client';

import { use, useEffect, useState } from 'react';
import Link from 'next/link';
import { fetchWithAuth } from '@/lib/fetch-client';


interface BacktestResult {
  symbol: string;
  params: { otm_pct: number; dte: number; profit_take_pct: number };
  annualized_return_pct: number;
  sharpe: number;
  win_rate_pct: number;
  max_drawdown_pct: number;
  num_cycles: number;
}

interface BacktestSummary {
  timestamp: string;
  symbols_tested: string[];
  top_10: BacktestResult[];
  current_params: { otm_pct: number; dte: number; profit_take_pct: number };
}

type PageProps = {
  params?: Promise<Record<string, string | string[]>>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

const EMPTY = Promise.resolve({});

export default function StrategyPage(props: PageProps) {
  use(props.params ?? EMPTY);
  use(props.searchParams ?? EMPTY);
  const [backtest, setBacktest] = useState<BacktestSummary | null>(null);
  const [backtestLoading, setBacktestLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetchWithAuth('/api/backtest-results');
        if (!r.ok || cancelled) return;
        const d = (await r.json()) as BacktestSummary;
        if (!cancelled) setBacktest(d);
      } catch {
        /* 401 → redirect; other errors leave null */
      } finally {
        if (!cancelled) setBacktestLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="min-h-screen bg-stone-50">
      <div className="max-w-4xl mx-auto px-8 py-12">

        {/* Header */}
        <header className="mb-12 pb-6 border-b border-stone-200">
          <Link href="/institutional" className="text-sm text-stone-500 hover:text-stone-600 mb-4 inline-block">
            ← Back to Dashboard
          </Link>
          <h1 className="font-serif text-5xl font-bold text-slate-900 tracking-tight mt-4">
            Combined Trading Strategy
          </h1>
          <p className="text-stone-500 mt-4 text-lg">
            Hybrid NX + AMS equity engine with systematic options premium income overlay — fully automated, regime-aware, Portfolio Margin enabled
          </p>
        </header>

        <div className="prose prose-stone max-w-none">

          {/* Live Account Context */}
          <div className="bg-green-50 border border-green-200 rounded-xl p-6 mb-8">
            <div className="flex items-center gap-3 mb-3">
              <span className="w-2.5 h-2.5 rounded-full bg-green-500 animate-pulse" />
              <span className="text-xs font-semibold uppercase tracking-wider text-green-700">Live Account Active</span>
            </div>
            <p className="text-sm text-green-900 leading-relaxed">
              The system trades a live IBKR account under Portfolio Margin (up to 6–7× leverage).
              Portfolio actively restructured in March 2026 — trimming to <strong>15–20 concentrated positions</strong>, closing decay hedges, and re-enabling the full momentum engine.
              Target return: <strong>40%+ annually</strong> via directional alpha (momentum), options premium income, and zero bleed from non-productive hedges.
              Every entry, exit, roll, and reopen is fully automated with no discretionary override.
            </p>
          </div>

          {/* Equity Backtest — pending formal run */}
          <div className="bg-slate-900 rounded-xl p-8 mb-8 text-white">
            <div className="flex items-start gap-5">
              <div className="w-10 h-10 rounded-full bg-slate-800 border border-slate-600 flex items-center justify-center shrink-0 mt-0.5">
                <span className="text-slate-400 font-bold text-sm">01</span>
              </div>
              <div>
                <h2 className="text-xl font-serif font-bold text-white mb-2">Equity Strategy Backtest</h2>
                <p className="text-slate-400 text-sm leading-relaxed mb-3">
                  A formal 2- and 3-year backtest of the hybrid NX + AMS equity engine is being prepared against the
                  200-symbol universe. Results will be published here once complete — with full methodology,
                  parameter specifications, and out-of-sample validation.
                </p>
                <p className="text-slate-500 text-xs leading-relaxed">
                  We are not publishing estimated or projected figures in their place.
                  Backtest results will reflect actual historical signal replay — not curve-fitted targets.
                </p>
              </div>
            </div>
          </div>

          {/* Live Strategy Attribution */}
          <div className="bg-white border border-stone-200 rounded-xl p-8 mb-8">
            <h2 className="text-2xl font-serif font-bold text-slate-900 mb-2">Live Strategy P&amp;L Attribution</h2>
            <p className="text-stone-500 text-sm mb-6">
              3:1 target ratio of directional alpha to options income — momentum is the primary driver, premium is the yield overlay
            </p>
            <div className="grid grid-cols-2 gap-4">
              {[
                { dot: 'bg-green-500', label: 'Equity Momentum', value: 'Primary alpha', note: 'NX + AMS hybrid · 15–20 concentrated positions · 1.5% risk/trade · 3:1 R/R target · partial exits at 2× ATR' },
                { dot: 'bg-green-600', label: 'Covered Calls', value: 'Yield overlay', note: '15–20 contracts · ~35 DTE · delta 0.20 · PROFIT_ROLL at 80% · calendar/diagonal when stock rallies above strike' },
                { dot: 'bg-purple-600', label: 'Cash-Secured Puts', value: 'Entry income', note: 'Long watchlist only · regime-gated · delta 0.25' },
                { dot: 'bg-blue-600', label: 'Iron Condors', value: 'Opportunistic', note: 'SPY/QQQ · CHOPPY/MIXED only · VIX-scaled size · max 4 open' },
                { dot: 'bg-red-500', label: 'Bearish Shorts', value: 'STRONG_DOWNTREND', note: 'Dedicated bearish screener · 30% allocation · Wilder RSI-filtered · blocked in uptrends' },
                { dot: 'bg-teal-600', label: 'PEAD + VWAP', value: 'Event-driven', note: 'Post-earnings drift screener + intraday VWAP reclaim setups · daily pre-market + 10:00 ET' },
                { dot: 'bg-orange-500', label: 'Dividend Capture', value: 'Income supplement', note: 'Systematic ex-div screener · yield + trend + volume filters · suggested entries + stops' },
                { dot: 'bg-amber-600', label: 'Protective Puts', value: 'Quarterly hedge', note: 'Single OTM SPY put quarterly · ~$1K · replaces decay ETFs' },
                { dot: 'bg-indigo-600', label: 'Sector ETF Hedges', value: 'Bearish/Choppy', note: 'Auto-deploy inverse ETFs for over-concentrated sectors · closes automatically on regime recovery' },
                { dot: 'bg-sky-600', label: 'Tax-Loss Harvesting', value: '~$3–5K/yr', note: 'Friday scan · wash-sale compliant · sector ETF replacements' },
              ].map(({ dot, label, value, note }) => (
                <div key={label} className="bg-stone-50 rounded-lg p-4 border border-stone-200">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`w-3 h-3 rounded-full ${dot} inline-block`} />
                    <span className="font-semibold text-slate-800 text-sm">{label}</span>
                  </div>
                  <p className="text-2xl font-bold text-slate-900">{value}</p>
                  <p className="text-stone-500 text-xs mt-1">{note}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Options Income Engine — detailed */}
          <div className="bg-white border border-stone-200 rounded-xl p-8 mb-8">
            <h2 className="text-2xl font-serif font-bold text-slate-900 mb-2">Options Income Engine</h2>
            <p className="text-stone-500 text-sm mb-6">
              The primary return driver at current account size — runs automatically every morning and manages itself throughout the day
            </p>

            <div className="space-y-6">
              <div className="border-l-4 border-green-600 pl-6">
                <h3 className="text-xl font-bold text-slate-900 mb-1">
                  Covered Calls
                  <span className="text-sm font-normal text-stone-500 ml-2">Primary income · existing positions ≥100 shares</span>
                </h3>
                <p className="text-stone-600 leading-relaxed mb-2">
                  Sell calls against stock positions of ≥100 shares at least 0.5% above entry. Strike delta-targeted at
                  ~0.20 (≥10% OTM floor). IV rank ≥0.45. Premium ≥0.8%. DTE 35 days.
                  When premium decays 80%+, the position is automatically closed <em>and reopened</em> (PROFIT_ROLL)
                  at a fresh 35 DTE strike — compounding income within the same cycle. The roll strategy adapts to
                  market conditions: <strong>diagonal</strong> when the stock has rallied &gt;5% above the strike (higher OTM strike for reduced delta),
                  <strong> calendar</strong> when near ATM with significant DTE remaining, or <strong>standard</strong> in all other cases.
                  Contract size scales with IV rank — larger at elevated volatility, smaller when premiums are thin.
                </p>
                <div className="bg-stone-50 rounded-lg p-3 text-sm space-y-1">
                  <p><strong>Dividend guard:</strong> Skips the call if ex-div date falls inside the expiry window and dividend &gt; 70% of premium, or ex-div is within 5 days of expiry (early assignment risk)</p>
                  <p><strong>Assignment monitor:</strong> Every 30 min — Telegram alert if option drifts within 2% of ITM (APPROACHING), crosses ITM, or goes deep ITM (&gt;3%)</p>
                  <p><strong>Delta drift alert:</strong> Urgent alert fires when short call delta exceeds 0.50 (deep ITM) — flags specific symbol, delta, and DTE, recommends immediate roll action</p>
                  <p><strong>Auto-roll:</strong> Rolled at DTE ≤7 or if ITM by ≥2% — new position opened at 35 DTE, delta-targeted strike, roll strategy selected dynamically</p>
                </div>
              </div>

              <div className="border-l-4 border-purple-600 pl-6">
                <h3 className="text-xl font-bold text-slate-900 mb-1">
                  Cash-Secured Puts
                  <span className="text-sm font-normal text-stone-500 ml-2">Entry income · long watchlist + premium-selling candidates</span>
                </h3>
                <p className="text-stone-600 leading-relaxed mb-2">
                  Sell puts on stocks we want to own at a lower price: 1.5–10% pullback from 20-day high,
                  near 50-EMA support, IV rank ≥0.45, pullback ≤$50K assignment risk per contract.
                  Also targets high-IV names from the premium-selling short screener — collecting rich premium
                  with assignment at a discount as the floor case.
                </p>
                <div className="bg-stone-50 rounded-lg p-3 text-sm space-y-1">
                  <p><strong>Active regimes:</strong> CHOPPY, MIXED, STRONG_UPTREND only (blocked during downtrends)</p>
                  <p><strong>Regime block:</strong> STRONG_DOWNTREND and UNFAVORABLE — assignment losses too costly</p>
                </div>
              </div>

              <div className="border-l-4 border-blue-600 pl-6">
                <h3 className="text-xl font-bold text-slate-900 mb-1">
                  Iron Condors
                  <span className="text-sm font-normal text-stone-500 ml-2">Sideways income · SPY &amp; QQQ</span>
                </h3>
                <p className="text-stone-600 leading-relaxed mb-2">
                  Sell 10% OTM put + 10% OTM call on SPY/QQQ, buy 15% OTM wings. Credit ~30% of max risk.
                  Most impactful in CHOPPY regimes — exactly when equity momentum generates less.
                </p>
                <div className="bg-stone-50 rounded-lg p-3 text-sm">
                  <p><strong>Active regimes:</strong> CHOPPY, MIXED, STRONG_UPTREND when IV rank &gt;0.30 · max 4 open</p>
                </div>
              </div>

              <div className="border-l-4 border-amber-500 pl-6">
                <h3 className="text-xl font-bold text-slate-900 mb-1">
                  Protective Puts
                  <span className="text-sm font-normal text-stone-500 ml-2">Tail-risk hedge · SPY only</span>
                </h3>
                <p className="text-stone-600 leading-relaxed mb-2">
                  Buy SPY puts 7% OTM as portfolio insurance during uncertain regimes.
                  Monthly budget capped at min($15K, 0.75% of NLV). Max 2 open. DTE 30 days.
                </p>
                <div className="bg-stone-50 rounded-lg p-3 text-sm">
                  <p><strong>Active regimes:</strong> MIXED, UNFAVORABLE, STRONG_DOWNTREND</p>
                </div>
              </div>
            </div>
          </div>

          {/* Auto-Optimization */}
          <div className="bg-white border border-stone-200 rounded-xl p-8 mb-8">
            <h2 className="text-2xl font-serif font-bold text-slate-900 mb-2">Automated Optimization</h2>
            <p className="text-stone-500 text-sm mb-6">The system continuously backtests itself and surfaces optimal parameters every week</p>

            {backtestLoading ? (
              <div className="animate-pulse space-y-3" aria-busy="true" aria-label="Loading backtest results">
                <div className="h-4 bg-stone-200 rounded w-2/3" />
                <div className="h-24 bg-stone-100 rounded-lg border border-stone-200" />
              </div>
            ) : backtest ? (
              <div>
                <div className="flex items-center gap-3 mb-4">
                  <span className="text-xs text-stone-400">Last run: {new Date(backtest.timestamp).toLocaleDateString()}</span>
                  <span className="text-xs text-stone-400">·</span>
                  <span className="text-xs text-stone-400">{backtest.symbols_tested.length} symbols tested</span>
                  <span className="text-xs text-stone-400">·</span>
                  <span className="text-xs font-semibold text-stone-600">
                    Current: {backtest.current_params.otm_pct}% OTM · {backtest.current_params.dte} DTE · {backtest.current_params.profit_take_pct}% PT
                  </span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-stone-200">
                        {['Symbol', 'OTM%', 'DTE', 'Profit-Take', 'Ann. Return', 'Sharpe', 'Win Rate', 'Cycles'].map((h) => (
                          <th key={h} className="text-left py-2 px-2 text-stone-500 font-semibold">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {backtest.top_10.slice(0, 8).map((r, i) => (
                        <tr key={i} className="border-b border-stone-100 hover:bg-stone-50">
                          <td className="py-2 px-2 font-bold text-slate-800">{r.symbol}</td>
                          <td className="py-2 px-2 text-stone-600">{r.params.otm_pct}%</td>
                          <td className="py-2 px-2 text-stone-600">{r.params.dte}d</td>
                          <td className="py-2 px-2 text-stone-600">{r.params.profit_take_pct}%</td>
                          <td className="py-2 px-2 font-semibold text-green-700">{(r.annualized_return_pct ?? 0).toFixed(1)}%</td>
                          <td className="py-2 px-2 font-semibold text-slate-800">{(r.sharpe ?? 0).toFixed(2)}</td>
                          <td className="py-2 px-2 text-stone-600">{(r.win_rate_pct ?? 0).toFixed(0)}%</td>
                          <td className="py-2 px-2 text-stone-500">{r.num_cycles}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <div className="bg-stone-50 rounded-lg p-6 border border-stone-200">
                <p className="text-stone-600 text-sm mb-3">
                  <strong>Every Friday post-close</strong>, `options_backtester.py` runs 80 parameter combinations
                  (5 OTM% × 4 DTE × 4 profit-take%) across the top 10 holdings and ranks by Sharpe ratio.
                </p>
                <p className="text-stone-500 text-xs">Results appear here after the first Friday run. Manual run: <code className="bg-stone-200 px-1 rounded">python3 options_backtester.py --months 6</code></p>
              </div>
            )}
          </div>

          {/* Market Regime */}
          <div className="bg-white border border-stone-200 rounded-xl p-8 mb-8">
            <h2 className="text-2xl font-serif font-bold text-slate-900 mb-4">Market Regime Engine</h2>
            <p className="text-stone-600 leading-relaxed mb-4">
              The system runs <strong>two layered regime classifiers</strong> that work together.
              Both are evaluated twice daily (7:45 AM and 12:45 PM MT). Regime changes trigger a Telegram alert immediately.
            </p>

            {/* Layer 1: Execution Regime */}
            <h3 className="text-lg font-bold text-slate-800 mb-2 mt-6">
              Layer 1 — Execution Regime
              <span className="text-sm font-normal text-stone-500 ml-2">Gates which strategies run · SPY vs 200 SMA + VIX</span>
            </h3>
            <p className="text-stone-600 text-sm mb-3">
              Classifies the market using SPY&apos;s distance from its 200-day SMA and the current VIX level.
              This determines which executors are active and what allocation each receives.
              Long/short capacity figures show the fraction of total slots available for each side.
            </p>
            <div className="space-y-3">
              {[
                { regime: 'STRONG_UPTREND', color: 'bg-green-100 border-green-300 text-green-800', action: 'Longs: 100% capacity · Shorts: none · ICs when IV rank >0.30 · Covered calls fully active · No new CSPs blocked.' },
                { regime: 'CHOPPY',         color: 'bg-blue-100 border-blue-300 text-blue-800',   action: 'Longs: 85% capacity · Shorts: 35% capacity · Iron condors + covered calls + CSPs all active.' },
                { regime: 'MIXED',          color: 'bg-amber-100 border-amber-300 text-amber-800', action: 'Longs: 80% capacity · Shorts: 25% capacity · ICs + protective puts active · entry criteria tightened.' },
                { regime: 'STRONG_DOWNTREND', color: 'bg-red-100 border-red-300 text-red-800',    action: 'Longs: 50% capacity · Shorts: 30% capacity (dedicated bearish screener) · No new CSPs · Protective puts + sector ETF hedges active.' },
                { regime: 'UNFAVORABLE',    color: 'bg-stone-100 border-stone-300 text-stone-600', action: 'Longs: 0 · Shorts: 0 · No new positions of any kind. Options income fully paused.' },
              ].map(({ regime, color, action }) => (
                <div key={regime} className={`flex items-start gap-3 px-4 py-3 rounded-lg border ${color}`}>
                  <code className="text-xs font-mono font-bold mt-0.5 whitespace-nowrap">{regime}</code>
                  <span className="text-sm">{action}</span>
                </div>
              ))}
            </div>

            {/* Layer 2: Macro Regime Monitor */}
            <h3 className="text-lg font-bold text-slate-800 mb-2 mt-8">
              Layer 2 — Macro Regime Band
              <span className="text-sm font-normal text-stone-500 ml-2">Adjusts sizing parameters · Multi-indicator score · Shown on dashboard</span>
            </h3>
            <p className="text-stone-600 text-sm mb-3">
              A scored composite of macro stress indicators, seven commodity supply-chain signals, and real-time news sentiment.
              Each indicator contributes independently to a 0–10+ score. Does not gate which strategies run — instead, it tightens or loosens the{' '}
              <em>position sizing parameters</em> used by the AMS executor. Commodity triggers also feed into sector rotation multipliers:
              oil and copper drive Energy and Materials sizing; corn and soybeans penalise Consumer Staples and Discretionary via the
              livestock-chain alert; the USD index scales commodity-sector multipliers inversely. Two compound alerts fire when multiple
              chains are stressed simultaneously: <em>food_chain_alert</em> (oil + wheat/natgas) and <em>livestock_chain_alert</em> (corn/soy).
              This is the regime band shown on the Overview dashboard card.
            </p>
            <div className="overflow-x-auto mb-4">
              <table className="w-full text-xs text-stone-600 border-collapse">
                <thead>
                  <tr className="bg-stone-50 border-b border-stone-200">
                    <th className="text-left px-3 py-2 font-semibold text-stone-700">Indicator</th>
                    <th className="text-left px-3 py-2 font-semibold text-stone-700">Data source</th>
                    <th className="text-left px-3 py-2 font-semibold text-stone-700">Trigger condition</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { name: 'VIX Term Structure', src: 'Yahoo Finance (^VIX, ^VIX3M)', trigger: 'Backwardation (VIX > VIX3M) — front-month fear premium spike' },
                    { name: 'HY Credit Spreads', src: 'FRED · BAMLH0A0HYM2', trigger: '+25 bps/day, +50 bps/10 days, or absolute ≥ 400 bps' },
                    { name: 'Real Yields (10Y TIPS)', src: 'FRED · DFII10', trigger: '≥ 2.0% or at/near 6-month high (real rate headwind for equities)' },
                    { name: 'Financial Conditions (NFCI)', src: 'FRED · NFCI', trigger: '> 0 — credit/leverage/risk sub-index tightening' },
                    { name: 'Industrial Production', src: 'FRED · IPMAN', trigger: '3-month decline ≥ 1.5% or YoY decline ≥ 3%' },
                    { name: 'Oil Price (WTI Crude)', src: 'Yahoo Finance (CL=F)', trigger: '30d: +20% surge (+2), +40% crisis (+3), −20% collapse (+1) — Energy sector multiplier; USD interaction applied' },
                    { name: 'Wheat Futures', src: 'Yahoo Finance (ZW=F)', trigger: '30d: +15% surge (info), +30% crisis (+1) — food cost inflation; combines with oil for food_chain_alert' },
                    { name: 'Natural Gas', src: 'Yahoo Finance (NG=F)', trigger: '30d: +25% surge (info), +50% crisis (+1) — fertilizer feedstock proxy; part of food chain' },
                    { name: 'Copper Futures', src: 'Yahoo Finance (HG=F)', trigger: '30d: +20% surge (+1) → Materials/Industrials boost; −20% collapse (+1) → demand warning' },
                    { name: 'Corn Futures', src: 'Yahoo Finance (ZC=F)', trigger: '30d: +20% surge (+1), +35% crisis (+2) — animal feed / ethanol chain; Consumer Staples penalty' },
                    { name: 'Soybean Futures', src: 'Yahoo Finance (ZS=F)', trigger: '30d: +20% surge (+1), +35% crisis (+2) — crush margin pressure on ag processors; livestock chain signal' },
                    { name: 'USD Index', src: 'Yahoo Finance (DX-Y.NYB)', trigger: '30d: +5% strong (+1) → commodity price suppression; −5% weak (+1) → commodity inflation' },
                    { name: 'News Sentiment', src: 'Marketaux API', trigger: 'Macro keyword sentiment ≤ −0.5 bearish (+1), ≤ −0.7 very bearish (+2) — portfolio + macro headlines' },
                  ].map(({ name, src, trigger }) => (
                    <tr key={name} className="border-b border-stone-100 last:border-0">
                      <td className="px-3 py-2 font-medium text-slate-700 whitespace-nowrap">{name}</td>
                      <td className="px-3 py-2 text-stone-500 whitespace-nowrap font-mono text-[11px]">{src}</td>
                      <td className="px-3 py-2 text-stone-600">{trigger}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="space-y-3">
              {[
                { band: 'RISK_ON',    emoji: '🟢', color: 'bg-emerald-100 border-emerald-300 text-emerald-800', desc: 'Score 0–1. Full size (1.0×). Standard z-entry (2.0). Normal 3-day cooldown.' },
                { band: 'NEUTRAL',    emoji: '⚠️', color: 'bg-amber-100 border-amber-300 text-amber-800',    desc: 'Score 2–3. Size reduced to 0.75×. Z-entry raised to 2.25. 5-day cooldown.' },
                { band: 'TIGHTENING', emoji: '🟠', color: 'bg-orange-100 border-orange-300 text-orange-800', desc: 'Score 4–5. Size cut to 0.50×. Z-entry raised to 2.50. 8-day cooldown.' },
                { band: 'DEFENSIVE',  emoji: '🔴', color: 'bg-red-100 border-red-300 text-red-800',          desc: 'Score 6+.  Size cut to 0.25×. Z-entry raised to 3.0. 13-day cooldown.' },
              ].map(({ band, emoji, color, desc }) => (
                <div key={band} className={`flex items-start gap-3 px-4 py-3 rounded-lg border ${color}`}>
                  <span className="text-base mt-0.5">{emoji}</span>
                  <code className="text-xs font-mono font-bold mt-0.5 whitespace-nowrap">{band}</code>
                  <span className="text-sm">{desc}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Equity Strategies */}
          <div className="bg-white border border-stone-200 rounded-xl p-8 mb-8">
            <h2 className="text-2xl font-serif font-bold text-slate-900 mb-4">Equity Strategies</h2>
            <div className="space-y-6 mt-2">
              {[
                {
                  color: 'border-green-600',
                  title: '1. Hybrid Momentum Longs',
                  body: 'Screens 200+ symbols daily using composite score (momentum + Bollinger + RSI), relative strength vs SPY, structure quality, higher-timeframe bias, and AMS volume score. Every candidate is then confirmed across three timeframes (weekly, daily, intraday), boosted by post-earnings drift when detected, and sized according to sector relative strength. Combined score ≥0.50 required. Exits: take-profit 3.5× ATR, trailing stop 3.0× ATR (activates after 1R banked), hard stop 1.5× ATR, 20-day time stop.',
                },
                {
                  color: 'border-red-500',
                  title: '2. Bearish Momentum Shorts',
                  body: 'Two-tier short execution. In CHOPPY/MIXED regimes: small hedge overlay via the dual-mode executor — capped at 8–10% of slots, requires composite <0.20 and structure <0.20. In STRONG_DOWNTREND: the dedicated bearish screener (nx_screener_shorts) runs its own pass — looking for stocks below their 200-day SMA with negative relative strength (RSI 40–68 for entry opportunity), poor volume quality, and no recent earnings. This tier receives 30% short allocation at 1.0× position sizing, functioning as a primary income source rather than a hedge overlay. Blocked in STRONG_UPTREND and UNFAVORABLE.',
                },
                {
                  color: 'border-amber-600',
                  title: '3. Mean Reversion (RSI-2 Pullbacks)',
                  body: 'Buys short-term oversold pullbacks (RSI(2) <10) in stocks above their 200-day SMA. Tight stops (1× ATR), take-profit (1.5× ATR), 5-day max hold, exits when RSI(2) >70.',
                },
                {
                  color: 'border-blue-600',
                  title: '4. Pairs Trading',
                  body: 'Market-neutral long/short on historically correlated pairs. Enters when spread z-score exceeds divergence threshold; exits on mean reversion or time stop. 2× ATR stop, 3× ATR take-profit per leg.',
                },
              ].map(({ color, title, body }) => (
                <div key={title} className={`border-l-4 ${color} pl-6`}>
                  <h3 className="text-xl font-bold text-slate-900 mb-2">{title}</h3>
                  <p className="text-stone-600 leading-relaxed">{body}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Edge Enhancements */}
          <div className="bg-white border border-stone-200 rounded-xl p-8 mb-8">
            <h2 className="text-2xl font-serif font-bold text-slate-900 mb-2">Edge Enhancements</h2>
            <p className="text-stone-500 text-sm mb-6">
              Three additive confirmation layers that improve entry quality without changing the fundamental strategy — each grounded in well-documented market structure research
            </p>

            <div className="space-y-6">
              <div className="border-l-4 border-sky-600 pl-6">
                <h3 className="text-xl font-bold text-slate-900 mb-1">
                  Multi-Timeframe Confirmation
                  <span className="text-sm font-normal text-stone-500 ml-2">Weekly + Daily + Intraday alignment scoring</span>
                </h3>
                <p className="text-stone-600 leading-relaxed mb-2">
                  Every candidate receives an MTF alignment score from 0.0 (conflicting) to 1.0 (all aligned).
                  Three timeframes are evaluated independently: the <strong>weekly trend</strong> (65-day ROC + price vs 50-day SMA),
                  the <strong>daily trend</strong> (20-day ROC + price vs 20-day SMA), and an <strong>intraday proxy</strong> (5-day ROC + linear regression slope).
                  Each uses a tanh-sigmoid to normalize signals.
                </p>
                <div className="bg-stone-50 rounded-lg p-3 text-sm space-y-1">
                  <p><strong>STRONG alignment (≥0.7):</strong> +15% conviction boost → 1.12× hybrid score multiplier → larger position size</p>
                  <p><strong>MODERATE (0.5–0.7):</strong> Neutral — no boost, no penalty</p>
                  <p><strong>CONFLICTING (&lt;0.3):</strong> −15% conviction penalty → 0.92× score multiplier → smaller position or filtered out</p>
                  <p><strong>Works for both sides:</strong> Signals are inverted for short candidates — downtrend alignment boosts short conviction</p>
                </div>
              </div>

              <div className="border-l-4 border-amber-600 pl-6">
                <h3 className="text-xl font-bold text-slate-900 mb-1">
                  Post-Earnings Drift Catalyst
                  <span className="text-sm font-normal text-stone-500 ml-2">PEAD anomaly detection · additive conviction boost</span>
                </h3>
                <p className="text-stone-600 leading-relaxed mb-2">
                  Detects recent earnings events within a 10-day lookback using yfinance earnings dates.
                  Measures the <strong>overnight gap</strong> (close-to-close on announcement day) and <strong>follow-through drift</strong> (announcement close to current close).
                  Requires a 2%+ gap in the directional bias plus 1%+ continuation to activate.
                </p>
                <div className="bg-stone-50 rounded-lg p-3 text-sm space-y-1">
                  <p><strong>Boost range:</strong> 0.0 to 0.25 — additive to hybrid_score (not multiplicative)</p>
                  <p><strong>Scoring:</strong> 60% gap magnitude (capped at 10% gap = max contribution) + 40% drift magnitude (capped at 8%)</p>
                  <p><strong>Recency decay:</strong> Linear fade over 10 days — a 2-day-old catalyst scores higher than a 9-day-old one</p>
                  <p><strong>Research basis:</strong> Post-Earnings Announcement Drift is one of the most persistent anomalies in finance, driven by institutional rebalancing lags</p>
                </div>
              </div>

              <div className="border-l-4 border-purple-600 pl-6">
                <h3 className="text-xl font-bold text-slate-900 mb-1">
                  Sector Rotation Overlay
                  <span className="text-sm font-normal text-stone-500 ml-2">Lean-in / lean-out sizing · 11 GICS sectors ranked by 63-day RS</span>
                </h3>
                <p className="text-stone-600 leading-relaxed mb-2">
                  Transforms the existing sector gate from a passive &ldquo;cap only&rdquo; mechanism into an active <strong>lean-in / lean-out</strong> overlay.
                  All 11 SPDR sector ETFs (XLK, XLF, XLE, etc.) are ranked by 63-day return.
                  Rankings are mapped to GICS sector names via ETF-to-sector mapping, then applied as a position-sizing multiplier.
                </p>
                <div className="bg-stone-50 rounded-lg p-3 text-sm space-y-1">
                  <p><strong>TOP tier (ranks 1–3):</strong> 1.25× position sizing multiplier → overweight strongest momentum sectors</p>
                  <p><strong>MID tier (ranks 4–7):</strong> 1.0× neutral — no boost, no penalty</p>
                  <p><strong>BOTTOM tier (ranks 8–11):</strong> 0.75× sizing penalty → underweight weak sectors, conserving capital</p>
                  <p><strong>Double integration:</strong> Affects both screener ranking (hybrid_score) and executor conviction (position sizing)</p>
                  <p><strong>Updated:</strong> Daily at post-close (14:30 MT) via sector_rotation.py → sector_allocation.json</p>
                </div>
              </div>
            </div>

            <div className="bg-stone-50 rounded-lg p-4 border border-stone-200 mt-6">
              <p className="text-sm text-stone-600">
                <strong>Combined effect:</strong> A momentum setup with STRONG MTF alignment, a recent earnings catalyst, and a top-ranked sector
                receives up to <strong>+50% higher conviction</strong> than the same setup without these confirmations — translating directly to larger
                position sizes through the ATR-based sizing engine. The three layers are independent and additive.
              </p>
            </div>

            <div className="mt-8 space-y-6">
              <div className="border-l-4 border-orange-500 pl-6">
                <h3 className="text-xl font-bold text-slate-900 mb-1">
                  PEAD Dedicated Screener
                  <span className="text-sm font-normal text-stone-500 ml-2">Post-earnings drift scanner · runs pre-market daily</span>
                </h3>
                <p className="text-stone-600 leading-relaxed mb-2">
                  Separate from the MTF PEAD boost, this standalone screener runs each morning and outputs a ranked list of
                  <strong> 1–10 day post-earnings drift setups</strong>. Criteria: gap ≥3% in the earnings direction,
                  follow-through drift ≥1%, price above 20-day SMA, RSI between 40 and 75, and volume confirmation
                  at 1.5× the 20-day average. Uses Wilder RSI to match TradingView/Bloomberg calibration.
                </p>
                <div className="bg-stone-50 rounded-lg p-3 text-sm space-y-1">
                  <p><strong>Output:</strong> <code className="bg-stone-200 px-1 rounded text-xs">watchlist_pead.json</code> — ranked candidates with gap%, drift%, RSI, volume multiplier, and capture score</p>
                  <p><strong>Dashboard:</strong> Surfaced on the PEAD tab — not automatically traded, requires manual review</p>
                  <p><strong>Window:</strong> Scored on days 1–10 post-earnings; linear decay eliminates stale setups automatically</p>
                </div>
              </div>

              <div className="border-l-4 border-teal-600 pl-6">
                <h3 className="text-xl font-bold text-slate-900 mb-1">
                  Intraday VWAP Reclaim Scanner
                  <span className="text-sm font-normal text-stone-500 ml-2">Gap-down reversal detection · 10:00–12:00 ET window</span>
                </h3>
                <p className="text-stone-600 leading-relaxed mb-2">
                  Scans portfolio holdings and watchlist names for intraday gap-down + VWAP reclaim setups.
                  Criteria: gap down &gt;1% at the open, price subsequently crosses VWAP to the upside within the
                  first 90 minutes, and the reclaim candle carries above-average volume (1.3× 20-day average).
                  The 20-day SMA check confirms the stock is in a longer-term uptrend — filtering out dead-cat bounces.
                </p>
                <div className="bg-stone-50 rounded-lg p-3 text-sm space-y-1">
                  <p><strong>Timing:</strong> Only runs between 10:00 and 12:00 ET — before this window, VWAP has insufficient accumulation; after it, the signal is stale</p>
                  <p><strong>Output:</strong> <code className="bg-stone-200 px-1 rounded text-xs">watchlist_vwap_reclaim.json</code> — ranked setups with gap%, VWAP reclaim %, and volume multiplier</p>
                  <p><strong>Alert:</strong> Top setups fire a Telegram notification for same-session consideration</p>
                </div>
              </div>
            </div>
          </div>

          {/* Risk Management */}
          <div className="bg-white border border-stone-200 rounded-xl p-8 mb-8">
            <h2 className="text-2xl font-serif font-bold text-slate-900 mb-4">Risk Management Stack</h2>
            <ul className="space-y-3 text-stone-600">
              {[
                { label: 'Drawdown circuit breaker', desc: 'Three graduated tiers: -3% daily → reduce position sizes 50%; -5% → halt all new entries; -8% → activate kill switch automatically. Resets each morning.' },
                { label: 'Kill switch', desc: 'One-click halt from the dashboard (mobile or desktop). Also auto-activates at the -8% drawdown tier. Blocks all executors until manually cleared.' },
                { label: 'Assignment risk alerts', desc: 'Every 30 min: Telegram alerts when short options drift within 2% of ITM (APPROACHING), cross ITM, go deep ITM (>3%), or have an upcoming ex-dividend date creating early assignment risk.' },
                { label: 'Execution gates', desc: 'Every order passes 10 gates before reaching the broker: daily loss limit, sector concentration (25% max), gap-risk window (no entries within 60 min of close), regime gate (shorts blocked in downtrends), position size (8% NLV cap), total notional cap (1.8× equity), per-position concentration, portfolio heat (open risk ≤ 8% equity), losing streak cooldown, and correlation gate (blocks new positions highly correlated with existing holdings). Additionally, stop-loss triggers at the open use a gap grace period: small gaps (<3%) get a 15-minute window to recover; large gaps (≥3%) execute immediately without waiting.' },
                { label: 'Dividend awareness', desc: 'Before writing any covered call, checks upcoming ex-dividend dates. Skips the call if the quarterly dividend exceeds 70% of call premium or ex-div is within 5 days of expiry.' },
                { label: 'Sector concentration', desc: 'Capped at 25% of equity per sector — auto-rebalancer closes weakest position when breached. Unmapped symbols trigger a dashboard warning and Telegram alert.' },
                { label: 'Correlation monitoring', desc: 'Live 60-day correlation matrix for top 15 holdings on the dashboard. High average correlation (>0.6) = concentrated risk — Portfolio Margin penalizes correlated books.' },
                { label: 'Earnings blackout', desc: 'No new options within 7 days of earnings announcement. Checked on every covered call and CSP candidate.' },
                { label: 'Tax-loss harvesting', desc: 'Weekly Friday scan for positions with unrealized losses >$200 / 5%+ held >31 days. Suggests wash-sale-compliant sector ETF replacements. Estimated $3–5K annual tax savings.' },
                { label: 'Portfolio Margin', desc: 'Account upgraded to Portfolio Margin — up to 6–7× leverage based on portfolio-wide risk vs fixed Reg T 2:1. Significantly expands capacity for covered calls and new positions.' },
                { label: 'Sector ETF hedging', desc: 'In STRONG_DOWNTREND and CHOPPY regimes, over-concentrated sectors receive automatic inverse ETF hedges (e.g., DRIP for Energy, SRS for Real Estate). Hedges sized proportionally to sector exposure. Closed automatically when regime recovers to MIXED or RISK_ON.' },
                { label: 'Re-entry watchlist', desc: 'Stopped-out positions are monitored for 30 days post-exit. Re-entry fires when: price > exit + 2% buffer, price > 20-day SMA, and RSI > 50. Stale entries expire automatically and are pruned to prevent unbounded list growth.' },
                { label: 'Partial profit scaling', desc: 'Equity positions may exit 50% at 2× ATR profit threshold, returning capital to the pool for redeployment. The remaining 50% continues with a tightened trailing stop. Improves realized win rate without abandoning winners early.' },
                { label: 'Options delta drift protection', desc: 'Short covered calls are monitored continuously for delta drift above 0.50 (deep ITM = elevated assignment risk). When triggered, an urgent Telegram alert fires with symbol, delta, DTE, and roll recommendation. Runs as part of the 30-minute options manager cycle.' },
              ].map(({ label, desc }) => (
                <li key={label} className="flex items-start">
                  <span className="text-green-600 font-bold mr-3 mt-0.5">✓</span>
                  <span><strong>{label}:</strong> {desc}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Key Parameters */}
          <div className="bg-white border border-stone-200 rounded-xl p-8 mb-8">
            <h2 className="text-2xl font-serif font-bold text-slate-900 mb-4">Key Parameters</h2>
            <div className="grid grid-cols-2 gap-4 text-sm">
              {[
                { label: 'Take profit', value: '3.5× ATR from entry', note: 'Equity longs/shorts' },
                { label: 'Hard stop', value: '1.5× ATR from entry', note: 'Initial stop-loss' },
                { label: 'Trailing stop', value: '3.0× ATR · activates at 1R', note: 'Only trails after 1R profit banked' },
                { label: 'Time stop', value: '20 days max hold', note: 'Equity positions' },
                { label: 'Options profit-take', value: '80% premium decay', note: 'Then auto-reopen (PROFIT_ROLL)' },
                { label: 'Options stop-loss', value: '2× collected premium', note: 'Buy-to-close to cut loss' },
                { label: 'Options roll trigger', value: 'DTE ≤ 7 or ITM > 2%', note: 'Roll to 35 DTE, delta-targeted' },
                { label: 'Options target delta', value: '0.20 calls · 0.25 puts', note: 'Via delta_strike_selector.py' },
                { label: 'Score floor', value: 'Combined score ≥ 0.50', note: 'Rejects low-conviction longs' },
                { label: 'Risk per trade', value: '1.5% of equity', note: 'ATR-normalized · ~$2,400 at current NLV' },
                { label: 'Max position', value: '8% of NLV per name', note: 'Hard cap — position concentration gate' },
                { label: 'Drawdown tiers', value: '-3% / -5% / -8%', note: 'Reduce / Halt / Kill switch' },
              ].map(({ label, value, note }) => (
                <div key={label} className="bg-stone-50 rounded-lg p-4 border border-stone-200">
                  <p className="text-xs text-stone-500 uppercase tracking-wide mb-1">{label}</p>
                  <p className="font-bold text-slate-900">{value}</p>
                  <p className="text-stone-500 text-xs mt-1">{note}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Automation Stack */}
          <div className="bg-white border border-stone-200 rounded-xl p-8 mb-8">
            <h2 className="text-2xl font-serif font-bold text-slate-900 mb-4">Automation Stack</h2>
            <p className="text-stone-600 leading-relaxed mb-4">
              Everything runs on a cron-like scheduler (APScheduler). No manual intervention is required on any normal trading day.
            </p>
            <div className="space-y-2 text-sm font-mono">
              {[
                ['05:30 MT', 'Pre-mkt orders', 'Extended-hours limit orders executed (watchlist_ext_hours.json)'],
                ['07:00 MT', 'Pre-market', 'Screeners run: NX longs, dual-mode, mean reversion, pairs, bearish shorts (nx_screener_shorts), PEAD (pead_screener), dividend capture → TV watchlist exported'],
                ['07:35 MT (Tue)', 'Restructure P1', 'Phase 1: close decay hedges + worst energy (auto-exits once no targets remain)'],
                ['07:35 MT (Wed)', 'Restructure P2', 'Phase 2: close ETFs + weak discretionary names'],
                ['07:35 MT (Fri)', 'Restructure P3', 'Phase 3: momentum review of MAYBE positions — trim if 5-day trend negative'],
                ['07:30 MT', 'Market open', 'Execute longs, dual-mode, mean reversion, bearish shorts from screener output; sector hedge executor evaluates and opens/closes ETF hedges based on regime; pending stop/TP orders checked against live prices'],
                ['07:32 MT', 'Gap scan', 'All long positions scanned for opening gap vs prior close. CRITICAL alert ≥3% down (execute immediately), WARNING ≥1.5% down (grace period), INFO ≥2% up (CC assignment risk check)'],
                ['07:35 MT', 'ATR stop ratchet', 'Recalculate 14-period ATR for every position; raise stops where new ATR-based level > existing stop (ratchet rule — stops never lower); auto-create stops for any new position; re-entry watchlist scanned for recovery signals'],
                ['07:45 MT', 'Regime check', 'Both regime layers run: SPY/VIX execution regime + macro band scored; result persisted to dashboard; Telegram alert on change'],
                ['08:00 MT', 'Options', 'Covered calls + CSPs scanned and executed; daily options email sent with stop column (price + % distance, colour-coded red/amber/grey)'],
                ['08:15 MT', 'Re-screen', 'Post-opening-noise screeners re-run for confirmed signals'],
                ['08:30 MT', 'VWAP scan', 'VWAP reclaim scanner identifies gap-down reversals with volume confirmation (10:00–12:00 ET window)'],
                ['08:30 MT', 'Execute', 'Post-open execution on confirmed signals'],
                ['Every 30m', 'Options mgr', 'Profit-take/roll/stop-loss check; assignment risk alerts'],
                ['Every 30m', 'Cash monitor', 'Drawdown breaker evaluated; idle cash deployed'],
                ['11:30 MT', 'Afternoon', 'Afternoon screeners + pairs; options re-scan'],
                ['12:45 MT', 'Regime check', 'Second daily regime pass — both layers re-evaluated; Telegram alert on change'],
                ['13:00 MT (Fri)', 'Tax harvest', 'Weekly tax-loss harvest — scan + auto-execute qualifying positions (wash-sale compliant, Telegram summary)'],
                ['13:55 MT', 'Gap risk', 'EOD gap risk check before close'],
                ['14:00 MT', 'Pre-close', 'Portfolio snapshot + daily report + options email'],
                ['14:30 MT', 'Post-close', 'Strategy analytics, adaptive params, EOD analysis'],
                ['15:00 MT (Fri)', 'Backtester', 'Options parameter sweep across top 10 holdings'],
              ].map(([time, phase, desc], i) => (
                <div key={`${phase}-${i}`} className="grid grid-cols-[110px_120px_1fr] gap-2 py-1.5 border-b border-stone-100 last:border-0">
                  <span className="text-stone-500">{time}</span>
                  <span className="font-semibold text-slate-700">{phase}</span>
                  <span className="text-stone-600 font-sans">{desc}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Why It Works */}
          <div className="bg-white border border-stone-200 rounded-xl p-8 mb-8">
            <h2 className="text-2xl font-serif font-bold text-slate-900 mb-4">Why This Approach Works</h2>
            <ol className="space-y-3 text-stone-600 list-decimal list-inside">
              <li><strong>Momentum is the primary return driver:</strong> A 45% win rate at 3:1 reward/risk on ~120 trades/year mathematically produces 40%+ returns on the active position book. Multi-timeframe confirmation improves the base win rate by filtering out false signals. Earnings catalysts and sector rotation overlay further concentrate capital on the highest-probability setups. Options premium is additive — not the load-bearing pillar.</li>
              <li><strong>The portfolio has something working in every regime:</strong> Momentum longs dominate in uptrends. Options income dominates in sideways markets. Bearish shorts and sector ETF hedges activate in downtrends. Mean reversion and VWAP reclaim setups fire in volatile, range-bound sessions. No single market environment leaves the portfolio idle.</li>
              <li><strong>PROFIT_ROLL eliminates dead premium days:</strong> When a call reaches 80% decay, it is closed and immediately reopened at a fresh 35 DTE strike with a new premium. The roll strategy adapts — diagonal when the stock has rallied above strike, calendar near ATM, standard otherwise. Each position generates 1.2–1.5× the premium of a hold-to-expiry approach over a full year.</li>
              <li><strong>Graduated risk response:</strong> The drawdown circuit breaker prevents a bad day from becoming a bad month. The system doesn't flip from full-on to kill switch — it steps down (50% size → halt entries → full stop), protecting capital while staying operational through normal volatility. Sector ETF hedges add a second layer of protection in bearish regimes.</li>
              <li><strong>Dividend awareness protects yield:</strong> Income-generating positions produce dividend income alongside call premium. The dividend guard prevents accidentally giving away that yield. Delta drift alerts fire when a call drifts above 0.50 delta — giving time to roll before assignment occurs.</li>
              <li><strong>Partial profits improve risk-adjusted returns:</strong> At 2× ATR, half a position is closed to lock in gains and free capital for redeployment. The remaining half runs with a tightened trailing stop. This reduces variance without abandoning winning positions — a key difference from binary hold-to-target strategies.</li>
              <li><strong>The system learns from its own trades:</strong> The analytics dashboard tracks win rates, R-multiples, hold times, and exit reasons by strategy and regime. The Friday backtester tests 80 parameter combinations weekly. Both feed into the optimization cycle — the investor sees data-backed evidence before any parameter changes are applied.</li>
              <li><strong>Missed recoveries are systematically monitored:</strong> Stopped-out positions continue to be watched for 30 days. When price, SMA, and RSI conditions all confirm a genuine recovery, an alert fires. Re-entries are never automatic — but they are never missed either.</li>
              <li><strong>Fully automated, zero discretion:</strong> Every signal, entry, exit, roll, and reopen is formula-driven. No emotional override is possible at the moment of trade — the most common source of retail trading losses is eliminated by design.</li>
            </ol>
          </div>

          {/* Disclaimer */}
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-8">
            <h2 className="text-2xl font-serif font-bold text-amber-900 mb-4">Disclaimer</h2>
            <p className="text-amber-800 leading-relaxed">
              Trading equities, short selling, and options involves substantial risk of loss. Leverage —
              including Portfolio Margin — amplifies both gains and losses. Past performance, including
              backtest results and live trading history, does not guarantee future results. Options can
              expire worthless or result in assignment; losses can exceed the premium collected.
              The system enforces risk limits and consistent rules, but market conditions, execution
              quality, model drift, and unforeseen events can lead to drawdowns or losses.
              This material is for informational purposes only and does not constitute investment advice.
              Do not risk capital you cannot afford to lose.
            </p>
          </div>
        </div>

        <footer className="mt-16 pt-8 border-t border-stone-200 text-center text-sm text-stone-400">
          <p>Winzinvest · Live Account</p>
        </footer>
      </div>
    </div>
  );
}
