#!/usr/bin/env node

/**
 * Granola Action Items - Task Creator
 * 
 * When user approves action items via Telegram (e.g., "1, 2, 3"),
 * this script creates tasks in Todoist
 * 
 * Usage: node scripts/granola-create-approved-tasks.mjs [item_numbers]
 * Example: node scripts/granola-create-approved-tasks.mjs "1,2,3"
 */

import https from 'https';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE_DIR = path.join(__dirname, '..');
const TODOIST_API_URL = 'https://api.todoist.com/api/v1';
const PENDING_ACTIONS_FILE = path.join(WORKSPACE_DIR, 'temp', 'granola-pending-actions.json');

const LOG_FILE = path.join(WORKSPACE_DIR, 'logs', 'granola-task-creation.log');

function log(message) {
  const timestamp = new Date().toISOString();
  const msg = `[${timestamp}] ${message}`;
  console.log(msg);
  if (!fs.existsSync(path.join(WORKSPACE_DIR, 'logs'))) {
    fs.mkdirSync(path.join(WORKSPACE_DIR, 'logs'), { recursive: true });
  }
  fs.appendFileSync(LOG_FILE, msg + '\n');
}

function getFromKeychain(service, account) {
  try {
    const result = execSync(
      `security find-generic-password -w -s "${service}" -a "${account}" ~/Library/Keychains/login.keychain-db`,
      { encoding: 'utf-8' }
    );
    return result.trim();
  } catch (err) {
    return null;
  }
}

async function createTodoistTask(item, meetingContext, todoistToken) {
  log(`Creating Todoist task: "${item.description}"`);

  const priorityMap = {
    high: 1,
    medium: 2,
    low: 3,
  };

  const taskPayload = {
    content: item.description,
    priority: priorityMap[item.priority] || 2,
    description: `From meeting: ${meetingContext.title}\nAttendees: ${meetingContext.participants?.join(', ') || 'N/A'}`,
  };

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
        'Authorization': `Bearer ${todoistToken}`,
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
          resolve(false);
        }
      });
    });

    req.on('error', (err) => {
      log(`✗ Request error: ${err.message}`);
      resolve(false);
    });

    req.write(payload);
    req.end();
  });
}

async function main() {
  try {
    log('===== Granola Task Creation Start =====');

    // Get approved item numbers from command line
    const approvedStr = process.argv[2];
    if (!approvedStr) {
      log('No item numbers provided. Usage: granola-create-approved-tasks.mjs "1,2,3"');
      process.exit(0);
    }

    const approvedNumbers = approvedStr.split(',').map(n => parseInt(n.trim())).filter(n => !isNaN(n));
    log(`Approved items: ${approvedNumbers.join(', ')}`);

    // Load pending actions
    if (!fs.existsSync(PENDING_ACTIONS_FILE)) {
      log('No pending actions file found');
      process.exit(0);
    }

    const pending = JSON.parse(fs.readFileSync(PENDING_ACTIONS_FILE, 'utf-8'));
    log(`Processing meeting: ${pending.meetingTitle}`);

    // Get Todoist token
    const todoistToken = getFromKeychain('OpenClaw', 'todoist-api-token');
    if (!todoistToken) {
      log('✗ Todoist API token not found in Keychain');
      process.exit(1);
    }

    // Create tasks for approved items
    let successCount = 0;
    for (const itemNum of approvedNumbers) {
      const itemIdx = itemNum - 1;
      if (itemIdx >= 0 && itemIdx < pending.items.length) {
        const item = pending.items[itemIdx];
        const success = await createTodoistTask(item, pending, todoistToken);
        if (success) successCount++;
      } else {
        log(`⚠ Invalid item number: ${itemNum}`);
      }
    }

    log(`✓ Created ${successCount}/${approvedNumbers.length} tasks`);

    // Clean up pending file
    fs.unlinkSync(PENDING_ACTIONS_FILE);
    log('Pending actions cleared');

    log('===== Granola Task Creation Complete =====');
  } catch (error) {
    log(`✗ Fatal error: ${error.message}`);
    process.exit(1);
  }
}

main();
