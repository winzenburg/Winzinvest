import { NextResponse } from 'next/server';
import { prisma } from '../../../lib/prisma';
import { hash } from 'bcryptjs';
import { randomBytes } from 'crypto';
import { Resend } from 'resend';

function isValidEmail(email: unknown): email is string {
  return (
    typeof email === 'string' &&
    email.length <= 254 &&
    /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())
  );
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const emailRaw = body.email;
    const password: string = body.password ?? '';
    const name: string | undefined = body.name;

    if (!isValidEmail(emailRaw)) {
      return NextResponse.json(
        { error: 'Please enter a valid email address.' },
        { status: 400 },
      );
    }

    const email = emailRaw.trim().toLowerCase();

    if (!password) {
      return NextResponse.json(
        { error: 'Email and password are required.' },
        { status: 400 },
      );
    }

    if (password.length < 8) {
      return NextResponse.json(
        { error: 'Password must be at least 8 characters long.' },
        { status: 400 },
      );
    }

    const existing = await prisma.user.findUnique({
      where: { email },
      select: { id: true },
    });

    if (existing) {
      return NextResponse.json(
        { error: 'An account with this email already exists.' },
        { status: 409 },
      );
    }

    const userCount = await prisma.user.count();
    const passwordHash = await hash(password, 12);

    const user = await prisma.user.create({
      data: {
        email,
        name: name?.trim() || null,
        passwordHash,
        role: userCount === 0 ? 'admin' : 'user',
      },
    });

    if (!process.env.RESEND_API_KEY) {
      console.error('[register] RESEND_API_KEY not set — skipping verification email');
      return NextResponse.json(
        {
          success: true,
          message:
            'Account created. Email verification is not configured on this environment.',
        },
        { status: 201 },
      );
    }

    const token = randomBytes(32).toString('hex');
    const expires = new Date(Date.now() + 1000 * 60 * 60 * 24); // 24 hours

    await prisma.verificationToken.create({
      data: {
        identifier: `verify:${user.email}`,
        token,
        expires,
      },
    });

    const baseUrl =
      process.env.NEXTAUTH_URL ?? 'http://localhost:3000';
    const verifyUrl = `${baseUrl}/verify-email?token=${encodeURIComponent(
      token,
    )}`;

    const resend = new Resend(process.env.RESEND_API_KEY);

    await resend.emails.send({
      from: 'Winzinvest <no-reply@winzinvest.com>',
      to: user.email ?? '',
      subject: 'Verify your email for Winzinvest',
      text: `Welcome to Winzinvest.\n\nConfirm your email to finish setting up your account:\n\n${verifyUrl}\n\nIf you did not request this, you can ignore this email.`,
    });

    return NextResponse.json(
      {
        success: true,
        message: 'Account created. Check your email to verify your address.',
      },
      { status: 201 },
    );
  } catch (error) {
    console.error('[register] Failed to create user', error);
    return NextResponse.json(
      { error: 'Something went wrong. Please try again.' },
      { status: 500 },
    );
  }
}

