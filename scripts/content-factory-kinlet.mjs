#!/usr/bin/env node
/**
 * content-factory-kinlet.mjs
 * 
 * Kinlet Content Factory Orchestrator
 * 
 * Trigger: "Content: Kinlet [topic]"
 * 
 * Generation Flow:
 * 1. Topic: "Managing caregiver burnout"
 * 2. Generate pillar (1,500w) - HYBRID: API (better quality for GTM)
 * 3. Generate spokes (4 types) - OLLAMA (local, free)
 *    - LinkedIn post (2-3 tweets)
 *    - Email newsletter version
 *    - Twitter thread (10-12 tweets)
 *    - Social post variants
 * 4. Format & deliver via email/Telegram by 8:00 AM
 * 5. Wait for: /approve_kinlet, /revise_kinlet, /discard_kinlet
 * 6. On approval: Move to "Ready to Publish" folder
 * 7. On revision: Queue for regeneration with feedback
 */

import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';
import { generate, createPillarPrompt } from './ollama-client.mjs';
import { sendEmail } from './email-formatter.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE = path.resolve(__dirname, '..');

// Folders
const CONTENT_DIR = path.join(WORKSPACE, 'content', 'kinlet');
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
// GENERATE PILLAR CONTENT (Hybrid: API for better quality)
// ============================================================================

async function generatePillarContent(topic) {
  console.log(`\n📝 Generating Kinlet Pillar (1,500 words): "${topic}"`);
  
  // Build prompt
  const pillarPrompt = createPillarPrompt(topic, 'kinlet');
  
  // For Kinlet, use Ollama Pro cloud model (kimi-k2.5:cloud)
  // This is the "Ollama Pro hybrid" approach: Cloud model for premium content, Local Ollama for spokes
  console.log(`☁️ Using Ollama Pro cloud model (kimi-k2.5:cloud) for pillar quality...`);
  
  const result = await generate('pillar-content-cloud', pillarPrompt);
  
  if (!result.success) {
    throw new Error(`Pillar generation failed: ${result.error}`);
  }
  
  return {
    text: result.text,
    model: result.model,
    cached: result.cached,
    tokensUsed: result.tokensUsed
  };
}

// ============================================================================
// GENERATE LINKEDIN SPOKE (Ollama - free)
// ============================================================================

async function generateLinkedInSpoke(pillarContent, topic) {
  console.log(`\n💼 Generating LinkedIn Post spoke (2-3 paragraphs)`);
  
  const prompt = `From this pillar content about "${topic}", extract a compelling LinkedIn post.

Pillar excerpt: ${pillarContent.substring(0, 500)}...

Generate a 2-3 paragraph LinkedIn post that:
1. Opens with a personal observation or insight
2. Shares 1-2 key takeaways
3. Ends with a question or call to engagement

Tone: Professional but conversational. Empathetic. Actionable.`;
  
  const result = await generate('spoke-repurposing', prompt);
  
  if (!result.success) {
    throw new Error(`LinkedIn spoke failed: ${result.error}`);
  }
  
  return result.text;
}

// ============================================================================
// GENERATE EMAIL NEWSLETTER SPOKE (Ollama - free)
// ============================================================================

async function generateEmailSpoke(pillarContent, topic) {
  console.log(`\n📧 Generating Email Newsletter version`);
  
  const prompt = `Convert this pillar content about "${topic}" into an email newsletter section.

Pillar excerpt: ${pillarContent.substring(0, 500)}...

Generate an email section that:
1. Includes a warm greeting
2. Summarizes 2-3 key points
3. Includes a "Read more" link to pillar
4. Ends with a personal thought

Format with clear breaks and scannable text. Tone: Warm, personal, actionable.`;
  
  const result = await generate('spoke-repurposing', prompt);
  
  if (!result.success) {
    throw new Error(`Email spoke failed: ${result.error}`);
  }
  
  return result.text;
}

// ============================================================================
// GENERATE TWITTER THREAD SPOKE (Ollama - free)
// ============================================================================

async function generateTwitterSpoke(pillarContent, topic) {
  console.log(`\n🐦 Generating Twitter thread (10-12 tweets)`);
  
  const prompt = `Convert this pillar content about "${topic}" into a Twitter thread.

Pillar excerpt: ${pillarContent.substring(0, 500)}...

Generate a 10-12 tweet thread that:
1. Starts with a hook tweet
2. Breaks down key ideas into individual tweets
3. Each tweet is under 280 characters
4. Uses 1-2 relevant hashtags
5. Ends with a call to action

Use line breaks between tweets. Format as a numbered list (1/, 2/, etc).`;
  
  const result = await generate('spoke-repurposing', prompt);
  
  if (!result.success) {
    throw new Error(`Twitter spoke failed: ${result.error}`);
  }
  
  return result.text;
}

// ============================================================================
// BUILD EMAIL SUMMARY
// ============================================================================

