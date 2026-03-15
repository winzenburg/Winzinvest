import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export const dynamic = 'force-dynamic';

const PREFS_PATH = path.join(process.cwd(), '..', 'trading', 'config', 'notification_prefs.json');

export interface NotificationPrefs {
  channels: {
    telegram: boolean;
    email: boolean;
    browser_push: boolean;
  };
  thresholds: {
    daily_loss_pct: number;        // alert when daily loss exceeds this %
    drawdown_pct: number;          // alert when drawdown exceeds this %
    margin_utilization_pct: number;// alert when margin > this %
    data_staleness_minutes: number;// alert when data is this stale
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
  channels: {
    telegram: true,
    email: false,
    browser_push: false,
  },
  thresholds: {
    daily_loss_pct: 1.0,
    drawdown_pct: 5.0,
    margin_utilization_pct: 80,
    data_staleness_minutes: 10,
  },
  events: {
    trade_executed: false,
    kill_switch_activated: true,
    drawdown_circuit_breaker: true,
    assignment_risk: true,
    screener_complete: false,
    daily_summary: true,
  },
};

function readPrefs(): NotificationPrefs {
  try {
    if (fs.existsSync(PREFS_PATH)) {
      return JSON.parse(fs.readFileSync(PREFS_PATH, 'utf-8')) as NotificationPrefs;
    }
  } catch {
    // fall through
  }
  return DEFAULT_PREFS;
}

export async function GET() {
  return NextResponse.json(readPrefs());
}

export async function POST(req: Request) {
  try {
    const body = await req.json() as Partial<NotificationPrefs>;
    const current = readPrefs();
    const updated: NotificationPrefs = {
      channels: { ...current.channels, ...body.channels },
      thresholds: { ...current.thresholds, ...body.thresholds },
      events: { ...current.events, ...body.events },
    };
    fs.mkdirSync(path.dirname(PREFS_PATH), { recursive: true });
    fs.writeFileSync(PREFS_PATH, JSON.stringify(updated, null, 2));
    return NextResponse.json({ ok: true, prefs: updated });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}
