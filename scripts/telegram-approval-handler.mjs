#!/usr/bin/env node
/**
 * telegram-approval-handler.mjs
 * 
 * Telegram command handler for content approvals
 * 
 * Commands:
 * - /approve_kinlet → Move to ready-to-publish + send confirmation with deep link
 * - /approve_linkedin → Move to ready-to-publish + send confirmation
 * - /revise_kinlet [feedback] → Add revision request + queue regeneration
 * - /discard_kinlet → Remove from approval queue
 * 
 * Automatically marks publishedAt when publishing is confirmed
 */

import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE = path.resolve(__dirname, '..');

// Folders
const PENDING_DIR = path.join(WORKSPACE, 'content', 'pending');
const READY_DIR = path.join(WORKSPACE, 'content', 'ready-to-publish');
const REVISION_DIR = path.join(WORKSPACE, 'content', 'revisions-requested');

// Telegram API
const TELEGRAM_API = 'https://api.telegram.org/bot';
const USER_ID = process.env.TELEGRAM_USER_ID || '5316436116';

// ============================================================================
// TELEGRAM MESSAGE SENDER
// ============================================================================

async function sendTelegramMessage(botToken, chatId, message, parseMode = 'Markdown') {
  try {
    const url = `${TELEGRAM_API}${botToken}/sendMessage`;
    
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        chat_id: chatId,
        text: message,
        parse_mode: parseMode,
        disable_web_page_preview: 'true',
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    if (!data.ok) {
      throw new Error(data.description || 'Unknown error');
    }

    return true;
  } catch (err) {
    console.error(`[TELEGRAM] Error sending message: ${err.message}`);
    return false;
  }
}

// ============================================================================
// FIND PENDING CONTENT
// ============================================================================

async function findPendingContent(stream) {
  try {
    const files = await fs.readdir(PENDING_DIR);
    const streamFiles = files.filter(f => f.startsWith(`${stream}_`) && f.endsWith('_pending.json'));
    
    if (streamFiles.length === 0) {
      return null;
    }

    const most = streamFiles.sort().pop();
    return {
      filename: most,
      path: path.join(PENDING_DIR, most),
      stream: stream,
    };
  } catch (err) {
    return null;
  }
}

// ============================================================================
// APPROVE HANDLER
// ============================================================================

async function handleApprove(stream, botToken) {
  const content = await findPendingContent(stream);

  if (!content) {
    await sendTelegramMessage(
      botToken,
      USER_ID,
      `❌ No pending ${stream} content found to approve.`
    );
    return;
  }

  try {
    // Read content
    const contentData = JSON.parse(await fs.readFile(content.path, 'utf-8'));

    // Move to ready folder
    const timestamp = new Date().toISOString().split('T')[0];
    const readyFile = path.join(READY_DIR, `${stream}_${timestamp}_ready.json`);
    const manifestFile = path.join(READY_DIR, `${stream}_${timestamp}_manifest.json`);

    await fs.writeFile(readyFile, JSON.stringify(contentData, null, 2), 'utf-8');

    // Create manifest with deep link
    const manifest = {
      id: `${stream}-${timestamp}`,
      stream: stream,
      topic: contentData.topic,
      approvedAt: new Date().toISOString(),
      status: 'approved',
      readyToPublishPath: readyFile,
      deepLink: `file://${readyFile}`,
      publishingSteps: generatePublishingSteps(stream),
    };

    await fs.writeFile(manifestFile, JSON.stringify(manifest, null, 2), 'utf-8');

    // Remove from pending
    await fs.unlink(content.path);

    // Send Telegram confirmation with deep link
    const message = `
✅ **${stream.toUpperCase()} Content Approved**

📝 **Topic:** ${contentData.topic}
📅 **Approved:** ${new Date().toLocaleString('en-US', { timeZone: 'America/Denver' })}

📂 **Ready to Publish:**
[\`${stream.toUpperCase()}\`](file://${readyFile})

**Next Steps:**
1. Open folder (link above)
2. Review content files
3. Publish to platform
4. Reply: \`/publish_${stream}_${timestamp}\` when done

**Publishing Steps:**
${manifest.publishingSteps.map((s, i) => `${i + 1}. ${s}`).join('\n')}
    `.trim();

    await sendTelegramMessage(botToken, USER_ID, message);

    console.log(`✅ ${stream.toUpperCase()} content approved and queued`);
  } catch (err) {
    console.error(`Error approving content: ${err.message}`);
    await sendTelegramMessage(botToken, USER_ID, `❌ Error approving content: ${err.message}`);
  }
}

