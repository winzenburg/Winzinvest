#!/usr/bin/env node

/**
 * Approved Tasks Creator
 * 
 * Takes approved action items and creates them in task manager
 * Supports: Todoist (REST API), Things 3 (AppleScript)
 * 
 * Usage:
 *   node scripts/create-approved-tasks.mjs "1, 3, 5"
 *   node scripts/create-approved-tasks.mjs "all"
 *   node scripts/create-approved-tasks.mjs "1, 2" --things3
 */

import fs from 'fs';
import { exec } from 'child_process';
import { promisify } from 'util';
import https from 'https';

const execAsync = promisify(exec);
const TODOIST_TOKEN = process.env.TODOIST_API_TOKEN;
const ACTIONS_FILE = './temp/extracted-actions.json';
const LOG_FILE = './logs/task-creation.log';

function log(message) {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] ${message}`);
  if (!fs.existsSync('./logs')) fs.mkdirSync('./logs', { recursive: true });
  fs.appendFileSync(LOG_FILE, `[${timestamp}] ${message}\n`);
}

async function createTodoistTask(task) {
  if (!TODOIST_TOKEN) {
    log('⚠ TODOIST_API_TOKEN not set, skipping Todoist');
    return false;
  }

  return new Promise((resolve) => {
    const payload = JSON.stringify({
      content: task.description,
      due_string: task.dueDate || 'today',
      priority: task.priority === 'high' ? 4 : task.priority === 'medium' ? 3 : 2,
      description: `From meeting: ${task.relatedContact || 'General'}${task.assignee !== 'me' ? ` - Assigned to: ${task.assignee}` : ''}`
    });

    const options = {
      hostname: 'api.todoist.com',
      path: '/rest/v2/tasks',
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${TODOIST_TOKEN}`,
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
          if (result.id) {
            log(`✓ Created Todoist task: ${task.description}`);
            resolve(true);
          } else {
            log(`✗ Todoist error: ${result.error || 'Unknown'}`);
            resolve(false);
          }
        } catch (e) {
          resolve(false);
        }
      });
    });

    req.on('error', () => resolve(false));
    req.write(payload);
    req.end();
  });
}

async function createThings3Task(task) {
  // Things 3 uses AppleScript or x-things:// URL scheme
  const escapeAppleScript = (str) => str.replace(/"/g, '\\"');
  
  const description = escapeAppleScript(task.description);
  const notes = escapeAppleScript(
    `From meeting${task.relatedContact ? ` with ${task.relatedContact}` : ''}\n` +
    `Assigned to: ${task.assignee}\n` +
    `Priority: ${task.priority}`
  );

  const dueDate = task.dueDate ? 
    `set due date of todo to date "${task.dueDate}"` : '';

  const script = `
    tell application "Things3"
      set newTodo to make new to do with properties {name:"${description}", notes:"${notes}"}
      ${dueDate}
      return id of newTodo
    end tell
  `;

  try {
    const { stdout } = await execAsync(`osascript -e '${script}'`);
    log(`✓ Created Things 3 task: ${task.description}`);
    return true;
  } catch (error) {
    log(`⚠ Things 3 error: ${error.message}`);
    return false;
  }
}

async function parseApprovedSelection(input, total) {
  if (input.toLowerCase() === 'all') {
    return Array.from({ length: total }, (_, i) => i);
  }

  try {
    return input
      .split(',')
      .map(s => parseInt(s.trim()) - 1)
      .filter(n => n >= 0 && n < total);
  } catch (e) {
    return [];
  }
}

async function main() {
  const selection = process.argv[2];
  const useThings3 = process.argv.includes('--things3');

  if (!selection) {
    console.error('Usage: node create-approved-tasks.mjs "1, 3, 5" [--things3]');
    console.error('Or: node create-approved-tasks.mjs "all"');
    process.exit(1);
  }

  if (!fs.existsSync(ACTIONS_FILE)) {
    log('❌ No extracted actions found. Parse a transcript first.');
    process.exit(1);
  }

  log('===== Task Creation Start =====');
  log(`Task Manager: ${useThings3 ? 'Things 3' : 'Todoist'}`);

  const data = JSON.parse(fs.readFileSync(ACTIONS_FILE, 'utf-8'));
  const { actionItems } = data;

  const approvedIndices = await parseApprovedSelection(selection, actionItems.length);
  
  if (approvedIndices.length === 0) {
    log('⚠ No valid selections');
    process.exit(0);
  }

  log(`Creating ${approvedIndices.length} approved tasks`);

  let successCount = 0;
  for (const idx of approvedIndices) {
    const task = actionItems[idx];
    
    try {
      const success = useThings3 
        ? await createThings3Task(task)
        : await createTodoistTask(task);
      
      if (success) successCount++;
    } catch (error) {
      log(`✗ Error creating task: ${error.message}`);
    }
  }

  log(`✓ Created ${successCount}/${approvedIndices.length} tasks`);

  // Update CRM with action items
  log('Updating CRM contacts...');
  for (const idx of approvedIndices) {
    const task = actionItems[idx];
    if (task.relatedContact) {
      log(`📇 Updating contact: ${task.relatedContact}`);
      // CRM update will be called separately
    }
  }

  log('===== Task Creation Complete =====');
}

main().catch(error => {
  log(`✗ Fatal error: ${error.message}`);
  process.exit(1);
});
