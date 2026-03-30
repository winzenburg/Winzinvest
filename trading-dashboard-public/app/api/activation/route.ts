import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { prisma } from '@/lib/prisma';

/**
 * Activation tracking API
 * 
 * Records when a user hits key activation milestones:
 * - firstAutomatedTradeAt: First time system placed a trade for them
 * - activationCompletedAt: All core activation steps done
 * 
 * Called by trading system when orders are placed, or by dashboard on manual tracking.
 */

export async function POST(req: Request) {
  // Support both session auth (user-initiated) and token auth (server-to-server)
  let userEmail: string | null = null;
  
  // Check for Bearer token (trading system)
  const authHeader = req.headers.get('Authorization');
  if (authHeader?.startsWith('Bearer ')) {
    const token = authHeader.replace('Bearer ', '');
    if (token === process.env.INTERNAL_API_TOKEN) {
      // Valid internal call — get email from header
      userEmail = req.headers.get('X-User-Email');
      if (!userEmail) {
        return NextResponse.json({ error: 'Missing X-User-Email header' }, { status: 400 });
      }
    } else {
      return NextResponse.json({ error: 'Invalid API token' }, { status: 401 });
    }
  } else {
    // Fallback: check NextAuth session (user-initiated)
    const session = await getServerSession(authOptions);
    if (!session?.user?.email) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    userEmail = session.user.email;
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 });
  }

  const { milestone } = body as Record<string, unknown>;

  if (milestone !== 'firstAutomatedTrade' && milestone !== 'activationCompleted') {
    return NextResponse.json({ error: 'Invalid milestone' }, { status: 400 });
  }

  try {
    const user = await prisma.user.findUnique({
      where: { email: userEmail },
      select: { 
        id: true, 
        firstAutomatedTradeAt: true,
        activationCompletedAt: true,
      },
    });

    if (!user) {
      return NextResponse.json({ error: 'User not found' }, { status: 404 });
    }

    // Only set timestamp if not already set (first occurrence)
    const updates: Record<string, Date> = {};
    
    if (milestone === 'firstAutomatedTrade' && !user.firstAutomatedTradeAt) {
      updates.firstAutomatedTradeAt = new Date();
    }
    
    if (milestone === 'activationCompleted' && !user.activationCompletedAt) {
      updates.activationCompletedAt = new Date();
    }

    if (Object.keys(updates).length > 0) {
      await prisma.user.update({
        where: { id: user.id },
        data: updates,
      });
    }

    return NextResponse.json({ ok: true, milestone, recorded: Object.keys(updates).length > 0 });
  } catch (err) {
    console.error('Activation tracking error:', err);
    return NextResponse.json({ error: 'Failed to record activation' }, { status: 500 });
  }
}

// Get activation metrics for admin dashboard
export async function GET() {
  const session = await getServerSession(authOptions);
  if (!session?.user?.email) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const user = await prisma.user.findUnique({
    where: { email: session.user.email },
    select: { role: true },
  });

  if (user?.role !== 'admin') {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 403 });
  }

  try {
    // Get all users with activation data
    const users = await prisma.user.findMany({
      select: {
        id: true,
        email: true,
        createdAt: true,
        firstAutomatedTradeAt: true,
        activationCompletedAt: true,
      },
      orderBy: { createdAt: 'desc' },
    });

    // Calculate metrics
    const now = Date.now();
    const total = users.length;
    
    const activatedWithin7Days = users.filter(u => {
      if (!u.firstAutomatedTradeAt) return false;
      const daysDiff = (u.firstAutomatedTradeAt.getTime() - u.createdAt.getTime()) / (1000 * 60 * 60 * 24);
      return daysDiff <= 7;
    }).length;

    const activatedTotal = users.filter(u => u.firstAutomatedTradeAt).length;
    
    const daysSinceCreation = (u: typeof users[0]) => 
      (now - u.createdAt.getTime()) / (1000 * 60 * 60 * 24);
    
    // Only count users who have been around long enough to activate
    const eligibleUsers = users.filter(u => daysSinceCreation(u) >= 7);
    const d7ActivationRate = eligibleUsers.length > 0 
      ? (activatedWithin7Days / eligibleUsers.length) * 100 
      : 0;

    return NextResponse.json({
      total,
      activatedTotal,
      activatedWithin7Days,
      d7ActivationRate: Math.round(d7ActivationRate * 10) / 10,
      target: 60,
      users: users.map(u => ({
        email: u.email,
        signupDate: u.createdAt,
        daysActive: Math.floor(daysSinceCreation(u)),
        firstTradeAt: u.firstAutomatedTradeAt,
        daysToFirstTrade: u.firstAutomatedTradeAt 
          ? Math.floor((u.firstAutomatedTradeAt.getTime() - u.createdAt.getTime()) / (1000 * 60 * 60 * 24))
          : null,
        activated: !!u.firstAutomatedTradeAt,
      })),
    });
  } catch (err) {
    console.error('Activation metrics error:', err);
    return NextResponse.json({ error: 'Failed to fetch activation metrics' }, { status: 500 });
  }
}
