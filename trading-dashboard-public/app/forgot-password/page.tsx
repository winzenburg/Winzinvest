'use client';

import { useState, FormEvent } from 'react';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    setMessage('');

    try {
      const res = await fetch('/api/request-password-reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.error ?? 'Unable to send reset link. Please try again.');
      } else {
        setMessage('If this email exists, a reset link has been sent.');
      }
    } catch (err) {
      console.error('[forgot-password] request failed', err);
      setError('Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-stone-50 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="font-serif text-2xl font-bold text-slate-900 tracking-tight">
            Forgot password
          </h1>
          <p className="text-sm text-stone-500 mt-1">
            Enter your email to receive a password reset link.
          </p>
        </div>

        <div className="bg-white border border-stone-200 rounded-xl p-6 shadow-sm">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="email"
                className="block text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2"
              >
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full px-4 py-3 bg-white border border-stone-200 rounded-xl text-slate-900 placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-sky-600 focus:ring-offset-2 transition-all"
                required
              />
            </div>

            {message && (
              <div className="px-3 py-2.5 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-700">
                {message}
              </div>
            )}

            {error && (
              <div className="px-3 py-2.5 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !email}
              className="w-full py-3 px-4 bg-sky-600 hover:bg-sky-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-colors focus:outline-none focus:ring-2 focus:ring-sky-600 focus:ring-offset-2"
            >
              {loading ? 'Sending link…' : 'Send reset link'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-stone-400 mt-6">
          Remembered your password?{' '}
          <a
            href="/login"
            className="font-semibold text-sky-700 hover:text-sky-800"
          >
            Back to login
          </a>
        </p>
      </div>
    </div>
  );
}

