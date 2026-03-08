#!/usr/bin/env node

/**
 * Content Factory Weekly Prompt
 * 
 * Sends a weekly reflection prompt via Telegram:
 * "What was your biggest professional learning this week?"
 * 
 * Runs: Every Monday at 9:00 AM MT
 */

import https from 'https';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE_DIR = path.join(__dirname, '..');
const LOG_FILE = path.join(WORKSPACE_DIR, 'logs', 'content-weekly-prompt.log');

const TELEGRAM_BOT_TOKEN = '8565359157:AAE3cA0Tn2OE62K2eaXiXYr1SFqAFkNtzMQ';
const TELEGRAM_CHAT_ID = '5316436116';

function log(message) {
  const timestamp = new Date().toISOString();
  const msg = `[${timestamp}] ${message}`;
  console.log(msg);
  fs.appendFileSync(LOG_FILE, msg + '\n');
}

async function sendTelegramPrompt() {
  log('Sending weekly content reflection prompt...');

  const message = `💭 **Weekly Content Reflection**

What was your biggest professional learning this week?

**Quick options:**

A) Framework/process I discovered
B) Lesson from a challenge or mistake
C) Customer insight that changed my thinking
D) Something else

Reply with the option or just share your learning! I'll turn it into a LinkedIn thread + article.`;

  const payload = JSON.stringify({
    chat_id: TELEGRAM_CHAT_ID,
    text: message,
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
            log('✓ Weekly prompt sent successfully');
            resolve(true);
          } else {
            log(`✗ Telegram error: ${result.description}`);
            resolve(false);
          }
        } catch (e) {
          log(`✗ Parse error: ${e.message}`);
          resolve(false);
        }
      });
    });

    req.on('error', (err) => {
      log(`✗ Request error: ${err.message}`);
      reject(err);
    });

    req.write(payload);
    req.end();
  });
}

async function main() {
  try {
    log('===== Content Factory Weekly Prompt Start =====');
    
    await sendTelegramPrompt();

    log('===== Content Factory Weekly Prompt Complete =====');
    process.exit(0);
  } catch (error) {
    log(`✗ Fatal error: ${error.message}`);
    process.exit(1);
  }
}

main();
