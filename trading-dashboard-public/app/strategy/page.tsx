'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

const BACKTEST_STATS = {
  twoYear: {
    annualizedReturn: '42.4%',
    sharpe: '4.03',
    maxDrawdown: '12.6%',
    totalPnl: '$54,327',
    endingEquity: '$152,326',
    trades: 588,
    winRate: '47.1%',
  },
  threeYear: {
    annualizedReturn: '37.8%',
    sharpe: '4.01',
    maxDrawdown: '7.1%',
    totalPnl: '$103,985',
    endingEquity: '$201,501',
    trades: 1146,
    winRate: '48.2%',
  },
};

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

export default function StrategyPage() {
  const [backtest, setBacktest] = useState<BacktestSummary | null>(null);

  useEffect(() => {
    fetch('/api/backtest-results')
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { if (d) setBacktest(d); })
      .catch(() => {});
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
              The system trades a live IBKR account with your NLV under Portfolio Margin (up to 6–7× leverage).
              Premium income run rate: <strong>~$8,600/month</strong> from covered calls and CSPs alone — on track for <strong>$100K+ annually from options</strong>.
              Every entry, exit, roll, and reopen is fully automated with no discretionary override.
            </p>
          </div>

          {/* Backtest Performance Banner */}
          <div className="bg-slate-900 rounded-xl p-8 mb-8 text-white">
            <h2 className="text-xl font-serif font-bold text-white mb-1">Backtest Performance</h2>
            <p className="text-slate-400 text-sm mb-6">Starting equity $100,000 · 200-symbol universe · Hybrid screener + options income</p>
            <div className="grid grid-cols-2 gap-6">
              <div>
                <p className="text-slate-400 text-xs uppercase tracking-widest mb-3">2-Year</p>
                <div className="space-y-2">
                  {[
                    ['Annualized return', BACKTEST_STATS.twoYear.annualizedReturn, 'text-green-400 font-bold'],
                    ['Sharpe ratio', BACKTEST_STATS.twoYear.sharpe, 'text-white font-semibold'],
                    ['Max drawdown', BACKTEST_STATS.twoYear.maxDrawdown, 'text-amber-400 font-semibold'],
                    ['Ending equity', BACKTEST_STATS.twoYear.endingEquity, 'text-white font-semibold'],
                    ['Trades · Win rate', `${BACKTEST_STATS.twoYear.trades} · ${BACKTEST_STATS.twoYear.winRate}`, 'text-white font-semibold'],
                  ].map(([label, value, cls]) => (
                    <div key={label} className="flex justify-between">
                      <span className="text-slate-300 text-sm">{label}</span>
                      <span className={cls as string}>{value}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-slate-400 text-xs uppercase tracking-widest mb-3">3-Year (robustness)</p>
                <div className="space-y-2">
                  {[
                    ['Annualized return', BACKTEST_STATS.threeYear.annualizedReturn, 'text-green-400 font-bold'],
                    ['Sharpe ratio', BACKTEST_STATS.threeYear.sharpe, 'text-white font-semibold'],
                    ['Max drawdown', BACKTEST_STATS.threeYear.maxDrawdown, 'text-amber-400 font-semibold'],
                    ['Ending equity', BACKTEST_STATS.threeYear.endingEquity, 'text-white font-semibold'],
                    ['Trades · Win rate', `${BACKTEST_STATS.threeYear.trades} · ${BACKTEST_STATS.threeYear.winRate}`, 'text-white font-semibold'],
                  ].map(([label, value, cls]) => (
                    <div key={label} className="flex justify-between">
                      <span className="text-slate-300 text-sm">{label}</span>
                      <span className={cls as string}>{value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <p className="text-slate-500 text-xs mt-6">Past performance does not guarantee future results. Backtest uses historical data with no look-ahead bias.</p>
          </div>

          {/* Live Strategy Attribution */}
          <div className="bg-white border border-stone-200 rounded-xl p-8 mb-8">
            <h2 className="text-2xl font-serif font-bold text-slate-900 mb-2">Live Strategy P&amp;L Attribution</h2>
            <p className="text-stone-500 text-sm mb-6">
              At scale the options income overlay dominates — covered calls + CSPs are the primary engine
            </p>
            <div className="grid grid-cols-2 gap-4">
              {[
                { dot: 'bg-green-600', label: 'Covered Calls', value: '~$7,200/mo', note: '20–25 contracts · ~35 DTE · delta 0.20 · PROFIT_ROLL at 80%' },
                { dot: 'bg-purple-600', label: 'Cash-Secured Puts', value: '~$1,400/mo', note: 'Long watchlist only · regime-gated · delta 0.25' },
                { dot: 'bg-blue-600', label: 'Iron Condors', value: 'Opportunistic', note: 'SPY/QQQ · CHOPPY/MIXED only · max 4 open' },
                { dot: 'bg-green-500', label: 'Equity Momentum', value: 'Compounding', note: 'NX + AMS hybrid · longs primary · shorts as hedge' },
                { dot: 'bg-amber-600', label: 'Protective Puts', value: 'Insurance', note: 'SPY puts · MIXED/UNFAVORABLE · tail-risk only' },
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
                  at a fresh 35 DTE strike — compounding income within the same cycle.
                </p>
                <div className="bg-stone-50 rounded-lg p-3 text-sm space-y-1">
                  <p><strong>Dividend guard:</strong> Skips the call if ex-div date falls inside the expiry window and dividend &gt; 70% of premium, or ex-div is within 5 days of expiry (early assignment risk)</p>
                  <p><strong>Assignment monitor:</strong> Every 30 min — Telegram alert if option drifts within 2% of ITM (APPROACHING), crosses ITM, or goes deep ITM (&gt;3%)</p>
                  <p><strong>Auto-roll:</strong> Rolled at DTE ≤7 or if ITM by ≥2% — new position opened at 35 DTE, delta-targeted strike</p>
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

            {backtest ? (
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
                          <td className="py-2 px-2 font-semibold text-green-700">{r.annualized_return_pct.toFixed(1)}%</td>
                          <td className="py-2 px-2 font-semibold text-slate-800">{r.sharpe.toFixed(2)}</td>
                          <td className="py-2 px-2 text-stone-600">{r.win_rate_pct.toFixed(0)}%</td>
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
                { regime: 'STRONG_DOWNTREND', color: 'bg-red-100 border-red-300 text-red-800',    action: 'Longs: 50% capacity · Shorts: none · No new CSPs (assignment risk) · Protective puts active.' },
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
              A scored composite of macro stress indicators (VIX structure, HY credit spreads, real yields, NFCI, ISM).
              Does not gate which strategies run — instead, it tightens or loosens the <em>position sizing parameters</em> used by the AMS executor.
              This is the regime band shown on the Overview dashboard card.
            </p>
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
                  body: 'Screens 200+ symbols daily using composite score (momentum + Bollinger + RSI), relative strength vs SPY, structure quality, higher-timeframe bias, and AMS volume score. Combined score ≥0.50 required. Exits: take-profit 3.5× ATR, trailing stop 3.0× ATR (activates after 1R banked), hard stop 1.5× ATR, 20-day time stop.',
                },
                {
                  color: 'border-red-500',
                  title: '2. Momentum Shorts (Hedge Overlay)',
                  body: 'Small hedge overlay — capped at 8% of slots (CHOPPY) and 10% (MIXED). Entry requires composite <0.20 and structure <0.20. Blocked in STRONG_UPTREND, STRONG_DOWNTREND, and UNFAVORABLE. Not a primary income source.',
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

          {/* Risk Management */}
          <div className="bg-white border border-stone-200 rounded-xl p-8 mb-8">
            <h2 className="text-2xl font-serif font-bold text-slate-900 mb-4">Risk Management Stack</h2>
            <ul className="space-y-3 text-stone-600">
              {[
                { label: 'Drawdown circuit breaker', desc: 'Three graduated tiers: -3% daily → reduce position sizes 50%; -5% → halt all new entries; -8% → activate kill switch automatically. Resets each morning.' },
                { label: 'Kill switch', desc: 'One-click halt from the dashboard (mobile or desktop). Also auto-activates at the -8% drawdown tier. Blocks all executors until manually cleared.' },
                { label: 'Assignment risk alerts', desc: 'Every 30 min: Telegram alerts when short options drift within 2% of ITM (APPROACHING), cross ITM, go deep ITM (>3%), or have an upcoming ex-dividend date creating early assignment risk.' },
                { label: 'Execution gates', desc: 'Every order passes 7 gates: daily loss limit, portfolio heat, position size (6% NLV cap), sector concentration (30% max), market hours, symbol validation, and per-position concentration.' },
                { label: 'Dividend awareness', desc: 'Before writing any covered call, checks upcoming ex-dividend dates. Skips the call if the quarterly dividend exceeds 70% of call premium or ex-div is within 5 days of expiry.' },
                { label: 'Sector concentration', desc: 'Capped at 30% of equity per sector. Unmapped symbols trigger a dashboard warning and Telegram alert.' },
                { label: 'Correlation monitoring', desc: 'Live 60-day correlation matrix for top 15 holdings on the dashboard. High average correlation (>0.6) = concentrated risk — Portfolio Margin penalizes correlated books.' },
                { label: 'Earnings blackout', desc: 'No new options within 7 days of earnings announcement. Checked on every covered call and CSP candidate.' },
                { label: 'Tax-loss harvesting', desc: 'Weekly Friday scan for positions with unrealized losses >$200 / 5%+ held >31 days. Suggests wash-sale-compliant sector ETF replacements. Estimated $3–5K annual tax savings.' },
                { label: 'Portfolio Margin', desc: 'Account upgraded to Portfolio Margin — up to 6–7× leverage based on portfolio-wide risk vs fixed Reg T 2:1. Significantly expands capacity for covered calls and new positions.' },
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
                { label: 'Risk per trade', value: '1% of equity', note: 'ATR-normalized' },
                { label: 'Max position', value: '6% of NLV per name', note: 'Hard cap — position concentration gate' },
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
                ['07:00 MT', 'Pre-market', 'Screeners run: NX longs, dual-mode, mean reversion, pairs → TV watchlist exported'],
                ['07:30 MT', 'Market open', 'Execute longs, dual-mode, mean reversion from screener output'],
                ['07:45 MT', 'Regime check', 'Both regime layers run: SPY/VIX execution regime + macro band scored; result persisted to dashboard; Telegram alert on change'],
                ['08:00 MT', 'Options', 'Covered calls + CSPs scanned and executed; daily options email sent'],
                ['08:15 MT', 'Re-screen', 'Post-opening-noise screeners re-run for confirmed signals'],
                ['08:30 MT', 'Execute', 'Post-open execution on confirmed signals'],
                ['Every 30m', 'Options mgr', 'Profit-take/roll/stop-loss check; assignment risk alerts'],
                ['Every 30m', 'Cash monitor', 'Drawdown breaker evaluated; idle cash deployed'],
                ['11:30 MT', 'Afternoon', 'Afternoon screeners + pairs; options re-scan'],
                ['12:45 MT', 'Regime check', 'Second daily regime pass — both layers re-evaluated; Telegram alert on change'],
                ['13:00 MT (Fri)', 'Tax harvest', 'Weekly tax-loss harvest scan (Telegram report)'],
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
              <li><strong>Premium income compounds with scale:</strong> At scale, selling 20–25 covered call contracts per cycle generates $8–10K monthly — regardless of market direction. This income is additive to equity returns and runs on autopilot.</li>
              <li><strong>PROFIT_ROLL eliminates dead premium days:</strong> When a call reaches 80% decay, it is closed and immediately reopened at a fresh 35 DTE strike with a new premium. Each position effectively generates 1.2–1.5× the premium of a hold-to-expiry approach over a full year.</li>
              <li><strong>Graduated risk response:</strong> The drawdown circuit breaker prevents a bad day from becoming a bad month. The system doesn't flip from full-on to kill switch — it steps down (50% size → halt entries → full stop), protecting capital while staying operational through normal volatility.</li>
              <li><strong>Dividend awareness protects yield:</strong> Energy positions (MPC, COP, OXY, VLO) generate meaningful dividend income. The dividend guard prevents accidentally giving away that yield by writing a call whose premium is less than the upcoming dividend.</li>
              <li><strong>Two orthogonal income streams:</strong> Equity momentum returns come from price trends. Options premium comes from time decay and implied volatility. In sideways markets where equity momentum slows, options income accelerates — they are natural complements.</li>
              <li><strong>Self-optimizing:</strong> The Friday backtester tests 80 parameter combinations weekly against live portfolio holdings and updates the optimal OTM%, DTE, and profit-take threshold. The system gets better as it accumulates data.</li>
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
          <p>Mission Control Trading System · Live Account</p>
        </footer>
      </div>
    </div>
  );
}
