# Mission Control Design System - Quick Reference

**For developers**: Copy-paste patterns for common UI elements.

---

## Typography

### Font Classes
```tsx
className="font-serif"  // Playfair Display - for headers, large numbers
className="font-sans"   // Inter - for body text, UI
className="font-mono"   // JetBrains Mono - for prices, codes, data
```

### Text Sizes
```tsx
className="text-xs"     // 12px - labels, captions
className="text-sm"     // 14px - body text, table data
className="text-base"   // 16px - default
className="text-2xl"    // 24px - small metrics
className="text-4xl"    // 36px - large metrics
className="text-5xl"    // 48px - page titles
```

### Hierarchy Pattern
```tsx
{/* Page title */}
<h1 className="font-serif text-5xl font-bold text-slate-900">
  Mission Control
</h1>

{/* Section header */}
<h2 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-6">
  Performance Metrics
</h2>

{/* Large metric */}
<div className="font-serif text-4xl font-bold text-green-600">
  +$2,340
</div>

{/* Body text */}
<p className="text-sm text-stone-600 leading-relaxed">
  Description text here
</p>
```

---

## Colors

### Semantic Colors
```tsx
// Profit/Loss
className="text-green-600"  // Profit, long positions
className="text-red-600"    // Loss, short positions

// Neutrals
className="text-slate-900"  // Primary text (headers, important data)
className="text-stone-600"  // Secondary text (body, labels)
className="text-stone-500"  // Tertiary text (captions, timestamps)
className="text-stone-400"  // Disabled, placeholder

// Backgrounds
className="bg-stone-50"     // Page background
className="bg-white"        // Card background
className="bg-stone-100"    // Subtle backgrounds

// Borders
className="border-stone-200"  // Primary borders
className="border-stone-100"  // Subtle borders (table rows)

// Accents
className="text-sky-600"      // Primary actions, info
className="text-orange-500"   // Warnings
className="text-blue-500"     // Info
```

### Badge Colors
```tsx
{/* Long/Buy */}
<span className="px-2 py-1 rounded text-xs font-semibold bg-green-100 text-green-700">
  LONG
</span>

{/* Short/Sell */}
<span className="px-2 py-1 rounded text-xs font-semibold bg-red-100 text-red-700">
  SHORT
</span>

{/* Status - Open */}
<span className="px-2 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-700">
  OPEN
</span>

{/* Status - Closed */}
<span className="px-2 py-1 rounded-full text-xs font-semibold bg-stone-100 text-stone-700">
  CLOSED
</span>
```

---

## Layout

### Container
```tsx
<div className="max-w-7xl mx-auto px-8 py-12">
  {/* Standard dashboard content */}
</div>

{/* Wider for institutional dashboard */}
<div className="max-w-[1600px] mx-auto px-8 py-12">
  {/* More data, needs more space */}
</div>
```

### Grid Layouts
```tsx
{/* 4-column metric grid */}
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
  {/* Metric cards */}
</div>

{/* 2-column layout */}
<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
  {/* Content cards */}
</div>
```

### Spacing
```tsx
className="mb-6"   // 24px - between related sections
className="mb-12"  // 48px - between major sections
className="mb-16"  // 64px - between page sections
className="gap-3"  // 12px - tight groups
className="gap-4"  // 16px - related items
className="gap-6"  // 24px - cards
```

---

## Components

### Metric Card
```tsx
<div className="bg-white border border-stone-200 rounded-xl p-6 hover:shadow-lg transition-shadow">
  <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">
    Daily P&L
  </div>
  <div className="font-serif text-4xl font-bold text-green-600">
    +$2,340
  </div>
  <div className="text-xs text-stone-500 mt-2">
    +0.12% • Updated 2m ago
  </div>
</div>
```

