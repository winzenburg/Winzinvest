#!/usr/bin/env node

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Parse all session logs from the last week
const sessionsDir = '/Users/pinchy/.openclaw/agents/main/sessions';
const now = Date.now();
const oneWeek = 7 * 24 * 60 * 60 * 1000;
const twoWeeks = 14 * 24 * 60 * 60 * 1000;

const thisWeekStart = now - oneWeek;
const lastWeekStart = now - twoWeeks;

const stats = {
  thisWeek: {
    byModel: {},
    byTaskType: {},
    totalTokens: 0,
    totalCost: 0
  },
  lastWeek: {
    byModel: {},
    byTaskType: {},
    totalTokens: 0,
    totalCost: 0
  }
};

// Approximate cost per 1M tokens (update these based on actual pricing)
const modelCosts = {
  'anthropic/claude-sonnet-4-5': { input: 3, output: 15 },
  'anthropic/claude-opus-4-5': { input: 15, output: 75 },
  'anthropic/claude-3-5-haiku-latest': { input: 1, output: 5 },
  'openai/gpt-5': { input: 5, output: 15 },
  'openai/gpt-5.1-codex': { input: 5, output: 15 },
  'google/gemini-2.5-flash-lite': { input: 0.075, output: 0.3 },
  'google/gemini-3-flash': { input: 0.075, output: 0.3 },
  'openai/gpt-5-nano': { input: 0.2, output: 0.8 },
};

function getTaskType(sessionFilePath, sessionKey, message, messageContent) {
  if (sessionKey && sessionKey.includes('cron:')) return 'cron';
  if (sessionKey && sessionKey.includes('isolated:')) return 'subagent';
  if (sessionFilePath && sessionFilePath.includes('isolated')) return 'subagent';
  if (sessionFilePath && sessionFilePath.includes('cron')) return 'cron';
  
  // Check message content for [cron:...] or [isolated:...] markers
  if (messageContent) {
    if (messageContent.includes('[cron:')) return 'cron';
    if (messageContent.includes('[isolated:')) return 'subagent';
  }
  
  if (message?.role === 'system') return 'system';
  return 'main';
}

function processSession(filePath) {
  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    const lines = content.trim().split('\n');
    
    let lastUserMessage = null;
    
    lines.forEach(line => {
      if (!line.trim()) return;
      
      try {
        const entry = JSON.parse(line);
        
        // Track user messages to identify cron/isolated markers
        const message = entry.message || entry;
        if (message.role === 'user') {
          lastUserMessage = message;
        }
        
        // Extract usage from assistant messages (check both entry.message and entry itself)
        if (message.role === 'assistant' && message.usage) {
          // Determine which week this message belongs to based on timestamp
          const messageTime = message.timestamp || entry.timestamp || 0;
          let weekBucket = null;
          if (messageTime >= thisWeekStart) {
            weekBucket = stats.thisWeek;
          } else if (messageTime >= lastWeekStart) {
            weekBucket = stats.lastWeek;
          } else {
            return; // Too old, skip
          }
          
          const model = message.model || 'unknown';
          const inputTokens = message.usage.input || 0;
          const outputTokens = message.usage.output || 0;
          const cacheReadTokens = message.usage.cacheRead || 0;
          const cacheWriteTokens = message.usage.cacheWrite || 0;
          const totalTokens = inputTokens + outputTokens; // Don't count cache read/write in total
          
          // Track by model
          if (!weekBucket.byModel[model]) {
            weekBucket.byModel[model] = {
              inputTokens: 0,
              outputTokens: 0,
              totalTokens: 0,
              cost: 0,
              calls: 0
            };
          }
          
          weekBucket.byModel[model].inputTokens += inputTokens;
          weekBucket.byModel[model].outputTokens += outputTokens;
          weekBucket.byModel[model].totalTokens += totalTokens;
          weekBucket.byModel[model].calls += 1;
          
          // Calculate cost (use actual cost if available, otherwise estimate)
          let cost;
          if (message.usage.cost && message.usage.cost.total) {
            cost = message.usage.cost.total;
          } else {
            const costs = modelCosts[model] || { input: 5, output: 15 };
            cost = (inputTokens / 1_000_000) * costs.input + (outputTokens / 1_000_000) * costs.output;
          }
          weekBucket.byModel[model].cost += cost;
          weekBucket.totalCost += cost;
          
          // Track by task type
          const sessionKey = entry.sessionKey || (entry.type === 'message' && entry.message?.sessionKey) || '';
          const taskType = getTaskType(filePath, sessionKey, message);
          if (!weekBucket.byTaskType[taskType]) {
            weekBucket.byTaskType[taskType] = {
              totalTokens: 0,
              cost: 0,
              calls: 0
            };
          }
          
          weekBucket.byTaskType[taskType].totalTokens += totalTokens;
          weekBucket.byTaskType[taskType].cost += cost;
          weekBucket.byTaskType[taskType].calls += 1;
          
          weekBucket.totalTokens += totalTokens;
        }
      } catch (e) {
        // Skip malformed lines
      }
    });
  } catch (e) {
    // Skip files we can't read
  }
}

