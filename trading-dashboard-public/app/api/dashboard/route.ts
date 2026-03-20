import { NextRequest, NextResponse } from 'next/server';
import { requireAuth } from '../../../lib/auth';
import { getSnapshot } from '../../../lib/data-access';

export const dynamic = 'force-dynamic';

const VALID_MODES = ['paper', 'live'] as const;
type TradingMode = (typeof VALID_MODES)[number];

function isValidMode(mode: string): mode is TradingMode {
  return VALID_MODES.includes(mode as TradingMode);
}

export async function GET(request: NextRequest) {
  const unauth = await requireAuth();
  if (unauth) return unauth;
  try {
    const requestedMode = request.nextUrl.searchParams.get('mode');
    const mode = requestedMode && isValidMode(requestedMode) ? requestedMode : undefined;
    const data = await getSnapshot(mode);

    if (!data) {
      return NextResponse.json(
        { error: 'No dashboard snapshot found. Make sure dashboard_data_aggregator.py is running.' },
        { status: 404 },
      );
    }

    return NextResponse.json(data);
  } catch (error) {
    if (process.env.NODE_ENV === 'development') console.error('Error reading dashboard snapshot:', error);
    return NextResponse.json({ error: 'Failed to load dashboard data' }, { status: 500 });
  }
}
