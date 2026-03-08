'use client';

interface RiskMetricsProps {
  risk: {
    sector_exposure: Record<string, number>;
    beta: number;
    correlation_spy: number;
    margin_utilization_pct: number;
    buying_power_used_pct: number;
  };
  performance: {
    var_95: number;
    cvar_95: number;
    var_99: number;
    cvar_99: number;
    max_drawdown_pct: number;
  };
}

export default function RiskMetrics({ risk, performance }: RiskMetricsProps) {
  const topSectors = Object.entries(risk.sector_exposure || {})
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Risk Metrics */}
      <div className="bg-white border border-stone-200 rounded-xl p-6">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-6">
          Risk Metrics
        </h2>
        <div className="space-y-4">
          <MetricRow label="VaR (95%)" value={`${performance.var_95.toFixed(2)}%`} />
          <MetricRow label="CVaR (95%)" value={`${performance.cvar_95.toFixed(2)}%`} />
          <MetricRow label="VaR (99%)" value={`${performance.var_99.toFixed(2)}%`} />
          <MetricRow label="CVaR (99%)" value={`${performance.cvar_99.toFixed(2)}%`} />
          <MetricRow label="Max Drawdown" value={`${performance.max_drawdown_pct.toFixed(2)}%`} />
          <MetricRow label="Beta (vs SPY)" value={risk.beta.toFixed(2)} />
          <MetricRow label="Correlation (SPY)" value={risk.correlation_spy.toFixed(2)} />
        </div>
      </div>

      {/* Margin & Exposure */}
      <div className="bg-white border border-stone-200 rounded-xl p-6">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-6">
          Margin & Leverage
        </h2>
        <div className="space-y-4">
          <div>
            <div className="flex justify-between text-sm mb-2">
              <span className="text-stone-600">Margin Utilization</span>
              <span className={`font-semibold ${
                risk.margin_utilization_pct > 80 ? 'text-red-600' : 
                risk.margin_utilization_pct > 60 ? 'text-orange-600' : 
                'text-green-600'
              }`}>
                {risk.margin_utilization_pct.toFixed(1)}%
              </span>
            </div>
            <div className="w-full h-3 bg-stone-100 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all ${
                  risk.margin_utilization_pct > 80 ? 'bg-red-500' :
                  risk.margin_utilization_pct > 60 ? 'bg-orange-500' :
                  'bg-green-500'
                }`}
                style={{ width: `${Math.min(100, risk.margin_utilization_pct)}%` }}
              />
            </div>
          </div>

          <div>
            <div className="flex justify-between text-sm mb-2">
              <span className="text-stone-600">Buying Power Used</span>
              <span className="font-semibold text-stone-900">
                {risk.buying_power_used_pct.toFixed(1)}%
              </span>
            </div>
            <div className="w-full h-3 bg-stone-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-sky-500 transition-all"
                style={{ width: `${Math.min(100, risk.buying_power_used_pct)}%` }}
              />
            </div>
          </div>
        </div>

        <div className="mt-6 pt-6 border-t border-stone-200">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-4">
            Top Sector Exposures
          </h3>
          <div className="space-y-3">
            {topSectors.map(([sector, pct]) => (
              <div key={sector}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-stone-600">{sector}</span>
                  <span className={`font-semibold ${
                    pct > 30 ? 'text-red-600' : 'text-stone-900'
                  }`}>
                    {pct.toFixed(1)}%
                  </span>
                </div>
                <div className="w-full h-2 bg-stone-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${pct > 30 ? 'bg-red-500' : 'bg-blue-500'}`}
                    style={{ width: `${Math.min(100, pct)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-sm text-stone-600">{label}</span>
      <span className="font-mono text-sm font-semibold text-slate-900">{value}</span>
    </div>
  );
}