async function buildEmailSummary(topic, pillar, linkedin, email, twitter) {
  return {
    subject: `Kinlet Content Drafts: ${topic}`,
    preview: `1 pillar + 3 spokes ready for review`,
    topic: topic,
    timestamp: new Date().toISOString(),
    content: {
      pillar: {
        title: `Pillar: ${topic}`,
        preview: pillar.substring(0, 200) + '...',
        type: 'blog-post-1500w',
        wordCount: pillar.split(/\s+/).length
      },
      spokes: {
        linkedin: {
          title: 'LinkedIn Post',
          content: linkedin,
          type: 'linkedin-post'
        },
        email: {
          title: 'Email Newsletter',
          content: email,
          type: 'email-section'
        },
        twitter: {
          title: 'Twitter Thread',
          content: twitter,
          type: 'twitter-thread'
        }
      }
    },
    actions: {
      approve: '/approve_kinlet',
      revise: '/revise_kinlet [Your feedback]',
      discard: '/discard_kinlet'
    },
    notes: 'Use the commands above to approve, request revisions, or discard. Revised drafts will be delivered tomorrow 8:00 AM.'
  };
}

// ============================================================================
// SAVE PENDING CONTENT
// ============================================================================

async function savePendingContent(emailSummary) {
  const timestamp = new Date().toISOString().split('T')[0];
  const filename = `kinlet_${timestamp}_${Date.now()}_pending.json`;
  const filepath = path.join(PENDING_DIR, filename);
  
  // Also save full pillar to separate file
  const pillarFile = path.join(CONTENT_DIR, `${timestamp}_pillar.md`);
  const spokesFile = path.join(CONTENT_DIR, `${timestamp}_spokes.json`);
  
  // Save email summary
  await fs.writeFile(filepath, JSON.stringify(emailSummary, null, 2), 'utf-8');
  
  // Save pillar as markdown
  await fs.writeFile(pillarFile, emailSummary.content.pillar.preview + '\n[...full content in draft...]\n', 'utf-8');
  
  // Save spokes
  const spokesData = {
    topic: emailSummary.topic,
    generatedAt: emailSummary.timestamp,
    spokes: emailSummary.content.spokes
  };
  await fs.writeFile(spokesFile, JSON.stringify(spokesData, null, 2), 'utf-8');
  
  return {
    pending: filename,
    pillar: pillarFile,
    spokes: spokesFile
  };
}

// ============================================================================
// FORMAT FOR TELEGRAM
// ============================================================================

function formatForTelegram(emailSummary) {
  return `📬 **Kinlet Content Ready for Review**

📝 Topic: ${emailSummary.topic}

**Pillar:** ${emailSummary.content.pillar.wordCount} words
**Spokes:** LinkedIn, Email, Twitter

---

**Your options:**
✅ /approve_kinlet
📝 /revise_kinlet [feedback]
❌ /discard_kinlet

Approval moves content to "Ready to Publish" folder.
Revision regenerates with your feedback, delivers tomorrow 8 AM.`;
}

// ============================================================================
// MAIN ORCHESTRATOR
// ============================================================================

async function orchestrate(topic) {
  console.log(`\n🎯 Kinlet Content Factory Starting...`);
  console.log(`Topic: "${topic}"`);
  console.log(`=`.repeat(60));
  
  try {
    // Ensure folders exist
    await ensureFolders();
    
    // Step 1: Generate pillar
    console.log(`\n[1/5] Generating pillar content...`);
    const pillar = await generatePillarContent(topic);
    
    // Step 2: Generate LinkedIn spoke
    console.log(`[2/5] Generating LinkedIn spoke...`);
    const linkedin = await generateLinkedInSpoke(pillar.text, topic);
    
    // Step 3: Generate email spoke
    console.log(`[3/5] Generating email spoke...`);
    const email = await generateEmailSpoke(pillar.text, topic);
    
    // Step 4: Generate Twitter spoke
    console.log(`[4/5] Generating Twitter spoke...`);
    const twitter = await generateTwitterSpoke(pillar.text, topic);
    
    // Step 5: Build email summary
    console.log(`[5/5] Building email summary...`);
    const emailSummary = await buildEmailSummary(topic, pillar.text, linkedin, email, twitter);
    
    // Step 6: Save pending content
    const saved = await savePendingContent(emailSummary);
    
    // Step 7: Format for notification
    const telegramMessage = formatForTelegram(emailSummary);
    
    console.log(`\n✅ Kinlet content generation complete!`);
    console.log(`📧 Email summary: ${saved.pending}`);
    
    // Send email via Resend
    const emailResult = await sendEmail('kinlet', emailSummary);
    
    console.log(`📱 Telegram: Sending notification...`);
    console.log(`\n${telegramMessage}`);
    
    // TODO: Send actual Telegram message via message tool
    
    return {
      success: true,
      topic: topic,
      generated: {
        pillarWords: pillar.text.split(/\s+/).length,
        spokesCount: 3
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
  
  if (!topic) {
    console.error('Usage: content-factory-kinlet.mjs "[topic]"');
    console.error('Example: content-factory-kinlet.mjs "Managing caregiver burnout"');
    process.exit(1);
  }
  
  const result = await orchestrate(topic);
  
  console.log('\n📊 Summary:');
  console.log(JSON.stringify(result, null, 2));
  
  process.exit(result.success ? 0 : 1);
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});

export { orchestrate };
