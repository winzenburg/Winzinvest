'use client';

import type { ReactNode } from 'react';

// Both SessionProvider and TradingModeProvider are intentionally omitted here.
//
// SessionProvider triggers /api/auth/session on every page load (including
// public ones), causing CLIENT_FETCH_ERROR when the secret or session is invalid.
//
// TradingModeProvider calls /api/trading-modes (an authenticated endpoint) on
// every mount. On public/login pages this fires a 401, which previously caused
// an infinite /login?callbackUrl=/login redirect loop.
//
// Both providers belong only in the authenticated section of the app.
// They are added in the layout for protected routes only (see app/(dashboard)/layout.tsx).
export default function Providers({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
