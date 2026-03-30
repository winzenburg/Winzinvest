import { NextRequest, NextResponse } from 'next/server';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { join } from 'path';

const UNSUBSCRIBE_FILE = join(process.cwd(), '..', 'trading', 'logs', 'email_unsubscribes.json');

interface UnsubscribeData {
  emails: string[];
  updated_at: string;
}

function loadUnsubscribes(): UnsubscribeData {
  if (!existsSync(UNSUBSCRIBE_FILE)) {
    return { emails: [], updated_at: new Date().toISOString() };
  }
  try {
    return JSON.parse(readFileSync(UNSUBSCRIBE_FILE, 'utf-8'));
  } catch {
    return { emails: [], updated_at: new Date().toISOString() };
  }
}

function saveUnsubscribes(data: UnsubscribeData): void {
  writeFileSync(UNSUBSCRIBE_FILE, JSON.stringify(data, null, 2), 'utf-8');
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const email = searchParams.get('email');
  const action = searchParams.get('action');

  if (!email) {
    return new NextResponse(
      `<html><body style="font-family: -apple-system, sans-serif; padding: 40px; text-align: center;">
        <h1>Invalid Request</h1>
        <p>No email address provided.</p>
      </body></html>`,
      { status: 400, headers: { 'Content-Type': 'text/html' } }
    );
  }

  // Handle unsubscribe action
  if (action === 'confirm') {
    const data = loadUnsubscribes();
    const normalizedEmail = email.toLowerCase().trim();
    
    if (!data.emails.includes(normalizedEmail)) {
      data.emails.push(normalizedEmail);
      data.updated_at = new Date().toISOString();
      saveUnsubscribes(data);
    }

    return new NextResponse(
      `<html><head><meta charset="utf-8"></head>
      <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 40px; max-width: 600px; margin: 0 auto;">
        <div style="text-align: center; padding: 40px 20px; background: #f8f9fb; border-radius: 12px; border: 1px solid #e9ecef;">
          <h1 style="color: #0f2027; margin: 0 0 16px;">Unsubscribed Successfully</h1>
          <p style="color: #495057; font-size: 16px; line-height: 1.6;">
            <strong>${email}</strong> has been removed from the Winzinvest mailing list.
          </p>
          <p style="color: #868e96; font-size: 14px; margin-top: 24px;">
            You will no longer receive daily position updates or market reports.
          </p>
        </div>
      </body></html>`,
      { headers: { 'Content-Type': 'text/html' } }
    );
  }

  // Show confirmation page
  return new NextResponse(
    `<html><head><meta charset="utf-8"></head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 40px; max-width: 600px; margin: 0 auto;">
      <div style="text-align: center; padding: 40px 20px; background: #fff8e1; border-radius: 12px; border: 1px solid #f59e0b; border-left: 4px solid #f59e0b;">
        <h1 style="color: #92400e; margin: 0 0 16px;">Confirm Unsubscribe</h1>
        <p style="color: #78350f; font-size: 16px; line-height: 1.6;">
          Are you sure you want to unsubscribe <strong>${email}</strong> from Winzinvest updates?
        </p>
        <div style="margin-top: 32px;">
          <a href="/api/unsubscribe?email=${encodeURIComponent(email)}&action=confirm" 
             style="display: inline-block; padding: 12px 32px; background: #c62828; color: white; 
                    text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 14px;">
            Yes, Unsubscribe
          </a>
        </div>
        <p style="color: #a8a29e; font-size: 13px; margin-top: 24px;">
          Changed your mind? Just close this page.
        </p>
      </div>
    </body></html>`,
    { headers: { 'Content-Type': 'text/html' } }
  );
}
