import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '../../../lib/auth';
import fs from 'fs';
import path from 'path';

export const dynamic = 'force-dynamic';

const KILL_SWITCH_PATH = path.join(process.cwd(), '..', 'trading', 'kill_switch.json');
const ACTION_LOG_PATH  = path.join(process.cwd(), '..', 'trading', 'logs', 'user_action_audit.jsonl');

interface KillSwitchState {
  active: boolean;
  reason: string;
  timestamp: string;
  activated_by?: string;
  cleared_at?: string;
  cleared_by?: string;
}

function readState(): KillSwitchState {
  try {
    if (fs.existsSync(KILL_SWITCH_PATH)) {
      return JSON.parse(fs.readFileSync(KILL_SWITCH_PATH, 'utf-8')) as KillSwitchState;
    }
  } catch {
    // fall through
  }
  return { active: false, reason: '', timestamp: new Date().toISOString() };
}

function logAction(entry: Record<string, unknown>) {
  try {
    fs.appendFileSync(ACTION_LOG_PATH, JSON.stringify(entry) + '\n', 'utf-8');
  } catch {
    // logging is best-effort — don't block kill switch
  }
}

export async function GET() {
  return NextResponse.json(readState());
}

export async function POST(req: Request) {
  try {
    // Require authenticated session
    const session = await getServerSession(authOptions);
    if (!session) {
      return NextResponse.json({ ok: false, error: 'Unauthorized' }, { status: 401 });
    }

    const body = await req.json() as { active: boolean; reason?: string; pin?: string };
    const now = new Date().toISOString();
    const user = session.user?.email ?? session.user?.name ?? 'unknown';

    // PIN required to ACTIVATE kill switch (not to clear it)
    if (body.active) {
      const expectedPin = process.env.KILL_SWITCH_PIN;
      if (expectedPin && body.pin !== expectedPin) {
        logAction({
          timestamp: now,
          action: 'KILL_SWITCH_PIN_REJECTED',
          user,
          details: { reason: body.reason },
        });
        return NextResponse.json({ ok: false, error: 'Invalid PIN' }, { status: 403 });
      }
    }

    const current = readState();
    const next: KillSwitchState = {
      active: body.active,
      reason: body.reason ?? (body.active
        ? 'Manual trigger from Mission Control UI'
        : 'Cleared from Mission Control UI'),
      timestamp: now,
      activated_by: body.active ? user : current.activated_by,
    };

    if (!body.active) {
      next.cleared_at = now;
      next.cleared_by = user;
    }

    fs.writeFileSync(KILL_SWITCH_PATH, JSON.stringify(next, null, 2));

    const action = body.active ? 'KILL_SWITCH_ACTIVATED' : 'KILL_SWITCH_CLEARED';
    logAction({ timestamp: now, action, user, details: { reason: next.reason, previous: current } });

    return NextResponse.json({ ok: true, state: next });
  } catch (err) {
    console.error('[kill-switch] POST error:', err);
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}
