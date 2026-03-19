import { NextResponse } from 'next/server';
import { requireAuth } from '../../../lib/auth';
import path from 'path';
import { isRemote, remoteGet, LOGS_DIR, readJson } from '../../../lib/data-access';

export const dynamic = 'force-dynamic';

interface AuditEntry {
  timestamp: string;
  event_type: string;
  symbol?: string;
  failed_gates?: string[];
  [key: string]: unknown;
}

interface AuditSummary {
  total: number;
  by_type: Record<string, number>;
  gate_rejections: {
    total: number;
    by_gate: Record<string, number>;
    by_symbol: Record<string, number>;
  };
}

export async function GET(request: Request) {
  const unauth = await requireAuth();
  if (unauth) return unauth;
  try {
    const { searchParams } = new URL(request.url);
    const hours = parseInt(searchParams.get('hours') ?? '24', 10);
    const eventType = searchParams.get('type');

    if (isRemote) {
      const qs = new URLSearchParams({ hours: String(hours), ...(eventType ? { type: eventType } : {}) });
      const data = await remoteGet(`/api/audit?${qs}`);
      return NextResponse.json(data ?? { entries: [], summary: {} });
    }

    const auditPath = path.join(LOGS_DIR, 'audit_trail.json');
    const entries = readJson<AuditEntry[]>(auditPath);

    if (!entries) return NextResponse.json({ entries: [], summary: {} });

    const cutoff = Date.now() - hours * 60 * 60 * 1000;
    let filtered = entries.filter((entry: AuditEntry) => {
      try { return new Date(entry.timestamp).getTime() >= cutoff; }
      catch { return false; }
    });

    if (eventType) {
      filtered = filtered.filter((e: AuditEntry) => e.event_type === eventType);
    }

    const summary: AuditSummary = {
      total: filtered.length,
      by_type: {},
      gate_rejections: { total: 0, by_gate: {}, by_symbol: {} },
    };

    for (const entry of filtered) {
      const type = entry.event_type ?? 'unknown';
      summary.by_type[type] = (summary.by_type[type] ?? 0) + 1;

      if (type === 'gate_rejection') {
        summary.gate_rejections.total++;
        const sym = entry.symbol ?? 'UNKNOWN';
        summary.gate_rejections.by_symbol[sym] = (summary.gate_rejections.by_symbol[sym] ?? 0) + 1;
        for (const gate of entry.failed_gates ?? []) {
          summary.gate_rejections.by_gate[gate] = (summary.gate_rejections.by_gate[gate] ?? 0) + 1;
        }
      }
    }

    return NextResponse.json({ entries: filtered.slice(-100), summary });
  } catch (error) {
    console.error('Error reading audit trail:', error);
    return NextResponse.json({ entries: [], summary: {} });
  }
}
