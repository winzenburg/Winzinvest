'use client';

import { useState, useEffect, useCallback } from 'react';
import { fetchWithAuth } from '@/lib/fetch-client';

interface NotificationPrefs {
  channels: {
    telegram: boolean;
    email: boolean;
    browser_push: boolean;
  };
  thresholds: {
    daily_loss_pct: number;
    drawdown_pct: number;
    margin_utilization_pct: number;
    data_staleness_minutes: number;
  };
  events: {
    trade_executed: boolean;
    kill_switch_activated: boolean;
    drawdown_circuit_breaker: boolean;
    assignment_risk: boolean;
    screener_complete: boolean;
    daily_summary: boolean;
  };
}

function Toggle({
  checked,
  onChange,
  label,
  description,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  description?: string;
}) {
  return (
    <div className="flex items-start gap-3 group">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={description ? `${label}. ${description}` : label}
        onClick={() => onChange(!checked)}
        className={`relative shrink-0 mt-0.5 w-9 h-5 rounded-full transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-1 ${
          checked ? 'bg-sky-500' : 'bg-stone-300'
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${
            checked ? 'translate-x-4' : 'translate-x-0'
          }`}
        />
      </button>
      <div className="min-w-0">
        <div className="text-sm font-medium text-stone-800">{label}</div>
        {description && <div className="text-xs text-stone-500 mt-0.5">{description}</div>}
      </div>
    </div>
  );
}

function NumberInput({
  value,
  onChange,
  label,
  suffix,
  min,
  max,
  step,
}: {
  value: number;
  onChange: (v: number) => void;
  label: string;
  suffix?: string;
  min?: number;
  max?: number;
  step?: number;
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <label className="text-sm text-stone-600 flex-1">{label}</label>
      <div className="flex items-center gap-1.5">
        <input
          type="number"
          value={value}
          onChange={e => onChange(Number(e.target.value))}
          min={min}
          max={max}
          step={step ?? 0.1}
          className="w-20 px-2 py-1 text-sm text-right border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-sky-500"
        />
        {suffix && <span className="text-xs text-stone-500 w-8">{suffix}</span>}
      </div>
    </div>
  );
}

