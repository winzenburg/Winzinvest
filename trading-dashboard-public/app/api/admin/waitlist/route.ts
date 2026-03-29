import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '../../../../lib/auth';
import { prisma } from '../../../../lib/prisma';

async function requireAdmin() {
  const session = await getServerSession(authOptions);
  if (!session || session.user?.email !== process.env.ADMIN_EMAIL) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }
  return null;
}

export async function GET(req: Request) {
  const unauth = await requireAdmin();
  if (unauth) return unauth;

  const { searchParams } = new URL(req.url);
  const status = searchParams.get('status');
  const tier = searchParams.get('tier');

  try {
    const where: Record<string, unknown> = {};
    if (status) where.status = status;
    if (tier) where.tier = tier;

    const entries = await prisma.waitlist.findMany({
      where,
      orderBy: { createdAt: 'desc' },
    });

    const stats = {
      total: await prisma.waitlist.count(),
      pending: await prisma.waitlist.count({ where: { status: 'pending' } }),
      invited: await prisma.waitlist.count({ where: { status: 'invited' } }),
      active: await prisma.waitlist.count({ where: { status: 'active' } }),
      rejected: await prisma.waitlist.count({ where: { status: 'rejected' } }),
      byTier: {
        intelligence: await prisma.waitlist.count({ where: { tier: 'intelligence' } }),
        automation: await prisma.waitlist.count({ where: { tier: 'automation' } }),
        professional: await prisma.waitlist.count({ where: { tier: 'professional' } }),
        founding: await prisma.waitlist.count({ where: { tier: 'founding' } }),
      },
    };

    return NextResponse.json({ entries, stats });
  } catch (error) {
    console.error('Failed to fetch waitlist:', error);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}

export async function PATCH(req: Request) {
  const unauth = await requireAdmin();
  if (unauth) return unauth;

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 });
  }

  const { id, status, metadata } = body as Record<string, unknown>;

  if (typeof id !== 'string') {
    return NextResponse.json({ error: 'Invalid ID' }, { status: 400 });
  }

  try {
    const data: Record<string, unknown> = {};
    if (typeof status === 'string') data.status = status;
    if (metadata !== undefined) data.metadata = metadata;

    const updated = await prisma.waitlist.update({
      where: { id },
      data,
    });

    return NextResponse.json({ ok: true, entry: updated });
  } catch (error) {
    console.error('Failed to update waitlist entry:', error);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}
