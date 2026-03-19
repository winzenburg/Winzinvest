import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '../../../lib/auth';
import path from 'path';
import { isRemote, remoteGet, remotePost, LOGS_DIR, readJson, appendJsonl } from '../../../lib/data-access';

export const dynamic = 'force-dynamic';

const LOG_PATH = path.join(LOGS_DIR, 'user_action_audit.jsonl');

interface UserAction {
  timestamp: string;
  action: string;
  details: Record<string, unknown>;
  user: string;
  ip: string;
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

    if (isRemote) {
      await remotePost('/api/user-actions', entry as unknown as Record<string, unknown>);
    } else {
      appendJsonl(LOG_PATH, entry as unknown as Record<string, unknown>);
    }

    return NextResponse.json({ ok: true });
  } catch (err) {
    console.error('[user-actions] POST error:', err);
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}

export async function GET() {
  const unauth = await requireAuth();
  if (unauth) return unauth;
  try {
    if (isRemote) {
      const data = await remoteGet<{ actions: UserAction[] }>('/api/user-actions');
      return NextResponse.json(data ?? { actions: [] });
    }

    const raw = readJson<UserAction[]>(LOG_PATH);
    if (!raw) {
      // JSONL file — readJson won't parse it; read line by line
      const fs = await import('fs');
      if (!fs.default.existsSync(LOG_PATH)) return NextResponse.json({ actions: [] });
      const lines = fs.default.readFileSync(LOG_PATH, 'utf-8').trim().split('\n').filter(Boolean);
      const actions = lines
        .map((line: string) => { try { return JSON.parse(line) as UserAction; } catch { return null; } })
        .filter((a): a is UserAction => a !== null)
        .reverse()
        .slice(0, 500);
      return NextResponse.json({ actions });
    }

    return NextResponse.json({ actions: (raw as UserAction[]).reverse().slice(0, 500) });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}
