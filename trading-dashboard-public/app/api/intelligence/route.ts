import { NextResponse } from 'next/server';
import { requireAuth } from '../../../lib/auth';
import fs from 'fs';
import path from 'path';
import { isRemote, remoteGet, LOGS_DIR } from '../../../lib/data-access';

export const dynamic = 'force-dynamic';

interface IntelligencePayload {
  recommendations: unknown;
  greeks: unknown;
  scenarios: unknown;
}

export async function GET() {
  const unauth = await requireAuth();
  if (unauth) return unauth;
  try {
    if (isRemote) {
      const data = await remoteGet<IntelligencePayload>('/api/intelligence');
      return NextResponse.json(
        data ?? { recommendations: null, greeks: null, scenarios: null },
      );
    }

    const read = (p: string) =>
      fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf-8')) : null;

    return NextResponse.json({
      recommendations: read(path.join(LOGS_DIR, 'recommendations.json')),
      greeks:          read(path.join(LOGS_DIR, 'portfolio_greeks.json')),
      scenarios:       read(path.join(LOGS_DIR, 'scenario_results.json')),
    });
  } catch (err) {
    console.error('Intelligence API error:', err);
    return NextResponse.json({ recommendations: null, greeks: null, scenarios: null });
  }
}
