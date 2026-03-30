'use client';

/**
 * Email Preferences Component
 * 
 * Lets users control email frequency (daily vs weekly).
 * Respects user autonomy (SDT — Self-Determination Theory).
 * 
 * Framework: Fogg B=MAP — give users ability to tune their own engagement level
 */

import { useState, useEffect } from 'react';

export default function EmailPreferences({ className = '' }: { className?: string }) {
  const [frequency, setFrequency] = useState<'daily' | 'weekly'>('weekly');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    const fetchPreferences = async () => {
      try {
        const res = await fetch('/api/user-segment', { credentials: 'include' });
        if (res.ok) {
          const data = await res.json();
          setFrequency(data.emailFrequency || 'weekly');
        }
      } catch (err) {
        console.error('Error fetching email preferences:', err);
      } finally {
        setLoading(false);
      }
    };
    
    fetchPreferences();
  }, []);

  const handleSave = async (newFrequency: 'daily' | 'weekly') => {
    setSaving(true);
    setMessage(null);

    try {
      const res = await fetch('/api/email-preferences', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ frequency: newFrequency }),
      });

      if (res.ok) {
        setFrequency(newFrequency);
        setMessage({ type: 'success', text: 'Email preferences saved' });
        setTimeout(() => setMessage(null), 3000);
      } else {
        setMessage({ type: 'error', text: 'Failed to save preferences' });
      }
    } catch (err) {
      console.error('Error saving preferences:', err);
      setMessage({ type: 'error', text: 'Network error' });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className={`rounded-xl border border-stone-200 bg-white p-6 ${className}`}>
        <div className="animate-pulse">
          <div className="h-6 bg-stone-200 rounded w-1/2 mb-4" />
          <div className="h-20 bg-stone-100 rounded" />
        </div>
      </div>
    );
  }

  return (
    <div className={`rounded-xl border border-stone-200 bg-white p-6 ${className}`}>
      <h3 className="font-semibold text-lg text-slate-900 mb-4">
        Email Insights Frequency
      </h3>

      <div className="space-y-3">
        <label className="flex items-start gap-3 cursor-pointer group">
          <input
            type="radio"
            name="frequency"
            value="daily"
            checked={frequency === 'daily'}
            onChange={() => handleSave('daily')}
            disabled={saving}
            className="mt-1 w-4 h-4 text-emerald-600 focus:ring-2 focus:ring-emerald-500"
          />
          <div className="flex-1">
            <div className="font-medium text-slate-900 group-hover:text-emerald-600 transition-colors">
              Daily
            </div>
            <div className="text-sm text-stone-600 mt-0.5">
              Get a summary of what happened today — every weekday at 5pm MT
            </div>
          </div>
        </label>

        <label className="flex items-start gap-3 cursor-pointer group">
          <input
            type="radio"
            name="frequency"
            value="weekly"
            checked={frequency === 'weekly'}
            onChange={() => handleSave('weekly')}
            disabled={saving}
            className="mt-1 w-4 h-4 text-emerald-600 focus:ring-2 focus:ring-emerald-500"
          />
          <div className="flex-1">
            <div className="font-medium text-slate-900 group-hover:text-emerald-600 transition-colors">
              Weekly
            </div>
            <div className="text-sm text-stone-600 mt-0.5">
              Get a curated insight from your data — every Friday at 5pm MT
            </div>
          </div>
        </label>
      </div>

      {message && (
        <div className={`mt-4 p-3 rounded-lg text-sm ${
          message.type === 'success'
            ? 'bg-green-50 text-green-800 border border-green-200'
            : 'bg-red-50 text-red-800 border border-red-200'
        }`}>
          {message.text}
        </div>
      )}

      <p className="mt-4 text-xs text-stone-500">
        Your inbox, your rules. You can change this anytime.
      </p>
    </div>
  );
}
