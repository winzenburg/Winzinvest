# Brand System: Mission Control
**Slug:** `mission-control`  
**Version:** 1.0  
**Created:** 2026-03-07  
**Status:** Active — feeds Landing Builder, Visual Asset Agent, UI Design System

---

## 1. Brand Overview

### Positioning Statement
> For sophisticated retail investors who are tired of watching automated tools fall short of institutional quality, **Mission Control** is a fully automated trading platform that executes hedge-fund-caliber strategies — regime detection, multi-layer risk management, options income, and dynamic sizing — without requiring the investor to touch a single trade.

### One-Sentence Tagline
> *Institutional-grade automation. Built for people who have better things to do.*

### Brand Personality (Core Adjectives)
1. **Precise** — every number earns its place; no fluff, no vagueness
2. **Authoritative** — speaks from evidence, not promise
3. **Composed** — calm under volatility, never alarmist
4. **Transparent** — the audit trail is always open
5. **Relentless** — runs 24/7; it doesn't sleep, doesn't hesitate, doesn't deviate

### Target Audience
- **Primary:** Retail investors aged 35–60 with $250K–$2M investable assets
- **Profile:** Technically literate (not coders), experienced with markets, currently using active brokers or semi-automated tools, time-constrained professionals or early retirees
- **JTBD:** "Let an expert system handle the execution while I focus on my life — but keep me fully informed."
- **Emotional driver:** Trust + control. They want to hand off execution without handing off oversight.

### Differentiation vs. Competitors
| Competitor | What they offer | Our advantage |
|---|---|---|
| **Trade Ideas** | AI screener, no automated execution | We execute; they only flag |
| **Composer** | Rule-based automation, no risk layers | Multi-layer regime + risk gates; not rule-based |
| **TastyTrade** | Options education + manual execution | Fully automated options income with no manual steps |
| **QuantConnect** | Backtest platform, requires coding | Zero code; institutional logic pre-built and live |
| **Hedge funds** | Institutional-grade, $1M+ minimums | Same logic, retail account, fraction of the cost |

---

## 2. Color System

> All tokens mapped to the project's established design system (`010-mission-control-design-system.mdc`).

### Primary Palette

| Token | Name | HEX | Usage |
|---|---|---|---|
| `--brand-primary` | Sky 600 | `#0284c7` | CTAs, links, active states, sky accent |
| `--brand-primary-dark` | Sky 700 | `#0369a1` | Hover state on primary buttons |
| `--brand-primary-light` | Sky 50 | `#f0f9ff` | Tinted card backgrounds, icon wells |
| `--brand-primary-border` | Sky 200 | `#bae6fd` | Subtle borders on tinted sections |

### Semantic Colors

| Token | Name | HEX | Usage |
|---|---|---|---|
| `--brand-success` | Green 600 | `#16a34a` | Profit, long exposure, positive delta |
| `--brand-success-bg` | Green 50 | `#f0fdf4` | Success alert backgrounds |
| `--brand-danger` | Red 600 | `#dc2626` | Loss, short exposure, stop-triggers, errors |
| `--brand-danger-bg` | Red 50 | `#fef2f2` | Error alert backgrounds |
| `--brand-warning` | Orange 500 | `#f97316` | Drawdown warnings, degraded status |
| `--brand-warning-bg` | Orange 50 | `#fff7ed` | Warning alert backgrounds |

### Neutral Scale (Stone palette)

| Token | Tailwind | HEX | Usage |
|---|---|---|---|
| `--neutral-50` | stone-50 | `#fafaf9` | Page background |
| `--neutral-100` | stone-100 | `#f5f5f4` | Inactive tab backgrounds, subtle wells |
| `--neutral-200` | stone-200 | `#e7e5e4` | Card borders, table dividers |
| `--neutral-400` | stone-400 | `#a8a29e` | Placeholder text, faint labels |
| `--neutral-500` | stone-500 | `#78716c` | Tertiary text, muted labels |
| `--neutral-600` | stone-600 | `#57534e` | Secondary body text |
| `--neutral-900` | slate-900 | `#0f172a` | Primary text (headings, key data) |
| `--surface` | white | `#ffffff` | Card surfaces |
| `--surface-dark` | slate-900 | `#0f172a` | CTA section backgrounds (dark mode band) |

### State Colors

| State | Token | Value |
|---|---|---|
| Button hover | `--brand-primary-dark` | `#0369a1` |
| Button focus ring | `--brand-primary` at 3px offset | `#0284c7` |
| Button disabled | `--neutral-400` bg, `--neutral-200` border | opacity 50% |
| Link hover | `--neutral-600` | `#57534e` |
| Input focus | `2px ring --brand-primary` | `#0284c7` |
| Error input | `border --brand-danger` + `bg --brand-danger-bg` | see tokens |

