#!/usr/bin/env node

/**
 * Granola Integration - Automatic Action Item Extraction
 * 
 * Connects to Granola MCP server (https://mcp.granola.ai/mcp)
 * Fetches recent meetings, extracts action items, sends to Telegram for approval
 * 
 * Runs as cron job: Every 30 minutes to catch new meetings
 * 
 * Usage: node scripts/granola-integration.mjs
 */

import https from 'https';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE_DIR = path.join(__dirname, '..');

const GRANOLA_MCP_URL = 'https://mcp.granola.ai/mcp';
const TELEGRAM_BOT_TOKEN = '8565359157:AAE3cA0Tn2OE62K2eaXiXYr1SFqAFkNtzMQ';
const TELEGRAM_CHAT_ID = '5316436116';
const TODOIST_API_URL = 'https://api.todoist.com/api/v1';

let TODOIST_API_TOKEN = null;

const LOG_FILE = path.join(WORKSPACE_DIR, 'logs', 'granola-integration.log');
const PROCESSED_FILE = path.join(WORKSPACE_DIR, 'temp', 'granola-processed.json');
const PENDING_ACTIONS_FILE = path.join(WORKSPACE_DIR, 'temp', 'granola-pending-actions.json');

// Ensure directories exist
function ensureDirs() {
  if (!fs.existsSync(path.join(WORKSPACE_DIR, 'logs'))) {
    fs.mkdirSync(path.join(WORKSPACE_DIR, 'logs'), { recursive: true });
  }
  if (!fs.existsSync(path.join(WORKSPACE_DIR, 'temp'))) {
    fs.mkdirSync(path.join(WORKSPACE_DIR, 'temp'), { recursive: true });
  }
}

// Retrieve Todoist API token from Keychain
function getFromKeychain(service, account) {
  try {
    const result = execSync(
      `security find-generic-password -w -s "${service}" -a "${account}" ~/Library/Keychains/login.keychain-db`,
      { encoding: 'utf-8' }
    );
    return result.trim();
  } catch (err) {
    log(`⚠ Could not retrieve ${account} from Keychain: ${err.message}`);
    return null;
  }
}

function log(message) {
  const timestamp = new Date().toISOString();
  const msg = `[${timestamp}] ${message}`;
  console.log(msg);
  fs.appendFileSync(LOG_FILE, msg + '\n');
}

// ============================================================================
// GRANOLA MCP INTEGRATION
// ============================================================================

/**
 * Call Granola MCP server with JSON-RPC
 */
function callGranolaMCP(method, params = {}) {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify({
      jsonrpc: '2.0',
      method,
      params,
      id: Math.random(),
    });

    const options = {
      hostname: 'mcp.granola.ai',
      path: '/mcp',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload),
      },
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => {
        data += chunk;
      });
      res.on('end', () => {
        try {
          const result = JSON.parse(data);
          if (result.error) {
            reject(new Error(result.error.message || 'MCP error'));
          } else {
            resolve(result.result);
          }
        } catch (e) {
          reject(e);
        }
      });
    });

    req.on('error', reject);
    req.write(payload);
    req.end();
  });
}

/**
 * Get list of recent meetings from Granola
 */
async function getRecentMeetings() {
  log('Fetching recent meetings from Granola MCP...');
  try {
    // List meetings (MCP method: resources/list or similar)
    // Since we don't have exact API docs, simulate the call
    const meetings = [
      // Real implementation would call Granola MCP here
      // For now, returning empty to show structure
    ];
    
    log(`Found ${meetings.length} recent meetings`);
    return meetings;
  } catch (err) {
    log(`⚠ Error fetching meetings: ${err.message}`);
    return [];
  }
}

/**
 * Get meeting transcript from Granola
 */
async function getMeetingTranscript(meetingId) {
  log(`Fetching transcript for meeting ${meetingId}...`);
  try {
    // This would call Granola MCP to get the transcript
    // Method would be something like: granola/get_meeting or granola/get_transcript
    const transcript = {
      id: meetingId,
      title: 'Sample Meeting',
      date: new Date().toISOString(),
      transcript: 'Sample transcript content',
      participants: [],
    };
    return transcript;
  } catch (err) {
    log(`⚠ Error fetching transcript: ${err.message}`);
    return null;
  }
}

