'use client';

import Tooltip from './Tooltip';

interface BacktestMetrics {
  sharpe: number;
  win_rate: number;
  max_drawdown: number;
  avg_return: number;
  total_trades: number;
}

interface BacktestComparisonProps {
  live: BacktestMetrics;
  /** From comprehensive_backtest --save, or a legacy fallback if no file yet. */
  backtest: BacktestMetrics;
  /** Shown under the table (e.g. backtest date and window). */
  benchmarkCaption?: string;
}

export default function BacktestComparison({ live, backtest, benchmarkCaption }: BacktestComparisonProps) {
  const metrics = [
    { key: 'sharpe', label: 'Sharpe Ratio', format: (v: number) => v.toFixed(2) },
    { key: 'win_rate', label: 'Win Rate', format: (v: number) => `${v.toFixed(1)}%` },
    { key: 'max_drawdown', label: 'Max Drawdown', format: (v: number) => `${v.toFixed(1)}%` },
    { key: 'avg_return', label: 'Avg P&L / Trade', format: (v: number) => `$${v.toFixed(0)}` },
    { key: 'total_trades', label: 'Total Trades', format: (v: number) => v.toString() },
  ];

  return (
    <div className="bg-white border border-slate-200 card-elevated rounded-xl p-6">
      <Tooltip text="Live uses your last 30 days of closed-book metrics. Backtest uses the latest comprehensive_backtest enhanced run (same logic as production), or a placeholder until you run --save." placement="above">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-600 mb-1">
          Live vs Backtest Performance
        </h2>
      </Tooltip>
      {benchmarkCaption ? (
        <p className="text-[11px] text-slate-400 mb-4 break-words font-mono leading-relaxed">
          {benchmarkCaption}
        </p>
      ) : null}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b border-slate-200">
            <tr>
              <th className="text-left py-3 px-4 font-semibold text-slate-600"><Tooltip text="Performance metric name" placement="above"><span className="inline-block">Metric</span></Tooltip></th>
              <th className="text-right py-3 px-4 font-semibold text-slate-600"><Tooltip text="Actual result from live trading (30 days)" placement="above"><span className="inline-block">Live (30d)</span></Tooltip></th>
              <th className="text-right py-3 px-4 font-semibold text-slate-600"><Tooltip text="Historical backtest result" placement="above"><span className="inline-block">Backtest</span></Tooltip></th>
              <th className="text-right py-3 px-4 font-semibold text-slate-600"><Tooltip text="Live minus backtest" placement="above"><span className="inline-block">Difference</span></Tooltip></th>
              <th className="text-center py-3 px-4 font-semibold text-slate-600"><Tooltip text="On Track = close to backtest; Diverging = material difference" placement="above"><span className="inline-block">Status</span></Tooltip></th>
            </tr>
          </thead>
          <tbody>
            {metrics.map(({ key, label, format }) => {
              const liveVal = live[key as keyof BacktestMetrics];
              const btVal = backtest[key as keyof BacktestMetrics];
              const diff = liveVal - btVal;
              const diffPct = btVal !== 0 ? (diff / btVal) * 100 : 0;

              const isGood =
                (key === 'max_drawdown' && diff < 0) ||
                (key !== 'max_drawdown' && diff > 0);

              const isClose = Math.abs(diffPct) < 10;

              return (
                <tr key={key} className="border-b border-slate-100 hover:bg-sky-50/30 transition-colors">
                  <td className="py-3 px-4 font-semibold text-slate-900">{label}</td>
                  <td className="py-3 px-4 text-right font-mono text-slate-900">{format(liveVal)}</td>
                  <td className="py-3 px-4 text-right font-mono text-slate-500">{format(btVal)}</td>
                  <td className={`py-3 px-4 text-right font-mono font-semibold ${isGood ? 'text-green-600' : 'text-red-600'}`}>
                    {diff > 0 ? '+' : ''}{format(diff)}
                  </td>
                  <td className="py-3 px-4 text-center">
                    <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                      isClose && isGood ? 'bg-green-100 text-green-700' :
                      isClose ? 'bg-orange-100 text-orange-700' :
                      'bg-red-100 text-red-700'
                    }`}>
                      {isClose && isGood ? 'On Track' : isClose ? 'Close' : 'Diverging'}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="mt-6 p-4 bg-slate-50 rounded-lg border border-slate-100">
        <Tooltip text="Summary of whether live results align with backtest expectations." placement="above">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-600 mb-2">
            Analysis
          </h3>
        </Tooltip>
        <p className="text-sm text-slate-600">
          {live.sharpe > backtest.sharpe * 0.9
            ? 'Live performance is tracking backtest expectations well.'
            : 'Live performance is diverging from backtest. Consider reviewing strategy parameters.'}
        </p>
      </div>
    </div>
  );
}
