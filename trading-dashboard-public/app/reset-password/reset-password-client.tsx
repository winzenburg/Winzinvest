'use client';

import { useRouter } from 'next/navigation';
import { useState, FormEvent } from 'react';

type Props = {
  token: string;
};

export default function ResetPasswordClient({ token }: Props) {
  const router = useRouter();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    setMessage('');

    if (password !== confirmPassword) {
      setLoading(false);
      setError('Passwords do not match.');
      return;
    }

    try {
      const res = await fetch('/api/reset-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, password }),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        setError(data.error ?? 'Unable to reset password. Please try again.');
      } else {
        setMessage('Your password has been reset. You can now sign in.');
        setTimeout(() => {
          router.push('/login');
        }, 2500);
      }
    } catch (err) {
      console.error('[reset-password] request failed', err);
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
            Reset password
          </h1>
          <p className="text-sm text-stone-500 mt-1">
            Choose a new password for your Winzinvest account.
          </p>
        </div>

        <div className="bg-white border border-stone-200 rounded-xl p-6 shadow-sm">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="password"
                className="block text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2"
              >
                New password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="Create a new password"
                className="w-full px-4 py-3 bg-white border border-stone-200 rounded-xl text-slate-900 placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-sky-600 focus:ring-offset-2 transition-all"
                required
              />
            </div>

            <div>
              <label
                htmlFor="confirm-password"
                className="block text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2"
              >
                Confirm password
              </label>
              <input
                id="confirm-password"
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                placeholder="Re-enter your new password"
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
              disabled={loading || !password || !confirmPassword}
              className="w-full py-3 px-4 bg-sky-600 hover:bg-sky-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-colors focus:outline-none focus:ring-2 focus:ring-sky-600 focus:ring-offset-2"
            >
              {loading ? 'Saving…' : 'Reset password'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

