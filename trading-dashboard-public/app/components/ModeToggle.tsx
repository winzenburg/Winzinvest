'use client';

import { useState } from 'react';
import { useTradingMode } from '../context/TradingModeContext';

type TradingMode = 'paper' | 'live';

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

/** Confirmation dialog shown before switching trading mode. */
function ModeConfirmDialog({
  targetMode,
  onConfirm,
  onCancel,
}: {
  targetMode: TradingMode;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const isLive = targetMode === 'live';
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-2xl p-6 max-w-md w-full mx-4">
        {isLive ? (
          <>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center text-red-600 text-xl font-bold">!</div>
              <h2 className="text-lg font-bold text-slate-900">Activate Live Trading</h2>
            </div>
            <p className="text-sm text-stone-600 mb-2">
              This will update <code className="bg-stone-100 px-1 rounded">trading/.env</code> and immediately switch to your <span className="font-semibold text-red-600">live IBKR account</span> (port 4001).
            </p>
            <p className="text-sm text-stone-500 mb-6">
              Real capital will be at risk. All automated strategies will execute against your live account on the next scheduler run.
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
              Paper mode uses simulated funds. Make sure the paper IB Gateway is running.
            </p>
          </>
        )}
        <div className="flex gap-3 justify-end">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 text-sm font-medium text-stone-600 bg-stone-100 rounded-lg hover:bg-stone-200 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={`px-4 py-2 text-sm font-semibold text-white rounded-lg transition-colors ${
              isLive
                ? 'bg-red-600 hover:bg-red-700'
                : 'bg-blue-600 hover:bg-blue-700'
            }`}
          >
            {isLive ? 'Activate Live' : 'Switch to Paper'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ModeToggle() {
  const { activeMode, paperGatewayUp, modes, loading, activateMode, activating } = useTradingMode();
  const [confirmTarget, setConfirmTarget] = useState<TradingMode | null>(null);
  const [activateError, setActivateError] = useState<string | null>(null);

  if (loading) {
    return (
      <div className="flex items-center gap-2 rounded-lg bg-stone-100 px-3 py-2 animate-pulse">
        <div className="h-6 w-16 rounded bg-stone-200" />
      </div>
    );
  }

  const modes_list: { key: TradingMode; label: string }[] = [
    { key: 'paper', label: 'Paper' },
    { key: 'live', label: 'Live' },
  ];

  async function handleConfirmed() {
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
        <ModeConfirmDialog
          targetMode={confirmTarget}
          onConfirm={handleConfirmed}
          onCancel={() => setConfirmTarget(null)}
        />
      )}

      <div className="flex flex-col items-end gap-2">
        {/* Single unified control */}
        <div className="flex items-center rounded-lg bg-stone-100 p-0.5 border border-stone-200">
          {modes_list.map(({ key, label }) => {
            const isActive = activeMode === key;
            const isLoading = activating === key;
            const info = modes[key];
            const isAvailable = info.available;
            const canActivatePaper = key === 'paper' && paperGatewayUp;
            const canActivateLive = key === 'live';
            const canSwitch = !isActive && (canActivatePaper || canActivateLive) && !activating;

            return (
              <button
                type="button"
                key={key}
                onClick={() => canSwitch && setConfirmTarget(key)}
                disabled={!canSwitch}
                title={
                  isActive
                    ? `${label} mode active — last updated ${timeAgo(info.lastUpdate)}`
                    : !isAvailable
                      ? `No ${label} snapshot available`
                      : key === 'paper' && !paperGatewayUp
                        ? 'Paper gateway offline'
                        : `Switch to ${label} mode`
                }
                className={[
                  'relative flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-semibold',
                  'transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-1',
                  isActive && key === 'live'
                    ? 'bg-red-600 text-white shadow-md cursor-default focus:ring-red-400'
                    : isActive
                      ? 'bg-white text-slate-900 shadow-md cursor-default focus:ring-slate-400'
                      : canSwitch
                        ? key === 'live'
                          ? 'text-stone-600 hover:text-red-600 hover:bg-red-50 focus:ring-red-400'
                          : 'text-stone-600 hover:text-blue-600 hover:bg-blue-50 focus:ring-blue-400'
                        : 'text-stone-300 cursor-not-allowed',
                ].join(' ')}
              >
                {isLoading ? (
                  <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                ) : (
                  <span className={`w-2 h-2 rounded-full shrink-0 ${
                    isActive 
                      ? (key === 'live' ? 'bg-white' : 'bg-slate-900') + ' animate-pulse'
                      : canSwitch 
                        ? (key === 'live' ? 'bg-red-400' : 'bg-blue-400')
                        : 'bg-stone-300'
                  }`} />
                )}
                {label}
                {isActive && key === 'live' && (
                  <span className="ml-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-red-500 text-white uppercase tracking-wide">
                    LIVE
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Status messages */}
        {(activateError || (activeMode !== 'live' && !paperGatewayUp)) && (
          <div className="text-xs text-right">
            {activateError && (
              <div className="text-red-600 mb-1">{activateError}</div>
            )}
            {activeMode !== 'live' && !paperGatewayUp && (
              <div className="text-stone-500">
                Paper gateway offline
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}
