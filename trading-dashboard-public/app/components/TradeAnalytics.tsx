'use client';

interface TradeAnalyticsProps {
  analytics: {
    avg_mae: number;
    avg_mfe: number;
    avg_slippage_bps: number;
    avg_hold_time_hours: number;
    best_trade: number;
    worst_trade: number;
    largest_position: number;
  };
  performance: {
    avg_win: number;
    avg_loss: number;
    profit_factor: number;
  };
}

export default function TradeAnalytics({ analytics, performance }: TradeAnalyticsProps) {
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-6">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-6">
        Trade Analytics (30 Days)
      </h2>
      
      <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
        <Metric
          label="Avg MAE"
          value={`${analytics.avg_mae.toFixed(2)}%`}
          tooltip="Maximum Adverse Excursion - worst drawdown during trade"
        />
        <Metric
          label="Avg MFE"
          value={`${analytics.avg_mfe.toFixed(2)}%`}
          tooltip="Maximum Favorable Excursion - best profit during trade"
        />
        <Metric
          label="Avg Slippage"
          value={`${analytics.avg_slippage_bps.toFixed(1)} bps`}
          tooltip="Average difference between expected and actual fill price"
        />
        <Metric
          label="Avg Hold Time"
          value={`${analytics.avg_hold_time_hours.toFixed(1)}h`}
          tooltip="Average time positions are held"
        />
        <Metric
          label="Profit Factor"
          value={performance.profit_factor.toFixed(2)}
          tooltip="Gross profit / Gross loss ratio"
        />
        <Metric
          label="Avg Win"
          value={`$${performance.avg_win.toFixed(0)}`}
          tooltip="Average winning trade size"
        />
        <Metric
          label="Avg Loss"
          value={`$${performance.avg_loss.toFixed(0)}`}
          tooltip="Average losing trade size"
        />
        <Metric
          label="Best Trade"
          value={`$${analytics.best_trade.toFixed(0)}`}
          tooltip="Largest winning trade"
        />
        <Metric
          label="Worst Trade"
          value={`$${analytics.worst_trade.toFixed(0)}`}
          tooltip="Largest losing trade"
        />
      </div>
    </div>
  );
}

function Metric({ label, value, tooltip }: { label: string; value: string; tooltip?: string }) {
  return (
    <div className="group relative">
      <div className="text-xs text-stone-500 mb-1">{label}</div>
      <div className="font-mono text-lg font-bold text-slate-900">{value}</div>
      {tooltip && (
        <div className="absolute bottom-full left-0 mb-2 hidden group-hover:block bg-slate-900 text-white text-xs rounded px-3 py-2 w-48 z-10">
          {tooltip}
        </div>
      )}
    </div>
  );
}
