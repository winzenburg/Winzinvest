import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { prisma } from '@/lib/prisma';

/**
 * Email Preferences API
 * 
 * Lets users control their email frequency (daily vs weekly).
 */

export async function POST(req: Request) {
  const session = await getServerSession(authOptions);
  
  if (!session?.user?.email) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const body: unknown = await req.json();
    
    if (typeof body !== 'object' || body === null || !('frequency' in body)) {
      return NextResponse.json({ error: 'Invalid request body' }, { status: 400 });
    }

    const { frequency } = body as Record<string, unknown>;
    
    if (frequency !== 'daily' && frequency !== 'weekly') {
      return NextResponse.json({ error: 'Invalid frequency value' }, { status: 400 });
    }

    await prisma.user.update({
      where: { email: session.user.email },
      data: { emailFrequency: frequency },
    });

    return NextResponse.json({ ok: true, frequency });
  } catch (error) {
    console.error('Error updating email preferences:', error);
    return NextResponse.json(
      { error: 'Failed to update preferences' },
      { status: 500 }
    );
  }
}