### Data Table
```tsx
<table className="w-full text-sm">
  <thead className="border-b border-stone-200">
    <tr>
      <th className="text-left py-3 px-2 font-semibold text-stone-600">Symbol</th>
      <th className="text-right py-3 px-2 font-semibold text-stone-600">Price</th>
      <th className="text-right py-3 px-2 font-semibold text-stone-600">P&L</th>
    </tr>
  </thead>
  <tbody>
    <tr className="border-b border-stone-100 hover:bg-stone-50">
      <td className="py-3 px-2 font-semibold text-slate-900">AAPL</td>
      <td className="py-3 px-2 text-right text-stone-600 font-mono">$178.20</td>
      <td className="py-3 px-2 text-right font-semibold text-green-600">+$637</td>
    </tr>
  </tbody>
</table>
```

### Progress Bar
```tsx
<div className="w-full h-3 bg-stone-100 rounded-full overflow-hidden">
  <div
    className="h-full bg-green-500 transition-all"
    style={{ width: `${percentage}%` }}
  />
</div>
```

### Alert Banner
```tsx
{/* Critical */}
<div className="rounded-xl p-4 bg-red-50 border border-red-200">
  <div className="flex items-start gap-3">
    <div className="text-red-600">⚠️</div>
    <div>
      <div className="font-semibold text-sm text-red-900">
        Daily loss limit exceeded
      </div>
      <div className="text-xs text-red-700 mt-1">
        Trading halted. Daily loss at 3.2% (limit: 3.0%)
      </div>
    </div>
  </div>
</div>

{/* Warning */}
<div className="rounded-xl p-4 bg-orange-50 border border-orange-200">
  <div className="flex items-start gap-3">
    <div className="text-orange-600">⚠️</div>
    <div>
      <div className="font-semibold text-sm text-orange-900">
        Approaching daily loss limit
      </div>
      <div className="text-xs text-orange-700 mt-1">
        Daily loss at 2.4% (limit: 3.0%)
      </div>
    </div>
  </div>
</div>

{/* Info */}
<div className="rounded-xl p-4 bg-blue-50 border border-blue-200">
  <div className="flex items-start gap-3">
    <div className="text-blue-600">ℹ️</div>
    <div>
      <div className="font-semibold text-sm text-blue-900">
        System update available
      </div>
      <div className="text-xs text-blue-700 mt-1">
        New version includes improved risk metrics
      </div>
    </div>
  </div>
</div>
```

### Button
```tsx
{/* Primary */}
<button className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-sm font-semibold transition-colors">
  View Details
</button>

{/* Secondary */}
<button className="px-4 py-2 bg-stone-100 hover:bg-stone-200 text-stone-700 rounded-lg text-sm font-semibold transition-colors">
  Cancel
</button>

{/* Danger */}
<button className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-semibold transition-colors">
  Stop Trading
</button>
```

### Link
```tsx
<Link
  href="/institutional"
  className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-sm font-semibold transition-colors"
>
  Institutional View
</Link>
```

### Loading State
```tsx
{loading && (
  <div className="min-h-screen bg-stone-50 flex items-center justify-center">
    <div className="text-stone-400">Loading...</div>
  </div>
)}
```

### Error State
```tsx
{error && (
  <div className="min-h-screen bg-stone-50 flex items-center justify-center">
    <div className="text-center">
      <div className="text-red-600 font-semibold mb-2">Error Loading Dashboard</div>
      <div className="text-stone-500 text-sm">{error}</div>
      <div className="text-stone-400 text-xs mt-4">
        Make sure dashboard_data_aggregator.py is running
      </div>
    </div>
  </div>
)}
```

### Empty State
```tsx
{items.length === 0 && (
  <div className="text-center text-stone-400 py-8">
    No trades yet
  </div>
)}
```

---

## Number Formatting

### Currency
```tsx
const formatCurrency = (value: number) => 
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);

// Usage
{formatCurrency(1936241)}  // "$1,936,241"
```

### Percentage
```tsx
const formatPercent = (value: number) => 
  `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;

// Usage
{formatPercent(2.45)}   // "+2.45%"
{formatPercent(-1.30)}  // "-1.30%"
```

### Large Numbers (with K/M suffix)
```tsx
const formatLarge = (value: number) => 
  value >= 1_000_000 ? `${(value / 1_000_000).toFixed(1)}M` :
  value >= 1_000 ? `${(value / 1_000).toFixed(1)}K` :
  value.toFixed(0);

