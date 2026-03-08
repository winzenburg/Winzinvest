#!/usr/bin/env node

/**
 * Ollama Local Model Tester
 * 
 * Test Mistral 7B locally without hitting external APIs
 * 
 * Usage:
 *   node scripts/test-ollama.mjs "Your prompt here"
 * 
 * Examples:
 *   node scripts/test-ollama.mjs "What are the top 3 swing trading rules?"
 *   node scripts/test-ollama.mjs "Summarize this market insight: ..."
 */

import https from 'https';
import http from 'http';

const OLLAMA_URL = 'http://127.0.0.1:11434';
const MODEL = 'mistral';

function makeRequest(endpoint, payload) {
  return new Promise((resolve, reject) => {
    const url = new URL(OLLAMA_URL);
    
    const options = {
      hostname: url.hostname,
      port: url.port || 11434,
      path: endpoint,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    };

    const req = (url.protocol === 'https:' ? https : http).request(options, (res) => {
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
    });

    req.on('error', reject);
    req.write(JSON.stringify(payload));
    req.end();
  });
}

async function testOllama() {
  const prompt = process.argv[2] || 'What is the best approach to swing trading?';

  console.log('🤖 Mistral 7B Local Model Test');
  console.log('==============================');
  console.log(`Model: ${MODEL}`);
  console.log(`Prompt: ${prompt}`);
  console.log('');
  console.log('Generating response (this may take 30-60 seconds on first run)...');
  console.log('');

  try {
    const response = await makeRequest('/api/generate', {
      model: MODEL,
      prompt: prompt,
      stream: false,
    });

    if (response.status === 200) {
      console.log('✅ Success!');
      console.log('');
      console.log('Response:');
      console.log('----------');
      console.log(response.data.response);
      console.log('----------');
      console.log('');
      console.log(`⏱️  Time: ${(response.data.eval_duration / 1e9).toFixed(1)}s`);
      console.log(`📊 Tokens: ${response.data.eval_count}`);
    } else {
      console.error(`❌ Error: HTTP ${response.status}`);
      console.error(response.data);
    }
  } catch (error) {
    console.error(`❌ Connection error: ${error.message}`);
    console.error('');
    console.error('Make sure Ollama is running:');
    console.error('  ollama serve');
    process.exit(1);
  }
}

testOllama();
