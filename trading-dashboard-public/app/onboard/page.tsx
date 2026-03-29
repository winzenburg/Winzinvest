'use client';

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';

function OnboardContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [status, setStatus] = useState<'verifying' | 'valid' | 'invalid' | 'creating'>('verifying');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');

  const email = searchParams.get('email');
  const token = searchParams.get('token');

  useEffect(() => {
    if (!email || !token) {
      setStatus('invalid');
      return;
    }

    verifyToken();
  }, [email, token]);

  async function verifyToken() {
    try {
      const res = await fetch('/api/verify-invitation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, token }),
      });

      if (res.ok) {
        setStatus('valid');
      } else {
        setStatus('invalid');
      }
    } catch {
      setStatus('invalid');
    }
  }

  async function handleCreateAccount(e: React.FormEvent) {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    setStatus('creating');

    try {
      const res = await fetch('/api/complete-onboarding', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, token, name, password }),
      });

      if (res.ok) {
        router.push('/login?registered=true');
      } else {
        const data = await res.json();
        setError(data.error || 'Failed to create account');
        setStatus('valid');
      }
    } catch {
      setError('Unexpected error. Please try again.');
      setStatus('valid');
    }
  }

  if (status === 'verifying') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Verifying your invitation...</p>
        </div>
      </div>
    );
  }

  if (status === 'invalid') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="max-w-md w-full bg-white rounded-lg shadow p-8 text-center">
          <div className="text-red-600 text-4xl mb-4">✕</div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Invalid Invitation</h1>
          <p className="text-gray-600 mb-6">
            This invitation link is invalid or has expired. Please contact support for a new invitation.
          </p>
          <a href="/" className="text-blue-600 hover:underline">
            Return to homepage
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="max-w-md w-full bg-white rounded-lg shadow p-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-2 text-center">Complete Your Account</h1>
        <p className="text-gray-600 mb-6 text-center">{email}</p>

        <form onSubmit={handleCreateAccount} className="space-y-4">
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
              Full Name
            </label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 mb-1">
              Confirm Password
            </label>
            <input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              minLength={8}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {error && (
            <div className="text-red-600 text-sm bg-red-50 p-3 rounded">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={status === 'creating'}
            className="w-full py-2.5 bg-blue-600 text-white rounded-md font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {status === 'creating' ? 'Creating Account...' : 'Create Account'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default function OnboardPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    }>
      <OnboardContent />
    </Suspense>
  );
}
