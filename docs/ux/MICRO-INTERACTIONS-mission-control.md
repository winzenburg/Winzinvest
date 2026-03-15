# Micro-Interaction Spec: Mission Control
**Rule 211 Deliverable**  
**Slug:** `mission-control`  
**Version:** 1.0  
**Created:** 2026-03-07  
**Easing Standard:** `cubic-bezier(0.4, 0, 0.2, 1)` (Apple-style, all interactions)  
**CSS Tokens:** `--ease-standard`, `--duration-fast` (150ms), `--duration-base` (250ms), `--duration-slow` (350ms), `--duration-reveal` (700ms)

---

## Principles (from Rule 211)

1. **Support the journey** — every animation reinforces a conversion step, state change, or data clarity moment.
2. **Subtlety first** — motion is "invisible" unless guiding; scale transforms stay ≤ 1.02, opacity shifts are gentle.
3. **Consistency** — all interactions use the same easing and duration tokens.
4. **Accessibility** — every animation is gated by `prefers-reduced-motion`. Fallback is always the static state.

---

## Interaction Catalog

### 1. Hero CTA Button — Primary Call to Action

**Component:** `.btn--primary`  
**Trigger:** Page load (idle pulse) + hover + click  

| Phase | Trigger | Purpose |
|---|---|---|
| Idle | Page load | Draw eye to primary conversion point |
| Hover | `mouseover` | Confirm affordance; raise elevation to signal importance |
| Active | `mousedown` | Tactile feedback; confirm click registered |
| Focus | Tab / keyboard | Accessible state — visible ring for keyboard users |

**Motion Spec:**

| State | Properties | Values | Duration | Easing |
|---|---|---|---|---|
| Idle pulse | `box-shadow` | `0 → 0 0 0 6px rgba(primary, 0.2) → 0` | 2000ms | `ease-in-out`, infinite |
| Hover | `transform`, `box-shadow`, `shimmer-sweep` | `translateY(-2px)`, shadow grows, pseudo-element slides 110% | 350ms | `cubic-bezier(0.4, 0, 0.2, 1)` |
| Shimmer | `::after transform` | `translateX(-110% skewX(-15°)) → translateX(110%)` | 550ms | `cubic-bezier(0.4, 0, 0.2, 1)` |
| Active | `transform`, `box-shadow` | `scale(0.98)`, shadow reduces | 150ms | `cubic-bezier(0.4, 0, 0.2, 1)` |
| Focus | `outline` | `3px solid --brand-primary, offset 3px` | instant | — |

**Fallback (reduced-motion):** Static gradient background. No pulse, no shimmer, no transform. Focus ring remains (accessibility).

**Testing:** Verify pulse stops on hover. Verify shimmer does not flash on keyboard focus (only mouse hover). Verify `prefers-reduced-motion: reduce` disables all animation properties.

---

### 2. KPI / Metric Cards — Scroll Reveal

**Component:** `.animate-fade-in` on `.card--metric`  
**Trigger:** Elements enter viewport  

**Motion Spec:**

| Phase | Properties | From → To | Duration | Easing | Delay (stagger) |
|---|---|---|---|---|---|
| Enter | `opacity`, `transform` | `0, translateY(24px)` → `1, translateY(0)` | 700ms | `cubic-bezier(0.4, 0, 0.2, 1)` | nth-child × 50ms |

**Stagger delays:** `0.05s, 0.10s, 0.15s, 0.20s` for up to 4 items.  
**Purpose:** Sequential reveal directs attention across the metric grid left-to-right; creates the impression of data "loading in" which signals live data rather than static illustration.  
**Fallback:** All cards visible at full opacity; no animation.

**Testing:** Cards animate once on first viewport entry. Disable `IntersectionObserver` and verify static fallback renders correctly.

---

### 3. Benefit Cards — Hover Choreography (3 properties)

**Component:** `.benefit-card` + child `.benefit-icon`  
**Trigger:** `mouseover`  

**Motion Spec:**

| Property | From → To | Duration | Easing |
|---|---|---|---|
| Card `transform` | `translateY(0) scale(1)` → `translateY(-6px) scale(1.01)` | 350ms | `cubic-bezier(0.4, 0, 0.2, 1)` |
| Card `box-shadow` | 3-stage base shadow → 3-stage hover shadow (brand-tinted) | 350ms | `cubic-bezier(0.4, 0, 0.2, 1)` |
| Icon `transform` | `scale(1) rotate(0)` → `scale(1.12) rotate(6deg)` | 350ms | `cubic-bezier(0.4, 0, 0.2, 1)` |
| Icon `background-color` | `rgba(primary, 0.08)` → `rgba(primary, 0.14)` | 250ms | `cubic-bezier(0.4, 0, 0.2, 1)` |

