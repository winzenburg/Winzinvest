#!/usr/bin/env node

/**
 * Meeting Transcript Parser - Action Item Extractor
 * 
 * Parses Granola transcripts and extracts action items
 * Sends for approval via Telegram
 * 
 * Usage:
 *   node scripts/parse-meeting-transcript.mjs path/to/transcript.json
 *   node scripts/parse-meeting-transcript.mjs path/to/transcript.txt
 * 
 * Supported formats:
 * - Granola JSON export
 * - Plain text transcript
 * - Fathom JSON export
 */

import fs from 'fs';
import path from 'path';
import https from 'https';

const TELEGRAM_BOT_TOKEN = '8565359157:AAE3cA0Tn2OE62K2eaXiXYr1SFqAFkNtzMQ';
const TELEGRAM_CHAT_ID = '5316436116';
const LOG_FILE = './logs/transcript-parser.log';
const ACTIONS_TEMP_FILE = './temp/extracted-actions.json';

function log(message) {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] ${message}`);
  if (!fs.existsSync('./logs')) fs.mkdirSync('./logs', { recursive: true });
  fs.appendFileSync(LOG_FILE, `[${timestamp}] ${message}\n`);
}

function extractActionItems(content) {
  // Action item patterns to search for
  const patterns = [
    /(?:action item|ai|action|todo|task|todo:|ai:|follow up)[\s:]*([^.!?\n]+)/gi,
    /([A-Z][a-z]+\s+will\s+[^.!?\n]+)/g,
    /([A-Z][a-z]+\s+needs? to\s+[^.!?\n]+)/g,
    /(?:by|due|deadline|until)[\s:]*([^.!?\n]+?)(?=by|due|deadline|until|$)/gi,
    /\[TODO\][\s:]*([^[\]]+)/gi,
    /❌\s+([^[\]]+)(?=\[|\n|$)/g,
  ];

  const actionItems = [];
  const seen = new Set();

  patterns.forEach(pattern => {
    let match;
    while ((match = pattern.exec(content)) !== null) {
      const text = match[1].trim();
      if (text && text.length > 10 && !seen.has(text.toLowerCase())) {
        seen.add(text.toLowerCase());
        actionItems.push({
          description: text,
          raw: text,
          priority: determinePriority(text),
          assignee: extractAssignee(text),
          dueDate: extractDueDate(text),
          relatedContact: extractContactName(text)
        });
      }
    }
  });

  return actionItems.slice(0, 20); // Limit to 20 items
}

function determinePriority(text) {
  const highKeywords = ['urgent', 'critical', 'asap', 'immediately', 'high priority', 'must', 'blocking', 'critical path'];
  const mediumKeywords = ['important', 'should', 'need to', 'medium priority'];
  
  const lower = text.toLowerCase();
  if (highKeywords.some(kw => lower.includes(kw))) return 'high';
  if (mediumKeywords.some(kw => lower.includes(kw))) return 'medium';
  return 'low';
}

function extractAssignee(text) {
  // Look for "John will..." or "I need to..." patterns
  const mePatterns = /^(i|me|myself|i\'ll|i need|i will|i have to)/i;
  if (mePatterns.test(text)) return 'me';

  // Look for other person patterns
  const nameMatch = text.match(/^([A-Z][a-z]+)\s+(will|needs? to|should|has to)/);
  if (nameMatch) return nameMatch[1];

  return 'unassigned';
}

function extractDueDate(text) {
  const datePatterns = [
    /(?:by|due|deadline|until)\s+([^,.\n]+)/i,
    /(?:end of|eow|eom|next)\s+(\w+)/i,
    /(\d{1,2}\/\d{1,2}\/\d{4})/,
    /(tomorrow|today|next\s+\w+|this\s+\w+)/i
  ];

  for (const pattern of datePatterns) {
    const match = text.match(pattern);
    if (match) return match[1];
  }

  return null;
}

function extractContactName(text) {
  // Look for person names in the text
  const namePatterns = [
    /(?:with|to|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)/,
    /^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:will|needs?|should)/
  ];

  for (const pattern of namePatterns) {
    const match = text.match(pattern);
    if (match) return match[1].trim();
  }

  return null;
}

function parseTranscript(content) {
  let transcript = {};

  // Try JSON first (Granola or Fathom export)
  try {
    const parsed = JSON.parse(content);
    transcript = {
      title: parsed.title || parsed.name || 'Meeting',
      attendees: parsed.attendees || parsed.participants || [],
      content: parsed.transcript || parsed.notes || parsed.summary || JSON.stringify(parsed),
      timestamp: parsed.timestamp || parsed.created_at || new Date().toISOString()
    };
  } catch (e) {
    // Parse as plain text
    transcript = {
      title: 'Meeting',
      content: content,
      attendees: [],
      timestamp: new Date().toISOString()
    };
  }

  return transcript;
}

async function sendTelegramMessage(text) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify({
      chat_id: TELEGRAM_CHAT_ID,
      text: text,
      parse_mode: 'Markdown'
    });

    const options = {
      hostname: 'api.telegram.org',
      path: `/bot${TELEGRAM_BOT_TOKEN}/sendMessage`,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload)
      }
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const result = JSON.parse(data);
          resolve(result.ok);
        } catch (e) {
          resolve(false);
        }
      });
    });

    req.on('error', reject);
    req.write(payload);
    req.end();
  });
}

async function main() {
  const transcriptPath = process.argv[2];

  if (!transcriptPath) {
    console.error('Usage: node parse-meeting-transcript.mjs <path-to-transcript>');
    process.exit(1);
  }

  if (!fs.existsSync(transcriptPath)) {
    console.error(`File not found: ${transcriptPath}`);
    process.exit(1);
  }

  log('===== Meeting Transcript Parser Start =====');
  log(`Processing: ${transcriptPath}`);

  const content = fs.readFileSync(transcriptPath, 'utf-8');
  const transcript = parseTranscript(content);
  const actionItems = extractActionItems(transcript.content);

  if (actionItems.length === 0) {
    log('⚠ No action items found in transcript');
    process.exit(0);
  }

  log(`Found ${actionItems.length} action items`);

  // Save to temp file for later processing
  if (!fs.existsSync('./temp')) fs.mkdirSync('./temp', { recursive: true });
  fs.writeFileSync(ACTIONS_TEMP_FILE, JSON.stringify({
    transcript: {
      title: transcript.title,
      timestamp: transcript.timestamp,
      attendees: transcript.attendees
    },
    actionItems: actionItems
  }, null, 2));

  // Format for Telegram
  let telegramMessage = `📋 *New Action Items from Meeting*\n\n`;
  telegramMessage += `*Meeting:* ${transcript.title}\n`;
  telegramMessage += `*Time:* ${new Date(transcript.timestamp).toLocaleString()}\n\n`;
  telegramMessage += `*Extracted Action Items:*\n\n`;

  actionItems.forEach((item, idx) => {
    const priority = item.priority === 'high' ? '🔴' : item.priority === 'medium' ? '🟡' : '⚪';
    const dueText = item.dueDate ? ` (due: ${item.dueDate})` : '';
    const assigneeText = item.assignee !== 'unassigned' ? ` → ${item.assignee}` : '';
    
    telegramMessage += `${idx + 1}. ${priority} ${item.description}${assigneeText}${dueText}\n\n`;
  });

  telegramMessage += `\n_Reply with numbers you want to add (e.g., "1, 3, 5") or "all"_`;

  log(`Sending ${actionItems.length} items to Telegram for approval`);
  const sent = await sendTelegramMessage(telegramMessage);

  if (sent) {
    log('✓ Message sent to Telegram');
    log(`✓ Action items saved to: ${ACTIONS_TEMP_FILE}`);
    console.log(`\nReply to the Telegram message to approve which items to add to your task manager.`);
  } else {
    log('✗ Failed to send Telegram message');
    process.exit(1);
  }

  log('===== Meeting Transcript Parser Complete =====');
}

main().catch(error => {
  log(`✗ Error: ${error.message}`);
  process.exit(1);
});
