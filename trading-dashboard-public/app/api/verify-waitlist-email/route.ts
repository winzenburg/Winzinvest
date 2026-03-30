import { NextResponse } from 'next/server';
import { prisma } from '../../../lib/prisma';
import { Resend } from 'resend';

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const token = searchParams.get('token');

  if (!token || typeof token !== 'string') {
    return NextResponse.json({ error: 'Invalid verification link.' }, { status: 400 });
  }

  try {
    // Find waitlist entry by verification token
    const entry = await prisma.waitlist.findUnique({
      where: { verificationToken: token },
    });

    if (!entry) {
      return NextResponse.json({ error: 'Invalid or expired verification link.' }, { status: 404 });
    }

    if (entry.status !== 'unverified') {
      // Already verified
      return NextResponse.json({ 
        ok: true, 
        message: 'Email already verified.',
        alreadyVerified: true,
        email: entry.email,
      });
    }

    // Update status to pending and mark as verified
    await prisma.waitlist.update({
      where: { id: entry.id },
      data: {
        status: 'pending',
        verifiedAt: new Date(),
      },
    });

    // Sync to Resend audience (optional)
    if (process.env.RESEND_API_KEY && process.env.RESEND_AUDIENCE_ID) {
      const resend = new Resend(process.env.RESEND_API_KEY);
      
      try {
        await resend.contacts.create({
          email: entry.email,
          audienceId: process.env.RESEND_AUDIENCE_ID,
          unsubscribed: false,
          firstName: entry.tier,
          lastName: '',
        });
      } catch (resendError) {
        console.warn('Resend sync failed (non-critical):', resendError);
      }
    }

    return NextResponse.json({ 
      ok: true, 
      message: 'Email verified successfully!',
      tier: entry.tier,
      email: entry.email,
    });
  } catch (err) {
    console.error('Verification error:', err);
    return NextResponse.json(
      { error: 'Could not verify email. Please try again.' },
      { status: 500 },
    );
  }
}
