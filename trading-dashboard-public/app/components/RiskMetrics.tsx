'use client';

import Tooltip from './Tooltip';

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
  nlv: number;
}

export default function RiskMetrics({ risk, performance, nlv }: RiskMetricsProps) {
  // sector_exposure values are in dollars — convert to % of NLV for display
  const topSectors = Object.entries(risk.sector_exposure || {})
    .map(([sector, dollars]): [string, number] => [sector, nlv > 0 ? (Math.abs(dollars) / nlv) * 100 : 0])
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Risk Metrics */}
      <div className="bg-white border border-stone-200 rounded-xl p-6 card-elevated">
        <Tooltip text="VaR, CVaR, drawdown, and market sensitivity. From historical returns." placement="above">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-600 mb-6">
            Risk Metrics
          </h2>
        </Tooltip>
        <div className="space-y-4">
          <MetricRow label="VaR (95%)" value={`${performance.var_95.toFixed(2)}%`} title="Value at Risk (95%): max expected daily loss at 95% confidence. From historical returns." />
          <MetricRow label="CVaR (95%)" value={`${performance.cvar_95.toFixed(2)}%`} title="Conditional VaR: expected loss when loss exceeds VaR (95%). Tail risk measure." />
          <MetricRow label="VaR (99%)" value={`${performance.var_99.toFixed(2)}%`} title="Value at Risk (99%): max expected daily loss at 99% confidence." />
          <MetricRow label="CVaR (99%)" value={`${performance.cvar_99.toFixed(2)}%`} title="Conditional VaR (99%): expected loss in worst 1% of days." />
          <MetricRow label="Max Drawdown" value={`${performance.max_drawdown_pct.toFixed(2)}%`} title="Largest peak-to-trough decline over the period." />
          <MetricRow label="Beta (vs SPY)" value={risk.beta.toFixed(2)} title="Sensitivity to SPY. Beta 1 = moves with market; >1 = more volatile." />
          <MetricRow label="Correlation (SPY)" value={risk.correlation_spy.toFixed(2)} title="Correlation of portfolio returns with SPY (-1 to 1)." />
        </div>
      </div>

      {/* Margin & Exposure */}
      <div className="bg-white border border-stone-200 rounded-xl p-6 card-elevated">
        <Tooltip text="How much of your margin and buying power is in use." placement="above">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-600 mb-6">
            Margin & Leverage
          </h2>
        </Tooltip>
        <div className="space-y-4">
          <div>
            <div className="flex justify-between text-sm mb-2">
              <Tooltip text="Portion of margin requirement currently used. High values increase margin-call risk." placement="above">
                <span className="text-stone-600">Margin Utilization</span>
              </Tooltip>
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
              <Tooltip text="Share of available buying power committed to positions." placement="above">
                <span className="text-stone-600">Buying Power Used</span>
              </Tooltip>
              <span className="font-semibold text-slate-900">
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
          <Tooltip text="Portfolio weight by sector. High concentration in one sector increases concentration risk." placement="above">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-4">
              Top Sector Exposures
            </h3>
          </Tooltip>
          <div className="space-y-3">
            {topSectors.map(([sector, pct]) => (
              <div key={sector}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-stone-600">{sector}</span>
                  <span className={`font-semibold ${
                    pct > 45 ? 'text-red-600' : pct > 30 ? 'text-orange-600' : 'text-slate-900'
                  }`}>
                    {pct.toFixed(1)}%
                  </span>
                </div>
                <div className="w-full h-2 bg-stone-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${pct > 45 ? 'bg-red-500' : pct > 30 ? 'bg-orange-400' : 'bg-blue-500'}`}
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

function MetricRow({ label, value, title }: { label: string; value: string; title?: string }) {
  const labelEl = <span className="text-sm text-stone-600">{label}</span>;
  return (
    <div className="flex justify-between items-center">
      {title ? (
        <Tooltip text={title} placement="above">
          {labelEl}
        </Tooltip>
      ) : (
        labelEl
      )}
      <span className="font-mono text-sm font-semibold text-slate-900">{value}</span>
    </div>
  );
}
