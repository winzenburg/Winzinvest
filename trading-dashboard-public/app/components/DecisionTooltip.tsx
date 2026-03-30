'use client';

/**
 * Decision Tooltip — "Why Did the System Do This?"
 * 
 * Educational overlay explaining system decisions.
 * Builds trust and understanding through transparency.
 * 
 * Framework: Core Drive 2 (Development & Accomplishment) via learning
 */

import { useState, useEffect } from 'react';

interface DecisionTooltipProps {
  symbol: string;
  type?: 'entry' | 'stop' | 'exit';
  className?: string;
}

interface PositionContext {
  entry_explanation: string;
  stop_explanation?: string | null;
  holding_days?: number | null;
  strategy: string;
  entry_date: string;
}

export default function DecisionTooltip({ symbol, type = 'entry', className = '' }: DecisionTooltipProps) {
  const [context, setContext] = useState<PositionContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [showTooltip, setShowTooltip] = useState(false);

  useEffect(() => {
    const fetchContext = async () => {
      try {
        const res = await fetch(`/api/decision-context?symbol=${symbol}`, {
          credentials: 'include',
        });
        
        if (res.ok) {
          const data = await res.json();
          // API returns { context } for symbol queries; tolerate { position } if ever unproxied
          const raw =
            data.context ?? data.position ?? null;
          setContext(raw);
        }
      } catch (err) {
        console.error('Error fetching decision context:', err);
      } finally {
        setLoading(false);
      }
    };
    
    fetchContext();
  }, [symbol]);

  if (loading || !context) {
    return null;
  }

  const explanation = type === 'stop' ? context.stop_explanation : context.entry_explanation;
  
  if (!explanation) {
    return null;
  }

  return (
    <div className={`relative inline-block ${className}`}>
      <button
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        onClick={() => setShowTooltip(!showTooltip)}
        className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-slate-200 hover:bg-slate-300 text-slate-600 hover:text-slate-900 transition-colors text-xs font-bold"
        aria-label="Why did the system do this?"
      >
        ?
      </button>

      {showTooltip && (
        <div className="absolute z-50 left-1/2 -translate-x-1/2 bottom-full mb-2 w-80 p-4 bg-slate-900 text-white text-sm rounded-lg shadow-xl">
          <div className="absolute left-1/2 -translate-x-1/2 top-full -mt-px w-0 h-0 border-l-8 border-r-8 border-t-8 border-transparent border-t-slate-900" />
          
          <div className="font-semibold mb-2 text-slate-100">
            Why {type === 'entry' ? 'We Entered' : type === 'stop' ? 'Stop Here' : 'We Exited'}: {symbol}
          </div>
          
          <p className="text-slate-300 leading-relaxed">
            {explanation}
          </p>
          
          {type === 'entry' && (
            <div className="mt-3 pt-3 border-t border-slate-700 text-xs text-slate-400">
              <div>Strategy: {context.strategy || 'Unknown'}</div>
              <div>
                Holding:{' '}
                {context.holding_days != null ? `${context.holding_days} days` : '—'}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
