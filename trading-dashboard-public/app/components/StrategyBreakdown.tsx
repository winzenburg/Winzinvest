'use client';

import Tooltip from './Tooltip';

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
    // Canonical keys (from dashboard_data_aggregator strategy mapping)
    momentum_long: 'Momentum Long',
    momentum_short: 'Momentum Short',
    mean_reversion: 'Mean Reversion',
    pairs: 'Pairs Trading',
    options: 'Options Premium',
    webhook: 'Webhook Signals',
    // Script-name keys (fallback when aggregator uses raw script names)
    'execute_longs.py': 'Momentum Long',
    'execute_dual_mode.py': 'Momentum Long',
    'execute_shorts.py': 'Momentum Short',
    'execute_mean_reversion.py': 'Mean Reversion',
    'execute_pairs.py': 'Pairs Trading',
    'auto_options_executor.py': 'Options Premium',
    'run_combined_strategy.py': 'Options Premium',
    'execute_options.py': 'Options Premium',
    'execute_high_iv_csp.py': 'High-IV CSP',
    'webhook_receiver.py': 'Webhook Signals',
    'execute_webhook_signal.py': 'Webhook Signals',
  };

  const sortedStrategies = Object.entries(strategies)
    .filter(([, data]) => data.trades > 0)
    .sort(([, a], [, b]) => b.pnl - a.pnl);

  const totalPnL = sortedStrategies.reduce((sum, [, data]) => sum + data.pnl, 0);

  return (
    <div className="bg-white border border-slate-200 card-elevated rounded-xl p-6">
      <Tooltip text="P&L and win rate by strategy type over the last 30 days." placement="above">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-600 mb-6">
          Strategy Performance (30 Days)
        </h2>
      </Tooltip>
      
      <div className="space-y-4">
        {sortedStrategies.map(([key, data]) => {
          const contributionPct = totalPnL !== 0 ? (data.pnl / totalPnL) * 100 : 0;
          
          return (
            <div key={key} className="border border-slate-200 rounded-lg p-4">
              <div className="flex justify-between items-start mb-3">
                <div>
                  <div className="font-semibold text-slate-900 mb-1">
                    {strategyNames[key] || key}
                  </div>
                  <div className="text-xs text-slate-600">
                    {data.trades} trades • {data.wins}W / {data.losses}L
                  </div>
                </div>
                <div className="text-right">
                  <div className={`font-serif text-xl font-bold ${data.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {data.pnl >= 0 ? '+' : ''}${data.pnl.toFixed(0)}
                  </div>
                  <div className="text-xs text-slate-600">
                    {contributionPct >= 0 ? '+' : ''}{contributionPct.toFixed(1)}%
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <Tooltip text="Percent of trades that were profitable" placement="above">
                    <span className="text-slate-600">Win Rate:</span>
                  </Tooltip>
                  <span className="ml-2 font-semibold text-slate-900">
                    {data.win_rate.toFixed(1)}%
                  </span>
                </div>
                <div>
                  <Tooltip text="Average profit or loss per trade for this strategy" placement="above">
                    <span className="text-slate-600">Avg P&L:</span>
                  </Tooltip>
                  <span className={`ml-2 font-semibold ${data.pnl / data.trades >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    ${(data.pnl / data.trades).toFixed(0)}
                  </span>
                </div>
              </div>

              <div className="mt-3 w-full h-2 bg-slate-100 rounded-full overflow-hidden">
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
