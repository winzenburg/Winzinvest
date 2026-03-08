# Meeting Action Item Pipeline - 5-Minute Quick Start

Your Meeting Action Item Pipeline is ready. Here's how to use it today.

## 🎯 What This Does

1. **Parse meeting transcripts** (Granola, Fathom, text)
2. **Extract action items** automatically
3. **Send to Telegram** for approval
4. **Create tasks** in Todoist or Things 3
5. **Update CRM** contacts with action items

## ⚡ The 3-Step Flow (Right Now)

### Step 1: Parse a Transcript

```bash
# Create a sample meeting transcript
cat > /tmp/meeting.txt << 'EOF'
Meeting with Dr. Samantha Faye - Feb 22, 2026

Discussion:
- Reviewed Kinlet MVP
- Discussed sundowning pain point
- Talked about research partnership

Action Items:
- I need to send MVP access to Dr. Faye by Feb 28
- Schedule Q&A call with Dr. Faye by Mar 1
- Dr. Faye will send research findings by Mar 15
EOF

# Parse the transcript
cd ~/.openclaw/workspace
node scripts/parse-meeting-transcript.mjs /tmp/meeting.txt
```

**What happens:**
- Extracts 3 action items
- Sends to your Telegram
- Saves to: `temp/extracted-actions.json`

### Step 2: Approve via Telegram

You'll get a Telegram message:

```
📋 New Action Items from Meeting

Meeting: Meeting with Dr. Samantha Faye
Time: Feb 22, 2026

1. 🔴 Send MVP access to Dr. Faye → me (due: Feb 28)
2. 🟡 Schedule Q&A call with Dr. Faye → me (due: Mar 1)
3. 🟡 Send research findings → Dr. Faye (due: Mar 15)

Reply with numbers you want to add (e.g., "1, 3, 5") or "all"
```

**Reply in Telegram:** `1, 2` (or `all`)

### Step 3: Create Tasks

```bash
# Create the approved tasks (using Todoist by default)
node scripts/create-approved-tasks.mjs "1, 2"

# Or use Things 3 if you prefer
node scripts/create-approved-tasks.mjs "1, 2" --things3
```

**What happens:**
- Tasks created in your task manager
- CRM contact "Dr. Samantha Faye" updated with:
  - New Interaction Log entry
  - New Action Items
- Confirmation sent to Telegram

---

## 🎛️ Real-World Usage

### After a Real Meeting

1. **Export transcript from Granola:**
   - Open Granola app
   - View meeting transcript
   - Share → "Copy" (or export as JSON)

2. **Parse it:**
   ```bash
   node scripts/parse-meeting-transcript.mjs ~/Downloads/granola-export.json
   ```

3. **Approve in Telegram:** Reply with item numbers

4. **Done!** Tasks created + CRM updated

---

## 🔧 Setup (5 minutes)

### For Todoist (Recommended)

1. Get your API token:
   - Go to https://todoist.com/prefs/integrations
   - Copy "API Token"

2. Set environment variable:
   ```bash
   export TODOIST_API_TOKEN="paste_your_token_here"
   
   # Make it permanent:
   echo 'export TODOIST_API_TOKEN="paste_your_token_here"' >> ~/.zshrc
   source ~/.zshrc
   ```

3. Test it:
   ```bash
   node scripts/create-approved-tasks.mjs "1"
   ```

### For Things 3 (macOS only)

No setup needed! Just use:
```bash
node scripts/create-approved-tasks.mjs "1" --things3
```

---

## 📋 Script Reference

### Parse Transcript

```bash
node scripts/parse-meeting-transcript.mjs <file>

# Accepts:
# - Granola JSON export
# - Fathom JSON export
# - Plain text file
```

Automatically sends Telegram message with extracted items.

---

### Create Approved Tasks

```bash
# Default: Todoist
node scripts/create-approved-tasks.mjs "1, 2, 3"

# All items
node scripts/create-approved-tasks.mjs "all"

# Things 3 instead
node scripts/create-approved-tasks.mjs "1, 2" --things3
```

---

### Update CRM Contacts

```bash
node scripts/update-crm-from-actions.mjs
```

This runs automatically after task creation, but can also run manually.

---

## 🎯 Real Examples

### Example 1: Simple Meeting

```bash
# Parse transcript
node scripts/parse-meeting-transcript.mjs meeting.json

# Telegram shows: 1. Task A  2. Task B  3. Task C

# You reply: 1, 3

# Create those tasks
node scripts/create-approved-tasks.mjs "1, 3"

# Done!
```

---

### Example 2: With CRM Contact

```bash
# Meeting with "John Smith"
node scripts/parse-meeting-transcript.mjs john-meeting.json

# Telegram shows:
# 1. 🔴 Call John back → me (due: tomorrow)
# 2. 🟡 John will send proposal → John Smith (due: Friday)

# You reply: all

# Create all tasks
node scripts/create-approved-tasks.mjs "all"

# Contact file crm/contacts/John_Smith.md is updated with:
# - New Interaction Log entry
# - "Things I Owe Them" and "Things They Owe Me" sections updated
```

---

## 🤖 Advanced: Telegram Approval Loop

The system is listening for your Telegram replies. When you reply with your approval:

1. Bot captures your message
2. Extracts numbers from your reply
3. Automatically runs task creation
4. Updates CRM
5. Sends confirmation to Telegram

**This requires:** Telegram webhook integration (optional, but makes it seamless)

---

## 📊 What Gets Extracted

From any transcript, the parser finds:

| Element | Example | Detection |
|---------|---------|-----------|
| **Task** | "Send MVP access" | "I need to", "will", "action item" |
| **Assignee** | "me" or "John Smith" | Pronoun + verb pattern |
| **Priority** | High/Medium/Low | Keywords: "urgent", "should", "asap" |
| **Due Date** | "Feb 28" or "Friday" | Date patterns, relative dates |
| **Contact** | "Dr. Samantha Faye" | Names mentioned near action items |

---

## ✅ Checklist: Get Started Today

- [ ] Run sample transcript test
- [ ] Set Todoist API token (or decide on Things 3)
- [ ] Parse a real meeting transcript
- [ ] Approve in Telegram
- [ ] Check task in your task manager
- [ ] Check updated CRM contact

---

## 🚀 Next Steps (Optional)

1. **Webhook automation:** Set up Granola → Zapier → Webhook (see MEETING_PIPELINE_SETUP.md)
2. **Telegram approval bot:** Auto-trigger task creation from Telegram reply
3. **Fathom direct integration:** Native webhook from Fathom
4. **Batch processing:** Run multiple transcripts at once

---

## 📞 Troubleshooting

**"No action items found"**
- Add explicit markers: "ACTION:", "TODO:", "[name] will", "by [date]"
- Or phrase it naturally: "I need to call John"

**"Task not created"**
- Check Todoist token: `echo $TODOIST_API_TOKEN`
- Or use Things 3: Add `--things3` flag

**"CRM not updated"**
- Contact file must exist: `crm/contacts/FirstName_LastName.md`
- Name in transcript must match contact file exactly

---

**Ready? Start here:** `node scripts/parse-meeting-transcript.mjs <file>`
