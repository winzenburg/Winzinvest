# Cursor Prompt: Winzinvest Landing Page & Waitlist Redesign

**Context for Cursor:**
You are an expert Next.js, Tailwind CSS, and UX engineer. We are redesigning the landing page for `Winzinvest`, an institutional-grade automated trading system for retail swing traders. The current landing page is located at `app/landing/page.tsx`. We need to rewrite the copy, restructure the sections based on Jobs-To-Be-Done (JTBD), and implement a waitlist signup flow to validate pricing tiers.

**Brand Voice & Tone Constraints:**
- **Archetype:** The Disciplined Operator / The Risk Manager.
- **Tone:** Calm, objective, institutional, restrained. No hype, no exclamation points, no promises of "massive gains."
- **Visual Language:** Light mode (Stone-50/White backgrounds). High contrast text (Slate-900). Accents in Sky-600. Status colors: Green-500 (Active), Orange-500 (Warning), Red-600 (Kill Switch).
- **Typography:** Playfair Display (Serif) for headlines/gravitas. Inter (Sans-serif) for body/UI. JetBrains Mono for data/metrics.

---

## Task 1: Rewrite the Hero Section
Update the hero section in `app/landing/page.tsx` to reflect the new positioning.

**New Copy:**
- **Eyebrow (Badge):** `Live Account · IBKR Portfolio Margin · Fully Automated`
- **Headline:** `The first retail trading system that knows when not to trade.`
- **Subheadline:** `A fully automated, regime-aware trading system running equity momentum and options premium income in parallel. With a 7-layer risk stack and PIN-protected kill switch, it removes the leading cause of retail underperformance: discretionary override at the moment of trade.`
- **Primary CTA Button:** `Join the Waitlist` (Scrolls to pricing/waitlist section)
- **Secondary CTA Button:** `Read the Strategy` (Links to `/strategy`)

---

## Task 2: Restructure the "Features" Section into JTBD Pillars
Replace the current 6-box feature grid with a 3-column layout focused on the core Jobs-To-Be-Done.

**Pillar 1: Protect capital from emotion**
- **Title:** Emotion is architecturally impossible.
- **Body:** You know how to trade. Your problem is overriding your own rules when you get scared or greedy. Winzinvest removes your hands from the keyboard at the exact moment you are most likely to make a mistake.

**Pillar 2: Institutional risk management**
- **Title:** A system built for capital preservation.
- **Body:** Anyone can build a screener that buys breakouts. The hard part is knowing when to sit in cash. With a 3-tier drawdown circuit breaker and a PIN-protected kill switch, the system actively prevents trading in choppy regimes.

**Pillar 3: Compound yield passively**
- **Title:** Yield that scales without your time.
- **Body:** Managing covered calls across 20 positions is a full-time job. Winzinvest automates the 80% decay roll, avoids earnings blackouts, and protects dividend yield—turning your equity portfolio into a passive income engine.

---

## Task 3: Implement the Pricing & Waitlist Section
Add a new section above the footer for the pricing tiers and waitlist signup. This replaces the current generic CTA.

**Section Header:** `Transparent pricing. Institutional infrastructure.`

**Tier 1: Intelligence (Signals Only)**
- **Price:** `$49/mo`
- **Features:**
  - Daily regime status (Expansion, Choppy, Tightening)
  - Pre-market screener signals (Longs & Mean Reversion)
  - Options income candidates
  - Manual execution required
- **CTA:** `Join Intelligence Waitlist` (Opens modal or form)

**Tier 2: Automation (Full Execution)**
- **Price:** `$149/mo`
- **Features:**
  - Everything in Intelligence
  - Direct IBKR API integration
  - Fully automated entry, exit, and options rolling
  - 7-layer execution risk gates
  - PIN-protected kill switch
- **CTA:** `Join Automation Waitlist` (Opens modal or form)

**Tier 3: Founding Member (Pre-Sell)**
- **Price:** `$79/mo` (Lifetime discount)
- **Badge:** `Limited to 50 spots`
- **Description:** Secure early access to the Automation tier at a permanent discount while we migrate the local infrastructure to the cloud.
- **CTA:** `Pre-Order Now` (Link to Stripe Payment Link - use `#` for now)

---

## Task 4: Build the Waitlist Capture Component
Create a new client component `app/components/WaitlistForm.tsx`.
- It should accept an `email` input and a hidden `tier` value based on which button was clicked.
- For now, mock the submission state (show a loading spinner for 1 second, then a success message: `You're on the list. We'll be in touch.`).
- Ensure the form styling matches the clean, light-mode SaaS aesthetic (Stone-50 background, Sky-600 focus rings).

---

## Task 5: Retain the Best Existing Sections
Do **not** delete or modify the following sections from the current `page.tsx`, as they are highly effective:
1. The "Backtest Performance" metric cards (2yr/3yr toggle).
2. The "What happens every trading day" timeline (7:00 AM to Fri 3PM).
3. The "Competitive Comparison" table (Winzinvest vs Trade Ideas, Composer, etc.).

**Execution Instructions:**
Please provide the updated code for `app/landing/page.tsx` and the new `app/components/WaitlistForm.tsx`. Ensure all Tailwind classes adhere strictly to the defined color palette and typography rules.
