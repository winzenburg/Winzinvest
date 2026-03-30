'use client';

/**
 * Waitlist Thank You + Referral Component
 * 
 * Shows after email verification with:
 * - Position in line
 * - Referral link (invite 3 friends, move up 10 spots)
 * - Copy button for easy sharing
 * 
 * Implements growth loop: user joins → shares link → friends join → original user moves up
 */

import { useEffect, useState } from 'react';

interface WaitlistStatus {
  status: string;
  tier: string;
  referralCode: string;
  referralCount: number;
  referralUrl: string;
  position: number | null;
  verifiedAt: string;
}

export default function WaitlistThankYou({ email }: { email: string }) {
  const [status, setStatus] = useState<WaitlistStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch(`/api/waitlist-status?email=${encodeURIComponent(email)}`);
        if (res.ok) {
          const data = await res.json();
          setStatus(data);
        }
      } catch (err) {
        console.error('Failed to fetch waitlist status:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchStatus();
  }, [email]);

  const handleCopy = async () => {
    if (!status?.referralUrl) return;
    
    try {
      await navigator.clipboard.writeText(status.referralUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Copy failed:', err);
    }
  };

  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="text-stone-600">Loading your waitlist status...</div>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="text-center py-12">
        <div className="text-red-600">Unable to load waitlist status.</div>
      </div>
    );
  }

  const tierNames: Record<string, string> = {
    intelligence: 'Intelligence',
    automation: 'Automation',
    professional: 'Professional',
    founding: 'Founding Member',
  };

  return (
    <div className="max-w-2xl mx-auto">
      
      {/* Confirmed */}
      <div className="bg-green-50 border border-green-200 rounded-xl p-8 mb-8">
        <div className="flex items-start gap-4">
          <svg className="w-12 h-12 text-green-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div>
            <h2 className="font-serif text-2xl font-bold text-slate-900 mb-2">
              You're on the list
            </h2>
            <p className="text-stone-700 leading-relaxed mb-4">
              You're confirmed for the <strong>{tierNames[status.tier] || status.tier}</strong> tier.
              {status.position && ` Position #${status.position} in line.`}
            </p>
            <p className="text-sm text-stone-600">
              We'll email you when your slot opens. Could be days, could be weeks. We'll keep you posted.
            </p>
          </div>
        </div>
      </div>

      {/* Referral CTA */}
      {status.referralUrl && (
        <div className="bg-white border border-stone-200 rounded-xl p-8">
          <div className="mb-6">
            <h3 className="font-serif text-xl font-bold text-slate-900 mb-2">
              Move up the line
            </h3>
            <p className="text-stone-600 leading-relaxed">
              Invite 3 friends. Each one who verifies their email moves you up 10 spots. 
              Simple growth loop: you help us, we help you.
            </p>
          </div>

          {/* Referral stats */}
          <div className="bg-stone-50 rounded-lg p-4 mb-6">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold text-slate-900">{status.referralCount}</div>
                <div className="text-sm text-stone-600">
                  {status.referralCount === 1 ? 'person' : 'people'} joined via your link
                </div>
              </div>
              {status.referralCount > 0 && status.position && (
                <div className="text-right">
                  <div className="text-2xl font-bold text-primary-600">
                    +{status.referralCount * 10}
                  </div>
                  <div className="text-sm text-stone-600">spots moved</div>
                </div>
              )}
            </div>
          </div>

          {/* Referral link */}
          <div className="space-y-3">
            <label htmlFor="referral-url" className="block text-sm font-semibold text-slate-900">
              Your referral link
            </label>
            <div className="flex gap-2">
              <input
                id="referral-url"
                type="text"
                value={status.referralUrl}
                readOnly
                className="flex-1 px-4 py-2.5 rounded-lg border border-stone-300 bg-stone-50 text-sm font-mono text-slate-800 focus:outline-none focus:ring-2 focus:ring-primary-600"
              />
              <button
                onClick={handleCopy}
                className="px-6 py-2.5 rounded-lg bg-primary-600 hover:bg-primary-700 text-white font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-primary-600 focus:ring-offset-2"
              >
                {copied ? 'Copied!' : 'Copy'}
              </button>
            </div>
            <p className="text-xs text-stone-500">
              Share on Twitter, Reddit (r/algotrading, r/options), or with trading friends.
            </p>
          </div>
        </div>
      )}

    </div>
  );
}
