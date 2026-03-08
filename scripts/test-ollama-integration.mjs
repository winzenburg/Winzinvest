#!/usr/bin/env node
/**
 * test-ollama-integration.mjs
 * 
 * Quick validation that Ollama is set up correctly and models are available.
 * Run this to verify before integrating Ollama into production scripts.
 */

import { generate } from './ollama-client.mjs';

console.log('\n=== Ollama Integration Test ===\n');

// Test 1: Quick summary (fast)
console.log('📝 Test 1: Quick Summary (should take 2-3 seconds)...');
try {
  const result1 = await generate(
    'quick-summary',
    'In one sentence, what is the best way to learn machine learning?'
  );
  if (result1.success) {
    console.log(`✅ Success! Model: ${result1.model}`);
    console.log(`   Response: "${result1.text.substring(0, 100)}..."`);
  } else {
    console.log(`❌ Failed: ${result1.error}`);
  }
} catch (err) {
  console.log(`❌ Error: ${err.message}`);
}

// Test 2: Email formatting
console.log('\n📧 Test 2: Email Formatting (should take 3-4 seconds)...');
try {
  const result2 = await generate(
    'email-formatting',
    'Create a brief approval button layout: [Approve] [Revise] [Discard]'
  );
  if (result2.success) {
    console.log(`✅ Success! Model: ${result2.model}`);
    console.log(`   Response: "${result2.text.substring(0, 100)}..."`);
  } else {
    console.log(`❌ Failed: ${result2.error}`);
  }
} catch (err) {
  console.log(`❌ Error: ${err.message}`);
}

// Test 3: Research synthesis
console.log('\n🔬 Test 3: Research Synthesis (should take 5-8 seconds)...');
try {
  const result3 = await generate(
    'research-synthesis',
    'Synthesize: [1. AI is changing work, 2. Caregiver demand is growing, 3. Tech adoption is increasing]. Create 3 themes.'
  );
  if (result3.success) {
    console.log(`✅ Success! Model: ${result3.model}`);
    console.log(`   Response: "${result3.text.substring(0, 100)}..."`);
  } else {
    console.log(`❌ Failed: ${result3.error}`);
  }
} catch (err) {
  console.log(`❌ Error: ${err.message}`);
}

// Summary
console.log('\n=== Test Summary ===');
console.log('If all three passed: Ollama is ready for production.');
console.log('If any failed: Check that neural-chat:latest has finished pulling.');
console.log('\nNext: Integrate Ollama into content-writing-engine.mjs\n');
