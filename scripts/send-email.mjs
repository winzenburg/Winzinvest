#!/usr/bin/env node

/**
 * Email sender using Resend API
 * Usage: node send-email.mjs "<subject>" "<content>"
 */

import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

const RESEND_API_KEY = process.env.RESEND_API_KEY || 're_UjAL42UD_N8hqtA5k5G8w7HUxxx2nFwCv';
const DEFAULT_TO = 'ryanwinzenburg@gmail.com';
const DEFAULT_FROM = 'Mr. Pinchy <onboarding@resend.dev>';

async function sendEmail({ to = DEFAULT_TO, from = DEFAULT_FROM, subject, content }) {
  const escapedContent = content.replace(/"/g, '\\"').replace(/\n/g, '\\n');
  
  const curlCommand = `curl -X POST 'https://api.resend.com/emails' \\
    -H 'Authorization: Bearer ${RESEND_API_KEY}' \\
    -H 'Content-Type: application/json' \\
    -d '{
      "from": "${from}",
      "to": ["${to}"],
      "subject": "${subject}",
      "text": "${escapedContent}"
    }'`;

  try {
    const { stdout, stderr } = await execAsync(curlCommand);
    
    if (stderr && !stderr.includes('% Total')) {
      throw new Error(stderr);
    }
    
    const result = JSON.parse(stdout.trim().split('\n').pop());
    
    if (result.id) {
      return { success: true, id: result.id };
    } else {
      throw new Error(`Unexpected response: ${stdout}`);
    }
  } catch (error) {
    throw new Error(`Failed to send email: ${error.message}`);
  }
}

// CLI usage
if (import.meta.url === `file://${process.argv[1]}`) {
  const args = process.argv.slice(2);
  
  if (args.length < 2) {
    console.error('Usage: node send-email.mjs "<subject>" "<content>"');
    process.exit(1);
  }

  const subject = args[0];
  const content = args[1];

  sendEmail({ subject, content })
    .then((result) => {
      console.log('✅ Email sent successfully!');
      console.log('Email ID:', result.id);
    })
    .catch((error) => {
      console.error('❌', error.message);
      process.exit(1);
    });
}

export { sendEmail };
