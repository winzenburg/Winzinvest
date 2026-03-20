import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions, requireAuth } from '../../../lib/auth';
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
    if (!session) {
      return NextResponse.json({ ok: false, error: 'Unauthorized' }, { status: 401 });
    }
    const user = session.user?.email ?? session.user?.name ?? 'unknown';
    const forwarded = req.headers.get('x-forwarded-for');
    const ip = forwarded ? forwarded.split(',')[0].trim() : 'unknown';
    const body: unknown = await req.json();
    const parsed = body as { action?: unknown; details?: unknown };

    if (!parsed.action || typeof parsed.action !== 'string') {
      return NextResponse.json({ ok: false, error: 'action is required' }, { status: 400 });
    }

    const entry: UserAction = {
      timestamp: new Date().toISOString(),
      action: parsed.action as string,
      details: (typeof parsed.details === 'object' && parsed.details !== null ? parsed.details : {}) as Record<string, unknown>,
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
    if (process.env.NODE_ENV === 'development') console.error('[user-actions] POST error:', err);
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
