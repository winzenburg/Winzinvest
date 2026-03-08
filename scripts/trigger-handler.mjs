#!/usr/bin/env node

/**
 * Trigger Handler - Detects and executes workflow triggers
 * 
 * Monitors for patterns like:
 * - "Research: [topic]" → Spawns research-agent.mjs
 * - "Content: [topic]" → Spawns content-factory-research.mjs
 * - "Build it" → Spawns prototype-builder.mjs (with context from prior research)
 * 
 * Can be called:
 * 1. From Telegram message hook
 * 2. From chat interface
 * 3. From HEARTBEAT.md as part of communication scan
 */

import { exec } from 'child_process';
import { promisify } from 'util';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const execAsync = promisify(exec);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const workspaceDir = path.join(__dirname, '..');

// ============================================================================
// TRIGGER PATTERNS
// ============================================================================

const TRIGGERS = {
  // ===== CONTENT GENERATION TRIGGERS =====
  research: {
    pattern: /^Research:\s+(.+)$/i,
    handler: 'research-agent.mjs',
    description: 'Last 30 days market research pipeline',
    type: 'generation'
  },
  contentKinlet: {
    pattern: /^Content:\s+Kinlet\s+(?:for\s+)?(.+)$/i,
    handler: 'content-factory-kinlet.mjs',
    description: 'Kinlet pillar + spokes generation',
    type: 'generation'
  },
  contentLinkedin: {
    pattern: /^Content:\s+LinkedIn\s+(.+)$/i,
    handler: 'content-factory-linkedin.mjs',
    description: 'LinkedIn multi-post generation (weekly batch)',
    type: 'generation'
  },
  
  // ===== APPROVAL TRIGGERS (Telegram Commands) =====
  approveKinlet: {
    pattern: /^\/approve_kinlet(?:\s+(.+))?$/i,
    handler: 'approval-handler.mjs',
    description: 'Approve and queue Kinlet content for publishing',
    type: 'approval',
    action: 'approve',
    stream: 'kinlet'
  },
  reviseKinlet: {
    pattern: /^\/revise_kinlet\s+(.+)$/i,
    handler: 'approval-handler.mjs',
    description: 'Request revision on Kinlet content',
    type: 'approval',
    action: 'revise',
    stream: 'kinlet'
  },
  discardKinlet: {
    pattern: /^\/discard_kinlet(?:\s+(.+))?$/i,
    handler: 'approval-handler.mjs',
    description: 'Discard Kinlet content',
    type: 'approval',
    action: 'discard',
    stream: 'kinlet'
  },
  
  approveLinkedin: {
    pattern: /^\/approve_linkedin(?:\s+(.+))?$/i,
    handler: 'approval-handler.mjs',
    description: 'Approve and queue LinkedIn content',
    type: 'approval',
    action: 'approve',
    stream: 'linkedin'
  },
  reviseLinkedin: {
    pattern: /^\/revise_linkedin\s+(.+)$/i,
    handler: 'approval-handler.mjs',
    description: 'Request revision on LinkedIn content',
    type: 'approval',
    action: 'revise',
    stream: 'linkedin'
  },
  discardLinkedin: {
    pattern: /^\/discard_linkedin(?:\s+(.+))?$/i,
    handler: 'approval-handler.mjs',
    description: 'Discard LinkedIn content',
    type: 'approval',
    action: 'discard',
    stream: 'linkedin'
  },
  
  // ===== RESEARCH ACTIONS =====
  createKinletFromResearch: {
    pattern: /^\/create_kinlet_from_research(?:\s+(.+))?$/i,
    handler: 'research-suggestion.mjs',
    description: 'Create Kinlet content from research findings',
    type: 'research-action',
    action: 'create'
  },
  ignoreResearchSuggestion: {
    pattern: /^\/ignore(?:\s+research)?(?:\s+(.+))?$/i,
    handler: 'research-suggestion.mjs',
    description: 'Ignore research suggestion',
    type: 'research-action',
    action: 'ignore'
  },
  
  // ===== LEGACY TRIGGERS =====
  buildProto: {
    pattern: /^Build it$/i,
    handler: 'prototype-builder.mjs',
    description: 'Spawn prototype builder from last research brief',
    type: 'generation',
    requiresContext: 'lastResearchBrief'
  }
};

