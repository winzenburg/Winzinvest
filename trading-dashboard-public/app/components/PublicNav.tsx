'use client';

/**
 * Shared navigation for all public pages.
 *
 * Links: How It Works, Performance, Pricing
 * Secondary: Log In (text link for returning users)
 * Primary CTA: Join Waitlist → /landing#pricing
 */

import Link from 'next/link';

const NAV_LINKS = [
  { href: '/methodology', label: 'How It Works' },
  { href: '/performance', label: 'Performance' },
  { href: '/#pricing', label: 'Pricing' },
] as const;

export function PublicNav() {
  return (
    <nav className="sticky top-0 z-50 bg-white border-b border-stone-200 print:hidden">
      <div className="max-w-7xl mx-auto px-8 h-14 flex items-center justify-between">

        {/* Brand mark */}
        <div className="flex items-center gap-2.5">
          <span className="w-2 h-2 rounded-full bg-success-500 regime-dot" />
          <Link href="/" className="font-serif font-bold text-slate-900 tracking-tight text-base">
            Winz<span className="text-primary-600">invest</span>
          </Link>
        </div>

        {/* Nav links + actions */}
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
            className="text-sm text-stone-500 hover:text-slate-900 transition-colors"
          >
            Log In
          </Link>
          <a
            href="/#pricing"
            className="px-4 py-1.5 rounded-lg bg-primary-600 hover:bg-primary-700 text-white text-sm font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-primary-600 focus:ring-offset-2"
          >
            Join Waitlist
          </a>
        </div>
      </div>
    </nav>
  );
}
