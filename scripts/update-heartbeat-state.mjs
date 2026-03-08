#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const CHECKS = new Set(['market','github','kinletFeedback','security','communications']);

function usage() {
  console.error('Usage: node scripts/update-heartbeat-state.mjs <check-name>');
  console.error('Valid checks:', Array.from(CHECKS).join(', '));
  process.exit(1);
}

const [, , check] = process.argv;
if (!check || !CHECKS.has(check)) usage();

const statePath = path.resolve(process.cwd(), 'memory/heartbeat-state.json');
try {
  const now = Date.now();
  let state = { lastChecks: {} };
  if (fs.existsSync(statePath)) {
    const raw = fs.readFileSync(statePath, 'utf8');
    if (raw.trim()) state = JSON.parse(raw);
  }
  if (!state.lastChecks) state.lastChecks = {};
  state.lastChecks[check] = now;
  fs.writeFileSync(statePath, JSON.stringify(state, null, 2) + '\n');
  console.log(`Updated ${check} at ${now}`);
} catch (err) {
  console.error('Failed to update heartbeat state:', err.message);
  process.exit(2);
}