// ============================================================================
// PARSE MESSAGE AND DETECT TRIGGER
// ============================================================================

function detectTrigger(message) {
  for (const [triggerName, triggerConfig] of Object.entries(TRIGGERS)) {
    const match = message.match(triggerConfig.pattern);
    if (match) {
      return {
        name: triggerName,
        config: triggerConfig,
        param: match[1] || null
      };
    }
  }
  return null;
}

// ============================================================================
// EXECUTE RESEARCH AGENT
// ============================================================================

async function executeResearch(topic) {
  console.log(`\n🔍 Executing Research Agent for: "${topic}"\n`);
  
  try {
    const { stdout, stderr } = await execAsync(
      `node "${path.join(__dirname, 'research-agent.mjs')}" "Research: ${topic}"`,
      { cwd: workspaceDir }
    );
    
    if (stdout) console.log(stdout);
    if (stderr) console.error(stderr);
    
    // Extract research brief filename from stdout
    const briefMatch = stdout.match(/research\/(.+?\.md)/);
    const briefFile = briefMatch ? briefMatch[1] : null;
    
    // Store context for "Build it" follow-up
    if (briefFile) {
      const contextFile = path.join(workspaceDir, '.research-context.json');
      writeFileSync(contextFile, JSON.stringify({
        lastBriefFile: briefFile,
        topic: topic,
        timestamp: new Date().toISOString()
      }), 'utf-8');
    }
    
    return { success: true, briefFile };
    
  } catch (err) {
    console.error(`❌ Research execution failed: ${err.message}`);
    return { success: false, error: err.message };
  }
}

// ============================================================================
// EXECUTE CONTENT FACTORY — KINLET STREAM
// ============================================================================

async function executeContentKinlet(topic) {
  console.log(`\n🎯 Executing Kinlet Content Factory for: "${topic}"\n`);
  
  try {
    const { stdout, stderr } = await execAsync(
      `node "${path.join(__dirname, 'content-factory-kinlet.mjs')}" "${topic}"`,
      { cwd: workspaceDir, timeout: 30000 }
    );
    
    if (stdout) console.log(stdout);
    if (stderr) console.error(stderr);
    
    return { success: true };
    
  } catch (err) {
    console.error(`❌ Kinlet Content Factory execution failed: ${err.message}`);
    return { success: false, error: err.message };
  }
}

// ============================================================================
// EXECUTE CONTENT FACTORY — LINKEDIN STREAM
// ============================================================================

async function executeContentLinkedin(topic) {
  console.log(`\n💼 Executing LinkedIn Content Factory for: "${topic}"\n`);
  
  try {
    const { stdout, stderr } = await execAsync(
      `node "${path.join(__dirname, 'content-factory-linkedin.mjs')}" "${topic}"`,
      { cwd: workspaceDir, timeout: 30000 }
    );
    
    if (stdout) console.log(stdout);
    if (stderr) console.error(stderr);
    
    return { success: true };
    
  } catch (err) {
    console.error(`❌ LinkedIn Content Factory execution failed: ${err.message}`);
    return { success: false, error: err.message };
  }
}

// ============================================================================
// EXECUTE APPROVAL HANDLER
// ============================================================================

async function executeApproval(stream, action, feedback = null) {
  console.log(`\n📋 Executing Approval: stream=${stream}, action=${action}, feedback="${feedback}"\n`);
  
  try {
    const { stdout, stderr } = await execAsync(
      `node "${path.join(__dirname, 'approval-handler.mjs')}" --stream "${stream}" --action "${action}" ${feedback ? `--feedback "${feedback}"` : ''}`,
      { cwd: workspaceDir }
    );
    
    if (stdout) console.log(stdout);
    if (stderr) console.error(stderr);
    
    return { success: true };
    
  } catch (err) {
    console.error(`❌ Approval execution failed: ${err.message}`);
    return { success: false, error: err.message };
  }
}

// ============================================================================
// EXECUTE RESEARCH SUGGESTION — CREATE
// ============================================================================

