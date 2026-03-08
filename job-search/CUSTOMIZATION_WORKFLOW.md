# Application Customization Workflow

## Overview

When you find a job opportunity you like, you trigger the customization engine:

```
You: "Anthropic - https://boards.greenhouse.io/anthropic/jobs/..."
     ↓
     Customization Engine
     ├─ Fetch job posting
     ├─ Generate customized cover letter (Sonnet)
     ├─ Customize resume (Sonnet)
     ├─ Create .docx files
     └─ Email to you
     ↓
You: Review + Submit
```

---

## How It Works

### Step 1: Trigger via Telegram
Send a message with company name and job URL:
```
Anthropic - https://boards.greenhouse.io/anthropic/jobs/...
```

### Step 2: Engine Processes
The customization script:
1. **Fetches** the job posting (title, description, requirements)
2. **Loads** your voice guide (VOICE_GUIDE.md)
3. **Generates** a customized cover letter via Claude Sonnet
4. **Customizes** the ATS resume (reorder bullets, add keywords)
5. **Creates** both as .docx files
6. **Emails** both to ryanwinzenburg@gmail.com

### Step 3: You Review
- Open email attachment
- Review customized documents
- Make any edits if needed
- Submit to company

---

## Files Involved

### Input Files
- **Base Cover Letter:** `templates/Resumes/Ryan_Winzenburg_Cover_Letter_Coinbase.docx`
- **Base Resume:** `templates/Resumes/Ryan_Winzenburg_Resume_ATS_Optimized.docx`
- **Voice Guide:** `VOICE_GUIDE.md` (controls tone/style)

### Script
- **Engine:** `customize_application.py`

### Output
- **Directory:** `customized_applications/[Company]/`
- **Files:**
  - `Cover_Letter_[Company].docx`
  - `Resume_[Company].docx`

---

## Running Manually (For Testing)

```bash
cd ~/.openclaw/workspace/job-search

python3 customize_application.py "Anthropic" "https://boards.greenhouse.io/anthropic/jobs/..."
```

This will:
1. Display fetch + customization progress
2. Generate .docx files in `customized_applications/Anthropic/`
3. Compose email with attachments

---

## Integration with Telegram

**In progress:** Setting up Telegram listener to:
1. Monitor your messages for pattern: `[Company] - [URL]`
2. Trigger `customize_application.py` automatically
3. Send email when complete
4. Reply to you with confirmation

---

## Sonnet Customization Logic

### Cover Letter Customization

Sonnet uses your **VOICE_GUIDE.md** to generate a letter that:

✅ Opens with strategic introduction (who you are as a leader)
✅ Includes 1-2 specific initiatives with quantified impact
✅ Demonstrates leadership, mentoring, influence
✅ Aligns your systems thinking with the company's product/mission
✅ Uses calm confidence, no hype
✅ 4-5 tight paragraphs (not overly long)

**Sonnet gets these inputs:**
- VOICE_GUIDE (tone, structure, what to avoid)
- Job posting content (requirements, company mission)
- Your background (10+ years, design systems, mentoring, AI focus)

### Resume Customization

Sonnet reorders your ATS resume to:
- Highlight experience most relevant to the job posting
- Front-load key achievements that match job requirements
- Integrate keywords from job description naturally
- Preserve quantified impact statements
- Maintain ATS optimization

---

## Current Status (Mar 5, 2026)

### ✅ Complete
- Voice guide capture (VOICE_GUIDE.md)
- Script structure (customize_application.py)
- Placeholder placeholders ready for Sonnet integration
- Output directory structure planned

### 🔄 In Progress
- **Sonnet API integration** — Will use Claude API to customize docs
- **DOCX generation** — python-docx library to create .docx files with customized content
- **Email integration** — OpenClaw message tool to send via ryanwinzenburg@gmail.com
- **Telegram listener** — Webhook to monitor Telegram messages and trigger script

### 📋 To Do (Next Steps)
1. Test Sonnet integration with real job posting
2. Implement DOCX file generation (preserve formatting from templates)
3. Set up email sender
4. Create Telegram listener/webhook

---

## Testing the Workflow

### Manual Test (Works Now)
```bash
python3 customize_application.py "TestCorp" "https://example.com/job/test"
```

Expected output:
- Progress messages showing fetch → customize → generate steps
- Files created in `customized_applications/TestCorp/`
- Email preview in console

### Full Integration Test (Once Telegram Listener is Ready)
1. Send Telegram message: `Anthropic - https://...`
2. Confirm receipt + processing started
3. Receive email with customized docs within 2-3 minutes
4. Review and submit

---

## Next Steps

**This week (Mar 5-7):**
1. ✅ Voice guide complete
2. ✅ Script structure ready
3. [ ] Integrate Claude Sonnet API
4. [ ] Test with 1-2 real job postings
5. [ ] Implement DOCX generation
6. [ ] Set up email sender

**Next week (Mar 10+):**
1. [ ] Telegram listener webhook
2. [ ] Full end-to-end test
3. [ ] Document customization examples
4. [ ] Deploy listener as background service

---

## Documentation References

- **Voice Guide:** `VOICE_GUIDE.md` — Tone, style, structure, examples
- **Job Scanner:** `job_search_scanner.py` — Finds opportunities
- **This Doc:** `CUSTOMIZATION_WORKFLOW.md` — How customization works
- **Config:** `CRON_JOB_CONFIG.md` — Cron job setup for scanner

---

*Last Updated: March 5, 2026 @ 8:35 AM MT*
*Status: Ready for Sonnet integration*
