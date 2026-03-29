import { NextResponse } from 'next/server';
import { prisma } from '../../../lib/prisma';

export async function POST(req: Request) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 });
  }

  const { email, token } = body as Record<string, unknown>;

  if (typeof email !== 'string' || typeof token !== 'string') {
    return NextResponse.json({ error: 'Invalid parameters' }, { status: 400 });
  }

  try {
    const entry = await prisma.waitlist.findUnique({
      where: { email: email.trim().toLowerCase() },
    });

    if (!entry || entry.invitationToken !== token) {
      return NextResponse.json({ error: 'Invalid invitation' }, { status: 401 });
    }

    if (entry.status === 'active') {
      return NextResponse.json({ error: 'Already activated' }, { status: 400 });
    }

    const invitedAt = entry.invitedAt ? new Date(entry.invitedAt) : null;
    if (!invitedAt) {
      return NextResponse.json({ error: 'Invalid invitation' }, { status: 401 });
    }

    const hoursValid = 48;
    const expiryTime = new Date(invitedAt.getTime() + hoursValid * 60 * 60 * 1000);
    if (new Date() > expiryTime) {
      return NextResponse.json({ error: 'Invitation expired' }, { status: 401 });
    }

    return NextResponse.json({ ok: true });
  } catch (error) {
    console.error('Failed to verify invitation:', error);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}
