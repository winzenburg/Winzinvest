#!/usr/bin/env node
/**
 * FeedHive MCP Client
 * Programmatic interface to FeedHive triggers via MCP
 */

import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Load API key from .env.feedhive
const envPath = join(__dirname, '../.env.feedhive');
const envContent = readFileSync(envPath, 'utf-8');
const API_KEY = envContent.match(/FEEDHIVE_API_KEY=(.+)/)?.[1]?.trim();

if (!API_KEY) {
  throw new Error('FEEDHIVE_API_KEY not found in .env.feedhive');
}

const MCP_ENDPOINT = 'https://mcp.feedhive.com';

/**
 * Make a JSON-RPC request to FeedHive MCP
 */
async function mcpRequest(method, params = {}) {
  const response = await fetch(MCP_ENDPOINT, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      jsonrpc: '2.0',
      id: Date.now(),
      method,
      params,
    }),
  });

  const data = await response.json();

  if (data.error) {
    throw new Error(`MCP Error: ${data.error.message || JSON.stringify(data.error)}`);
  }

  return data.result;
}

/**
 * List all available triggers
 */
export async function listTriggers() {
  const result = await mcpRequest('tools/list');
  return result.tools;
}

/**
 * Call a specific trigger
 */
export async function callTrigger(triggerName, args) {
  const result = await mcpRequest('tools/call', {
    name: triggerName,
    arguments: args,
  });
  return result;
}

/**
 * Post to Twitter via Kinlet trigger
 */
export async function postKinletTwitter({ prompt, scheduled, mediaUrls }) {
  const args = { prompt };
  
  if (scheduled) {
    args.scheduled = scheduled;
  }
  
  if (mediaUrls && mediaUrls.length > 0) {
    args.media_urls = mediaUrls;
  }
  
  return await callTrigger('trigger_6831n', args);
}

/**
 * CLI interface
 */
if (import.meta.url === `file://${process.argv[1]}`) {
  const command = process.argv[2];
  
  try {
    switch (command) {
      case 'list':
        const triggers = await listTriggers();
        console.log('Available triggers:');
        triggers.forEach(t => {
          console.log(`  - ${t.name}: ${t.description}`);
        });
        break;
        
      case 'twitter':
        const prompt = process.argv[3];
        if (!prompt) {
          console.error('Error: Prompt required');
          console.log('Usage: feedhive-client.mjs twitter "<prompt>" [scheduled-iso-date]');
          process.exit(1);
        }
        
        const scheduled = process.argv[4];
        const result = await postKinletTwitter({ prompt, scheduled });
        console.log('✓ Post created successfully!');
        console.log(JSON.stringify(result, null, 2));
        break;
        
      default:
        console.log('Usage:');
        console.log('  feedhive-client.mjs list');
        console.log('  feedhive-client.mjs twitter "<prompt>" [scheduled-iso-date]');
        process.exit(1);
    }
  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  }
}
