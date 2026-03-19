import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '../../../lib/auth';
import fs from 'fs';
import path from 'path';
import { isRemote, remoteGet, remotePost, TRADING_DIR } from '../../../lib/data-access';

export const dynamic = 'force-dynamic';

const PREFS_PATH = path.join(TRADING_DIR, 'config', 'notification_prefs.json');

export interface NotificationPrefs {
  channels: {
    telegram: boolean;
    email: boolean;
    browser_push: boolean;
  };
  thresholds: {
    daily_loss_pct: number;
    drawdown_pct: number;
    margin_utilization_pct: number;
    data_staleness_minutes: number;
  };
  events: {
    trade_executed: boolean;
    kill_switch_activated: boolean;
    drawdown_circuit_breaker: boolean;
    assignment_risk: boolean;
    screener_complete: boolean;
    daily_summary: boolean;
  };
}

const DEFAULT_PREFS: NotificationPrefs = {
  channels:   { telegram: true, email: false, browser_push: false },
  thresholds: { daily_loss_pct: 1.0, drawdown_pct: 5.0, margin_utilization_pct: 80, data_staleness_minutes: 10 },
  events:     { trade_executed: false, kill_switch_activated: true, drawdown_circuit_breaker: true, assignment_risk: true, screener_complete: false, daily_summary: true },
};

function readPrefs(): NotificationPrefs {
  try {
    if (fs.existsSync(PREFS_PATH)) {
      return JSON.parse(fs.readFileSync(PREFS_PATH, 'utf-8')) as NotificationPrefs;
    }
  } catch { /* fall through */ }
  return DEFAULT_PREFS;
}

export async function GET() {
  if (isRemote) {
    const data = await remoteGet<NotificationPrefs>('/api/notification-prefs');
    return NextResponse.json(data ?? DEFAULT_PREFS);
  }
  return NextResponse.json(readPrefs());
}

export async function POST(req: Request) {
  try {
    const session = await getServerSession(authOptions);
    if (!session) {
      return NextResponse.json({ ok: false, error: 'Unauthorized' }, { status: 401 });
    }

    const body = await req.json() as Partial<NotificationPrefs>;

    if (isRemote) {
      const data = await remotePost<{ ok: boolean; prefs: NotificationPrefs }>('/api/notification-prefs', body as Record<string, unknown>);
      return NextResponse.json(data ?? { ok: false, error: 'Remote update failed' });
    }

    const current = readPrefs();
    const updated: NotificationPrefs = {
      channels:   { ...current.channels,   ...body.channels },
      thresholds: { ...current.thresholds, ...body.thresholds },
      events:     { ...current.events,     ...body.events },
    };
    fs.mkdirSync(path.dirname(PREFS_PATH), { recursive: true });
    fs.writeFileSync(PREFS_PATH, JSON.stringify(updated, null, 2));
    return NextResponse.json({ ok: true, prefs: updated });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}
