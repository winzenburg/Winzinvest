#!/usr/bin/env node
/**
 * email-formatter.mjs
 * 
 * Formats content drafts for email delivery
 * 
 * Features:
 * - Per-stream HTML formatting (Kinlet vs LinkedIn)
 * - Action buttons (Approve, Revise, Discard)
 * - Draft preview + link to full content
 * - Publishing steps
 * - Dark mode template
 * - Multipart (HTML + plaintext) delivery via Resend
 */

import fs from 'fs/promises';
import path from 'path';
import { getEmailProvider } from './email-provider.mjs';

// ============================================================================
// BUILD HTML EMAIL (Dark Mode, Professional)
// ============================================================================

function buildEmailHTML(emailSummary, stream) {
  const isDark = true;
  const bgColor = isDark ? '#1a1a1a' : '#ffffff';
  const textColor = isDark ? '#e0e0e0' : '#333333';
  const accentColor = '#2563eb';
  const borderColor = isDark ? '#333333' : '#e0e0e0';
  
  let contentHTML = '';
  
  if (stream === 'kinlet') {
    contentHTML = buildKinletEmail(emailSummary, bgColor, textColor, accentColor, borderColor);
  } else if (stream === 'linkedin') {
    contentHTML = buildLinkedInEmail(emailSummary, bgColor, textColor, accentColor, borderColor);
  }
  
  const html = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {
      background-color: ${bgColor};
      color: ${textColor};
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
      line-height: 1.6;
      margin: 0;
      padding: 20px;
    }
    .container {
      max-width: 600px;
      margin: 0 auto;
      background-color: ${isDark ? '#0a0a0a' : '#ffffff'};
      border: 1px solid ${borderColor};
      border-radius: 8px;
      padding: 40px;
    }
    h1 {
      font-size: 24px;
      margin: 0 0 10px 0;
      color: ${textColor};
    }
    h2 {
      font-size: 18px;
      margin: 30px 0 15px 0;
      color: ${accentColor};
      border-bottom: 2px solid ${borderColor};
      padding-bottom: 10px;
    }
    .preview {
      background-color: ${isDark ? '#1a1a1a' : '#f5f5f5'};
      border-left: 4px solid ${accentColor};
      padding: 15px;
      margin: 15px 0;
      border-radius: 4px;
      font-size: 14px;
      line-height: 1.5;
    }
    .action-buttons {
      display: flex;
      gap: 10px;
      margin: 30px 0;
      flex-wrap: wrap;
    }
    .btn {
      padding: 12px 24px;
      border-radius: 6px;
      text-decoration: none;
      font-weight: 500;
      border: none;
      cursor: pointer;
      font-size: 14px;
      transition: all 0.2s;
    }
    .btn-approve {
      background-color: #10b981;
      color: white;
    }
    .btn-approve:hover {
      background-color: #059669;
    }
    .btn-revise {
      background-color: ${accentColor};
      color: white;
    }
    .btn-revise:hover {
      background-color: #1d4ed8;
    }
    .btn-discard {
      background-color: #ef4444;
      color: white;
    }
    .btn-discard:hover {
      background-color: #dc2626;
    }
    .command {
      background-color: ${isDark ? '#1a1a1a' : '#f5f5f5'};
      padding: 8px 12px;
      border-radius: 4px;
      font-family: 'Courier New', monospace;
      font-size: 12px;
      color: ${accentColor};
      margin: 5px 0;
    }
    .metadata {
      font-size: 12px;
      color: ${isDark ? '#999999' : '#666666'};
      margin: 10px 0;
    }
    .divider {
      border: none;
      border-top: 1px solid ${borderColor};
      margin: 30px 0;
    }
    .footer {
      font-size: 12px;
      color: ${isDark ? '#666666' : '#999999'};
      margin-top: 30px;
      padding-top: 20px;
      border-top: 1px solid ${borderColor};
    }
  </style>
</head>
<body>
  <div class="container">
    ${contentHTML}
    
    <div class="divider"></div>
    
    <div class="footer">
      <p>📧 Content Factory Email | Generated at ${new Date().toLocaleString()}</p>
      <p>Reply to this email with your decision or use the Telegram commands above.</p>
    </div>
  </div>
</body>
</html>
  `;
  
  return html;
}

// ============================================================================
// KINLET EMAIL
// ============================================================================

function buildKinletEmail(emailSummary, bgColor, textColor, accentColor, borderColor) {
  const pillar = emailSummary.content.pillar;
  const spokes = emailSummary.content.spokes;
  
  return `
    <h1>🎯 Kinlet Content Drafts</h1>
    <p><strong>${emailSummary.topic}</strong></p>
    <p class="metadata">Generated: ${new Date(emailSummary.timestamp).toLocaleDateString()}</p>
    
    <h2>📝 Pillar Content (1,500 words)</h2>
    <p>Blog post ready for Kinlet.com</p>
    <div class="preview">
      ${pillar.preview}
    </div>
    <p class="metadata">Word count: ${pillar.wordCount}</p>
    
    <h2>🔊 Spokes (Ready to Publish)</h2>
    
    <h3>💼 LinkedIn Post</h3>
    <div class="preview">
      ${spokes.linkedin.content.substring(0, 300)}...
    </div>
    
    <h3>📧 Email Newsletter</h3>
    <div class="preview">
      ${spokes.email.content.substring(0, 300)}...
    </div>
    
    <h3>🐦 Twitter Thread</h3>
    <div class="preview">
      ${spokes.twitter.content.substring(0, 300)}...
    </div>
    
    <h2>Your Decision</h2>
    <p>This content is ready for your review. Choose one:</p>
    
    <div class="action-buttons">
      <button class="btn btn-approve">✅ Approve & Publish</button>
      <button class="btn btn-revise">📝 Request Revision</button>
      <button class="btn btn-discard">❌ Discard</button>
    </div>
    
    <h3>Or use Telegram commands:</h3>
    <div class="command">/approve_kinlet</div>
    <div class="command">/revise_kinlet Needs stronger hook about personal story</div>
    <div class="command">/discard_kinlet</div>
    
    <p class="metadata">✅ Approve → Moves to "Ready to Publish" folder (you manually publish)</p>
    <p class="metadata">📝 Revise → Regenerates with your feedback, delivers tomorrow 8:00 AM</p>
    <p class="metadata">❌ Discard → Removes from queue</p>
  `;
}

// ============================================================================
// LINKEDIN EMAIL
// ============================================================================

function buildLinkedInEmail(emailSummary, bgColor, textColor, accentColor, borderColor) {
  const posts = emailSummary.content.posts;
  
  let postsHTML = '';
  for (const post of posts) {
    postsHTML += `
      <div style="margin-bottom: 30px; border: 1px solid ${borderColor}; padding: 20px; border-radius: 6px;">
        <h3>Post ${post.number}</h3>
        <div class="preview">
          ${post.content.substring(0, 400)}...
        </div>
        <p class="metadata">Word count: ${post.wordCount}</p>
      </div>
    `;
  }
  
  return `
    <h1>💼 LinkedIn Posts Ready for Review</h1>
    <p><strong>Weekly Batch: ${emailSummary.topic}</strong></p>
    <p class="metadata">Generated: ${new Date(emailSummary.timestamp).toLocaleDateString()}</p>
    
    <h2>📅 This Week's Posts (${posts.length})</h2>
    ${postsHTML}
    
    <h2>Your Decision</h2>
    <p>All posts are independent and ready to publish throughout the week.</p>
    
    <div class="action-buttons">
      <button class="btn btn-approve">✅ Approve All</button>
      <button class="btn btn-revise">📝 Request Revision</button>
      <button class="btn btn-discard">❌ Discard</button>
    </div>
    
    <h3>Or use Telegram commands:</h3>
    <div class="command">/approve_linkedin</div>
    <div class="command">/revise_linkedin Post 1 needs more personal story</div>
    <div class="command">/discard_linkedin</div>
    
    <p class="metadata">✅ Approve → Moves to "Ready to Publish" folder</p>
    <p class="metadata">📝 Revise → Regenerates with your feedback, delivers tomorrow 8:00 AM</p>
    <p class="metadata">❌ Discard → Removes from queue</p>
    
    <h2>📌 Publishing Tips</h2>
    <ul>
      <li>Post 1 on Monday or Tuesday</li>
      <li>Post 2 on Wednesday or Thursday</li>
      <li>Post 3 on Friday (pin this one for weekend views)</li>
      <li>Space them out for better engagement</li>
    </ul>
  `;
}

// ============================================================================
// FORMAT FOR TELEGRAM
// ============================================================================

function buildTelegramMessage(emailSummary, stream) {
  let message = '';
  
  if (stream === 'kinlet') {
    message = `📬 **Kinlet Content Ready for Review**\n\n`;
    message += `📝 Topic: ${emailSummary.topic}\n`;
    message += `🎯 Pillar: ${emailSummary.content.pillar.wordCount} words\n`;
    message += `🔊 Spokes: LinkedIn, Email, Twitter\n\n`;
    message += `**Your options:**\n`;
    message += `✅ /approve_kinlet\n`;
    message += `📝 /revise_kinlet [feedback]\n`;
    message += `❌ /discard_kinlet\n`;
  } else if (stream === 'linkedin') {
    message = `📬 **LinkedIn Posts Ready for Review**\n\n`;
    message += `📅 Topic: ${emailSummary.topic}\n`;
    message += `📊 Posts: ${emailSummary.batch.count}\n`;
    message += `📈 Total words: ${emailSummary.content.posts.reduce((sum, p) => sum + p.wordCount, 0)}\n\n`;
    message += `**Your options:**\n`;
    message += `✅ /approve_linkedin\n`;
    message += `📝 /revise_linkedin [feedback]\n`;
    message += `❌ /discard_linkedin\n`;
  }
  
  message += `\nApproval moves to "Ready to Publish" folder.`;
  message += `\nFull email with all content sent separately.`;
  
  return message;
}

// ============================================================================
// SEND EMAIL
// ============================================================================

export async function sendEmail(stream, emailSummary) {
  const provider = getEmailProvider();

  // Generate idempotency key (prevent double-sends)
  const idempotencyKey = `email-${stream}-${emailSummary.topic}-${Math.floor(Date.now() / 1000)}`;
  
  // Check if already sent
  const alreadySent = await provider.checkIdempotency(idempotencyKey);
  if (alreadySent) {
    console.log(`[EMAIL] Email already sent (idempotency key: ${idempotencyKey}). Skipping.`);
    return {
      success: true,
      messageId: alreadySent.messageId,
      alreadySent: true,
    };
  }

  // Build plaintext version (fallback for clients that don't support HTML)
  const plaintextContent = buildPlaintextEmail(stream, emailSummary);
  const htmlContent = buildEmailHTML(emailSummary, stream);

  // Send via email provider
  const result = await provider.send({
    to: process.env.TO_EMAIL || 'ryanwinzenburg@gmail.com',
    subject: emailSummary.subject,
    html: htmlContent,
    text: plaintextContent,
    tags: [stream, 'content-factory'],
    headers: {
      'X-App': 'OpenClaw',
      'X-Content-Stream': stream,
      'X-Priority': 'normal',
    },
  });

  // Log if successful
  if (result.success) {
    await provider.logSent(idempotencyKey, result.messageId);
  }

  return result;
}

/**
 * Build plaintext version for email fallback
 */
function buildPlaintextEmail(stream, emailSummary) {
  let text = `${emailSummary.subject}\n`;
  text += `Generated: ${new Date(emailSummary.timestamp).toLocaleString()}\n\n`;
  
  if (stream === 'kinlet') {
    text += `TOPIC: ${emailSummary.topic}\n`;
    text += `PILLAR: ${emailSummary.content.pillar.wordCount} words\n\n`;
    text += `PREVIEW:\n${emailSummary.content.pillar.preview}\n\n`;
  } else if (stream === 'linkedin') {
    text += `TOPIC: ${emailSummary.topic}\n`;
    text += `POSTS: ${emailSummary.batch.count}\n\n`;
    for (const post of emailSummary.content.posts) {
      text += `POST ${post.number} (${post.wordCount} words):\n`;
      text += `${post.preview}...\n\n`;
    }
  }
  
  text += `\nYOUR OPTIONS:\n`;
  text += `/approve_${stream}\n`;
  text += `/revise_${stream} [your feedback]\n`;
  text += `/discard_${stream}\n\n`;
  
  text += `Approval moves to "Ready to Publish" folder.\n`;
  text += `Revisions regenerate with feedback, deliver tomorrow 8:00 AM.\n`;
  
  return text;
}

// ============================================================================
// EXPORTS
// ============================================================================

export { buildEmailHTML, buildTelegramMessage };
