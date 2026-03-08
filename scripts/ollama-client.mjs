#!/usr/bin/env node
/**
 * ollama-client.mjs
 * 
 * Smart Ollama routing client. Routes different tasks to optimal local models:
 * - Mistral 7B: Fast tasks, summaries, email formatting
 * - Neural-Chat 7B: Research synthesis, quick decisions  
 * - Llama 2 13B: Premium pillar content (if available)
 * 
 * Caches responses and handles fallback to API if Ollama unavailable.
 * Uses native Node 18+ fetch (no node-fetch dependency needed)
 */

import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';
import crypto from 'crypto';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE = path.resolve(__dirname, '..');
const CACHE_DIR = path.join(WORKSPACE, '.ollama-cache');
const OLLAMA_URL = 'http://localhost:11434';
const OLLAMA_TIMEOUT = 60000; // 60s timeout

// Ensure cache directory exists
await fs.mkdir(CACHE_DIR, { recursive: true });

/**
 * Model selection logic based on task type
 */
const MODEL_ROUTING = {
  'pillar-content': {
    preferred: 'kimi-k2.5:cloud', // Ollama Pro cloud model (newer, faster, better)
    fallbackLocal: 'gpt-oss:20b', // Local gpt-oss for consistency (not Mistral)
    fallbackAPI: 'openai/gpt-4o-mini', // Ultimate fallback via OpenAI
    maxTokens: 2000,
    temperature: 0.7,
  },
  'pillar-content-cloud': {
    preferred: 'kimi-k2.5:cloud', // Ollama Pro cloud model for Kinlet pillar
    fallbackLocal: 'gpt-oss:20b', // Local fallback (architectural consistency)
    fallbackAPI: 'openai/gpt-4o-mini', // OpenAI fallback
    maxTokens: 2000,
    temperature: 0.7,
  },
  'research-synthesis': {
    preferred: 'neural-chat:latest',
    fallback: 'mistral:latest',
    maxTokens: 1500,
    temperature: 0.5,
  },
  'email-formatting': {
    preferred: 'mistral:latest',
    fallback: 'neural-chat:latest',
    maxTokens: 1000,
    temperature: 0.3,
  },
  'quick-summary': {
    preferred: 'neural-chat:latest',
    fallback: 'mistral:latest',
    maxTokens: 500,
    temperature: 0.4,
  },
  'spoke-repurposing': {
    preferred: 'mistral:latest',
    fallback: 'neural-chat:latest',
    maxTokens: 800,
    temperature: 0.6,
  },
};

/**
 * Check if Ollama is available (local)
 */
async function isOllamaAvailable() {
  try {
    const response = await Promise.race([
      fetch(`${OLLAMA_URL}/api/tags`),
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Timeout')), 3000)
      ),
    ]);
    return response.ok;
  } catch (err) {
    return false;
  }
}

/**
 * Check if Ollama Pro cloud is available
 */
async function isOllamaCloudAvailable() {
  try {
    // Attempt health check against cloud model endpoint
    const response = await Promise.race([
      fetch(`${OLLAMA_URL}/api/tags`), // Cloud models show in local tags if authenticated
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Cloud timeout')), 5000)
      ),
    ]);
    
    if (!response.ok) return false;
    
    const data = await response.json();
    const models = data.models || [];
    
    // Check if any cloud models are accessible (contain 'cloud' in name)
    const hasCloudModels = models.some(m => m.name && m.name.includes(':cloud'));
    return hasCloudModels;
  } catch (err) {
    console.warn(`[OLLAMA] Cloud availability check failed: ${err.message}`);
    return false;
  }
}

/**
 * List available models in Ollama
 */
async function listModels() {
  try {
    const response = await fetch(`${OLLAMA_URL}/api/tags`);
    const data = await response.json();
    return data.models || [];
  } catch (err) {
    console.error('Error listing models:', err.message);
    return [];
  }
}

/**
 * Generate cache key for response
 */
function getCacheKey(taskType, prompt) {
  const hash = crypto.createHash('md5').update(prompt).digest('hex');
  return `${taskType}_${hash}.json`;
}

/**
 * Generate with three-tier fallback chain
 * Tier 1: Ollama Pro cloud (kimi-k2.5:cloud)
 * Tier 2: Local Ollama (gpt-oss:20b)
 * Tier 3: OpenAI API (gpt-4o-mini)
 */
