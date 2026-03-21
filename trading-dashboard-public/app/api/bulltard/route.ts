import { NextResponse } from 'next/server';
import path from 'path';
import { requireAuth } from '../../../lib/auth';
import { readJson, remoteGet, isRemote, LOGS_DIR } from '../../../lib/data-access';

export const dynamic = 'force-dynamic';

interface BulltardEntry {
  date: string;
  title: string;
  url: string;
  pulled_at: string;
  bias_score: number;
  bias_label: string;
  key_levels: string[];
  themes: string[];
  tickers_mentioned: string[];
  summary: string;
}

interface BulltardResponse {
  entries: BulltardEntry[];
  latest: BulltardEntry | null;
  available: boolean;
}

export async function GET() {
  const unauth = await requireAuth();
  if (unauth) return unauth;

  try {
    let entries: BulltardEntry[] = [];

    if (isRemote) {
      const data = await remoteGet<BulltardEntry[]>('/api/bulltard');
      entries = data ?? [];
    } else {
      const filePath = path.join(LOGS_DIR, 'bulltard_insights.json');
      entries = readJson<BulltardEntry[]>(filePath) ?? [];
    }

    const response: BulltardResponse = {
      entries: entries.slice(0, 14),  // last 2 weeks
      latest: entries[0] ?? null,
      available: entries.length > 0,
    };

    return NextResponse.json(response);
  } catch {
    return NextResponse.json({ entries: [], latest: null, available: false }, { status: 500 });
  }
}
