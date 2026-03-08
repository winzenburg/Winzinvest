#!/usr/bin/env node
/**
 * content-factory-linkedin.mjs
 * 
 * LinkedIn Content Factory Orchestrator
 * 
 * Trigger: "Content: LinkedIn [topic]" or scheduled Monday 7:00 AM
 * 
 * Generation Flow:
 * 1. Generate 2-3 independent posts for the week
 * 2. All posts are generated at once (batch)
 * 3. Format & deliver via email by 8:00 AM Monday
 * 4. Wait for: /approve_linkedin, /revise_linkedin, /discard_linkedin
 * 5. User can approve all at once or revise individual posts
 * 6. On approval: Move to "Ready to Publish" folder
 * 7. Publishing: User copies posts to LinkedIn throughout week
 * 
 * Note: All generation uses Ollama (no API needed for personal brand)
 */

import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';
import { generate } from './ollama-client.mjs';
import { sendEmail } from './email-formatter.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE = path.resolve(__dirname, '..');

// Folders
const CONTENT_DIR = path.join(WORKSPACE, 'content', 'linkedin');
const PENDING_DIR = path.join(WORKSPACE, 'content', 'pending');

// ============================================================================
// INITIALIZATION
// ============================================================================

async function ensureFolders() {
  for (const folder of [CONTENT_DIR, PENDING_DIR]) {
    await fs.mkdir(folder, { recursive: true });
  }
}

// ============================================================================
// GENERATE INDIVIDUAL LINKEDIN POST
// ============================================================================

async function generateLinkedInPost(topic, postNumber, totalPosts) {
  console.log(`\n💼 Generating LinkedIn Post ${postNumber}/${totalPosts}: "${topic}"`);
  
  const angles = [
    'Start with a surprising insight or contrarian take',
    'Open with a personal story or learning',
    'Share a framework or mental model',
    'Ask a thought-provoking question'
  ];
  
  const angle = angles[postNumber - 1] || angles[0];
  
  const prompt = `Create an independent LinkedIn post on the topic: "${topic}"

Approach: ${angle}

Requirements:
- 2-4 paragraphs (LinkedIn sweet spot)
- Conversational, authentic tone
- Include 1-2 specific examples or insights
- End with a question to spark engagement
- Include relevant hashtags (3-5)
- Under 500 words

This is POST ${postNumber} of ${totalPosts} for the week. Make it distinct and valuable.`;
  
  const result = await generate('spoke-repurposing', prompt);
  
  if (!result.success) {
    throw new Error(`Post ${postNumber} generation failed: ${result.error}`);
  }
  
  return {
    postNumber: postNumber,
    content: result.text,
    model: result.model,
    wordCount: result.text.split(/\s+/).length
  };
}

// ============================================================================
// GENERATE WEEKLY BATCH (2-3 posts)
// ============================================================================

async function generateWeeklyBatch(topic, count = 3) {
  console.log(`\n📅 Generating Weekly Batch: ${count} posts for "${topic}"`);
  console.log(`=`.repeat(60));
  
  const posts = [];
  
  for (let i = 1; i <= count; i++) {
    try {
      const post = await generateLinkedInPost(topic, i, count);
      posts.push(post);
    } catch (err) {
      console.error(`Failed to generate post ${i}: ${err.message}`);
      throw err;
    }
  }
  
  return posts;
}

// ============================================================================
// BUILD EMAIL SUMMARY
// ============================================================================

async function buildEmailSummary(topic, posts) {
  return {
    subject: `LinkedIn Posts for the Week: ${topic}`,
    preview: `${posts.length} posts ready for review`,
    topic: topic,
    timestamp: new Date().toISOString(),
    batch: {
      type: 'weekly-batch',
      count: posts.length,
      postCount: posts.length
    },
    content: {
      posts: posts.map((post, idx) => ({
        number: post.postNumber,
        preview: post.content.substring(0, 150) + '...',
        wordCount: post.wordCount,
        content: post.content
      }))
    },
    actions: {
      approveAll: '/approve_linkedin',
      revisePost: '/revise_linkedin [post number] [feedback]',
      discard: '/discard_linkedin'
    },
    publishingNotes: [
      'These posts are ready to publish throughout the week',
      'You can post them Monday-Friday for optimal engagement',
      'Space them out (1 post every 1-2 days)',
      'Pin the best-performing post on Friday'
    ],
    notes: 'Use the commands above to approve, request revisions, or discard. Revised posts will be delivered by 8:00 AM next day.'
  };
}

// ============================================================================
// SAVE PENDING CONTENT
// ============================================================================