async function executeCreateFromResearch(researchTopic = null) {
  console.log(`\n🔬 Creating content from research suggestion\n`);
  
  try {
    const { stdout, stderr } = await execAsync(
      `node "${path.join(__dirname, 'research-suggestion.mjs')}" --action create ${researchTopic ? `--topic "${researchTopic}"` : ''}`,
      { cwd: workspaceDir }
    );
    
    if (stdout) console.log(stdout);
    if (stderr) console.error(stderr);
    
    return { success: true };
    
  } catch (err) {
    console.error(`❌ Research content creation failed: ${err.message}`);
    return { success: false, error: err.message };
  }
}

// ============================================================================
// EXECUTE RESEARCH SUGGESTION — IGNORE
// ============================================================================

async function executeIgnoreResearch(researchTopic = null) {
  console.log(`\n⏭️ Ignoring research suggestion\n`);
  
  try {
    const { stdout, stderr } = await execAsync(
      `node "${path.join(__dirname, 'research-suggestion.mjs')}" --action ignore ${researchTopic ? `--topic "${researchTopic}"` : ''}`,
      { cwd: workspaceDir }
    );
    
    if (stdout) console.log(stdout);
    if (stderr) console.error(stderr);
    
    return { success: true };
    
  } catch (err) {
    console.error(`❌ Research ignore failed: ${err.message}`);
    return { success: false, error: err.message };
  }
}

// ============================================================================
// EXECUTE PROTOTYPE BUILDER
// ============================================================================

async function executePrototypeBuilder() {
  console.log(`\n🛠️ Executing Prototype Builder\n`);
  
  // Check for research context
  const contextFile = path.join(workspaceDir, '.research-context.json');
  
  if (!existsSync(contextFile)) {
    return {
      success: false,
      error: 'No recent research brief found. Try "Research: [topic]" first.'
    };
  }
  
  try {
    const context = JSON.parse(readFileSync(contextFile, 'utf-8'));
    
    // In production, would spawn prototype-builder.mjs with context
    // For now, acknowledge and prepare
    
    console.log(`Building prototype for research brief: ${context.topic}`);
    console.log(`Source: ${context.lastBriefFile}`);
    
    // Placeholder: actual implementation would:
    // 1. Read the research brief
    // 2. Extract MVP features
    // 3. Generate Next.js scaffold
    // 4. Deploy to Vercel
    // 5. Return prototype URL
    
    return { success: true, context };
    
  } catch (err) {
    console.error(`❌ Prototype builder failed: ${err.message}`);
    return { success: false, error: err.message };
  }
}

// ============================================================================
// SEND TELEGRAM NOTIFICATION
// ============================================================================

async function sendTelegramNotification(message, trigger) {
  console.log(`\n📱 Preparing Telegram notification:\n${message}\n`);
  
  // In production, would use message tool:
  // await message({ action: 'send', channel: 'telegram', message });
  
  // For now, store for manual delivery
  const notifFile = path.join(workspaceDir, `.pending-notification-${Date.now()}.txt`);
  writeFileSync(notifFile, message, 'utf-8');
  
  return true;
}

// ============================================================================
// MAIN HANDLER
// ============================================================================