// ============================================================================
// REVISE HANDLER
// ============================================================================

async function handleRevise(stream, feedback, botToken) {
  const content = await findPendingContent(stream);

  if (!content) {
    await sendTelegramMessage(botToken, USER_ID, `❌ No pending ${stream} content found to revise.`);
    return;
  }

  try {
    // Read content
    const contentData = JSON.parse(await fs.readFile(content.path, 'utf-8'));

    // Create revision record
    const revisionRecord = {
      stream: stream,
      topic: contentData.topic,
      requestedAt: new Date().toISOString(),
      feedback: feedback,
      originalContent: contentData,
      status: 'pending-regeneration',
    };

    const revisionFile = path.join(REVISION_DIR, `${stream}_${Date.now()}_revision.json`);
    await fs.writeFile(revisionFile, JSON.stringify(revisionRecord, null, 2), 'utf-8');

    // Remove from pending
    await fs.unlink(content.path);

    const message = `
📝 **${stream.toUpperCase()} Revision Queued**

**Feedback:** "${feedback}"

⏰ **New drafts will be ready by 8:00 AM MST tomorrow**

You'll receive a new approval request with the revised content.
    `.trim();

    await sendTelegramMessage(botToken, USER_ID, message);

    console.log(`✅ Revision queued for ${stream}`);
  } catch (err) {
    console.error(`Error revising content: ${err.message}`);
    await sendTelegramMessage(botToken, USER_ID, `❌ Error queuing revision: ${err.message}`);
  }
}

// ============================================================================
// DISCARD HANDLER
// ============================================================================

async function handleDiscard(stream, botToken) {
  const content = await findPendingContent(stream);

  if (!content) {
    await sendTelegramMessage(botToken, USER_ID, `❌ No pending ${stream} content found to discard.`);
    return;
  }

  try {
    // Remove from pending
    await fs.unlink(content.path);

    const message = `
❌ **${stream.toUpperCase()} Content Discarded**

Content has been removed from queue.
    `.trim();

    await sendTelegramMessage(botToken, USER_ID, message);

    console.log(`✅ ${stream.toUpperCase()} content discarded`);
  } catch (err) {
    console.error(`Error discarding content: ${err.message}`);
    await sendTelegramMessage(botToken, USER_ID, `❌ Error discarding content: ${err.message}`);
  }
}

// ============================================================================
// PUBLISH CONFIRMATION (Marks publishedAt)
// ============================================================================

