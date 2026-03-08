import { NextResponse } from 'next/server';

export async function GET() {
  // TODO: Connect to your database (Supabase, Postgres, etc.)
  // For now, returning mock data
  
  const data = {
    accountValue: 1936241,
    dailyPnL: 0,
    totalPnL: 12450,
    winRate: 62.1,
    sharpeRatio: 2.14,
    maxDrawdown: 4.3,
    totalTrades: 87,
    openPositions: 12,
    lastUpdate: new Date().toISOString(),
  };

  return NextResponse.json(data);
}
