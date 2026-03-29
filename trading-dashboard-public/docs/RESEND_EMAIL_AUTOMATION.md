# Resend Email Automation Setup

This document provides the configuration for the automated email sequence for waitlist signups.

## Overview

When a user joins the waitlist, they are automatically added to a Resend audience (via the `/api/waitlist` endpoint). Resend's Broadcasts and Automations features handle the drip email sequence.

## Email Sequence

### Email 1: Welcome (T+0 - Immediate)

**Subject:** Welcome to Winzinvest Beta - Here's What's Next

**Send:** Immediately upon audience contact creation

**Content:**

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; background-color: #f9fafb;">
  <div style="max-width: 600px; margin: 40px auto; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
    <div style="padding: 40px 32px; text-align: center; border-bottom: 1px solid #e5e7eb;">
      <h1 style="margin: 0; font-size: 28px; font-weight: 700; color: #111827;">You're on the List</h1>
      <p style="margin: 12px 0 0 0; font-size: 16px; color: #6b7280;">Welcome to Winzinvest Beta</p>
    </div>
    
    <div style="padding: 32px;">
      <p style="margin: 0 0 16px 0; font-size: 15px; line-height: 1.6; color: #374151;">
        Thanks for joining the beta testing program. You're in the queue for early access to our automated trading system.
      </p>
      
      <p style="margin: 0 0 16px 0; font-size: 15px; line-height: 1.6; color: #374151;">
        Over the next two weeks, we'll send you a few emails to help you understand:
      </p>
      
      <ul style="margin: 0 0 16px 0; padding-left: 24px; font-size: 15px; line-height: 1.8; color: #374151;">
        <li>Why we built this system</li>
        <li>How our risk management works</li>
        <li>What makes our execution gates unique</li>
      </ul>
      
      <p style="margin: 0 0 16px 0; font-size: 15px; line-height: 1.6; color: #374151;">
        When we're ready for your cohort, you'll receive an invitation email with your dashboard access.
      </p>
      
      <div style="margin-top: 32px; padding-top: 24px; border-top: 1px solid #e5e7eb;">
        <p style="margin: 0; font-size: 14px; color: #6b7280;">
          <strong>What to expect:</strong><br>
          • Beta testing begins in phases<br>
          • You'll get full access to the dashboard<br>
          • Direct line to the team for feedback
        </p>
      </div>
    </div>
    
    <div style="padding: 24px 32px; background-color: #f9fafb; border-top: 1px solid #e5e7eb; text-align: center;">
      <p style="margin: 0; font-size: 13px; color: #9ca3af;">
        Winzinvest &bull; Automated Trading System
      </p>
    </div>
  </div>
</body>
</html>
```

---

### Email 2: Why We Built This (T+3 Days)

**Subject:** The Discipline Problem in Trading

**Send:** 3 days after contact creation

**Content:**

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; background-color: #f9fafb;">
  <div style="max-width: 600px; margin: 40px auto; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
    <div style="padding: 40px 32px; text-align: center; border-bottom: 1px solid #e5e7eb;">
      <h1 style="margin: 0; font-size: 28px; font-weight: 700; color: #111827;">The Problem We're Solving</h1>
    </div>
    
    <div style="padding: 32px;">
      <p style="margin: 0 0 16px 0; font-size: 15px; line-height: 1.6; color: #374151;">
        Most traders know <em>what</em> to do. The hard part is actually doing it when emotions run high.
      </p>
      
      <p style="margin: 0 0 16px 0; font-size: 15px; line-height: 1.6; color: #374151;">
        That's why we built Winzinvest: a system that enforces discipline automatically.
      </p>
      
      <div style="margin: 24px 0; padding: 20px; background-color: #f3f4f6; border-left: 4px solid #2563eb; border-radius: 4px;">
        <p style="margin: 0; font-size: 15px; line-height: 1.6; color: #1f2937; font-weight: 600;">
          Key Insight:
        </p>
        <p style="margin: 8px 0 0 0; font-size: 15px; line-height: 1.6; color: #374151;">
          The best traders don't rely on willpower. They build systems that make correct decisions automatic.
        </p>
      </div>
      
      <p style="margin: 0 0 16px 0; font-size: 15px; line-height: 1.6; color: #374151;">
        Our execution gates prevent emotional overrides:
      </p>
      
      <ul style="margin: 0 0 16px 0; padding-left: 24px; font-size: 15px; line-height: 1.8; color: #374151;">
        <li>Can't add to losing positions</li>
        <li>Can't override stop losses</li>
        <li>Can't exceed sector concentration limits</li>
        <li>Can't flip position sides (long to short or vice versa)</li>
      </ul>
      
      <p style="margin: 0; font-size: 15px; line-height: 1.6; color: #374151;">
        Next email: We'll show you how regime detection works under the hood.
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
```

