import { NextResponse } from 'next/server';

export async function GET() {
  // TODO: Connect to your database (Supabase, Postgres, etc.)
  // For now, returning realistic dummy data
  
  const data = {
    accountValue: 1936241,
    dailyPnL: 2340,
    totalPnL: 12450,
    winRate: 62.1,
    sharpeRatio: 2.14,
    maxDrawdown: 4.3,
    totalTrades: 87,
    openPositions: 12,
    wins: 54,
    losses: 33,
    avgTrade: 143,
    bestTrade: 2450,
    worstTrade: -890,
    consecutiveWins: 7,
    consecutiveLosses: 3,
    profitFactor: 1.85,
    avgWin: 285,
    avgLoss: -154,
    largestWin: 2450,
    largestLoss: -890,
    avgHoldTime: '2.3 days',
    lastUpdate: new Date().toISOString(),
  };

  return NextResponse.json(data);
}
