# Design System: Mission Control
**UI Design Playbook Deliverable**  
**Slug:** `mission-control`  
**Version:** 1.0  
**Created:** 2026-03-07  
**Sources:** Rule 118 (Brand System), Rule 211 (Micro-Interactions), Rule 213 (Sophisticated Visual Design)  
**References:** `BRAND-SYSTEM-mission-control.md`, `MICRO-INTERACTIONS-mission-control.md`

---

## 1. Design Philosophy

**Aesthetic Direction:** "Bloomberg Terminal meets Kinfolk magazine"  
Not dark/neon (crypto). Not corporate gray (enterprise SaaS). Not flat minimal (consumer app).  
**Warm, institutional precision** — stone neutrals with sky-600 accent, serif headlines, multi-layer depth.

**Differentiation from Generic Shadcn/UI:**
- Playfair Display serif replaces Inter-everywhere monoculture
- 3-stage layered shadows instead of single `shadow-sm`
- Animated orb mesh gradient hero vs. flat colored banner
- Premium button with shimmer sweep vs. flat color fill
- Testimonial watermark quote character vs. plain card
- Decorative gradient line under section headers vs. nothing

**Red Dot Award Inspirations:**
- **Layout:** Award-winning financial data tools (density + whitespace balance)
- **Typography pairing:** Editorial publications (serif metric + sans body)
- **Depth system:** Physical product design (material elevation translated to CSS shadow stacks)
- **Motion:** Apple HIG precision (cubic-bezier easing, purposeful transforms)

---

## 2. Color System

### 2.1 CSS Custom Property Tokens

```css
:root {
  /* Primary */
  --brand-primary:        #0284c7;  /* sky-600  */
  --brand-primary-dark:   #0369a1;  /* sky-700  — hover state */
  --brand-primary-light:  #f0f9ff;  /* sky-50   — tinted wells */
  --brand-primary-border: #bae6fd;  /* sky-200  — subtle borders */

  /* RGB variants (for rgba() in shadows) */
  --brand-primary-rgb:    2, 132, 199;
  --brand-success-rgb:   22, 163, 74;
  --brand-danger-rgb:   220, 38, 38;
  --neutral-ink-rgb:     15, 23, 42;

  /* Semantic */
  --brand-success:        #16a34a;  /* green-600 */
  --brand-success-bg:     #f0fdf4;  /* green-50  */
  --brand-success-border: #bbf7d0;  /* green-200 */
  --brand-danger:         #dc2626;  /* red-600   */
  --brand-danger-bg:      #fef2f2;  /* red-50    */
  --brand-danger-border:  #fecaca;  /* red-200   */
  --brand-warning:        #f97316;  /* orange-500 */
  --brand-warning-bg:     #fff7ed;  /* orange-50  */

  /* Neutral Scale */
  --neutral-50:  #fafaf9;  /* page background */
  --neutral-100: #f5f5f4;
  --neutral-200: #e7e5e4;  /* borders */
  --neutral-300: #d6d3d1;
  --neutral-400: #a8a29e;  /* placeholders */
  --neutral-500: #78716c;  /* labels */
  --neutral-600: #57534e;  /* secondary text */
  --neutral-900: #0f172a;  /* primary text (slate-900) */
  --surface:     #ffffff;
  --surface-dark:#0f172a;  /* CTA dark band */
}
```

### 2.2 State Color Map

| Interaction State | Color Token | Visual |
|---|---|---|
| Primary button rest | `--brand-primary` | sky-600 |
| Primary button hover | `--brand-primary-dark` | sky-700 |
| Primary button active | `#075985` (sky-800) | darker press state |
| Primary button disabled | `--neutral-400` + 50% opacity | muted |
| Link rest | `--brand-primary` | sky-600 |
| Link hover | `--brand-primary-dark` | sky-700 |
| Focus ring | `--brand-primary` 3px offset-2 | sky-600 outline |
| Success/profit | `--brand-success` | green-600 |
| Error/loss | `--brand-danger` | red-600 |
| Warning | `--brand-warning` | orange-500 |

### 2.3 WCAG AA Contrast Reference

