'use client';

import type { ReactNode } from 'react';
import { SessionProvider } from 'next-auth/react';
import { TradingModeProvider } from '../context/TradingModeContext';

export default function InstitutionalLayout({ children }: { children: ReactNode }) {
  return (
    <SessionProvider>
      <TradingModeProvider>{children}</TradingModeProvider>
    </SessionProvider>
  );
}

