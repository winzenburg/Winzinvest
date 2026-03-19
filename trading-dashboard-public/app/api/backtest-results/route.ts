import { NextResponse } from 'next/server';
import { requireAuth } from '../../../lib/auth';
import path from 'path';
import { isRemote, remoteGet, LOGS_DIR, readJson } from '../../../lib/data-access';

export const dynamic = 'force-dynamic';

export async function GET() {
  const unauth = await requireAuth();
  if (unauth) return unauth;
  try {
    if (isRemote) {
      const data = await remoteGet('/api/backtest-results');
      return NextResponse.json(data ?? null);
    }
    const data = readJson(path.join(LOGS_DIR, 'backtest_results.json'));
    return NextResponse.json(data ?? null);
  } catch {
    return NextResponse.json(null);
  }
}
