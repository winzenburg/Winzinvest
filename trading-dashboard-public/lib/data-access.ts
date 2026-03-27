/**
 * Dual-mode data access layer.
 *
 * LOCAL  (TRADING_API_URL not set) → reads files directly via Node.js fs.
 * REMOTE (TRADING_API_URL is set)  → fetches from Python backend over HTTP.
 *
 * Local behaviour is 100% unchanged. The remote path activates only when
 * deployed to Cloudflare Pages and the env var is configured.
 */

import fs from 'fs';
import path from 'path';

export const TRADING_API_URL = process.env.TRADING_API_URL?.replace(/\/$/, '');
export const TRADING_DIR     = path.join(process.cwd(), '..', 'trading');
export const LOGS_DIR        = path.join(TRADING_DIR, 'logs');

/** True when the app is connected to a remote Python backend */
export const isRemote = Boolean(TRADING_API_URL);

// ── Remote fetch ──────────────────────────────────────────────────────────────

/** GET from Python backend; returns parsed JSON or null on any error */
export async function remoteGet<T>(endpoint: string): Promise<T | null> {
  if (!TRADING_API_URL) return null;
  try {
    const res = await fetch(`${TRADING_API_URL}${endpoint}`, {
      headers: { 'x-api-key': process.env.TRADING_API_KEY ?? '' },
      cache: 'no-store',
    });
    if (!res.ok) return null;
    return res.json() as Promise<T>;
  } catch {
    return null;
  }
}

/** POST to Python backend; returns parsed JSON or null on any error */
export async function remotePost<T>(
  endpoint: string,
  body: Record<string, unknown>,
): Promise<T | null> {
  if (!TRADING_API_URL) return null;
  try {
    const res = await fetch(`${TRADING_API_URL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': process.env.TRADING_API_KEY ?? '',
      },
      body: JSON.stringify(body),
    });
    if (!res.ok) return null;
    return res.json() as Promise<T>;
  } catch {
    return null;
  }
}

// ── Local helpers ─────────────────────────────────────────────────────────────

/** Read and parse a local JSON file; returns null if missing or unreadable */
export function readJson<T>(filePath: string): T | null {
  try {
    if (fs.existsSync(filePath)) {
      return JSON.parse(fs.readFileSync(filePath, 'utf-8')) as T;
    }
  } catch {
    // fall through
  }
  return null;
}

/** Append a line to a JSONL file (best-effort, never throws) */
export function appendJsonl(filePath: string, entry: Record<string, unknown>): void {
  try {
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.appendFileSync(filePath, JSON.stringify(entry) + '\n', 'utf-8');
  } catch {
    // logging is best-effort
  }
}

// ── Snapshot ──────────────────────────────────────────────────────────────────

/** Read the dashboard snapshot (local files or remote Python endpoint).
 *
 * When no explicit mode is passed, tries the active mode's snapshot first
 * (e.g. dashboard_snapshot_live.json) to avoid the race where a paper
 * aggregator overwrites the unqualified file after the live one.
 */
export async function getSnapshot(mode?: string): Promise<unknown> {
  if (isRemote) {
    const qs = mode ? `?mode=${mode}` : '';
    return remoteGet(`/api/snapshot${qs}`);
  }
  const candidates: string[] = [];
  if (mode) {
    candidates.push(path.join(LOGS_DIR, `dashboard_snapshot_${mode}.json`));
  } else {
    // Prefer the active trading mode's dedicated file over the generic one
    const activeMode = process.env.TRADING_MODE || 'live';
    candidates.push(path.join(LOGS_DIR, `dashboard_snapshot_${activeMode}.json`));
  }
  candidates.push(path.join(LOGS_DIR, 'dashboard_snapshot.json'));
  const found = candidates.find(p => fs.existsSync(p));
  return found ? readJson(found) : null;
}
