import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';

/**
 * Get waitlist status and referral stats for a given email.
 * Public endpoint (no auth required) but rate-limited by email verification.
 */

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const email = searchParams.get('email');

  if (!email || typeof email !== 'string') {
    return NextResponse.json({ error: 'Email required' }, { status: 400 });
  }

  const normalizedEmail = email.trim().toLowerCase();

  try {
    const entry = await prisma.waitlist.findUnique({
      where: { email: normalizedEmail },
      select: {
        id: true,
        email: true,
        tier: true,
        status: true,
        referralCode: true,
        referralCount: true,
        verifiedAt: true,
        createdAt: true,
      },
    });

    if (!entry) {
      return NextResponse.json({ error: 'Not found' }, { status: 404 });
    }

    // Get position in waitlist (count of verified entries before this one, same tier)
    const position = await prisma.waitlist.count({
      where: {
        tier: entry.tier,
        status: { in: ['pending', 'invited'] },
        verifiedAt: { not: null },
        createdAt: { lt: entry.createdAt },
      },
    }) + 1;

    // Generate referral URL
    const referralUrl = entry.referralCode 
      ? `${process.env.NEXTAUTH_URL || 'https://winzinvest.com'}/?ref=${entry.referralCode}`
      : null;

    return NextResponse.json({
      status: entry.status,
      tier: entry.tier,
      referralCode: entry.referralCode,
      referralCount: entry.referralCount,
      referralUrl,
      position: entry.status === 'pending' ? position : null,
      verifiedAt: entry.verifiedAt,
    });
  } catch (err) {
    console.error('Waitlist status error:', err);
    return NextResponse.json({ error: 'Failed to fetch status' }, { status: 500 });
  }
}
