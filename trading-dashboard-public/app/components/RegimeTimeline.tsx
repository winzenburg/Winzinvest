'use client';

/**
 * Regime History Timeline — Market Context Visualization
 * 
 * Shows how market regime has shifted over time and how the system adapted.
 * Helps users understand why performance varies across periods.
 * 
 * Framework: Pattern recognition via historical context
 */

import { useEffect, useState } from 'react';

interface RegimeEntry {
  timestamp: string;
  regime: string;
  note: string;
}

interface RegimeTimelineProps {
  days?: number;
  className?: string;
}

const REGIME_COLORS: Record<string, { bg: string; border: string; text: string; dot: string }> = {
  STRONG_UPTREND: {
    bg: 'bg-green-50',
    border: 'border-green-300',
    text: 'text-green-800',
    dot: 'bg-green-500',
  },
  CHOPPY: {
    bg: 'bg-blue-50',
    border: 'border-blue-300',
    text: 'text-blue-800',
    dot: 'bg-blue-500',
  },
  MIXED: {
    bg: 'bg-amber-50',
    border: 'border-amber-300',
    text: 'text-amber-800',
    dot: 'bg-amber-500',
  },
  STRONG_DOWNTREND: {
    bg: 'bg-red-50',
    border: 'border-red-300',
    text: 'text-red-800',
    dot: 'bg-red-500',
  },
  UNFAVORABLE: {
    bg: 'bg-stone-50',
    border: 'border-stone-300',
    text: 'text-stone-700',
    dot: 'bg-stone-400',
  },
};

export default function RegimeTimeline({ days = 90, className = '' }: RegimeTimelineProps) {
  const [history, setHistory] = useState<RegimeEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const res = await fetch(`/api/regime-history?days=${days}`, {
          credentials: 'include',
        });
        
        if (res.ok) {
          const data = await res.json();
          setHistory(data.history || []);
        }
      } catch (err) {
        console.error('Error fetching regime history:', err);
      } finally {
        setLoading(false);
      }
    };
    
    fetchHistory();
  }, [days]);

  if (loading) {
    return (
      <div className={`rounded-xl border border-stone-200 bg-white p-8 ${className}`}>
        <div className="animate-pulse">
          <div className="h-6 bg-stone-200 rounded w-1/3 mb-4" />
          <div className="space-y-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-16 bg-stone-100 rounded" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (history.length === 0) {
    return (
      <div className={`rounded-xl border border-stone-200 bg-white p-8 ${className}`}>
        <h2 className="font-serif text-2xl font-bold text-slate-900 mb-4">
          Regime History
        </h2>
        <p className="text-stone-600">
          No regime history available yet. Check back after the system has been running for a few days.
        </p>
      </div>
    );
  }

  return (
    <div className={`rounded-xl border border-stone-200 bg-white p-8 ${className}`}>
      <div className="mb-6">
        <h2 className="font-serif text-2xl font-bold text-slate-900 mb-2">
          Regime History
        </h2>
        <p className="text-sm text-stone-600">
          Market environment shifts over the last {days} days — how the system adapted
        </p>
      </div>

      <div className="relative">
        {/* Timeline line */}
        <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-stone-200" />

        {/* Timeline entries */}
        <div className="space-y-6">
          {history.map((entry, idx) => {
            const colors = REGIME_COLORS[entry.regime] || REGIME_COLORS.MIXED;
            const date = new Date(entry.timestamp);
            const isRecent = idx === 0;
            
            return (
              <div key={idx} className="relative pl-12">
                {/* Dot on timeline */}
                <div className={`absolute left-2 top-2 w-4 h-4 rounded-full ${colors.dot} border-2 border-white ${
                  isRecent ? 'ring-2 ring-offset-2 ring-' + colors.dot.split('-')[1] + '-300' : ''
                }`} />

                {/* Content card */}
                <div className={`rounded-lg border ${colors.border} ${colors.bg} p-4`}>
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <div className={`inline-block text-xs font-bold uppercase tracking-wider ${colors.text} px-2 py-1 rounded ${colors.bg} border ${colors.border}`}>
                        {entry.regime.replace(/_/g, ' ')}
                      </div>
                      {isRecent && (
                        <span className="ml-2 text-xs font-semibold text-slate-600">
                          Current
                        </span>
                      )}
                    </div>
                    <time className="text-xs text-stone-500">
                      {date.toLocaleDateString('en-US', { 
                        month: 'short', 
                        day: 'numeric',
                        year: date.getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined,
                      })}
                    </time>
                  </div>

                  {entry.note && (
                    <p className={`text-sm ${colors.text} leading-relaxed`}>
                      {entry.note}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Legend */}
      <div className="mt-8 pt-6 border-t border-stone-200">
        <div className="flex flex-wrap gap-3 text-xs">
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-green-500" />
            <span className="text-stone-600">Strong Uptrend</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-blue-500" />
            <span className="text-stone-600">Choppy</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-amber-500" />
            <span className="text-stone-600">Mixed</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-red-500" />
            <span className="text-stone-600">Strong Downtrend</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-stone-400" />
            <span className="text-stone-600">Unfavorable</span>
          </div>
        </div>
      </div>
    </div>
  );
}
