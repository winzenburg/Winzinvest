#!/usr/bin/env node

/**
 * CRM Transcript Parser
 * 
 * Parses meeting transcripts (from Fathom, Otter.ai, or similar)
 * Extracts attendee names, email addresses, and key topics
 * Updates relevant contact files with interaction log
 * 
 * Usage:
 *   node scripts/crm-parse-transcript.mjs path/to/transcript.txt
 *   node scripts/crm-parse-transcript.mjs path/to/transcript.json
 * 
 * Supports:
 * - Fathom JSON export
 * - Otter.ai JSON export
 * - Plain text with "Attendees: Name <email>" format
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

function findContactFile(firstName, lastName) {
  const filename = formatFileName(firstName, lastName);
  const filepath = path.join(CRM_PATH, filename);
  return fs.existsSync(filepath) ? filepath : null;
}

function updateContactWithInteraction(filepath, interaction) {
  let content = fs.readFileSync(filepath, 'utf-8');

  // Find Interaction Log section
  const logRegex = /## Interaction Log\n\n\| Date \| Type \| Topics \| Notes \|\n\|.*?\n([\s\S]*?)(?=\n---|\Z)/;
  const match = content.match(logRegex);

  if (match) {
    // Insert new row at beginning of table
    const newRow = `| ${interaction.date} | ${interaction.type} | ${interaction.topics} | ${interaction.notes} |\n`;
    const tableContent = match[1];
    const updatedTable = newRow + tableContent;
    content = content.replace(logRegex, `## Interaction Log\n\n| Date | Type | Topics | Notes |\n|------|------|--------|-------|\n${updatedTable}---`);
  }

  fs.writeFileSync(filepath, content);
  log(`✓ Updated contact: ${path.basename(filepath)}`);
}

function parseTranscript(content, filename) {
  let transcript = {};

  // Try to parse as JSON first (Fathom or Otter export)
  try {
    transcript = JSON.parse(content);
    log('Detected JSON format (likely Fathom or Otter.ai export)');
  } catch (e) {
    // Parse as plain text
    log('Parsing as plain text format');
    
    // Extract attendees from various formats
    const attendeeMatch = content.match(/Attendees?:?\s*(.+?)(?=\n|$)/i);
    if (attendeeMatch) {
      transcript.attendees = attendeeMatch[1]
        .split(/[,;]/)
        .map(a => a.trim())
        .filter(a => a);
    }

    // Extract topics/description
    transcript.title = filename.replace(/\.[^/.]+$/, '');
    transcript.summary = content.substring(0, 500);
  }

  return transcript;
}

function extractAttendees(transcript) {
  const attendees = [];

  // Handle different transcript formats
  if (Array.isArray(transcript.attendees)) {
    transcript.attendees.forEach(attendee => {
      const match = attendee.match(/(.+?)\s*<(.+?)>/);
      if (match) {
        const [, name, email] = match;
        const [firstName, ...lastNameParts] = name.trim().split(' ');
        attendees.push({
          firstName,
          lastName: lastNameParts.join(' ') || 'Contact',
          email: email.trim()
        });
      } else if (attendee.includes('@')) {
        const [localPart] = attendee.split('@');
        const [firstName, ...lastNameParts] = localPart.split('.');
        attendees.push({
          firstName: firstName || 'Unknown',
          lastName: lastNameParts.join('_') || 'Contact',
          email: attendee
        });
      }
    });
  } else if (typeof transcript.attendees === 'string') {
    const parts = transcript.attendees.split(/[,;]/);
    parts.forEach(attendee => {
      const match = attendee.trim().match(/(.+?)\s*<(.+?)>/);
      if (match) {
        const [, name, email] = match;
        const [firstName, ...lastNameParts] = name.trim().split(' ');
        attendees.push({
          firstName,
          lastName: lastNameParts.join(' ') || 'Contact',
          email: email.trim()
        });
      }
    });
  }

  return attendees;
}

function main() {
  const transcriptPath = process.argv[2];

  if (!transcriptPath) {
    console.error('Usage: node crm-parse-transcript.mjs <path-to-transcript>');
    process.exit(1);
  }

  if (!fs.existsSync(transcriptPath)) {
    console.error(`File not found: ${transcriptPath}`);
    process.exit(1);
  }

  log('===== CRM Transcript Parser Start =====');
  log(`Processing: ${transcriptPath}`);

  const content = fs.readFileSync(transcriptPath, 'utf-8');
  const transcript = parseTranscript(content, path.basename(transcriptPath));

  if (!transcript.attendees || transcript.attendees.length === 0) {
    log('⚠ No attendees found in transcript');
    log('Expected format: Attendees: FirstName LastName <email@example.com>');
    process.exit(0);
  }

  const attendees = extractAttendees(transcript);
  log(`Found ${attendees.length} attendees`);

  // Extract topics/key discussion points
  const topics = transcript.title || transcript.summary || 'Meeting discussion';

  // Update each attendee's contact file
  attendees.forEach(attendee => {
    const contactPath = findContactFile(attendee.firstName, attendee.lastName);
    
    if (contactPath) {
      const interaction = {
        date: new Date().toISOString().split('T')[0],
        type: 'Meeting',
        topics: topics.substring(0, 50),
        notes: `Transcript: ${path.basename(transcriptPath)}`
      };
      updateContactWithInteraction(contactPath, interaction);
    } else {
      log(`⚠ Contact file not found: ${attendee.firstName} ${attendee.lastName} (${attendee.email})`);
    }
  });

  log('===== CRM Transcript Parser Complete =====');
}

main();