async function generateWithOllama(taskType, prompt) {
  const config = MODEL_ROUTING[taskType] || MODEL_ROUTING['quick-summary'];
  const cacheKey = getCacheKey(taskType, prompt);
  const cachePath = path.join(CACHE_DIR, cacheKey);

  // Check cache first
  try {
    const cached = await fs.readFile(cachePath, 'utf-8');
    const cached_data = JSON.parse(cached);
    console.log(`[CACHE] Hit: ${taskType} (model: ${cached_data.model})`);
    return {
      success: true,
      text: cached_data.text,
      model: cached_data.model,
      cached: true,
      tokensUsed: cached_data.tokensUsed,
    };
  } catch (err) {
    // Cache miss, continue
  }

  // ===== TIER 1: Try Ollama Pro Cloud =====
  console.log(`[TIER 1] Attempting Ollama Pro cloud (${config.preferred})...`);
  
  const cloudAvailable = await isOllamaCloudAvailable();
  if (cloudAvailable) {
    try {
      const result = await tryGenerateWithModel(config.preferred, prompt, config, taskType, cachePath);
      if (result.success) return result;
    } catch (err) {
      console.warn(`[TIER 1] Cloud failed: ${err.message}`);
    }
  }

  // ===== TIER 2: Fall back to Local Ollama =====
  console.log(`[TIER 2] Falling back to local Ollama (${config.fallbackLocal})...`);
  
  try {
    const result = await tryGenerateWithModel(config.fallbackLocal, prompt, config, taskType, cachePath);
    if (result.success) return result;
  } catch (err) {
    console.warn(`[TIER 2] Local fallback failed: ${err.message}`);
  }

  // ===== TIER 3: Ultimate fallback to OpenAI API =====
  console.log(`[TIER 3] Ultimate fallback to OpenAI API (${config.fallbackAPI})...`);
  
  try {
    return await generateWithOpenAI(prompt, config, taskType, cachePath);
  } catch (err) {
    console.error(`[TIER 3] OpenAI fallback failed: ${err.message}`);
    return {
      success: false,
      error: `All generation tiers failed. Last error: ${err.message}`,
      model: 'none',
    };
  }
}

/**
 * Helper: Try generation with specific model
 */
async function tryGenerateWithModel(model, prompt, config, taskType, cachePath) {
  console.log(`[GENERATING] Model: ${model}, Task: ${taskType}...`);

  const response = await Promise.race([
    fetch(`${OLLAMA_URL}/api/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model,
        prompt,
        stream: false,
        temperature: config.temperature,
        num_predict: config.maxTokens,
      }),
    }),
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error('Generation timeout')), OLLAMA_TIMEOUT)
    ),
  ]);

  if (!response.ok) {
    throw new Error(`Generation failed: HTTP ${response.status}`);
  }

  const data = await response.json();
  const text = data.response || '';

  // Cache the result
  const cacheData = {
    text,
    model,
    tokensUsed: data.eval_count || 0,
    generatedAt: new Date().toISOString(),
  };
  await fs.writeFile(cachePath, JSON.stringify(cacheData, null, 2));

  return {
    success: true,
    text,
    model,
    cached: false,
    tokensUsed: data.eval_count || 0,
  };
}

/**
 * Helper: OpenAI API fallback
 */
async function generateWithOpenAI(prompt, config, taskType, cachePath) {
  // This is a placeholder - actual implementation would use OpenAI SDK
  // For now, return error with guidance
  console.error(`[OPENAI] API integration not yet implemented`);
  console.error(`[OPENAI] Would use: gpt-4o-mini with prompt: ${prompt.substring(0, 100)}...`);
  
  throw new Error('OpenAI API fallback not yet configured. Set OPENAI_API_KEY to enable.');
}

/**
 * Main export: Universal generate function
 * Falls back to API if Ollama unavailable
 */
export async function generate(taskType, prompt, options = {}) {
  const available = await isOllamaAvailable();

  if (!available) {
    console.warn(
      '[OLLAMA] Not available, would fall back to API (not implemented yet)'
    );
    throw new Error('Ollama not available and API fallback not configured');
  }

  return generateWithOllama(taskType, prompt);
}

/**
 * Utility: Pre-format pillar content prompt
 */
export function createPillarPrompt(topic, stream) {
  const streamGuides = {
    kinlet: `You are writing for Kinlet.com. The audience is adult children caring for a parent with Alzheimer's or dementia. 
    Focus on practical, empathetic advice. Include specific, actionable strategies. 
    Write in second person ("you"). Include emotional validation alongside tactical steps.`,
    personal: `You are writing for winzenburg.com. The audience is product managers, designers, and entrepreneurs.
    Focus on frameworks, patterns, and strategic insights. Be opinionated. Reference specific examples from product/design/SaaS.
    Write authoritatively but accessibly.`,
  };

  const guide = streamGuides[stream] || streamGuides.personal;

  return `${guide}

Topic: ${topic}

Write a comprehensive, 1,500-word blog post. Include:
1. Opening hook (personal story or insight)
2. Problem statement (why this matters)
3. 3-4 core ideas or strategies
4. Real examples or case studies
5. Action steps for readers
6. Closing thought

Use clear headings. Be specific. Avoid jargon. Make it memorable.`;
}

/**
 * Utility: Pre-format research synthesis prompt
 */
export function createResearchPrompt(topic, findings) {
  return `Synthesize the following research findings about "${topic}" into actionable insights.

Findings:
${findings.map((f, i) => `${i + 1}. ${f}`).join('\n')}

Produce:
1. Executive Summary (2-3 sentences)
2. Key Themes (3-4 themes with supporting evidence)
3. Opportunity Statement (there is an opportunity to build X for Y)
4. Recommended Next Steps

Be specific and actionable. Reference the findings directly.`;
}

// CLI for testing
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const taskType = process.argv[2] || 'quick-summary';
  const prompt = process.argv[3] || 'What is the best way to learn AI?';

  const result = await generate(taskType, prompt);
  console.log('\n=== RESULT ===');
  console.log(JSON.stringify(result, null, 2));
  process.exit(result.success ? 0 : 1);
}

export default { generate, createPillarPrompt, createResearchPrompt };
