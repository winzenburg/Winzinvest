import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export const dynamic = 'force-dynamic';

const TRADING_DIR = path.join(process.cwd(), '..', 'trading');
const LOGS_DIR = path.join(TRADING_DIR, 'logs');
const ENV_FILE = path.join(TRADING_DIR, '.env');
const ENV_PAPER_FILE = path.join(TRADING_DIR, '.env.paper');
const ACTIVE_MODE_FILE = path.join(TRADING_DIR, 'active_mode.json');

// Settings that differ between live and paper execution modes
const MODE_OVERRIDES: Record<string, Record<string, string>> = {
  live: {
    TRADING_MODE: 'live',
    IB_PORT: '4001',
  },
  paper: {
    TRADING_MODE: 'paper',
    IB_PORT: '4002',
  },
};

interface ModeInfo {
  available: boolean;
  lastUpdate: string | null;
  tradingMode: string | null;
  allocationPct: number | null;
}

function readModeInfo(mode: string): ModeInfo {
  const snapshotPath = path.join(LOGS_DIR, `dashboard_snapshot_${mode}.json`);
  if (!fs.existsSync(snapshotPath)) {
    return { available: false, lastUpdate: null, tradingMode: null, allocationPct: null };
  }
  try {
    const data = JSON.parse(fs.readFileSync(snapshotPath, 'utf-8'));
    return {
      available: true,
      lastUpdate: data.timestamp ?? null,
      tradingMode: data.trading_mode ?? mode,
      allocationPct: data.live_allocation_pct ?? null,
    };
  } catch {
    return { available: false, lastUpdate: null, tradingMode: null, allocationPct: null };
  }
}

function readActiveMode(): string | null {
  // Prefer active_mode.json (set by POST) then fall back to dashboard snapshot
  if (fs.existsSync(ACTIVE_MODE_FILE)) {
    try {
      const data = JSON.parse(fs.readFileSync(ACTIVE_MODE_FILE, 'utf-8'));
      if (data.mode === 'live' || data.mode === 'paper') return data.mode;
    } catch { /* ignore */ }
  }
  const defaultSnapshot = path.join(LOGS_DIR, 'dashboard_snapshot.json');
  if (fs.existsSync(defaultSnapshot)) {
    try {
      const data = JSON.parse(fs.readFileSync(defaultSnapshot, 'utf-8'));
      return data.trading_mode ?? null;
    } catch { /* ignore */ }
  }
  return null;
}

/** Rewrite trading/.env, merging in overrides for the target mode. */
function patchEnvFile(targetMode: 'live' | 'paper'): void {
  const overrides = MODE_OVERRIDES[targetMode];

  // Read extra defaults from .env.paper if switching to paper
  const extraDefaults: Record<string, string> = {};
  if (targetMode === 'paper' && fs.existsSync(ENV_PAPER_FILE)) {
    for (const line of fs.readFileSync(ENV_PAPER_FILE, 'utf-8').split('\n')) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) continue;
      const [k, ...rest] = trimmed.split('=');
      const key = k.trim();
      // Only carry over mode-specific keys from .env.paper
      if (key in overrides) extraDefaults[key] = rest.join('=').trim();
    }
  }

  const finalOverrides = { ...extraDefaults, ...overrides };

  if (!fs.existsSync(ENV_FILE)) {
    // Create a minimal .env if it doesn't exist
    const lines = Object.entries(finalOverrides).map(([k, v]) => `${k}=${v}`);
    fs.writeFileSync(ENV_FILE, lines.join('\n') + '\n', 'utf-8');
    return;
  }

  const existing = fs.readFileSync(ENV_FILE, 'utf-8').split('\n');
  const patched: string[] = [];
  const applied = new Set<string>();

  for (const line of existing) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) {
      patched.push(line);
      continue;
    }
    if (!trimmed.includes('=')) {
      patched.push(line);
      continue;
    }
    const key = trimmed.split('=')[0].trim();
    if (key in finalOverrides) {
      patched.push(`${key}=${finalOverrides[key]}`);
      applied.add(key);
    } else {
      patched.push(line);
    }
  }

  // Append any overrides not yet in the file
  for (const [key, val] of Object.entries(finalOverrides)) {
    if (!applied.has(key)) {
      patched.push(`${key}=${val}`);
    }
  }

  fs.writeFileSync(ENV_FILE, patched.join('\n'), 'utf-8');
}

// ── GET — return current mode availability ────────────────────────────────────

export async function GET() {
  const paper = readModeInfo('paper');
  const live = readModeInfo('live');
  const activeMode = readActiveMode();

  // Check if paper gateway is reachable so the UI can hint
  const IB_PAPER_PORT = parseInt(process.env.IB_PAPER_PORT ?? '4002', 10);
  const IB_HOST = process.env.IB_HOST ?? '127.0.0.1';
  let paperGatewayUp = false;
  try {
    const net = await import('net');
    await new Promise<void>((resolve, reject) => {
      const sock = net.createConnection({ host: IB_HOST, port: IB_PAPER_PORT });
      sock.setTimeout(1500);
      sock.on('connect', () => { sock.destroy(); resolve(); });
      sock.on('error', reject);
      sock.on('timeout', () => { sock.destroy(); reject(new Error('timeout')); });
    });
    paperGatewayUp = true;
  } catch { /* not reachable */ }

  return NextResponse.json({
    activeMode,
    paperGatewayUp,
    modes: { paper, live },
  });
}

// ── POST — switch active execution mode ──────────────────────────────────────

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  if (
    typeof body !== 'object' ||
    body === null ||
    !('mode' in body) ||
    (body as Record<string, unknown>).mode !== 'live' &&
    (body as Record<string, unknown>).mode !== 'paper'
  ) {
    return NextResponse.json(
      { error: 'Body must be { mode: "live" | "paper" }' },
      { status: 400 },
    );
  }

  const targetMode = (body as { mode: 'live' | 'paper' }).mode;

  try {
    // 1. Patch trading/.env with new mode values
    patchEnvFile(targetMode);

    // 2. Write active_mode.json as the authoritative mode record
    fs.writeFileSync(
      ACTIVE_MODE_FILE,
      JSON.stringify({ mode: targetMode, switched_at: new Date().toISOString() }, null, 2),
      'utf-8',
    );

    return NextResponse.json({ ok: true, mode: targetMode });
  } catch (err) {
    console.error('Failed to switch mode:', err);
    return NextResponse.json(
      { error: 'Failed to switch mode', detail: String(err) },
      { status: 500 },
    );
  }
}
