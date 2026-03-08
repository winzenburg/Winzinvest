'use client';

import { useEffect, useState } from 'react';

interface PerformanceData {
  accountValue: number;
  dailyPnL: number;
  totalPnL: number;
  winRate: number;
  sharpeRatio: number;
  maxDrawdown: number;
  totalTrades: number;
  openPositions: number;
}

export default function Dashboard() {
  const [data, setData] = useState<PerformanceData | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string>('');

  useEffect(() => {
    // In production, this would fetch from your API
    // For now, using mock data
    const mockData: PerformanceData = {
      accountValue: 1936241,
      dailyPnL: 0,
      totalPnL: 12450,
      winRate: 62.1,
      sharpeRatio: 2.14,
      maxDrawdown: 4.3,
      totalTrades: 87,
      openPositions: 12,
    };

    setData(mockData);
    setLastUpdate(new Date().toLocaleTimeString());

    // Refresh every 30 seconds
    const interval = setInterval(() => {
      setLastUpdate(new Date().toLocaleTimeString());
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  if (!data) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center">
        <div className="text-stone-400">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-stone-50">
      <div className="max-w-7xl mx-auto px-8 py-12">
        {/* Header */}
        <header className="mb-16 pb-8 border-b border-stone-200">
          <div className="flex justify-between items-start">
            <h1 className="font-serif text-5xl font-bold text-slate-900 tracking-tight">
              Mission Control
            </h1>
            <div className="text-right">
              <div className="flex items-center gap-2 text-sm text-stone-500">
                <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                <span>Live</span>
              </div>
              <div className="text-xs text-stone-400 mt-1">
                Updated {lastUpdate}
              </div>
            </div>
          </div>
        </header>

        {/* Key Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
          <MetricCard
            label="Account Value"
            value={formatCurrency(data.accountValue)}
            color="text-sky-600"
          />
          <MetricCard
            label="Daily P&L"
            value={formatCurrency(data.dailyPnL)}
            color={data.dailyPnL >= 0 ? 'text-green-600' : 'text-red-600'}
          />
          <MetricCard
            label="Total P&L (30d)"
            value={formatCurrency(data.totalPnL)}
            color={data.totalPnL >= 0 ? 'text-green-600' : 'text-red-600'}
          />
          <MetricCard
            label="Win Rate"
            value={`${data.winRate.toFixed(1)}%`}
            color="text-green-600"
          />
        </div>

        {/* Performance Stats */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-12">
          <div className="bg-white border border-stone-200 rounded-xl p-8">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-6">
              Performance (30 Days)
            </h2>
            <div className="grid grid-cols-2 gap-6">
              <StatItem label="Sharpe Ratio" value={data.sharpeRatio.toFixed(2)} />
              <StatItem label="Max Drawdown" value={`${data.maxDrawdown.toFixed(1)}%`} />
              <StatItem label="Total Trades" value={data.totalTrades.toString()} />
              <StatItem label="Open Positions" value={data.openPositions.toString()} />
            </div>
          </div>

          <div className="bg-white border border-stone-200 rounded-xl p-8">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-6">
              Strategy Allocation
            </h2>
            <div className="space-y-4">
              <AllocationBar label="Long Positions" percentage={60} color="bg-green-500" />
              <AllocationBar label="Short Positions" percentage={20} color="bg-red-500" />
              <AllocationBar label="Options Premium" percentage={15} color="bg-orange-500" />
              <AllocationBar label="Cash" percentage={5} color="bg-stone-300" />
            </div>
          </div>
        </div>

        {/* About */}
        <div className="bg-white border border-stone-200 rounded-xl p-8">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-4">
            About This System
          </h2>
          <p className="text-stone-600 leading-relaxed">
            Automated trading system with multi-strategy execution, real-time risk management,
            and adaptive learning. Integrates with Interactive Brokers and TradingView for
            comprehensive market coverage. All data shown is historical and for informational
            purposes only.
          </p>
        </div>

        {/* Footer */}
        <footer className="mt-16 pt-8 border-t border-stone-200 text-center text-sm text-stone-400">
          <p>Mission Control Trading System • Read-Only Dashboard</p>
          <p className="mt-2">
            Past performance does not guarantee future results. Trading involves risk of loss.
          </p>
        </footer>
      </div>
    </div>
  );
}

function MetricCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-6 hover:shadow-lg transition-shadow">
      <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">
        {label}
      </div>
      <div className={`font-serif text-4xl font-bold ${color}`}>
        {value}
      </div>
    </div>
  );
}

function StatItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-stone-500 mb-1">{label}</div>
      <div className="font-serif text-2xl font-bold text-slate-900">{value}</div>
    </div>
  );
}

function AllocationBar({ label, percentage, color }: { label: string; percentage: number; color: string }) {
  return (
    <div>
      <div className="flex justify-between text-sm mb-2">
        <span className="text-stone-600">{label}</span>
        <span className="font-semibold text-stone-900">{percentage}%</span>
      </div>
      <div className="w-full h-2 bg-stone-100 rounded-full overflow-hidden">
        <div
          className={`h-full ${color} transition-all duration-500`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}