async function savePendingContent(emailSummary) {
  const timestamp = new Date().toISOString().split('T')[0];
  const batchId = `linkedin_${timestamp}_${Date.now()}`;
  const filename = `${batchId}_pending.json`;
  const filepath = path.join(PENDING_DIR, filename);
  
  // Save pending email summary
  await fs.writeFile(filepath, JSON.stringify(emailSummary, null, 2), 'utf-8');
  
  // Save individual posts to content folder
  const postsFile = path.join(CONTENT_DIR, `${batchId}_posts.json`);
  await fs.writeFile(postsFile, JSON.stringify(emailSummary.content, null, 2), 'utf-8');
  
  return {
    batchId: batchId,
    pending: filename,
    posts: postsFile
  };
}

// ============================================================================
// FORMAT FOR TELEGRAM
// ============================================================================

function formatForTelegram(emailSummary) {
  let message = `📬 **LinkedIn Posts Ready for Review**\n\n`;
  message += `📅 Topic: ${emailSummary.topic}\n`;
  message += `📊 Posts: ${emailSummary.batch.count} (${emailSummary.content.posts.reduce((sum, p) => sum + p.wordCount, 0)} words total)\n\n`;
  
  for (const post of emailSummary.content.posts) {
    message += `**Post ${post.number}:** ${post.wordCount} words\n`;
    message += `${post.preview}\n\n`;
  }
  
  message += `---\n\n`;
  message += `**Your options:**\n`;
  message += `✅ /approve_linkedin (approve all posts)\n`;
  message += `📝 /revise_linkedin [feedback] (revise all or specific)\n`;
  message += `❌ /discard_linkedin\n\n`;
  message += `Approval moves content to "Ready to Publish" folder.\n`;
  message += `Publishing: You copy posts to LinkedIn throughout the week.`;
  
  return message;
}

// ============================================================================
// MAIN ORCHESTRATOR
// ============================================================================

async function orchestrate(topic, postCount = 3) {
  console.log(`\n💼 LinkedIn Content Factory Starting...`);
  console.log(`Topic: "${topic}" | Posts: ${postCount}`);
  console.log(`=`.repeat(60));
  
  try {
    // Ensure folders exist
    await ensureFolders();
    
    // Step 1: Generate weekly batch
    console.log(`\n[1/4] Generating ${postCount} posts...`);
    const posts = await generateWeeklyBatch(topic, postCount);
    
    // Step 2: Build email summary
    console.log(`[2/4] Building email summary...`);
    const emailSummary = await buildEmailSummary(topic, posts);
    
    // Step 3: Save pending content
    console.log(`[3/4] Saving pending content...`);
    const saved = await savePendingContent(emailSummary);
    
    // Step 4: Format for notification
    console.log(`[4/4] Formatting notification...`);
    const telegramMessage = formatForTelegram(emailSummary);
    
    console.log(`\n✅ LinkedIn content generation complete!`);
    console.log(`📧 Email summary: ${saved.pending}`);
    
    // Send email via Resend
    const emailResult = await sendEmail('linkedin', emailSummary);
    
    console.log(`📱 Telegram: Sending notification...`);
    console.log(`\n${telegramMessage}`);
    
    // TODO: Send actual Telegram message via message tool
    
    return {
      success: true,
      topic: topic,
      batchId: saved.batchId,
      generated: {
        postsCount: posts.length,
        totalWords: posts.reduce((sum, p) => sum + p.wordCount, 0),
        avgWordsPerPost: Math.round(posts.reduce((sum, p) => sum + p.wordCount, 0) / posts.length)
      },
      files: saved,
      emailSummary: emailSummary,
      emailDelivery: {
        success: emailResult.success,
        messageId: emailResult.messageId,
        error: emailResult.error,
      }
    };
    
  } catch (err) {
    console.error(`\n❌ Error: ${err.message}`);
    return {
      success: false,
      error: err.message
    };
  }
}

// ============================================================================
// CLI EXECUTION
// ============================================================================

async function main() {
  const topic = process.argv[2];
  const postCount = parseInt(process.argv[3] || '3', 10);
  
  if (!topic) {
    console.error('Usage: content-factory-linkedin.mjs "[topic]" [postCount=3]');
    console.error('Example: content-factory-linkedin.mjs "Building design systems" 3');
    process.exit(1);
  }
  
  const result = await orchestrate(topic, postCount);
  
  console.log('\n📊 Summary:');
  console.log(JSON.stringify(result, null, 2));
  
  process.exit(result.success ? 0 : 1);
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});

export { orchestrate };
