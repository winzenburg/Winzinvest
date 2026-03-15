import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export const dynamic = 'force-dynamic';

interface EquityPoint {
  date: string;
  equity: number;
  drawdown: number;
}

export async function GET() {
  try {
    const tradingDir = path.join(process.cwd(), '..', 'trading');
    const historyPath = path.join(tradingDir, 'logs', 'sod_equity_history.jsonl');
    const portfolioPath = path.join(tradingDir, 'portfolio.json');

    const points: EquityPoint[] = [];

    // Read historical SOD equity entries
    if (fs.existsSync(historyPath)) {
      const lines = fs.readFileSync(historyPath, 'utf-8').split('\n').filter(Boolean);
      for (const line of lines) {
        try {
          const obj = JSON.parse(line);
          if (obj.date && typeof obj.equity === 'number') {
            points.push({ date: obj.date, equity: obj.equity, drawdown: 0 });
          }
        } catch {
          // skip malformed lines
        }
      }
    }

    // Append today's current NLV from portfolio.json if newer than last history entry
    const today = new Date().toISOString().split('T')[0];
    const lastEntry = points[points.length - 1];
    try {
      if (fs.existsSync(portfolioPath)) {
        const portfolio = JSON.parse(fs.readFileSync(portfolioPath, 'utf-8'));
        const nlv = portfolio?.summary?.net_liquidation;
        if (typeof nlv === 'number' && nlv > 0) {
          if (!lastEntry || lastEntry.date !== today) {
            // Today not yet in history — add live intraday point
            points.push({ date: today, equity: nlv, drawdown: 0 });
          } else {
            // Update today's entry with the freshest NLV
            points[points.length - 1].equity = nlv;
          }
        }
      }
    } catch {
      // portfolio.json unreadable — use history as-is
    }

    // Sort chronologically
    points.sort((a, b) => a.date.localeCompare(b.date));

    // Compute drawdown from rolling peak
    let peak = 0;
    for (const pt of points) {
      if (pt.equity > peak) peak = pt.equity;
      pt.drawdown = peak > 0 ? -((peak - pt.equity) / peak) * 100 : 0;
    }

    return NextResponse.json({ points, count: points.length });
  } catch (error) {
    console.error('Error reading equity history:', error);
    return NextResponse.json({ points: [], count: 0 });
  }
}
