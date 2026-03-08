#!/usr/bin/env node
/**
 * research-suggestion.mjs
 * 
 * Manages research suggestions
 * 
 * Flow:
 * 1. Research completes: "3 pain points in caregiver burnout"
 * 2. System suggests: "Create Kinlet post about caregiver burnout?"
 * 3. User decision: /create_kinlet_from_research OR /ignore
 * 4. If create: Adds to generation queue, delivers pillar + spokes by 8 AM
 * 5. If ignore: Removes suggestion, logs for analytics
 * 
 * Keeps user in control while automating the happy path
 */

import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE = path.resolve(__dirname, '..');

const RESEARCH_DIR = path.join(WORKSPACE, 'research');
const SUGGESTION_DIR = path.join(WORKSPACE, 'content', 'research-suggestions');
const PENDING_DIR = path.join(WORKSPACE, 'content', 'pending');

// ============================================================================
// INITIALIZATION
// ============================================================================

async function ensureFolders() {
  for (const folder of [RESEARCH_DIR, SUGGESTION_DIR, PENDING_DIR]) {
    await fs.mkdir(folder, { recursive: true });
  }
}

// ============================================================================
// FIND LATEST RESEARCH
// ============================================================================

async function findLatestResearch() {
  try {
    const files = await fs.readdir(RESEARCH_DIR);
    const mdFiles = files.filter(f => f.endsWith('.md')).sort();
    
    if (mdFiles.length === 0) {
      return null;
    }
    
    const latestFile = mdFiles.pop();
    const content = await fs.readFile(path.join(RESEARCH_DIR, latestFile), 'utf-8');
    
    return {
      filename: latestFile,
      path: path.join(RESEARCH_DIR, latestFile),
      content: content
    };
  } catch (err) {
    return null;
  }
}

// ============================================================================
// EXTRACT SUGGESTION FROM RESEARCH
// ============================================================================

