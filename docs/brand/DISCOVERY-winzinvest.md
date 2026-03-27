# Cultivate Discovery: Winzinvest (Revised)

## 1. Thesis
Winzinvest is an institutional-grade, fully automated trading system designed for serious retail swing traders who want to execute momentum and options income strategies without the emotional drag of discretionary trading. Unlike visual automation tools (Composer) or alert-only screeners (Trade Ideas), Winzinvest connects directly to an Interactive Brokers Portfolio Margin account and enforces a 7-layer risk gate system—including regime-aware sizing and a PIN-protected kill switch—making it the first retail platform that actively prevents users from trading when market conditions are unfavorable.

## 2. Personas / ICP Set
**Primary ICP: The "Burned but Capable" Swing Trader**
- **Profile:** 35-55 years old, high-earning professional (tech, finance, real estate), manages a $50k-$250k IBKR account.
- **Context:** They understand market mechanics, options Greeks, and momentum strategies. They have built their own TradingView indicators or complex spreadsheets.
- **The Problem:** They know *how* to trade, but they lack the discipline to execute mechanically. They give back months of gains during choppy regimes because they overtrade or ignore their own stops.

**Secondary ICP: The "Yield-Starved" Portfolio Manager**
- **Profile:** Manages a larger, static equity portfolio ($250k+).
- **Context:** Holds long-term positions in quality names but wants to generate additional yield without staring at options chains all day.
- **The Problem:** Selling covered calls and cash-secured puts manually is tedious and prone to assignment risk around earnings or ex-dividend dates.

## 3. Jobs To Be Done (JTBD)
1. **Protect me from myself:** "When the market gets choppy and I want to revenge-trade, stop me from entering new positions and reduce my sizing automatically."
2. **Execute my edge mechanically:** "When my screener finds a setup, execute the entry, set the ATR-based stop, and take profit without requiring me to click a button."
3. **Compound my yield passively:** "Automatically write covered calls against my long positions, roll them at 80% decay, and avoid earnings/dividend traps."

## 4. Pain Language Library
*(Sourced from Reddit r/algotrading, r/Daytrading, and the Winzinvest landing page)*
- "I really wish I had a bot that would call me up and say, 'you've given it all back. stop trading today.'"
- "I have a great strategy on TradingView, but I keep overriding it when I get scared."
- "Selling covered calls is great until you forget an earnings date and get your shares called away."
- "The leading cause of retail underperformance is discretionary override at the moment of trade." (Winzinvest Landing Page)

## 5. Existing Alternatives & Competitors
| Competitor | What They Do | Where They Fail the ICP |
|---|---|---|
| **Trade Ideas** | AI-powered stock screener and alerts ($89-$178/mo) | Alerts only. Requires the user to manually execute, leaving room for emotional override. |
| **Composer** | Visual, no-code algorithmic trading ($32/mo) | Lacks institutional risk layers (no kill switch, no complex regime gating, no portfolio margin awareness). |
| **QuantConnect** | Institutional algorithmic trading platform | Requires writing C# or Python code. Too high a barrier for the average swing trader. |
| **TastyTrade** | Brokerage with great options UI | Still a manual execution platform. Does not automate the rolling or screening process. |

## 6. Differentiation & Positioning
**The Whitespace Formula:** `Full auditability + institutional-grade risk layers + zero-code = Winzinvest`

1. **Regime-Aware Risk Gates (The Moat):** Winzinvest doesn't just automate trades; it automates *not* trading. The 7-layer execution gate (regime, sector cap, drawdown circuit breaker) is unique in the retail space.
2. **Dual-Strategy Parallelism:** It runs equity momentum and options premium income simultaneously, using the options to smooth out the equity equity curve.
3. **Institutional Safeguards:** Features like the PIN-protected kill switch, dividend guards, and earnings blackouts are typically reserved for prop desks, not retail SaaS.
4. **Zero-Code Execution:** Users get the power of a Python/ib_insync algorithmic system without having to write or host the code themselves.

## 7. Willingness-to-Pay Signals
- **Evidence:** The target ICP already pays $56/mo for TradingView Premium, $89-$178/mo for Trade Ideas, and often $100+/mo for Discord alert rooms.
- **Inference:** A system that actually executes the trades and protects capital via automated risk management commands a premium over alert-only tools.
- **Proposed Tiers:**
  - **Intelligence Tier ($49/mo):** Access to the dashboard, regime status, and screener signals (manual execution).
  - **Automation Tier ($149/mo):** Full IBKR integration, automated execution, and risk gates.

## 8. Trust, Compliance Posture, and Liability
*(Crucial for an automated execution product)*
- **The Risk:** FINRA actively warns against unregistered entities providing auto-trading services that send instructions to retail accounts.
- **The Posture:** Winzinvest must be positioned strictly as **"Self-Directed Execution Software."** The user connects their own IBKR API keys, sets their own risk parameters (via the dashboard), and the software merely executes those mechanical instructions. Winzinvest does not hold funds or provide discretionary advisory services.
- **Evidence in Repo:** The `audit_logger.py` and PIN-protected `kill-switch/route.ts` provide the necessary audit trails to prove the user is in control.

## 9. Acquisition Hooks & Channels
- **Hook 1: The Regime Status (Free Tool):** Publish the daily output of `regime_monitor.py` (e.g., "Market is in TIGHTENING regime. Winzinvest has reduced position sizing by 50% and halted new longs.") on FinTwit/X.
- **Hook 2: The "Stop Loss" for Your Emotions:** Content focusing on the psychological pain of discretionary trading and how the 3-tier circuit breaker solves it.
- **Channels:** X (FinTwit), Reddit (r/algotrading, r/options), and a waitlist landing page.

## 10. Moat Vectors
1. **High Switching Cost:** Once a user connects their IBKR account and the system is managing their options rolls and momentum stops, turning it off means going back to manual, emotional trading.
2. **Brand Trust:** Built through transparent, auditable execution logs and the visible presence of institutional risk controls (kill switch).
3. **Proprietary Logic:** The specific combination of the NX scoring engine, regime detection, and 7-layer risk gates.

## 11. Validation Plan Seeds
1. **The Exhaust Test:** Start tweeting the daily regime status and screener outputs (already generated by the system) to build an audience.
2. **The Landing Page Gate:** Drive traffic to the existing Next.js landing page (updated with the new positioning) to capture waitlist emails.
3. **The Pre-Sell Test:** Offer a "Founding Member" lifetime discount ($79/mo) to the waitlist to validate actual willingness to pay before building the multi-tenant cloud infrastructure.

## 12. Citations / Sources
- [1] Winzinvest Repository Deep Scan Report (March 2026)
- [2] `trading-dashboard-public/app/landing/page.tsx` (Product claims and competitor matrix)
- [3] `trading/scripts/execution_gates.py` & `drawdown_circuit_breaker.py` (Risk logic)
- [4] FINRA Investor Insights: Auto-Trading and Unregistered Entities (July 2025)