---

### Email 3: Inside the System (T+7 Days)

**Subject:** How Winzinvest Adapts to Market Regimes

**Send:** 7 days after contact creation

**Content:**

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; background-color: #f9fafb;">
  <div style="max-width: 600px; margin: 40px auto; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
    <div style="padding: 40px 32px; text-align: center; border-bottom: 1px solid #e5e7eb;">
      <h1 style="margin: 0; font-size: 28px; font-weight: 700; color: #111827;">Regime Detection</h1>
      <p style="margin: 12px 0 0 0; font-size: 16px; color: #6b7280;">How the system adapts</p>
    </div>
    
    <div style="padding: 32px;">
      <p style="margin: 0 0 16px 0; font-size: 15px; line-height: 1.6; color: #374151;">
        The market isn't static, so your strategy shouldn't be either.
      </p>
      
      <p style="margin: 0 0 16px 0; font-size: 15px; line-height: 1.6; color: #374151;">
        Winzinvest classifies market conditions into five regimes:
      </p>
      
      <div style="margin: 24px 0;">
        <div style="margin-bottom: 16px; padding: 16px; background-color: #f0fdf4; border-left: 4px solid #22c55e; border-radius: 4px;">
          <p style="margin: 0; font-size: 14px; font-weight: 600; color: #166534;">STRONG UPTREND</p>
          <p style="margin: 8px 0 0 0; font-size: 14px; color: #374151;">Longs + covered calls, no shorts</p>
        </div>
        
        <div style="margin-bottom: 16px; padding: 16px; background-color: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 4px;">
          <p style="margin: 0; font-size: 14px; font-weight: 600; color: #92400e;">CHOPPY</p>
          <p style="margin: 8px 0 0 0; font-size: 14px; color: #374151;">Premium selling + mean reversion</p>
        </div>
        
        <div style="margin-bottom: 16px; padding: 16px; background-color: #fee2e2; border-left: 4px solid #ef4444; border-radius: 4px;">
          <p style="margin: 0; font-size: 14px; font-weight: 600; color: #991b1b;">STRONG DOWNTREND</p>
          <p style="margin: 8px 0 0 0; font-size: 14px; color: #374151;">Shorts + protective puts, no longs</p>
        </div>
      </div>
      
      <p style="margin: 0 0 16px 0; font-size: 15px; line-height: 1.6; color: #374151;">
        The regime detector runs every 4 hours, analyzing:
      </p>
      
      <ul style="margin: 0 0 16px 0; padding-left: 24px; font-size: 15px; line-height: 1.8; color: #374151;">
        <li>SPY price action & trend strength</li>
        <li>VIX level & term structure</li>
        <li>Market breadth & sector rotation</li>
        <li>Credit spreads & volatility regime</li>
      </ul>
      
      <p style="margin: 0; font-size: 15px; line-height: 1.6; color: #374151;">
        When the regime shifts, the system automatically adjusts which screeners run and which strategies are active.
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
```

---

### Email 4: You're Moving Up (T+14 Days)

**Subject:** You're in Our Next Beta Wave

**Send:** 14 days after contact creation

**Content:**

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; background-color: #f9fafb;">
  <div style="max-width: 600px; margin: 40px auto; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
    <div style="padding: 40px 32px; text-align: center; border-bottom: 1px solid #e5e7eb;">
      <h1 style="margin: 0; font-size: 28px; font-weight: 700; color: #111827;">You're in Our Next Wave</h1>
      <p style="margin: 12px 0 0 0; font-size: 16px; color: #6b7280;">Beta access coming soon</p>
    </div>
    
    <div style="padding: 32px;">
      <p style="margin: 0 0 16px 0; font-size: 15px; line-height: 1.6; color: #374151;">
        We're preparing to onboard your cohort to the Winzinvest beta platform.
      </p>
      
      <div style="margin: 24px 0; padding: 20px; background-color: #eff6ff; border-radius: 8px;">
        <p style="margin: 0 0 12px 0; font-size: 15px; font-weight: 600; color: #1e40af;">
          What You'll Get Access To:
        </p>
        <ul style="margin: 0; padding-left: 24px; font-size: 15px; line-height: 1.8; color: #374151;">
          <li>Live trading dashboard with real-time positions</li>
          <li>Strategy performance analytics and attribution</li>
          <li>Regime detection and execution gates insight</li>
          <li>Trade journal and P&L tracking</li>
          <li>Risk monitoring and alert system</li>
        </ul>
      </div>
      
      <p style="margin: 0 0 16px 0; font-size: 15px; line-height: 1.6; color: #374151;">
        Keep an eye on your inbox - your invitation email will arrive in the next 1-2 weeks.
      </p>
      
      <p style="margin: 0; font-size: 15px; line-height: 1.6; color: #374151;">
        In the meantime, if you have questions about the system or what tier is right for you, just reply to this email.
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
```

