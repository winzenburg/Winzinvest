import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions, requireAuth } from '../../../lib/auth';
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

function clamp(n: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, n));
}

/** Merge only well-typed fields from body; ignore unknown keys. */
function mergeValidatedPrefs(current: NotificationPrefs, body: unknown): NotificationPrefs {
  if (body === null || typeof body !== 'object' || Array.isArray(body)) {
    return current;
  }
  const b = body as Record<string, unknown>;
  let channels = { ...current.channels };
  if (b.channels !== undefined) {
    if (typeof b.channels === 'object' && b.channels !== null && !Array.isArray(b.channels)) {
      const c = b.channels as Record<string, unknown>;
      if (typeof c.telegram === 'boolean') channels.telegram = c.telegram;
      if (typeof c.email === 'boolean') channels.email = c.email;
      if (typeof c.browser_push === 'boolean') channels.browser_push = c.browser_push;
    }
  }
  let thresholds = { ...current.thresholds };
  if (b.thresholds !== undefined) {
    if (typeof b.thresholds === 'object' && b.thresholds !== null && !Array.isArray(b.thresholds)) {
      const t = b.thresholds as Record<string, unknown>;
      if (typeof t.daily_loss_pct === 'number' && Number.isFinite(t.daily_loss_pct)) {
        thresholds.daily_loss_pct = clamp(t.daily_loss_pct, 0, 100);
      }
      if (typeof t.drawdown_pct === 'number' && Number.isFinite(t.drawdown_pct)) {
        thresholds.drawdown_pct = clamp(t.drawdown_pct, 0, 100);
      }
      if (typeof t.margin_utilization_pct === 'number' && Number.isFinite(t.margin_utilization_pct)) {
        thresholds.margin_utilization_pct = clamp(t.margin_utilization_pct, 0, 100);
      }
      if (typeof t.data_staleness_minutes === 'number' && Number.isFinite(t.data_staleness_minutes)) {
        thresholds.data_staleness_minutes = clamp(Math.round(t.data_staleness_minutes), 1, 10_080);
      }
    }
  }
  let events = { ...current.events };
  if (b.events !== undefined) {
    if (typeof b.events === 'object' && b.events !== null && !Array.isArray(b.events)) {
      const e = b.events as Record<string, unknown>;
      if (typeof e.trade_executed === 'boolean') events.trade_executed = e.trade_executed;
      if (typeof e.kill_switch_activated === 'boolean') events.kill_switch_activated = e.kill_switch_activated;
      if (typeof e.drawdown_circuit_breaker === 'boolean') events.drawdown_circuit_breaker = e.drawdown_circuit_breaker;
      if (typeof e.assignment_risk === 'boolean') events.assignment_risk = e.assignment_risk;
      if (typeof e.screener_complete === 'boolean') events.screener_complete = e.screener_complete;
      if (typeof e.daily_summary === 'boolean') events.daily_summary = e.daily_summary;
    }
  }
  return { channels, thresholds, events };
}

function readPrefs(): NotificationPrefs {
  try {
    if (fs.existsSync(PREFS_PATH)) {
      return JSON.parse(fs.readFileSync(PREFS_PATH, 'utf-8')) as NotificationPrefs;
    }
  } catch { /* fall through */ }
  return DEFAULT_PREFS;
}

export async function GET() {
  const unauth = await requireAuth();
  if (unauth) return unauth;
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

    const body: unknown = await req.json();

    if (isRemote) {
      const data = await remotePost<{ ok: boolean; prefs: NotificationPrefs }>(
        '/api/notification-prefs',
        body as Record<string, unknown>,
      );
      return NextResponse.json(data ?? { ok: false, error: 'Remote update failed' });
    }

    const current = readPrefs();
    const updated = mergeValidatedPrefs(current, body);
    fs.mkdirSync(path.dirname(PREFS_PATH), { recursive: true });
    fs.writeFileSync(PREFS_PATH, JSON.stringify(updated, null, 2));
    return NextResponse.json({ ok: true, prefs: updated });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}
