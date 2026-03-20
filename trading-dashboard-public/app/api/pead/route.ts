import { NextResponse } from 'next/server';
import path from 'path';
import { requireAuth } from '../../../lib/auth';
import { readJson, TRADING_DIR, isRemote, remoteGet } from '../../../lib/data-access';

interface PeadCandidate {
  symbol: string;
  earnings_date: string;
  gap_pct: number;
  drift_pct: number;
  days_since_earnings: number;
  volume_ratio: number;
  rsi: number | null;
  pead_score: number;
  price: number;
  sma50: number;
  suggested_action: string;
}

interface PeadData {
  generated_at: string;
  total_scanned: number;
  candidates: PeadCandidate[];
}

export async function GET() {
  const unauth = await requireAuth();
  if (unauth) return unauth;

  if (isRemote) {
    const data = await remoteGet<PeadData>('/api/pead');
    if (data) return NextResponse.json(data);
    return NextResponse.json(
      { error: 'PEAD data not available from remote backend', candidates: [] },
      { status: 503 },
    );
  }

  const filePath = path.join(TRADING_DIR, 'watchlist_pead.json');
  const data = readJson<PeadData>(filePath);

  if (!data) {
    return NextResponse.json({
      generated_at: new Date().toISOString(),
      note: 'PEAD watchlist not yet generated. Run pead_screener.py to produce it.',
      candidates: [],
    });
  }

  return NextResponse.json(data);
}
