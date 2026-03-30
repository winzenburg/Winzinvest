import { NextResponse } from 'next/server';
import { requireAuth } from '@/lib/auth';
import { LOGS_DIR } from '@/lib/data-access';
import path from 'path';
import fs from 'fs';

/**
 * Trade History API
 * 
 * Returns closed trades with full context for Performance Explorer.
 * Enables self-service performance analysis by regime/strategy/sector.
 */

export async function GET() {
  const unauth = await requireAuth();
  if (unauth) return unauth;

  try {
    const dbPath = path.join(LOGS_DIR, 'trades.db');
    
    // For now, read from executions.json (closed trades)
    // TODO: Query trades.db when available
    const executionPath = path.join(LOGS_DIR, 'executions.json');
    
    if (!fs.existsSync(executionPath)) {
      return NextResponse.json({ trades: [] });
    }

    const text = fs.readFileSync(executionPath, 'utf-8');
    const lines = text.trim().split('\n').filter(l => l.trim());
    
    const trades: any[] = [];
    
    for (const line of lines) {
      try {
        const obj = JSON.parse(line);
        
        // Only include closed trades (exits)
        if (!obj.exit_price && !obj.realized_pnl) continue;
        
        const pnl = obj.realized_pnl || obj.pnl || 0;
        const returnPct = obj.return_pct || 0;
        
        trades.push({
          symbol: obj.symbol || '',
          strategy: obj.strategy || obj.source_script || 'unknown',
          sector: obj.sector || 'Unknown',
          regime: obj.regime || 'MIXED',
          entry_date: obj.timestamp || obj.entry_date || '',
          exit_date: obj.exit_timestamp || obj.exit_date || '',
          holding_days: obj.holding_days || 0,
          pnl,
          return_pct: returnPct,
          r_multiple: obj.r_multiple,
        });
      } catch {
        continue;
      }
    }

    return NextResponse.json({ trades });
  } catch (error) {
    console.error('Error loading trade history:', error);
    return NextResponse.json(
      { error: 'Failed to load trade history' },
      { status: 500 }
    );
  }
}
