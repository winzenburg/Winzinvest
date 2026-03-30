import { NextResponse } from 'next/server';
import { requireAuth } from '@/lib/auth';
import { readJson, LOGS_DIR } from '@/lib/data-access';
import path from 'path';

/**
 * Daily Narrative API
 * 
 * Returns auto-generated summary of today's system activity.
 * Primary engagement driver: satisfies curiosity without action.
 */

export async function GET() {
  const unauth = await requireAuth();
  if (unauth) return unauth;

  try {
    const narrativePath = path.join(LOGS_DIR, 'daily_narrative.json');
    const data = readJson(narrativePath);

    if (!data) {
      // Fallback: generate basic narrative from snapshot
      const snapshotPath = path.join(LOGS_DIR, 'dashboard_snapshot.json');
      const snapshot = readJson(snapshotPath);

      if (!snapshot) {
        return NextResponse.json({
          date: new Date().toISOString().split('T')[0],
          summary: 'No activity data available. System is monitoring.',
          regime: 'MIXED',
          decisions: [],
          stats: { screened: 0, executed: 0, blocked: 0 },
        });
      }

      // Build basic narrative from snapshot data
      const regime = (snapshot as any).performance?.regime || 'MIXED';
      const positionCount = (snapshot as any).positions?.list?.length || 0;

      return NextResponse.json({
        date: new Date().toISOString().split('T')[0],
        summary: `System is managing ${positionCount} positions. Market regime: ${regime}.`,
        regime,
        decisions: [],
        stats: { screened: 0, executed: 0, blocked: 0 },
      });
    }

    return NextResponse.json(data);
  } catch (error) {
    console.error('Error loading daily narrative:', error);
    return NextResponse.json(
      { error: 'Failed to load daily narrative' },
      { status: 500 }
    );
  }
}
