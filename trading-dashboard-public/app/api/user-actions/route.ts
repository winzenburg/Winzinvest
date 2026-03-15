import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '../../../lib/auth';
import fs from 'fs';
import path from 'path';

export const dynamic = 'force-dynamic';

const LOG_PATH = path.join(process.cwd(), '..', 'trading', 'logs', 'user_action_audit.jsonl');

interface UserAction {
  timestamp: string;
  action: string;
  details: Record<string, unknown>;
  user: string;
  ip: string;
}

function appendAction(entry: UserAction) {
  const line = JSON.stringify(entry) + '\n';
  fs.appendFileSync(LOG_PATH, line, 'utf-8');
}

export async function POST(req: Request) {
  try {
    const session = await getServerSession(authOptions);
    const user = session?.user?.email ?? session?.user?.name ?? 'anonymous';

    const forwarded = req.headers.get('x-forwarded-for');
    const ip = forwarded ? forwarded.split(',')[0].trim() : 'unknown';

    const body = await req.json() as { action: string; details?: Record<string, unknown> };

    if (!body.action || typeof body.action !== 'string') {
      return NextResponse.json({ ok: false, error: 'action is required' }, { status: 400 });
    }

    const entry: UserAction = {
      timestamp: new Date().toISOString(),
      action: body.action,
      details: body.details ?? {},
      user,
      ip,
    };

    appendAction(entry);

    return NextResponse.json({ ok: true });
  } catch (err) {
    console.error('[user-actions] POST error:', err);
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}

export async function GET() {
  try {
    if (!fs.existsSync(LOG_PATH)) {
      return NextResponse.json({ actions: [] });
    }

    const raw = fs.readFileSync(LOG_PATH, 'utf-8');
    const lines = raw.trim().split('\n').filter(Boolean);

    const actions = lines
      .map(line => {
        try { return JSON.parse(line) as UserAction; }
        catch { return null; }
      })
      .filter((a): a is UserAction => a !== null)
      .reverse() // newest first
      .slice(0, 500);

    return NextResponse.json({ actions });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}
