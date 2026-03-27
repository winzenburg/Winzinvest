import { TradingModeProvider } from '../context/TradingModeContext';
import type { ReactNode } from 'react';

export default function JournalLayout({ children }: { children: ReactNode }) {
  return <TradingModeProvider>{children}</TradingModeProvider>;
}
