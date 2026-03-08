#!/usr/bin/env node

/**
 * LinkedIn Data Fetcher
 * 
 * Fetches profile metrics from LinkedIn
 * 
 * LinkedIn's official API is restrictive. For now, manual updates are recommended.
 * 
 * Usage:
 *   node scripts/fetch-linkedin-data.mjs --manual <followers> <engagement> <topPostEngagements> <repurposed>
 * 
 * Example:
 *   node scripts/fetch-linkedin-data.mjs --manual 1250 8.5 156 4
 * 
 * Arguments:
 *   1. Followers (total)
 *   2. Engagement rate (%)
 *   3. Top post engagements (this month)
 *   4. Repurposed content (this month)
 */

import fs from 'fs';

const dashboardPath = './dashboard-data.json';

function updateFromManual(followers, engagement, topPostEngagements, repurposed) {
  try {
    let data = JSON.parse(fs.readFileSync(dashboardPath, 'utf-8'));
    
    data.content.linkedin = {
      followers: parseInt(followers),
      engagement: parseFloat(engagement),
      topPostEngagements: parseInt(topPostEngagements),
      repurposedThisMonth: parseInt(repurposed),
    };
    data.timestamp = new Date().toISOString();
    
    fs.writeFileSync(dashboardPath, JSON.stringify(data, null, 2));
    
    console.log(`✓ Updated LinkedIn data:`);
    console.log(`  Followers: ${followers}`);
    console.log(`  Engagement: ${engagement}%`);
    console.log(`  Top Post: ${topPostEngagements} engagements`);
    console.log(`  Repurposed: ${repurposed} posts`);
  } catch (error) {
    console.error(`Error: ${error.message}`);
    process.exit(1);
  }
}

function main() {
  const args = process.argv.slice(2);
  
  if (args[0] === '--manual' && args[1] && args[2] && args[3] && args[4]) {
    updateFromManual(args[1], args[2], args[3], args[4]);
  } else {
    console.log('Usage:');
    console.log('  node scripts/fetch-linkedin-data.mjs --manual <followers> <engagement> <topPostEngagements> <repurposed>');
    console.log('');
    console.log('Example:');
    console.log('  node scripts/fetch-linkedin-data.mjs --manual 1250 8.5 156 4');
    console.log('');
    console.log('Note: LinkedIn API access is restricted.');
    console.log('Recommend manually checking your profile and updating daily.');
    process.exit(1);
  }
}

main();