// Usage
{formatLarge(1936241)}  // "1.9M"
{formatLarge(45000)}    // "45.0K"
{formatLarge(500)}      // "500"
```

---

## Accessibility

### Focus States
```tsx
className="focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2"
```

### Alt Text
```tsx
<img src="/chart.png" alt="Equity curve showing 12% growth over 30 days" />
```

### Semantic HTML
```tsx
<header>...</header>
<nav>...</nav>
<main>...</main>
<footer>...</footer>
<table>...</table>  // Not divs styled as tables
```

### Skip Links (for complex dashboards)
```tsx
<a 
  href="#main-content" 
  className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-white focus:border focus:border-stone-200"
>
  Skip to main content
</a>
```

---

## Responsive Design

### Breakpoints
```tsx
className="hidden md:block"           // Show on tablet+
className="block md:hidden"           // Show on mobile only
className="grid-cols-1 md:grid-cols-2 lg:grid-cols-4"  // Responsive grid
```

### Mobile-First Patterns
```tsx
{/* Stack on mobile, side-by-side on desktop */}
<div className="flex flex-col md:flex-row gap-4">
  <div>Left</div>
  <div>Right</div>
</div>

{/* Full width on mobile, constrained on desktop */}
<div className="w-full md:w-1/2 lg:w-1/3">
  Content
</div>
```

---

## Micro-Interactions

### Hover States
```tsx
className="hover:shadow-lg transition-shadow"        // Cards
className="hover:bg-stone-200 transition-colors"     // Buttons
className="hover:bg-stone-50"                        // Table rows
className="hover:text-stone-700"                     // Links
```

### Transitions
```tsx
className="transition-colors"   // 150ms color changes
className="transition-shadow"   // 150ms elevation changes
className="transition-all"      // 150ms multiple properties
```

---

## Common Patterns

### Page Structure
```tsx
export default function Page() {
  return (
    <div className="min-h-screen bg-stone-50">
      <div className="max-w-7xl mx-auto px-8 py-12">
        
        {/* Header */}
        <header className="mb-16 pb-8 border-b border-stone-200">
          <h1 className="font-serif text-5xl font-bold text-slate-900">
            Page Title
          </h1>
        </header>

        {/* Content */}
        <main>
          {/* Your content here */}
        </main>

        {/* Footer */}
        <footer className="mt-16 pt-8 border-t border-stone-200 text-center text-sm text-stone-400">
          <p>Mission Control Trading System</p>
          <p className="mt-2">
            Past performance does not guarantee future results.
          </p>
        </footer>
      </div>
    </div>
  );
}
```

### Metric Grid
```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
  <MetricCard label="Account Value" value="$1,936,241" color="text-sky-600" />
  <MetricCard label="Daily P&L" value="+$2,340" color="text-green-600" />
  <MetricCard label="Win Rate" value="62.1%" color="text-green-600" />
  <MetricCard label="Sharpe Ratio" value="2.14" color="text-sky-600" />
</div>
```

### Section Card
```tsx
<div className="bg-white border border-stone-200 rounded-xl p-8 mb-12">
  <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-6">
    Section Title
  </h2>
  {/* Content */}
</div>
```

### Data Table with Hover
```tsx
<div className="overflow-x-auto">
  <table className="w-full text-sm">
    <thead>
      <tr className="border-b border-stone-200">
        <th className="text-left py-3 px-2 font-semibold text-stone-600">Column</th>
      </tr>
    </thead>
    <tbody>
      <tr className="border-b border-stone-100 hover:bg-stone-50">
        <td className="py-3 px-2 text-stone-900">Data</td>
      </tr>
    </tbody>
  </table>
</div>
```

### Modal/Dialog
```tsx
<div 
  className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50"
  onClick={onClose}
