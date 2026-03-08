#!/usr/bin/env node

/**
 * Content Factory - Personal Brand Stream Orchestrator
 * 
 * Manages your personal brand content pipeline:
 * - Detects triggers: manual ("Content: My framework for..."), scheduled (weekly reflection)
 * - Generates LinkedIn-first content (threads + short posts)
 * - Generates article for winzenburg.com
 * - Sends for review via email
 * 
 * Runs on:
 * - Manual trigger: Immediately via trigger-handler
 * - Scheduled: Weekly prompt "What was your biggest professional learning?"
 */

import { generateContentPackage } from './content-writing-engine.mjs';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE_DIR = path.join(__dirname, '..');
const LOG_FILE = path.join(WORKSPACE_DIR, 'logs', 'content-personal.log');

function log(message) {
  const timestamp = new Date().toISOString();
  const msg = `[${timestamp}] ${message}`;
  console.log(msg);
  fs.appendFileSync(LOG_FILE, msg + '\n');
}

// ============================================================================
// TRIGGER DETECTION
// ============================================================================

function detectPersonalBrandTrigger(message) {
  // Manual: "Content: My framework for [topic]" or "Content: Lessons from [experience]"
  const frameworkMatch = message.match(/^Content:\s+My\s+framework\s+for\s+(.+)$/i);
  if (frameworkMatch) {
    return {
      type: 'manual',
      subtype: 'framework',
      topic: frameworkMatch[1].trim(),
      priority: 'high',
    };
  }

  const lessonsMatch = message.match(/^Content:\s+Lessons?\s+(?:from|learned?)\s+(.+)$/i);
  if (lessonsMatch) {
    return {
      type: 'manual',
      subtype: 'lessons',
      topic: lessonsMatch[1].trim(),
      priority: 'high',
    };
  }

  // Scheduled: Weekly reflection
  if (message.includes('weekly reflection')) {
    return {
      type: 'scheduled',
      subtype: 'reflection',
      priority: 'medium',
    };
  }

  return null;
}

// ============================================================================
// CONTEXT EXTRACTION
// ============================================================================

function extractPersonalLearnings() {
  log(`Extracting your professional learnings...`);

  // In production, would read from your daily memory logs
  // For now, return structure for weekly prompt
  return {
    thisWeek: {
      learning: 'TBD - extracted from your daily notes',
      framework: 'TBD - how you approached this',
      outcome: 'TBD - what you learned',
    },
    expertiseAreas: [
      'Product Design',
      'Design Systems',
      'SaaS Development',
      'AI Integration',
      'Career Navigation',
    ],
  };
}

function buildPersonalContext(trigger, learnings) {
  log(`Building personal brand context for: "${trigger.topic}"`);

  const context = {
    topic: trigger.topic,
    triggerType: trigger.subtype,
    audience: 'Recruiters, hiring managers, peers in product/design/SaaS',
    goal: 'Position as thought leader to attract job + consulting + speaking opportunities',
    expertiseAreas: learnings.expertiseAreas,
    tone: 'Authentic, insightful, thought-leadership',
    destination: 'LinkedIn first, then winzenburg.com',
  };

  return context;
}

// ============================================================================
// EMAIL SUMMARY GENERATION
// ============================================================================

async function sendEmailSummary(contentSummary, trigger) {
  log(`Generating email summary for review...`);

  const emailContent = {
    to: 'ryanwinzenburg@gmail.com',
    subject: `[Personal Brand Content Draft] ${contentSummary.topic} - Ready for Review`,
    preview: `New personal brand content draft ready: ${contentSummary.topic}`,
    body: generateEmailBody(contentSummary, trigger),
  };

  // Log the email (in production, would send via Resend API)
  const emailFile = path.join(WORKSPACE_DIR, 'temp', `email-${contentSummary.slug}-${Date.now()}.json`);
  fs.writeFileSync(emailFile, JSON.stringify(emailContent, null, 2));
  log(`Email summary saved: ${emailFile}`);

  return emailContent;
}

function generateEmailBody(summary, trigger) {
  return `Hi Ryan,

Your personal brand content draft is ready for review!

---

**CONTENT PACKAGE: "${summary.topic}"**

Generated: ${summary.timestamp}
Stream: Personal Brand (LinkedIn + winzenburg.com)
Type: ${trigger.subtype}
Status: Draft (Ready for Review)

---

## What's Included

✓ Pillar Article (thought leadership piece)
✓ LinkedIn Thread (5-7 posts) - PRIMARY
✓ Twitter Thread (12-15 tweets)
✓ Email Newsletter Version
✓ YouTube Script (5-min)

---

## LinkedIn-First Strategy

This content is optimized for LinkedIn where recruiters and hiring managers are active.

**LinkedIn Delivery:**
1. Thread starts with insight hook
2. Build credibility with framework/lessons
3. End with engagement question

**Secondary Publishing:**
- Best threads → Expand into full articles on winzenburg.com
- Create permanent knowledge asset

---

## Quick Access

All files are saved here:
${summary.location}

Files:
- pillar.md (full article)
- linkedin-thread.json (primary - use this first)
- twitter-thread.json
- email-version.json
- youtube-script.json

---

## Next Steps

1. **Review LinkedIn Thread First**
   - Does it feel authentic to your voice?
   - Is the insight compelling?
   - Would this generate engagement from your target audience?

2. **Edit**: Make changes you want
   - More specific examples?
   - Different angle?
   - Better hook?

3. **Publish**: When ready, choose:
   \`\`\`
   Content: Personal [topic] PUBLISH
   \`\`\`
   
   Or just reply with approval

---

## Publishing Workflow

LinkedIn:
1. Publish thread immediately
2. Pin best-performing tweet
3. Reply to own thread with additional thoughts

winzenburg.com:
1. Schedule for next available slot (1 article/1-2 weeks)
2. I'll expand LinkedIn thread into full article
3. Add meta info, tags, cross-links

---

Questions? Reply to this email.

Mr. Pinchy
`;
}

// ============================================================================
// MAIN ORCHESTRATION
// ============================================================================

async function orchestratePersonalContent(trigger) {
  try {
    log('===== Personal Brand Content Factory Start =====');

    // Extract context
    const learnings = extractPersonalLearnings();
    const context = buildPersonalContext(trigger, learnings);

    log(`Context: ${JSON.stringify(context)}`);

    // Generate content
    const summary = await generateContentPackage(trigger.topic, context, 'personal');

    // Send email summary
    await sendEmailSummary(summary, trigger);

    log('✓ Content package generated and email summary sent');
    log('===== Personal Brand Content Factory Complete =====');

    return summary;
  } catch (error) {
    log(`✗ Fatal error: ${error.message}`);
    throw error;
  }
}

// ============================================================================
// CLI EXECUTION
// ============================================================================

if (process.argv[1] === new URL(import.meta.url).pathname) {
  const message = process.argv[2];

  if (!message) {
    console.error('Usage: node content-factory-personal.mjs "Content: My framework for [topic]"');
    process.exit(1);
  }

  const trigger = detectPersonalBrandTrigger(message);

  if (!trigger) {
    console.error('Not a personal brand content trigger');
    process.exit(1);
  }

  orchestratePersonalContent(trigger)
    .then(summary => {
      console.log('✓ Success:', summary);
      process.exit(0);
    })
    .catch(err => {
      console.error('✗ Error:', err.message);
      process.exit(1);
    });
}

export { orchestratePersonalContent };
