import { NextResponse } from 'next/server';
import { prisma } from '../../../lib/prisma';
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

    if (!isValidEmail(emailRaw)) {
      return NextResponse.json(
        { error: 'Please enter a valid email address.' },
        { status: 400 },
      );
    }

    const email = emailRaw.trim().toLowerCase();

    const user = await prisma.user.findUnique({
      where: { email },
      select: { id: true, emailVerified: true },
    });

    // Do not reveal whether the account exists or is verified.
    if (!user || !user.emailVerified) {
      return NextResponse.json(
        { success: true },
        { status: 200 },
      );
    }

    if (!process.env.RESEND_API_KEY) {
      console.error(
        '[password-reset] RESEND_API_KEY not set — cannot send reset email',
      );
      return NextResponse.json(
        { error: 'Password reset is not configured.' },
        { status: 503 },
      );
    }

    const token = randomBytes(32).toString('hex');
    const expires = new Date(Date.now() + 1000 * 60 * 60); // 1 hour

    await prisma.verificationToken.create({
      data: {
        identifier: `reset:${email}`,
        token,
        expires,
      },
    });

    const baseUrl =
      process.env.NEXTAUTH_URL ?? 'http://localhost:3000';
    const resetUrl = `${baseUrl}/reset-password?token=${encodeURIComponent(
      token,
    )}`;

    const resend = new Resend(process.env.RESEND_API_KEY);

    await resend.emails.send({
      from: 'Winzinvest <no-reply@winzinvest.com>',
      to: email,
      subject: 'Reset your Winzinvest password',
      text: `We received a request to reset your Winzinvest password.\n\nYou can reset it here:\n\n${resetUrl}\n\nIf you did not request this, you can safely ignore this email.`,
    });

    return NextResponse.json({ success: true }, { status: 200 });
  } catch (error) {
    console.error('[password-reset] Failed to send reset email', error);
    return NextResponse.json(
      { error: 'Something went wrong. Please try again.' },
      { status: 500 },
    );
  }
}