**Purpose:** The icon responding independently of the card creates depth and delight; signals interactivity without being distracting. The 6deg rotation adds personality while staying institutional.  
**Fallback:** No transform or shadow change on hover. Static card.

**Testing:** Verify 4 properties all transition simultaneously (not sequentially). Verify icon returns to rest position on `mouseleave`.

---

### 4. Step Cards — Number Badge Transform

**Component:** `.step.card` + child `.step__number`  
**Trigger:** `mouseover`  

**Motion Spec:**

| Property | From → To | Duration | Easing |
|---|---|---|---|
| Card `transform` | `translateY(0)` → `translateY(-4px) scale(1.005)` | 350ms | `cubic-bezier(0.4, 0, 0.2, 1)` |
| Card `border-left` | `transparent` → `3px solid --brand-primary` | 250ms | `ease` |
| Number `background` | `--brand-primary-light` → `--brand-primary` | 250ms | `cubic-bezier(0.4, 0, 0.2, 1)` |
| Number `color` | `--brand-primary-dark` → `white` | 250ms | `cubic-bezier(0.4, 0, 0.2, 1)` |
| Number `transform` | `scale(1)` → `scale(1.06)` | 350ms | `cubic-bezier(0.4, 0, 0.2, 1)` |

**Purpose:** The number badge inverting to filled brand color reinforces that you're at "step N" — guides comprehension through the 3-step flow.  
**Fallback:** Static card.

---

### 5. FAQ Accordion — Open/Close

**Component:** `<details>` + `<summary>` + `.faq-chevron`  
**Trigger:** `click` / `Enter` on summary  

**Motion Spec:**

| Property | Phase | From → To | Duration | Easing |
|---|---|---|---|---|
| `.faq-chevron` `transform` | Open | `rotate(0deg)` → `rotate(180deg)` | 250ms | `cubic-bezier(0.4, 0, 0.2, 1)` |
| `.faq-item__body` entrance | Open | `opacity: 0, translateY(-6px)` → `opacity: 1, translateY(0)` | 250ms | `cubic-bezier(0, 0, 0.2, 1)` |
| `.faq-item` `box-shadow` | Open | `none` → `var(--shadow-card)` | 350ms | `cubic-bezier(0.4, 0, 0.2, 1)` |
| `aria-expanded` | Toggle | `false` ↔ `true` | instant (JS) | — |

**Purpose:** Chevron rotation confirms state change. The body content sliding in from above (not below) feels natural given the summary sits above. Box-shadow appearing on the open item separates it from the closed stack visually.  
**Fallback:** Body visible immediately with no animation. Chevron static.

**Testing:** `aria-expanded` synced to `open` attribute via small JS snippet (already implemented). Verify keyboard focus moves to first line of answer after opening.

---

### 6. Testimonial Cards — Hover Lift + Border Grow

**Component:** `.testimonial-card`  
**Trigger:** `mouseover`  

**Motion Spec:**

| Property | From → To | Duration | Easing |
|---|---|---|---|
| `transform` | `translateY(0)` → `translateY(-5px)` | 350ms | `cubic-bezier(0.4, 0, 0.2, 1)` |
| `box-shadow` | base 3-stage → hover 3-stage | 350ms | `cubic-bezier(0.4, 0, 0.2, 1)` |
| `border-left-width` | `4px` → `6px` | 250ms | `cubic-bezier(0.4, 0, 0.2, 1)` |

**Decorative (non-interactive):** Large `"` watermark at `::after` is pure CSS; no animation.  
**Purpose:** The border growing subtly echoes the card lifting — two properties reinforcing one message: "this is important." Social proof cards lift more than benefit cards (5px vs 6px) to subtly de-emphasize decorative elements.  
**Fallback:** Static.

---

### 7. Form Input (Final CTA) — Focus Lift

**Component:** Email `<input>` in final CTA form  
**Trigger:** `focus` event  

**Motion Spec:**

| Property | From → To | Duration | Easing |
|---|---|---|---|
| `border-color` | `rgba(white, 0.2)` → `rgba(white, 0.5)` | 150ms | `ease` |
| `box-shadow` | `none` → `0 0 0 3px rgba(brand-primary, 0.3)` | 150ms | `ease` |

