import { NextResponse } from 'next/server';

/**
 * Legacy performance endpoint — data now flows through /api/dashboard.
 * Returns a minimal stub to avoid breaking any clients still calling this route.
 */
export async function GET() {
  return NextResponse.json({
    _note: 'This endpoint is deprecated. Use /api/dashboard for live performance data.',
    lastUpdate: new Date().toISOString(),
  });
}
