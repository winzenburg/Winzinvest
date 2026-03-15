import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const tradingDir = path.join(process.cwd(), '..', 'trading');

    const recsPath     = path.join(tradingDir, 'logs', 'recommendations.json');
    const greeksPath   = path.join(tradingDir, 'logs', 'portfolio_greeks.json');
    const scenariosPath = path.join(tradingDir, 'logs', 'scenario_results.json');

    const read = (p: string) => fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf-8')) : null;

    return NextResponse.json({
      recommendations: read(recsPath),
      greeks:          read(greeksPath),
      scenarios:       read(scenariosPath),
    });
  } catch (err) {
    console.error('Intelligence API error:', err);
    return NextResponse.json({ recommendations: null, greeks: null, scenarios: null });
  }
}
