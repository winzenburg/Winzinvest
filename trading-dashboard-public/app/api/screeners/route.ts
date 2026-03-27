import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { requireAuth } from '../../../lib/auth';
import { TRADING_DIR } from '../../../lib/data-access';

export const dynamic = 'force-dynamic';

/** Shape expected by dashboard screener consumers */
interface ScreenerPayload {
  longs: unknown[];
  shorts: unknown[];
  updatedAt: string | null;
}

function readJsonSafe(filePath: string): unknown | null {
  try {
    if (!fs.existsSync(filePath)) return null;
    return JSON.parse(fs.readFileSync(filePath, 'utf-8')) as unknown;
  } catch {
    return null;
  }
}

/**
 * Aggregates long/short screener candidates from trading workspace JSON exports.
 * Files may be absent on a fresh machine — returns empty arrays (not 404).
 */
export async function GET() {
  const unauth = await requireAuth();
  if (unauth) return unauth;

  const longs: unknown[] = [];
  const shorts: unknown[] = [];
  let updatedAt: string | null = null;

  const candidatesPath = path.join(TRADING_DIR, 'screener_candidates.json');
  const raw = readJsonSafe(candidatesPath);
  if (raw && typeof raw === 'object' && raw !== null) {
    const o = raw as Record<string, unknown>;
    const pick = (k: string): unknown[] => {
      const v = o[k];
      return Array.isArray(v) ? v : [];
    };
    longs.push(...pick('tier_1'), ...pick('tier_2'), ...pick('long_candidates'));
    shorts.push(...pick('short_candidates'), ...pick('shorts'), ...pick('tier_3'));
    const ts = o.updated_at ?? o.timestamp ?? o.generated_at;
    if (typeof ts === 'string') updatedAt = ts;
  }

  const wlLong = readJsonSafe(path.join(TRADING_DIR, 'watchlist_longs.json')) as Record<
    string,
    unknown
  > | null;
  if (wlLong?.long_candidates && Array.isArray(wlLong.long_candidates)) {
    longs.push(...wlLong.long_candidates);
  }

  const payload: ScreenerPayload = {
    longs,
    shorts,
    updatedAt,
  };

  return NextResponse.json(payload);
}
