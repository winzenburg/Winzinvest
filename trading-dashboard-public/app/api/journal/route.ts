import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { isRemote, remoteGet, LOGS_DIR } from '../../../lib/data-access';

export const dynamic = 'force-dynamic';

interface JournalTrade {
  id: number | null;
  symbol: string;
  side: 'LONG' | 'SHORT';
  status: 'OPEN' | 'CLOSED';
  strategy: string;
  entry_timestamp: string;
  exit_timestamp: string | null;
  entry_price: number;
  exit_price: number | null;
  qty: number;
  pnl: number | null;
  pnl_pct: number | null;
  r_multiple: number | null;
  holding_days: number | null;
  exit_reason: string | null;
  reason: string | null;
  regime: string | null;
  conviction: number | null;
}

interface JournalSnapshot {
  generated_at: string;
  closed: JournalTrade[];
  open: JournalTrade[];
  total_closed: number;
  total_open: number;
}

export async function GET() {
  try {
    if (isRemote) {
      const data = await remoteGet<JournalSnapshot>('/api/journal');
      return NextResponse.json(data ?? { closed: [], open: [], total_closed: 0, total_open: 0 });
    }

    const journalPath = path.join(LOGS_DIR, 'trades_journal.json');

    if (!fs.existsSync(journalPath)) {
      return NextResponse.json(
        { closed: [], open: [], total_closed: 0, total_open: 0, error: 'Journal not yet generated — run dashboard_data_aggregator.py' },
        { status: 200 },
      );
    }

    const raw = fs.readFileSync(journalPath, 'utf-8');
    const data = JSON.parse(raw) as JournalSnapshot;
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error reading journal snapshot:', error);
    return NextResponse.json({ closed: [], open: [], total_closed: 0, total_open: 0 }, { status: 500 });
  }
}
