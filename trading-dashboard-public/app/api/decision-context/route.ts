import { NextResponse } from 'next/server';
import { requireAuth } from '@/lib/auth';
import { readJson, remoteGet, isRemote, LOGS_DIR } from '@/lib/data-access';
import path from 'path';

/**
 * Decision Context API
 * 
 * Returns educational explanations for system decisions.
 * Powers "Why did the system do this?" tooltips.
 */

export async function GET(req: Request) {
  const unauth = await requireAuth();
  if (unauth) return unauth;

  const { searchParams } = new URL(req.url);
  const symbol = searchParams.get('symbol');

  try {
    let data: any;
    
    if (isRemote) {
      const endpoint = symbol ? `/api/decision-context?symbol=${symbol}` : '/api/decision-context';
      data = await remoteGet(endpoint);
    } else {
      const contextPath = path.join(LOGS_DIR, 'decision_context.json');
      data = readJson(contextPath) as any;
    }

    if (!data) {
      return NextResponse.json({
        positions: {},
        decisions: {},
      });
    }

    // If symbol requested, filter to that symbol only
    if (symbol) {
      const posContext = data.positions?.[symbol] || null;
      return NextResponse.json({
        symbol,
        context: posContext,
      });
    }

    // Return full context map
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error loading decision context:', error);
    return NextResponse.json(
      { error: 'Failed to load decision context' },
      { status: 500 }
    );
  }
}
