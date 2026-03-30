import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '../../../lib/auth';
import { requireAuth } from '../../../lib/auth';
import { getSnapshot } from '../../../lib/data-access';
import { prisma } from '../../../lib/prisma';

export const dynamic = 'force-dynamic';

const VALID_MODES = ['paper', 'live'] as const;
type TradingMode = (typeof VALID_MODES)[number];

function isValidMode(mode: string): mode is TradingMode {
  return VALID_MODES.includes(mode as TradingMode);
}

export async function GET(request: NextRequest) {
  const unauth = await requireAuth();
  if (unauth) return unauth;
  
  try {
    const session = await getServerSession(authOptions);
    const requestedMode = request.nextUrl.searchParams.get('mode');
    const mode = requestedMode && isValidMode(requestedMode) ? requestedMode : undefined;
    const data = await getSnapshot(mode);

    if (!data) {
      return NextResponse.json(
        { error: 'No dashboard snapshot found. Make sure dashboard_data_aggregator.py is running.' },
        { status: 404 },
      );
    }

    // Fetch user context for growth tracking (PMF survey, activation)
    let userContext = null;
    if (session?.user?.email) {
      const user = await prisma.user.findUnique({
        where: { email: session.user.email },
        select: {
          id: true,
          createdAt: true,
          firstAutomatedTradeAt: true,
          pmfSurveys: {
            select: { id: true },
            take: 1,
          },
        },
      });

      if (user) {
        const daysActive = Math.floor((Date.now() - user.createdAt.getTime()) / (1000 * 60 * 60 * 24));
        const daysToFirstTrade = user.firstAutomatedTradeAt
          ? Math.floor((user.firstAutomatedTradeAt.getTime() - user.createdAt.getTime()) / (1000 * 60 * 60 * 24))
          : null;

        userContext = {
          createdDaysAgo: daysActive,
          hasTakenPmfSurvey: user.pmfSurveys.length > 0,
          hasActivated: !!user.firstAutomatedTradeAt,
          daysToActivation: daysToFirstTrade,
        };
      }
    }

    return NextResponse.json({ 
      ...data,
      user: userContext,
    });
  } catch (error) {
    if (process.env.NODE_ENV === 'development') console.error('Error reading dashboard snapshot:', error);
    return NextResponse.json({ error: 'Failed to load dashboard data' }, { status: 500 });
  }
}
