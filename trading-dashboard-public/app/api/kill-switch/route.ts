import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '../../../lib/auth';
import fs from 'fs';
import path from 'path';
import { isRemote, remoteGet, remotePost, TRADING_DIR, LOGS_DIR, readJson, appendJsonl } from '../../../lib/data-access';

export const dynamic = 'force-dynamic';

const KILL_SWITCH_PATH = path.join(TRADING_DIR, 'kill_switch.json');
const ACTION_LOG_PATH  = path.join(LOGS_DIR, 'user_action_audit.jsonl');

interface KillSwitchState {
  active: boolean;
  reason: string;
  timestamp: string;
  activated_by?: string;
  cleared_at?: string;
  cleared_by?: string;
}

function readState(): KillSwitchState {
  return readJson<KillSwitchState>(KILL_SWITCH_PATH)
    ?? { active: false, reason: '', timestamp: new Date().toISOString() };
}

export async function GET() {
  if (isRemote) {
    const data = await remoteGet<KillSwitchState>('/api/kill-switch');
    return NextResponse.json(data ?? { active: false, reason: '', timestamp: new Date().toISOString() });
  }
  return NextResponse.json(readState());
}

export async function POST(req: Request) {
  try {
    const session = await getServerSession(authOptions);
    if (!session) {
      return NextResponse.json({ ok: false, error: 'Unauthorized' }, { status: 401 });
    }

    const body = await req.json() as { active: boolean; reason?: string; pin?: string };
    const now  = new Date().toISOString();
    const user = session.user?.email ?? session.user?.name ?? 'unknown';

    if (body.active) {
      const expectedPin = process.env.KILL_SWITCH_PIN;
      if (expectedPin && body.pin !== expectedPin) {
        appendJsonl(ACTION_LOG_PATH, { timestamp: now, action: 'KILL_SWITCH_PIN_REJECTED', user, details: { reason: body.reason } });
        return NextResponse.json({ ok: false, error: 'Invalid PIN' }, { status: 403 });
      }
    }

    if (isRemote) {
      const endpoint = body.active ? '/api/kill-switch/activate' : '/api/kill-switch/clear';
      const data = await remotePost<{ ok: boolean; state: KillSwitchState }>(endpoint, { reason: body.reason, user });
      return NextResponse.json(data ?? { ok: false, error: 'Remote request failed' });
    }

    const current = readState();
    const next: KillSwitchState = {
      active:       body.active,
      reason:       body.reason ?? (body.active ? 'Manual trigger from Winzinvest UI' : 'Cleared from Winzinvest UI'),
      timestamp:    now,
      activated_by: body.active ? user : current.activated_by,
    };
    if (!body.active) { next.cleared_at = now; next.cleared_by = user; }

    fs.writeFileSync(KILL_SWITCH_PATH, JSON.stringify(next, null, 2));
    const action = body.active ? 'KILL_SWITCH_ACTIVATED' : 'KILL_SWITCH_CLEARED';
    appendJsonl(ACTION_LOG_PATH, { timestamp: now, action, user, details: { reason: next.reason, previous: current } });

    return NextResponse.json({ ok: true, state: next });
  } catch (err) {
    console.error('[kill-switch] POST error:', err);
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}
