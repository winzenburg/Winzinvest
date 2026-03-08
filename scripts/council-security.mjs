#!/usr/bin/env node

/**
 * Security Council
 * 
 * Runs nightly at 11:30 PM MT
 * Scans for security vulnerabilities and delivers security brief
 */

import fs from 'fs';
import path from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';
import https from 'https';

const execAsync = promisify(exec);
const LOG_FILE = './logs/council-security.log';

const TELEGRAM_BOT_TOKEN = '8565359157:AAE3cA0Tn2OE62K2eaXiXYr1SFqAFkNtzMQ';
const TELEGRAM_CHAT_ID = '5316436116';

function log(message) {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] ${message}`);
  if (!fs.existsSync('./logs')) fs.mkdirSync('./logs', { recursive: true });
  fs.appendFileSync(LOG_FILE, `[${timestamp}] ${message}\n`);
}

function scanForSecrets() {
  log('🔐 Scanning for hardcoded secrets...');
  const issues = [];
  
  try {
    // Scan workspace for common secret patterns
    const secretPatterns = [
      { pattern: /api[_-]?key\s*=\s*["'][^"']+["']/gi, name: 'API Key' },
      { pattern: /password\s*=\s*["'][^"']+["']/gi, name: 'Password' },
      { pattern: /token\s*=\s*["'][^"']+["']/gi, name: 'Token' },
      { pattern: /secret\s*=\s*["'][^"']+["']/gi, name: 'Secret' },
      { pattern: /private[_-]?key\s*=\s*["'][^"']+["']/gi, name: 'Private Key' }
    ];
    
    const filesToCheck = [
      '.env',
      '.env.local',
      'config.js',
      'config.json',
      'secrets.json',
      'credentials.json'
    ];
    
    for (const file of filesToCheck) {
      const filePath = path.join('.', file);
      if (fs.existsSync(filePath)) {
        const content = fs.readFileSync(filePath, 'utf-8');
        
        for (const { pattern, name } of secretPatterns) {
          if (pattern.test(content)) {
            issues.push({
              severity: 'critical',
              type: name,
              file: file,
              message: `${name} found in ${file}`
            });
          }
        }
      }
    }
  } catch (error) {
    log(`⚠ Secret scan failed: ${error.message}`);
  }
  
  return issues;
}

function checkDependencies() {
  log('📦 Checking for vulnerable dependencies...');
  const issues = [];
  
  try {
    // Check for package.json
    if (fs.existsSync('./package.json')) {
      const pkg = JSON.parse(fs.readFileSync('./package.json', 'utf-8'));
      const deps = { ...pkg.dependencies, ...pkg.devDependencies };
      
      // Known vulnerable packages (simplified list)
      const knownVulnerable = {
        'lodash': '4.17.15',
        'moment': '2.29.0',
        'express': '4.17.0'
      };
      
      for (const [pkg, minVersion] of Object.entries(knownVulnerable)) {
        if (deps[pkg] && deps[pkg] < minVersion) {
          issues.push({
            severity: 'high',
            type: 'Vulnerable Dependency',
            package: pkg,
            message: `${pkg} has known vulnerabilities. Update to ${minVersion}+`
          });
        }
      }
    }
    
    // Check for requirements.txt
    if (fs.existsSync('./requirements.txt')) {
      // Simplified Python dependency check
      const content = fs.readFileSync('./requirements.txt', 'utf-8');
      
      const knownVulnerablePython = ['pillow<9.0', 'requests<2.28'];
      for (const vuln of knownVulnerablePython) {
        if (content.includes(vuln)) {
          issues.push({
            severity: 'high',
            type: 'Vulnerable Dependency',
            package: vuln,
            message: `Python dependency ${vuln} has known vulnerabilities`
          });
        }
      }
    }
  } catch (error) {
    log(`⚠ Dependency check failed: ${error.message}`);
  }
  
  return issues;
}

function checkWebhookSecurity() {
  log('🔗 Checking webhook security...');
  const issues = [];
  
  try {
    // Check for exposed webhook endpoints
    const webhookFiles = [
      './scripts/webhook_listener.py',
      './webhook.js',
      './handlers/webhooks.js'
    ];
    
    for (const file of webhookFiles) {
      if (fs.existsSync(file)) {
        const content = fs.readFileSync(file, 'utf-8');
        
        // Check for missing auth
        if (!content.includes('auth') && !content.includes('verify') && !content.includes('secret')) {
          issues.push({
            severity: 'high',
            type: 'Webhook Security',
            file: file,
            message: `${file} may lack authentication/verification`
          });
        }
        
        // Check for proper HTTPS
        if (content.includes('http://') && !content.includes('https://')) {
          issues.push({
            severity: 'high',
            type: 'Webhook Security',
            file: file,
            message: `${file} uses HTTP instead of HTTPS`
          });
        }
      }
    }
    
    // Verify webhook token exists
    if (!process.env.WEBHOOK_SECRET && !fs.existsSync('./.env')) {
      issues.push({
        severity: 'medium',
        type: 'Webhook Security',
        message: 'WEBHOOK_SECRET environment variable not set'
      });
    }
  } catch (error) {
    log(`⚠ Webhook check failed: ${error.message}`);
  }
  
  return issues;
}

function analyzeSecurityPosture(allIssues) {
  const critical = allIssues.filter(i => i.severity === 'critical').length;
  const high = allIssues.filter(i => i.severity === 'high').length;
  const medium = allIssues.filter(i => i.severity === 'medium').length;
  const low = allIssues.filter(i => i.severity === 'low').length;
  
  let status = '🟢';
  let statusText = 'SECURE';
  
  if (critical > 0) {
    status = '🔴';
    statusText = 'CRITICAL - IMMEDIATE ACTION REQUIRED';
  } else if (high > 2) {
    status = '🟠';
    statusText = 'AT RISK - ACTION REQUIRED';
  } else if (high > 0 || medium > 2) {
    status = '🟡';
    statusText = 'CAUTION - REVIEW RECOMMENDED';
  }
  
  return { status, statusText, critical, high, medium, low };
}

async function sendTelegramReport(report) {
  log('📤 Sending Security Council Report...');
  
  const severityIssues = report.issues
    .reduce((acc, issue) => {
      acc[issue.severity] = (acc[issue.severity] || 0) + 1;
      return acc;
    }, {});
  
  const message = `🔐 *SECURITY COUNCIL REPORT*

