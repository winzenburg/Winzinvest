# Cultivate Validation Plan: Winzinvest (Revised)

## 1. Validation Objectives
The goal of this validation phase is to test the three riskiest assumptions of the Winzinvest product strategy before investing in cloud infrastructure or multi-tenant architecture. The deep scan of the repository confirms that the core trading engine, risk gates, and Next.js dashboard are already built and functional locally. The validation must focus purely on market demand, regulatory posture, and willingness to pay.

## 2. Core Hypotheses to Test

### Hypothesis 1: The "Regime Awareness" Wedge (Demand)
**Belief:** Retail swing traders are more interested in a system that tells them *when not to trade* (regime awareness, circuit breakers) than just another stock screener.
**Test:** The Exhaust Test (FinTwit Audience Building).
**Metric:** Engagement rate and waitlist signups from content focused on risk management vs. content focused on stock picks.

### Hypothesis 2: The "Self-Directed Execution" Posture (Compliance)
**Belief:** Winzinvest can operate legally as a SaaS platform (not an RIA) if it strictly provides the software infrastructure for users to execute their own parameters via their own IBKR API keys.
**Test:** The Legal Gate.
**Metric:** A formal, written opinion from a securities compliance attorney confirming the "Self-Directed Execution Software" posture.

### Hypothesis 3: The $149/mo Willingness to Pay (Monetization)
**Belief:** The target ICP will pay $149/mo for the Automation Tier (full IBKR execution) and $49/mo for the Intelligence Tier (signals only).
**Test:** The Pre-Sell Gate.
**Metric:** 10 paid pre-orders at a discounted "Founding Member" rate of $79/mo.

## 3. Experiment Designs

### Experiment 1: The Exhaust Test (Weeks 1-2)
**What it is:** Leveraging the existing `regime_monitor.py` and `portfolio_intelligence.py` scripts to generate daily content without writing new code.
**Execution:**
1. Every morning, run the local Winzinvest system.
2. Take the output of the regime monitor (e.g., "Market is in TIGHTENING regime. Winzinvest has reduced position sizing by 50% and halted new longs.") and post it to X (FinTwit).
3. Include a link to the Winzinvest waitlist landing page in the bio and below high-performing posts.
**Pass/Fail Criteria:**
- **Pass:** >50 waitlist signups in 14 days.
- **Fail:** <20 waitlist signups in 14 days.

### Experiment 2: The Landing Page Gate (Weeks 2-3)
**What it is:** Updating the existing Next.js landing page (`app/landing/page.tsx`) to reflect the revised positioning and capture waitlist emails.
**Execution:**
1. Update the hero copy to focus on the "Stop Loss for Your Emotions" and the 7-layer risk gates.
2. Add a clear pricing section showing the $49/mo Intelligence Tier and $149/mo Automation Tier.
3. Add an email capture form for the waitlist.
**Pass/Fail Criteria:**
- **Pass:** >10% conversion rate from unique visitor to waitlist signup.
- **Fail:** <5% conversion rate.

### Experiment 3: The Pre-Sell Gate (Weeks 3-4)
**What it is:** Offering the waitlist a chance to pre-order the product at a discounted rate to fund the cloud migration.
**Execution:**
1. Send an email to the waitlist offering 50 "Founding Member" spots at $79/mo (lifetime discount).
2. Clearly state that the product is currently running locally and the pre-orders will fund the migration to a multi-tenant cloud architecture.
3. Use Stripe payment links to collect the pre-orders.
**Pass/Fail Criteria:**
- **Pass:** 10 paid pre-orders ($790 MRR committed).
- **Fail:** <5 paid pre-orders.

## 4. Decision Matrix

| Outcome | Action | Next Steps |
|---|---|---|
| **Green (All Tests Pass)** | Build the Cloud Product | Proceed to the Build Phase. Focus on migrating `ib_insync` to the IBKR Client Portal Web API and implementing multi-tenant NextAuth. |
| **Yellow (Demand Passes, Pre-Sell Fails)** | Pivot to Intelligence Tier | The market wants the data but doesn't trust the automated execution yet. Launch the $49/mo Intelligence Tier first using the existing `api/intelligence/route.ts`. |
| **Red (Demand Fails)** | Keep it Personal | The market does not resonate with the offering. Keep Winzinvest as a personal, local trading system and do not invest further in productization. |

## 5. Required Resources
- **Legal:** Budget for 2-3 hours of consultation with a securities compliance attorney.
- **Marketing:** X (Twitter) account, Kajabi or similar for email list management.
- **Development:** Minimal. Only updates to the existing Next.js landing page are required for validation.
