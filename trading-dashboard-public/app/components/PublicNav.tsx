'use client';

/**
 * Shared navigation for all public pages.
 *
 * Links: How It Works, Performance, Pricing
 * Secondary: Log In (text link for returning users)
 * Primary CTA: Join Waitlist → /landing#pricing
 * Mobile: Hamburger menu with slide-in drawer
 */

import Link from 'next/link';
import { useState } from 'react';

const NAV_LINKS = [
  { href: '/methodology', label: 'How It Works' },
  { href: '/performance', label: 'Performance' },
  { href: '/#pricing', label: 'Pricing' },
] as const;

export function PublicNav() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

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

        {/* Desktop nav links + actions */}
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

        {/* Mobile hamburger button */}
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="sm:hidden p-2 rounded-lg hover:bg-stone-100 transition-colors focus:outline-none focus:ring-2 focus:ring-primary-600 focus:ring-offset-2"
          aria-label="Toggle menu"
          aria-expanded={mobileMenuOpen}
        >
          <svg
            className="w-6 h-6 text-slate-900"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            {mobileMenuOpen ? (
              <path d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>
      </div>

      {/* Mobile menu overlay */}
      {mobileMenuOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-slate-900/20 backdrop-blur-sm z-40 sm:hidden"
            onClick={() => setMobileMenuOpen(false)}
          />

          {/* Menu drawer */}
          <div className="fixed top-14 left-0 right-0 bg-white border-b border-stone-200 shadow-lg z-40 sm:hidden">
            <div className="px-8 py-6 space-y-4">
              {NAV_LINKS.map(({ href, label }) => (
                <Link
                  key={href}
                  href={href}
                  className="block text-base text-stone-700 hover:text-slate-900 transition-colors py-2"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  {label}
                </Link>
              ))}
              <Link
                href="/login"
                className="block text-base text-stone-600 hover:text-slate-900 transition-colors py-2"
                onClick={() => setMobileMenuOpen(false)}
              >
                Log In
              </Link>
              <div className="pt-4 border-t border-stone-200">
                <a
                  href="/#pricing"
                  className="block w-full px-4 py-2.5 rounded-lg bg-primary-600 hover:bg-primary-700 text-white text-sm font-semibold text-center transition-colors focus:outline-none focus:ring-2 focus:ring-primary-600 focus:ring-offset-2"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Join Waitlist
                </a>
              </div>
            </div>
          </div>
        </>
      )}
    </nav>
  );
}
