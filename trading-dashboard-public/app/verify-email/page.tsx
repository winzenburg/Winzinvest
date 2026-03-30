'use client';

import { useEffect, useState, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import WaitlistThankYou from '../components/WaitlistThankYou';

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get('token');
  
  const [status, setStatus] = useState<'loading' | 'success' | 'error' | 'already_verified'>('loading');
  const [message, setMessage] = useState('');
  const [email, setEmail] = useState('');

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
          }
          setMessage(data.message);
          setEmail(data.email || '');
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

  if (status === 'loading') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center px-4">
        <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-8">
          <div className="text-center">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-slate-800 border-r-transparent mb-4"></div>
            <h1 className="text-2xl font-semibold text-slate-900 mb-2">Verifying...</h1>
            <p className="text-slate-600">Please wait while we verify your email address.</p>
          </div>
        </div>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center px-4">
        <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-8">
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
        </div>
      </div>
    );
  }

  // Success or already verified - show referral component
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 py-16 px-4">
      <WaitlistThankYou email={email} />
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
