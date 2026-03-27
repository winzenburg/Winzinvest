# Winzinvest Visual Identity Specification

## The Differentiation Strategy

The automated trading space is dominated by two visual extremes:
1. **The "Hype" Aesthetic (Trade Ideas, TastyTrade):** Dark mode, neon greens/reds, busy charts, aggressive typography. It feels like a casino.
2. **The "Tech" Aesthetic (Composer, QuantConnect):** Abstract shapes, standard SaaS sans-serifs, code-editor dark modes. It feels like a developer tool.

**Winzinvest's Whitespace:** The "Institutional Wealth" aesthetic. It should feel like a high-end family office or a Swiss private bank that happens to be fully automated. It must project calm, transparency, and rigorous risk management.

---

## 1. Typography System

We are using a three-font system to separate narrative (Serif), utility (Sans-serif), and data (Monospace).

### Font Pairings
- **Display & Narrative:** `Playfair Display` (Google Fonts) - Provides institutional gravitas and editorial authority.
- **UI & Body:** `Inter` (Google Fonts) - The gold standard for highly legible, dense SaaS interfaces.
- **Data & Metrics:** `JetBrains Mono` (Google Fonts) - A beautiful, highly readable monospace font for tickers, prices, and system logs.

### Typographic Hierarchy (Tailwind Scale)

| Role | Font Family | Weight | Size / Line Height | Tracking | Usage |
|---|---|---|---|---|---|
| **Display 1** | Playfair Display | SemiBold (600) | `text-6xl` (60px / 1.1) | `tracking-tight` | Hero headline only |
| **Display 2** | Playfair Display | Medium (500) | `text-5xl` (48px / 1.1) | `tracking-tight` | Section headers (e.g., "Pricing") |
| **Heading 1** | Playfair Display | Medium (500) | `text-4xl` (36px / 1.2) | `tracking-tight` | Feature pillar titles |
| **Heading 2** | Inter | SemiBold (600) | `text-2xl` (24px / 1.3) | `tracking-normal` | Card titles, modal headers |
| **Heading 3** | Inter | Medium (500) | `text-xl` (20px / 1.4) | `tracking-normal` | Sub-section headers |
| **Body Large** | Inter | Regular (400) | `text-lg` (18px / 1.6) | `tracking-normal` | Hero subheadline, intro paragraphs |
| **Body Base** | Inter | Regular (400) | `text-base` (16px / 1.6) | `tracking-normal` | Standard paragraph text |
| **Body Small** | Inter | Regular (400) | `text-sm` (14px / 1.5) | `tracking-normal` | Secondary text, tooltips |
| **Label / Eyebrow** | Inter | SemiBold (600) | `text-xs` (12px / 1.5) | `tracking-widest` | Uppercase badges, section kickers |
| **Data Large** | JetBrains Mono | Medium (500) | `text-3xl` (30px / 1.2) | `tracking-tight` | Portfolio balance, large metrics |
| **Data Base** | JetBrains Mono | Regular (400) | `text-sm` (14px / 1.5) | `tracking-normal` | Tickers, prices, table data |
| **Log Output** | JetBrains Mono | Regular (400) | `text-xs` (12px / 1.5) | `tracking-normal` | Audit logs, system status feeds |

---

## 2. Color System

The color system avoids pure black and pure white to reduce eye strain, and uses a sophisticated "Slate" and "Stone" neutral palette to feel premium rather than generic.

### Primary Brand Ramp (The "Trust" Blue)
Used for primary actions, active states, and brand moments. It is a deep, calm, maritime blue—not a bright "tech" blue.

- `primary-50`: `#F0F6FF` (Subtle backgrounds, hover states)
- `primary-100`: `#E0EDFF`
- `primary-200`: `#C0DAFF`
- `primary-300`: `#9BBEFF`
- `primary-400`: `#739BFF`
- `primary-500`: `#4F73FF`
- `primary-600`: `#334FFF` (Primary Buttons, Active Tabs)
- `primary-700`: `#2536E6` (Button Hover)
- `primary-800`: `#1E2DBF`
- `primary-900`: `#1D2A99` (Deep brand backgrounds)
- `primary-950`: `#151D7A`

### Secondary Brand Ramp (The "Institutional" Gold)
Used sparingly for premium accents, the "Founding Member" tier, and highlighting key differentiators.

- `secondary-50`: `#FFFAF0`
- `secondary-100`: `#FEF0C7`
- `secondary-200`: `#FDE08B`
- `secondary-300`: `#FBCB4B`
- `secondary-400`: `#F8B016`
- `secondary-500`: `#F09006` (Badges, Premium Accents)
- `secondary-600`: `#D56B03`
- `secondary-700`: `#B14A06`
- `secondary-800`: `#8F3A0B`
- `secondary-900`: `#75310E`

### Neutral Ramp (The "Canvas")
A mix of Slate (cool gray for text) and Stone (warm gray for backgrounds) to create a sophisticated, non-sterile environment.

- `bg-canvas`: `#FAFAFA` (Stone-50 equivalent - Main page background)
- `bg-surface`: `#FFFFFF` (Pure white - Cards, modals, dropdowns)
- `neutral-100`: `#F1F5F9` (Subtle borders, inactive backgrounds)
- `neutral-200`: `#E2E8F0` (Standard borders, dividers)
- `neutral-300`: `#CBD5E1` (Strong borders)
- `neutral-400`: `#94A3B8` (Disabled text, placeholder text)
- `neutral-500`: `#64748B` (Secondary icons, metadata)
- `neutral-600`: `#475569` (Secondary text, subtitles)
- `neutral-700`: `#334155` (Body text)
- `neutral-800`: `#1E293B` (Headings, primary text)
- `neutral-900`: `#0F172A` (Display text, high-contrast moments)

