'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { signOut } from 'next-auth/react';
import type { ReactNode } from 'react';
import KillSwitchButton from './KillSwitchButton';
import ModeToggle from './ModeToggle';

const NAV: { href: string; label: string; match: (path: string) => boolean }[] = [
  {
    href: '/dashboard',
    label: 'Dashboard',
    match: (p) => p === '/dashboard' || p.startsWith('/dashboard/'),
  },
  { href: '/journal', label: 'Journal', match: (p) => p.startsWith('/journal') },
  { href: '/audit', label: 'Audit', match: (p) => p.startsWith('/audit') },
];

export default function DashboardNav({
  onOpenNotificationPrefs,
  statusSlot,
  extraLinks,
}: {
  onOpenNotificationPrefs?: () => void;
  /** Optional row below controls (e.g. system health on the main dashboard). */
  statusSlot?: ReactNode;
  /** Extra text links after Audit (e.g. How It Works). */
  extraLinks?: ReactNode;
}) {
  const pathname = usePathname() ?? '';

  return (
    <header className="mb-6 pb-5 border-b border-slate-200">
      <div className="flex flex-col gap-4 lg:flex-row lg:flex-wrap lg:items-center lg:justify-between">
        <div className="flex items-center gap-4 min-w-0">
          <Link
            href="/dashboard"
            className="font-serif text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 shrink-0 focus:outline-none focus:ring-2 focus:ring-primary-600 focus:ring-offset-2 rounded"
          >
            Winz<span className="text-primary-600">invest</span>
          </Link>
          <nav className="flex flex-wrap items-center gap-2" aria-label="Primary">
            {NAV.map(({ href, label, match }) => {
              const active = match(pathname);
              return (
                <Link
                  key={href}
                  href={href}
                  aria-current={active ? 'page' : undefined}
                  className={`px-3 py-1.5 text-sm font-medium rounded-lg border transition-all focus:outline-none focus:ring-2 focus:ring-primary-600 focus:ring-offset-1 ${
                    active
                      ? 'border-primary-600 bg-primary-50 text-primary-800 shadow-sm'
                      : 'border-slate-200 text-slate-600 hover:bg-white hover:border-slate-300 hover:shadow-sm'
                  }`}
                >
                  {label}
                </Link>
              );
            })}
            {extraLinks}
          </nav>
        </div>

        <div className="flex flex-col items-stretch sm:items-end gap-2">
          <div className="flex items-start justify-end gap-2 flex-wrap">
            {onOpenNotificationPrefs && (
              <button
                type="button"
                onClick={onOpenNotificationPrefs}
                className="p-1.5 rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50 transition-colors focus:outline-none focus:ring-2 focus:ring-primary-600 mt-0.5"
                aria-label="Notification preferences"
                title="Notification preferences"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
                  />
                </svg>
              </button>
            )}
            <div className="mt-0.5">
              <KillSwitchButton />
            </div>
            <ModeToggle />
            <button
              type="button"
              onClick={() => signOut({ callbackUrl: '/' })}
              className="p-1.5 rounded-lg border border-slate-200 text-slate-500 hover:bg-red-50 hover:border-red-200 hover:text-red-600 transition-colors focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-1 mt-0.5"
              aria-label="Sign out"
              title="Sign out"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
            </button>
          </div>
          {statusSlot}
        </div>
      </div>
    </header>
  );
}
