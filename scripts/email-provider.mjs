#!/usr/bin/env node
/**
 * email-provider.mjs
 * 
 * Abstract email provider interface with Resend implementation
 * Allows swapping providers (Resend → SES → Postmark) without changing callers
 * 
 * Uses native fetch (Node 18+) — no dependencies required
 */

import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE = path.resolve(__dirname, '..');
const SENT_LOG_FILE = path.join(WORKSPACE, '.sent-log.json');

// ============================================================================
// ABSTRACT INTERFACE
// ============================================================================

export class EmailProvider {
  /**
   * Send an email
   * @param {Object} options
   * @param {string} options.to - Recipient email
   * @param {string} options.subject - Email subject
   * @param {string} options.html - HTML body
   * @param {string} options.text - Plaintext body
   * @param {string} options.from - From email (optional, uses default)
   * @param {string} options.replyTo - Reply-to email (optional)
   * @param {Array<string>} options.tags - Tags for filtering/logging
   * @param {Object} options.headers - Custom headers
   * @returns {Promise<{success: boolean, messageId: string, error?: string}>}
   */
  async send(options) {
    throw new Error('send() not implemented');
  }

  /**
   * Check if email was already sent (idempotency)
   */
  async checkIdempotency(key) {
    throw new Error('checkIdempotency() not implemented');
  }

  /**
   * Log that an email was sent
   */
  async logSent(key, messageId) {
    throw new Error('logSent() not implemented');
  }
}

// ============================================================================
// RESEND IMPLEMENTATION
// ============================================================================

export class ResendProvider extends EmailProvider {
  constructor(apiKey) {
    super();
    this.apiKey = apiKey || process.env.RESEND_API_KEY;
    this.fromEmail = process.env.FROM_EMAIL || 'notifications@example.com';
    this.baseUrl = 'https://api.resend.com';

    if (!this.apiKey) {
      console.warn('[RESEND] Warning: RESEND_API_KEY not set. Email sending will fail.');
    }
  }

  /**
   * Send email via Resend API
   */
  async send(options) {
    const {
      to,
      subject,
      html,
      text,
      from = this.fromEmail,
      replyTo = process.env.REPLY_TO_EMAIL,
      tags = [],
      headers = {},
    } = options;

    if (!this.apiKey) {
      return {
        success: false,
        error: 'RESEND_API_KEY not configured',
        messageId: null,
      };
    }

    if (!to || !subject || (!html && !text)) {
      return {
        success: false,
        error: 'Missing required: to, subject, and (html or text)',
        messageId: null,
      };
    }

    // Build Resend payload
    const payload = {
      from,
      to,
      subject,
      ...(html && { html }),
      ...(text && { text }),
      ...(replyTo && { reply_to: replyTo }),
      tags,
      headers,
    };

    try {
      console.log(`[RESEND] Sending email to ${to}: "${subject}"`);

      const response = await fetch(`${this.baseUrl}/emails`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const error = await response.text();
        console.error(`[RESEND] Error ${response.status}: ${error}`);
        return {
          success: false,
          error: `HTTP ${response.status}: ${error}`,
          messageId: null,
        };
      }

      const data = await response.json();
      const messageId = data.id;

      console.log(`[RESEND] ✅ Email sent. Message ID: ${messageId}`);

      return {
        success: true,
        messageId,
        timestamp: new Date().toISOString(),
      };
    } catch (err) {
      console.error(`[RESEND] Exception: ${err.message}`);
      return {
        success: false,
        error: err.message,
        messageId: null,
      };
    }
  }

  /**
   * Check idempotency log
   */
  async checkIdempotency(key) {
    try {
      const log = await this.readLog();
      return log.sent && log.sent[key];
    } catch (err) {
      return null;
    }
  }

  /**
   * Log sent email
   */
  async logSent(key, messageId) {
    try {
      const log = await this.readLog();

      if (!log.sent) {
        log.sent = {};
      }

      log.sent[key] = {
        messageId,
        timestamp: new Date().toISOString(),
      };

      await this.writeLog(log);
      console.log(`[LOG] Idempotency key recorded: ${key}`);
    } catch (err) {
      console.error(`[LOG] Error writing idempotency log: ${err.message}`);
    }
  }

  /**
   * Read sent log
   */
  async readLog() {
    try {
      const data = await fs.readFile(SENT_LOG_FILE, 'utf-8');
      return JSON.parse(data);
    } catch (err) {
      return { sent: {} };
    }
  }

  /**
   * Write sent log
   */
  async writeLog(log) {
    await fs.writeFile(SENT_LOG_FILE, JSON.stringify(log, null, 2), 'utf-8');
  }
}

// ============================================================================
// FACTORY
// ============================================================================

export function createEmailProvider(type = 'resend') {
  switch (type.toLowerCase()) {
    case 'resend':
      return new ResendProvider();
    default:
      throw new Error(`Unknown email provider: ${type}`);
  }
}

// ============================================================================
// SINGLETON INSTANCE
// ============================================================================

let _provider = null;

export function getEmailProvider() {
  if (!_provider) {
    _provider = createEmailProvider(process.env.EMAIL_PROVIDER || 'resend');
  }
  return _provider;
}

export function setEmailProvider(provider) {
  _provider = provider;
}

// ============================================================================
// CONFIGURATION HELPER
// ============================================================================

export function getEmailConfig() {
  return {
    provider: process.env.EMAIL_PROVIDER || 'resend',
    apiKey: process.env.RESEND_API_KEY ? '***' : 'NOT_SET',
    fromEmail: process.env.FROM_EMAIL || 'notifications@example.com',
    toEmail: process.env.TO_EMAIL || 'ryanwinzenburg@gmail.com',
    replyTo: process.env.REPLY_TO_EMAIL || 'ryanwinzenburg@gmail.com',
  };
}

// ============================================================================
// CLI TEST
// ============================================================================

async function main() {
  const provider = getEmailProvider();

  console.log('\n📧 Email Provider Config:');
  console.log(JSON.stringify(getEmailConfig(), null, 2));

  // Test send (will fail if no API key, which is expected)
  console.log('\n🧪 Testing email send (this will fail without RESEND_API_KEY)...');

  const result = await provider.send({
    to: 'test@example.com',
    subject: 'Test Email',
    html: '<p>This is a test.</p>',
    text: 'This is a test.',
    tags: ['test'],
  });

  console.log('\nResult:', result);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main().catch(console.error);
}
