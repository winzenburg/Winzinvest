import { TradingModeProvider } from '../context/TradingModeContext';
import type { ReactNode } from 'react';

export default function AuditLayout({ children }: { children: ReactNode }) {
  return <TradingModeProvider>{children}</TradingModeProvider>;
}