**Implemented via:** Inline `onfocus`/`onblur` handlers (JS-light; no dependency).  
**Purpose:** Confirms which field is active; critical for keyboard navigation.  
**Fallback:** High-contrast focus ring always present (inline border-color change happens in all cases).

**Testing:** Tab to the input — confirm focus ring is visible without mouse interaction. Verify `aria-required="true"` is present.

---

### 8. Navigation Links — Underline Grow

**Component:** `.nav__links a`  
**Trigger:** `mouseover`  

**Motion Spec:**

| Property | From → To | Duration | Easing |
|---|---|---|---|
| `::after width` | `0` → `100%` | 250ms | `cubic-bezier(0.4, 0, 0.2, 1)` |
| `color` | `--neutral-600` → `--neutral-900` | 150ms | `ease` |

**Purpose:** Growing underline reveals which nav item is active without jarring color pop; the color shift is a secondary reinforcement.  
**Fallback:** Standard `:hover` color change only. No animated underline.

---

### 9. Comparison Table — Row Hover

**Component:** `table tbody tr`  
**Trigger:** `mouseover`  

**Motion Spec (CSS only):**

| Property | From → To | Duration |
|---|---|---|
| `background-color` | `transparent` → `var(--neutral-50)` | 100ms |

**Purpose:** Keeps the eye on the row being read; reduces cognitive load in a dense 7-column table.  
**Fallback:** No row highlight.

---

### 10. Live Status Badge — Pulse

**Component:** `.hero__badge-dot`  
**Trigger:** Always-on (signals live system status)  

**Motion Spec:**

| Property | Keyframes | Duration | Easing |
|---|---|---|---|
| `opacity` | `1 → 0.4 → 1` | 2000ms | `ease-in-out`, infinite |

**Purpose:** The pulse is the only always-on animation. It signals a live, running system — critical trust signal that the system is active. All other animations are triggered or scroll-based.  
**Fallback (`prefers-reduced-motion`):** Dot visible at full opacity; no pulse. The ARIA label `"System status: live and trading"` conveys the same information.

---

## Motion Token Summary

| Token | Value | Used For |
|---|---|---|
| `--ease-standard` | `cubic-bezier(0.4, 0, 0.2, 1)` | All primary transitions |
| `--ease-decelerate` | `cubic-bezier(0, 0, 0.2, 1)` | Elements entering (e.g. FAQ body) |
| `--ease-accelerate` | `cubic-bezier(0.4, 0, 1, 1)` | Elements exiting (reserved) |
| `--duration-fast` | `150ms` | Micro-states (row hover, color change) |
| `--duration-base` | `250ms` | Icon transforms, border changes |
| `--duration-slow` | `350ms` | Card hover, shadow, button |
| `--duration-reveal` | `700ms` | Scroll-triggered fade-in-up |
| Shimmer | `550ms` | Button shimmer sweep only |
| Orb drift | `18s` / `22s` | Background orbs (ambient) |

---

## Reduced-Motion Policy

```css
@media (prefers-reduced-motion: reduce) {
  /* Disable */
  .hero::before, .hero::after { animation: none; opacity: 0; }
  .btn--primary               { animation: none; }
  .btn--primary::after        { display: none; }
  .hero__badge-dot            { animation: none; }
  .animate-fade-in            { animation: none; opacity: 1; transform: none; }

  /* Suppress transforms on hover — keep color/shadow feedback */
  .card:hover, .benefit-card:hover,
  .testimonial-card:hover, .step.card:hover { transform: none; }

  /* Suppress child transforms */
  .benefit-card:hover .benefit-icon,
  .step.card:hover .step__number,
  .trust-item:hover svg { transform: none; }

  /* Keep underline static */
  .nav__links a::after { transition: none; }
}
```

**Key principle:** Reduced-motion mode must never remove functional feedback (hover color, focus ring, accordion open state). Only decorative motion is suppressed.

---

## Testing Checklist

- [ ] CTA pulse stops on hover; shimmer runs only once per hover
- [ ] `prefers-reduced-motion: reduce` disables all animated properties
- [ ] FAQ `aria-expanded` syncs with `open` attribute
- [ ] All cards return to rest position on `mouseleave`
- [ ] Focus rings visible on all interactive elements without mouse
- [ ] Scroll-reveal fires only once per element (not on scroll-up)
- [ ] Live status dot is accessible as text via `aria-label`
- [ ] No cumulative layout shift (CLS) from animations
- [ ] Transitions feel smooth at 60fps (no jank on scroll-heavy section)

---

*Feeds into: Rule 116 (landing page), Rule 213 (sophisticated visual design), Rule 240 (a11y audit).*
