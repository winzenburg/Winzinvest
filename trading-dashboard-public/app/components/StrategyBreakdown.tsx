'use client';

interface Strategy {
  trades: number;
  pnl: number;
  wins: number;
  losses: number;
  win_rate: number;
}

interface StrategyBreakdownProps {
  strategies: Record<string, Strategy>;
}

export default function StrategyBreakdown({ strategies }: StrategyBreakdownProps) {
  const strategyNames: Record<string, string> = {
    momentum_long: 'Momentum Long',
    momentum_short: 'Momentum Short',
    mean_reversion: 'Mean Reversion',
    pairs: 'Pairs Trading',
    options: 'Options',
    webhook: 'Webhook Signals',
  };

  const sortedStrategies = Object.entries(strategies)
    .filter(([, data]) => data.trades > 0)
    .sort(([, a], [, b]) => b.pnl - a.pnl);

  const totalPnL = sortedStrategies.reduce((sum, [, data]) => sum + data.pnl, 0);

  return (
    <div className="bg-white border border-stone-200 rounded-xl p-6">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-6">
        Strategy Performance (30 Days)
      </h2>
      
      <div className="space-y-4">
        {sortedStrategies.map(([key, data]) => {
          const contributionPct = totalPnL !== 0 ? (data.pnl / totalPnL) * 100 : 0;
          
          return (
            <div key={key} className="border border-stone-200 rounded-lg p-4">
              <div className="flex justify-between items-start mb-3">
                <div>
                  <div className="font-semibold text-slate-900 mb-1">
                    {strategyNames[key] || key}
                  </div>
                  <div className="text-xs text-stone-500">
                    {data.trades} trades • {data.wins}W / {data.losses}L
                  </div>
                </div>
                <div className="text-right">
                  <div className={`font-serif text-xl font-bold ${
                    data.pnl >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {data.pnl >= 0 ? '+' : ''}${data.pnl.toFixed(0)}
                  </div>
                  <div className="text-xs text-stone-500">
                    {contributionPct >= 0 ? '+' : ''}{contributionPct.toFixed(1)}%
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-stone-500">Win Rate:</span>
                  <span className="ml-2 font-semibold text-slate-900">
                    {data.win_rate.toFixed(1)}%
                  </span>
                </div>
                <div>
                  <span className="text-stone-500">Avg P&L:</span>
                  <span className={`ml-2 font-semibold ${
                    data.pnl / data.trades >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}>
                    ${(data.pnl / data.trades).toFixed(0)}
                  </span>
                </div>
              </div>

              <div className="mt-3 w-full h-2 bg-stone-100 rounded-full overflow-hidden">
                <div
                  className={`h-full ${data.pnl >= 0 ? 'bg-green-500' : 'bg-red-500'}`}
                  style={{ width: `${Math.min(100, Math.abs(contributionPct))}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {sortedStrategies.length === 0 && (
        <div className="text-center text-stone-400 py-8">
          No strategy data available
        </div>
      )}
    </div>
  );
}
