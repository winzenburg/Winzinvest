import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions, requireAuth } from '../../../lib/auth';
import fs from 'fs';
import path from 'path';
import { isRemote, remoteGet, remotePost, TRADING_DIR, LOGS_DIR, readJson } from '../../../lib/data-access';

export const dynamic = 'force-dynamic';

const ENV_FILE        = path.join(TRADING_DIR, '.env');
const ENV_PAPER_FILE  = path.join(TRADING_DIR, '.env.paper');
const ACTIVE_MODE_FILE = path.join(TRADING_DIR, 'active_mode.json');

const MODE_OVERRIDES: Record<string, Record<string, string>> = {
  live:  { TRADING_MODE: 'live',  IB_PORT: '4001' },
  paper: { TRADING_MODE: 'paper', IB_PORT: '4002' },
};

interface ModeInfo {
  available: boolean;
  lastUpdate: string | null;
  tradingMode: string | null;
  allocationPct: number | null;
}

interface ModeData {
  timestamp?: string;
  trading_mode?: string;
  live_allocation_pct?: number;
}

function readModeInfo(mode: string): ModeInfo {
  const snapshotPath = path.join(LOGS_DIR, `dashboard_snapshot_${mode}.json`);
  const data = readJson<ModeData>(snapshotPath);
  if (!data) return { available: false, lastUpdate: null, tradingMode: null, allocationPct: null };
  return {
    available:     true,
    lastUpdate:    data.timestamp ?? null,
    tradingMode:   data.trading_mode ?? mode,
    allocationPct: data.live_allocation_pct ?? null,
  };
}

function readActiveMode(): string | null {
  const saved = readJson<{ mode: string }>(ACTIVE_MODE_FILE);
  if (saved?.mode === 'live' || saved?.mode === 'paper') return saved.mode;
  const snapshot = readJson<ModeData>(path.join(LOGS_DIR, 'dashboard_snapshot.json'));
  return snapshot?.trading_mode ?? null;
}

function patchEnvFile(targetMode: 'live' | 'paper'): void {
  const overrides = MODE_OVERRIDES[targetMode];
  const extraDefaults: Record<string, string> = {};
  if (targetMode === 'paper' && fs.existsSync(ENV_PAPER_FILE)) {
    for (const line of fs.readFileSync(ENV_PAPER_FILE, 'utf-8').split('\n')) {
      const t = line.trim();
      if (!t || t.startsWith('#') || !t.includes('=')) continue;
      const [k, ...rest] = t.split('=');
      const key = k.trim();
      if (key in overrides) extraDefaults[key] = rest.join('=').trim();
    }
  }
  const final = { ...extraDefaults, ...overrides };
  if (!fs.existsSync(ENV_FILE)) {
    fs.writeFileSync(ENV_FILE, Object.entries(final).map(([k, v]) => `${k}=${v}`).join('\n') + '\n');
    return;
  }
  const lines = fs.readFileSync(ENV_FILE, 'utf-8').split('\n');
  const applied = new Set<string>();
  const patched = lines.map(line => {
    const t = line.trim();
    if (!t || t.startsWith('#') || !t.includes('=')) return line;
    const key = t.split('=')[0].trim();
    if (key in final) { applied.add(key); return `${key}=${final[key]}`; }
    return line;
  });
  for (const [key, val] of Object.entries(final)) {
    if (!applied.has(key)) patched.push(`${key}=${val}`);
  }
  fs.writeFileSync(ENV_FILE, patched.join('\n'));
}

// ── GET ───────────────────────────────────────────────────────────────────────

export async function GET() {
  const unauth = await requireAuth();
  if (unauth) return unauth;
  if (isRemote) {
    const data = await remoteGet('/api/trading-modes');
    return NextResponse.json(data ?? { activeMode: 'paper', paperGatewayUp: false, modes: { paper: { available: false }, live: { available: false } } });
  }

  const paper = readModeInfo('paper');
  const live  = readModeInfo('live');
  const activeMode = readActiveMode();

  const IB_PAPER_PORT = parseInt(process.env.IB_PAPER_PORT ?? '4002', 10);
  const IB_HOST = process.env.IB_HOST ?? '127.0.0.1';
  let paperGatewayUp = false;
  try {
    const net = await import('net');
    await new Promise<void>((resolve, reject) => {
      const sock = net.default.createConnection({ host: IB_HOST, port: IB_PAPER_PORT });
      sock.setTimeout(1500);
      sock.on('connect', () => { sock.destroy(); resolve(); });
      sock.on('error', reject);
      sock.on('timeout', () => { sock.destroy(); reject(new Error('timeout')); });
    });
    paperGatewayUp = true;
  } catch { /* Gateway down or unreachable — expected when offline */ }

  return NextResponse.json({ activeMode, paperGatewayUp, modes: { paper, live } });
}

// ── POST ──────────────────────────────────────────────────────────────────────

export async function POST(request: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  let body: unknown;
  try { body = await request.json(); }
  catch { return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 }); }

  if (
    typeof body !== 'object' || body === null || !('mode' in body) ||
    ((body as Record<string, unknown>).mode !== 'live' && (body as Record<string, unknown>).mode !== 'paper')
  ) {
    return NextResponse.json({ error: 'Body must be { mode: "live" | "paper" }' }, { status: 400 });
  }

  const targetMode = (body as { mode: 'live' | 'paper' }).mode;

  if (isRemote) {
    const data = await remotePost('/api/trading-modes', { mode: targetMode });
    return NextResponse.json(data ?? { ok: true, mode: targetMode });
  }

  try {
    patchEnvFile(targetMode);
    fs.writeFileSync(ACTIVE_MODE_FILE, JSON.stringify({ mode: targetMode, switched_at: new Date().toISOString() }, null, 2));
    return NextResponse.json({ ok: true, mode: targetMode });
  } catch (err) {
    if (process.env.NODE_ENV === 'development') console.error('Failed to switch mode:', err);
    return NextResponse.json({ error: 'Failed to switch mode', detail: String(err) }, { status: 500 });
  }
}
