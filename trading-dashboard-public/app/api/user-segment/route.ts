import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { prisma } from '@/lib/prisma';

/**
 * User Segment API
 * 
 * Returns the user's engagement segment and personalization hints.
 * 
 * POST: Record dashboard view (for behavior tracking)
 * GET: Get current segment classification
 */

export async function POST() {
  const session = await getServerSession(authOptions);
  
  if (!session?.user?.email) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    // Update view count and timestamp
    await prisma.user.update({
      where: { email: session.user.email },
      data: {
        lastDashboardViewAt: new Date(),
        dashboardViewCount: {
          increment: 1,
        },
      },
    });

    return NextResponse.json({ ok: true });
  } catch (error) {
    console.error('Error recording dashboard view:', error);
    return NextResponse.json(
      { error: 'Failed to record view' },
      { status: 500 }
    );
  }
}

export async function GET() {
  const session = await getServerSession(authOptions);
  
  if (!session?.user?.email) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const user = await prisma.user.findUnique({
      where: { email: session.user.email },
      select: {
        dashboardViewCount: true,
        lastDashboardViewAt: true,
        engagementSegment: true,
        emailFrequency: true,
        preferredViewDepth: true,
        createdAt: true,
      },
    });

    if (!user) {
      return NextResponse.json({ error: 'User not found' }, { status: 404 });
    }

    // Calculate segment if not set or stale (> 7 days)
    const needsUpdate = !user.engagementSegment || 
                        !user.lastDashboardViewAt ||
                        (Date.now() - user.lastDashboardViewAt.getTime()) > 7 * 24 * 60 * 60 * 1000;

    let segment = user.engagementSegment;

    if (needsUpdate && user.createdAt) {
      const daysSinceJoin = Math.max(
        1,
        Math.floor((Date.now() - user.createdAt.getTime()) / (24 * 60 * 60 * 1000))
      );
      
      const viewsPerDay = user.dashboardViewCount / daysSinceJoin;

      // Classify
      if (viewsPerDay >= 2.0) {
        segment = 'nervous_monitor';
      } else if (viewsPerDay >= 0.7) {
        segment = 'daily_checker';
      } else if (viewsPerDay >= 0.25) {
        segment = 'weekly_checker';
      } else {
        segment = 'monthly_reviewer';
      }

      // Update DB
      await prisma.user.update({
        where: { email: session.user.email },
        data: { engagementSegment: segment },
      });
    }

    // Personalization hints
    const hints: Record<string, any> = {
      nervous_monitor: {
        label: 'Nervous Monitor',
        dashboardHint: 'Show reassurance metrics first (stop coverage, risk gates working)',
        emailFrequency: 'daily',
      },
      daily_checker: {
        label: 'Daily Checker',
        dashboardHint: 'Show daily narrative first, performance summary second',
        emailFrequency: 'daily',
      },
      weekly_checker: {
        label: 'Weekly Checker',
        dashboardHint: 'Show aggregated weekly insights, hide daily noise',
        emailFrequency: 'weekly',
      },
      monthly_reviewer: {
        label: 'Monthly Reviewer',
        dashboardHint: 'Show long-term trends only, skip daily details',
        emailFrequency: 'weekly',
      },
    };

    const hint = segment ? hints[segment] : hints.weekly_checker;

    return NextResponse.json({
      segment: segment || 'weekly_checker',
      viewCount: user.dashboardViewCount,
      lastViewAt: user.lastDashboardViewAt,
      emailFrequency: user.emailFrequency || hint.emailFrequency,
      preferredViewDepth: user.preferredViewDepth || 'overview',
      hint,
    });
  } catch (error) {
    console.error('Error loading user segment:', error);
    return NextResponse.json(
      { error: 'Failed to load segment' },
      { status: 500 }
    );
  }
}
