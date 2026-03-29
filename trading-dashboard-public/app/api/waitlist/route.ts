import { Resend } from 'resend';
import { NextResponse } from 'next/server';
import { prisma } from '../../../lib/prisma';
const VALID_TIERS = new Set(['intelligence', 'automation', 'professional', 'founding']);

function isValidEmail(email: unknown): email is string {
  return (
    typeof email === 'string' &&
    email.length <= 254 &&
    /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())
  );
}

function isValidTier(tier: unknown): tier is string {
  return typeof tier === 'string' && VALID_TIERS.has(tier);
}

export async function POST(req: Request) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'Invalid request body.' }, { status: 400 });
  }

  const { email, tier } = body as Record<string, unknown>;

  if (!isValidEmail(email)) {
    return NextResponse.json({ error: 'Invalid email address.' }, { status: 400 });
  }

  if (!isValidTier(tier)) {
    return NextResponse.json({ error: 'Invalid tier.' }, { status: 400 });
  }

  const normalizedEmail = email.trim().toLowerCase();

  try {
    // 1. Save to PostgreSQL (source of truth)
    const existing = await prisma.waitlist.findUnique({
      where: { email: normalizedEmail },
    });

    if (existing) {
      // Already on list - return success without revealing duplicate
      return NextResponse.json({ ok: true });
    }

    const waitlistEntry = await prisma.waitlist.create({
      data: {
        email: normalizedEmail,
        tier,
        status: 'pending',
        source: 'landing',
      },
    });

    // 2. Sync to Resend (for email automation) - non-blocking
    if (process.env.RESEND_API_KEY && process.env.RESEND_AUDIENCE_ID) {
      const resend = new Resend(process.env.RESEND_API_KEY);
      
      try {
        await resend.contacts.create({
          email: normalizedEmail,
          audienceId: process.env.RESEND_AUDIENCE_ID,
          unsubscribed: false,
          firstName: tier,
          lastName: '',
        });
      } catch (resendError) {
        // Log but don't fail - PostgreSQL is source of truth
        console.warn('Resend sync failed (non-critical):', resendError);
      }
    }

    return NextResponse.json({ ok: true, id: waitlistEntry.id });
  } catch (err) {
    console.error('Waitlist database error:', err);
    console.error('Error details:', JSON.stringify(err, Object.getOwnPropertyNames(err)));
    console.error('DATABASE_URL exists:', !!process.env.DATABASE_URL);
    console.error('DATABASE_URL prefix:', process.env.DATABASE_URL?.substring(0, 30));
    return NextResponse.json(
      { error: 'Could not add you to the waitlist. Please try again.' },
      { status: 500 },
    );
  }
}
