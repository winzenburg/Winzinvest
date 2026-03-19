import { NextResponse } from 'next/server';
import { requireAuth } from '../../../lib/auth';

/**
 * Legacy performance endpoint — data now flows through /api/dashboard.
 * Returns a minimal stub to avoid breaking any clients still calling this route.
 */
export async function GET() {
  const unauth = await requireAuth();
  if (unauth) return unauth;
  return NextResponse.json({
    _note: 'This endpoint is deprecated. Use /api/dashboard for live performance data.',
    lastUpdate: new Date().toISOString(),
  });
}
