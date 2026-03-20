'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchWithAuth } from '@/lib/fetch-client';

interface KillSwitchState {
  active: boolean;
  reason: string;
  timestamp: string;
  activated_by?: string;
  cleared_at?: string;
  cleared_by?: string;
}

export default function KillSwitchButton() {
  const [state, setState] = useState<KillSwitchState | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState(false);
  const [pin, setPin] = useState('');
  const [pinError, setPinError] = useState('');
  const dialogRef = useRef<HTMLDivElement>(null);
  const pinInputRef = useRef<HTMLInputElement>(null);

  const fetchState = useCallback(async () => {
    try {
      const res = await fetchWithAuth('/api/kill-switch');
      if (res.ok) setState(await res.json() as KillSwitchState);
    } catch {
      // non-fatal — AuthError handled by redirect inside fetchWithAuth
    }
  }, []);

  useEffect(() => {
    fetchState();
    const id = setInterval(fetchState, 15000);
    return () => clearInterval(id);
  }, [fetchState]);

  // Reset pin when dialog opens/closes
  useEffect(() => {
    if (!showConfirm) {
      setPin('');
      setPinError('');
    } else if (!state?.active) {
      // Focus PIN field when activating
      setTimeout(() => pinInputRef.current?.focus(), 50);
    }
  }, [showConfirm, state?.active]);

  // Close dialog on outside click
  useEffect(() => {
    if (!showConfirm) return;
    const handler = (e: MouseEvent) => {
      if (dialogRef.current && !dialogRef.current.contains(e.target as Node)) {
        setShowConfirm(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showConfirm]);

  // Close on Escape
  useEffect(() => {
    if (!showConfirm) return;
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') setShowConfirm(false); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [showConfirm]);

  const toggle = useCallback(async () => {
    if (busy || !state) return;
    setBusy(true);
    setPinError('');

    try {
      const next = !state.active;
      const res = await fetchWithAuth('/api/kill-switch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active: next, pin: next ? pin : undefined }),
      });

      if (res.status === 403) {
        setPinError('Incorrect PIN. Try again.');
        setBusy(false);
        setPin('');
        pinInputRef.current?.focus();
        return;
      }

      if (res.ok) {
        const data = await res.json() as { ok: boolean; state: KillSwitchState };
        setState(data.state);
        setFlash(true);
        setShowConfirm(false);
        setTimeout(() => setFlash(false), 1500);
      }
    } finally {
      setBusy(false);
    }
  }, [busy, state, pin]);

  if (!state) return null;

  const isActive = state.active;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setShowConfirm(true)}
        disabled={busy}
        aria-label={isActive ? 'Kill switch is ACTIVE — click to clear' : 'Activate kill switch'}
        className={[
          'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-semibold transition-all duration-150 select-none border',
          busy ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer',
          isActive
            ? 'bg-red-600 border-red-600 text-white shadow-sm animate-pulse hover:bg-red-700'
            : 'bg-stone-100 border-stone-200 text-stone-600 hover:bg-red-50 hover:border-red-300 hover:text-red-700',
          flash ? 'scale-95' : '',
        ].join(' ')}
      >
        <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M18.36 6.64A9 9 0 1 1 5.64 6.64" />
          <line x1="12" y1="2" x2="12" y2="12" />
        </svg>
        <span>{isActive ? 'KILL SWITCH ACTIVE' : 'Kill Switch'}</span>
      </button>

      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div
            ref={dialogRef}
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="ks-title"
            aria-describedby="ks-desc"
            className="bg-white rounded-xl shadow-2xl w-full max-w-sm mx-4 p-6 border border-stone-200"
          >
            {isActive ? (
              <>
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center shrink-0">
                    <svg className="w-5 h-5 text-green-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  </div>
                  <div>
                    <h2 id="ks-title" className="text-base font-bold text-slate-900">Clear Kill Switch?</h2>
                    <p id="ks-desc" className="text-sm text-stone-500 mt-0.5">Resume automated trading</p>
                  </div>
                </div>
                <div className="bg-stone-50 rounded-lg p-3 mb-5 text-xs text-stone-500 border border-stone-200">
                  <span className="font-semibold text-stone-600">Active since:</span>{' '}
                  {new Date(state.timestamp).toLocaleString()}
                  {state.activated_by && <><br /><span className="font-semibold text-stone-600">Activated by:</span> {state.activated_by}</>}
                  {state.reason && <><br /><span className="font-semibold text-stone-600">Reason:</span> {state.reason}</>}
                </div>
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => setShowConfirm(false)}
                    className="flex-1 px-4 py-2 rounded-lg border border-stone-300 text-stone-600 text-sm font-medium hover:bg-stone-50 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={toggle}
                    disabled={busy}
                    className="flex-1 px-4 py-2 rounded-lg bg-green-600 text-white text-sm font-semibold hover:bg-green-700 transition-colors disabled:opacity-50"
                  >
                    Clear & Resume
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center shrink-0">
                    <svg className="w-5 h-5 text-red-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M18.36 6.64A9 9 0 1 1 5.64 6.64" />
                      <line x1="12" y1="2" x2="12" y2="12" />
                    </svg>
                  </div>
                  <div>
                    <h2 id="ks-title" className="text-base font-bold text-slate-900">Activate Kill Switch?</h2>
                    <p id="ks-desc" className="text-sm text-stone-500 mt-0.5">All automated trading halts immediately</p>
                  </div>
                </div>
                <ul className="text-sm text-stone-600 space-y-1.5 mb-5 bg-red-50 rounded-lg p-3 border border-red-200">
                  <li className="flex items-start gap-2"><span className="text-red-600 mt-0.5">•</span> Screeners will continue running</li>
                  <li className="flex items-start gap-2"><span className="text-red-600 mt-0.5">•</span> No new orders will be placed</li>
                  <li className="flex items-start gap-2"><span className="text-red-600 mt-0.5">•</span> Existing positions are <strong>not</strong> closed</li>
                </ul>

                {/* PIN field */}
                <div className="mb-5">
                  <label htmlFor="ks-pin" className="block text-xs font-semibold text-stone-500 uppercase tracking-wider mb-1.5">
                    Confirmation PIN
                  </label>
                  <input
                    ref={pinInputRef}
                    id="ks-pin"
                    type="password"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    value={pin}
                    onChange={e => { setPin(e.target.value); setPinError(''); }}
                    onKeyDown={e => { if (e.key === 'Enter' && pin) void toggle(); }}
                    placeholder="Enter PIN to confirm"
                    className={`w-full px-3 py-2 text-sm rounded-lg border ${pinError ? 'border-red-400 bg-red-50' : 'border-stone-300'} text-slate-900 placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-red-600`}
                  />
                  {pinError && <p className="mt-1 text-xs text-red-600">{pinError}</p>}
                  <p className="mt-1 text-xs text-stone-400">Set <code className="bg-stone-100 px-1 rounded">KILL_SWITCH_PIN</code> in your .env.local</p>
                </div>

                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => setShowConfirm(false)}
                    className="flex-1 px-4 py-2 rounded-lg border border-stone-300 text-stone-600 text-sm font-medium hover:bg-stone-50 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={toggle}
                    disabled={busy || !pin}
                    className="flex-1 px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-semibold hover:bg-red-700 transition-colors disabled:opacity-50"
                  >
                    {busy ? 'Halting…' : 'Halt Trading'}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
