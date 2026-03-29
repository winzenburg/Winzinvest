'use client';

import { useState } from 'react';

type Tier = 'intelligence' | 'automation' | 'professional' | 'founding';

interface WaitlistFormProps {
  tier: Tier;
  ctaLabel?: string;
  className?: string;
}

const TIER_LABELS: Record<Tier, string> = {
  intelligence:  'Intelligence ($49/mo)',
  automation:    'Automation ($149/mo)',
  professional:  'Professional ($399/mo)',
  founding:      'Founding Member ($79/mo lifetime)',
};

export function WaitlistForm({ tier, ctaLabel, className = '' }: WaitlistFormProps) {
  const [email, setEmail]       = useState('');
  const [status, setStatus]     = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState('');

  const label = ctaLabel ?? (tier === 'founding' ? 'Pre-Order Now' : 'Join Waitlist');

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const trimmed = email.trim();
    if (!trimmed || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
      setErrorMsg('Please enter a valid email address.');
      return;
    }
    setErrorMsg('');
    setStatus('loading');

    try {
      const res = await fetch('/api/waitlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: trimmed, tier }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({})) as { error?: string };
        setErrorMsg(data.error ?? 'Something went wrong. Please try again.');
        setStatus('error');
        return;
      }

      setStatus('success');
    } catch {
      setErrorMsg('Network error. Please check your connection and try again.');
      setStatus('error');
    }
  }

  if (status === 'success') {
    return (
      <div className={`rounded-xl border border-success-100 bg-success-50 p-4 ${className}`}>
        <p className="text-sm font-semibold text-success-700 mb-0.5">Check your email.</p>
        <p className="text-xs text-success-600 leading-relaxed">
          We sent a verification link to <strong>{email}</strong>. Click it to confirm your spot on the {TIER_LABELS[tier]} waitlist.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className={`flex flex-col gap-2 ${className}`} noValidate>
      <input
        type="email"
        required
        value={email}
        onChange={(e) => { setEmail(e.target.value); setErrorMsg(''); }}
        placeholder="your@email.com"
        aria-label="Email address"
        disabled={status === 'loading'}
        className="w-full px-4 py-2.5 rounded-xl border border-neutral-200 bg-white text-sm text-slate-900 placeholder-neutral-400 focus:outline-none focus:ring-2 focus:ring-primary-600 focus:border-transparent disabled:opacity-50 transition-colors"
      />
      <button
        type="submit"
        disabled={status === 'loading'}
        className="w-full px-5 py-2.5 rounded-xl bg-primary-600 hover:bg-primary-700 text-white font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-primary-600 focus:ring-offset-2 disabled:opacity-60 flex items-center gap-2 justify-center"
      >
        {status === 'loading' ? (
          <>
            <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            <span>Adding you...</span>
          </>
        ) : label}
      </button>
      {errorMsg && (
        <p role="alert" className="text-xs text-danger-600">{errorMsg}</p>
      )}
    </form>
  );
}
