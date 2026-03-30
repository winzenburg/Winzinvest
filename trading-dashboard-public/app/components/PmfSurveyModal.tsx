'use client';

/**
 * Sean Ellis PMF Survey Modal
 * 
 * Shows at Day 14 after signup. Asks the core PMF question:
 * "How would you feel if you could no longer use Winzinvest?"
 * 
 * Target: 40%+ "Very disappointed" = PMF achieved
 * 
 * Dismissible but will re-prompt at D21, D30 if not completed.
 */

import { useState } from 'react';
import { fetchWithAuth } from '@/lib/fetch-client';

interface PmfSurveyModalProps {
  onClose: () => void;
  onComplete: () => void;
}

export default function PmfSurveyModal({ onClose, onComplete }: PmfSurveyModalProps) {
  const [step, setStep] = useState<'main' | 'followup'>('main');
  const [disappointment, setDisappointment] = useState<'very' | 'somewhat' | 'not' | null>(null);
  const [idealCustomer, setIdealCustomer] = useState('');
  const [mainBenefit, setMainBenefit] = useState('');
  const [improvements, setImprovements] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleMainQuestion = (level: 'very' | 'somewhat' | 'not') => {
    setDisappointment(level);
    setStep('followup');
  };

  const handleSubmit = async () => {
    if (!disappointment) return;

    setSubmitting(true);
    try {
      await fetchWithAuth('/api/pmf-survey', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          disappointmentLevel: disappointment,
          idealCustomer: idealCustomer.trim() || null,
          mainBenefit: mainBenefit.trim() || null,
          improvements: improvements.trim() || null,
        }),
      });

      onComplete();
    } catch (err) {
      console.error('Failed to submit PMF survey:', err);
      alert('Failed to submit survey. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        
        {step === 'main' && (
          <div className="p-8">
            <div className="mb-6">
              <h2 className="font-serif text-2xl font-bold text-slate-900 mb-2">
                Quick question
              </h2>
              <p className="text-stone-600 leading-relaxed">
                You've been using Winzinvest for a couple weeks now. We'd love your honest feedback.
              </p>
            </div>

            <div className="mb-8">
              <div className="font-semibold text-slate-900 mb-4">
                How would you feel if you could no longer use Winzinvest?
              </div>
              
              <div className="space-y-3">
                <button
                  onClick={() => handleMainQuestion('very')}
                  className="w-full p-4 text-left rounded-lg border-2 border-stone-200 hover:border-green-500 hover:bg-green-50 transition-colors focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2"
                >
                  <div className="font-semibold text-slate-900 mb-1">Very disappointed</div>
                  <div className="text-sm text-stone-600">I'd have a hard time without it</div>
                </button>

                <button
                  onClick={() => handleMainQuestion('somewhat')}
                  className="w-full p-4 text-left rounded-lg border-2 border-stone-200 hover:border-yellow-500 hover:bg-yellow-50 transition-colors focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:ring-offset-2"
                >
                  <div className="font-semibold text-slate-900 mb-1">Somewhat disappointed</div>
                  <div className="text-sm text-stone-600">I'd miss it but could find alternatives</div>
                </button>

                <button
                  onClick={() => handleMainQuestion('not')}
                  className="w-full p-4 text-left rounded-lg border-2 border-stone-200 hover:border-stone-300 hover:bg-stone-50 transition-colors focus:outline-none focus:ring-2 focus:ring-stone-400 focus:ring-offset-2"
                >
                  <div className="font-semibold text-slate-900 mb-1">Not disappointed</div>
                  <div className="text-sm text-stone-600">It wouldn't really affect me</div>
                </button>
              </div>
            </div>

            <div className="text-right">
              <button
                onClick={onClose}
                className="text-sm text-stone-500 hover:text-slate-900 transition-colors"
              >
                Maybe later
              </button>
            </div>
          </div>
        )}

        {step === 'followup' && (
          <div className="p-8">
            <div className="mb-6">
              <h2 className="font-serif text-2xl font-bold text-slate-900 mb-2">
                Three more quick questions
              </h2>
              <p className="text-stone-600 leading-relaxed">
                Your feedback helps us improve the system for everyone.
              </p>
            </div>

            <div className="space-y-6 mb-8">
              <div>
                <label htmlFor="ideal-customer" className="block font-semibold text-sm text-slate-900 mb-2">
                  1. What type of person would most benefit from Winzinvest?
                </label>
                <input
                  id="ideal-customer"
                  type="text"
                  value={idealCustomer}
                  onChange={(e) => setIdealCustomer(e.target.value)}
                  placeholder="e.g., swing traders with full-time jobs"
                  className="w-full px-4 py-2.5 rounded-lg border border-stone-300 focus:outline-none focus:ring-2 focus:ring-primary-600 focus:border-transparent text-slate-900"
                />
              </div>

              <div>
                <label htmlFor="main-benefit" className="block font-semibold text-sm text-slate-900 mb-2">
                  2. What is the main benefit you receive from Winzinvest?
                </label>
                <input
                  id="main-benefit"
                  type="text"
                  value={mainBenefit}
                  onChange={(e) => setMainBenefit(e.target.value)}
                  placeholder="e.g., removes emotion from execution"
                  className="w-full px-4 py-2.5 rounded-lg border border-stone-300 focus:outline-none focus:ring-2 focus:ring-primary-600 focus:border-transparent text-slate-900"
                />
              </div>

              <div>
                <label htmlFor="improvements" className="block font-semibold text-sm text-slate-900 mb-2">
                  3. How can we improve Winzinvest for you?
                </label>
                <textarea
                  id="improvements"
                  value={improvements}
                  onChange={(e) => setImprovements(e.target.value)}
                  placeholder="Be specific: features, bugs, confusing parts, etc."
                  rows={4}
                  className="w-full px-4 py-2.5 rounded-lg border border-stone-300 focus:outline-none focus:ring-2 focus:ring-primary-600 focus:border-transparent text-slate-900 resize-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-between">
              <button
                onClick={onClose}
                className="text-sm text-stone-500 hover:text-slate-900 transition-colors"
              >
                Skip for now
              </button>
              <button
                onClick={handleSubmit}
                disabled={submitting}
                className="px-6 py-2.5 rounded-lg bg-primary-600 hover:bg-primary-700 disabled:bg-stone-300 text-white font-semibold text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-primary-600 focus:ring-offset-2"
              >
                {submitting ? 'Submitting...' : 'Submit Feedback'}
              </button>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
