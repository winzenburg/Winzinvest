# Component Template

Use this template when creating new React components for the Mission Control dashboard.

---

## File: `ComponentName.tsx`

```tsx
'use client';

import { useState, useEffect } from 'react';

interface ComponentNameProps {
  // Define props with clear types
  label: string;
  value: number;
  onChange?: (value: number) => void;
}

/**
 * ComponentName - Brief description of what this component does
 * 
 * @param label - Description of label prop
 * @param value - Description of value prop
 * @param onChange - Optional callback when value changes
 */
export default function ComponentName({ 
  label, 
  value, 
  onChange 
}: ComponentNameProps) {
  const [localState, setLocalState] = useState<number>(value);

  useEffect(() => {
    // Side effects here
    setLocalState(value);
  }, [value]);

  const handleChange = (newValue: number) => {
    setLocalState(newValue);
    onChange?.(newValue);
  };

  return (
    <div className="bg-white border border-stone-200 rounded-xl p-6 hover:shadow-lg transition-shadow">
      {/* Section header */}
      <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-4">
        {label}
      </h2>
      
      {/* Main content */}
      <div className="font-serif text-4xl font-bold text-slate-900">
        {localState}
      </div>
      
      {/* Optional subtitle or actions */}
      <div className="text-xs text-stone-500 mt-2">
        Additional context
      </div>
    </div>
  );
}
```

---

## Design System Checklist

Before committing, verify:

- [ ] **Typography**: Uses `font-serif` for numbers, `font-sans` for text
- [ ] **Colors**: Uses stone palette (`text-stone-500`, `text-slate-900`)
- [ ] **Spacing**: Uses design system scale (`p-6`, `mb-4`, `mt-2`)
- [ ] **Layout**: Uses `bg-white border border-stone-200 rounded-xl`
- [ ] **Hover**: Includes `hover:shadow-lg transition-shadow` if interactive
- [ ] **Accessibility**: Semantic HTML, proper heading hierarchy
- [ ] **Type Safety**: All props typed, no `any`
- [ ] **Error Handling**: Handles missing/invalid data gracefully
- [ ] **Responsive**: Works on mobile/tablet/desktop

---

## Common Patterns

### Metric Card
```tsx
<div className="bg-white border border-stone-200 rounded-xl p-6">
  <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">
    {label}
  </div>
  <div className="font-serif text-4xl font-bold text-green-600">
    {value}
  </div>
</div>
```

### Data Table
```tsx
<table className="w-full text-sm">
  <thead className="border-b border-stone-200">
    <tr>
      <th className="text-left py-3 px-2 font-semibold text-stone-600">Header</th>
    </tr>
  </thead>
  <tbody>
    <tr className="border-b border-stone-100 hover:bg-stone-50">
      <td className="py-3 px-2 text-stone-900">Data</td>
    </tr>
  </tbody>
</table>
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
  <div className="rounded-xl p-4 bg-red-50 border border-red-200">
    <div className="font-semibold text-sm text-red-900">{error}</div>
  </div>
)}
```

---

## Testing

```tsx
// Manual testing checklist
// 1. Test with valid data
// 2. Test with missing data
// 3. Test with invalid data
// 4. Test on mobile (< 768px)
// 5. Test on tablet (768-1024px)
// 6. Test on desktop (> 1024px)
// 7. Test keyboard navigation
// 8. Test with screen reader (if applicable)
```

---

## See Also

- `DESIGN_QUICK_REFERENCE.md` - Copy-paste patterns
- `.cursor/rules/010-mission-control-design-system.mdc` - Full design system
- `.cursor/rules/020-mission-control-gates.mdc` - Quality gates