*Date:* ${new Date().toLocaleDateString()}

*Status:* ${report.status} *${report.statusText}*

*Issues Found:*
🔴 Critical: ${report.critical}
🟠 High: ${report.high}
🟡 Medium: ${report.medium}
🟢 Low: ${report.low}

*Top Issues:*
${report.issues.slice(0, 5).map(i => 
  `• [${i.severity.toUpperCase()}] ${i.type}: ${i.message}`
).join('\n') || '✅ None detected'}

*Recommended Actions:*
${report.recommendations.join('\n')}

*Last Scan:* ${new Date().toLocaleTimeString()}`;

  return new Promise((resolve) => {
    const payload = JSON.stringify({
      chat_id: TELEGRAM_CHAT_ID,
      text: message,
      parse_mode: 'Markdown'
    });

    const options = {
      hostname: 'api.telegram.org',
      path: `/bot${TELEGRAM_BOT_TOKEN}/sendMessage`,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload)
      }
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const result = JSON.parse(data);
          resolve(result.ok);
        } catch (e) {
          resolve(false);
        }
      });
    });

    req.on('error', () => resolve(false));
    req.write(payload);
    req.end();
  });
}

async function main() {
  log('===== Security Council Start =====');
  
  try {
    // Run all security scans
    const secretIssues = scanForSecrets();
    const depIssues = checkDependencies();
    const webhookIssues = checkWebhookSecurity();
    
    const allIssues = [...secretIssues, ...depIssues, ...webhookIssues];
    
    // Analyze posture
    const posture = analyzeSecurityPosture(allIssues);
    
    // Generate recommendations
    const recommendations = [];
    if (secretIssues.length > 0) recommendations.push('🔴 Move all secrets to .env or secure vault');
    if (depIssues.length > 0) recommendations.push('🟠 Update vulnerable dependencies');
    if (webhookIssues.length > 0) recommendations.push('🟡 Review webhook authentication');
    if (allIssues.length === 0) recommendations.push('✅ All security checks passed');
    
    // Compile report
    const report = {
      ...posture,
      issues: allIssues,
      recommendations
    };
    
    // Send telegram
    const sent = await sendTelegramReport(report);
    if (sent) {
      log('✓ Security Council Report sent');
    } else {
      log('⚠ Failed to send report');
    }
    
  } catch (error) {
    log(`✗ Council failed: ${error.message}`);
  }
  
  log('===== Security Council Complete =====');
}

main();