>
  <div 
    className="bg-white rounded-xl max-w-4xl w-full max-h-[80vh] overflow-hidden"
    onClick={(e) => e.stopPropagation()}
  >
    {/* Header */}
    <div className="p-8 border-b border-stone-200 flex justify-between items-center">
      <h2 className="text-xl font-serif font-bold text-slate-900">
        Modal Title
      </h2>
      <button 
        onClick={onClose}
        className="text-stone-400 hover:text-stone-600 text-2xl"
      >
        ×
      </button>
    </div>
    
    {/* Content */}
    <div className="overflow-y-auto max-h-[60vh] p-8">
      {/* Content here */}
    </div>
  </div>
</div>
```

---

## TypeScript Patterns

### Type Guard
```tsx
interface Trade {
  symbol: string;
  pnl: number;
  timestamp: string;
}

const isTrade = (value: unknown): value is Trade => {
  return (
    typeof value === "object" &&
    value !== null &&
    "symbol" in value &&
    "pnl" in value &&
    "timestamp" in value &&
    typeof (value as Trade).symbol === "string" &&
    typeof (value as Trade).pnl === "number" &&
    typeof (value as Trade).timestamp === "string"
  );
};

// Usage
const trades = data.filter(isTrade);
```

### API Fetch with Error Handling
```tsx
const [data, setData] = useState<DashboardData | null>(null);
const [error, setError] = useState<string>("");
const [loading, setLoading] = useState(true);

useEffect(() => {
  const fetchData = async () => {
    try {
      const res = await fetch('/api/dashboard');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };
  
  fetchData();
  const interval = setInterval(fetchData, 30000);  // Refresh every 30s
  return () => clearInterval(interval);
}, []);
```

---

## Don'ts

❌ **Never:**
```tsx
// Pure black text
className="text-black"  // Use text-slate-900 instead

// Pure white background on colored text
className="bg-white text-blue-500"  // Poor contrast

// Console logs in production
console.log('Debug info');  // Remove before commit

// Inline styles for colors
style={{ color: '#16a34a' }}  // Use Tailwind classes

// Generic error messages
throw new Error('Error');  // Be specific: 'Failed to fetch dashboard data'

// Missing alt text
<img src="/chart.png" />  // Always include alt

// Centering data tables
className="text-center"  // Use text-left for scannability
```

✅ **Always:**
```tsx
// Semantic colors
className="text-slate-900"  // Primary text
className="text-green-600"  // Profit

// Type guards for external data
const isValid = (data: unknown): data is MyType => { ... }

// Helpful error messages
throw new Error('Failed to fetch dashboard data: API returned 404');

// Alt text
<img src="/chart.png" alt="Equity curve showing 12% growth" />

// Left-align data
className="text-left"  // For tables
```

---

## Testing Checklist

Before committing any UI change:

- [ ] Works on mobile (< 768px)
- [ ] Works on tablet (768-1024px)
- [ ] Works on desktop (> 1024px)
- [ ] All text meets WCAG AA contrast
- [ ] Focus states visible on all interactive elements
- [ ] No console errors in browser
- [ ] Loading states shown
- [ ] Error states handled
- [ ] Numbers format correctly
- [ ] Timestamps visible
- [ ] Alt text on images
- [ ] Semantic HTML used

---

## Quick Commands

```bash
# Start dev server
cd trading-dashboard-public && npm run dev

# Check for linter errors
npm run lint

# Build for production
npm run build

# Type check (if configured)
npm run type-check
```

---

## Resources

- **Full Design System**: `.cursor/rules/010-mission-control-design-system.mdc`
- **Quality Gates**: `.cursor/rules/020-mission-control-gates.mdc`
- **Agent System**: `AGENTS.md`
- **Tailwind v4 Docs**: https://tailwindcss.com/docs
- **WCAG 2.2 Guidelines**: https://www.w3.org/WAI/WCAG22/quickref/

---

## Need Help?

1. Check the full design system (`.cursor/rules/010-mission-control-design-system.mdc`)
2. Look at existing components for patterns
3. Test on multiple screen sizes
4. Run linter before committing
5. Ask if unsure (better than guessing)