| Foreground | Background | Ratio | Pass Level |
|---|---|---|---|
| `--neutral-900` (#0f172a) | `--neutral-50` (#fafaf9) | 19.1:1 | ✅ AAA |
| `--neutral-600` (#57534e) | white | 5.8:1 | ✅ AA |
| `--brand-primary` (#0284c7) | white | 5.1:1 | ✅ AA large; use `--brand-primary-dark` for body text |
| `--brand-primary-dark` (#0369a1) | white | 7.0:1 | ✅ AAA |
| `--brand-success` (#16a34a) | white | 4.6:1 | ✅ AA large; pair with `--brand-success-bg` for body |
| `--brand-danger` (#dc2626) | white | 4.5:1 | ✅ AA minimum; use `--brand-danger-bg` for alerts |
| white | `--surface-dark` (#0f172a) | 19.1:1 | ✅ AAA |

---

## 3. Typography System

### 3.1 Font Stack

| Role | Font Family | Fallback | Token |
|---|---|---|---|
| **Display / Headlines** | Playfair Display | Georgia, Times New Roman, serif | `--font-serif` |
| **Body / UI** | Inter | system-ui, -apple-system, sans-serif | `--font-sans` |
| **Data / Prices** | JetBrains Mono | Fira Code, Cascadia Code, monospace | `--font-mono` |

**Load:** `@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap')`

### 3.2 Type Scale

| Token | Name | Size | Line Height | Weight | Font | Usage |
|---|---|---|---|---|---|---|
| `--type-display` | Display | `clamp(2.25rem, 5vw, 3.5rem)` | 1.15 | 700 | Playfair | Hero headline |
| `--type-h1` | H1 | `2.5rem` | 1.2 | 700 | Playfair | Page title |
| `--type-h2` | H2 | `2rem` | 1.25 | 700 | Playfair | Section header |
| `--type-h3` | H3 | `1.25rem` | 1.4 | 600 | Inter | Card title |
| `--type-body` | Body | `1rem` | 1.6 | 400 | Inter | Body copy |
| `--type-sm` | Small | `0.875rem` | 1.55 | 400 | Inter | Supporting text |
| `--type-xs` | Caption/Label | `0.75rem` | 1.4 | 600 | Inter (uppercase) | Section labels |
| `--type-metric` | KPI | `2.5rem` | 1.0 | 700 | Playfair | Dashboard metrics |
| `--type-mono` | Mono | `0.875rem` | 1.5 | 400 | JetBrains Mono | Prices, data |

### 3.3 Label Pattern (Section + Card Labels)
```css
.section-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--neutral-500);
}
```

### 3.4 Metric Value Pattern (KPI Cards — Rules 116/118)
```css
.metric-value {
  font-family: var(--font-serif);
  font-size: 2.5rem;
  font-weight: 700;
  line-height: 1;
  color: var(--brand-primary);
}
```

---

## 4. Spacing System

**Base unit:** 4px (0.25rem)  
**Scale:** 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80 px

| Token | Value | Common Use |
|---|---|---|
| `--space-1` | 0.25rem (4px) | Icon margins |
| `--space-2` | 0.5rem (8px) | Tight label → value |
| `--space-3` | 0.75rem (12px) | Badge padding |
| `--space-4` | 1rem (16px) | Standard gap |
| `--space-6` | 1.5rem (24px) | Card padding |
| `--space-8` | 2rem (32px) | Between sections in a card |
| `--space-section` | 5rem (80px) | Section padding-block |
| `--radius` | 0.75rem (12px) | All cards, inputs, badges |

---

## 5. Shadow & Elevation System (Rule 213)

**Principle:** Never use a single shadow. All elevation uses 3-stage stacks.

```css
/* Stage 1: Resting surface */
--shadow-sm:
  0 1px 2px rgba(var(--neutral-ink-rgb), 0.04);

/* Stage 2: Standard card */
--shadow-card:
  0 2px  8px  rgba(var(--neutral-ink-rgb), 0.04),
  0 8px  24px rgba(var(--neutral-ink-rgb), 0.06),
  0 16px 48px rgba(var(--neutral-ink-rgb), 0.08);

/* Stage 3: Hover / lifted */
--shadow-hover:
  0 4px  12px rgba(var(--neutral-ink-rgb), 0.06),
  0 12px 32px rgba(var(--neutral-ink-rgb), 0.08),
  0 24px 64px rgba(var(--brand-primary-rgb), 0.12); /* brand-tinted far shadow */

/* Stage 4: Floating / modal */
--shadow-float:
  0 8px  32px rgba(var(--neutral-ink-rgb), 0.10),
  0 24px 64px rgba(var(--brand-primary-rgb), 0.14);
```

**Z-Index Hierarchy:**
| Level | Z-Index | Use |
|---|---|---|
| Surface 1 | z-auto | Base content |
| Surface 2 | z-10 | Cards, elevated |
| Surface 3 | z-20 | Dropdowns |
| Surface 4 | z-50 | Modals, toasts |
| Overlays | z-100 | Nav, sticky header |

---

## 6. Component Specifications

### 6.1 Metric Card (Rules 116, 118, 119)
```
background: white
border: 1px solid --neutral-200
border-radius: 12px (--radius)
padding: 1.25rem 1.5rem
box-shadow: --shadow-card

Label:   font-xs, font-semibold, uppercase, tracking-wider, neutral-500
Value:   font-serif, text-4xl, font-bold, brand-primary (neutral) / green-600 (profit) / red-600 (loss)
Sub:     font-xs, neutral-400
Hover:   translateY(-4px), --shadow-hover
```

### 6.2 Primary Button
```
background: linear-gradient(135deg, brand-primary 0%, brand-primary-dark 100%)
box-shadow: 0 4px 12px rgba(primary-rgb, 0.28), inset 0 1px 0 rgba(255,255,255, 0.18)
border-radius: 12px
padding: 0.75rem 1.5rem (base) / 0.9rem 2rem (--btn--lg)
font: Inter, 1rem, semibold
overflow: hidden (for shimmer ::after)

States:
  Rest:   gradient + pulse animation
  Hover:  translateY(-2px), shimmer sweep, enhanced shadow
  Active: scale(0.98), reduced shadow
  Focus:  3px solid brand-primary, offset 3px
  Disabled: neutral-400 bg, 50% opacity, no animation
```

### 6.3 Secondary / Ghost Button
```
background: transparent
border: 2px solid --neutral-300
color: --neutral-600
border-radius: 12px

States:
  Hover:  bg-neutral-100, border-neutral-400, color-neutral-900
  Focus:  2px solid brand-primary, offset 3px
```

### 6.4 Standard Card
```
background: white
border: 1px solid --neutral-200
border-radius: 12px
padding: 1.5rem
box-shadow: --shadow-card

Hover:
  transform: translateY(-6px) scale(1.01)
  box-shadow: --shadow-hover
  Duration: 350ms, cubic-bezier(0.4, 0, 0.2, 1)
```

### 6.5 Accent-Border Card Variants
```
.card--accent:  border-left: 4px solid --brand-primary
.card--success: border-left: 4px solid --brand-success
.card--danger:  border-left: 4px solid --brand-danger
.card--warning: border-left: 4px solid --brand-warning
```

### 6.6 Table
```
Min-width: 36rem (prevents mobile squish)
Header:   bg-neutral-50, border-bottom neutral-200, xs label style
Row:      border-bottom neutral-200, hover bg-neutral-50
Cell:     padding 0.875rem 1rem, font-sm, neutral-600
Highlighted col:  bg-brand-primary-light, box-shadow inset brand-primary-border
```

### 6.7 FAQ Accordion
```
Native <details>/<summary> — zero JavaScript required
Container: bg-white, border neutral-200, border-radius 12px

Summary:   padding 1.125rem 1.25rem, font-semibold, neutral-900
           display: flex, justify-content: space-between
           hover: bg-neutral-50
           focus-visible: 2px ring brand-primary (inset)

Chevron:   transition rotate(0 → 180deg) on open, 250ms ease-standard
Body:      fade-in-up 250ms ease-decelerate on open
Open state: box-shadow --shadow-card, border-color neutral-300

aria-expanded: synced via small inline JS
```

### 6.8 Form Input
```
background: white
border: 1px solid --neutral-200
border-radius: 12px
padding: 0.75rem 1.25rem
font: Inter, 1rem, neutral-900

Focus:
  border-color: brand-primary
  box-shadow: 0 0 0 3px rgba(brand-primary-rgb, 0.15)
  transition: 150ms ease

On dark bg (final CTA):
  background: rgba(255,255,255, 0.08)
  border: 1px solid rgba(255,255,255, 0.2)
  color: white
  Focus border: rgba(255,255,255, 0.5)
```

---

## 7. Hero Section System (Rule 213)

### 7.1 Mesh Gradient Background
```css
/* 3-layer radial mesh */
background:
  radial-gradient(ellipse 80% 60% at 0% 10%,
    rgba(var(--brand-primary-rgb), 0.07), transparent 55%),
  radial-gradient(ellipse 60% 50% at 100% 90%,
    rgba(var(--brand-success-rgb), 0.05), transparent 50%),
  var(--neutral-50);
```

### 7.2 Animated Orbs (pseudo-elements)
```
Orb 1: 560×560px, brand-primary 10%, blur 80px, top-left, 22s drift
Orb 2: 400×400px, brand-success 7%, blur 70px, bottom-right, 18s drift (delay -7s)
Animation: translate + scale, ease-in-out, infinite
z-index: 0 (behind content)
```

### 7.3 Dot-Grid Pattern Overlay
```
Element: .hero__pattern (HTML span, aria-hidden)
Pattern: radial-gradient 1px dots, 28px × 28px grid
Opacity: 0.04
z-index: 1 (above orbs, below content)
```

### 7.4 Content Layer
```
All hero copy + CTAs: z-index 10
position: relative (to establish stacking context)
```

### 7.5 Hero Visual Checklist (Rule 213)
- [x] Animated gradient mesh background (3-layer radial)
- [x] Floating orb elements (2 CSS pseudo-element orbs)
- [x] Pattern overlay (28px dot grid, 4% opacity)
- [x] Proper layering: bg (z-0) → pattern (z-1) → content (z-10)
- [ ] Optional: Dashboard screenshot mockup (add at handoff)

---

## 8. Animation & Motion System (Rule 211)

Full spec: `MICRO-INTERACTIONS-mission-control.md`

**Quick Reference:**

| Token | Value |
|---|---|
| `--ease-standard` | `cubic-bezier(0.4, 0, 0.2, 1)` |
| `--ease-decelerate` | `cubic-bezier(0, 0, 0.2, 1)` |
| `--duration-fast` | `150ms` |
| `--duration-base` | `250ms` |
| `--duration-slow` | `350ms` |
| `--duration-reveal` | `700ms` |

**Scroll Reveal:**
```css
.animate-fade-in {
  animation: fade-in-up 700ms cubic-bezier(0.4, 0, 0.2, 1) both;
}
/* Stagger: nth-child × 50ms delay */
```

**Hover Choreography Rule (Rule 213):** Every card hover must animate ≥3 properties (transform, shadow, + at least one child element).

---

## 9. Content & Accessibility Standards (Rules 214, 211)

### Writing
- Section labels: uppercase, `font-xs font-semibold tracking-wider`, neutral-500
- Body copy: max-width 65ch, 1.6 line-height, neutral-600
- CTAs: verb-first, outcome-describing ("Request dashboard access" not "Submit")
- Error messages: 3-part (what happened / why / how to fix)
- No "click here", "learn more", "powerful", "robust", "seamless"

### Accessibility
- Semantic HTML5: `<header>`, `<nav>`, `<main>`, `<section>`, `<footer>`
- Every `<section>` has `aria-labelledby` pointing to its heading
- Every interactive element: visible `focus-visible` ring (3px, brand-primary)
- All images: meaningful `alt` text (not "image of…")
- FAQ: `aria-expanded` synced to `open` attribute
- Form inputs: `<label>` always visible (not placeholder-only)
- `prefers-reduced-motion`: all animations gated
- Color is never the sole differentiator (always paired with text/icon)

---

## 10. Red Dot Award Design Inspiration Map

| Design Decision | Inspiration Source |
|---|---|
| Serif + sans-serif pairing (Playfair + Inter) | Award-winning editorial / financial data product typography |
| 3-stage shadow depth system | Physical product material elevation, translated to digital surface design |
| Warm stone neutrals (not cool gray) | Premium consumer goods brands; warm neutrals signal care/quality |
| Sky-600 accent (precise, not flashy) | Professional instrument UX (measurement tools, medical devices) |
| Dot-grid pattern overlay | Award-winning dashboard tools — adds depth without noise |
| Minimal animation with purpose | Apple HIG award pattern — "motion should be invisible unless guiding" |
| Testimonial watermark quote character | Print magazine / editorial design pattern |

---

## 11. Quality Gates (Before Shipping Any UI)

### Visual
- [ ] Multi-layer shadows (3+ stages on all elevated surfaces)
- [ ] Hero section: mesh gradient + orbs + pattern + content layers
- [ ] No flat single-shadow cards
- [ ] Premium button: gradient fill + shimmer on hover
- [ ] Section headers: decorative gradient underline present
- [ ] Testimonials: quote watermark present

### Interaction (Rule 213)
- [ ] Card hovers animate ≥3 properties
- [ ] Staggered reveals use `cubic-bezier(0.4, 0, 0.2, 1)`
- [ ] All hover transforms return to rest on `mouseleave`
- [ ] CTA pulse stops on hover; shimmer fires

### Accessibility (Rules 211, 214)
- [ ] `prefers-reduced-motion` disables all animated properties
- [ ] Focus rings visible on all interactive elements without mouse
- [ ] `aria-expanded` synced on all accordions
- [ ] Color contrast passes WCAG AA for all text/UI combinations
- [ ] `axe DevTools` audit: 0 violations

### Content (Rule 214)
- [ ] No "click here", "learn more", or abstract adjectives
- [ ] Every CTA is verb-first
- [ ] Error messages use 3-part format
- [ ] Headings form logical H1→H2→H3 hierarchy
- [ ] Body copy max-width: 65ch

---

*Canonical source for all UI implementation, component design, and creative asset work.*  
*Cross-references: `BRAND-SYSTEM-mission-control.md`, `MICRO-INTERACTIONS-mission-control.md`, `VOICE-TONE-GLOSSARY-mission-control.md`*
