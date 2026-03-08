# Personal CRM System - Complete Guide

Your Personal CRM is a relationship management system built entirely on local Markdown files with a web search interface.

## 📁 System Architecture

```
crm/
├── contacts/              # Individual contact files (.md)
│   ├── FirstName_LastName.md
│   ├── Dr_Samantha_Faye.md
│   └── ...
├── crm-search.html        # Web search interface
├── contacts-data.json     # Contact index (for search)
├── CONTACT_TEMPLATE.md    # Template for new contacts
└── CRM_GUIDE.md          # This file
```

## 🚀 Quick Start

### 1. Open the Web Interface

```bash
open ~/.openclaw/workspace/crm/crm-search.html
```

The interface will:
- Display all contacts as cards
- Allow full-text search by name, company, email
- Filter by tags
- Show statistics (total, hot/warm/cold relationships, need follow-up)
- Click any contact to view full details

### 2. Add Your First Contact

Copy the template and create a new file:

```bash
cp ~/.openclaw/workspace/crm/CONTACT_TEMPLATE.md \
   ~/.openclaw/workspace/crm/contacts/John_Doe.md
```

Then edit `John_Doe.md` with the contact information.

### 3. Update the Contact Index

After adding contacts manually, update the JSON index:

```bash
cd ~/.openclaw/workspace
node scripts/crm-index-contacts.mjs
```

This scans `crm/contacts/` and regenerates `contacts-data.json` for the search interface.

## 📊 Contact File Format

Every contact file has these sections:

### Basic Information
```markdown
| Field | Value |
|-------|-------|
| **Full Name** | ... |
| **Company** | ... |
| **Role** | ... |
| **Email** | ... |
| **Phone** | ... |
```

### Relationship Summary
- How you know each other
- Relationship strength (Type, Status, Strength, Last interaction, Frequency)
- Why the relationship matters

### Interaction Log
| Date | Type | Topics | Notes |
- Chronological record of every interaction
- Type: Meeting, Email, Phone, Event, etc.
- Topics: What was discussed
- Notes: Any relevant context

### Action Items
- Things I Owe Them (checklist)
- Things They Owe Me (checklist)

### Notes
- Key facts about the person
- Inside jokes or personal details
- Potential opportunities

### Context Tags
Tags for filtering and organization:
- `#kinlet` - Related to Kinlet product
- `#trading` - Related to swing trading
- `#job-search` - Related to job search
- `#investor` - Potential investor
- `#advisor` - Can provide strategic advice
- `#mentor` - Mentor relationship
- `#customer` - Customer or prospect
- `#warm-intro` - Can provide introductions

## 🔄 Workflow: Three Ways to Add/Update Contacts

### Method 1: Manual Entry (Anytime)

1. Copy template: `cp CONTACT_TEMPLATE.md contacts/FirstName_LastName.md`
2. Edit the file
3. Update index: `node scripts/crm-index-contacts.mjs`
4. View in web interface

### Method 2: From Google Calendar (Weekly)

Export your Google Calendar as CSV and import:

```bash
# Export from Google Calendar > Settings > Calendar > Export
# File will be named: calendar.csv

node scripts/crm-sync-calendar.mjs calendar.csv
```

This:
- Extracts all attendees from your meetings (last 90 days)
- Creates contact files for new attendees
- Updates the contact index

### Method 3: From Meeting Transcripts (After each meeting)

Upload transcripts from Fathom or Otter.ai:

```bash
node scripts/crm-parse-transcript.mjs path/to/transcript.json
```

This:
- Extracts attendee names and emails
- Finds matching contact files
- Adds a new row to each attendee's Interaction Log

## 🔍 Search & Query Interface

### Web Search

Open `crm-search.html` in your browser:
- **Search box:** Name, company, email (full-text search)
- **Filter chips:** Click tags to filter (e.g., `#kinlet`, `#warm-intro`)
- **Contact cards:** Hover to see interactions summary
- **Click card:** View full details

### Command-Line Query

Ask me natural language questions like:

```
"What did I last discuss with Dr. Samantha Faye?"
"Who should I follow up with this week?"
"Show me all warm relationships in the #kinlet tag"
"List people from Denver who work in Alzheimer's care"
```

I'll:
1. Search the contact files using `memory_search`
2. Parse the Interaction Log
3. Extract relevant information
4. Give you a natural language answer

## 📝 Automation & Integration

### Heartbeat Integration

Add to your `HEARTBEAT.md`:

```markdown
### CRM Follow-ups (Daily, 9:00 AM)
- Scan all contacts for Action Items due today
- Alert on overdue follow-ups (>7 days)
- Suggest 2-3 people to reach out to based on last interaction date
```

### Cron Job for Auto-Updates

Create a daily cron job:

```bash
# Every morning at 7 AM, scan calendar for new attendees
0 7 * * * cd ~/.openclaw/workspace && node scripts/crm-sync-calendar.mjs calendar.csv
```

### Memory Integration

I can search your CRM using `memory_search`:

```
User: "Who should I follow up with?"
Me: <searches CRM for interactions >30 days old>
    <returns list with context>
```

## 🎯 Use Cases

### 1. Before a Meeting
Ask: "Show me my history with John Doe"
- Last interactions
- Topics we discussed
- Action items
- Interests/background

### 2. Weekly Review
"Who needs follow-up this week?"
- Shows overdue action items
- People not contacted in >30 days
- High-priority relationships to maintain

### 3. Warm Introductions
"Who do I know in [industry/location]?"
- Filters by tags
- Shows relationship strength
- Suggests warm introduction opportunities

### 4. Proactive Outreach
"Who should I reach out to for [topic]?"
- Searches by tags and interaction history
- Identifies dormant relationships to reactivate

## 📊 Statistics Dashboard

The web interface shows:
- **Total Contacts:** Full count
- **Hot Relationships:** People you interact with frequently
- **Warm Relationships:** Active, growing relationships
- **Need Follow-up:** Contacts with overdue action items

## 🔐 Privacy & Security

All data is **local**. No cloud sync:
- Contact files stored in `crm/contacts/`
- Search index is a JSON file
- No external APIs or data transmission
- Completely private

## 🛠️ File Reference

### Core Files

| File | Purpose |
|------|---------|
| `crm-search.html` | Web interface for searching/browsing |
| `contacts-data.json` | Index for fast search |
| `CONTACT_TEMPLATE.md` | Template for new contacts |
| `contacts/` | Folder with all contact files |

### Scripts

| Script | Purpose |
|--------|---------|
| `crm-index-contacts.mjs` | Regenerate search index |
| `crm-sync-calendar.mjs` | Import from Google Calendar CSV |
| `crm-parse-transcript.mjs` | Parse meeting transcripts |

## 📖 Next Steps

1. **Create first contact:** `cp CONTACT_TEMPLATE.md contacts/Your_Contact.md`
2. **Open web interface:** `open crm-search.html`
3. **Update index:** `node scripts/crm-index-contacts.mjs`
4. **Test search:** Type a name in the search box
5. **Import calendar:** Export Google Calendar, run sync script
6. **Try natural language:** Ask me questions about your contacts

---

**Your CRM is now ready. Start adding contacts and building relationship intelligence.**