// Process all session files
const files = fs.readdirSync(sessionsDir);
files.forEach(file => {
  if (file.endsWith('.jsonl') && !file.includes('.lock') && !file.includes('.deleted')) {
    processSession(path.join(sessionsDir, file));
  }
});

// Generate report
console.log('WEEKLY TOKEN USAGE REVIEW');
console.log('=========================');
console.log(`Report Period: ${new Date(thisWeekStart).toLocaleDateString()} - ${new Date(now).toLocaleDateString()}`);
console.log(`Comparison: ${new Date(lastWeekStart).toLocaleDateString()} - ${new Date(thisWeekStart).toLocaleDateString()}\n`);

// 1. Tokens by Model
console.log('1. TOKENS BY MODEL (This Week)');
console.log('-------------------------------');
const modelEntries = Object.entries(stats.thisWeek.byModel).sort((a, b) => b[1].totalTokens - a[1].totalTokens);
for (const [model, data] of modelEntries) {
  const modelName = model.split('/')[1] || model;
  console.log(`${modelName}:`);
  console.log(`  Input:  ${data.inputTokens.toLocaleString()} tokens`);
  console.log(`  Output: ${data.outputTokens.toLocaleString()} tokens`);
  console.log(`  Total:  ${data.totalTokens.toLocaleString()} tokens (${data.calls} calls)`);
  console.log(`  Cost:   $${data.cost.toFixed(2)}`);
  console.log();
}
console.log(`TOTAL THIS WEEK: ${stats.thisWeek.totalTokens.toLocaleString()} tokens | $${stats.thisWeek.totalCost.toFixed(2)}\n`);

// 2. Cost by Task Type
console.log('2. COST BY TASK TYPE (This Week)');
console.log('---------------------------------');
const taskEntries = Object.entries(stats.thisWeek.byTaskType).sort((a, b) => b[1].cost - a[1].cost);
for (const [task, data] of taskEntries) {
  const pct = (data.cost / stats.thisWeek.totalCost * 100).toFixed(1);
  console.log(`${task}: $${data.cost.toFixed(2)} (${pct}%) - ${data.totalTokens.toLocaleString()} tokens, ${data.calls} calls`);
}
console.log();

// 3. Routing Savings
console.log('3. ROUTING EFFICIENCY');
console.log('---------------------');
const haikusUsage = stats.thisWeek.byModel['anthropic/claude-3-5-haiku-latest'] || { totalTokens: 0, cost: 0 };
const geminiUsage = stats.thisWeek.byModel['google/gemini-2.5-flash-lite'] || { totalTokens: 0, cost: 0 };
const gemini3Usage = stats.thisWeek.byModel['google/gemini-3-flash'] || { totalTokens: 0, cost: 0 };
const cheapTokens = haikusUsage.totalTokens + geminiUsage.totalTokens + gemini3Usage.totalTokens;
const cheapCost = haikusUsage.cost + geminiUsage.cost + gemini3Usage.cost;

// Estimate savings vs all-Sonnet
const sonnetInputCost = 3;
const sonnetOutputCost = 15;
const avgRatio = 0.2; // Assume 20% output, 80% input
const estimatedSonnetCost = (cheapTokens / 1_000_000) * (sonnetInputCost * 0.8 + sonnetOutputCost * 0.2);
const savings = estimatedSonnetCost - cheapCost;

console.log(`Cheap model usage: ${cheapTokens.toLocaleString()} tokens ($${cheapCost.toFixed(2)})`);
console.log(`If routed to Sonnet: ~$${estimatedSonnetCost.toFixed(2)}`);
console.log(`Estimated savings: $${savings.toFixed(2)}\n`);

// 4. Optimization Candidates
console.log('4. OPTIMIZATION CANDIDATES');
console.log('--------------------------');
const sonnetUsage = stats.thisWeek.byModel['anthropic/claude-sonnet-4-5'] || { totalTokens: 0, cost: 0, calls: 0 };
const opusUsage = stats.thisWeek.byModel['anthropic/claude-opus-4-5'] || { totalTokens: 0, cost: 0, calls: 0 };