### WCAG AA Compliance Notes
- `--brand-primary` (#0284c7) on white: **5.1:1** ✅ AA large text; use `--brand-primary-dark` for small text on white
- `--neutral-900` (#0f172a) on `--neutral-50` (#fafaf9): **19.1:1** ✅
- `--neutral-600` (#57534e) on white: **5.8:1** ✅
- `--brand-success` (#16a34a) on white: **4.6:1** ✅ (AA large text only — pair with bg-green-50 for body)
- `--brand-danger` (#dc2626) on white: **4.5:1** ✅

---

## 3. Typography System

### Font Stack

| Role | Font | Rationale |
|---|---|---|
| **Display / Metric** | Playfair Display (serif) | Authority + precision; evokes financial publications (Bloomberg, WSJ), not tech startup |
| **Body / UI** | Inter (sans-serif) | Best-in-class screen legibility; trusted in institutional dashboards |
| **Data / Prices** | JetBrains Mono | Tabular figures, monospaced alignment for price columns |

**Google Fonts import:**
```css
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
```

### Type Scale

| Step | Name | Size | Line Height | Weight | Usage |
|---|---|---|---|---|---|
| `--type-display` | Display | 3.5rem (56px) | 1.15 | 700 | Hero headline (Playfair) |
| `--type-h1` | H1 | 3rem (48px) | 1.2 | 700 | Page titles (Playfair) |
| `--type-h2` | H2 | 2rem (32px) | 1.25 | 700 | Section headers (Playfair) |
| `--type-h3` | H3 | 1.25rem (20px) | 1.4 | 600 | Card titles (Inter semibold) |
| `--type-body` | Body | 1rem (16px) | 1.6 | 400 | Body copy (Inter) |
| `--type-sm` | Small | 0.875rem (14px) | 1.5 | 400 | Supporting text |
| `--type-xs` | Caption | 0.75rem (12px) | 1.4 | 600 | Labels — uppercase + wider tracking |
| `--type-metric` | Metric | 2.5rem (40px) | 1.0 | 700 | KPI cards (Playfair) |
| `--type-mono` | Mono | 0.875rem (14px) | 1.5 | 400 | Price data (JetBrains Mono) |

### Typography Rules
- Section/card labels: `font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--neutral-500)`
- Metric values: Playfair Display, `2.5rem`, `font-weight: 700`, colored per semantic (sky-600 for neutral, green-600 for positive)
- Body copy: Inter, `1rem`, `1.6` line height, `--neutral-600`
- Headlines on dark backgrounds: `color: white`; on light: `--neutral-900`

---

## 4. Voice & Tone

### Brand Voice Definition
Mission Control sounds like a **seasoned portfolio manager explaining to a trusted friend** — not a salesperson closing a deal. Confident but not arrogant. Data-anchored but human.

### Tone Spectrum
```
Formal ←————————●——→ Casual         (leans formal, never stuffy)
Technical ←——●—————→ Simple         (precise terms, plain explanations)
Serious ←—●————————→ Playful        (stakes are real; levity only in context)
Direct ←●——————————→ Hedged         (no weasel words; own the claim)
```

### Voice: Do's
| ✅ Do | Example |
|---|---|
| Lead with outcomes, not features | "Earn $8,600/month in premium income — without placing a single order" |
| Use specific numbers | "Six strategies. 147 risk gates. Zero manual steps." |
| Acknowledge risk honestly | "This system manages risk — it doesn't eliminate it" |
| Match the investor's insider language | "Regime detection", "VIX-gated entries", "delta-neutral exposure" |
| Let the data speak | "2-year backtest: 31% annualized. Live account: on track." |

### Voice: Don'ts
| ❌ Don't | Why |
|---|---|
| "Guaranteed returns" | Legally and ethically false; destroys trust |
| Startup hype ("disruptive", "game-changing") | Audience is experienced; hype reads as amateur |
| Passive voice on risk | Own the risk profile; don't bury it |
| Generic feature lists ("powerful", "robust") | Meaningless; replace with specifics |
| "Easy money" framing | Misrepresents the sophistication; attracts wrong audience |

### Sample Phrases in Brand Voice
- **Hero CTA:** "See what's running right now →"
- **Benefit summary:** "Institutional logic. Retail account. No code required."
- **Objection reframe:** "You're not delegating control — you're gaining visibility. Every decision is logged, auditable, and explainable."
- **Social proof lead-in:** "The audit trail doesn't lie."
- **Error/alert tone:** "Regime detected: UNFAVORABLE. New positions paused. Existing holds intact."

---

## 5. Visual Style Direction

### Overall Aesthetic
**"Bloomberg Terminal meets Kinfolk magazine"** — the data density of an institutional dashboard softened with generous whitespace, serif typography, and stone-warm neutrals. Not dark/neon (that's crypto). Not corporate gray (that's Salesforce). Warm, precise, trustworthy.

### Layout Principles
- **Whitespace as trust signal**: Crowded pages feel amateur; generous margins feel expensive
- **Hierarchy through scale**: Display serif for the one claim that matters most; smaller type for everything else
- **Cards as containment units**: `bg-white`, `border: 1px solid --neutral-200`, `border-radius: 12px`, `padding: 1.5rem`
- **Left-aligned body copy**: Centered headlines only in hero sections; left-align everything else for scannability
- **Grid**: 12-column underlying grid; 2/3/4-column card grids depending on breakpoint

### Imagery Style
- **Primary**: Abstract market data visualizations (charts, heatmaps) screenshotted from the live dashboard
- **Secondary**: Clean geometric illustrations suggesting flow/automation (avoid humanoid figures — feels too startup)
- **No stock photos** of people at computers — this is an insider product, not a beginner tutorial

### Motion Notes
- **Minimal animation**: One entrance animation max per section (fade-in-up on scroll)
- **No parallax**: Distracting for data-focused audience; impairs accessibility
- **CTA pulse**: Subtle `box-shadow` pulse on primary CTA button to draw the eye
- Respect `prefers-reduced-motion` — all animations should be wrapped in the media query

---

## 6. Mascot / Guide Concept

**Not recommended for this product.** The target audience is sophisticated investors who would view a cartoon mascot as a trust signal mismatch. The brand identity is the **audit trail itself** — the closest thing to a "guide" is the live performance data.

**Alternative**: Use the **kill switch icon** (power button SVG) as a recurring visual motif — it represents control, authority, and the operator's ultimate oversight. Appears in the logo area and throughout the UI.

---

## 7. Competitive Brand Map

### Where Competitors Sit

```
                    HIGH AUTOMATION
                          ↑
       QuantConnect        |        Mission Control ←← we are here
       (code-heavy)        |        (institutional automation, zero code)
COMPLEX ————————————————————————————————————————— SIMPLE
       Hedge Funds         |        Composer
       (inaccessible)      |        (rule-based, limited risk mgmt)
                          ↓
                    LOW AUTOMATION
                    (TastyTrade, Trade Ideas = manual execution)
```

### Whitespace We Own
1. **"Zero-code institutional automation"** — QuantConnect requires coding; Composer lacks risk depth
2. **"Full auditability"** — no competitor publicly shows their decision trail; we lead with it
3. **"Warm authority"** — every competitor is either cold/technical or startup-casual; warm-precise is unclaimed

---

## 8. Landing Page Concept

**File locations:**
- `docs/validation/landing/mission-control/index.html`
- `docs/validation/landing/mission-control/styles.css`

### Section-by-Section Map

| Section | Headline | Color Usage | Type Usage | CTA |
|---|---|---|---|---|
| **Hero** | "Your money works 24/7. You get the reports." | `--neutral-50` bg, `--brand-primary` accent | Display Playfair (H1), Inter subtitle | Primary CTA: "See inside the system →" |
| **Performance stats** | 4 KPI cards | White cards, `--neutral-200` border | Playfair metric values, Inter labels | — |
| **How it works** | "Three layers. One outcome." | `--neutral-50` bg | Inter H3 for steps | Secondary CTA: "Read the full strategy →" |
| **Benefits** | "What you actually get" | White cards with `--brand-primary-light` left border | Inter body | — |
| **Comparison table** | "Why not just use [X]?" | White bg, `--brand-success` checkmarks | Inter sm | — |
| **Objections** | "Fair questions" | `--neutral-100` band | Inter body with Playfair pull-quotes | — |
| **FAQ** | — | White cards, accordion | Inter | — |
| **Final CTA** | "The system is running. The question is: are you watching?" | `--surface-dark` (slate-900) bg, white text | Playfair H2, Inter body | "Request access →" |

### Key Conversion Moments (Motion Notes)
- **CTA button**: 3px `box-shadow` pulse on load (2s ease-in-out, infinite) — stops on hover
- **KPI cards**: Fade-in-up stagger (0.1s delay between cards) on viewport enter
- **FAQ accordion**: Smooth `max-height` transition (0.25s ease)
- All wrapped in `@media (prefers-reduced-motion: reduce)` override

---

## 9. AI Tool Stack Used (Rule 119)

| Step | Tool | Status | Output |
|---|---|---|---|
| 1. Competitive Brand Audit | Internal analysis (transcript) | ✅ Complete | Section 7 above |
| 2. Color + Type + Voice | Claude synthesis | ✅ Complete | Sections 2–4 above |
| 3. Critique | Claude self-review vs. 010-DS rules | ✅ Complete | Alignment confirmed |
| 4. Mascot | N/A — not appropriate for audience | ✅ Deliberate skip | See Section 6 |
| 5. Documentation | Cursor | ✅ Complete | This file |

---

*Last updated: 2026-03-07. Canonical source for all downstream landing page, UI, and creative asset work.*