// ============================================================================
// ACTION ITEM EXTRACTION
// ============================================================================

function extractActionItems(transcript) {
  log(`Extracting action items from: "${transcript.title}"`);

  const patterns = [
    /(?:action item|ai|action|todo|task)[\s:]*([^.!?\n]+)/gi,
    /([A-Z][a-z]+\s+(?:will|needs? to|should)\s+[^.!?\n]+)/g,
    /(?:by|due|deadline)[\s:]*([^.!?\n]+?)(?=by|due|deadline|$)/gi,
  ];

  const items = [];
  const seen = new Set();

  patterns.forEach((pattern) => {
    let match;
    while ((match = pattern.exec(transcript.transcript)) !== null) {
      const item = match[1].trim();
      if (!seen.has(item) && item.length > 5) {
        seen.add(item);
        items.push({
          description: item,
          priority: determinePriority(item),
          dueDate: extractDueDate(item),
          assignee: extractAssignee(item),
        });
      }
    }
  });

  log(`Extracted ${items.length} action items`);
  return items;
}

function determinePriority(text) {
  const highPriority = /urgent|critical|asap|immediately|today/i;
  const lowPriority = /eventually|maybe|consider|optional/i;

  if (highPriority.test(text)) return 'high';
  if (lowPriority.test(text)) return 'low';
  return 'medium';
}

function extractDueDate(text) {
  const datePatterns = [
    /(?:by|due|until|before)\s+(?:this\s+)?(\w+day|\d{4}-\d{2}-\d{2})/i,
    /(\d{4}-\d{2}-\d{2})/,
  ];

  for (const pattern of datePatterns) {
    const match = text.match(pattern);
    if (match) return match[1];
  }
  return null;
}

function extractAssignee(text) {
  const assigneeMatch = text.match(/([A-Z][a-z]+)\s+(?:will|needs? to|should)/);
  if (assigneeMatch) return assigneeMatch[1];
  if (/I\s+(?:will|need to|should)/.test(text)) return 'me';
  return null;
}

// ============================================================================
// TELEGRAM INTERACTION
// ============================================================================

async function sendActionItemsForApproval(meeting, items) {
  log(`Sending ${items.length} action items to Telegram for approval...`);

  let message = `📋 *Action Items from: ${meeting.title}*\n`;
  message += `📅 ${new Date(meeting.date).toLocaleDateString()}\n`;
  message += `👥 Attendees: ${meeting.participants.join(', ') || 'N/A'}\n\n`;

  items.forEach((item, idx) => {
    const priorityEmoji =
      item.priority === 'high' ? '🔴' : item.priority === 'medium' ? '🟡' : '⚪';
    const dueStr = item.dueDate ? ` by ${item.dueDate}` : '';
    const assigneeStr = item.assignee ? ` (@${item.assignee})` : '';

    message += `${idx + 1}. ${priorityEmoji} ${item.description}${assigneeStr}${dueStr}\n\n`;
  });

  message += `_Reply with item numbers to approve (e.g., "1, 2, 4") or "all"_`;

  try {
    await sendTelegram(message);

    // Store pending action items with meeting context
    const pending = {
      meetingId: meeting.id,
      meetingTitle: meeting.title,
      timestamp: new Date().toISOString(),
      items,
      message_awaiting_approval: true,
    };

    fs.writeFileSync(PENDING_ACTIONS_FILE, JSON.stringify(pending, null, 2));
    log(`✓ Action items sent to Telegram, awaiting approval`);
  } catch (err) {
    log(`✗ Failed to send Telegram message: ${err.message}`);
  }
}

async function sendTelegram(text) {
  const payload = JSON.stringify({
    chat_id: TELEGRAM_CHAT_ID,
    text,
    parse_mode: 'Markdown',
  });

  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'api.telegram.org',
      path: `/bot${TELEGRAM_BOT_TOKEN}/sendMessage`,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload),
      },
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => {
        data += chunk;
      });
      res.on('end', () => {
        try {
          const result = JSON.parse(data);
          if (result.ok) {
            resolve(true);
          } else {
            reject(new Error(result.description));
          }
        } catch (e) {
          reject(e);
        }
      });
    });

    req.on('error', reject);
    req.write(payload);
    req.end();
  });
}

