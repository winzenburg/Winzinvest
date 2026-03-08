'use client';

interface BacktestMetrics {
  sharpe: number;
  win_rate: number;
  max_drawdown: number;
  avg_return: number;
  total_trades: number;
}

interface BacktestComparisonProps {
  live: BacktestMetrics;
  backtest: BacktestMetrics;
}

export default function BacktestComparison({ live, backtest }: BacktestComparisonProps) {
  const metrics = [
    { key: 'sharpe', label: 'Sharpe Ratio', format: (v: number) => v.toFixed(2) },
    { key: 'win_rate', label: 'Win Rate', format: (v: number) => `${v.toFixed(1)}%` },
    { key: 'max_drawdown', label: 'Max Drawdown', format: (v: number) => `${v.toFixed(1)}%` },
    { key: 'avg_return', label: 'Avg Return/Trade', format: (v: number) => `${v.toFixed(2)}%` },
    { key: 'total_trades', label: 'Total Trades', format: (v: number) => v.toString() },
  ];

  return (
    <div className="bg-white border border-stone-200 rounded-xl p-6">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-6">
        Live vs Backtest Performance
      </h2>
      
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b border-stone-200">
            <tr>
              <th className="text-left py-3 px-4 font-semibold text-stone-600">Metric</th>
              <th className="text-right py-3 px-4 font-semibold text-stone-600">Live (30d)</th>
              <th className="text-right py-3 px-4 font-semibold text-stone-600">Backtest</th>
              <th className="text-right py-3 px-4 font-semibold text-stone-600">Difference</th>
              <th className="text-center py-3 px-4 font-semibold text-stone-600">Status</th>
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
                <tr key={key} className="border-b border-stone-100 hover:bg-stone-50">
                  <td className="py-3 px-4 font-semibold text-slate-900">{label}</td>
                  <td className="py-3 px-4 text-right font-mono text-slate-900">
                    {format(liveVal)}
                  </td>
                  <td className="py-3 px-4 text-right font-mono text-stone-600">
                    {format(btVal)}
                  </td>
                  <td className={`py-3 px-4 text-right font-mono font-semibold ${
                    isGood ? 'text-green-600' : 'text-red-600'
                  }`}>
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

      <div className="mt-6 p-4 bg-stone-50 rounded-lg">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">
          Analysis
        </h3>
        <p className="text-sm text-stone-700">
          {live.sharpe > backtest.sharpe * 0.9 
            ? 'Live performance is tracking backtest expectations well.'
            : 'Live performance is diverging from backtest. Consider reviewing strategy parameters.'}
        </p>
      </div>
    </div>
  );
}