---

### Email 5: Invitation (Manual Trigger)

**Subject:** Welcome to Winzinvest Beta - You're In!

**Send:** Manually triggered via admin dashboard when user is approved

**Content:** Already implemented in `/app/api/admin/send-invitation/route.ts`

---

## Configuration Steps in Resend Dashboard

1. **Create Audience:**
   - Go to Resend dashboard → Audiences
   - Create audience named "Winzinvest Beta Waitlist"
   - Copy Audience ID to `RESEND_AUDIENCE_ID` env var

2. **Set Up Automations:**
   - Navigate to Automations section
   - Create automation: "Welcome Email"
     - Trigger: Contact added to audience
     - Delay: 0 minutes
     - Email: Paste Email 1 HTML above
     - From: `onboarding@winzinvest.com`

   - Create automation: "Discipline Email"
     - Trigger: Contact added to audience
     - Delay: 3 days
     - Email: Paste Email 2 HTML above
     - From: `onboarding@winzinvest.com`

   - Create automation: "Inside the System"
     - Trigger: Contact added to audience
     - Delay: 7 days
     - Email: Paste Email 3 HTML above
     - From: `onboarding@winzinvest.com`

   - Create automation: "You're Moving Up"
     - Trigger: Contact added to audience
     - Delay: 14 days
     - Email: Paste Email 4 HTML above
     - From: `onboarding@winzinvest.com`

3. **Domain Verification:**
   - Verify `winzinvest.com` domain in Resend
   - Add DNS records for DKIM/SPF/DMARC
   - Set sending domain to `onboarding@winzinvest.com`

4. **Test the Flow:**
   - Add a test email to the audience manually
   - Verify all automations fire on schedule
   - Check email rendering on mobile/desktop clients

---

## Environment Variables Required

| Variable | Purpose | Where to Get It |
|----------|---------|-----------------|
| `RESEND_API_KEY` | API authentication | Resend dashboard → API Keys |
| `RESEND_AUDIENCE_ID` | Target audience for contacts | Resend dashboard → Audiences |
| `NEXTAUTH_URL` | Base URL for magic links | Your production URL (e.g., `https://winzinvest.com`) |
| `ADMIN_EMAIL` | Admin access control | Your email address |

---

## Testing Checklist

Before going live:
- [ ] Test duplicate email handling (frontend shows success, backend deduplicates)
- [ ] Verify all tier values correctly stored in PostgreSQL
- [ ] Test admin approval flow end-to-end (approve → invitation email → onboarding → account creation)
- [ ] Verify invitation email delivery and magic link generation
- [ ] Test magic link expiry (48 hours)
- [ ] Check email rendering on Gmail, Outlook, Apple Mail (desktop + mobile)
- [ ] Verify CSV export from admin panel
- [ ] Test status filters and tier filters in admin panel
- [ ] Confirm Resend automations fire on correct delays
- [ ] Test password validation (min 8 chars)
- [ ] Verify user account created with correct role

---

## Monitoring

After launch, monitor:
- **PostgreSQL:** Check `Waitlist` table growth and status distribution
- **Resend Dashboard:** Track email open rates, click rates, bounces
- **Admin Panel:** Review pending signups daily, batch invite when ready
- **Logs:** Check Next.js logs for `/api/waitlist` and `/api/admin/*` errors

---

## Notes

- PostgreSQL is the source of truth - Resend sync is non-blocking
- Magic links expire after 48 hours
- Only admin email (from `ADMIN_EMAIL` env) can access `/admin/waitlist`
- Invitation email is sent via Resend Transactional API (not Automations)
- Automated drip emails are sent via Resend Automations (configured in dashboard)
