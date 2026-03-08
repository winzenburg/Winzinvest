#!/usr/bin/env node

/**
 * Evening Task Summary (6:00 PM MT)
 * 
 * Reviews in-progress tasks
 * Sends Telegram summary of today + tomorrow plan
 * 
 * Scheduled via cron: 0 18 * * * (MST/MDT)
 */

import fs from 'fs';
import https from 'https';

const TASKS_PATH = './tasks';
const LOG_FILE = './logs/evening-summary.log';
const TELEGRAM_BOT_TOKEN = '8565359157:AAE3cA0Tn2OE62K2eaXiXYr1SFqAFkNtzMQ';
const TELEGRAM_CHAT_ID = '5316436116';

function log(message) {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] ${message}`);
  if (!fs.existsSync('./logs')) fs.mkdirSync('./logs', { recursive: true });
  fs.appendFileSync(LOG_FILE, `[${timestamp}] ${message}\n`);
}

function loadTaskIndex() {
  try {
    const indexPath = `${TASKS_PATH}/index.json`;
    const content = fs.readFileSync(indexPath, 'utf-8');
    return JSON.parse(content);
  } catch (error) {
    log(`⚠ Error loading task index: ${error.message}`);
    return { tasks: [], byStatus: { 'In Progress': [], 'Done': [] } };
  }
}

async function sendTelegramMessage(text) {
  return new Promise((resolve) => {
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

    req.on('error', () => resolve(false));
    req.write(payload);
    req.end();
  });
}

async function generateEveningSummary() {
  log('===== Evening Summary Start =====');

  const index = loadTaskIndex();
  const inProgressTasks = index.byStatus['In Progress'] || [];
  const doneTasks = index.byStatus['Done'] || [];

  // Build summary message
  let message = '📊 *Daily Task Summary*\n\n';
  message += `*${new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })}*\n\n`;

  // In Progress
  message += '*Currently Working On:*\n';
  if (inProgressTasks.length === 0) {
    message += '⚪ No tasks in progress\n\n';
  } else {
    inProgressTasks.forEach(task => {
      message += `🔵 ${task.title}\n`;
    });
    message += '\n';
  }

  // Completed Today
  message += '*Completed Today:*\n';
  if (doneTasks.length === 0) {
    message += '⚪ No tasks completed today\n\n';
  } else {
    doneTasks.slice(-5).forEach(task => {
      message += `✅ ${task.title}\n`;
    });
    message += '\n';
  }

  // Tomorrow's Plan
  const backlogTasks = index.byStatus.Backlog || [];
  message += '*Plan for Tomorrow:*\n';
  if (backlogTasks.length === 0) {
    message += '⚪ Empty backlog - ready for new priorities\n';
  } else {
    backlogTasks.slice(0, 3).forEach(task => {
      message += `□ ${task.title}\n`;
    });
    if (backlogTasks.length > 3) {
      message += `_+ ${backlogTasks.length - 3} more in backlog_\n`;
    }
  }

  // Stats
  message += `\n*Stats:* ${inProgressTasks.length} in progress · ${doneTasks.length} done · ${backlogTasks.length} backlog`;

  log('Sending summary to Telegram...');
  const sent = await sendTelegramMessage(message);

  if (sent) {
    log('✓ Summary sent to Telegram');
  } else {
    log('✗ Failed to send Telegram message');
  }

  log('===== Evening Summary Complete =====');
}

generateEveningSummary();
