import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export const dynamic = 'force-dynamic';

const VALID_MODES = ['paper', 'live'] as const;
type TradingMode = (typeof VALID_MODES)[number];

function isValidMode(mode: string): mode is TradingMode {
  return VALID_MODES.includes(mode as TradingMode);
}

export async function GET(request: NextRequest) {
  try {
    const logsDir = path.join(process.cwd(), '..', 'trading', 'logs');
    const requestedMode = request.nextUrl.searchParams.get('mode');

    if (requestedMode && isValidMode(requestedMode)) {
      const modeSnapshot = path.join(logsDir, `dashboard_snapshot_${requestedMode}.json`);
      if (fs.existsSync(modeSnapshot)) {
        const data = JSON.parse(fs.readFileSync(modeSnapshot, 'utf-8'));
        return NextResponse.json(data);
      }
      return NextResponse.json(
        { error: `No ${requestedMode} snapshot found. The system may not have run in ${requestedMode} mode yet.` },
        { status: 404 }
      );
    }

    const defaultSnapshot = path.join(logsDir, 'dashboard_snapshot.json');
    if (!fs.existsSync(defaultSnapshot)) {
      return NextResponse.json(
        { error: 'Dashboard snapshot not found. Run dashboard_data_aggregator.py first.' },
        { status: 404 }
      );
    }

    const data = JSON.parse(fs.readFileSync(defaultSnapshot, 'utf-8'));
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error reading dashboard snapshot:', error);
    return NextResponse.json(
      { error: 'Failed to load dashboard data' },
      { status: 500 }
    );
  }
}
