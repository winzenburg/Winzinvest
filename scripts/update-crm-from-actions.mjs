#!/usr/bin/env node

/**
 * CRM Updater - Action Item Integration
 * 
 * Updates contact files with action items from meetings
 * Adds to Interaction Log and Action Items section
 * 
 * Usage:
 *   node scripts/update-crm-from-actions.mjs
 * 
 * Reads from: temp/extracted-actions.json
 */

import fs from 'fs';
import path from 'path';

const ACTIONS_FILE = './temp/extracted-actions.json';
const CRM_PATH = './crm/contacts';
const LOG_FILE = './logs/crm-update.log';

function log(message) {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] ${message}`);
  if (!fs.existsSync('./logs')) fs.mkdirSync('./logs', { recursive: true });
  fs.appendFileSync(LOG_FILE, `[${timestamp}] ${message}\n`);
}

function formatFileName(name) {
  if (!name) return null;
  const parts = name.trim().split(' ');
  const firstName = parts[0];
  const lastName = parts.slice(1).join('_') || 'Contact';
  return `${firstName}_${lastName}.md`;
}

function updateContactFile(filepath, actionItem, meetingTitle) {
  let content = fs.readFileSync(filepath, 'utf-8');

  // Add to Interaction Log
  const interactionDate = new Date().toISOString().split('T')[0];
  const newLogRow = `| ${interactionDate} | Meeting | ${meetingTitle} | Action item: ${actionItem.description.substring(0, 40)}... |`;

  // Find and update Interaction Log table
  const logRegex = /## Interaction Log\n\n\| Date \| Type \| Topics \| Notes \|\n\|.*?\n([\s\S]*?)(?=\n---|\n##)/;
  const logMatch = content.match(logRegex);
  
  if (logMatch) {
    const tableContent = logMatch[1];
    const updatedTable = newLogRow + '\n' + tableContent;
    content = content.replace(logRegex, `## Interaction Log\n\n| Date | Type | Topics | Notes |\n|------|------|--------|-------|\n${updatedTable}\n---\n`);
  }

  // Add to Action Items section
  if (actionItem.assignee !== 'me') {
    // They owe us something
    const actionItemText = `- [ ] ${actionItem.description}${actionItem.dueDate ? ` (due: ${actionItem.dueDate})` : ''}`;
    
    const theyOweRegex = /### Things They Owe Me\n([\s\S]*?)(?=\n###|\n---)/;
    const theyOweMatch = content.match(theyOweRegex);
    
    if (theyOweMatch) {
      const section = theyOweMatch[1];
      const updatedSection = `${section}${actionItemText}\n`;
      content = content.replace(theyOweRegex, `### Things They Owe Me\n${updatedSection}\n###`);
    }
  } else {
    // We owe them something
    const actionItemText = `- [ ] ${actionItem.description}${actionItem.dueDate ? ` (due: ${actionItem.dueDate})` : ''}`;
    
    const weOweRegex = /### Things I Owe Them\n([\s\S]*?)(?=\n###|\n---)/;
    const weOweMatch = content.match(weOweRegex);
    
    if (weOweMatch) {
      const section = weOweMatch[1];
      const updatedSection = `${section}${actionItemText}\n`;
      content = content.replace(weOweRegex, `### Things I Owe Them\n${updatedSection}\n###`);
    }
  }

  // Update Last Updated timestamp
  content = content.replace(
    /\*\*Last Updated:\*\* [\d-]+/,
    `**Last Updated:** ${new Date().toISOString().split('T')[0]}`
  );

  fs.writeFileSync(filepath, content);
}

async function main() {
  if (!fs.existsSync(ACTIONS_FILE)) {
    log('⚠ No extracted actions found');
    process.exit(0);
  }

  log('===== CRM Update from Actions Start =====');

  const data = JSON.parse(fs.readFileSync(ACTIONS_FILE, 'utf-8'));
  const { actionItems, transcript } = data;

  let updated = 0;

  actionItems.forEach(actionItem => {
    if (actionItem.relatedContact) {
      const filename = formatFileName(actionItem.relatedContact);
      if (!filename) return;

      const filepath = path.join(CRM_PATH, filename);
      
      if (fs.existsSync(filepath)) {
        try {
          updateContactFile(filepath, actionItem, transcript.title);
          log(`✓ Updated contact: ${actionItem.relatedContact}`);
          updated++;
        } catch (error) {
          log(`⚠ Error updating ${filename}: ${error.message}`);
        }
      } else {
        log(`⚠ Contact file not found: ${filename}`);
      }
    }
  });

  log(`✓ Updated ${updated} contact files`);
  log('===== CRM Update Complete =====');
}

main().catch(error => {
  log(`✗ Error: ${error.message}`);
  process.exit(1);
});
