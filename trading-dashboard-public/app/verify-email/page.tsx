'use client';

import { useEffect, useState, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get('token');
  
  const [status, setStatus] = useState<'loading' | 'success' | 'error' | 'already_verified'>('loading');
  const [message, setMessage] = useState('');
  const [tier, setTier] = useState('');

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setMessage('Invalid verification link.');
      return;
    }

    const verifyEmail = async () => {
      try {
        const response = await fetch(`/api/verify-waitlist-email?token=${token}`);
        const data = await response.json();

        if (data.ok) {
          if (data.alreadyVerified) {
            setStatus('already_verified');
          } else {
            setStatus('success');
            setTier(data.tier);
          }
          setMessage(data.message);
        } else {
          setStatus('error');
          setMessage(data.error || 'Verification failed.');
        }
      } catch (err) {
        setStatus('error');
        setMessage('Could not verify email. Please try again later.');
      }
    };

    verifyEmail();
  }, [token]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center px-4">
      <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-8">
        {status === 'loading' && (
          <div className="text-center">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-slate-800 border-r-transparent mb-4"></div>
            <h1 className="text-2xl font-semibold text-slate-900 mb-2">Verifying...</h1>
            <p className="text-slate-600">Please wait while we verify your email address.</p>
          </div>
        )}

        {status === 'success' && (
          <div className="text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-green-100 mb-4">
              <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h1 className="text-2xl font-semibold text-slate-900 mb-2">Email Verified!</h1>
            <p className="text-slate-600 mb-6">
              You're now on the <strong>{tier}</strong> tier waitlist. We'll email you when access opens.
            </p>
            <a
              href="/"
              className="inline-block bg-slate-800 text-white px-6 py-3 rounded-lg hover:bg-slate-700 transition-colors"
            >
              Return to Home
            </a>
          </div>
        )}

        {status === 'already_verified' && (
          <div className="text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-blue-100 mb-4">
              <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h1 className="text-2xl font-semibold text-slate-900 mb-2">Already Verified</h1>
            <p className="text-slate-600 mb-6">
              Your email has already been verified. You're on the waitlist!
            </p>
            <a
              href="/"
              className="inline-block bg-slate-800 text-white px-6 py-3 rounded-lg hover:bg-slate-700 transition-colors"
            >
              Return to Home
            </a>
          </div>
        )}

        {status === 'error' && (
          <div className="text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-100 mb-4">
              <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h1 className="text-2xl font-semibold text-slate-900 mb-2">Verification Failed</h1>
            <p className="text-slate-600 mb-6">{message}</p>
            <a
              href="/"
              className="inline-block bg-slate-800 text-white px-6 py-3 rounded-lg hover:bg-slate-700 transition-colors"
            >
              Return to Home
            </a>
          </div>
        )}
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-slate-800 border-r-transparent"></div>
        </div>
      </div>
    }>
      <VerifyEmailContent />
    </Suspense>
  );
}
