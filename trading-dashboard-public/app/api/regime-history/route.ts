import { NextResponse } from 'next/server';
import { requireAuth } from '@/lib/auth';
import { LOGS_DIR } from '@/lib/data-access';
import path from 'path';
import fs from 'fs';

/**
 * Regime History API
 * 
 * Returns timeline of regime transitions for visualization.
 * Helps users understand market context shifts.
 */

export async function GET(req: Request) {
  const unauth = await requireAuth();
  if (unauth) return unauth;

  const { searchParams } = new URL(req.url);
  const daysParam = searchParams.get('days');
  const days = daysParam ? parseInt(daysParam, 10) : 90;

  try {
    const historyPath = path.join(LOGS_DIR, 'regime_history.jsonl');
    
    if (!fs.existsSync(historyPath)) {
      return NextResponse.json({ history: [] });
    }

    const text = fs.readFileSync(historyPath, 'utf-8');
    const lines = text.trim().split('\n').filter(l => l.trim());
    
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - days);
    
    const history: any[] = [];
    
    for (const line of lines) {
      try {
        const obj = JSON.parse(line);
        const entryDate = new Date(obj.timestamp);
        
        if (entryDate >= cutoffDate) {
          history.push({
            timestamp: obj.timestamp,
            regime: obj.regime || 'MIXED',
            note: obj.note || '',
          });
        }
      } catch {
        continue;
      }
    }

    // Sort by timestamp (oldest first for timeline display)
    history.sort((a, b) => a.timestamp.localeCompare(b.timestamp));

    return NextResponse.json({ history });
  } catch (error) {
    console.error('Error loading regime history:', error);
    return NextResponse.json(
      { error: 'Failed to load regime history' },
      { status: 500 }
    );
  }
}
