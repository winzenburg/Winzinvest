# Personal CRM - Quick Start Guide

Your Personal CRM system is now ready to use. Here's how to get started in 5 minutes.

## 📋 What You Have

```
~/.openclaw/workspace/crm/
├── crm-search.html          ← Open this in your browser
├── CONTACT_TEMPLATE.md      ← Copy this to create new contacts
├── contacts/                ← Folder with all contact files
│   └── Sample_Contact.md   ← Example contact
└── CRM_GUIDE.md            ← Full documentation
```

## 🎯 3-Minute Setup

### 1. Open the Web Interface

```bash
open ~/.openclaw/workspace/crm/crm-search.html
```

You'll see:
- Search box (search by name, company, email)
- Filter chips (click to filter by tags)
- Contact cards (click for full details)
- Statistics (total contacts, hot/warm/cold relationships)

### 2. Add Your First Contact

```bash
# Copy template
cp ~/.openclaw/workspace/crm/CONTACT_TEMPLATE.md \
   ~/.openclaw/workspace/crm/contacts/John_Smith.md

# Edit the file
open ~/.openclaw/workspace/crm/contacts/John_Smith.md
```

Fill in:
- Name, company, role
- Email, phone
- How you know them
- Last interaction
- Action items
- Tags (#kinlet, #job-search, etc.)

### 3. Refresh the Search Index

```bash
cd ~/.openclaw/workspace
node scripts/crm-index-contacts.mjs
```

Reload your browser tab and you'll see your new contact!

## 🔄 Three Ways to Populate Your CRM

### Method 1: Manual Entry (Anytime)
1. Copy the template file
2. Edit and save
3. Run `node scripts/crm-index-contacts.mjs`

### Method 2: From Google Calendar (Weekly)
```bash
# Export your Google Calendar as CSV from Calendar Settings
# Then import:
node scripts/crm-sync-calendar.mjs ~/Downloads/calendar.csv
```

This creates contact files for all meeting attendees.

### Method 3: From Meeting Transcripts (After meetings)
```bash
# Upload transcript from Fathom or Otter.ai
node scripts/crm-parse-transcript.mjs ~/Downloads/meeting-transcript.json
```

This updates contact Interaction Logs with meeting details.

## 🔍 Search & Query

### In the Web Interface
- **Search:** Type name, company, or email
- **Filter:** Click tags to show only certain contacts
- **Browse:** Click any card to see full details

### Ask Me Naturally
```
"Show me all warm relationships"
"Who should I follow up with this week?"
"What did I last discuss with John Smith?"
"List all contacts with the #kinlet tag"
"Show me people in Denver working in healthcare"
```

I'll search your CRM and give you a natural language answer.

## 📝 Contact File Structure

Every contact has:
- **Basic Info:** Name, company, role, email, phone
- **Relationship Summary:** How you know them, strength (Hot/Warm/Cold)
- **Interaction Log:** Dates and topics of all meetings/calls/emails
- **Action Items:** Things you owe them or they owe you
- **Notes:** Key facts, interests, opportunities
- **Tags:** For filtering (#kinlet, #investor, #mentor, etc.)

## ⚡ Pro Tips

1. **Add tags consistently** - Use the same tags across contacts for easy filtering
2. **Update Interaction Log** - Add entries after every meeting or significant email
3. **Set Action Items** - Don't forget to follow up
4. **Regular Review** - Check the CRM weekly for people to reach out to
5. **Use for warm intros** - Search by location/industry to find intro opportunities

## 📊 Relationship Strength

Mark contacts as:
- **Hot:** People you interact with frequently, active relationships
- **Warm:** Growing relationships, regular contact
- **Cold:** New contacts, haven't connected much yet

## 🏷️ Suggested Tags

Create your own, or use these:
- `#kinlet` - Related to Kinlet product
- `#trading` - Related to swing trading  
- `#job-search` - Related to job search
- `#investor` - Potential investor
- `#advisor` - Can provide strategic advice
- `#mentor` - Mentor relationship
- `#customer` - Customer or prospect
- `#warm-intro` - Can provide introductions
- `#denver` - Based in Denver
- `#healthcare` - Healthcare industry

## 📂 File Locations

```bash
# Web interface
open ~/.openclaw/workspace/crm/crm-search.html

# Contact template
cat ~/.openclaw/workspace/crm/CONTACT_TEMPLATE.md

# Your contacts
ls ~/.openclaw/workspace/crm/contacts/

# Full documentation
cat ~/.openclaw/workspace/crm/CRM_GUIDE.md

# Scripts
ls ~/.openclaw/workspace/scripts/crm-*.mjs
```

## 🎯 Next Steps

1. Open the web interface → `open crm-search.html`
2. Create 2-3 contacts manually
3. Run the indexer → `node scripts/crm-index-contacts.mjs`
4. Test the search
5. Export your Google Calendar and import it
6. Start asking me questions about your relationships!

---

**You're ready to build relationship intelligence. Start adding contacts!**
