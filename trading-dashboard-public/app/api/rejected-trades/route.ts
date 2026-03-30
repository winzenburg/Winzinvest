import { NextResponse } from 'next/server';
import { requireAuth } from '@/lib/auth';
import { readJson, LOGS_DIR } from '@/lib/data-access';
import path from 'path';
import fs from 'fs';

/**
 * Rejected Trades API
 * 
 * Returns signals the system blocked with reasons.
 * Builds trust by showing risk gates are working.
 */

export async function GET(req: Request) {
  const unauth = await requireAuth();
  if (unauth) return unauth;

  const { searchParams } = new URL(req.url);
  const period = searchParams.get('period') || 'today';  // today | week | month

  try {
    const executionPath = path.join(LOGS_DIR, 'executions.json');
    
    if (!fs.existsSync(executionPath)) {
      return NextResponse.json({
        period,
        totalScreened: 0,
        totalExecuted: 0,
        totalBlocked: 0,
        reasons: [],
        recentSignals: [],
      });
    }

    // Parse JSONL execution log
    const text = fs.readFileSync(executionPath, 'utf-8');
    const lines = text.trim().split('\n').filter(l => l.trim());
    
    // Determine date range
    const now = new Date();
    let startDate: Date;
    
    if (period === 'today') {
      startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    } else if (period === 'week') {
      startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    } else {
      startDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
    }

    const records: any[] = [];
    for (const line of lines) {
      try {
        const obj = JSON.parse(line);
        const ts = obj.timestamp || obj.timestamp_iso || '';
        const recDate = new Date(ts);
        if (recDate >= startDate) {
          records.push(obj);
        }
      } catch {
        continue;
      }
    }

    // Categorize
    const executed = records.filter(r => 
      (r.status || '').toUpperCase() === 'FILLED' || 
      (r.status || '').toUpperCase() === 'FILL'
    );
    
    const blocked = records.filter(r =>
      ['REJECTED', 'BLOCKED', 'SKIPPED'].includes((r.status || '').toUpperCase())
    );

    const totalScreened = executed.length + blocked.length;

    // Count rejection reasons
    const reasonCounts: Record<string, number> = {};
    for (const rec of blocked) {
      let reason = rec.reason || 'Unknown';
      
      // Normalize
      const lower = reason.toLowerCase();
      if (lower.includes('conviction')) {
        reason = 'Low Conviction';
      } else if (lower.includes('sector')) {
        reason = 'Sector Concentration';
      } else if (lower.includes('regime')) {
        reason = 'Regime Gate';
      } else if (lower.includes('budget') || lower.includes('daily')) {
        reason = 'Daily Trade Budget';
      } else if (lower.includes('loss')) {
        reason = 'Daily Loss Limit';
      }
      
      reasonCounts[reason] = (reasonCounts[reason] || 0) + 1;
    }

    const total = Object.values(reasonCounts).reduce((a, b) => a + b, 0);
    const reasons = Object.entries(reasonCounts)
      .map(([reason, count]) => ({
        reason,
        count,
        pct: total > 0 ? (count / total) * 100 : 0,
      }))
      .sort((a, b) => b.count - a.count);

    // Recent rejected signals
    const recentSignals = blocked
      .slice(-10)
      .reverse()
      .map(r => ({
        symbol: r.symbol || '',
        reason: r.reason || 'Risk gate triggered',
        conviction: r.conviction_score,
        rejectedAt: r.timestamp || r.timestamp_iso || new Date().toISOString(),
      }));

    return NextResponse.json({
      period: period === 'today' ? 'Today' : period === 'week' ? 'This Week' : 'This Month',
      totalScreened,
      totalExecuted: executed.length,
      totalBlocked: blocked.length,
      reasons,
      recentSignals,
    });
  } catch (error) {
    console.error('Error loading rejected trades:', error);
    return NextResponse.json(
      { error: 'Failed to load rejected trades' },
      { status: 500 }
    );
  }
}
