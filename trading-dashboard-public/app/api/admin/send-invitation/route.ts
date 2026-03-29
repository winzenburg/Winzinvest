import { NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '../../../../lib/auth';
import { prisma } from '../../../../lib/prisma';
import { Resend } from 'resend';
import crypto from 'crypto';

async function requireAdmin() {
  const session = await getServerSession(authOptions);
  if (!session || session.user?.email !== process.env.ADMIN_EMAIL) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }
  return null;
}

function generateInvitationToken(): string {
  return crypto.randomBytes(32).toString('hex');
}

function generateMagicLink(email: string, token: string): string {
  const baseUrl = process.env.NEXTAUTH_URL || 'http://localhost:3000';
  const params = new URLSearchParams({ email, token });
  return `${baseUrl}/onboard?${params}`;
}

export async function POST(req: Request) {
  const unauth = await requireAdmin();
  if (unauth) return unauth;

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 });
  }

  const { waitlistId } = body as Record<string, unknown>;

  if (typeof waitlistId !== 'string') {
    return NextResponse.json({ error: 'Invalid waitlist ID' }, { status: 400 });
  }

  try {
    const entry = await prisma.waitlist.findUnique({
      where: { id: waitlistId },
    });

    if (!entry) {
      return NextResponse.json({ error: 'Entry not found' }, { status: 404 });
    }

    if (entry.status !== 'pending') {
      return NextResponse.json(
        { error: `Entry is already ${entry.status}` },
        { status: 400 }
      );
    }

    const invitationToken = generateInvitationToken();
    const magicLink = generateMagicLink(entry.email, invitationToken);

    await prisma.waitlist.update({
      where: { id: waitlistId },
      data: {
        status: 'invited',
        invitedAt: new Date(),
        invitationToken,
      },
    });

    if (!process.env.RESEND_API_KEY) {
      return NextResponse.json(
        { error: 'Email service not configured' },
        { status: 503 }
      );
    }

    const resend = new Resend(process.env.RESEND_API_KEY);

    const tierNames = {
      intelligence: 'Intelligence',
      automation: 'Automation',
      professional: 'Professional',
      founding: 'Founding Member',
    };

    const tierName = tierNames[entry.tier as keyof typeof tierNames] || entry.tier;

    await resend.emails.send({
      from: 'Winzinvest <onboarding@winzinvest.com>',
      to: entry.email,
      subject: `Welcome to Winzinvest Beta - You're In!`,
      html: `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; background-color: #f9fafb;">
  <div style="max-width: 600px; margin: 40px auto; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
    <div style="padding: 40px 32px; text-align: center; border-bottom: 1px solid #e5e7eb;">
      <h1 style="margin: 0; font-size: 28px; font-weight: 700; color: #111827;">Welcome to Winzinvest Beta</h1>
      <p style="margin: 12px 0 0 0; font-size: 16px; color: #6b7280;">You're approved for early access</p>
    </div>
    
    <div style="padding: 32px;">
      <p style="margin: 0 0 16px 0; font-size: 15px; line-height: 1.6; color: #374151;">
        You've been selected for early access to <strong>${tierName}</strong> tier testing.
      </p>
      
      <p style="margin: 0 0 24px 0; font-size: 15px; line-height: 1.6; color: #374151;">
        Click the button below to set up your account and start exploring the platform:
      </p>
      
      <div style="text-align: center; margin: 32px 0;">
        <a href="${magicLink}" style="display: inline-block; padding: 14px 28px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 15px;">
          Complete Onboarding
        </a>
      </div>
      
      <p style="margin: 24px 0 0 0; font-size: 14px; line-height: 1.6; color: #6b7280;">
        This link is valid for 48 hours. If you need help, reply to this email.
      </p>
    </div>
    
    <div style="padding: 24px 32px; background-color: #f9fafb; border-top: 1px solid #e5e7eb; text-align: center;">
      <p style="margin: 0; font-size: 13px; color: #9ca3af;">
        Winzinvest &bull; Automated Trading System
      </p>
    </div>
  </div>
</body>
</html>
      `,
    });

    return NextResponse.json({
      ok: true,
      message: 'Invitation sent successfully',
      magicLink,
    });
  } catch (error) {
    console.error('Failed to send invitation:', error);
    return NextResponse.json({ error: 'Failed to send invitation' }, { status: 500 });
  }
}
