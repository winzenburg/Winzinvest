#!/usr/bin/env node

/**
 * Dashboard Scheduler
 * 
 * Master script that orchestrates all dashboard data refreshes
 * Run hourly or on-demand to keep dashboard up-to-date
 * 
 * Usage:
 *   node scripts/dashboard-scheduler.mjs [--full|--quick]
 * 
 * --quick: Only refresh GitHub and Vercel (fast, API-based)
 * --full:  Include manual prompts for Substack, LinkedIn (interactive)
 */

import { exec } from 'child_process';
import { promisify } from 'util';
import fs from 'fs';
import path from 'path';

const execAsync = promisify(exec);
const logPath = './logs/dashboard-scheduler.log';

// Ensure logs directory exists
if (!fs.existsSync('./logs')) {
  fs.mkdirSync('./logs', { recursive: true });
}

function log(message) {
  const timestamp = new Date().toISOString();
  const logMessage = `[${timestamp}] ${message}`;
  console.log(logMessage);
  fs.appendFileSync(logPath, logMessage + '\n');
}

async function runCommand(command, description) {
  try {
    log(`Running: ${description}...`);
    const { stdout, stderr } = await execAsync(command);
    if (stderr) {
      log(`⚠ ${description}: ${stderr.trim()}`);
    }
    log(`✓ ${description} completed`);
    return true;
  } catch (error) {
    log(`✗ ${description} failed: ${error.message}`);
    return false;
  }
}

async function main() {
  const args = process.argv.slice(2);
  const mode = args[0] || '--quick';

  log('===== Dashboard Scheduler Start =====');
  log(`Mode: ${mode}`);

  // Always run quick refreshes
  log('Running quick refreshes (GitHub, Vercel)...');
  await runCommand('node scripts/refresh-dashboard-data.mjs', 'Full data refresh');

  // If --full mode, prompt for manual updates
  if (mode === '--full') {
    log('Full mode: Would need manual input for Substack, LinkedIn, Website');
    log('To update manually, use:');
    log('  node scripts/fetch-substack-data.mjs --manual <subs> <openRate> <paid>');
    log('  node scripts/fetch-linkedin-data.mjs --manual <followers> <engagement> <topPost> <repurposed>');
  }

  log('===== Dashboard Scheduler Complete =====');
}

main().catch(error => {
  log(`Fatal error: ${error.message}`);
  process.exit(1);
});
