#!/usr/bin/env node

/**
 * CRM Contact Indexer
 * 
 * Scans crm/contacts/ folder and generates contacts-data.json
 * Called after manually adding/editing contact files
 * 
 * Usage:
 *   node scripts/crm-index-contacts.mjs
 */

import fs from 'fs';
import path from 'path';

const CRM_PATH = './crm';
const CONTACTS_PATH = './crm/contacts';
const DATA_FILE = './crm/contacts-data.json';
const LOG_FILE = './logs/crm-sync.log';

function log(message) {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] ${message}`);
  if (!fs.existsSync('./logs')) fs.mkdirSync('./logs', { recursive: true });
  fs.appendFileSync(LOG_FILE, `[${timestamp}] ${message}\n`);
}

function extractMetadata(content, filename) {
  const metadata = {
    filename,
    name: 'Unknown',
    company: 'Unknown',
    role: 'Unknown',
    email: null,
    phone: null,
    strength: 'Cold',
    status: 'New',
    lastInteraction: null,
    needsFollowUp: false,
    tags: []
  };

  // Extract from h1
  const nameMatch = content.match(/^# (.+?)$/m);
  if (nameMatch) {
    metadata.name = nameMatch[1];
  }

  // Extract from Basic Information table
  const basicMatch = content.match(/## Basic Information\n\n([\s\S]*?)(?=\n---|\n## )/);
  if (basicMatch) {
    const table = basicMatch[1];
    
    const companyMatch = table.match(/\| \*\*Company\*\* \| (.+?) \|/);
    if (companyMatch) metadata.company = companyMatch[1];

    const roleMatch = table.match(/\| \*\*Role\*\* \| (.+?) \|/);
    if (roleMatch) metadata.role = roleMatch[1];

    const emailMatch = table.match(/\| \*\*Email\*\* \| (.+?) \|/);
    if (emailMatch) metadata.email = emailMatch[1];

    const phoneMatch = table.match(/\| \*\*Phone\*\* \| (.+?) \|/);
    if (phoneMatch) metadata.phone = phoneMatch[1];
  }

  // Extract from Relationship Summary
  const relMatch = content.match(/## Relationship Summary\n\n([\s\S]*?)(?=\n---|\n## )/);
  if (relMatch) {
    const section = relMatch[1];
    
    const strengthMatch = section.match(/\*\*Strength:\*\*.*?\n- \*\*Strength:\*\* \[(.+?)\]/);
    if (strengthMatch) {
      const strength = strengthMatch[1].trim();
      if (['Hot', 'Warm', 'Cold'].includes(strength)) {
        metadata.strength = strength;
      }
    }

    const statusMatch = section.match(/\*\*Status:\*\* \[(.+?)\]/);
    if (statusMatch) {
      metadata.status = statusMatch[1].trim();
    }

    const lastMatch = section.match(/\*\*Last meaningful interaction:\*\* \[(.+?)\]/);
    if (lastMatch) {
      metadata.lastInteraction = lastMatch[1].trim();
    }
  }

  // Extract from Interaction Log
  const logMatch = content.match(/## Interaction Log\n\n\| Date \| Type \| Topics \| Notes \|\n\|.*?\n([\s\S]*?)(?=\n---|\n## )/);
  if (logMatch) {
    const rows = logMatch[1].split('\n').filter(r => r.trim() && r.includes('|'));
    if (rows.length > 0) {
      const lastRow = rows[rows.length - 1];
      const parts = lastRow.split('|').map(p => p.trim());
      if (parts.length >= 2) {
        metadata.lastInteraction = parts[1];
      }
    }
  }

  // Extract Action Items to check if follow-up needed
  if (content.includes('- [ ]')) {
    metadata.needsFollowUp = true;
  }

  // Extract tags
  const tagsMatch = content.match(/Tags:\s*(.+?)(?=\n---|\Z)/);
  if (tagsMatch) {
    const tagString = tagsMatch[1];
    metadata.tags = (tagString.match(/#\w+/g) || []).map(t => t.substring(1)); // Remove #
  }

  return metadata;
}

async function main() {
  if (!fs.existsSync(CONTACTS_PATH)) {
    log(`❌ Contacts folder not found: ${CONTACTS_PATH}`);
    process.exit(1);
  }

  log('===== CRM Contact Indexer Start =====');

  // Read all .md files from contacts/
  const files = fs.readdirSync(CONTACTS_PATH)
    .filter(f => f.endsWith('.md'))
    .sort();

  log(`Found ${files.length} contact files`);

  const contactsData = [];

  files.forEach(filename => {
    const filepath = path.join(CONTACTS_PATH, filename);
    const content = fs.readFileSync(filepath, 'utf-8');
    const metadata = extractMetadata(content, filename);
    
    contactsData.push({
      filename: metadata.filename,
      name: metadata.name,
      company: metadata.company,
      role: metadata.role,
      email: metadata.email,
      phone: metadata.phone,
      strength: metadata.strength,
      status: metadata.status,
      lastInteraction: metadata.lastInteraction,
      needsFollowUp: metadata.needsFollowUp,
      tags: metadata.tags.map(t => `#${t}`) // Add # back for display
    });

    log(`✓ Indexed: ${metadata.name}`);
  });

  // Write contacts-data.json
  fs.writeFileSync(DATA_FILE, JSON.stringify(contactsData, null, 2));
  log(`✓ Generated ${DATA_FILE} (${contactsData.length} contacts)`);

  // Print statistics
  const hotCount = contactsData.filter(c => c.strength === 'Hot').length;
  const warmCount = contactsData.filter(c => c.strength === 'Warm').length;
  const coldCount = contactsData.filter(c => c.strength === 'Cold').length;
  const followUpCount = contactsData.filter(c => c.needsFollowUp).length;

  log(`\n📊 Statistics:`);
  log(`  Total contacts: ${contactsData.length}`);
  log(`  Hot: ${hotCount}, Warm: ${warmCount}, Cold: ${coldCount}`);
  log(`  Need follow-up: ${followUpCount}`);

  log('===== CRM Contact Indexer Complete =====');
}

main().catch(error => {
  log(`✗ Error: ${error.message}`);
  process.exit(1);
});
