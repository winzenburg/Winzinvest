import { NextResponse } from 'next/server';
import { prisma } from '../../../lib/prisma';
import { hash } from 'bcryptjs';

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const token: string | undefined = body.token;
    const password: string = body.password ?? '';

    if (!token || !password) {
      return NextResponse.json(
        { error: 'Token and new password are required.' },
        { status: 400 },
      );
    }

    if (password.length < 8) {
      return NextResponse.json(
        { error: 'Password must be at least 8 characters long.' },
        { status: 400 },
      );
    }

    const record = await prisma.verificationToken.findUnique({
      where: { token },
    });

    if (!record || record.expires < new Date()) {
      return NextResponse.json(
        { error: 'This reset link is invalid or has expired.' },
        { status: 400 },
      );
    }

    if (!record.identifier.startsWith('reset:')) {
      return NextResponse.json(
        { error: 'Invalid reset token.' },
        { status: 400 },
      );
    }

    const email = record.identifier.replace(/^reset:/, '');

    const passwordHash = await hash(password, 12);

    await prisma.user.updateMany({
      where: { email },
      data: { passwordHash },
    });

    await prisma.verificationToken.delete({
      where: { token },
    });

    return NextResponse.json({ success: true }, { status: 200 });
  } catch (error) {
    console.error('[reset-password] Failed to reset password', error);
    return NextResponse.json(
      { error: 'Something went wrong. Please try again.' },
      { status: 500 },
    );
  }
}

