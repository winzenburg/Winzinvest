'use client';

import { SessionProvider } from 'next-auth/react';
import { TradingModeProvider } from './context/TradingModeContext';
import type { ReactNode } from 'react';

export default function Providers({ children }: { children: ReactNode }) {
  return (
    <SessionProvider>
      <TradingModeProvider>{children}</TradingModeProvider>
    </SessionProvider>
  );
}
