#!/usr/bin/env node
/**
 * revision-handler.mjs
 * 
 * Processes revision requests
 * 
 * Flow:
 * 1. User: /revise_kinlet "Needs stronger hook about personal story"
 * 2. System: Captures feedback, queues for regeneration
 * 3. System: Regenerates pillar + spokes with revised prompt
 * 4. System: Delivers revised drafts by 8:00 AM next day
 * 5. User: Reviews revised content, approves or requests more revisions
 * 
 * Can iterate multiple times until satisfied
 */

import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';
import { generate, createPillarPrompt } from './ollama-client.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE = path.resolve(__dirname, '..');

const REVISION_DIR = path.join(WORKSPACE, 'content', 'revisions-requested');
const PENDING_DIR = path.join(WORKSPACE, 'content', 'pending');

// ============================================================================
// INITIALIZATION
// ============================================================================

async function ensureFolders() {
  for (const folder of [REVISION_DIR, PENDING_DIR]) {
    await fs.mkdir(folder, { recursive: true });
  }
}

// ============================================================================
// FIND REVISION REQUEST
// ============================================================================

async function findRevisionRequest(stream) {
  try {
    const files = await fs.readdir(REVISION_DIR);
    const streamFiles = files.filter(f => f.startsWith(`${stream}_`) && f.endsWith('_revision.json'));
    
    if (streamFiles.length === 0) {
      return null;
    }
    
    // Return most recent
    const most = streamFiles.sort().pop();
    return {
      filename: most,
      path: path.join(REVISION_DIR, most),
      stream: stream
    };
  } catch (err) {
    return null;
  }
}

// ============================================================================
// REGENERATE PILLAR WITH FEEDBACK
// ============================================================================

async function regeneratePillarWithFeedback(originalContent, feedback, topic) {
  console.log(`\n🔄 Regenerating pillar with feedback: "${feedback}"`);
  
  const revisedPrompt = createPillarPrompt(topic, 'kinlet');
  const feedbackAddendum = `\n\nUser feedback for revision: ${feedback}\n\nIncorporate this feedback into your revised version.`;
  const fullPrompt = revisedPrompt + feedbackAddendum;
  
  // For hybrid approach: API for pillar revisions (better quality)
  const result = await generate('pillar-content', fullPrompt);
  
  if (!result.success) {
    throw new Error(`Pillar regeneration failed: ${result.error}`);
  }
  
  return result.text;
}

// ============================================================================
// REGENERATE SPOKES WITH FEEDBACK
// ============================================================================

async function regenerateSpokesWithFeedback(originalContent, feedback, topic) {
  console.log(`\n🔄 Regenerating spokes with feedback...`);
  
  const spokes = {
    linkedin: null,
    email: null,
    twitter: null
  };
  
  // LinkedIn
  const linkedinPrompt = `Revise this LinkedIn post based on feedback: "${feedback}"

Original: ${originalContent.linkedin.substring(0, 300)}...

Create revised version that addresses the feedback.`;
  
  const linkedinResult = await generate('spoke-repurposing', linkedinPrompt);
  if (linkedinResult.success) {
    spokes.linkedin = linkedinResult.text;
  }
  
  // Email
  const emailPrompt = `Revise this email newsletter section based on feedback: "${feedback}"

Original: ${originalContent.email.substring(0, 300)}...

Create revised version.`;
  
  const emailResult = await generate('spoke-repurposing', emailPrompt);
  if (emailResult.success) {
    spokes.email = emailResult.text;
  }
  
  // Twitter
  const twitterPrompt = `Revise this Twitter thread based on feedback: "${feedback}"

Original: ${originalContent.twitter.substring(0, 300)}...

Create revised version.`;
  
  const twitterResult = await generate('spoke-repurposing', twitterPrompt);
  if (twitterResult.success) {
    spokes.twitter = twitterResult.text;
  }
  
  return spokes;
}

// ============================================================================
// PROCESS REVISION REQUEST
// ============================================================================

async function processRevision(stream) {
  const revision = await findRevisionRequest(stream);
  
  if (!revision) {
    console.log(`❌ No revision request found for ${stream}`);
    return { success: false, error: 'No revision request found' };
  }
  
  try {
    // Read revision request
    const revisionData = JSON.parse(
      await fs.readFile(revision.path, 'utf-8')
    );
    
    const { topic, feedback, originalContent } = revisionData;
    
    console.log(`\n✏️ Processing Revision for ${stream}`);
    console.log(`Topic: ${topic}`);
    console.log(`Feedback: ${feedback}`);
    console.log(`=`.repeat(60));
    
    // Regenerate content with feedback
    let revisedPillar = originalContent.pillar;
    let revisedSpokes = originalContent.spokes;
    
    if (stream === 'kinlet') {
      revisedPillar = await regeneratePillarWithFeedback(originalContent, feedback, topic);
      revisedSpokes = await regenerateSpokesWithFeedback(originalContent, feedback, topic);
    } else if (stream === 'linkedin') {
      // For LinkedIn, regenerate all posts
      revisedSpokes = originalContent;
      // Could regenerate posts here with feedback
    }
    
    // Create revised email summary
    const timestamp = new Date().toISOString().split('T')[0];
    const revisedSummary = {
      subject: `REVISED: ${stream.toUpperCase()} Content - ${topic}`,
      preview: `Revised based on your feedback`,
      topic: topic,
      timestamp: new Date().toISOString(),
      revision: {
        feedbackApplied: feedback,
        revisedAt: new Date().toISOString(),
        revisionNumber: (revisionData.revisionNumber || 0) + 1
      },
      content: {
        pillar: stream === 'kinlet' ? {
          content: revisedPillar,
          wordCount: revisedPillar.split(/\s+/).length
        } : null,
        spokes: {
          linkedin: revisedSpokes.linkedin || originalContent.spokes.linkedin,
          email: revisedSpokes.email || originalContent.spokes.email,
          twitter: revisedSpokes.twitter || originalContent.spokes.twitter
        }
      },
      actions: {
        approve: `/approve_${stream}`,
        revise: `/revise_${stream} [additional feedback]`,
        discard: `/discard_${stream}`
      }
    };
    
    // Save revised pending content
    const revisionId = `${stream}_${timestamp}_revision${revisedSummary.revision.revisionNumber}`;
    const pendingFile = path.join(PENDING_DIR, `${revisionId}_pending.json`);
    await fs.writeFile(pendingFile, JSON.stringify(revisedSummary, null, 2), 'utf-8');
    
    // Remove old revision request
    await fs.unlink(revision.path);
    
    console.log(`\n✅ Revision regenerated and queued`);
    console.log(`📧 Will be delivered by 8:00 AM MST`);
    console.log(`📍 Pending file: ${pendingFile}`);
    
    return {
      success: true,
      revisionNumber: revisedSummary.revision.revisionNumber,
      topic: topic,
      feedback: feedback,
      pendingFile: pendingFile
    };
    
  } catch (err) {
    console.error(`❌ Revision processing failed: ${err.message}`);
    return { success: false, error: err.message };
  }
}

// ============================================================================
// MAIN HANDLER
// ============================================================================

async function main() {
  const stream = process.argv[2] || 'kinlet';
  
  await ensureFolders();
  
  const result = await processRevision(stream);
  
  console.log('\n📊 Result:');
  console.log(JSON.stringify(result, null, 2));
  
  process.exit(result.success ? 0 : 1);
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});

export { processRevision };
