import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const resultsPath = path.join(process.cwd(), '..', 'trading', 'logs', 'backtest_results.json');
    if (!fs.existsSync(resultsPath)) {
      return NextResponse.json(null);
    }
    const data = JSON.parse(fs.readFileSync(resultsPath, 'utf-8'));
    return NextResponse.json(data);
  } catch {
    return NextResponse.json(null);
  }
}
