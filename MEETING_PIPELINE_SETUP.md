# Meeting Action Item Pipeline - Setup Guide

Complete setup for extracting action items from meeting transcripts, approving them, and creating tasks.

## 🎯 Overview

**Flow:**
1. Send meeting transcript (Granola, Fathom, or text) → Pipeline parses it
2. Extract action items automatically
3. Send to Telegram for approval
4. Reply with approved items
5. Create tasks in Todoist or Things 3
6. Update CRM contacts with action items

## 🚀 Quick Start

### Step 1: Test with Sample Transcript

```bash
# Create a sample transcript
cat > /tmp/sample-meeting.txt << 'EOF'
Meeting with Dr. Samantha Faye - 2026-02-22

ACTION ITEMS:
1. I need to send MVP access to Dr. Faye by 2026-02-28
2. Schedule Q&A call with Dr. Faye by 2026-03-01
3. Dr. Faye will send research findings by 2026-03-15

Notes:
- Discussed Kinlet validation
- Sundowning is top pain point
- She's interested in research partnership
EOF

# Parse the transcript
node scripts/parse-meeting-transcript.mjs /tmp/sample-meeting.txt
```

You'll get a Telegram message with extracted action items.

### Step 2: Configure Task Manager

#### Option A: Todoist (Recommended)

1. Get your Todoist API token:
   - Go to https://todoist.com/prefs/integrations
   - Copy your token
2. Set environment variable:
   ```bash
   export TODOIST_API_TOKEN="your_token_here"
   echo 'export TODOIST_API_TOKEN="your_token_here"' >> ~/.zshrc
   ```
3. Test connection:
   ```bash
   node scripts/create-approved-tasks.mjs "1"
   ```

#### Option B: Things 3 (macOS Only)

1. Things 3 is already available via AppleScript
2. No setup needed
3. Create tasks using:
   ```bash
   node scripts/create-approved-tasks.mjs "1" --things3
   ```

### Step 3: Approve Tasks via Telegram

After parsing a transcript, you'll get a Telegram message like:

```
📋 New Action Items from Meeting

Meeting: Dr. Samantha Faye
Time: Feb 22, 2026

Extracted Action Items:

1. 🔴 Send MVP access to Dr. Faye → me (due: 2026-02-28)
2. 🟡 Schedule Q&A call with Dr. Faye → me (due: 2026-03-01)
3. 🟡 Send research findings → Dr. Faye (due: 2026-03-15)

Reply with numbers you want to add (e.g., "1, 3, 5") or "all"
```

Reply with: `1, 2` (or `all`)

### Step 4: Confirm Task Creation

The pipeline will:
1. Create tasks in your task manager
2. Update CRM contact files with action items
3. Send confirmation to Telegram

## 📚 Script Reference

### Parse Transcript
```bash
node scripts/parse-meeting-transcript.mjs <file>

# Supports:
# - Granola JSON export
# - Fathom JSON export
# - Plain text transcripts
```

**Output:** Telegram message with extracted items

---

### Create Approved Tasks
```bash
# Using Todoist (default)
node scripts/create-approved-tasks.mjs "1, 2, 3"
node scripts/create-approved-tasks.mjs "all"

# Using Things 3
node scripts/create-approved-tasks.mjs "1, 2" --things3
```

**Output:** Tasks created in task manager

---

### Update CRM
```bash
node scripts/update-crm-from-actions.mjs

# Reads from: temp/extracted-actions.json
# Updates: crm/contacts/*.md
```

**Output:** Contact files updated with action items

---

## 🔌 Webhook Setup (Granola + Fathom)

### Granola Integration

Granola supports exporting to Zapier. To auto-trigger the pipeline:

1. **Export Granola transcript to Zapier:**
   - Open Granola → Meeting
   - Click "Share" → "Zapier"
   - Create new Zap

2. **Zap Configuration:**
   - **Trigger:** Granola - New meeting completed
   - **Action:** Webhook - POST to:
     ```
     http://your-domain.com/webhook/meeting-transcript
     ```
   - **Payload:**
     ```json
     {
       "transcript": "{{ transcript }}",
       "title": "{{ meeting_title }}",
       "attendees": "{{ attendees }}",
       "timestamp": "{{ created_at }}"
     }
     ```

