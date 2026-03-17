'use client';

/**
 * Shared navigation for all public pages (landing, overview, methodology, research, performance).
 * Keeps nav items consistent so they do not disappear when navigating between pages.
 */

import Link from 'next/link';

const NAV_LINKS = [
  { href: '/overview', label: 'Overview' },
  { href: '/methodology', label: 'Methodology' },
  { href: '/research', label: 'Research' },
  { href: '/performance', label: 'Performance' },
  { href: '/landing#pricing', label: 'Pricing' },
] as const;

export function PublicNav() {
  return (
    <nav className="sticky top-0 z-50 bg-white border-b border-stone-200 print:hidden">
      <div className="max-w-7xl mx-auto px-8 h-14 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-green-500" />
          <Link href="/landing" className="font-serif font-bold text-slate-900 tracking-tight">
            Winz<span className="text-sky-600">invest</span>
          </Link>
        </div>
        <div className="hidden sm:flex items-center gap-8">
          {NAV_LINKS.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className="text-sm text-stone-600 hover:text-slate-900 transition-colors"
            >
              {label}
            </Link>
          ))}
          <Link
            href="/login"
            className="px-4 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-700 text-white text-sm font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-sky-600 focus:ring-offset-2"
          >
            Dashboard
          </Link>
        </div>
      </div>
    </nav>
  );
}
