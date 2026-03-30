import { Resend } from 'resend';
import { NextResponse } from 'next/server';
import { prisma } from '../../../lib/prisma';
import { randomBytes } from 'crypto';

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

  const { email, tier, referredBy } = body as Record<string, unknown>;

  if (!isValidEmail(email)) {
    return NextResponse.json({ error: 'Invalid email address.' }, { status: 400 });
  }

  if (!isValidTier(tier)) {
    return NextResponse.json({ error: 'Invalid tier.' }, { status: 400 });
  }

  const normalizedEmail = email.trim().toLowerCase();
  const referralCode = typeof referredBy === 'string' && referredBy.length > 0 
    ? referredBy.trim().toUpperCase() 
    : null;

  try {
    // 1. Check for existing entry
    const existing = await prisma.waitlist.findUnique({
      where: { email: normalizedEmail },
    });

    if (existing) {
      // If already verified/pending, return success
      if (existing.status === 'pending' || existing.status === 'invited' || existing.status === 'active') {
        return NextResponse.json({ ok: true });
      }
      
      // If unverified, resend verification email
      if (existing.status === 'unverified' && existing.verificationToken) {
        await sendVerificationEmail(normalizedEmail, existing.verificationToken, tier);
        return NextResponse.json({ ok: true, message: 'Verification email resent.' });
      }
    }

    // 2. Generate verification token and referral code
    const verificationToken = randomBytes(32).toString('hex');
    const myReferralCode = randomBytes(4).toString('hex').toUpperCase(); // 8-char code

    // 3. Validate referral code if provided
    let referrerEntry = null;
    if (referralCode) {
      referrerEntry = await prisma.waitlist.findUnique({
        where: { referralCode: referralCode },
      });
      
      // If invalid referral code, still allow signup but don't link
      if (!referrerEntry) {
        console.warn(`Invalid referral code provided: ${referralCode}`);
      }
    }

    // 4. Save to database with unverified status
    const waitlistEntry = await prisma.waitlist.create({
      data: {
        email: normalizedEmail,
        tier,
        status: 'unverified',
        source: referralCode && referrerEntry ? 'referral' : 'landing',
        verificationToken,
        referralCode: myReferralCode,
        referredBy: referrerEntry ? referralCode : null,
      },
    });

    // 5. Increment referrer's count if valid referral
    if (referrerEntry) {
      await prisma.waitlist.update({
        where: { id: referrerEntry.id },
        data: { referralCount: { increment: 1 } },
      });
    }

    // 6. Send verification email
    await sendVerificationEmail(normalizedEmail, verificationToken, tier);

    return NextResponse.json({ 
      ok: true, 
      id: waitlistEntry.id,
      referralCode: myReferralCode,
    });
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

async function sendVerificationEmail(email: string, token: string, tier: string): Promise<void> {
  if (!process.env.RESEND_API_KEY) {
    console.warn('RESEND_API_KEY not set - skipping verification email');
    return;
  }

  const resend = new Resend(process.env.RESEND_API_KEY);
  const verifyUrl = `${process.env.NEXTAUTH_URL || 'https://winzinvest.com'}/verify-email?token=${token}`;

  const tierNames = {
    intelligence: 'Intelligence ($49/mo)',
    automation: 'Automation ($149/mo)',
    professional: 'Professional ($399/mo)',
    founding: 'Founding Member ($79/mo)',
  };

  try {
    await resend.emails.send({
      from: 'Winzinvest <hello@winzinvest.com>',
      to: email,
      subject: 'Verify your email for Winzinvest waitlist',
      html: `
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
          <h1 style="color: #1a1a1a; font-size: 24px; font-weight: 600; margin: 0 0 24px 0;">
            Confirm your email
          </h1>
          
          <p style="color: #4a4a4a; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
            You requested to join the <strong>${tierNames[tier as keyof typeof tierNames] || tier}</strong> waitlist for Winzinvest.
          </p>
          
          <p style="color: #4a4a4a; font-size: 16px; line-height: 1.6; margin: 0 0 32px 0;">
            Click the button below to verify your email address:
          </p>
          
          <div style="text-align: center; margin: 0 0 32px 0;">
            <a href="${verifyUrl}" 
               style="display: inline-block; background: #1a1a1a; color: #ffffff; padding: 14px 32px; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 16px;">
              Verify Email Address
            </a>
          </div>
          
          <p style="color: #737373; font-size: 14px; line-height: 1.5; margin: 0 0 16px 0;">
            Or copy and paste this link into your browser:
          </p>
          
          <p style="color: #737373; font-size: 14px; line-height: 1.5; margin: 0 0 32px 0; word-break: break-all;">
            ${verifyUrl}
          </p>
          
          <hr style="border: none; border-top: 1px solid #e5e5e5; margin: 32px 0;" />
          
          <p style="color: #9a9a9a; font-size: 12px; line-height: 1.5; margin: 0;">
            If you didn't request to join the Winzinvest waitlist, you can safely ignore this email.
          </p>
        </div>
      `,
    });
  } catch (emailError) {
    console.error('Failed to send verification email:', emailError);
    throw emailError; // Propagate to trigger retry or alert
  }
}