function extractSuggestion(research) {
  // Parse research brief to find opportunity statement
  const opportunityMatch = research.content.match(
    /Opportunity[^:]*:\s*(.+?)(?:\n|$)/i
  );
  
  const opportunity = opportunityMatch ? opportunityMatch[1].trim() : null;
  
  // Extract key pain points
  const painPointMatch = research.content.match(
    /Pain Point[s]*:?\s*([\s\S]+?)(?=\n\n|\n#{1,2}|$)/i
  );
  
  const painPoints = painPointMatch ? painPointMatch[1].trim().split('\n').slice(0, 3) : [];
  
  return {
    topic: research.filename.replace(/[_\-]/g, ' ').replace('.md', ''),
    opportunity: opportunity,
    painPoints: painPoints,
    researchFile: research.filename
  };
}

// ============================================================================
// CREATE SUGGESTION CARD
// ============================================================================

function createSuggestionCard(suggestion) {
  return {
    id: `${Date.now()}`,
    timestamp: new Date().toISOString(),
    research: {
      topic: suggestion.topic,
      file: suggestion.researchFile,
      opportunity: suggestion.opportunity
    },
    suggestion: {
      action: 'Create Kinlet content',
      topic: suggestion.topic,
      painPoints: suggestion.painPoints
    },
    status: 'pending-user-decision',
    userOptions: {
      create: '/create_kinlet_from_research',
      ignore: '/ignore'
    }
  };
}

// ============================================================================
// PRESENT SUGGESTION
// ============================================================================

async function presentSuggestion() {
  try {
    await ensureFolders();
    
    // Find latest research
    const research = await findLatestResearch();
    if (!research) {
      console.log('❌ No research found');
      return { success: false, error: 'No research found' };
    }
    
    // Extract suggestion
    const suggestion = extractSuggestion(research);
    
    // Create suggestion card
    const card = createSuggestionCard(suggestion);
    
    // Save suggestion
    const suggestionFile = path.join(SUGGESTION_DIR, `${card.id}_suggestion.json`);
    await fs.writeFile(suggestionFile, JSON.stringify(card, null, 2), 'utf-8');
    
    console.log(`\n💡 Research Suggestion Created`);
    console.log(`Topic: ${suggestion.topic}`);
    console.log(`Opportunity: ${suggestion.opportunity}`);
    console.log(`\n📋 Pain Points:`);
    suggestion.painPoints.forEach(point => {
      console.log(`  • ${point.trim()}`);
    });
    
    console.log(`\n🤔 Your options:`);
    console.log(`  ✅ /create_kinlet_from_research`);
    console.log(`  ⏭️ /ignore`);
    
    return {
      success: true,
      card: card,
      suggestionFile: suggestionFile
    };
    
  } catch (err) {
    console.error(`Error presenting suggestion: ${err.message}`);
    return { success: false, error: err.message };
  }
}

// ============================================================================
// CREATE CONTENT FROM SUGGESTION
// ============================================================================

async function createFromSuggestion(suggestionId = null) {
  try {
    await ensureFolders();
    
    // Find suggestion
    let suggestion = null;
    
    if (suggestionId) {
      const suggestionFile = path.join(SUGGESTION_DIR, `${suggestionId}_suggestion.json`);
      suggestion = JSON.parse(await fs.readFile(suggestionFile, 'utf-8'));
    } else {
      // Find most recent
      const files = await fs.readdir(SUGGESTION_DIR);
      const suggestionFiles = files.filter(f => f.endsWith('_suggestion.json')).sort();
      if (suggestionFiles.length === 0) {
        return { success: false, error: 'No suggestions found' };
      }
      const latest = suggestionFiles.pop();
      suggestion = JSON.parse(
        await fs.readFile(path.join(SUGGESTION_DIR, latest), 'utf-8')
      );
    }
    
    console.log(`\n✅ Creating Kinlet content from research suggestion`);
    console.log(`Topic: ${suggestion.research.topic}`);
    console.log(`Research file: ${suggestion.research.file}`);
    console.log(`\n🎯 This will queue generation for 8:00 AM delivery`);
    
    // Create generation task
    const task = {
      type: 'content-generation',
      stream: 'kinlet',
      topic: suggestion.research.topic,
      sourceResearch: suggestion.research.file,
      queuedAt: new Date().toISOString(),
      status: 'pending-generation'
    };
    
    // Save task to generation queue
    const taskFile = path.join(PENDING_DIR, `${Date.now()}_kinlet_from_research.json`);
    await fs.writeFile(taskFile, JSON.stringify(task, null, 2), 'utf-8');
    
    // Mark suggestion as accepted
    suggestion.status = 'accepted-for-generation';
    suggestion.acceptedAt = new Date().toISOString();
    const suggestionFile = path.join(SUGGESTION_DIR, `${suggestion.id}_suggestion.json`);
    await fs.writeFile(suggestionFile, JSON.stringify(suggestion, null, 2), 'utf-8');
    
    console.log(`📧 Content queued for generation`);
    console.log(`⏰ Delivery: 8:00 AM MST tomorrow`);
    
    return {
      success: true,
      task: task,
      taskFile: taskFile,
      topic: suggestion.research.topic
    };
    
  } catch (err) {
    console.error(`Error creating from suggestion: ${err.message}`);
    return { success: false, error: err.message };
  }
}

// ============================================================================
// IGNORE SUGGESTION
// ============================================================================

async function ignoreSuggestion(suggestionId = null) {
  try {
    await ensureFolders();
    
    // Find suggestion
    let suggestion = null;
    let suggestionFile = null;
    
    if (suggestionId) {
      suggestionFile = path.join(SUGGESTION_DIR, `${suggestionId}_suggestion.json`);
      suggestion = JSON.parse(await fs.readFile(suggestionFile, 'utf-8'));
    } else {
      // Find most recent
      const files = await fs.readdir(SUGGESTION_DIR);
      const suggestionFiles = files.filter(f => f.endsWith('_suggestion.json')).sort();
      if (suggestionFiles.length === 0) {
        return { success: false, error: 'No suggestions found' };
      }
      const latest = suggestionFiles.pop();
      suggestionFile = path.join(SUGGESTION_DIR, latest);
      suggestion = JSON.parse(await fs.readFile(suggestionFile, 'utf-8'));
    }
    
    // Mark as ignored
    suggestion.status = 'ignored-by-user';
    suggestion.ignoredAt = new Date().toISOString();
    
    // Save updated suggestion
    await fs.writeFile(suggestionFile, JSON.stringify(suggestion, null, 2), 'utf-8');
    
    console.log(`✅ Suggestion ignored: ${suggestion.research.topic}`);
    
    return {
      success: true,
      topic: suggestion.research.topic,
      status: 'ignored'
    };
    
  } catch (err) {
    console.error(`Error ignoring suggestion: ${err.message}`);
    return { success: false, error: err.message };
  }
}

// ============================================================================
// MAIN HANDLER
// ============================================================================

async function main() {
  const action = process.argv[2] || 'present';
  const id = process.argv[3] || null;
  
  let result;
  
  switch (action) {
    case 'present':
      result = await presentSuggestion();
      break;
    case 'create':
      result = await createFromSuggestion(id);
      break;
    case 'ignore':
      result = await ignoreSuggestion(id);
      break;
    default:
      console.error(`Unknown action: ${action}`);
      process.exit(1);
  }
  
  console.log('\n📊 Result:');
  console.log(JSON.stringify(result, null, 2));
  
  process.exit(result.success ? 0 : 1);
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});

export { presentSuggestion, createFromSuggestion, ignoreSuggestion };