if (sonnetUsage.calls > 0) {
  const cronSonnet = stats.thisWeek.byTaskType['cron'] || { cost: 0 };
  if (cronSonnet.cost > 1) {
    console.log(`- Cron jobs on Sonnet: $${cronSonnet.cost.toFixed(2)} - Consider routing to Gemini Flash for simple checks`);
  }
}

if (opusUsage.calls > 0) {
  console.log(`- Opus usage detected: ${opusUsage.calls} calls, $${opusUsage.cost.toFixed(2)} - Review if all calls needed highest-tier model`);
}

const mainTaskCost = stats.thisWeek.byTaskType['main']?.cost || 0;
if (mainTaskCost > stats.thisWeek.totalCost * 0.7) {
  console.log(`- Main session uses ${(mainTaskCost / stats.thisWeek.totalCost * 100).toFixed(0)}% of budget - Consider routing simple queries to Haiku`);
}

if (Object.keys(stats.thisWeek.byModel).length === 1) {
  console.log('- Single model usage detected - Multi-model routing not active; significant savings available');
}

console.log();

// 5. Week-over-Week
console.log('5. WEEK-OVER-WEEK COMPARISON');
console.log('-----------------------------');
const tokenChange = stats.thisWeek.totalTokens - stats.lastWeek.totalTokens;
const costChange = stats.thisWeek.totalCost - stats.lastWeek.totalCost;
const tokenChangePct = stats.lastWeek.totalTokens > 0 ? (tokenChange / stats.lastWeek.totalTokens * 100) : 0;
const costChangePct = stats.lastWeek.totalCost > 0 ? (costChange / stats.lastWeek.totalCost * 100) : 0;

console.log(`Last week: ${stats.lastWeek.totalTokens.toLocaleString()} tokens | $${stats.lastWeek.totalCost.toFixed(2)}`);
console.log(`This week: ${stats.thisWeek.totalTokens.toLocaleString()} tokens | $${stats.thisWeek.totalCost.toFixed(2)}`);
console.log(`Change: ${tokenChange >= 0 ? '+' : ''}${tokenChange.toLocaleString()} tokens (${tokenChangePct >= 0 ? '+' : ''}${tokenChangePct.toFixed(1)}%)`);
console.log(`        ${costChange >= 0 ? '+$' : '-$'}${Math.abs(costChange).toFixed(2)} (${costChangePct >= 0 ? '+' : ''}${costChangePct.toFixed(1)}%)`);
console.log();

// Recommendations
console.log('RECOMMENDATIONS');
console.log('===============');

const recommendations = [];

// Model routing
if (Object.keys(stats.thisWeek.byModel).length < 3) {
  recommendations.push('1. Enable multi-model routing: Config shows fallbacks available but not being used. Route cron jobs to Gemini Flash and simple queries to Haiku.');
}

// Cron optimization
const cronCost = stats.thisWeek.byTaskType['cron']?.cost || 0;
if (cronCost > 5) {
  recommendations.push(`2. Optimize cron jobs: Currently spending $${cronCost.toFixed(2)}/week on scheduled tasks. Heartbeats should use gemini-2.5-flash-lite (already configured but verify it's active).`);
}

// Usage trend
if (costChangePct > 50) {
  recommendations.push(`3. Usage spike detected: ${costChangePct.toFixed(0)}% increase WoW. Review recent activities for optimization opportunities.`);
}

// Cost efficiency
if (stats.thisWeek.totalCost > 50) {
  recommendations.push('4. High usage week: Consider consolidating similar queries and using context more efficiently to reduce token burn.');
}

// Opus usage
if (opusUsage.cost > 10) {
  recommendations.push(`5. Opus usage review: $${opusUsage.cost.toFixed(2)} on highest-tier model. Ensure these tasks require maximum capability.`);
}

// Gemini routing
const currentHeartbeatModel = 'google/gemini-2.5-flash-lite';
if (!stats.thisWeek.byModel[currentHeartbeatModel] && cronCost > 1) {
  recommendations.push('6. Heartbeat routing not active: Config specifies Gemini Flash Lite for heartbeats but usage not detected. Verify routing is working.');
}

if (recommendations.length === 0) {
  recommendations.push('No major optimization opportunities detected. Current routing is efficient.');
}

recommendations.forEach(rec => console.log(rec));
console.log();
