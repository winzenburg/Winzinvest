import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const hours = parseInt(searchParams.get('hours') || '24');
    const eventType = searchParams.get('type');

    const auditPath = path.join(
      process.cwd(),
      '..',
      'trading',
      'logs',
      'audit_trail.json'
    );

    if (!fs.existsSync(auditPath)) {
      return NextResponse.json([]);
    }

    const entries = JSON.parse(fs.readFileSync(auditPath, 'utf-8'));
    
    const cutoff = Date.now() - (hours * 60 * 60 * 1000);
    let filtered = entries.filter((entry: any) => {
      try {
        const ts = new Date(entry.timestamp).getTime();
        return ts >= cutoff;
      } catch {
        return false;
      }
    });

    if (eventType) {
      filtered = filtered.filter((entry: any) => entry.event_type === eventType);
    }

    const summary = {
      total: filtered.length,
      by_type: {} as Record<string, number>,
      gate_rejections: {
        total: 0,
        by_gate: {} as Record<string, number>,
        by_symbol: {} as Record<string, number>,
      },
    };

    filtered.forEach((entry: any) => {
      const type = entry.event_type || 'unknown';
      summary.by_type[type] = (summary.by_type[type] || 0) + 1;

      if (type === 'gate_rejection') {
        summary.gate_rejections.total++;
        const symbol = entry.symbol || 'UNKNOWN';
        summary.gate_rejections.by_symbol[symbol] = 
          (summary.gate_rejections.by_symbol[symbol] || 0) + 1;
        
        (entry.failed_gates || []).forEach((gate: string) => {
          summary.gate_rejections.by_gate[gate] = 
            (summary.gate_rejections.by_gate[gate] || 0) + 1;
        });
      }
    });

    return NextResponse.json({
      entries: filtered.slice(-100),
      summary,
    });
  } catch (error) {
    console.error('Error reading audit trail:', error);
    return NextResponse.json({ entries: [], summary: {} });
  }
}
