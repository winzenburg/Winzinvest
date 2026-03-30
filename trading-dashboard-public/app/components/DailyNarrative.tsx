'use client';

/**
 * Daily Narrative — "What Happened Today"
 * 
 * Auto-generated natural language summary of system activity.
 * Primary engagement driver: satisfies curiosity without requiring action.
 * 
 * Framework: Hook Model (Variable Reward via curiosity)
 */

import { useEffect, useState } from 'react';

interface KeyDecision {
  action: 'entered' | 'exited' | 'blocked' | 'rolled' | 'adjusted';
  symbol: string;
  reason: string;
  detail?: string;
}

interface DailyNarrativeData {
  date: string;
  summary: string;
  regime: string;
  decisions: KeyDecision[];
  stats: {
    screened: number;
    executed: number;
    blocked: number;
  };
}

interface DailyNarrativeProps {
  data?: DailyNarrativeData | null;
  className?: string;
}

const ACTION_ICONS = {
  entered: '📈',
  exited: '💰',
  blocked: '🛡️',
  rolled: '🔄',
  adjusted: '⚙️',
};

const ACTION_LABELS = {
  entered: 'Entered',
  exited: 'Exited',
  blocked: 'Blocked',
  rolled: 'Rolled',
  adjusted: 'Adjusted',
};

const REGIME_COLORS: Record<string, string> = {
  STRONG_UPTREND: 'bg-green-100 text-green-800',
  CHOPPY: 'bg-yellow-100 text-yellow-800',
  MIXED: 'bg-orange-100 text-orange-800',
  STRONG_DOWNTREND: 'bg-red-100 text-red-800',
  UNFAVORABLE: 'bg-red-200 text-red-900',
};

export default function DailyNarrative({ data, className = '' }: DailyNarrativeProps) {
  const [expanded, setExpanded] = useState(false);

  if (!data) {
    return (
      <div className={`rounded-xl border border-stone-200 bg-white p-8 ${className}`}>
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-xl">
            📖
          </div>
          <h2 className="font-serif text-2xl font-bold text-slate-900">
            What Happened Today
          </h2>
        </div>
        <p className="text-stone-600 leading-relaxed">
          No activity yet. The system will update this after market close.
        </p>
      </div>
    );
  }

  const { summary, regime, decisions, stats } = data;
  const visibleDecisions = expanded ? decisions : decisions.slice(0, 3);
  const hasMore = decisions.length > 3;

  return (
    <div className={`rounded-xl border border-stone-200 bg-white p-8 ${className}`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-xl">
            📖
          </div>
          <div>
            <h2 className="font-serif text-2xl font-bold text-slate-900">
              What Happened Today
            </h2>
            <p className="text-sm text-stone-500 mt-1">
              {new Date(data.date).toLocaleDateString('en-US', { 
                weekday: 'long', 
                month: 'long', 
                day: 'numeric' 
              })}
            </p>
          </div>
        </div>

        {/* Regime badge */}
        <div className={`inline-flex items-center px-3 py-1.5 rounded-full text-xs font-semibold ${
          REGIME_COLORS[regime] || 'bg-stone-100 text-stone-700'
        }`}>
          {regime.replace(/_/g, ' ')}
        </div>
      </div>

      {/* Summary narrative */}
      <div className="prose prose-stone max-w-none mb-6">
        <p className="text-base leading-relaxed text-slate-700">
          {summary}
        </p>
      </div>

      {/* Stats bar */}
      <div className="flex items-center gap-6 p-4 bg-stone-50 rounded-lg mb-6">
        <div className="flex items-center gap-2">
          <span className="text-2xl font-bold text-slate-900">{stats.screened}</span>
          <span className="text-sm text-stone-600">Screened</span>
        </div>
        <div className="w-px h-8 bg-stone-300" />
        <div className="flex items-center gap-2">
          <span className="text-2xl font-bold text-green-600">{stats.executed}</span>
          <span className="text-sm text-stone-600">Executed</span>
        </div>
        <div className="w-px h-8 bg-stone-300" />
        <div className="flex items-center gap-2">
          <span className="text-2xl font-bold text-amber-600">{stats.blocked}</span>
          <span className="text-sm text-stone-600">Blocked</span>
        </div>
      </div>

      {/* Key decisions */}
      {decisions.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wider text-stone-600 mb-3">
            Key Decisions
          </h3>
          <div className="space-y-2">
            {visibleDecisions.map((decision, idx) => (
              <div
                key={idx}
                className="flex items-start gap-3 p-3 rounded-lg hover:bg-stone-50 transition-colors"
              >
                <div className="flex-shrink-0 text-2xl mt-0.5">
                  {ACTION_ICONS[decision.action]}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-2 mb-1">
                    <span className="font-semibold text-slate-900">
                      {ACTION_LABELS[decision.action]}
                    </span>
                    <span className="font-mono font-bold text-slate-700">
                      {decision.symbol}
                    </span>
                  </div>
                  <p className="text-sm text-stone-600 leading-relaxed">
                    {decision.reason}
                  </p>
                  {decision.detail && (
                    <p className="text-xs text-stone-500 mt-1">
                      {decision.detail}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Show more/less toggle */}
          {hasMore && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="mt-4 w-full py-2 text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors"
            >
              {expanded ? '↑ Show Less' : `↓ Show ${decisions.length - 3} More Decisions`}
            </button>
          )}
        </div>
      )}

      {/* Empty state */}
      {decisions.length === 0 && stats.executed === 0 && (
        <div className="text-center py-6 text-stone-500">
          No trades executed today. System is monitoring.
        </div>
      )}
    </div>
  );
}
