'use client';

/**
 * Portfolio Composition — Sector & Strategy Breakdown
 * 
 * Shows what the system is actually holding (transparency).
 * Helps users understand their exposure at a glance.
 * 
 * Framework: Trust building through visibility
 */

interface SectorExposure {
  sector: string;
  notional: number;
  pct: number;
  positionCount: number;
}

interface StrategyBreakdown {
  strategy: string;
  count: number;
  pct: number;
  notional: number;
}

interface PortfolioCompositionProps {
  sectors: SectorExposure[];
  strategies: StrategyBreakdown[];
  longNotional: number;
  shortNotional: number;
  netNotional: number;
  totalNotional: number;
  optionsPremium30d?: number;
  className?: string;
}

export default function PortfolioComposition({
  sectors,
  strategies,
  longNotional,
  shortNotional,
  netNotional,
  totalNotional,
  optionsPremium30d,
  className = '',
}: PortfolioCompositionProps) {
  // Sort sectors by notional (largest first)
  const sortedSectors = [...sectors].sort((a, b) => Math.abs(b.notional) - Math.abs(a.notional));
  const topSectors = sortedSectors.slice(0, 5);
  const otherSectors = sortedSectors.slice(5);
  const otherNotional = otherSectors.reduce((sum, s) => sum + Math.abs(s.notional), 0);
  const otherPct = otherSectors.reduce((sum, s) => sum + s.pct, 0);

  const displaySectors = topSectors;
  if (otherNotional > 0) {
    displaySectors.push({
      sector: 'Other',
      notional: otherNotional,
      pct: otherPct,
      positionCount: otherSectors.reduce((sum, s) => sum + s.positionCount, 0),
    });
  }

  // Color palette for sectors
  const SECTOR_COLORS = [
    'bg-blue-500',
    'bg-purple-500',
    'bg-pink-500',
    'bg-orange-500',
    'bg-teal-500',
    'bg-stone-400',
  ];

  // Calculate long/short balance bar
  const longPct = totalNotional > 0 ? (longNotional / totalNotional) * 100 : 50;
  const shortPct = totalNotional > 0 ? (Math.abs(shortNotional) / totalNotional) * 100 : 50;

  return (
    <div className={`rounded-xl border border-stone-200 bg-white p-8 ${className}`}>
      <h2 className="font-serif text-2xl font-bold text-slate-900 mb-6">
        Portfolio Composition
      </h2>

      {/* Sector breakdown */}
      <div className="mb-8">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-stone-600 mb-4">
          By Sector
        </h3>
        
        {displaySectors.length > 0 ? (
          <div className="space-y-3">
            {displaySectors.map((sector, idx) => (
              <div key={sector.sector}>
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <div className={`w-3 h-3 rounded-sm ${SECTOR_COLORS[idx % SECTOR_COLORS.length]}`} />
                    <span className="text-sm font-medium text-slate-900">
                      {sector.sector}
                    </span>
                    <span className="text-xs text-stone-500">
                      ({sector.positionCount} {sector.positionCount === 1 ? 'position' : 'positions'})
                    </span>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-sm font-bold text-slate-900">
                      {sector.pct.toFixed(1)}%
                    </span>
                    <span className="text-xs text-stone-500">
                      ${(sector.notional / 1000).toFixed(1)}k
                    </span>
                  </div>
                </div>
                <div className="w-full bg-stone-100 rounded-full h-2 overflow-hidden">
                  <div
                    className={`h-full ${SECTOR_COLORS[idx % SECTOR_COLORS.length]} transition-all`}
                    style={{ width: `${Math.min(sector.pct, 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-stone-500">No positions</p>
        )}
      </div>

      {/* Long/Short balance */}
      <div className="mb-8">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-stone-600 mb-4">
          Long / Short Balance
        </h3>
        
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-baseline gap-2">
            <span className="text-green-600 font-bold">
              Long: ${(longNotional / 1000).toFixed(1)}k
            </span>
            <span className="text-xs text-stone-500">
              ({longPct.toFixed(0)}%)
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-red-600 font-bold">
              Short: ${(Math.abs(shortNotional) / 1000).toFixed(1)}k
            </span>
            <span className="text-xs text-stone-500">
              ({shortPct.toFixed(0)}%)
            </span>
          </div>
        </div>
        
        {/* Visual balance bar */}
        <div className="relative w-full h-8 bg-stone-100 rounded-lg overflow-hidden flex">
          <div
            className="bg-green-500 flex items-center justify-end pr-2"
            style={{ width: `${longPct}%` }}
          >
            {longPct > 15 && (
              <span className="text-xs font-semibold text-white">
                LONG
              </span>
            )}
          </div>
          <div
            className="bg-red-500 flex items-center justify-start pl-2"
            style={{ width: `${shortPct}%` }}
          >
            {shortPct > 15 && (
              <span className="text-xs font-semibold text-white">
                SHORT
              </span>
            )}
          </div>
        </div>

        <div className="mt-3 text-center">
          <span className="text-xs text-stone-600">
            Net Exposure:{' '}
          </span>
          <span className={`text-sm font-bold ${
            netNotional > 0 ? 'text-green-600' : 
            netNotional < 0 ? 'text-red-600' : 
            'text-stone-600'
          }`}>
            ${(netNotional / 1000).toFixed(1)}k {netNotional > 0 ? 'Long' : netNotional < 0 ? 'Short' : 'Neutral'}
          </span>
        </div>
      </div>

      {/* Strategy mix */}
      <div className="mb-6">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-stone-600 mb-4">
          By Strategy
        </h3>
        
        {strategies.length > 0 ? (
          <div className="grid grid-cols-2 gap-3">
            {strategies.map((strat) => (
              <div
                key={strat.strategy}
                className="flex items-center justify-between p-3 rounded-lg bg-stone-50"
              >
                <div>
                  <div className="text-sm font-medium text-slate-900">
                    {strat.strategy}
                  </div>
                  <div className="text-xs text-stone-500">
                    {strat.count} {strat.count === 1 ? 'position' : 'positions'}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-lg font-bold text-slate-900">
                    {strat.pct.toFixed(0)}%
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-stone-500">No active strategies</p>
        )}
      </div>

      {/* Options income (if available) */}
      {optionsPremium30d !== undefined && optionsPremium30d > 0 && (
        <div className="pt-6 border-t border-stone-200">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-stone-600 mb-1">
                Premium Income (30d)
              </h3>
              <p className="text-xs text-stone-500">
                From covered calls, CSPs, and spreads
              </p>
            </div>
            <div className="text-right">
              <div className="text-2xl font-serif font-bold text-green-600">
                ${optionsPremium30d.toLocaleString()}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
