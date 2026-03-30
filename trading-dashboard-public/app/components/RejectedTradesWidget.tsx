'use client';

/**
 * Rejected Trades Widget — System Risk Management Transparency
 * 
 * Shows signals the system blocked and why. Builds trust by proving
 * risk gates are working. Satisfies curiosity about what could have been.
 * 
 * Framework: Core Drive 8 (Loss Avoidance) + transparency
 */

interface RejectedSignal {
  symbol: string;
  reason: string;
  conviction?: number;
  rejectedAt: string;
  estimatedSavings?: number;
}

interface RejectedTradesData {
  period: string;              // "Today" | "This Week" | "This Month"
  totalScreened: number;
  totalExecuted: number;
  totalBlocked: number;
  reasons: Array<{
    reason: string;
    count: number;
    pct: number;
  }>;
  recentSignals: RejectedSignal[];
  estimatedTotalSavings?: number;
}

interface RejectedTradesWidgetProps {
  data?: RejectedTradesData | null;
  className?: string;
}

const REASON_ICONS: Record<string, string> = {
  conviction: '📊',
  sector: '🎯',
  regime: '🌡️',
  budget: '💼',
  'daily loss': '🛑',
  timing: '⏰',
  default: '🛡️',
};

function getReasonIcon(reason: string): string {
  const lower = reason.toLowerCase();
  for (const [key, icon] of Object.entries(REASON_ICONS)) {
    if (lower.includes(key)) return icon;
  }
  return REASON_ICONS.default;
}

export default function RejectedTradesWidget({ data, className = '' }: RejectedTradesWidgetProps) {
  if (!data) {
    return (
      <div className={`rounded-xl border border-stone-200 bg-white p-8 ${className}`}>
        <h2 className="font-serif text-2xl font-bold text-slate-900 mb-4">
          System Risk Management
        </h2>
        <p className="text-stone-600">
          No rejected signals yet. Check back after the next screening run.
        </p>
      </div>
    );
  }

  const { 
    period, 
    totalScreened, 
    totalExecuted, 
    totalBlocked, 
    reasons = [], 
    recentSignals = [], 
    estimatedTotalSavings 
  } = data;
  const blockRate = totalScreened > 0 ? (totalBlocked / totalScreened) * 100 : 0;

  return (
    <div className={`rounded-xl border border-stone-200 bg-white p-8 ${className}`}>
      {/* Header */}
      <div className="mb-6">
        <h2 className="font-serif text-2xl font-bold text-slate-900 mb-2">
          System Risk Management
        </h2>
        <p className="text-sm text-stone-600">
          {period} activity — showing what the system blocked and why
        </p>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="text-center p-4 rounded-lg bg-blue-50">
          <div className="text-3xl font-bold text-blue-600">
            {totalScreened}
          </div>
          <div className="text-xs uppercase tracking-wide text-blue-700 mt-1">
            Screened
          </div>
        </div>
        
        <div className="text-center p-4 rounded-lg bg-green-50">
          <div className="text-3xl font-bold text-green-600">
            {totalExecuted}
          </div>
          <div className="text-xs uppercase tracking-wide text-green-700 mt-1">
            Executed
          </div>
        </div>
        
        <div className="text-center p-4 rounded-lg bg-amber-50">
          <div className="text-3xl font-bold text-amber-600">
            {totalBlocked}
          </div>
          <div className="text-xs uppercase tracking-wide text-amber-700 mt-1">
            Blocked
          </div>
        </div>
      </div>

      {/* Block rate and savings */}
      <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg mb-6">
        <div>
          <div className="text-sm text-stone-600 mb-1">
            Block Rate
          </div>
          <div className="text-2xl font-bold text-slate-900">
            {blockRate.toFixed(1)}%
          </div>
        </div>
        
        {estimatedTotalSavings !== undefined && estimatedTotalSavings > 0 && (
          <div className="text-right">
            <div className="text-sm text-stone-600 mb-1">
              Estimated Saves
            </div>
            <div className="text-2xl font-bold text-green-600">
              ${estimatedTotalSavings.toLocaleString()}
            </div>
          </div>
        )}
      </div>

      {/* Rejection reasons breakdown */}
      {reasons.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-stone-600 mb-3">
            Why Signals Were Blocked
          </h3>
          <div className="space-y-2">
            {reasons.map((r) => (
              <div
                key={r.reason}
                className="flex items-center justify-between p-3 rounded-lg bg-stone-50"
              >
                <div className="flex items-center gap-2">
                  <span className="text-xl">{getReasonIcon(r.reason)}</span>
                  <span className="text-sm text-slate-900">
                    {r.reason}
                  </span>
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-sm font-bold text-slate-900">
                    {r.count}
                  </span>
                  <span className="text-xs text-stone-500">
                    ({r.pct.toFixed(0)}%)
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent rejected signals */}
      {recentSignals.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wider text-stone-600 mb-3">
            Recent Blocked Signals
          </h3>
          <div className="space-y-2">
            {recentSignals.slice(0, 5).map((signal, idx) => (
              <div
                key={idx}
                className="flex items-start justify-between p-3 rounded-lg border border-stone-200 hover:border-stone-300 transition-colors"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-mono font-bold text-slate-900">
                      {signal.symbol}
                    </span>
                    {signal.conviction !== undefined && (
                      <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                        Conv: {(signal.conviction * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-stone-600">
                    {signal.reason}
                  </p>
                  {signal.estimatedSavings !== undefined && signal.estimatedSavings > 0 && (
                    <p className="text-xs text-green-600 mt-1">
                      Est. saved: ${signal.estimatedSavings}
                    </p>
                  )}
                </div>
                <div className="text-xs text-stone-400 flex-shrink-0 ml-4">
                  {new Date(signal.rejectedAt).toLocaleTimeString('en-US', { 
                    hour: 'numeric', 
                    minute: '2-digit' 
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {totalBlocked === 0 && (
        <div className="text-center py-8 text-stone-500">
          <div className="text-4xl mb-2">✓</div>
          <p className="text-sm">
            All screened signals passed risk gates. System executed {totalExecuted} trades.
          </p>
        </div>
      )}
    </div>
  );
}
