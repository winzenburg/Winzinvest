# Kinlet Admin Access - What's Needed for Phase 1 Email Execution

**Status:** BLOCKED (waiting for admin dashboard access)  
**Priority:** CRITICAL for Week 1 GTM success  
**Expected Impact:** +18 signups if executed (9 existing × ~2 referral conversions)

---

## CURRENT SITUATION

**We have:** 9 existing waitlist signups  
**We have:** Email template ready to send  
**We DON'T have:** Access to get names + emails + ability to generate referral links

**Without admin access:** Can execute Reddit (3 posts) + DM outreach (15 DMs) = ~13-20 signups  
**With admin access:** Can also email 9 existing signups + their referrals = ~26-40 new signups total

**Critical path:** Get admin access ASAP to maximize Week 1

---

## WHAT WE NEED FROM KINLET ADMIN PANEL

### 1. Email List of 9 Waitlist Signups
**File:** Signup export (CSV or JSON)  
**Required fields:**
- [ ] First name
- [ ] Email address
- [ ] Signup date (optional but useful)
- [ ] Relationship to person with dementia (optional but useful)

**Example format:**
```
First Name,Email,Signup Date
Jane,jane@example.com,2026-02-10
Sarah,sarah@example.com,2026-02-12
Robert,robert@example.com,2026-02-08
[etc.]
```

### 2. Referral Link Generation Capability
**What we need:** Ability to create unique referral links for each person

**Option A: Simple manual approach**
- Admin generates 9 unique referral codes (one per person)
- Format: https://kinlet.care/?ref=jane_smith_001
- Can be generated manually or via admin dashboard

**Option B: Automated approach**
- Admin dashboard has built-in referral link generator
- Each signup gets unique link automatically
- We export the mapping (person → their referral link)

**Either works** - just need the 9 unique links

### 3. Analytics Tracking
**For attribution:** Need way to track which email/DM drove which signup

**Minimum:** Each referral link should track:
- [ ] Which person shared the link (source)
- [ ] Who clicked it (recipient)
- [ ] Did they sign up? (conversion)

**Ideal:** Dashboard shows:
- Signup source (email from Jane, DM from reddit user X, etc.)
- Conversion date
- Referral chain (Jane → Sarah → Family friend = 3 signups from 1 email)

---

## ACTION ITEMS FOR RYAN

### IMMEDIATE (Today/Tomorrow)

**Step 1: Determine who has admin access**
- [ ] Is there a Kinlet admin panel/dashboard?
- [ ] Who has login credentials?
- [ ] Is it you, a co-founder, or someone else?

**Step 2: Request required data**
If you don't have access yourself:
- Email/message admin with this checklist
- Include message: "Need to execute Phase 1 email outreach by Feb 26. Need: 9 email addresses + ability to generate referral links."
- Set SLA: "Need this by Feb 23 AM" (3 days from now)

**Step 3: Get the data**
- [ ] Receive email export (9 signups)
- [ ] Verify all fields present (name, email, etc.)
- [ ] Get 9 unique referral links
- [ ] Test one link to verify it works

### BY FEB 23, 8:00 AM (LATEST)

**Step 4: Prepare email personalization**
Once you have the list, you'll have:
- [ ] Jane's email address
- [ ] Jane's referral link: [unique link 1]
- [ ] Sarah's email address
- [ ] Sarah's referral link: [unique link 2]
- [etc. for all 9]

**Step 5: Execute email batch (Feb 26, once you have data)**
- [ ] Time: 10-15 minutes to send 9 emails
- [ ] Template: email-existing-signups.md (ready to use)
- [ ] Just swap names + referral links
- [ ] Send all 9 at once or batch over 2 hours (up to you)

---

## EMAIL TEMPLATE (Ready to Use)

**Subject:** "We're forming the first groups this week"

**Body:**

Hi [First Name],

You joined the Kinlet waitlist a few weeks ago. Thank you for trusting us.

We're forming the first groups this week—small, matched support groups for people caring for someone with Alzheimer's or dementia.

**If you know someone who's going through this, they should join too.**

Here's your personal invite link:  
[THEIR UNIQUE REFERRAL LINK]

When they join and confirm their email, you'll move up in line for the Founder Cohort (priority matching into the first groups).

No pressure. Just wanted you to know we're ready.

– Ryan  
Kinlet

---

**P.S.** If you're not sure this is for you anymore, that's okay. Just reply and I'll remove you from the list.

---

## EXPECTED OUTCOME (With Email)

**Emails sent:** 9  
**Expected response rate:** 20-30% (caregivers are time-poor)  
**Expected referral signups:** 9-18 (1-2 per email)  
**Impact on Week 1 goal:** Brings total to 22-38 new signups (vs. 13-20 without email)

---

## IF ADMIN ACCESS IS DELAYED...

**Worst case:** Admin access isn't available until mid-Week 2  
**Workaround 1:** Use generic Kinlet.care link for all referrals, track manually in Google Sheet  
**Workaround 2:** Ask people to mention "who referred you" in signup form, track that way  
**Workaround 3:** Send DMs to 9 people instead (more personal, less scalable)

**Still better than nothing**, but loses attribution data.

---

## NICE-TO-HAVE (Optional)

**If admin panel has these features, even better:**

- [ ] Email template builder (but we have template, so not critical)
- [ ] Scheduling (send at optimal time for each timezone)
- [ ] A/B testing (test 2 subject lines, see which converts better)
- [ ] Drip campaigns (automated follow-ups if they don't click)
- [ ] Dashboard to see email opens + clicks in real-time

**But these are optional.** We can execute Phase 1 with just email addresses + referral links.

---

## ADMIN ACCESS CHECKLIST (What to Ask For)

**Copy-paste this in your message to admin:**

```
Hi,

Need admin access to execute Phase 1 GTM for Kinlet this week. Specifically need:

CRITICAL:
[ ] Export of 9 waitlist signups (first name, email address)
[ ] Ability to generate unique referral links (9 total)
    - Format: Can be manual links or dashboard-generated
    - Need mapping: signup name → referral link

OPTIONAL:
[ ] Analytics to track which email drove which signup
[ ] Email sending tool (we have template, can send manually)

Timeline: Need by Monday Feb 24 AM to execute Phase 1.

Thanks,
Ryan
```

---

## CONTACT INFO

**If unsure who has admin access:**
- Check Kinlet GitHub repo (README usually lists founders/maintainers)
- Check Kinlet.care footer (often has "Contact" or "Team" link)
- Check internal team Slack/Discord
- Check your own email (you may have received admin invite)

---

## SUCCESS CRITERIA

✅ Have email list of 9 signups by Feb 24 AM  
✅ Have 9 unique referral links by Feb 24 AM  
✅ Can send emails by Feb 26 AM  
✅ Referral links track signups in analytics by Feb 28

---

**Current Status:** WAITING FOR ADMIN ACCESS  
**Backup Plan:** Manual tracking + generic links if admin access delayed  
**Time Required (once data received):** 15 minutes to send emails  
**Impact:** +18 potential signups with email outreach (vs. +0 without)

