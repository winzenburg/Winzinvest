import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

/**
 * Batch activation tracking endpoint
 * 
 * Called by trading system when processing multiple trades in one run.
 * Updates activation timestamps for multiple users at once (reduces API calls).
 * 
 * Requires INTERNAL_API_TOKEN for authentication (server-to-server only).
 */

export async function POST(req: Request) {
  // Validate API token (server-to-server only)
  const authHeader = req.headers.get('Authorization');
  if (!authHeader?.startsWith('Bearer ')) {
    return NextResponse.json({ error: 'Missing Bearer token' }, { status: 401 });
  }
  
  const token = authHeader.replace('Bearer ', '');
  if (token !== process.env.INTERNAL_API_TOKEN) {
    return NextResponse.json({ error: 'Invalid API token' }, { status: 401 });
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 });
  }

  const { users, milestone } = body as Record<string, unknown>;

  // Validate users array
  if (!Array.isArray(users) || users.length === 0) {
    return NextResponse.json({ error: 'Invalid users array' }, { status: 400 });
  }

  if (milestone !== 'firstAutomatedTrade' && milestone !== 'activationCompleted') {
    return NextResponse.json({ error: 'Invalid milestone' }, { status: 400 });
  }

  try {
    // Build update data based on milestone
    const updateData: Record<string, Date> = {};
    
    if (milestone === 'firstAutomatedTrade') {
      updateData.firstAutomatedTradeAt = new Date();
    }
    
    if (milestone === 'activationCompleted') {
      updateData.activationCompletedAt = new Date();
    }

    // Batch update — only updates users where the field is null (idempotent)
    const whereClause: Record<string, any> = { email: { in: users } };
    
    if (milestone === 'firstAutomatedTrade') {
      whereClause.firstAutomatedTradeAt = null;
    } else if (milestone === 'activationCompleted') {
      whereClause.activationCompletedAt = null;
    }

    const result = await prisma.user.updateMany({
      where: whereClause,
      data: updateData,
    });

    return NextResponse.json({ 
      ok: true, 
      milestone,
      requestedCount: users.length,
      updatedCount: result.count,
    });
  } catch (err) {
    console.error('Batch activation error:', err);
    return NextResponse.json({ error: 'Failed to record batch activation' }, { status: 500 });
  }
}