3. **Note:** Zapier requires a public URL. For local testing, use ngrok:
   ```bash
   ngrok http 3000  # Forward your webhook server to public URL
   ```

### Fathom Integration

Fathom supports webhooks directly. To set up:

1. **Fathom Settings:**
   - Go to Fathom Dashboard → Integrations → Webhooks
   - Add webhook URL
   - Event: "Meeting transcribed"

2. **Webhook URL:**
   ```
   http://your-domain.com/webhook/fathom-transcript
   ```

3. **Payload format:** Fathom sends JSON with:
   - `transcript_text`
   - `transcript_json`
   - `meeting_title`
   - `meeting_date`
   - `attendees`

---

## 📋 Workflow Examples

### Example 1: Ad-Hoc Meeting Notes

```bash
# After a meeting, send notes via Telegram
# Send screenshot or copy transcript

# OR use local file:
node scripts/parse-meeting-transcript.mjs ~/Downloads/meeting.json

# Telegram message arrives → Reply "1, 2, 3"

node scripts/create-approved-tasks.mjs "1, 2, 3"

# Done! Tasks created + CRM updated
```

### Example 2: Automatic Granola Integration

1. Granola completes meeting
2. Granola → Zapier → Your webhook
3. Webhook triggers `parse-meeting-transcript.mjs`
4. Your Telegram gets approval message
5. You reply with approval
6. Webhook triggered again with your selection
7. Tasks auto-created + CRM updated

---

## 🔐 Environment Variables

Set these for full automation:

```bash
# Todoist API
export TODOIST_API_TOKEN="your_api_token"

# Telegram (already set, but for reference)
export TELEGRAM_BOT_TOKEN="8565359157:AAE3cA0Tn2OE62K2eaXiXYr1SFqAFkNtzMQ"
export TELEGRAM_CHAT_ID="5316436116"

# Optional: Granola API if available
export GRANOLA_API_KEY="your_key"
```

Add to `~/.zshrc`:
```bash
echo 'export TODOIST_API_TOKEN="..."' >> ~/.zshrc
source ~/.zshrc
```

---

## 🛠️ Troubleshooting

### "No action items found"
- Transcript may not have clear action item language
- Try using keywords: "action item", "TODO", "need to", "will", "by [date]"
- Add explicit markers in transcript: "ACTION: ..."

### "Task creation failed"
- **Todoist:** Check API token is correct
  ```bash
  curl -H "Authorization: Bearer YOUR_TOKEN" https://api.todoist.com/rest/v2/tasks
  ```
- **Things 3:** Ensure app is installed and AppleScript enabled

### "CRM contact not found"
- Contact file must exist in `crm/contacts/`
- Name must match exactly (FirstName_LastName.md)
- Create contact first, then update manually if needed

---

## 📊 Pipeline Status

| Component | Status | Notes |
|-----------|--------|-------|
| Transcript Parser | ✅ Ready | Extracts action items |
| Telegram Approval | ✅ Ready | Sends message + awaits reply |
| Todoist Integration | ✅ Ready | Requires API token |
| Things 3 Integration | ✅ Ready | macOS only, AppleScript |
| CRM Update | ✅ Ready | Updates contact files |
| Granola Webhook | 🟡 Partial | Requires Zapier setup |
| Fathom Webhook | 🟡 Partial | Requires endpoint implementation |

---

## 📝 Manual Workflow (Simplest Start)

1. **After meeting:** Export transcript as JSON/TXT
2. **Run:** `node scripts/parse-meeting-transcript.mjs file.json`
3. **Get Telegram message** with extracted items
4. **Reply:** "1, 2, 3"
5. **Tasks created** + CRM updated

No webhooks needed. Works today.

---

## 🎯 Next Steps

1. **Test locally:** Run sample transcript through pipeline
2. **Set Todoist token:** Configure your task manager
3. **Reply to Telegram:** Approve items and create tasks
4. **Check CRM:** See updated contact files
5. **Optional:** Set up webhooks for automation

**Ready to go? Start with:** `node scripts/parse-meeting-transcript.mjs <file>`
