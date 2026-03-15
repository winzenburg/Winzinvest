'use client';

import { useState } from 'react';
import { useTradingMode } from '../context/TradingModeContext';

type ViewMode = 'paper' | 'live';

function timeAgo(isoString: string | null): string {
  if (!isoString) return '';
  const diff = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

/** Confirmation dialog shown before switching the active execution mode. */
function ActivateConfirmDialog({
  targetMode,
  onConfirm,
  onCancel,
}: {
  targetMode: ViewMode;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const isLive = targetMode === 'live';
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-2xl p-6 max-w-sm w-full mx-4">
        {isLive ? (
          <>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center text-red-600 text-xl font-bold">!</div>
              <h2 className="text-lg font-bold text-slate-900">Switch to Live Trading</h2>
            </div>
            <p className="text-sm text-stone-600 mb-2">
              This will update <code className="bg-stone-100 px-1 rounded">trading/.env</code> to route all new orders to your <span className="font-semibold text-red-600">live IBKR account</span>.
            </p>
            <p className="text-sm text-stone-500 mb-6">
              Real money will be at risk. The change takes effect on the next scheduler run.
            </p>
          </>
        ) : (
          <>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 text-xl">📄</div>
              <h2 className="text-lg font-bold text-slate-900">Switch to Paper Trading</h2>
            </div>
            <p className="text-sm text-stone-600 mb-2">
              This will update <code className="bg-stone-100 px-1 rounded">trading/.env</code> to route all new orders to your <span className="font-semibold text-blue-600">paper IBKR account</span> (port 4002).
            </p>
            <p className="text-sm text-stone-500 mb-6">
              Make sure the paper IB Gateway is running before confirming.
            </p>
          </>
        )}
        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm font-medium text-stone-600 bg-stone-100 rounded-lg hover:bg-stone-200 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={`px-4 py-2 text-sm font-semibold text-white rounded-lg transition-colors ${
              isLive
                ? 'bg-red-600 hover:bg-red-700'
                : 'bg-blue-600 hover:bg-blue-700'
            }`}
          >
            {isLive ? 'Switch to Live' : 'Switch to Paper'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ModeToggle() {
  const { viewMode, setViewMode, activeMode, paperGatewayUp, modes, loading, activateMode, activating } = useTradingMode();
  const [confirmTarget, setConfirmTarget] = useState<ViewMode | null>(null);
  const [activateError, setActivateError] = useState<string | null>(null);

  if (loading) {
    return (
      <div className="flex items-center gap-1 rounded-lg bg-stone-100 p-1 animate-pulse">
        <div className="h-8 w-20 rounded-md bg-stone-200" />
        <div className="h-8 w-20 rounded-md bg-stone-200" />
      </div>
    );
  }

  const tabs: { key: ViewMode; label: string }[] = [
    { key: 'paper', label: 'Paper' },
    { key: 'live', label: 'Live' },
  ];

  async function handleActivateConfirmed() {
    if (!confirmTarget) return;
    setConfirmTarget(null);
    setActivateError(null);
    const ok = await activateMode(confirmTarget);
    if (!ok) {
      setActivateError(`Failed to switch to ${confirmTarget} mode. Check server logs.`);
    }
  }

  return (
    <>
      {confirmTarget && (
        <ActivateConfirmDialog
          targetMode={confirmTarget}
          onConfirm={handleActivateConfirmed}
          onCancel={() => setConfirmTarget(null)}
        />
      )}

      <div className="flex flex-col items-end gap-1">

        {/* ── Single control row ── */}
        <div className="flex items-center gap-2">

          {/* Viewing pill */}
          <div className="flex items-center rounded-lg bg-stone-100 p-0.5 border border-stone-200">
            <span className="px-2 text-xs text-stone-400 font-medium select-none">View</span>
            {tabs.map(({ key, label }) => {
              const isSelected = viewMode === key;
              const isRunning  = activeMode === key;
              const info       = modes[key];
              const isAvailable = info.available;

              return (
                <button
                  key={key}
                  onClick={() => setViewMode(key)}
                  disabled={!isAvailable}
                  title={
                    !isAvailable
                      ? `No ${label} snapshot available yet`
                      : isRunning
                        ? `${label} — currently executing`
                        : `${label} — last updated ${timeAgo(info.lastUpdate)}`
                  }
                  className={[
                    'relative flex items-center gap-1 px-3 py-1.5 rounded-md text-sm font-semibold',
                    'transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-1',
                    isSelected && key === 'live'
                      ? 'bg-red-600 text-white shadow-sm focus:ring-red-400'
                      : isSelected
                        ? 'bg-white text-slate-900 shadow-sm focus:ring-slate-400'
                        : isAvailable
                          ? 'text-stone-500 hover:text-stone-600 hover:bg-stone-50 focus:ring-sky-600'
                          : 'text-stone-300 cursor-not-allowed',
                  ].join(' ')}
                >
                  {label}
                  {isRunning && (
                    <span className={`w-1.5 h-1.5 rounded-full animate-pulse shrink-0 ${
                      isSelected && key === 'live' ? 'bg-white' : 'bg-green-500'
                    }`} />
                  )}
                </button>
              );
            })}
          </div>

          {/* Executing pill */}
          <div className="flex items-center rounded-lg bg-stone-100 p-0.5 border border-stone-200">
            <span className="px-2 text-xs text-stone-400 font-medium select-none flex items-center gap-1">
              Exec
              {activeMode === 'live' && (
                <span className="px-1 py-0 rounded text-[10px] font-bold bg-red-100 text-red-700 uppercase tracking-wide leading-4">
                  LIVE
                </span>
              )}
            </span>
            {tabs.map(({ key, label }) => {
              const isActive          = activeMode === key;
              const isLoading         = activating === key;
              const canActivatePaper  = key === 'paper' && paperGatewayUp;
              const canActivateLive   = key === 'live';
              const canActivate       = !isActive && (canActivatePaper || canActivateLive) && !activating;

              return (
                <button
                  key={key}
                  onClick={() => canActivate && setConfirmTarget(key)}
                  disabled={!canActivate}
                  title={
                    isActive
                      ? `${label} is already active`
                      : key === 'paper' && !paperGatewayUp
                        ? 'Paper gateway offline — run start_paper_gateway.sh first'
                        : `Switch execution to ${label}`
                  }
                  className={[
                    'flex items-center gap-1 px-3 py-1.5 rounded-md text-sm font-semibold',
                    'transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-1',
                    isActive && key === 'live'
                      ? 'bg-red-600 text-white shadow-sm cursor-default focus:ring-red-400'
                      : isActive
                        ? 'bg-white text-slate-900 shadow-sm cursor-default focus:ring-slate-400'
                        : canActivate
                          ? key === 'live'
                            ? 'text-stone-500 hover:text-red-600 hover:bg-red-50 focus:ring-red-400'
                            : 'text-stone-500 hover:text-blue-600 hover:bg-blue-50 focus:ring-blue-400'
                          : 'text-stone-300 cursor-not-allowed',
                  ].join(' ')}
                >
                  {isLoading ? (
                    <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                      isActive ? 'bg-white animate-pulse' :
                      canActivate ? (key === 'live' ? 'bg-red-400' : 'bg-blue-400') :
                      'bg-stone-300'
                    }`} />
                  )}
                  {label}
                </button>
              );
            })}
          </div>
        </div>

        {/* ── Status hints (below controls) ── */}
        {(activateError || !paperGatewayUp) && (
          <div className="flex items-center gap-3 text-xs">
            {activateError && (
              <span className="text-red-600">{activateError}</span>
            )}
            {!paperGatewayUp && (
              <span className="text-stone-500 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-stone-400 shrink-0" />
                Paper gateway offline —{' '}
                <code className="text-stone-400">start_paper_gateway.sh</code>
              </span>
            )}
          </div>
        )}
      </div>
    </>
  );
}
