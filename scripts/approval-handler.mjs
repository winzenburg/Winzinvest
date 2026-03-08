#!/usr/bin/env node
/**
 * approval-handler.mjs
 * 
 * Processes content approvals, revisions, and discards
 * Listens to:
 * - Telegram commands: /approve_kinlet, /revise_kinlet, /discard_kinlet
 * - Email keywords: APPROVE KINLET, REVISE KINLET, DISCARD KINLET
 * 
 * Workflow:
 * 1. Capture approval action (approve/revise/discard)
 * 2. Move content to appropriate folder
 * 3. If revise: add to revision queue, regenerate, deliver next 8 AM
 * 4. If approve: move to "Ready to Publish" folder with manifest
 * 5. If discard: remove from tracking
 */

import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';
import minimist from 'minimist';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE = path.resolve(__dirname, '..');

// Folders
const PENDING_FOLDER = path.join(WORKSPACE, 'content', 'pending');
const READY_FOLDER = path.join(WORKSPACE, 'content', 'ready-to-publish');
const REVISION_FOLDER = path.join(WORKSPACE, 'content', 'revisions-requested');
const DISCARDED_FOLDER = path.join(WORKSPACE, 'content', 'discarded');
const STATE_FILE = path.join(WORKSPACE, 'content', '.approval-state.json');

// ============================================================================
// INITIALIZATION
// ============================================================================

async function ensureFolders() {
  for (const folder of [PENDING_FOLDER, READY_FOLDER, REVISION_FOLDER, DISCARDED_FOLDER]) {
    await fs.mkdir(folder, { recursive: true });
  }
}

async function loadState() {
  try {
    const data = await fs.readFile(STATE_FILE, 'utf-8');
    return JSON.parse(data);
  } catch (err) {
    return {
      pending: {},
      approved: {},
      revisions: {},
      discarded: {}
    };
  }
}

async function saveState(state) {
  await fs.writeFile(STATE_FILE, JSON.stringify(state, null, 2), 'utf-8');
}

// ============================================================================
// FIND PENDING CONTENT
// ============================================================================

async function findPendingContent(stream) {
  try {
    const files = await fs.readdir(PENDING_FOLDER);
    const streamFiles = files.filter(f => f.startsWith(`${stream}_`));
    
    if (streamFiles.length === 0) {
      return null;
    }
    
    // Return most recent
    const most = streamFiles.sort().pop();
    return {
      filename: most,
      path: path.join(PENDING_FOLDER, most),
      stream: stream
    };
  } catch (err) {
    return null;
  }
}

// ============================================================================
// APPROVE: Move to Ready to Publish
// ============================================================================

async function handleApprove(stream) {
  const content = await findPendingContent(stream);
  
  if (!content) {
    console.log(`❌ No pending ${stream} content found to approve`);
    return { success: false, error: 'No pending content' };
  }
  
  try {
    // Read content
    const contentData = JSON.parse(await fs.readFile(content.path, 'utf-8'));
    
    // Move to ready folder
    const timestamp = new Date().toISOString().split('T')[0];
    const readyFile = path.join(READY_FOLDER, `${stream}_${timestamp}_ready.json`);
    await fs.writeFile(readyFile, JSON.stringify(contentData, null, 2), 'utf-8');
    
    // Create publishing manifest
    const manifest = {
      stream: stream,
      approvedAt: new Date().toISOString(),
      content: {
        pillar: contentData.pillar ? 'Pillar content ready (1,500 words)' : null,
        spokes: Object.keys(contentData.spokes || {})
      },
      publishingSteps: generatePublishingSteps(stream),
      files: {
        manifest: readyFile,
        pillar: contentData.pillarFile || null,
        spokes: contentData.spokesFiles || {}
      }
    };
    
    const manifestFile = path.join(READY_FOLDER, `${stream}_${timestamp}_manifest.json`);
    await fs.writeFile(manifestFile, JSON.stringify(manifest, null, 2), 'utf-8');
    
    // Remove from pending
    await fs.unlink(content.path);
    
    // Update state
    const state = await loadState();
    state.approved[`${stream}_${timestamp}`] = {
      approvedAt: new Date().toISOString(),
      files: [readyFile, manifestFile]
    };
    await saveState(state);
    
    console.log(`✅ ${stream.toUpperCase()} content approved and queued for publishing`);
    console.log(`📍 Location: ${readyFile}`);
    console.log(`📋 Manifest: ${manifestFile}`);
    
    return {
      success: true,
      manifestFile: manifestFile,
      readyFile: readyFile
    };
    
  } catch (err) {
    console.error(`❌ Approve failed: ${err.message}`);
    return { success: false, error: err.message };
  }
}

// ============================================================================
// REVISE: Queue for Regeneration
// ============================================================================

