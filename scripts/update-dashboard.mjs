#!/usr/bin/env node

/**
 * Dashboard Data Updater
 * 
 * Usage: node scripts/update-dashboard.mjs [section] [key] [value]
 * 
 * Examples:
 *   node scripts/update-dashboard.mjs system telegram true
 *   node scripts/update-dashboard.mjs content postshards posts 15
 *   node scripts/update-dashboard.mjs kinlet signups 25
 */

import fs from 'fs';
import path from 'path';

const dashboardPath = './dashboard-data.json';

function getNestedValue(obj, keys) {
  return keys.reduce((current, key) => current?.[key], obj);
}

function setNestedValue(obj, keys, value) {
  let current = obj;
  for (let i = 0; i < keys.length - 1; i++) {
    const key = keys[i];
    if (!(key in current)) {
      current[key] = {};
    }
    current = current[key];
  }
  current[keys[keys.length - 1]] = value;
}

async function updateDashboard() {
  const [section, key, value] = process.argv.slice(2);

  if (!section || !key) {
    console.error('Usage: node scripts/update-dashboard.mjs [section] [key] [value]');
    console.error('Example: node scripts/update-dashboard.mjs system telegram true');
    process.exit(1);
  }

  try {
    // Read current data
    let data = JSON.parse(fs.readFileSync(dashboardPath, 'utf-8'));

    // Parse value (auto-detect number, boolean, or string)
    let parsedValue = value;
    if (value === 'true' || value === 'false') {
      parsedValue = value === 'true';
    } else if (!isNaN(value) && value !== '') {
      parsedValue = Number(value);
    }

    // Update nested value
    if (section === 'system') {
      data.system[key] = parsedValue;
    } else {
      const parts = [section, key];
      if (value && typeof value === 'string' && value.includes('.')) {
        // Handle deeply nested keys like "kinlet.signups"
        const [topSection, ...nestedKeys] = section.split('.');
        parts[0] = topSection;
        parts.push(...nestedKeys);
      }
      setNestedValue(data, [section, key], parsedValue);
    }

    // Update timestamp
    data.timestamp = new Date().toISOString();

    // Write back
    fs.writeFileSync(dashboardPath, JSON.stringify(data, null, 2));
    console.log(`✓ Updated ${section}.${key} = ${parsedValue}`);
  } catch (error) {
    console.error(`Error updating dashboard: ${error.message}`);
    process.exit(1);
  }
}

updateDashboard();
