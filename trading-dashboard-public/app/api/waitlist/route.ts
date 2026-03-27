import { Resend } from 'resend';
import { NextResponse } from 'next/server';

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
  // Validate env is configured
  if (!process.env.RESEND_API_KEY || !process.env.RESEND_AUDIENCE_ID) {
    console.error('Waitlist: RESEND_API_KEY or RESEND_AUDIENCE_ID not set');
    return NextResponse.json(
      { error: 'Waitlist service not configured.' },
      { status: 503 },
    );
  }

  const resend = new Resend(process.env.RESEND_API_KEY as string);

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
    const { error } = await resend.contacts.create({
      email: normalizedEmail,
      audienceId: process.env.RESEND_AUDIENCE_ID,
      unsubscribed: false,
      // Store tier as first name so it's visible in the Resend Audiences UI
      // without needing custom fields (which are on paid plans).
      firstName: tier,
      lastName: '',
    });

    if (error) {
      // Resend returns a duplicate-contact error with code "validation_error"
      // when the email is already on the list — treat as success so we don't
      // leak whether an address is already registered.
      const isDuplicate =
        error.name === 'validation_error' ||
        (error.message ?? '').toLowerCase().includes('already exist');

      if (!isDuplicate) {
        console.error('Waitlist Resend error:', error);
        return NextResponse.json(
          { error: 'Could not add you to the waitlist. Please try again.' },
          { status: 502 },
        );
      }
    }

    return NextResponse.json({ ok: true });
  } catch (err) {
    console.error('Waitlist unexpected error:', err);
    return NextResponse.json(
      { error: 'Unexpected error. Please try again.' },
      { status: 500 },
    );
  }
}