async function handleTrigger(userMessage) {
  console.log(`\n📨 Processing message: "${userMessage}"\n`);
  
  // Detect trigger
  const trigger = detectTrigger(userMessage);
  
  if (!trigger) {
    console.log('No trigger detected. Message processing skipped.');
    return { handled: false };
  }
  
  console.log(`✅ Trigger detected: ${trigger.name}`);
  console.log(`📍 Description: ${trigger.config.description}\n`);
  
  // Handle context requirements (e.g., "Build it" needs recent research)
  if (trigger.config.requiresContext) {
    const contextFile = path.join(workspaceDir, '.research-context.json');
    if (!existsSync(contextFile)) {
      const msg = `⚠️ No recent research brief found. Try "Research: [topic]" first.`;
      await sendTelegramNotification(msg, trigger);
      return { handled: true, error: 'Missing context' };
    }
  }
  
  // Execute appropriate handler
  let result;
  let notification;
  
  switch (trigger.name) {
    // ===== GENERATION TRIGGERS =====
    case 'research':
      result = await executeResearch(trigger.param);
      notification = result.success
        ? `✅ Research brief generated: ${result.briefFile}`
        : `❌ Research failed: ${result.error}`;
      break;
      
    case 'contentKinlet':
      result = await executeContentKinlet(trigger.param);
      notification = result.success
        ? `✅ Kinlet content pipeline started for: "${trigger.param}"\n📧 Drafts will be delivered by 8:00 AM MST`
        : `❌ Kinlet content failed: ${result.error}`;
      break;
      
    case 'contentLinkedin':
      result = await executeContentLinkedin(trigger.param);
      notification = result.success
        ? `✅ LinkedIn content pipeline started for: "${trigger.param}"\n📧 Posts will be delivered by 8:00 AM MST`
        : `❌ LinkedIn content failed: ${result.error}`;
      break;
      
    // ===== APPROVAL TRIGGERS =====
    case 'approveKinlet':
      result = await executeApproval('kinlet', 'approve', trigger.param);
      notification = result.success
        ? `✅ Kinlet content approved and queued for publishing!`
        : `❌ Approval failed: ${result.error}`;
      break;
      
    case 'reviseKinlet':
      result = await executeApproval('kinlet', 'revise', trigger.param);
      notification = result.success
        ? `✅ Revision recorded: "${trigger.param}"\n📅 Revised draft will be delivered tomorrow 8:00 AM MST`
        : `❌ Revision failed: ${result.error}`;
      break;
      
    case 'discardKinlet':
      result = await executeApproval('kinlet', 'discard', trigger.param);
      notification = result.success
        ? `✅ Kinlet content discarded`
        : `❌ Discard failed: ${result.error}`;
      break;
      
    case 'approveLinkedin':
      result = await executeApproval('linkedin', 'approve', trigger.param);
      notification = result.success
        ? `✅ LinkedIn content approved and queued for publishing!`
        : `❌ Approval failed: ${result.error}`;
      break;
      
    case 'reviseLinkedin':
      result = await executeApproval('linkedin', 'revise', trigger.param);
      notification = result.success
        ? `✅ Revision recorded: "${trigger.param}"\n📅 Revised posts will be delivered tomorrow 8:00 AM MST`
        : `❌ Revision failed: ${result.error}`;
      break;
      
    case 'discardLinkedin':
      result = await executeApproval('linkedin', 'discard', trigger.param);
      notification = result.success
        ? `✅ LinkedIn content discarded`
        : `❌ Discard failed: ${result.error}`;
      break;
      
    // ===== RESEARCH ACTIONS =====
    case 'createKinletFromResearch':
      result = await executeCreateFromResearch(trigger.param);
      notification = result.success
        ? `✅ Creating Kinlet content from research findings\n📧 Drafts will be delivered by 8:00 AM MST`
        : `❌ Failed: ${result.error}`;
      break;
      
    case 'ignoreResearchSuggestion':
      result = await executeIgnoreResearch(trigger.param);
      notification = result.success
        ? `✅ Research suggestion ignored`
        : `❌ Failed: ${result.error}`;
      break;
      
    case 'buildProto':
      result = await executePrototypeBuilder();
      notification = result.success
        ? `🛠️ Prototype builder started for: ${result.context.topic}`
        : `❌ Prototype builder failed: ${result.error}`;
      break;
      
    default:
      return { handled: false };
  }
  
  // Send notification
  await sendTelegramNotification(notification, trigger);
  
  return {
    handled: true,
    trigger: trigger.name,
    result
  };
}

// ============================================================================
// COMMAND LINE EXECUTION
// ============================================================================

async function main() {
  const userMessage = process.argv[2];
  
  if (!userMessage) {
    console.error('Usage: trigger-handler.mjs "[message with trigger]"');
    process.exit(1);
  }
  
  const result = await handleTrigger(userMessage);
  
  if (result.handled) {
    console.log(`\n✅ Trigger processed successfully`);
    process.exit(0);
  } else {
    console.log(`\n⏭️ No trigger detected, message ignored`);
    process.exit(0);
  }
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});

// ============================================================================
// EXPORTS (for use as module)
// ============================================================================

export { detectTrigger, handleTrigger };
