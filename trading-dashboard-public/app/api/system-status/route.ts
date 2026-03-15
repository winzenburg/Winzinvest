import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

const TRADING_HEALTH_URL =
  process.env.TRADING_HEALTH_URL || 'http://127.0.0.1:8000';
const HEALTH_PATH = '/health';
const TIMEOUT_MS = 5000;

export interface TradingHealthPayload {
  kill_switch_active?: boolean;
  last_signal?: Record<string, unknown> | null;
  portfolio_summary?: Record<string, unknown>;
  ib_connected?: boolean | null;
  open_orders_count?: number | null;
  positions_count?: number | null;
  ib_error?: string;
}

export interface SystemStatusResponse {
  trading: {
    reachable: boolean;
    url: string;
    error?: string;
    payload?: TradingHealthPayload;
  };
  checked_at: string;
}

/**
 * Proxies to the trading system health endpoint (e.g. agents.health_check on port 8000).
 * Returns reachability and payload for the System Monitor UI.
 */
export async function GET(): Promise<NextResponse<SystemStatusResponse>> {
  const url = `${TRADING_HEALTH_URL.replace(/\/$/, '')}${HEALTH_PATH}`;
  const checked_at = new Date().toISOString();

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);

    const res = await fetch(url, {
      signal: controller.signal,
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    });
    clearTimeout(timeout);

    if (!res.ok) {
      return NextResponse.json({
        trading: {
          reachable: false,
          url: TRADING_HEALTH_URL,
          error: `HTTP ${res.status}`,
        },
        checked_at,
      });
    }

    const payload = (await res.json()) as TradingHealthPayload;

    return NextResponse.json({
      trading: {
        reachable: true,
        url: TRADING_HEALTH_URL,
        payload,
      },
      checked_at,
    });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : 'Unknown error';
    const error =
      message === 'The operation was aborted.'
        ? 'Timeout'
        : message;

    return NextResponse.json({
      trading: {
        reachable: false,
        url: TRADING_HEALTH_URL,
        error,
      },
      checked_at,
    });
  }
}
