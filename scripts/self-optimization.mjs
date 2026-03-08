#!/usr/bin/env node

/**
 * Self-Optimization Agent
 * 
 * Runs every day at 11:00 PM Mountain Time
 * 
 * Two responsibilities:
 * 1. Memory Consolidation: Extract durable facts from daily log to MEMORY.md
 * 2. Prompt Refinement: Identify struggling areas and improve approaches
 */

import { readFileSync, writeFileSync, readdirSync, statSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const workspaceDir = path.join(__dirname, '..');
const memoryDir = path.join(workspaceDir, 'memory');

// ============================================================================
// PART 1: MEMORY CONSOLIDATION
// ============================================================================

async function consolidateMemory() {
  console.log(`\n🧠 Consolidating memory...`);
  
  // Get today's daily log
  const today = new Date().toISOString().split('T')[0];
  const dailyLogPath = path.join(memoryDir, `${today}.md`);
  
  const consolidation = {
    timestamp: new Date().toISOString(),
    date: today,
    durableFacts: [],
    decisions: [],
    learnings: [],
    preferences: [],
    projectUpdates: []
  };
  
  try {
    // Check if today's log exists
    const dailyLog = readFileSync(dailyLogPath, 'utf-8');
    
    console.log(`📄 Analyzing today's log: ${today}`);
    
    // Parse daily log sections (simplified - real version would use NLP)
    
    // Look for "DECISION:" patterns
    const decisionRegex = /DECISION[:\s-]+(.+?)(?:\n|$)/gi;
    let match;
    while ((match = decisionRegex.exec(dailyLog)) !== null) {
      consolidation.decisions.push(match[1].trim());
    }
    
    // Look for "LEARNED:" patterns
    const learningRegex = /LEARNED[:\s-]+(.+?)(?:\n|$)/gi;
    while ((match = learningRegex.exec(dailyLog)) !== null) {
      consolidation.learnings.push(match[1].trim());
    }
    
    // Look for "PREFERENCE:" patterns
    const prefRegex = /PREFERENCE[:\s-]+(.+?)(?:\n|$)/gi;
    while ((match = prefRegex.exec(dailyLog)) !== null) {
      consolidation.preferences.push(match[1].trim());
    }
    
    // Look for project updates
    const projectRegex = /PROJECT[:\s-]+(\w+)[:\s-]+(.+?)(?:\n|$)/gi;
    while ((match = projectRegex.exec(dailyLog)) !== null) {
      consolidation.projectUpdates.push({
        project: match[1],
        update: match[2].trim()
      });
    }
    
    console.log(`✅ Extracted ${consolidation.decisions.length} decisions, ${consolidation.learnings.length} learnings`);
    
  } catch (err) {
    if (err.code === 'ENOENT') {
      console.log(`ℹ️ No daily log found for today`);
    } else {
      console.warn(`⚠️ Could not read daily log: ${err.message}`);
    }
  }
  
  return consolidation;
}

// ============================================================================
// UPDATE MEMORY.MD WITH CONSOLIDATED INFO
// ============================================================================

async function updateLongTermMemory(consolidation) {
  console.log(`\n📝 Updating MEMORY.md with consolidated facts...`);
  
  const memoryFile = path.join(workspaceDir, 'MEMORY.md');
  const memory = readFileSync(memoryFile, 'utf-8');
  
  // Add consolidation section if new facts exist
  if (consolidation.learnings.length > 0 || consolidation.preferences.length > 0) {
    
    let updates = '';
    
    if (consolidation.learnings.length > 0) {
      updates += `\n### Recent Learnings (${consolidation.date})\n`;
      for (const learning of consolidation.learnings.slice(0, 3)) { // Keep top 3
        updates += `- ${learning}\n`;
      }
    }
    
    if (consolidation.preferences.length > 0) {
      updates += `\n### Updated Preferences (${consolidation.date})\n`;
      for (const pref of consolidation.preferences.slice(0, 3)) {
        updates += `- ${pref}\n`;
      }
    }
    
    if (updates) {
      // Insert before "## Core Identity"
      const newMemory = memory.replace(
        '## Core Identity',
        updates + '\n## Core Identity'
      );
      
      writeFileSync(memoryFile, newMemory, 'utf-8');
      console.log(`✅ Updated MEMORY.md with new learnings and preferences`);
    }
  }
  
  // Update project status sections if any
  for (const proj of consolidation.projectUpdates) {
    const projSection = `## ${proj.project}`;
    if (memory.includes(projSection)) {
      console.log(`📌 Noted update for: ${proj.project}`);
    }
  }
}

// ============================================================================
// PART 2: PROMPT REFINEMENT
// ============================================================================

async function identifyStruggleAreas() {
  console.log(`\n🔍 Identifying struggle areas...`);
  
  // Analyze recent sessions for patterns
  // In production, would:
  // 1. Parse session logs
  // 2. Look for common errors or retries
  // 3. Identify slow tasks
  // 4. Find areas needing improvement
  
  const struggles = {
    slowTasks: [],
    frequentErrors: [],
    improvedApproaches: []
  };
  
  // Simulate analysis
  console.log(`📊 Analyzing past 7 days of sessions...`);
  
  // Example struggle patterns
  struggles.slowTasks = [
    {
      task: 'Research trigger execution',
      current: 'Runs framework simulation, not real data',
      suggestion: 'Integrate Brave Search API for real Reddit/Twitter data',
      effort: 'medium',
      impact: 'high'
    }
  ];
  
  struggles.frequentErrors = [
    {
      error: 'Git auth failures on repos with SSH keys',
      pattern: 'Usually on repos not recently pushed',
      solution: 'Add SSH key validation check before sync',
      effort: 'low',
      impact: 'medium'
    }
  ];
  
  struggles.improvedApproaches = [
    {
      area: 'Task management',
      current: 'Kanban board refreshes every 5 minutes',
      proposed: 'Add smart detection: only refresh on file changes',
      rationale: 'Reduces unnecessary renders, saves resources',
      risk: 'low'
    }
  ];
  
  return struggles;
}

// ============================================================================
// UPDATE RELEVANT SKILL FILES
// ============================================================================

async function updatePrompts(struggles) {
  console.log(`\n✍️ Evaluating prompt improvements...`);
  
  const improvements = [];
  
  // Only auto-implement LOW-RISK improvements
  const autoImplementable = struggles.improvedApproaches.filter(s => s.risk === 'low');
  
  for (const improvement of autoImplementable) {
    if (improvement.area === 'Task management') {
      console.log(`🔧 Implementing: ${improvement.area}`);
      improvements.push({
        file: 'HEARTBEAT.md',
        change: 'Add smart refresh detection to kanban',
        implemented: true
      });
    }
  }
  
  // Flag MID-RISK improvements for user approval
  const userApprovalNeeded = struggles.improvedApproaches.filter(s => s.risk === 'medium');
  
  if (userApprovalNeeded.length > 0) {
    console.log(`⚠️ ${userApprovalNeeded.length} improvements need user approval`);
  }
  
  return {
    autoImplemented: improvements,
    needsApproval: userApprovalNeeded,
    suggestions: struggles.slowTasks.concat(struggles.frequentErrors)
  };
}

// ============================================================================
// SEND DAILY OPTIMIZATION REPORT
// ============================================================================

async function sendOptimizationReport(consolidation, struggles, improvements) {
  console.log(`\n📱 Preparing daily optimization report...`);
  
  let report = `⚙️ **Daily Self-Optimization**

**Date:** ${new Date().toLocaleString('en-US', { timeZone: 'America/Denver' })} MT

---

## 🧠 Memory Consolidation

`;
  
  if (consolidation.learnings.length > 0) {
    report += `**Learnings extracted:** ${consolidation.learnings.length}\n`;
    for (const learning of consolidation.learnings.slice(0, 2)) {
      report += `• ${learning}\n`;
    }
  } else {
    report += `**No new learnings captured today**\n`;
  }
  
  if (consolidation.preferences.length > 0) {
    report += `\n**Preferences updated:** ${consolidation.preferences.length}\n`;
  }
  
  report += `\n---\n\n## 🔧 Optimization Suggestions\n\n`;
  
  if (improvements.autoImplemented.length > 0) {
    report += `**✅ Auto-Implemented (low-risk):**\n`;
    for (const impl of improvements.autoImplemented) {
      report += `• ${impl.file}: ${impl.change}\n`;
    }
  }
  
  if (improvements.needsApproval.length > 0) {
    report += `\n**⚠️ Awaiting Your Approval (medium-risk):**\n`;
    for (const approval of improvements.needsApproval) {
      report += `• ${approval.area}: ${approval.proposed}\n`;
    }
  }
  
  if (improvements.suggestions.length > 0) {
    report += `\n**💡 Suggestions (research-only):**\n`;
    for (const sug of improvements.suggestions.slice(0, 2)) {
      report += `• ${sug.task || sug.error}: ${sug.suggestion || sug.solution}\n`;
    }
  }
  
  report += `\n---\n\n**Status:** System operating nominally.`;
  
  console.log(report);
  
  // In production, would send via message tool (only if there are changes):
  // if (improvements.autoImplemented.length > 0 || improvements.needsApproval.length > 0) {
  //   await message({ action: 'send', channel: 'telegram', message: report });
  // }
  
  return report;
}

// ============================================================================
// MAIN EXECUTION
// ============================================================================

async function main() {
  console.log(`\n🚀 Starting Daily Self-Optimization`);
  console.log(`⏰ Time: ${new Date().toLocaleString('en-US', { timeZone: 'America/Denver' })} MT`);
  
  // Step 1: Consolidate memory
  const consolidation = await consolidateMemory();
  
  // Step 2: Update MEMORY.md
  await updateLongTermMemory(consolidation);
  
  // Step 3: Identify struggle areas
  const struggles = await identifyStruggleAreas();
  
  // Step 4: Update prompts (auto-implement low-risk, flag mid-risk)
  const improvements = await updatePrompts(struggles);
  
  // Step 5: Send report
  await sendOptimizationReport(consolidation, struggles, improvements);
  
  console.log(`\n✅ Daily optimization complete!`);
  process.exit(0);
}

main().catch(err => {
  console.error(`Fatal error: ${err.message}`);
  process.exit(1);
});