async function handleRevise(stream, feedback) {
  const content = await findPendingContent(stream);
  
  if (!content) {
    console.log(`❌ No pending ${stream} content found to revise`);
    return { success: false, error: 'No pending content' };
  }
  
  try {
    // Read content
    const contentData = JSON.parse(await fs.readFile(content.path, 'utf-8'));
    
    // Create revision record
    const timestamp = new Date().toISOString();
    const revisionRecord = {
      stream: stream,
      requestedAt: timestamp,
      feedback: feedback,
      originalContent: contentData,
      topic: contentData.topic,
      regenerateBy: '08:00 MST next morning'
    };
    
    // Save revision request
    const revisionFile = path.join(REVISION_FOLDER, `${stream}_${Date.now()}_revision.json`);
    await fs.writeFile(revisionFile, JSON.stringify(revisionRecord, null, 2), 'utf-8');
    
    // Add to state
    const state = await loadState();
    if (!state.revisions[stream]) {
      state.revisions[stream] = [];
    }
    state.revisions[stream].push({
      revisionFile: revisionFile,
      feedback: feedback,
      requestedAt: timestamp,
      status: 'pending-regeneration'
    });
    await saveState(state);
    
    // Remove from pending (will be regenerated)
    await fs.unlink(content.path);
    
    console.log(`✅ Revision recorded: "${feedback}"`);
    console.log(`🔄 Content will be regenerated and delivered by 8:00 AM MST`);
    console.log(`📍 Revision file: ${revisionFile}`);
    
    return {
      success: true,
      revisionFile: revisionFile,
      feedback: feedback
    };
    
  } catch (err) {
    console.error(`❌ Revise failed: ${err.message}`);
    return { success: false, error: err.message };
  }
}

// ============================================================================
// DISCARD: Remove Content
// ============================================================================

async function handleDiscard(stream) {
  const content = await findPendingContent(stream);
  
  if (!content) {
    console.log(`❌ No pending ${stream} content found to discard`);
    return { success: false, error: 'No pending content' };
  }
  
  try {
    // Read content before discarding
    const contentData = JSON.parse(await fs.readFile(content.path, 'utf-8'));
    
    // Create discard record
    const timestamp = new Date().toISOString();
    const discardRecord = {
      stream: stream,
      discardedAt: timestamp,
      content: contentData,
      reason: 'User discard'
    };
    
    // Move to discarded folder
    const discardedFile = path.join(DISCARDED_FOLDER, `${stream}_${Date.now()}_discarded.json`);
    await fs.writeFile(discardedFile, JSON.stringify(discardRecord, null, 2), 'utf-8');
    
    // Update state
    const state = await loadState();
    if (!state.discarded[stream]) {
      state.discarded[stream] = [];
    }
    state.discarded[stream].push({
      discardedFile: discardedFile,
      discardedAt: timestamp
    });
    await saveState(state);
    
    // Remove from pending
    await fs.unlink(content.path);
    
    console.log(`✅ ${stream.toUpperCase()} content discarded`);
    console.log(`📍 Archived at: ${discardedFile}`);
    
    return {
      success: true,
      discardedFile: discardedFile
    };
    
  } catch (err) {
    console.error(`❌ Discard failed: ${err.message}`);
    return { success: false, error: err.message };
  }
}

// ============================================================================
// GENERATE PUBLISHING STEPS
// ============================================================================

function generatePublishingSteps(stream) {
  const steps = {
    kinlet: [
      '1. Copy pillar post to Kinlet.com blog editor',
      '2. Add featured image (1200x630px)',
      '3. Add internal links to related posts',
      '4. Schedule publish (or publish immediately)',
      '5. Share pillar link on Kinlet LinkedIn',
      '6. Deploy email newsletter version'
    ],
    linkedin: [
      '1. Open LinkedIn in a new tab',
      '2. For each post: Copy text, paste, post individually',
      '3. Space posts throughout the week (Mon-Fri if possible)',
      '4. Pin top-performing post for week',
      '5. Engage with comments (if any)'
    ]
  };
  
  return steps[stream] || [];
}

// ============================================================================
// MAIN HANDLER
// ============================================================================

async function main() {
  const args = minimist(process.argv.slice(2));
  
  const stream = args.stream || args.s;
  const action = args.action || args.a;
  const feedback = args.feedback || args.f || null;
  
  if (!stream || !action) {
    console.error('Usage: approval-handler.mjs --stream kinlet|linkedin --action approve|revise|discard [--feedback "text"]');
    process.exit(1);
  }
  
  // Ensure folders exist
  await ensureFolders();
  
  // Execute action
  let result;
  switch (action.toLowerCase()) {
    case 'approve':
      result = await handleApprove(stream);
      break;
    case 'revise':
      if (!feedback) {
        console.error('❌ Revision requires feedback: --feedback "your feedback"');
        process.exit(1);
      }
      result = await handleRevise(stream, feedback);
      break;
    case 'discard':
      result = await handleDiscard(stream);
      break;
    default:
      console.error(`❌ Unknown action: ${action}`);
      process.exit(1);
  }
  
  process.exit(result.success ? 0 : 1);
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});

export { handleApprove, handleRevise, handleDiscard };
