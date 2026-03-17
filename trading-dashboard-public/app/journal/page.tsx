'use client';

import { use, useEffect, useState } from 'react';
import Link from 'next/link';

interface Trade {
  timestamp: string;
  symbol: string;
  side: 'LONG' | 'SHORT';
  action: 'ENTRY' | 'EXIT';
  quantity: number;
  price: number;
  notional: number;
  strategy?: string;
  pnl?: number;
  reason?: string;
}

interface TradeGroup {
  symbol: string;
  side: 'LONG' | 'SHORT';
  entry: Trade;
  exit?: Trade;
  pnl?: number;
  returnPct?: number;
  status: 'OPEN' | 'CLOSED';
  daysHeld?: number;
}

type PageProps = {
  params?: Promise<Record<string, string | string[]>>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

const EMPTY = Promise.resolve({});

export default function JournalPage(props: PageProps) {
  use(props.params ?? EMPTY);
  use(props.searchParams ?? EMPTY);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [groupedTrades, setGroupedTrades] = useState<TradeGroup[]>([]);
  const [filter, setFilter] = useState<'all' | 'open' | 'closed'>('all');
  const [sortBy, setSortBy] = useState<'date' | 'pnl' | 'return'>('date');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // In production, fetch from API endpoint that reads executions.json
    // For now, using realistic dummy data
    const dummyTrades: Trade[] = [
      {
        timestamp: '2026-03-07T14:32:15',
        symbol: 'AAPL',
        side: 'LONG',
        action: 'ENTRY',
        quantity: 150,
        price: 178.20,
        notional: 26730,
        strategy: 'momentum',
        reason: 'Strong RS, above all MAs',
      },
      {
        timestamp: '2026-03-07T15:45:22',
        symbol: 'AAPL',
        side: 'LONG',
        action: 'EXIT',
        quantity: 150,
        price: 182.45,
        notional: 27367.50,
        pnl: 637.50,
        reason: 'Take profit target hit',
      },
      {
        timestamp: '2026-03-07T10:15:30',
        symbol: 'MSFT',
        side: 'LONG',
        action: 'ENTRY',
        quantity: 200,
        price: 408.15,
        notional: 81630,
        strategy: 'momentum',
        reason: 'Breakout above resistance',
      },
      {
        timestamp: '2026-03-07T14:20:18',
        symbol: 'MSFT',
        side: 'LONG',
        action: 'EXIT',
        quantity: 200,
        price: 415.30,
        notional: 83060,
        pnl: 1430,
        reason: 'Take profit',
      },
      {
        timestamp: '2026-03-06T11:22:45',
        symbol: 'NVDA',
        side: 'LONG',
        action: 'ENTRY',
        quantity: 100,
        price: 862.40,
        notional: 86240,
        strategy: 'momentum',
        reason: 'High volume breakout',
      },
      {
        timestamp: '2026-03-06T15:30:12',
        symbol: 'NVDA',
        side: 'LONG',
        action: 'EXIT',
        quantity: 100,
        price: 875.20,
        notional: 87520,
        pnl: 1280,
        reason: 'Take profit',
      },
      {
        timestamp: '2026-03-06T09:45:00',
        symbol: 'TSLA',
        side: 'SHORT',
        action: 'ENTRY',
        quantity: 50,
        price: 205.40,
        notional: 10270,
        strategy: 'momentum_short',
        reason: 'Weak RS, below MAs',
      },
      {
        timestamp: '2026-03-06T13:15:30',
        symbol: 'TSLA',
        side: 'SHORT',
        action: 'EXIT',
        quantity: 50,
        price: 198.75,
        notional: 9937.50,
        pnl: 332.50,
        reason: 'Cover on target',
      },
      {
        timestamp: '2026-03-05T10:30:00',
        symbol: 'META',
        side: 'LONG',
        action: 'ENTRY',
        quantity: 90,
        price: 478.20,
        notional: 43038,
        strategy: 'momentum',
        reason: 'Strong momentum',
      },
      {
        timestamp: '2026-03-05T14:45:00',
        symbol: 'META',
        side: 'LONG',
        action: 'EXIT',
        quantity: 90,
        price: 485.60,
        notional: 43704,
        pnl: 666,
        reason: 'Take profit',
      },
      {
        timestamp: '2026-03-05T11:00:00',
        symbol: 'AMZN',
        side: 'LONG',
        action: 'ENTRY',
        quantity: 180,
        price: 175.30,
        notional: 31554,
        strategy: 'momentum',
        reason: 'Consolidation breakout',
      },
      {
        timestamp: '2026-03-05T15:20:00',
        symbol: 'AMZN',
        side: 'LONG',
        action: 'EXIT',
        quantity: 180,
        price: 178.90,
        notional: 32202,
        pnl: 648,
        reason: 'Take profit',
      },
      {
        timestamp: '2026-03-04T10:45:00',
        symbol: 'GOOGL',
        side: 'LONG',
        action: 'ENTRY',
        quantity: 120,
        price: 139.20,
        notional: 16704,
        strategy: 'momentum',
        reason: 'Above all MAs',
      },
      {
        timestamp: '2026-03-04T14:30:00',
        symbol: 'GOOGL',
        side: 'LONG',
        action: 'EXIT',
        quantity: 120,
        price: 142.85,
        notional: 17142,
        pnl: 438,
        reason: 'Take profit',
      },
      {
        timestamp: '2026-03-07T09:30:15',
        symbol: 'AMD',
        side: 'LONG',
        action: 'ENTRY',
        quantity: 250,
        price: 185.40,
        notional: 46350,
        strategy: 'momentum',
        reason: 'Sector strength, high RS',
      },
      {
        timestamp: '2026-03-06T10:00:00',
        symbol: 'RIVN',
        side: 'SHORT',
        action: 'ENTRY',
        quantity: 300,
        price: 12.45,
        notional: 3735,
        strategy: 'momentum_short',
        reason: 'Weak downtrend, below MAs',
      },
    ];

    setTrades(dummyTrades);

    // Group trades by symbol and match entries with exits
    const grouped: TradeGroup[] = [];
    const entries = dummyTrades.filter(t => t.action === 'ENTRY');
    
    entries.forEach(entry => {
      const exit = dummyTrades.find(
        t => t.action === 'EXIT' && t.symbol === entry.symbol && t.side === entry.side &&
        new Date(t.timestamp) > new Date(entry.timestamp)
      );

      const group: TradeGroup = {
        symbol: entry.symbol,
        side: entry.side,
        entry,
        exit,
        status: exit ? 'CLOSED' : 'OPEN',
      };

      if (exit) {
        const entryNotional = entry.quantity * entry.price;
        const exitNotional = exit.quantity * exit.price;
        
        if (entry.side === 'LONG') {
          group.pnl = exitNotional - entryNotional;
          group.returnPct = ((exit.price - entry.price) / entry.price) * 100;
        } else {
          group.pnl = entryNotional - exitNotional;
          group.returnPct = ((entry.price - exit.price) / entry.price) * 100;
        }

        const entryDate = new Date(entry.timestamp);
        const exitDate = new Date(exit.timestamp);
        group.daysHeld = Math.ceil((exitDate.getTime() - entryDate.getTime()) / (1000 * 60 * 60 * 24));
      }

      grouped.push(group);
    });

    setGroupedTrades(grouped);
    setLoading(false);
  }, []);

  const filteredTrades = groupedTrades.filter(trade => {
    if (filter === 'all') return true;
    return trade.status === filter.toUpperCase();
  });

  const sortedTrades = [...filteredTrades].sort((a, b) => {
    if (sortBy === 'date') {
      return new Date(b.entry.timestamp).getTime() - new Date(a.entry.timestamp).getTime();
    } else if (sortBy === 'pnl') {
      return (b.pnl || 0) - (a.pnl || 0);
    } else if (sortBy === 'return') {
      return (b.returnPct || 0) - (a.returnPct || 0);
    }
    return 0;
  });

  const totalPnL = groupedTrades
    .filter(t => t.status === 'CLOSED')
    .reduce((sum, t) => sum + (t.pnl || 0), 0);
  
  const winningTrades = groupedTrades.filter(t => t.status === 'CLOSED' && (t.pnl || 0) > 0).length;
  const losingTrades = groupedTrades.filter(t => t.status === 'CLOSED' && (t.pnl || 0) < 0).length;
  const winRate = winningTrades + losingTrades > 0 
    ? (winningTrades / (winningTrades + losingTrades) * 100).toFixed(1)
    : '0.0';

  if (loading) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center">
        <div className="text-stone-400">Loading journal...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-stone-50">
      <div className="max-w-7xl mx-auto px-8 py-12">
        {/* Header */}
        <header className="mb-12 pb-6 border-b border-stone-200">
          <Link 
            href="/" 
            className="text-sm text-stone-500 hover:text-stone-600 mb-4 inline-block"
          >
            ← Back to Dashboard
          </Link>
          <h1 className="font-serif text-5xl font-bold text-slate-900 tracking-tight mt-4">
            Trading Journal
          </h1>
          <p className="text-stone-500 mt-4 text-lg">
            Complete history of all trades executed by the system
          </p>
        </header>

        {/* Summary Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white border border-stone-200 rounded-xl p-6">
            <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">
              Total P&L
            </div>
            <div className={`font-serif text-4xl font-bold ${totalPnL >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {totalPnL >= 0 ? '+' : ''}{formatCurrency(totalPnL)}
            </div>
          </div>

          <div className="bg-white border border-stone-200 rounded-xl p-6">
            <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">
              Win Rate
            </div>
            <div className="font-serif text-4xl font-bold text-sky-600">
              {winRate}%
            </div>
            <div className="text-xs text-stone-500 mt-1">
              {winningTrades}W / {losingTrades}L
            </div>
          </div>

          <div className="bg-white border border-stone-200 rounded-xl p-6">
            <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">
              Total Trades
            </div>
            <div className="font-serif text-4xl font-bold text-sky-600">
              {groupedTrades.length}
            </div>
            <div className="text-xs text-stone-500 mt-1">
              {groupedTrades.filter(t => t.status === 'OPEN').length} open
            </div>
          </div>

          <div className="bg-white border border-stone-200 rounded-xl p-6">
            <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">
              Avg Return
            </div>
            <div className="font-serif text-4xl font-bold text-sky-600">
              {groupedTrades.filter(t => t.status === 'CLOSED').length > 0
                ? (groupedTrades
                    .filter(t => t.status === 'CLOSED')
                    .reduce((sum, t) => sum + (t.returnPct || 0), 0) /
                    groupedTrades.filter(t => t.status === 'CLOSED').length
                  ).toFixed(2)
                : '0.00'}%
            </div>
          </div>
        </div>

        {/* Filters and Sort */}
        <div className="bg-white border border-stone-200 rounded-xl p-6 mb-8">
          <div className="flex flex-wrap gap-4 items-center justify-between">
            <div className="flex gap-2">
              <button
                onClick={() => setFilter('all')}
                className={`px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${
                  filter === 'all'
                    ? 'bg-slate-900 text-white'
                    : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
                }`}
              >
                All Trades
              </button>
              <button
                onClick={() => setFilter('open')}
                className={`px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${
                  filter === 'open'
                    ? 'bg-slate-900 text-white'
                    : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
                }`}
              >
                Open Positions
              </button>
              <button
                onClick={() => setFilter('closed')}
                className={`px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${
                  filter === 'closed'
                    ? 'bg-slate-900 text-white'
                    : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
                }`}
              >
                Closed Trades
              </button>
            </div>

            <div className="flex gap-2 items-center">
              <span className="text-sm text-stone-500">Sort by:</span>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as 'date' | 'pnl' | 'return')}
                className="px-3 py-2 bg-stone-100 border border-stone-200 rounded-lg text-sm text-stone-600 focus:outline-none focus:ring-2 focus:ring-sky-600"
              >
                <option value="date">Date</option>
                <option value="pnl">P&L</option>
                <option value="return">Return %</option>
              </select>
            </div>
          </div>
        </div>

        {/* Trades Table */}
        <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-stone-50 border-b border-stone-200">
                <tr>
                  <th className="text-left py-4 px-4 font-semibold text-stone-600">Status</th>
                  <th className="text-left py-4 px-4 font-semibold text-stone-600">Symbol</th>
                  <th className="text-left py-4 px-4 font-semibold text-stone-600">Side</th>
                  <th className="text-right py-4 px-4 font-semibold text-stone-600">Entry Date</th>
                  <th className="text-right py-4 px-4 font-semibold text-stone-600">Entry Price</th>
                  <th className="text-right py-4 px-4 font-semibold text-stone-600">Exit Price</th>
                  <th className="text-right py-4 px-4 font-semibold text-stone-600">Qty</th>
                  <th className="text-right py-4 px-4 font-semibold text-stone-600">P&L</th>
                  <th className="text-right py-4 px-4 font-semibold text-stone-600">Return</th>
                  <th className="text-left py-4 px-4 font-semibold text-stone-600">Days</th>
                </tr>
              </thead>
              <tbody>
                {sortedTrades.map((trade, idx) => (
                  <tr key={idx} className="border-b border-stone-100 hover:bg-stone-50">
                    <td className="py-4 px-4">
                      <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                        trade.status === 'OPEN'
                          ? 'bg-blue-100 text-blue-700'
                          : 'bg-stone-100 text-stone-600'
                      }`}>
                        {trade.status}
                      </span>
                    </td>
                    <td className="py-4 px-4 font-bold text-slate-900">{trade.symbol}</td>
                    <td className="py-4 px-4">
                      <span className={`px-2 py-1 rounded text-xs font-semibold ${
                        trade.side === 'LONG'
                          ? 'bg-green-100 text-green-700'
                          : 'bg-red-100 text-red-700'
                      }`}>
                        {trade.side}
                      </span>
                    </td>
                    <td className="py-4 px-4 text-right text-stone-600">
                      {formatDate(trade.entry.timestamp)}
                    </td>
                    <td className="py-4 px-4 text-right text-slate-900 font-mono">
                      ${trade.entry.price.toFixed(2)}
                    </td>
                    <td className="py-4 px-4 text-right text-slate-900 font-mono">
                      {trade.exit ? `$${trade.exit.price.toFixed(2)}` : '—'}
                    </td>
                    <td className="py-4 px-4 text-right text-stone-600">
                      {trade.entry.quantity}
                    </td>
                    <td className={`py-4 px-4 text-right font-bold ${
                      !trade.pnl ? 'text-stone-400' :
                      trade.pnl > 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {trade.pnl ? (trade.pnl > 0 ? '+' : '') + formatCurrency(trade.pnl) : '—'}
                    </td>
                    <td className={`py-4 px-4 text-right font-bold ${
                      !trade.returnPct ? 'text-stone-400' :
                      trade.returnPct > 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {trade.returnPct ? (trade.returnPct > 0 ? '+' : '') + trade.returnPct.toFixed(2) + '%' : '—'}
                    </td>
                    <td className="py-4 px-4 text-stone-600">
                      {trade.daysHeld ? `${trade.daysHeld}d` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Trade Details Section */}
        <div className="mt-8 space-y-4">
          {sortedTrades.slice(0, 5).map((trade, idx) => (
            <div key={idx} className="bg-white border border-stone-200 rounded-xl p-6">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <span className="font-bold text-xl text-slate-900">{trade.symbol}</span>
                    <span className={`px-2 py-1 rounded text-xs font-semibold ${
                      trade.side === 'LONG'
                        ? 'bg-green-100 text-green-700'
                        : 'bg-red-100 text-red-700'
                    }`}>
                      {trade.side}
                    </span>
                    <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                      trade.status === 'OPEN'
                        ? 'bg-blue-100 text-blue-700'
                        : 'bg-stone-100 text-stone-600'
                    }`}>
                      {trade.status}
                    </span>
                  </div>
                  <div className="text-sm text-stone-500">
                    Strategy: {trade.entry.strategy || 'N/A'}
                  </div>
                </div>
                {trade.pnl !== undefined && (
                  <div className="text-right">
                    <div className={`font-serif text-2xl font-bold ${
                      trade.pnl > 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {trade.pnl > 0 ? '+' : ''}{formatCurrency(trade.pnl)}
                    </div>
                    <div className={`text-sm font-semibold ${
                      (trade.returnPct || 0) > 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {(trade.returnPct || 0) > 0 ? '+' : ''}{(trade.returnPct || 0).toFixed(2)}%
                    </div>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-6 text-sm">
                <div>
                  <div className="font-semibold text-slate-900 mb-2">Entry</div>
                  <div className="space-y-1 text-stone-600">
                    <div>Date: {formatDateTime(trade.entry.timestamp)}</div>
                    <div>Price: ${trade.entry.price.toFixed(2)}</div>
                    <div>Quantity: {trade.entry.quantity}</div>
                    <div>Notional: {formatCurrency(trade.entry.notional)}</div>
                    {trade.entry.reason && (
                      <div className="mt-2 text-xs italic text-stone-500">
                        Reason: {trade.entry.reason}
                      </div>
                    )}
                  </div>
                </div>

                {trade.exit && (
                  <div>
                    <div className="font-semibold text-slate-900 mb-2">Exit</div>
                    <div className="space-y-1 text-stone-600">
                      <div>Date: {formatDateTime(trade.exit.timestamp)}</div>
                      <div>Price: ${trade.exit.price.toFixed(2)}</div>
                      <div>Quantity: {trade.exit.quantity}</div>
                      <div>Notional: {formatCurrency(trade.exit.notional)}</div>
                      {trade.exit.reason && (
                        <div className="mt-2 text-xs italic text-stone-500">
                          Reason: {trade.exit.reason}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <footer className="mt-16 pt-8 border-t border-stone-200 text-center text-sm text-stone-400">
          <p>Winzinvest • Journal</p>
          <p className="mt-2">
            All trades are executed automatically based on predefined rules and risk parameters.
          </p>
        </footer>
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

function formatDate(timestamp: string): string {
  return new Date(timestamp).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
}

function formatDateTime(timestamp: string): string {
  return new Date(timestamp).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
