'use client';

import { useCallback, useEffect, useState } from 'react';
import Tooltip from './Tooltip';

interface SystemHealth {
  status: string;
  issues: string[];
  data_freshness_minutes: number;
}

interface TradingHealthPayload {
  kill_switch_active?: boolean;
  last_signal?: Record<string, unknown> | null;
  portfolio_summary?: Record<string, unknown>;
  ib_connected?: boolean | null;
  open_orders_count?: number | null;
  positions_count?: number | null;
  ib_error?: string;
}

interface SystemStatusResponse {
  trading: {
    reachable: boolean;
    url: string;
    error?: string;
    payload?: TradingHealthPayload;
  };
  checked_at: string;
}

interface SystemMonitorProps {
  /** From dashboard snapshot: indicates aggregator health and data age */
  systemHealth: SystemHealth;
  /** True when the dashboard successfully loaded (Dashboard API is up) */
  dashboardUp: boolean;
}

function StatusRow({
  label,
  up,
  detail,
  tooltip,
}: {
  label: string;
  up: boolean;
  detail?: string;
  tooltip?: string;
}) {
  const labelEl = (
    <span className="text-sm font-medium text-stone-600">{label}</span>
  );
  return (
    <div className="flex items-center justify-between py-2 first:pt-0 last:pb-0 border-b border-stone-100 last:border-b-0">
      <div className="flex items-center gap-2">
        <span
          className={`inline-block w-2.5 h-2.5 rounded-full shrink-0 ${
            up ? 'bg-green-500' : 'bg-red-500'
          }`}
          aria-hidden
        />
        {tooltip ? (
          <Tooltip text={tooltip} placement="above">
            {labelEl}
          </Tooltip>
        ) : (
          labelEl
        )}
      </div>
      {detail != null && (
        <span className="text-xs text-slate-600 font-mono">{detail}</span>
      )}
    </div>
  );
}

export default function SystemMonitor({
  systemHealth,
  dashboardUp,
}: SystemMonitorProps) {
  const [trading, setTrading] = useState<SystemStatusResponse['trading'] | null>(
    null
  );
  const [checkedAt, setCheckedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchSystemStatus = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/system-status', { cache: 'no-store' });
      const data: SystemStatusResponse = await res.json();
      setTrading(data.trading);
      setCheckedAt(data.checked_at);
    } catch {
      setTrading({
        reachable: false,
        url: '',
        error: 'Request failed',
      });
      setCheckedAt(new Date().toISOString());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSystemStatus();
    const interval = setInterval(fetchSystemStatus, 30000);
    return () => clearInterval(interval);
  }, [fetchSystemStatus]);

  const dataFreshness =
    systemHealth.data_freshness_minutes <= 0
      ? 'Live'
      : `${systemHealth.data_freshness_minutes}m old`;
  const aggregatorUp =
    systemHealth.status === 'healthy' || systemHealth.status === 'warning';

  return (
    <section
      id="system-monitor"
      className="scroll-mt-6 bg-white border border-slate-200 card-elevated rounded-xl p-6 mb-8"
      aria-labelledby="system-monitor-heading"
    >
      <div className="flex items-center justify-between mb-4">
        <h2
          id="system-monitor-heading"
          className="text-xs font-semibold uppercase tracking-wider text-slate-600"
        >
          System Monitor
        </h2>
        <div className="flex items-center gap-3">
          {checkedAt && (
            <span className="text-xs text-slate-500" aria-live="polite">
              Checked {new Date(checkedAt).toLocaleTimeString()}
            </span>
          )}
          <button
            type="button"
            onClick={fetchSystemStatus}
            disabled={loading}
            className="text-xs font-semibold text-sky-600 hover:text-sky-700 disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:ring-offset-2 rounded px-2 py-1"
          >
            {loading ? 'Checking…' : 'Refresh'}
          </button>
        </div>
      </div>

      <div className="space-y-0">
        <StatusRow
          label="Dashboard API"
          up={dashboardUp}
          detail={dashboardUp ? 'Up' : 'Down'}
          tooltip="Next.js API serving dashboard snapshot. Down if snapshot missing or server error."
        />
        <StatusRow
          label="Data aggregator"
          up={aggregatorUp}
          detail={dataFreshness}
          tooltip="dashboard_data_aggregator.py writes dashboard_snapshot.json. Age = time since last write."
        />
        <StatusRow
          label="Alerts API"
          up={dashboardUp}
          detail={dashboardUp ? 'Up' : '—'}
          tooltip="Alerts are derived from the same snapshot as the dashboard."
        />
        <StatusRow
          label="Trading health"
          up={trading?.reachable ?? false}
          detail={
            trading?.reachable
              ? trading.payload?.ib_connected === true
                ? 'IB connected'
                : trading.payload?.ib_connected === false
                  ? 'IB disconnected'
                  : 'Up'
              : trading?.error ?? 'Unreachable'
          }
          tooltip="Trading health agent (e.g. port 8000). Shows IB connection and kill switch. Set TRADING_HEALTH_URL if not on localhost:8000."
        />
        {trading?.reachable && trading.payload?.kill_switch_active && (
          <div className="flex items-center gap-2 py-2 border-b border-stone-100 bg-red-50 -mx-2 px-2 rounded">
            <span className="inline-block w-2.5 h-2.5 rounded-full bg-red-500 shrink-0" aria-hidden />
            <span className="text-sm font-semibold text-red-800">
              Kill switch active
            </span>
          </div>
        )}
        {!trading?.reachable && (
          <details className="mt-3 pt-3 border-t border-stone-200">
            <summary className="text-xs text-slate-600 cursor-pointer hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-600 focus:ring-offset-1 rounded">
              How to bring Trading health up
            </summary>
            <p className="text-xs text-stone-600 mt-2 mb-1">
              Start the health agent (from repo root):
            </p>
            <code className="block text-xs font-mono bg-stone-100 text-slate-800 px-3 py-2 rounded overflow-x-auto">
              cd trading/scripts &amp;&amp; uvicorn agents.health_check:app --host 0.0.0.0 --port 8000
            </code>
            <p className="text-xs text-slate-600 mt-2">
              Requires: <code className="bg-stone-100 px-1 rounded">pip install fastapi uvicorn</code>. If the agent runs on another host/port, set <code className="bg-stone-100 px-1 rounded">TRADING_HEALTH_URL</code> in the dashboard env.
            </p>
          </details>
        )}
      </div>
    </section>
  );
}
