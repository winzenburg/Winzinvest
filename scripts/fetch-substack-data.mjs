#!/usr/bin/env node

/**
 * Substack Data Fetcher
 * 
 * Fetches subscriber and post data from your Substack publication
 * 
 * Method 1: Using Substack API (recommended)
 * - Get your API key from: https://substack.com/app/publication/settings/api
 * - Set SUBSTACK_API_KEY environment variable
 * 
 * Method 2: Manual update (simplest for now)
 * - Check your Substack dashboard
 * - Run: node scripts/fetch-substack-data.mjs --manual 847 34 12
 * 
 * Usage:
 *   node scripts/fetch-substack-data.mjs --api
 *   node scripts/fetch-substack-data.mjs --manual 847 34 12
 * 
 * Arguments for manual:
 *   1. Subscribers (total)
 *   2. Open rate (%)
 *   3. Paid subscribers
 */

import fs from 'fs';
import https from 'https';

const dashboardPath = './dashboard-data.json';
const SUBSTACK_PUBLICATION = 'potshardscast'; // Your publication slug

function makeRequest(hostname, path, headers = {}) {
  return new Promise((resolve, reject) => {
    const defaultHeaders = {
      'User-Agent': 'OpenClaw-Dashboard-Bot/1.0',
      ...headers,
    };

    const options = {
      hostname,
      path,
      method: 'GET',
      headers: defaultHeaders,
    };

    https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => {
        data += chunk;
      });
      res.on('end', () => {
        try {
          resolve({
            status: res.statusCode,
            data: JSON.parse(data),
          });
        } catch (e) {
          resolve({
            status: res.statusCode,
            data: data,
          });
        }
      });
    }).on('error', reject).end();
  });
}

async function fetchViaAPI() {
  const apiKey = process.env.SUBSTACK_API_KEY;
  
  if (!apiKey) {
    console.error('Error: SUBSTACK_API_KEY not set');
    console.error('Get your API key from: https://substack.com/app/publication/settings/api');
    process.exit(1);
  }

  try {
    console.log(`Fetching Substack data for publication: ${SUBSTACK_PUBLICATION}`);
    
    // Fetch publication stats
    // Note: Substack API endpoint depends on your account type
    // This is the public API URL for fetching publication data
    const response = await makeRequest('substack.com', `/api/v1/publications/${SUBSTACK_PUBLICATION}`, {
      'Authorization': `Bearer ${apiKey}`,
    });

    if (response.status !== 200) {
      console.error(`API Error: ${response.status}`);
      console.error('Note: Substack API access is limited. Manual updates recommended.');
      return null;
    }

    const pub = response.data;
    
    return {
      subscribers: pub.subscriber_count || 0,
      paid: pub.paid_subscriber_count || 0,
      posts: pub.posts_count || 0,
      // Open rate requires accessing individual post data
      openRate: pub.avg_open_rate || 0,
    };
  } catch (error) {
    console.error(`Error fetching via API: ${error.message}`);
    return null;
  }
}

function updateFromManual(subscribers, openRate, paid) {
  try {
    let data = JSON.parse(fs.readFileSync(dashboardPath, 'utf-8'));
    
    data.content.postshards.subscribers = parseInt(subscribers);
    data.content.postshards.openRate = parseInt(openRate);
    data.content.postshards.paid = parseInt(paid);
    data.timestamp = new Date().toISOString();
    
    fs.writeFileSync(dashboardPath, JSON.stringify(data, null, 2));
    
    console.log(`✓ Updated Substack data:`);
    console.log(`  Subscribers: ${subscribers}`);
    console.log(`  Open Rate: ${openRate}%`);
    console.log(`  Paid: ${paid}`);
  } catch (error) {
    console.error(`Error: ${error.message}`);
    process.exit(1);
  }
}

async function main() {
  const args = process.argv.slice(2);
  
  if (args[0] === '--manual' && args[1] && args[2] && args[3]) {
    // Manual mode: node fetch-substack-data.mjs --manual 847 34 12
    updateFromManual(args[1], args[2], args[3]);
  } else if (args[0] === '--api') {
    // API mode
    const data = await fetchViaAPI();
    if (data) {
      try {
        let dashboard = JSON.parse(fs.readFileSync(dashboardPath, 'utf-8'));
        dashboard.content.postshards = {
          ...dashboard.content.postshards,
          ...data,
        };
        dashboard.timestamp = new Date().toISOString();
        fs.writeFileSync(dashboardPath, JSON.stringify(dashboard, null, 2));
        console.log('✓ Updated Substack data from API');
      } catch (error) {
        console.error(`Error updating: ${error.message}`);
        process.exit(1);
      }
    }
  } else {
    console.log('Usage:');
    console.log('  node scripts/fetch-substack-data.mjs --api');
    console.log('  node scripts/fetch-substack-data.mjs --manual <subscribers> <openRate> <paid>');
    console.log('');
    console.log('Example:');
    console.log('  node scripts/fetch-substack-data.mjs --manual 847 34 12');
    process.exit(1);
  }
}

main();
