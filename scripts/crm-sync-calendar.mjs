#!/usr/bin/env node

/**
 * CRM Calendar Sync
 * 
 * Syncs Google Calendar events from the last 90 days
 * Extracts attendee information and creates/updates contact files
 * 
 * Usage:
 *   node scripts/crm-sync-calendar.mjs [--dry-run]
 * 
 * Required setup:
 * 1. Install Google Calendar API: npm install googleapis
 * 2. Create OAuth 2.0 credentials: https://console.cloud.google.com
 * 3. Save credentials to: ~/.openclaw/crm/google-credentials.json
 * 4. Run once to authenticate and create token
 * 
 * For now: Manual mode or use --import to upload calendar CSV
 */

import fs from 'fs';
import path from 'path';

const CRM_PATH = './crm/contacts';
const DATA_FILE = './crm/contacts-data.json';
const LOG_FILE = './logs/crm-sync.log';

function log(message) {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] ${message}`);
  if (!fs.existsSync('./logs')) fs.mkdirSync('./logs', { recursive: true });
  fs.appendFileSync(LOG_FILE, `[${timestamp}] ${message}\n`);
}

function formatFileName(firstName, lastName) {
  return `${firstName}_${lastName}.md`;
}

function createContactFile(contact, dryRun = false) {
  const filename = formatFileName(contact.firstName, contact.lastName);
  const filepath = path.join(CRM_PATH, filename);

  const content = `# ${contact.firstName} ${contact.lastName}

## Basic Information

| Field | Value |
|-------|-------|
| **Full Name** | ${contact.firstName} ${contact.lastName} |
| **Company** | ${contact.company || 'Not specified'} |
| **Role** | ${contact.role || 'Not specified'} |
| **Email** | ${contact.email || 'Not specified'} |
| **Phone** | ${contact.phone || 'Not specified'} |
| **LinkedIn** | ${contact.linkedin || 'Not specified'} |
| **Location** | ${contact.location || 'Not specified'} |

---

## Relationship Summary

**How we know each other:**
[Add context]

**Relationship strength:**
- **Type:** Professional
- **Status:** New
- **Strength:** Cold
- **Last meaningful interaction:** [Date]
- **Frequency:** As needed

**Why this relationship matters:**
[Add rationale]

---

## Interaction Log

| Date | Type | Topics | Notes |
|------|------|--------|-------|
| ${new Date().toISOString().split('T')[0]} | Meeting | ${contact.meetingTopic || 'N/A'} | Imported from calendar |

---

## Action Items

### Things I Owe Them
- [ ] Follow up by [date]

### Things They Owe Me
- [ ] [Task] by [date]

---

## Notes

### Key Facts
- [Add key facts]

### Potential Opportunities
- [Opportunities]

---

## Context Tags

Tags: #new-contact

---

## CRM Metadata

- **Created:** ${new Date().toISOString().split('T')[0]}
- **Last Updated:** ${new Date().toISOString().split('T')[0]}
- **Update Frequency:** As needed
- **Source:** Google Calendar
`;

  if (!dryRun) {
    fs.writeFileSync(filepath, content);
    log(`✓ Created contact: ${filename}`);
  } else {
    log(`[DRY-RUN] Would create: ${filename}`);
  }

  return {
    filename,
    name: `${contact.firstName} ${contact.lastName}`,
    company: contact.company || 'Unknown',
    role: contact.role || 'Unknown',
    email: contact.email,
    phone: contact.phone,
    strength: 'Cold',
    status: 'New',
    lastInteraction: new Date().toISOString().split('T')[0],
    needsFollowUp: true,
    tags: ['#new-contact']
  };
}

function updateContactsData(newContacts, dryRun = false) {
  let data = [];
  if (fs.existsSync(DATA_FILE)) {
    data = JSON.parse(fs.readFileSync(DATA_FILE, 'utf-8'));
  }

  // Merge with existing
  newContacts.forEach(newContact => {
    const existing = data.find(c => c.filename === newContact.filename);
    if (!existing) {
      data.push(newContact);
    }
  });

  if (!dryRun) {
    fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2));
    log(`✓ Updated contacts-data.json (${data.length} total contacts)`);
  } else {
    log(`[DRY-RUN] Would update contacts-data.json with ${newContacts.length} new contacts`);
  }

  return data;
}

function parseCalendarCSV(csvContent) {
  // Parse CSV from Google Calendar export
  // Expected format: Event Title, Start Date, Start Time, End Time, Attendees, Description
  
  const lines = csvContent.split('\n');
  const contacts = [];

  lines.slice(1).forEach(line => {
    if (!line.trim()) return;
    
    const parts = line.split(',').map(p => p.trim().replace(/^"|"$/g, ''));
    if (parts.length < 5) return;

    const [title, startDate, startTime, endTime, attendees, description] = parts;
    
    // Parse attendee emails
    if (attendees) {
      attendees.split(';').forEach(attendee => {
        const emailMatch = attendee.match(/([^<]+)<(.+?)>/);
        if (emailMatch) {
          const [, name, email] = emailMatch;
          const [firstName, ...lastNameParts] = name.trim().split(' ');
          const lastName = lastNameParts.join(' ') || 'Contact';

          contacts.push({
            firstName,
            lastName,
            email: email.trim(),
            company: 'Unknown',
            meetingTopic: title
          });
        }
      });
    }
  });

  return contacts;
}

async function main() {
  const args = process.argv.slice(2);
  const dryRun = args.includes('--dry-run');

  if (dryRun) {
    log('Running in DRY-RUN mode (no changes will be made)');
  }

  log('===== CRM Calendar Sync Start =====');

  // Check for CSV import
  const csvPath = args.find(arg => arg.endsWith('.csv'));
  
  if (csvPath && fs.existsSync(csvPath)) {
    log(`Importing from CSV: ${csvPath}`);
    const csvContent = fs.readFileSync(csvPath, 'utf-8');
    const contacts = parseCalendarCSV(csvContent);
    
    log(`Found ${contacts.length} attendees from calendar`);

    const newContacts = [];
    contacts.forEach(contact => {
      const contactData = createContactFile(contact, dryRun);
      newContacts.push(contactData);
    });

    updateContactsData(newContacts, dryRun);
    log('✓ Calendar sync complete');
  } else {
    log('Next steps:');
    log('1. Export your Google Calendar as CSV');
    log('2. Run: node scripts/crm-sync-calendar.mjs path/to/calendar.csv');
    log('Or set up OAuth for automatic sync (see script comments)');
  }

  log('===== CRM Calendar Sync Complete =====');
}

main().catch(error => {
  log(`✗ Error: ${error.message}`);
  process.exit(1);
});
