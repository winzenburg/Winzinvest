import { NextResponse } from 'next/server';
import { requireAuth } from '../../../lib/auth';
import fs from 'fs';
import path from 'path';
import { isRemote, remoteGet, LOGS_DIR, TRADING_DIR } from '../../../lib/data-access';

export const dynamic = 'force-dynamic';

interface EquityPoint {
  date: string;
  equity: number;
  drawdown: number;
}

interface RemoteHistory {
  points?: EquityPoint[];
  count?: number;
}

function computeDrawdown(points: EquityPoint[]): EquityPoint[] {
  let peak = 0;
  return points.map(pt => {
    if (pt.equity > peak) peak = pt.equity;
    return { ...pt, drawdown: peak > 0 ? -((peak - pt.equity) / peak) * 100 : 0 };
  });
}

export async function GET() {
  const unauth = await requireAuth();
  if (unauth) return unauth;
  try {
    if (isRemote) {
      const data = await remoteGet<RemoteHistory>('/api/equity-history');
      return NextResponse.json(data ?? { points: [], count: 0 });
    }

    const historyPath   = path.join(LOGS_DIR, 'sod_equity_history.jsonl');
    const portfolioPath = path.join(TRADING_DIR, 'portfolio.json');
    const points: EquityPoint[] = [];

    if (fs.existsSync(historyPath)) {
      for (const line of fs.readFileSync(historyPath, 'utf-8').split('\n').filter(Boolean)) {
        try {
          const obj = JSON.parse(line) as Record<string, unknown>;
          if (obj.date && typeof obj.equity === 'number') {
            points.push({ date: obj.date as string, equity: obj.equity, drawdown: 0 });
          }
        } catch { /* skip malformed */ }
      }
    }

    const today = new Date().toISOString().split('T')[0];
    try {
      if (fs.existsSync(portfolioPath)) {
        const portfolio = JSON.parse(fs.readFileSync(portfolioPath, 'utf-8')) as Record<string, Record<string, unknown>>;
        const nlv = portfolio?.summary?.net_liquidation;
        if (typeof nlv === 'number' && nlv > 0) {
          const last = points[points.length - 1];
          if (!last || last.date !== today) {
            points.push({ date: today, equity: nlv, drawdown: 0 });
          } else {
            points[points.length - 1].equity = nlv;
          }
        }
      }
    } catch { /* portfolio.json unreadable */ }

    points.sort((a, b) => a.date.localeCompare(b.date));
    const withDrawdown = computeDrawdown(points);
    return NextResponse.json({ points: withDrawdown, count: withDrawdown.length });
  } catch (error) {
    if (process.env.NODE_ENV === 'development') console.error('Error reading equity history:', error);
    return NextResponse.json({ points: [], count: 0 });
  }
}
