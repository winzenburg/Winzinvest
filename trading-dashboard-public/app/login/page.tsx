'use client';

import { signIn } from 'next-auth/react';
import { use, useState, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense } from 'react';

type Mode = 'login' | 'signup';

function LoginForm() {
  const [mode, setMode] = useState<Mode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const passwordInputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const params = useSearchParams();
  const callbackUrl = params.get('callbackUrl') ?? '/dashboard';

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    const result = await signIn('credentials', {
      email,
      password,
      redirect: false,
      callbackUrl,
    });
    setLoading(false);
    if (result?.error) {
      setError('Incorrect email or password. Try again.');
      setPassword('');
      passwordInputRef.current?.focus();
    } else {
      router.replace(callbackUrl);
    }
  }

  async function handleSignup(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');

    if (password !== confirmPassword) {
      setLoading(false);
      setError('Passwords do not match.');
      return;
    }

    try {
      const res = await fetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.error ?? 'Unable to create account. Please try again.');
        setLoading(false);
        return;
      }

      // Auto-log in after successful registration.
      const result = await signIn('credentials', {
        email,
        password,
        redirect: false,
        callbackUrl,
      });

      setLoading(false);

      if (result?.error) {
        setError('Account created, but login failed. Please try again.');
      } else {
        router.replace(callbackUrl);
      }
    } catch (err) {
      console.error('[login] signup failed', err);
      setError('Something went wrong. Please try again.');
      setLoading(false);
    }
  }

  const handleSubmit = mode === 'login' ? handleLogin : handleSignup;

  return (
    <div className="min-h-screen bg-stone-50 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">

        {/* Logo / Title */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-xl bg-sky-50 border border-sky-200 mb-5">
            <svg className="w-7 h-7 text-sky-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
            </svg>
          </div>
          <h1 className="font-serif text-2xl font-bold text-slate-900 tracking-tight">Winz<span className="text-sky-600">invest</span></h1>
          <p className="text-sm text-stone-500 mt-1">Trading Dashboard</p>
        </div>

        {/* Form card */}
        <div className="bg-white border border-stone-200 rounded-xl p-6 shadow-sm">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full px-4 py-3 bg-white border border-stone-200 rounded-xl text-slate-900 placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-sky-600 focus:ring-offset-2 transition-all mb-4"
                required
              />
              <label htmlFor="password" className="block text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2">
                Password
              </label>
              <input
                ref={passwordInputRef}
                id="password"
                type="password"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                autoFocus
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder={mode === 'login' ? 'Enter your password' : 'Create a password'}
                className="w-full px-4 py-3 bg-white border border-stone-200 rounded-xl text-slate-900 placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-sky-600 focus:ring-offset-2 transition-all"
                required
              />
              {mode === 'signup' && (
                <div className="mt-4">
                  <label htmlFor="confirm-password" className="block text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2">
                    Confirm Password
                  </label>
                  <input
                    id="confirm-password"
                    type="password"
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={e => setConfirmPassword(e.target.value)}
                    placeholder="Re-enter your password"
                    className="w-full px-4 py-3 bg-white border border-stone-200 rounded-xl text-slate-900 placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-sky-600 focus:ring-offset-2 transition-all"
                    required
                  />
                </div>
              )}
            </div>

            {error && (
              <div className="flex items-center gap-2 px-3 py-2.5 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700" role="alert">
                <svg className="w-4 h-4 shrink-0 text-red-600" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                </svg>
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !email || !password || (mode === 'signup' && !confirmPassword)}
              className="w-full py-3 px-4 bg-sky-600 hover:bg-sky-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-colors focus:outline-none focus:ring-2 focus:ring-sky-600 focus:ring-offset-2"
            >
              {loading
                ? mode === 'login'
                  ? 'Signing in…'
                  : 'Creating account…'
                : mode === 'login'
                  ? 'Sign in'
                  : 'Create account'}
            </button>
          </form>

          {/* Social providers */}
          <div className="mt-6 border-t border-stone-200 pt-4">
            <p className="text-xs text-stone-400 mb-3 text-center">Or continue with</p>
            <div className="flex flex-col gap-2">
              <button
                type="button"
                onClick={() => signIn('google', { callbackUrl })}
                className="w-full py-2.5 px-4 border border-stone-200 rounded-xl text-sm font-semibold text-stone-700 hover:bg-stone-50 flex items-center justify-center gap-2"
              >
                <span>Google</span>
              </button>
              <button
                type="button"
                onClick={() => signIn('facebook', { callbackUrl })}
                className="w-full py-2.5 px-4 border border-stone-200 rounded-xl text-sm font-semibold text-stone-700 hover:bg-stone-50 flex items-center justify-center gap-2"
              >
                <span>Facebook</span>
              </button>
              <button
                type="button"
                onClick={() => signIn('apple', { callbackUrl })}
                className="w-full py-2.5 px-4 border border-stone-200 rounded-xl text-sm font-semibold text-stone-700 hover:bg-stone-50 flex items-center justify-center gap-2"
              >
                <span>Apple</span>
              </button>
            </div>
          </div>
        </div>

        <div className="mt-4 text-center text-xs text-stone-500 space-y-1">
          {mode === 'login' ? (
            <>
              <div>
                <span>New here? </span>
                <button
                  type="button"
                  onClick={() => {
                    setMode('signup');
                    setError('');
                  }}
                  className="font-semibold text-sky-700 hover:text-sky-800"
                >
                  Create a Winzinvest account
                </button>
              </div>
              <div>
                <a
                  href="/forgot-password"
                  className="font-semibold text-sky-700 hover:text-sky-800"
                >
                  Forgot your password?
                </a>
              </div>
            </>
          ) : (
            <>
              <span>Already have an account? </span>
              <button
                type="button"
                onClick={() => {
                  setMode('login');
                  setError('');
                }}
                className="font-semibold text-sky-700 hover:text-sky-800"
              >
                Sign in instead
              </button>
            </>
          )}
        </div>

        <p className="text-center text-xs text-stone-400 mt-6">
          Stay signed in for 30 days · Paper &amp; live trading controls inside
        </p>
      </div>
    </div>
  );
}

type PageProps = {
  params?: Promise<Record<string, string | string[]>>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

const EMPTY = Promise.resolve({});

export default function LoginPage(props: PageProps) {
  use(props.params ?? EMPTY);
  use(props.searchParams ?? EMPTY);
  return (
    <Suspense fallback={<div className="min-h-screen bg-stone-50" />}>
      <LoginForm />
    </Suspense>
  );
}