async function handlePublishConfirm(stream, timestamp, botToken) {
  try {
    const manifestFile = path.join(READY_DIR, `${stream}_${timestamp}_manifest.json`);
    const readyFile = path.join(READY_DIR, `${stream}_${timestamp}_ready.json`);

    // Update manifest with publishedAt
    const manifest = JSON.parse(await fs.readFile(manifestFile, 'utf-8'));
    manifest.publishedAt = new Date().toISOString();
    manifest.status = 'published';
    
    await fs.writeFile(manifestFile, JSON.stringify(manifest, null, 2), 'utf-8');

    // Archive to published folder
    const publishedFolder = path.join(WORKSPACE, 'content', 'published');
    await fs.mkdir(publishedFolder, { recursive: true });
    
    const publishedManifestFile = path.join(publishedFolder, `${stream}_${timestamp}_manifest.json`);
    const publishedReadyFile = path.join(publishedFolder, `${stream}_${timestamp}_published.json`);
    
    await fs.copyFile(manifestFile, publishedManifestFile);
    await fs.copyFile(readyFile, publishedReadyFile);

    // Remove from ready folder
    await fs.unlink(manifestFile);
    await fs.unlink(readyFile);

    const message = `
✅ **${stream.toUpperCase()} Published**

📅 **Published:** ${new Date().toLocaleString('en-US', { timeZone: 'America/Denver' })}
📁 **Archived:** Published folder

Great work! Ready for your next piece of content.
    `.trim();

    await sendTelegramMessage(botToken, USER_ID, message);

    console.log(`✅ ${stream.toUpperCase()} marked as published`);
  } catch (err) {
    console.error(`Error confirming publish: ${err.message}`);
    await sendTelegramMessage(botToken, USER_ID, `❌ Error marking as published: ${err.message}`);
  }
}

// ============================================================================
// PUBLISHING STEPS GENERATOR
// ============================================================================

function generatePublishingSteps(stream) {
  const steps = {
    kinlet: [
      'Copy pillar post to Kinlet.com blog editor',
      'Add featured image (1200x630px)',
      'Add internal links to related posts',
      'Publish to Kinlet.com',
      'Share pillar link on LinkedIn',
      'Deploy email newsletter version',
    ],
    linkedin: [
      'Open LinkedIn in browser',
      'Copy first post text',
      'Paste and post individually',
      'Space posts throughout the week (Mon-Fri)',
      'Pin top-performing post on Friday',
      'Engage with comments',
    ],
  };

  return steps[stream] || ['Review content', 'Publish to platform'];
}

// ============================================================================
// MAIN HANDLER (called from webhook or CLI)
// ============================================================================

export async function handleTelegramCommand(command, stream, feedback = null) {
  const botTokenMap = {
    kinlet: process.env.TELEGRAM_CONTENT_BOT_TOKEN,
    linkedin: process.env.TELEGRAM_CONTENT_BOT_TOKEN,
  };

  const botToken = botTokenMap[stream];

  if (!botToken) {
    console.error(`No bot token for stream: ${stream}`);
    return;
  }

  switch (command) {
    case 'approve':
      await handleApprove(stream, botToken);
      break;
    case 'revise':
      if (!feedback) {
        await sendTelegramMessage(botToken, USER_ID, '❌ Revision requires feedback.');
        return;
      }
      await handleRevise(stream, feedback, botToken);
      break;
    case 'discard':
      await handleDiscard(stream, botToken);
      break;
    case 'publish':
      // publish command: /publish_kinlet_2026-02-23
      const timestamp = feedback; // timestamp passed as feedback param
      await handlePublishConfirm(stream, timestamp, botToken);
      break;
    default:
      console.error(`Unknown command: ${command}`);
  }
}

// ============================================================================
// CLI FOR TESTING
// ============================================================================

async function main() {
  const command = process.argv[2]; // approve, revise, discard, publish
  const stream = process.argv[3] || 'kinlet';
  const feedback = process.argv[4] || null;

  if (!command) {
    console.error('Usage: telegram-approval-handler.mjs <approve|revise|discard|publish> <stream> [feedback]');
    console.error('Examples:');
    console.error('  node telegram-approval-handler.mjs approve kinlet');
    console.error('  node telegram-approval-handler.mjs revise kinlet "Needs stronger hook"');
    console.error('  node telegram-approval-handler.mjs discard linkedin');
    console.error('  node telegram-approval-handler.mjs publish kinlet 2026-02-23');
    process.exit(1);
  }

  await handleTelegramCommand(command, stream, feedback);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main().catch(console.error);
}

export { handleTelegramCommand, handleApprove, handleRevise, handleDiscard, handlePublishConfirm };
