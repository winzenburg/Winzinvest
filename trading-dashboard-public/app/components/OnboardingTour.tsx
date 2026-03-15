'use client';

import { useState, useEffect, useCallback } from 'react';

interface TourStep {
  title: string;
  body: string;
  tab?: string;
  emoji: string;
}

const TOUR_STEPS: TourStep[] = [
  {
    emoji: '👋',
    title: 'Welcome to Mission Control',
    body: "This is your automated trading command center. Let's take a quick tour of what you're looking at.",
    tab: 'overview',
  },
  {
    emoji: '📊',
    title: 'Overview Tab — Your Daily Scorecard',
    body: "The Overview shows your five most important numbers: Net Liquidation (total account value), Daily P&L (today's gain/loss), 30-day P&L, Sharpe Ratio (risk-adjusted performance), and open position count. The equity curve below tracks your account growth over time.",
    tab: 'overview',
  },
  {
    emoji: '🧠',
    title: 'Intelligence Tab — Your AI Advisor',
    body: "The Intelligence panel monitors your portfolio around the clock and surfaces actionable recommendations — things like 'Your tech exposure is too concentrated' or 'Consider rolling this option before expiry.' It's the system's automated risk brain.",
    tab: 'intelligence',
  },
  {
    emoji: '⚠️',
    title: 'Risk Tab — Know Your Exposure',
    body: "Risk shows how much of your capital is deployed (Long/Short/Net Exposure), sector concentration, Value at Risk (the worst expected loss on a bad day), margin utilization, and the correlation matrix between your holdings. High correlation means less diversification.",
    tab: 'risk',
  },
  {
    emoji: '📈',
    title: 'Performance Tab — Strategy Report Card',
    body: "Performance breaks down results by strategy (momentum, mean reversion, pairs, options) with win rates and P&L. Trade Analytics shows slippage, hold times, and best/worst trades. Backtest Comparison tells you how live results compare to the model's historical expectations.",
    tab: 'performance',
  },
  {
    emoji: '📋',
    title: 'Positions Tab — What You Own',
    body: "Positions lists every open trade with real-time marks from IBKR: quantity, average cost, current price, unrealized P&L, and sector. Use the Export CSV button to download for tax prep or record-keeping.",
    tab: 'positions',
  },
  {
    emoji: '🔴',
    title: 'Kill Switch — Emergency Brake',
    body: "The Kill Switch in the top right instantly halts all automated trading. No new orders will be placed. Existing positions are NOT closed — it's a pause, not an exit. A PIN is required to activate it. Use it if something looks wrong.",
  },
  {
    emoji: '📄 / 🔴',
    title: 'Paper vs Live Mode',
    body: "The mode toggle controls what data you see (Viewing) and what the system executes (Executing). Paper mode uses simulated trades with no real money. Live mode uses your actual IBKR account. The red banner at the top appears whenever live execution is active.",
  },
  {
    emoji: '✅',
    title: "You're Ready",
    body: "The system runs automatically during market hours. Check daily P&L in Overview, review Intelligence recommendations when alerts fire, and monitor Risk if you see concentration warnings. Questions? Check the Strategy page in the top nav.",
  },
];

const STORAGE_KEY = 'mc_tour_completed_v1';

export default function OnboardingTour({ onTabChange }: { onTabChange?: (tab: string) => void }) {
  const [step, setStep] = useState(0);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const done = localStorage.getItem(STORAGE_KEY);
    if (!done) setVisible(true);
  }, []);

  const current = TOUR_STEPS[step];
  const isLast = step === TOUR_STEPS.length - 1;

  const advance = useCallback(() => {
    if (isLast) {
      localStorage.setItem(STORAGE_KEY, '1');
      setVisible(false);
      return;
    }
    const next = step + 1;
    setStep(next);
    const nextTab = TOUR_STEPS[next].tab;
    if (nextTab && onTabChange) onTabChange(nextTab);
  }, [isLast, step, onTabChange]);

  const dismiss = useCallback(() => {
    localStorage.setItem(STORAGE_KEY, '1');
    setVisible(false);
  }, []);

  if (!visible) {
    return (
      <button
        onClick={() => { localStorage.removeItem(STORAGE_KEY); setStep(0); setVisible(true); }}
        className="fixed bottom-6 right-6 z-40 w-10 h-10 rounded-full bg-sky-600 hover:bg-sky-500 text-white shadow-lg flex items-center justify-center transition-all focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2"
        aria-label="Reopen onboarding tour"
        title="Tour"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </button>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center pb-8 px-4 pointer-events-none">
      <div
        className="pointer-events-auto w-full max-w-md bg-white rounded-2xl shadow-2xl border border-stone-200 p-6 animate-in slide-in-from-bottom-4 duration-300"
        role="dialog"
        aria-modal="true"
        aria-labelledby="tour-title"
      >
        {/* Progress dots */}
        <div className="flex gap-1.5 mb-4">
          {TOUR_STEPS.map((_, i) => (
            <div
              key={i}
              className={`h-1 flex-1 rounded-full transition-all ${i <= step ? 'bg-sky-500' : 'bg-stone-200'}`}
            />
          ))}
        </div>

        <div className="flex items-start gap-3 mb-4">
          <span className="text-2xl leading-none mt-0.5" aria-hidden="true">{current.emoji}</span>
          <div>
            <h3 id="tour-title" className="text-base font-bold text-slate-900 mb-1">{current.title}</h3>
            <p className="text-sm text-stone-600 leading-relaxed">{current.body}</p>
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 pt-3 border-t border-stone-100">
          <button
            onClick={dismiss}
            className="text-xs text-stone-400 hover:text-stone-600 transition-colors focus:outline-none focus:ring-1 focus:ring-stone-400 rounded px-1"
          >
            Skip tour
          </button>
          <div className="flex items-center gap-2">
            {step > 0 && (
              <button
                onClick={() => {
                  const prev = step - 1;
                  setStep(prev);
                  const prevTab = TOUR_STEPS[prev].tab;
                  if (prevTab && onTabChange) onTabChange(prevTab);
                }}
                className="px-4 py-1.5 text-sm font-medium rounded-lg border border-stone-200 text-stone-600 hover:bg-stone-50 transition-colors focus:outline-none focus:ring-2 focus:ring-sky-600"
              >
                Back
              </button>
            )}
            <button
              onClick={advance}
              className="px-4 py-1.5 text-sm font-semibold rounded-lg bg-sky-600 text-white hover:bg-sky-500 transition-colors focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-1"
            >
              {isLast ? "Got it, let's go!" : 'Next'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