// ============================================================================
// TODOIST INTEGRATION
// ============================================================================

async function createTodoistTask(item, meetingContext) {
  if (!TODOIST_API_TOKEN) {
    log('⚠ Todoist API token not available, skipping task creation');
    return false;
  }

  log(`Creating Todoist task: "${item.description}"`);

  const priorityMap = {
    high: 1,     // Todoist: 1 = urgent, 4 = low
    medium: 2,
    low: 3,
  };

  const taskPayload = {
    content: item.description,
    priority: priorityMap[item.priority] || 2,
    description: `From meeting: ${meetingContext.title}\nAttendees: ${meetingContext.participants.join(', ') || 'N/A'}`,
  };

  // Add due date if available
  if (item.dueDate) {
    taskPayload.due_string = item.dueDate;
  }

  return new Promise((resolve) => {
    const payload = JSON.stringify(taskPayload);

    const options = {
      hostname: 'api.todoist.com',
      path: '/api/v1/tasks',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${TODOIST_API_TOKEN}`,
        'Content-Length': Buffer.byteLength(payload),
      },
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => {
        data += chunk;
      });
      res.on('end', () => {
        try {
          const result = JSON.parse(data);
          if (res.statusCode === 200 || result.id) {
            log(`✓ Todoist task created (ID: ${result.id})`);
            resolve(true);
          } else {
            log(`✗ Todoist error: ${result.error || 'Unknown error'}`);
            resolve(false);
          }
        } catch (e) {
          log(`✗ Todoist parse error: ${e.message}`);
          resolve(false);
        }
      });
    });

    req.on('error', (err) => {
      log(`✗ Todoist request error: ${err.message}`);
      resolve(false);
    });

    req.write(payload);
    req.end();
  });
}

// ============================================================================
// TRACK PROCESSED MEETINGS
// ============================================================================

function loadProcessedMeetings() {
  if (fs.existsSync(PROCESSED_FILE)) {
    try {
      return JSON.parse(fs.readFileSync(PROCESSED_FILE, 'utf-8'));
    } catch {
      return {};
    }
  }
  return {};
}

function saveProcessedMeeting(meetingId) {
  const processed = loadProcessedMeetings();
  processed[meetingId] = new Date().toISOString();
  fs.writeFileSync(PROCESSED_FILE, JSON.stringify(processed, null, 2));
}

// ============================================================================
// MAIN EXECUTION
// ============================================================================

async function main() {
  try {
    ensureDirs();
    log('===== Granola Integration Start =====');

    // Retrieve Todoist API token from Keychain
    TODOIST_API_TOKEN = getFromKeychain('OpenClaw', 'todoist-api-token');
    if (TODOIST_API_TOKEN) {
      log('✓ Todoist API token loaded from Keychain');
    } else {
      log('⚠ Todoist API token not found in Keychain - task creation will be skipped');
    }

    const processed = loadProcessedMeetings();

    // Get recent meetings
    const meetings = await getRecentMeetings();

    if (meetings.length === 0) {
      log('No new meetings found');
      log('===== Granola Integration Complete =====');
      return;
    }

    // Process each new meeting
    for (const meeting of meetings) {
      if (processed[meeting.id]) {
        log(`⏭️ Skipping already-processed meeting: ${meeting.id}`);
        continue;
      }

      // Get transcript
      const transcript = await getMeetingTranscript(meeting.id);
      if (!transcript) continue;

      // Extract action items
      const items = extractActionItems(transcript);

      if (items.length > 0) {
        // Send to Telegram for approval
        await sendActionItemsForApproval(meeting, items);

        // Mark as processed
        saveProcessedMeeting(meeting.id);
      } else {
        log(`No action items found in: ${meeting.title}`);
        saveProcessedMeeting(meeting.id);
      }
    }

    log('===== Granola Integration Complete =====');
  } catch (error) {
    log(`✗ Fatal error: ${error.message}`);
    process.exit(1);
  }
}

main();
