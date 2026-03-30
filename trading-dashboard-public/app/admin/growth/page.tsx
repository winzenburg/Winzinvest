'use client';

/**
 * Growth Metrics Admin Dashboard
 * 
 * Tracks the P0 growth metrics:
 * - PMF Score (Sean Ellis 40% benchmark)
 * - D7 Activation Rate (60% target)
 * - Referral Conversion (waitlist growth loop)
 * 
 * Only accessible to admin users.
 */

import { useEffect, useState } from 'react';
import { fetchWithAuth } from '@/lib/fetch-client';
import DashboardNav from '@/app/components/DashboardNav';

interface PmfMetrics {
  total: number;
  veryDisappointed: number;
  somewhatDisappointed: number;
  notDisappointed: number;
  pmfScore: number;
  hasPmf: boolean;
  benchmark: number;
}

interface ActivationMetrics {
  total: number;
  activatedTotal: number;
  activatedWithin7Days: number;
  d7ActivationRate: number;
  target: number;
  users: Array<{
    email: string;
    signupDate: string;
    daysActive: number;
    firstTradeAt: string | null;
    daysToFirstTrade: number | null;
    activated: boolean;
  }>;
}

export default function GrowthMetricsPage() {
  const [pmf, setPmf] = useState<PmfMetrics | null>(null);
  const [activation, setActivation] = useState<ActivationMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const [pmfRes, activationRes] = await Promise.all([
          fetchWithAuth('/api/pmf-survey'),
          fetchWithAuth('/api/activation'),
        ]);

        if (!pmfRes.ok || !activationRes.ok) {
          throw new Error('Failed to fetch growth metrics');
        }

        const pmfData = await pmfRes.json();
        const activationData = await activationRes.json();

        setPmf(pmfData);
        setActivation(activationData);
      } catch (err) {
        console.error('Growth metrics error:', err);
        setError(err instanceof Error ? err.message : 'Failed to load metrics');
      } finally {
        setLoading(false);
      }
    };

    fetchMetrics();
  }, []);

  if (loading) {
    return (
      <>
        <DashboardNav />
        <div className="min-h-screen bg-stone-50 flex items-center justify-center">
          <div className="text-stone-600">Loading growth metrics...</div>
        </div>
      </>
    );
  }

  if (error) {
    return (
      <>
        <DashboardNav />
        <div className="min-h-screen bg-stone-50 flex items-center justify-center">
          <div className="text-red-600">{error}</div>
        </div>
      </>
    );
  }

  return (
    <>
      <DashboardNav />
      <div className="min-h-screen bg-stone-50">
        <div className="max-w-7xl mx-auto px-8 py-16">
          
          {/* Header */}
          <div className="mb-12">
            <h1 className="font-serif text-4xl font-bold text-slate-900 mb-2">
              Growth Metrics
            </h1>
            <p className="text-stone-600 leading-relaxed">
              P0 metrics tracking PMF, activation, and referral loops. Updated live.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-12">
            
            {/* PMF Score Card */}
            {pmf && (
              <div className="bg-white border border-stone-200 rounded-xl p-8">
                <div className="flex items-start justify-between mb-6">
                  <div>
                    <h2 className="font-serif text-2xl font-bold text-slate-900 mb-1">
                      Product-Market Fit
                    </h2>
                    <p className="text-sm text-stone-600">Sean Ellis 40% benchmark</p>
                  </div>
                  <div className={`inline-flex px-3 py-1 rounded-full text-xs font-semibold ${
                    pmf.hasPmf ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
                  }`}>
                    {pmf.hasPmf ? 'PMF Achieved' : 'Not Yet'}
                  </div>
                </div>

                <div className="mb-6">
                  <div className="flex items-baseline gap-2 mb-2">
                    <div className={`font-serif text-5xl font-bold ${
                      pmf.hasPmf ? 'text-green-600' : 'text-yellow-600'
                    }`}>
                      {pmf.pmfScore}%
                    </div>
                    <div className="text-stone-500">/ {pmf.benchmark}% target</div>
                  </div>
                  <div className="text-sm text-stone-600">
                    {pmf.veryDisappointed} of {pmf.total} users would be very disappointed
                  </div>
                </div>

                {/* Distribution */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-stone-600">Very disappointed</span>
                    <div className="flex items-center gap-3">
                      <div className="w-40 bg-stone-100 rounded-full h-2">
                        <div 
                          className="bg-green-600 h-2 rounded-full"
                          style={{ width: `${pmf.total > 0 ? (pmf.veryDisappointed / pmf.total) * 100 : 0}%` }}
                        />
                      </div>
                      <span className="text-sm font-semibold text-slate-900 w-8 text-right">
                        {pmf.veryDisappointed}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-sm text-stone-600">Somewhat disappointed</span>
                    <div className="flex items-center gap-3">
                      <div className="w-40 bg-stone-100 rounded-full h-2">
                        <div 
                          className="bg-yellow-500 h-2 rounded-full"
                          style={{ width: `${pmf.total > 0 ? (pmf.somewhatDisappointed / pmf.total) * 100 : 0}%` }}
                        />
                      </div>
                      <span className="text-sm font-semibold text-slate-900 w-8 text-right">
                        {pmf.somewhatDisappointed}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-sm text-stone-600">Not disappointed</span>
                    <div className="flex items-center gap-3">
                      <div className="w-40 bg-stone-100 rounded-full h-2">
                        <div 
                          className="bg-stone-400 h-2 rounded-full"
                          style={{ width: `${pmf.total > 0 ? (pmf.notDisappointed / pmf.total) * 100 : 0}%` }}
                        />
                      </div>
                      <span className="text-sm font-semibold text-slate-900 w-8 text-right">
                        {pmf.notDisappointed}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Activation Rate Card */}
            {activation && (
              <div className="bg-white border border-stone-200 rounded-xl p-8">
                <div className="flex items-start justify-between mb-6">
                  <div>
                    <h2 className="font-serif text-2xl font-bold text-slate-900 mb-1">
                      D7 Activation Rate
                    </h2>
                    <p className="text-sm text-stone-600">First automated trade within 7 days</p>
                  </div>
                  <div className={`inline-flex px-3 py-1 rounded-full text-xs font-semibold ${
                    activation.d7ActivationRate >= activation.target 
                      ? 'bg-green-100 text-green-700' 
                      : 'bg-yellow-100 text-yellow-700'
                  }`}>
                    {activation.d7ActivationRate >= activation.target ? 'On Track' : 'Below Target'}
                  </div>
                </div>

                <div className="mb-6">
                  <div className="flex items-baseline gap-2 mb-2">
                    <div className={`font-serif text-5xl font-bold ${
                      activation.d7ActivationRate >= activation.target ? 'text-green-600' : 'text-yellow-600'
                    }`}>
                      {activation.d7ActivationRate}%
                    </div>
                    <div className="text-stone-500">/ {activation.target}% target</div>
                  </div>
                  <div className="text-sm text-stone-600">
                    {activation.activatedWithin7Days} of {activation.total} users activated in 7 days
                  </div>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-2 gap-4 pt-6 border-t border-stone-200">
                  <div>
                    <div className="text-2xl font-bold text-slate-900">{activation.activatedTotal}</div>
                    <div className="text-xs text-stone-600">Total activated</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-slate-900">{activation.total - activation.activatedTotal}</div>
                    <div className="text-xs text-stone-600">Never activated</div>
                  </div>
                </div>
              </div>
            )}

          </div>

          {/* User Table */}
          {activation && activation.users.length > 0 && (
            <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
              <div className="px-8 py-6 border-b border-stone-200">
                <h2 className="font-serif text-2xl font-bold text-slate-900">
                  User Activation Timeline
                </h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-stone-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-stone-600 uppercase tracking-wider">
                        Email
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-stone-600 uppercase tracking-wider">
                        Signup Date
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-stone-600 uppercase tracking-wider">
                        Days Active
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-stone-600 uppercase tracking-wider">
                        First Trade
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-stone-600 uppercase tracking-wider">
                        Days to Activate
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-stone-600 uppercase tracking-wider">
                        Status
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-200">
                    {activation.users.map((u) => (
                      <tr key={u.email} className="hover:bg-stone-50">
                        <td className="px-6 py-4 text-sm text-slate-900 font-mono">
                          {u.email}
                        </td>
                        <td className="px-6 py-4 text-sm text-stone-600">
                          {new Date(u.signupDate).toLocaleDateString()}
                        </td>
                        <td className="px-6 py-4 text-sm text-stone-600">
                          {u.daysActive}
                        </td>
                        <td className="px-6 py-4 text-sm text-stone-600">
                          {u.firstTradeAt ? new Date(u.firstTradeAt).toLocaleDateString() : '—'}
                        </td>
                        <td className="px-6 py-4 text-sm text-stone-600">
                          {u.daysToFirstTrade !== null ? `${u.daysToFirstTrade} days` : '—'}
                        </td>
                        <td className="px-6 py-4 text-sm">
                          {u.activated ? (
                            <span className="inline-flex px-2 py-1 rounded-full text-xs font-semibold bg-green-100 text-green-700">
                              Activated
                            </span>
                          ) : u.daysActive <= 7 ? (
                            <span className="inline-flex px-2 py-1 rounded-full text-xs font-semibold bg-yellow-100 text-yellow-700">
                              Pending
                            </span>
                          ) : (
                            <span className="inline-flex px-2 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-700">
                              At Risk
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

        </div>
      </div>
    </>
  );
}
