# Sonnet Application Customization — Quick Start

## In 60 Seconds

### 1. Set Your API Key (Once)
```bash
export ANTHROPIC_API_KEY="sk-ant-..."  # Get from https://console.anthropic.com
echo $ANTHROPIC_API_KEY  # Verify it's set
```

### 2. Test the System
```bash
cd ~/.openclaw/workspace/job-search

python3 customize_application_sonnet.py "Anthropic" "https://boards.greenhouse.io/anthropic/jobs/..."
```

### 3. Check Your Output
Files appear in:
```
~/.openclaw/workspace/job-search/customized_applications/Anthropic/
  ├── Cover_Letter_Anthropic.txt
  └── Resume_Anthropic.txt
```

That's it! The customized documents are ready to review.

---

## What Gets Customized

### Cover Letter
✓ **Strategic opening** — Who you are as a leader  
✓ **Impact statements** — 1-2 specific initiatives with metrics  
✓ **Leadership** — Mentoring, cross-functional influence  
✓ **Company alignment** — How you fit their product/mission  
✓ **Your voice** — Principal-level tone from VOICE_GUIDE.md  
✓ **Length** — 4-5 tight paragraphs (not long-winded)  

### Resume
✓ **Reordered** — Most relevant experience first  
✓ **Keyword-matched** — Job requirements integrated naturally  
✓ **Impact-focused** — Quantified achievements highlighted  
✓ **Leadership** — Mentoring, systems thinking emphasized  
✓ **ATS-optimized** — Maintains scanning compatibility  

---

## Full Workflow (When Ready)

```
You send Telegram:
  "Anthropic - https://boards.greenhouse.io/..."
           ↓
System processes:
  1. Fetches job posting
  2. Loads your voice guide
  3. Generates customized cover letter (Sonnet)
  4. Customizes resume (Sonnet)
  5. Creates .docx files
  6. Emails to you
           ↓
You review + submit
```

---

## Files You Need

- **API Key:** `ANTHROPIC_API_KEY` environment variable
- **Voice Guide:** `VOICE_GUIDE.md` (already created)
- **Resume Base:** `templates/Resumes/Ryan_Winzenburg_Resume_ATS_Optimized.docx`
- **Script:** `customize_application_sonnet.py`

---

## Troubleshooting

**"ANTHROPIC_API_KEY not set"**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

**"anthropic module not found"**
```bash
pip3 install anthropic
```

**"Invalid API key"**
- Verify key is correct at https://console.anthropic.com
- Check you have available credits/quota

---

## Next: Full Integration

Once you confirm this works:
1. [ ] Test with a real job posting
2. [ ] Review customized documents
3. [ ] Make feedback (tone adjustments, etc.)
4. [ ] We'll set up Telegram listener
5. [ ] Full automation: send message → get email with docs

---

*Ready to test? Run:*
```bash
python3 customize_application_sonnet.py "TestCorp" "https://example.com/jobs/..."
```

*Questions? Check `SONNET_INTEGRATION.md` for full details.*
