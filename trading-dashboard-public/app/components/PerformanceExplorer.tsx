'use client';

/**
 * Performance Explorer — Interactive Trade History Analysis
 * 
 * Self-service data slicing by regime, strategy, sector, timeframe.
 * Satisfies curiosity about "How did X perform in Y conditions?"
 * 
 * Framework: Core Drive 7 (Curiosity) via pattern discovery
 */

import { useState, useEffect, useMemo } from 'react';

interface TradeRecord {
  symbol: string;
  strategy: string;
  sector: string;
  regime: string;
  entry_date: string;
  exit_date?: string;
  holding_days: number;
  pnl: number;
  return_pct: number;
  r_multiple?: number;
}

interface PerformanceExplorerProps {
  className?: string;
}

interface FilterState {
  regime: string;
  strategy: string;
  sector: string;
  timeframe: string;
}

interface AggregatedStats {
  totalTrades: number;
  winRate: number;
  avgReturn: number;
  totalPnl: number;
  profitFactor: number;
  avgRMultiple: number;
  bestTrade: number;
  worstTrade: number;
}

export default function PerformanceExplorer({ className = '' }: PerformanceExplorerProps) {
  const [trades, setTrades] = useState<TradeRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<FilterState>({
    regime: 'all',
    strategy: 'all',
    sector: 'all',
    timeframe: '30d',
  });

  // Fetch trade history
  useEffect(() => {
    const fetchTrades = async () => {
      try {
        const res = await fetch('/api/trade-history', {
          credentials: 'include',
        });
        
        if (res.ok) {
          const data = await res.json();
          setTrades(data.trades || []);
        }
      } catch (err) {
        console.error('Error fetching trade history:', err);
      } finally {
        setLoading(false);
      }
    };
    
    fetchTrades();
  }, []);

  // Get unique filter values
  const uniqueRegimes = useMemo(() => {
    const regimes = new Set(trades.map(t => t.regime).filter(Boolean));
    return ['all', ...Array.from(regimes).sort()];
  }, [trades]);

  const uniqueStrategies = useMemo(() => {
    const strategies = new Set(trades.map(t => t.strategy).filter(Boolean));
    return ['all', ...Array.from(strategies).sort()];
  }, [trades]);

  const uniqueSectors = useMemo(() => {
    const sectors = new Set(trades.map(t => t.sector).filter(Boolean));
    return ['all', ...Array.from(sectors).sort()];
  }, [trades]);

  // Filter trades
  const filteredTrades = useMemo(() => {
    let filtered = trades;

    // Timeframe filter
    const now = new Date();
    let cutoffDate: Date;
    
    if (filters.timeframe === '7d') {
      cutoffDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    } else if (filters.timeframe === '30d') {
      cutoffDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
    } else if (filters.timeframe === '90d') {
      cutoffDate = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000);
    } else if (filters.timeframe === '1y') {
      cutoffDate = new Date(now.getTime() - 365 * 24 * 60 * 60 * 1000);
    } else {
      cutoffDate = new Date(0);  // All time
    }

    filtered = filtered.filter(t => {
      const exitDate = t.exit_date ? new Date(t.exit_date) : now;
      return exitDate >= cutoffDate;
    });

    // Category filters
    if (filters.regime !== 'all') {
      filtered = filtered.filter(t => t.regime === filters.regime);
    }
    
    if (filters.strategy !== 'all') {
      filtered = filtered.filter(t => t.strategy === filters.strategy);
    }
    
    if (filters.sector !== 'all') {
      filtered = filtered.filter(t => t.sector === filters.sector);
    }

    return filtered;
  }, [trades, filters]);

  // Calculate aggregated stats
  const stats: AggregatedStats = useMemo(() => {
    if (filteredTrades.length === 0) {
      return {
        totalTrades: 0,
        winRate: 0,
        avgReturn: 0,
        totalPnl: 0,
        profitFactor: 0,
        avgRMultiple: 0,
        bestTrade: 0,
        worstTrade: 0,
      };
    }

    const wins = filteredTrades.filter(t => t.pnl > 0);
    const losses = filteredTrades.filter(t => t.pnl < 0);
    
    const totalWinPnl = wins.reduce((sum, t) => sum + t.pnl, 0);
    const totalLossPnl = Math.abs(losses.reduce((sum, t) => sum + t.pnl, 0));
    const totalPnl = filteredTrades.reduce((sum, t) => sum + t.pnl, 0);
    
    const rMultiples = filteredTrades.filter(t => t.r_multiple !== undefined).map(t => t.r_multiple!);
    const avgRMultiple = rMultiples.length > 0
      ? rMultiples.reduce((sum, r) => sum + r, 0) / rMultiples.length
      : 0;

    return {
      totalTrades: filteredTrades.length,
      winRate: wins.length / filteredTrades.length * 100,
      avgReturn: filteredTrades.reduce((sum, t) => sum + t.return_pct, 0) / filteredTrades.length,
      totalPnl,
      profitFactor: totalLossPnl > 0 ? totalWinPnl / totalLossPnl : 0,
      avgRMultiple,
      bestTrade: filteredTrades.length > 0 ? Math.max(...filteredTrades.map(t => t.pnl)) : 0,
      worstTrade: filteredTrades.length > 0 ? Math.min(...filteredTrades.map(t => t.pnl)) : 0,
    };
  }, [filteredTrades]);

  if (loading) {
    return (
      <div className={`rounded-xl border border-stone-200 bg-white p-8 ${className}`}>
        <div className="animate-pulse">
          <div className="h-8 bg-stone-200 rounded w-1/3 mb-6" />
          <div className="grid grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-12 bg-stone-100 rounded" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`rounded-xl border border-stone-200 bg-white p-8 ${className}`}>
      {/* Header */}
      <div className="mb-6">
        <h2 className="font-serif text-2xl font-bold text-slate-900 mb-2">
          Performance Explorer
        </h2>
        <p className="text-sm text-stone-600">
          Explore trade performance by filters — discover what works in different conditions
        </p>
      </div>

      {/* Filters */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-stone-600 mb-2">
            Timeframe
          </label>
          <select
            value={filters.timeframe}
            onChange={(e) => setFilters(f => ({ ...f, timeframe: e.target.value }))}
            className="w-full px-3 py-2 rounded-lg border border-stone-300 bg-white text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="7d">Last 7 Days</option>
            <option value="30d">Last 30 Days</option>
            <option value="90d">Last 90 Days</option>
            <option value="1y">Last Year</option>
            <option value="all">All Time</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-stone-600 mb-2">
            Regime
          </label>
          <select
            value={filters.regime}
            onChange={(e) => setFilters(f => ({ ...f, regime: e.target.value }))}
            className="w-full px-3 py-2 rounded-lg border border-stone-300 bg-white text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            {uniqueRegimes.map(r => (
              <option key={r} value={r}>
                {r === 'all' ? 'All Regimes' : r.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-stone-600 mb-2">
            Strategy
          </label>
          <select
            value={filters.strategy}
            onChange={(e) => setFilters(f => ({ ...f, strategy: e.target.value }))}
            className="w-full px-3 py-2 rounded-lg border border-stone-300 bg-white text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            {uniqueStrategies.map(s => (
              <option key={s} value={s}>
                {s === 'all' ? 'All Strategies' : s.toUpperCase()}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-stone-600 mb-2">
            Sector
          </label>
          <select
            value={filters.sector}
            onChange={(e) => setFilters(f => ({ ...f, sector: e.target.value }))}
            className="w-full px-3 py-2 rounded-lg border border-stone-300 bg-white text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            {uniqueSectors.map(s => (
              <option key={s} value={s}>
                {s === 'all' ? 'All Sectors' : s}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Results summary */}
      {filteredTrades.length > 0 ? (
        <>
          {/* Stats grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="p-4 rounded-lg bg-slate-50">
              <div className="text-xs text-stone-600 mb-1">Total Trades</div>
              <div className="text-2xl font-bold text-slate-900">{stats.totalTrades}</div>
            </div>
            
            <div className="p-4 rounded-lg bg-green-50">
              <div className="text-xs text-stone-600 mb-1">Win Rate</div>
              <div className="text-2xl font-bold text-green-600">{stats.winRate.toFixed(1)}%</div>
            </div>
            
            <div className="p-4 rounded-lg bg-blue-50">
              <div className="text-xs text-stone-600 mb-1">Avg R-Multiple</div>
              <div className="text-2xl font-bold text-blue-600">{stats.avgRMultiple.toFixed(2)}R</div>
            </div>
            
            <div className={`p-4 rounded-lg ${stats.totalPnl >= 0 ? 'bg-green-50' : 'bg-red-50'}`}>
              <div className="text-xs text-stone-600 mb-1">Total P&L</div>
              <div className={`text-2xl font-bold ${stats.totalPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {stats.totalPnl >= 0 ? '+' : ''}${stats.totalPnl.toLocaleString()}
              </div>
            </div>
          </div>

          {/* Additional metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="flex items-center justify-between p-3 rounded-lg bg-white border border-stone-200">
              <span className="text-xs text-stone-600">Profit Factor</span>
              <span className="text-sm font-bold text-slate-900">
                {stats.profitFactor.toFixed(2)}
              </span>
            </div>
            
            <div className="flex items-center justify-between p-3 rounded-lg bg-white border border-stone-200">
              <span className="text-xs text-stone-600">Avg Return</span>
              <span className={`text-sm font-bold ${stats.avgReturn >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {stats.avgReturn >= 0 ? '+' : ''}{stats.avgReturn.toFixed(2)}%
              </span>
            </div>
            
            <div className="flex items-center justify-between p-3 rounded-lg bg-white border border-stone-200">
              <span className="text-xs text-stone-600">Best Trade</span>
              <span className="text-sm font-bold text-green-600">
                +${stats.bestTrade.toLocaleString()}
              </span>
            </div>
            
            <div className="flex items-center justify-between p-3 rounded-lg bg-white border border-stone-200">
              <span className="text-xs text-stone-600">Worst Trade</span>
              <span className="text-sm font-bold text-red-600">
                ${stats.worstTrade.toLocaleString()}
              </span>
            </div>
          </div>

          {/* Recent trades table */}
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-stone-600 mb-3">
              Matching Trades (showing last 20)
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-stone-300">
                  <tr className="text-left">
                    <th className="pb-2 text-xs font-semibold uppercase tracking-wider text-stone-600">Symbol</th>
                    <th className="pb-2 text-xs font-semibold uppercase tracking-wider text-stone-600">Strategy</th>
                    <th className="pb-2 text-xs font-semibold uppercase tracking-wider text-stone-600">Regime</th>
                    <th className="pb-2 text-xs font-semibold uppercase tracking-wider text-stone-600 text-right">Days</th>
                    <th className="pb-2 text-xs font-semibold uppercase tracking-wider text-stone-600 text-right">Return</th>
                    <th className="pb-2 text-xs font-semibold uppercase tracking-wider text-stone-600 text-right">P&L</th>
                    <th className="pb-2 text-xs font-semibold uppercase tracking-wider text-stone-600 text-right">R-Mult</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTrades
                    .slice(-20)
                    .reverse()
                    .map((trade, idx) => (
                      <tr key={idx} className="border-b border-stone-100 hover:bg-stone-50">
                        <td className="py-2 font-mono font-bold text-slate-900">{trade.symbol}</td>
                        <td className="py-2 text-stone-700">{trade.strategy}</td>
                        <td className="py-2">
                          <span className="text-xs px-2 py-1 rounded bg-stone-100 text-stone-700">
                            {trade.regime.replace(/_/g, ' ')}
                          </span>
                        </td>
                        <td className="py-2 text-right text-stone-700">{trade.holding_days}</td>
                        <td className={`py-2 text-right font-semibold ${
                          trade.return_pct >= 0 ? 'text-green-600' : 'text-red-600'
                        }`}>
                          {trade.return_pct >= 0 ? '+' : ''}{trade.return_pct.toFixed(2)}%
                        </td>
                        <td className={`py-2 text-right font-semibold ${
                          trade.pnl >= 0 ? 'text-green-600' : 'text-red-600'
                        }`}>
                          {trade.pnl >= 0 ? '+' : ''}${trade.pnl.toLocaleString()}
                        </td>
                        <td className="py-2 text-right text-stone-700">
                          {trade.r_multiple !== undefined ? `${trade.r_multiple.toFixed(2)}R` : '—'}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      ) : (
        <div className="text-center py-12 text-stone-500">
          <div className="text-4xl mb-3">🔍</div>
          <p className="text-sm">
            No trades match your current filters. Try adjusting the criteria.
          </p>
        </div>
      )}
    </div>
  );
}