### Semantic Ramps (System Status & Trading)
In trading, colors mean money. They must be unambiguous but not visually aggressive.

#### Success / Profit / Active (Emerald)
- `success-50`: `#ECFDF5` (Profit row background)
- `success-100`: `#D1FAE5`
- `success-500`: `#10B981` (Status indicator dot)
- `success-600`: `#059669` (Profit text, "Active" badges)
- `success-700`: `#047857`

#### Warning / Drawdown / Choppy Regime (Amber)
- `warning-50`: `#FFFBEB` (Warning row background)
- `warning-100`: `#FEF3C7`
- `warning-500`: `#F59E0B` (Status indicator dot)
- `warning-600`: `#D97706` (Drawdown text, "Choppy" badges)
- `warning-700`: `#B45309`

#### Failure / Loss / Kill Switch (Rose)
- `danger-50`: `#FFF1F2` (Loss row background)
- `danger-100`: `#FFE4E6`
- `danger-500`: `#F43F5E` (Status indicator dot)
- `danger-600`: `#E11D48` (Loss text, "Halted" badges, Kill Switch button)
- `danger-700`: `#BE123C`

---

## 3. Implementation Notes for Tailwind

To implement this in `tailwind.config.ts`, extend the theme:

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        display: ['var(--font-playfair)', 'serif'],
        sans: ['var(--font-inter)', 'sans-serif'],
        mono: ['var(--font-jetbrains)', 'monospace'],
      },
      colors: {
        primary: {
          50: '#F0F6FF',
          100: '#E0EDFF',
          200: '#C0DAFF',
          300: '#9BBEFF',
          400: '#739BFF',
          500: '#4F73FF',
          600: '#334FFF',
          700: '#2536E6',
          800: '#1E2DBF',
          900: '#1D2A99',
          950: '#151D7A',
        },
        secondary: {
          50: '#FFFAF0',
          100: '#FEF0C7',
          200: '#FDE08B',
          300: '#FBCB4B',
          400: '#F8B016',
          500: '#F09006',
          600: '#D56B03',
          700: '#B14A06',
          800: '#8F3A0B',
          900: '#75310E',
        },
        // Map success to emerald, warning to amber, danger to rose
        success: { 50: '#ECFDF5', 100: '#D1FAE5', 500: '#10B981', 600: '#059669', 700: '#047857' },
        warning: { 50: '#FFFBEB', 100: '#FEF3C7', 500: '#F59E0B', 600: '#D97706', 700: '#B45309' },
        danger: { 50: '#FFF1F2', 100: '#FFE4E6', 500: '#F43F5E', 600: '#E11D48', 700: '#BE123C' },
        canvas: '#FAFAFA',
        surface: '#FFFFFF',
      },
    },
  },
  plugins: [],
};
export default config;
```

## 4. Imagery Direction & Midjourney Prompts

The imagery for Winzinvest must avoid the two biggest clichés in the trading space:
1. **No "Stressed Trader" photos:** No people looking intensely at six monitors with their head in their hands.
2. **No "Hacker Matrix" graphics:** No glowing green numbers falling down a black screen.

**The Winzinvest Imagery Concept: "Architectural Precision"**
The imagery should evoke the feeling of a highly engineered, physical machine or a pristine architectural space. It should feel like a Swiss vault, a high-end server room, or a precision-machined engine part. The visual metaphor is *structure, safety, and automation*.

### Midjourney Prompt 1: The "Risk Gates" Metaphor
*Use case: Hero background or the "Institutional Risk Management" section.*
> **Prompt:** `A macro photography shot of a precision-machined titanium vault mechanism, interlocking gears, clean architectural lighting, soft shadows, studio photography, minimalist, stone and slate color palette with subtle sky blue accents, depth of field, 8k, highly detailed, corporate wealth management aesthetic --ar 16:9 --style raw --v 6.0`

### Midjourney Prompt 2: The "Regime Detection" Metaphor
*Use case: The "Emotion is architecturally impossible" section.*
> **Prompt:** `Abstract architectural visualization of a calm, pristine data center, rows of white servers with subtle blue indicator lights, clean white and stone environment, soft diffused daylight coming from above, institutional, secure, quiet, minimalist, 8k, photorealistic --ar 16:9 --style raw --v 6.0`

### Midjourney Prompt 3: The "Options Yield" Metaphor
*Use case: The "Compound yield passively" section.*
> **Prompt:** `Abstract geometric composition of smooth white marble and frosted glass layers stacking perfectly on top of each other, soft studio lighting, subtle shadows, clean, minimalist, wealth management aesthetic, conveying compounding and structure, 8k, photorealistic --ar 16:9 --style raw --v 6.0`

### Midjourney Prompt 4: The "Kill Switch" Metaphor
*Use case: The security/auditability section.*
> **Prompt:** `A single, elegant brushed aluminum button on a pristine white surface, soft studio lighting, minimalist industrial design, high-end audio equipment aesthetic, secure, tactile, macro photography, 8k --ar 16:9 --style raw --v 6.0`

**Image Usage Rules:**
- Images should be used as subtle backgrounds or supporting visuals, never overpowering the UI or the copy.
- Apply a 10-20% white overlay to images if text needs to sit on top of them to maintain the light-mode aesthetic.
- Never use images that contain recognizable text or UI elements generated by AI (they always look fake). Use the actual Next.js dashboard screenshots for UI representation.