export default function NotificationPrefsPanel({ onClose }: { onClose: () => void }) {
  const [prefs, setPrefs] = useState<NotificationPrefs | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetchWithAuth('/api/notification-prefs');
      if (res.ok) setPrefs(await res.json() as NotificationPrefs);
    } catch {
      // non-fatal
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const save = async () => {
    if (!prefs) return;
    setSaving(true);
    try {
      const res = await fetchWithAuth('/api/notification-prefs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(prefs),
      });
      if (!res.ok) {
        return;
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  if (!prefs) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
        <div className="bg-white rounded-2xl p-8 shadow-2xl">
          <div className="text-stone-400 text-sm">Loading preferences…</div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm px-4" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-lg border border-stone-200 overflow-hidden"
        onClick={e => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Notification Preferences"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-stone-200">
          <div>
            <h2 className="text-base font-bold text-slate-900">Notification Preferences</h2>
            <p className="text-xs text-stone-500 mt-0.5">Control how and when Winzinvest alerts you</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-stone-400 hover:bg-stone-100 hover:text-stone-600 transition-colors"
            aria-label="Close"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="px-6 py-5 overflow-y-auto max-h-[70vh] space-y-6">

          {/* Channels */}
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-stone-400 mb-3">Alert Channels</h3>
            <div className="space-y-3">
              <Toggle
                checked={prefs.channels.telegram}
                onChange={v => setPrefs(p => p ? { ...p, channels: { ...p.channels, telegram: v } } : p)}
                label="Telegram"
                description="Requires TELEGRAM_BOT_TOKEN in .env"
              />
              <Toggle
                checked={prefs.channels.email}
                onChange={v => setPrefs(p => p ? { ...p, channels: { ...p.channels, email: v } } : p)}
                label="Email"
                description="Requires RESEND_API_KEY in .env"
              />
              <Toggle
                checked={prefs.channels.browser_push}
                onChange={v => setPrefs(p => p ? { ...p, channels: { ...p.channels, browser_push: v } } : p)}
                label="Browser Push"
                description="Requires notification permission in your browser"
              />
            </div>
          </section>

          {/* Thresholds */}
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-stone-400 mb-3">Alert Thresholds</h3>
            <div className="space-y-3">
              <NumberInput
                label="Daily loss alert"
                value={prefs.thresholds.daily_loss_pct}
                onChange={v => setPrefs(p => p ? { ...p, thresholds: { ...p.thresholds, daily_loss_pct: v } } : p)}
                suffix="%"
                min={0.1}
                max={20}
                step={0.1}
              />
              <NumberInput
                label="Drawdown alert"
                value={prefs.thresholds.drawdown_pct}
                onChange={v => setPrefs(p => p ? { ...p, thresholds: { ...p.thresholds, drawdown_pct: v } } : p)}
                suffix="%"
                min={0.5}
                max={50}
                step={0.5}
              />
              <NumberInput
                label="Margin utilization alert"
                value={prefs.thresholds.margin_utilization_pct}
                onChange={v => setPrefs(p => p ? { ...p, thresholds: { ...p.thresholds, margin_utilization_pct: v } } : p)}
                suffix="%"
                min={10}
                max={100}
                step={5}
              />
              <NumberInput
                label="Data staleness alert"
                value={prefs.thresholds.data_staleness_minutes}
                onChange={v => setPrefs(p => p ? { ...p, thresholds: { ...p.thresholds, data_staleness_minutes: v } } : p)}
                suffix="min"
                min={1}
                max={60}
                step={1}
              />
            </div>
          </section>

          {/* Events */}
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-stone-400 mb-3">Alert Events</h3>
            <div className="space-y-3">
              <Toggle
                checked={prefs.events.trade_executed}
                onChange={v => setPrefs(p => p ? { ...p, events: { ...p.events, trade_executed: v } } : p)}
                label="Trade Executed"
                description="Alert every time the system places an order"
              />
              <Toggle
                checked={prefs.events.kill_switch_activated}
                onChange={v => setPrefs(p => p ? { ...p, events: { ...p.events, kill_switch_activated: v } } : p)}
                label="Kill Switch Activated / Cleared"
                description="Critical — always recommended"
              />
              <Toggle
                checked={prefs.events.drawdown_circuit_breaker}
                onChange={v => setPrefs(p => p ? { ...p, events: { ...p.events, drawdown_circuit_breaker: v } } : p)}
                label="Drawdown Circuit Breaker Triggered"
                description="When the system enters a risk-reduction mode"
              />
              <Toggle
                checked={prefs.events.assignment_risk}
                onChange={v => setPrefs(p => p ? { ...p, events: { ...p.events, assignment_risk: v } } : p)}
                label="Assignment Risk Detected"
                description="When an ITM option is close to expiry"
              />
              <Toggle
                checked={prefs.events.screener_complete}
                onChange={v => setPrefs(p => p ? { ...p, events: { ...p.events, screener_complete: v } } : p)}
                label="Screener Complete"
                description="When watchlists are refreshed (noisy)"
              />
              <Toggle
                checked={prefs.events.daily_summary}
                onChange={v => setPrefs(p => p ? { ...p, events: { ...p.events, daily_summary: v } } : p)}
                label="Daily Summary"
                description="End-of-day P&L and position report"
              />
            </div>
          </section>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-stone-200 flex items-center justify-between gap-3 bg-stone-50">
          <p className="text-xs text-stone-500">
            Changes take effect immediately. Channel credentials managed in <code className="bg-stone-200 px-1 rounded">.env</code>.
          </p>
          <button
            type="button"
            onClick={save}
            disabled={saving}
            className="px-5 py-2 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white text-sm font-semibold rounded-xl transition-colors focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            {saved ? '✓ Saved' : saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
