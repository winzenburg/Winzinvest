import { NextResponse } from 'next/server';
import { prisma } from '../../../lib/prisma';
import bcrypt from 'bcryptjs';

export async function POST(req: Request) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 });
  }

  const { email, token, name, password } = body as Record<string, unknown>;

  if (
    typeof email !== 'string' ||
    typeof token !== 'string' ||
    typeof name !== 'string' ||
    typeof password !== 'string'
  ) {
    return NextResponse.json({ error: 'Invalid parameters' }, { status: 400 });
  }

  if (password.length < 8) {
    return NextResponse.json({ error: 'Password must be at least 8 characters' }, { status: 400 });
  }

  try {
    const entry = await prisma.waitlist.findUnique({
      where: { email: email.trim().toLowerCase() },
    });

    if (!entry || entry.invitationToken !== token) {
      return NextResponse.json({ error: 'Invalid invitation' }, { status: 401 });
    }

    if (entry.status === 'active') {
      return NextResponse.json({ error: 'Account already exists' }, { status: 400 });
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

    const existingUser = await prisma.user.findUnique({
      where: { email: email.trim().toLowerCase() },
    });

    if (existingUser) {
      return NextResponse.json({ error: 'Account already exists' }, { status: 400 });
    }

    const passwordHash = await bcrypt.hash(password, 10);

    await prisma.user.create({
      data: {
        email: email.trim().toLowerCase(),
        name: name.trim(),
        passwordHash,
        role: 'user',
      },
    });

    await prisma.waitlist.update({
      where: { email: email.trim().toLowerCase() },
      data: { status: 'active' },
    });

    return NextResponse.json({ ok: true });
  } catch (error) {
    console.error('Failed to complete onboarding:', error);
    return NextResponse.json({ error: 'Failed to create account' }, { status: 500 });
  }
}
