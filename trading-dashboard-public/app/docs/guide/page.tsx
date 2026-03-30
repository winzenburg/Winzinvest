/**
 * Operational Guide — authenticated users only.
 *
 * Purpose:  Post-purchase documentation. How to use the system, read the dashboard,
 *           respond to alerts, interpret regime changes, use the journal, etc.
 *           This is NOT marketing. It's a user manual for paying customers.
 *
 * Design:   Clean, scannable, practical. Sticky sidebar for quick navigation.
 *           Single page so Cmd+F works across all sections.
 */

import DashboardNav from '@/app/components/DashboardNav';
import Link from 'next/link';

const SIDEBAR_SECTIONS = [
  { id: 'overview', label: 'Overview' },
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'regime', label: 'Regime Cards' },
  { id: 'positions', label: 'Position Management' },
  { id: 'alerts', label: 'Alerts & Responses' },
  { id: 'journal', label: 'Journal' },
  { id: 'kill-switch', label: 'Kill Switch' },
  { id: 'troubleshooting', label: 'Troubleshooting' },
] as const;

export default function GuideDocPage() {
  return (
    <>
      <DashboardNav />
      <div className="min-h-screen bg-stone-50">
        <div className="max-w-7xl mx-auto px-8 py-16">
          <div className="grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-12">
            
            {/* Sticky sidebar navigation */}
            <aside className="hidden lg:block">
              <nav className="sticky top-24 space-y-1" aria-label="Guide sections">
                <div className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-3">
                  Guide Sections
                </div>
                {SIDEBAR_SECTIONS.map(({ id, label }) => (
                  <a
                    key={id}
                    href={`#${id}`}
                    className="block px-3 py-1.5 text-sm text-stone-600 hover:text-slate-900 hover:bg-white rounded-lg transition-colors"
                  >
                    {label}
                  </a>
                ))}
              </nav>
            </aside>

            {/* Main content */}
            <main className="max-w-3xl">
              
              {/* Header */}
              <div className="mb-12">
                <h1 className="font-serif text-4xl font-bold text-slate-900 mb-4">
                  How to Use This System
                </h1>
                <p className="text-lg text-stone-600 leading-relaxed">
                  Operational guide for Winzinvest. How to read the dashboard, interpret regime changes, 
                  respond to alerts, and use the journal. This isn't marketing. It's the manual for the 
                  system you're running.
                </p>
              </div>

              {/* Overview */}
              <section id="overview" className="mb-16">
                <h2 className="font-serif text-2xl font-bold text-slate-900 mb-6">Overview</h2>
                <div className="prose prose-stone max-w-none">
                  <p className="text-stone-600 leading-relaxed mb-4">
                    Winzinvest is execution software, not a robo-advisor. It screens for setups, runs 
                    risk checks, places orders, and manages positions according to the rules configured 
                    in your account. You can watch it work, override it when necessary, or let it run 
                    fully automated.
                  </p>
                  <p className="text-stone-600 leading-relaxed mb-4">
                    The dashboard shows you everything the system is doing: current positions, regime 
                    status, upcoming actions, recent trades, and the full audit trail. Every decision 
                    the system makes is logged and visible.
                  </p>
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-5 mt-6">
                    <div className="font-semibold text-sm text-amber-900 mb-2">
                      Kill Switch
                    </div>
                    <p className="text-sm text-amber-800 leading-relaxed">
                      The red kill switch button (top right) immediately halts all automated trading. 
                      Open positions remain but no new orders will be placed. Use it when you need 
                      to pause the system for any reason. Re-enable from the same button.
                    </p>
                  </div>
                </div>
              </section>

              {/* Dashboard */}
              <section id="dashboard" className="mb-16">
                <h2 className="font-serif text-2xl font-bold text-slate-900 mb-6">Reading the Dashboard</h2>
                
                <div className="space-y-8">
                  <div>
                    <h3 className="font-semibold text-lg text-slate-900 mb-3">Portfolio Status Card</h3>
                    <p className="text-stone-600 leading-relaxed mb-4">
                      Top left. Shows current equity, today's P&L, total return since system start, 
                      and current drawdown from peak. The return percentage includes both equity moves 
                      and options premium.
                    </p>
                    <div className="bg-white border border-stone-200 rounded-lg p-4">
                      <div className="text-xs text-stone-600 mb-2">Example:</div>
                      <div className="font-mono text-sm text-slate-800">
                        <div>Equity: $175,432</div>
                        <div>Today: +$1,243 (+0.71%)</div>
                        <div>Total Return: +8.37%</div>
                        <div className="text-red-600">Drawdown: -2.14%</div>
                      </div>
                    </div>
                  </div>

                  <div>
                    <h3 className="font-semibold text-lg text-slate-900 mb-3">Open Positions</h3>
                    <p className="text-stone-600 leading-relaxed mb-4">
                      Every stock and option position with current P&L, entry date, and stop price. 
                      Green rows are winning, red are losing. The stop column shows where the position 
                      will be closed automatically if price hits that level.
                    </p>
                    <p className="text-stone-600 leading-relaxed">
                      <strong className="text-slate-900">R-multiple</strong> shows profit/loss in units 
                      of initial risk. +1.0R means the position made exactly what was risked. +2.5R means 
                      it made 2.5× the initial risk. This normalizes performance across different position sizes.
                    </p>
                  </div>

                  <div>
                    <h3 className="font-semibold text-lg text-slate-900 mb-3">Audit Trail</h3>
                    <p className="text-stone-600 leading-relaxed">
                      Every action the system takes is logged here: orders placed, stops adjusted, regime 
                      changes, parameter updates, and rejected setups. Each entry shows the timestamp, 
                      action type, and reason. Use this to understand what happened during the day.
                    </p>
                  </div>
                </div>
              </section>

              {/* Regime */}
              <section id="regime" className="mb-16">
                <h2 className="font-serif text-2xl font-bold text-slate-900 mb-6">Understanding Regime Cards</h2>
                
                <div className="space-y-8">
                  <p className="text-stone-600 leading-relaxed">
                    The system uses two regime layers to decide which strategies are active. Layer 1 
                    controls execution (momentum vs mean reversion vs shorts). Layer 2 controls options 
                    and hedging.
                  </p>

                  <div>
                    <h3 className="font-semibold text-lg text-slate-900 mb-3">Layer 1: Execution Regime</h3>
                    <div className="space-y-3">
                      <div className="bg-white border border-stone-200 rounded-lg p-4">
                        <div className="font-mono text-sm font-bold text-green-600 mb-2">STRONG_UPTREND</div>
                        <p className="text-sm text-stone-600">
                          Momentum longs active. Mean reversion active. Shorts off. Full position sizing. 
                          This is the favorable regime for growth strategies.
                        </p>
                      </div>
                      <div className="bg-white border border-stone-200 rounded-lg p-4">
                        <div className="font-mono text-sm font-bold text-yellow-600 mb-2">CHOPPY</div>
                        <p className="text-sm text-stone-600">
                          Mean reversion active. Momentum reduced. Position sizes smaller. The system 
                          trades more cautiously.
                        </p>
                      </div>
                      <div className="bg-white border border-stone-200 rounded-lg p-4">
                        <div className="font-mono text-sm font-bold text-orange-600 mb-2">MIXED</div>
                        <p className="text-sm text-stone-600">
                          Momentum longs active but cautious. Mean reversion active. Shorts may activate 
                          depending on stress signals.
                        </p>
                      </div>
                      <div className="bg-white border border-stone-200 rounded-lg p-4">
                        <div className="font-mono text-sm font-bold text-red-600 mb-2">STRONG_DOWNTREND</div>
                        <p className="text-sm text-stone-600">
                          Shorts active. Longs off or severely restricted. The system is defensive.
                        </p>
                      </div>
                      <div className="bg-white border border-stone-200 rounded-lg p-4">
                        <div className="font-mono text-sm font-bold text-slate-600 mb-2">UNFAVORABLE</div>
                        <p className="text-sm text-stone-600">
                          All strategies restricted or off. The system is mostly in cash waiting for 
                          conditions to improve.
                        </p>
                      </div>
                    </div>
                  </div>

                  <div>
                    <h3 className="font-semibold text-lg text-slate-900 mb-3">Layer 2: Macro Regime</h3>
                    <p className="text-stone-600 leading-relaxed mb-3">
                      Controls options strategies and hedging. Based on credit spreads, VIX term structure, 
                      and breadth indicators.
                    </p>
                    <div className="space-y-3">
                      <div className="bg-white border border-stone-200 rounded-lg p-4">
                        <div className="font-mono text-sm font-bold text-green-600 mb-2">RISK_ON</div>
                        <p className="text-sm text-stone-600">Covered calls active. CSPs active. Iron condors active if vol is high enough.</p>
                      </div>
                      <div className="bg-white border border-stone-200 rounded-lg p-4">
                        <div className="font-mono text-sm font-bold text-yellow-600 mb-2">NEUTRAL</div>
                        <p className="text-sm text-stone-600">All options strategies active but with tighter filters.</p>
                      </div>
                      <div className="bg-white border border-stone-200 rounded-lg p-4">
                        <div className="font-mono text-sm font-bold text-orange-600 mb-2">TIGHTENING</div>
                        <p className="text-sm text-stone-600">CSPs off. Covered calls only. Protective puts considered.</p>
                      </div>
                      <div className="bg-white border border-stone-200 rounded-lg p-4">
                        <div className="font-mono text-sm font-bold text-red-600 mb-2">DEFENSIVE</div>
                        <p className="text-sm text-stone-600">All new premium selling off. Protective puts active. Hedges activated.</p>
                      </div>
                    </div>
                  </div>

                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-5 mt-6">
                    <div className="font-semibold text-sm text-blue-900 mb-2">
                      When regime changes
                    </div>
                    <p className="text-sm text-blue-800 leading-relaxed">
                      You'll get a Telegram alert. The dashboard regime card updates immediately. Existing 
                      positions stay open but new entries will follow the new regime rules. You don't need 
                      to do anything unless you want to manually close positions early.
                    </p>
                  </div>
                </div>
              </section>

              {/* Position Management */}
              <section id="positions" className="mb-16">
                <h2 className="font-serif text-2xl font-bold text-slate-900 mb-6">Position Management</h2>
                
                <div className="space-y-8">
                  <div>
                    <h3 className="font-semibold text-lg text-slate-900 mb-3">How Stops Work</h3>
                    <p className="text-stone-600 leading-relaxed mb-4">
                      Every stock position gets a stop order placed at your broker immediately after entry. 
                      The stop is calculated as a multiple of ATR (Average True Range) and updates every 
                      morning. Stops only move up (for longs) or down (for shorts), never against you.
                    </p>
                    <div className="bg-white border border-stone-200 rounded-lg p-4">
                      <div className="text-xs text-stone-600 mb-2">Example progression (long position):</div>
                      <div className="font-mono text-sm text-slate-800 space-y-1">
                        <div>Day 1: Entry $100, Stop $95 (risk $5)</div>
                        <div>Day 3: Price $105, Stop $98 (locked in +$3)</div>
                        <div>Day 7: Price $112, Stop $106 (locked in +$6)</div>
                      </div>
                    </div>
                    <p className="text-stone-600 leading-relaxed mt-4">
                      If the system is offline when the stop triggers, the order still executes. Stops 
                      are native broker orders, not client-side logic.
                    </p>
                  </div>

                  <div>
                    <h3 className="font-semibold text-lg text-slate-900 mb-3">Trailing Stops</h3>
                    <p className="text-stone-600 leading-relaxed">
                      Once a position hits a profit threshold (typically +1.5R or +2.0R depending on regime), 
                      the hard stop converts to a trailing stop. The trail distance is set as a multiple 
                      of ATR. This lets winners run while protecting gains.
                    </p>
                  </div>

                  <div>
                    <h3 className="font-semibold text-lg text-slate-900 mb-3">Time Stops</h3>
                    <p className="text-stone-600 leading-relaxed mb-4">
                      Positions held longer than the configured time limit (typically 20–45 days depending 
                      on regime) are closed automatically. This prevents capital from sitting in stale ideas. 
                      In strong uptrends, the window extends to let winners run longer.
                    </p>
                  </div>

                  <div>
                    <h3 className="font-semibold text-lg text-slate-900 mb-3">Early Exits (Bobblehead)</h3>
                    <p className="text-stone-600 leading-relaxed mb-4">
                      If a long position is still below entry after 2 days AND has drifted more than 0.35× ATR 
                      from entry, the system closes it early. This is the "bobblehead exit" and it redeploys 
                      capital from failed setups before they turn into larger losses.
                    </p>
                  </div>

                  <div>
                    <h3 className="font-semibold text-lg text-slate-900 mb-3">Winner Pyramid</h3>
                    <p className="text-stone-600 leading-relaxed">
                      If a long position is up 1R or more within 2 days, the system adds 50% more shares 
                      (Layer 1) and moves the stop to breakeven on the full position. If open profit later 
                      reaches 2× ATR, a second add (Layer 2) is made using 30% of open profit as collateral. 
                      This builds into confirmed winners without risking original capital.
                    </p>
                  </div>
                </div>
              </section>

              {/* Alerts */}
              <section id="alerts" className="mb-16">
                <h2 className="font-serif text-2xl font-bold text-slate-900 mb-6">Alerts & Responses</h2>
                
                <div className="space-y-8">
                  <p className="text-stone-600 leading-relaxed">
                    Telegram alerts notify you of important events. Most require no action. Some need 
                    a quick decision.
                  </p>

                  <div className="space-y-4">
                    {[
                      {
                        alert: 'Regime changed to CHOPPY',
                        meaning: 'Market conditions shifted. System is now trading more defensively.',
                        action: 'No action required. Existing positions stay open, new entries will be filtered more strictly.',
                      },
                      {
                        alert: 'Daily loss limit: -1.0%',
                        meaning: 'Drawdown tier 1 triggered. Position sizes now cut to 50%.',
                        action: 'No action required. System will continue trading but with smaller sizes until tomorrow.',
                      },
                      {
                        alert: 'AAPL short call approaching ITM',
                        meaning: 'One of your covered calls is getting close to the strike price.',
                        action: 'Check the dashboard options section. System will auto-roll at DTE 7 or when ITM, but you can manually close or roll earlier if you prefer.',
                      },
                      {
                        alert: `Gap risk alert: TSLA up 12% pre-market`,
                        meaning: `You hold a position that gapped significantly overnight.`,
                        action: `Review the position. System will place a stop if one doesn't exist, but you may want to take profit manually if the gap is large.`,
                      },
                      {
                        alert: 'Assignment risk: XYZ $50 call DEEP_ITM',
                        meaning: 'Covered call is deep in the money. Assignment is likely before expiry.',
                        action: 'Decide: let it assign (you keep premium + sell stock at strike), or roll the call to a higher strike/later expiry to keep the position.',
                      },
                      {
                        alert: `Orphaned position detected: ABC`,
                        meaning: `You have a stock position that isn't in the trade log database.`,
                        action: `Likely a manual trade you placed via TWS. Add it to the log using the journal or the system will keep alerting.`,
                      },
                    ].map(({ alert, meaning, action }, i) => (
                      <div key={i} className="bg-white border border-stone-200 rounded-lg p-5">
                        <div className="font-mono text-xs font-bold text-slate-800 mb-2">{alert}</div>
                        <div className="text-sm text-stone-600 mb-2">
                          <strong className="text-slate-900">What it means:</strong> {meaning}
                        </div>
                        <div className="text-sm text-stone-600">
                          <strong className="text-slate-900">What to do:</strong> {action}
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="bg-red-50 border border-red-200 rounded-lg p-5">
                    <div className="font-semibold text-sm text-red-900 mb-2">
                      Daily loss limit: -3.0% KILL SWITCH ACTIVATED
                    </div>
                    <p className="text-sm text-red-800 leading-relaxed">
                      The system has stopped trading for the day. All open positions remain but no new 
                      orders will be placed. This resets at market open tomorrow. You can manually override 
                      the kill switch if you have a good reason, but the default is to stop trading when 
                      down 3% in a day.
                    </p>
                  </div>
                </div>
              </section>

              {/* Journal */}
              <section id="journal" className="mb-16">
                <h2 className="font-serif text-2xl font-bold text-slate-900 mb-6">Using the Journal</h2>
                
                <div className="space-y-6">
                  <p className="text-stone-600 leading-relaxed">
                    The journal is where you add notes, mark overrides, and log manual trades. Every 
                    entry is timestamped and searchable. Use it to track why you intervened, what you 
                    learned from losing trades, and patterns you notice over time.
                  </p>

                  <div>
                    <h3 className="font-semibold text-base text-slate-900 mb-3">What to log</h3>
                    <ul className="space-y-2 text-sm text-stone-600">
                      <li className="flex items-start gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-primary-600 shrink-0 mt-1.5" />
                        <span>Manual trades (placed via TWS or mobile app, not through the system)</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-primary-600 shrink-0 mt-1.5" />
                        <span>Override decisions (you closed a position early or skipped a signal)</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-primary-600 shrink-0 mt-1.5" />
                        <span>Post-mortem notes on losing trades</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-primary-600 shrink-0 mt-1.5" />
                        <span>Parameter changes you made (stop distance, conviction floors, etc.)</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-primary-600 shrink-0 mt-1.5" />
                        <span>Regime observations (why you think the system called it correctly or incorrectly)</span>
                      </li>
                    </ul>
                  </div>

                  <div className="bg-white border border-stone-200 rounded-lg p-5">
                    <div className="text-xs text-stone-600 mb-3">Example journal entry:</div>
                    <div className="font-mono text-xs text-slate-800 bg-stone-50 p-3 rounded">
                      2026-03-29 14:22 MT<br />
                      Closed NVDA long manually at +$2,340 (+1.8R).<br />
                      <br />
                      System had trail stop at $118. Price hit $124 intraday, then started pulling back 
                      hard on volume. Closed at $122.50 rather than wait for trail to hit.<br />
                      <br />
                      Override reason: Intraday reversal on heavy volume felt like distribution. Didn't 
                      want to give back another $4/share waiting for the trail.
                    </div>
                  </div>

                  <div>
                    <h3 className="font-semibold text-base text-slate-900 mb-3">Manual trades</h3>
                    <p className="text-stone-600 leading-relaxed">
                      If you place a trade directly via TWS or the broker's mobile app (not through 
                      Winzinvest), log it in the journal immediately. The system needs to know about it 
                      for sector concentration, position limits, and stop management. Otherwise it will 
                      flag the position as "orphaned" and keep alerting.
                    </p>
                  </div>
                </div>
              </section>

              {/* Kill Switch */}
              <section id="kill-switch" className="mb-16">
                <h2 className="font-serif text-2xl font-bold text-slate-900 mb-6">Kill Switch Usage</h2>
                
                <div className="space-y-6">
                  <p className="text-stone-600 leading-relaxed">
                    The kill switch (red button, top right of dashboard) immediately stops all automated 
                    trading. Open positions remain but no new orders will be placed.
                  </p>

                  <div>
                    <h3 className="font-semibold text-base text-slate-900 mb-3">When to use it</h3>
                    <ul className="space-y-2 text-sm text-stone-600">
                      <li className="flex items-start gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-red-600 shrink-0 mt-1.5" />
                        <span>You're going on vacation and want to pause new trades</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-red-600 shrink-0 mt-1.5" />
                        <span>Market conditions feel abnormal (flash crash, news event, etc.)</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-red-600 shrink-0 mt-1.5" />
                        <span>You want to review something before allowing more trades</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-red-600 shrink-0 mt-1.5" />
                        <span>You're making manual changes to positions and don't want the system interfering</span>
                      </li>
                    </ul>
                  </div>

                  <div>
                    <h3 className="font-semibold text-base text-slate-900 mb-3">What it does</h3>
                    <p className="text-stone-600 leading-relaxed mb-3">
                      When activated:
                    </p>
                    <ul className="space-y-2 text-sm text-stone-600">
                      <li className="flex items-start gap-2">
                        <span className="text-red-600 shrink-0">✗</span>
                        <span>No new entries (momentum, mean reversion, shorts, options)</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-red-600 shrink-0">✗</span>
                        <span>No options rolling or profit-takes</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-red-600 shrink-0">✗</span>
                        <span>No pyramid adds or rebalancing</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-green-600 shrink-0">✓</span>
                        <span>Existing stop orders stay active (your downside protection remains)</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-green-600 shrink-0">✓</span>
                        <span>Trailing stops continue to adjust upward as positions gain</span>
                      </li>
                    </ul>
                  </div>

                  <div>
                    <h3 className="font-semibold text-base text-slate-900 mb-3">Automatic triggers</h3>
                    <p className="text-stone-600 leading-relaxed">
                      The kill switch activates automatically when daily loss hits -3.0%. It resets at 
                      market open the next day. You can manually re-enable it if you want to resume 
                      trading before then, but the default behavior is to stay off until tomorrow.
                    </p>
                  </div>
                </div>
              </section>

              {/* Troubleshooting */}
              <section id="troubleshooting" className="mb-16">
                <h2 className="font-serif text-2xl font-bold text-slate-900 mb-6">Common Issues</h2>
                
                <div className="space-y-6">
                  {[
                    {
                      issue: `Dashboard shows "Connection Lost"`,
                      cause: `IB Gateway is offline or the API connection dropped.`,
                      fix: `Check that IB Gateway or TWS is running on your machine. The system will auto-reconnect within 60 seconds if Gateway comes back online. If it doesn't reconnect, restart Gateway and refresh the dashboard.`,
                    },
                    {
                      issue: `Position shows no stop price`,
                      cause: `Stop order was rejected or never placed (rare).`,
                      fix: `The system will attempt to place a stop on the next update cycle (every morning). If it persists, check the audit trail for error messages or contact support.`,
                    },
                    {
                      issue: `"Orphaned position" alert for a symbol you own`,
                      cause: `You placed a manual trade via TWS that isn't in the system's trade log.`,
                      fix: `Go to the journal and add an entry for that trade, or the alert will keep firing every day.`,
                    },
                    {
                      issue: `System isn't placing any new trades`,
                      cause: `Either (1) kill switch is active, (2) drawdown tier reduced sizing to zero, (3) regime is UNFAVORABLE, or (4) no setups passed the conviction floor.`,
                      fix: `Check the regime card and drawdown status. If kill switch is red, that's the reason. If regime is UNFAVORABLE, wait for conditions to improve. Otherwise, it may just be a slow day with no high-quality setups.`,
                    },
                    {
                      issue: `Covered call alert: "No shares to cover"`,
                      cause: `System tried to write a covered call but you have fewer than 100 shares of that stock.`,
                      action: `Either buy more shares to reach 100 (then the system will write the call automatically) or ignore (can't write calls on <100 shares).`,
                    },
                  ].map(({ issue, cause, fix, action }, i) => (
                    <div key={i} className="bg-white border border-stone-200 rounded-lg p-5">
                      <div className="font-semibold text-sm text-slate-900 mb-2">{issue}</div>
                      <div className="text-sm text-stone-600 mb-2">
                        <strong className="text-slate-900">Cause:</strong> {cause}
                      </div>
                      <div className="text-sm text-stone-600">
                        <strong className="text-slate-900">{action ? 'Action' : 'Fix'}:</strong> {action || fix}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="bg-stone-100 border border-stone-300 rounded-lg p-5 mt-8">
                  <div className="font-semibold text-sm text-slate-900 mb-2">
                    Still stuck?
                  </div>
                  <p className="text-sm text-stone-600">
                    Check the audit trail first. Most issues show up there with error messages. 
                    If you can't resolve it, email support with the timestamp and symbol from 
                    the audit log.
                  </p>
                </div>
              </section>

              {/* Footer CTA */}
              <div className="border-t border-stone-200 pt-12 mt-16">
                <div className="text-center">
                  <p className="text-sm text-stone-600 mb-6">
                    For detailed methodology and strategy descriptions, see the full documentation.
                  </p>
                  <div className="flex items-center justify-center gap-4">
                    <Link
                      href="/methodology"
                      className="px-6 py-2.5 rounded-lg border border-stone-300 hover:bg-white hover:border-stone-400 text-stone-700 font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-primary-600 focus:ring-offset-2"
                    >
                      Full Methodology
                    </Link>
                    <Link
                      href="/dashboard"
                      className="px-6 py-2.5 rounded-lg bg-primary-600 hover:bg-primary-700 text-white font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-primary-600 focus:ring-offset-2"
                    >
                      Back to Dashboard
                    </Link>
                  </div>
                </div>
              </div>

            </main>
          </div>
        </div>
      </div>
    </>
  );
}
