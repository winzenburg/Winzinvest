#!/usr/bin/env node

/**
 * Business Council
 * 
 * Runs nightly at 11:00 PM MT
 * Analyzes business metrics and delivers strategic brief
 */

import fs from 'fs';
import path from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';
import https from 'https';

const execAsync = promisify(exec);
const LOG_FILE = './logs/council-business.log';

const TELEGRAM_BOT_TOKEN = '8565359157:AAE3cA0Tn2OE62K2eaXiXYr1SFqAFkNtzMQ';
const TELEGRAM_CHAT_ID = '5316436116';

function log(message) {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] ${message}`);
  if (!fs.existsSync('./logs')) fs.mkdirSync('./logs', { recursive: true });
  fs.appendFileSync(LOG_FILE, `[${timestamp}] ${message}\n`);
}

async function analyzeGitHub() {
  log('📊 Analyzing GitHub activity...');
  try {
    const { stdout } = await execAsync('gh repo list --json name,updatedAt,openIssues,forkCount --limit 10 2>/dev/null || echo "[]"');
    const repos = JSON.parse(stdout || '[]');
    
    return {
      totalRepos: repos.length,
      recentlyActive: repos.filter(r => {
        const date = new Date(r.updatedAt);
        const daysSince = (Date.now() - date.getTime()) / (1000 * 60 * 60 * 24);
        return daysSince < 7;
      }).length,
      totalOpenIssues: repos.reduce((sum, r) => sum + (r.openIssues || 0), 0),
      repos: repos.slice(0, 3)
    };
  } catch (error) {
    log(`⚠ GitHub analysis failed: ${error.message}`);
    return { totalRepos: 0, recentlyActive: 0, totalOpenIssues: 0, repos: [] };
  }
}

function analyzeTaskCompletion() {
  log('📋 Analyzing task completion...');
  try {
    const doneFolder = './tasks/done';
    const backlogFolder = './tasks/backlog';
    
    let doneCount = 0;
    let backlogCount = 0;
    
    if (fs.existsSync(doneFolder)) {
      doneCount = fs.readdirSync(doneFolder).filter(f => f.endsWith('.md')).length;
    }
    if (fs.existsSync(backlogFolder)) {
      backlogCount = fs.readdirSync(backlogFolder).filter(f => f.endsWith('.md')).length;
    }
    
    const completionRate = doneCount + backlogCount > 0 
      ? Math.round((doneCount / (doneCount + backlogCount)) * 100)
      : 0;
    
    return {
      completed: doneCount,
      inBacklog: backlogCount,
      completionRate: completionRate,
      trend: completionRate > 60 ? '📈 Strong' : completionRate > 40 ? '→ Steady' : '📉 Needs attention'
    };
  } catch (error) {
    log(`⚠ Task analysis failed: ${error.message}`);
    return { completed: 0, inBacklog: 0, completionRate: 0, trend: 'Unknown' };
  }
}

function analyzeProjects() {
  log('🎯 Analyzing active projects...');
  try {
    const projectFolders = ['kinlet', 'cultivate', 'design-system', 'swing-trading', 'content', 'knowledge'];
    const activeProjects = [];
    
    for (const proj of projectFolders) {
      const path_to_check = path.join('.', proj);
      if (fs.existsSync(path_to_check)) {
        const files = fs.readdirSync(path_to_check).length;
        activeProjects.push({
          name: proj,
          status: 'Active',
          items: files
        });
      }
    }
    
    return {
      total: activeProjects.length,
      projects: activeProjects
    };
  } catch (error) {
    log(`⚠ Project analysis failed: ${error.message}`);
    return { total: 0, projects: [] };
  }
}

async function sendTelegramReport(report) {
  log('📤 Sending Business Council Report...');
  
  const message = `📊 *BUSINESS COUNCIL REPORT*

*Date:* ${new Date().toLocaleDateString()}

*Strategic Recommendations:*
${report.recommendations.map((r, i) => `${i + 1}. ${r}`).join('\n')}

*Key Metrics:*
• Task Completion: ${report.metrics.completionRate}% ${report.metrics.trend}
• GitHub Activity: ${report.metrics.activeRepos} repos active
• Open Issues: ${report.metrics.totalIssues}
• Active Projects: ${report.metrics.projectCount}

*Urgent Items:*
${report.urgent.length > 0 ? report.urgent.map(u => `⚠️ ${u}`).join('\n') : '✅ None'}

*Council Status:* ✅ All systems analyzed`;

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
  log('===== Business Council Start =====');
  
  try {
    // Analyze all metrics
    const github = await analyzeGitHub();
    const tasks = analyzeTaskCompletion();
    const projects = analyzeProjects();
    
    // Generate recommendations
    const recommendations = [
      tasks.completionRate > 50 
        ? `✅ Task completion at ${tasks.completionRate}% - maintain momentum`
        : `⚠️ Task completion at ${tasks.completionRate}% - prioritize backlog`,
      github.recentlyActive > 2
        ? `GitHub activity healthy (${github.recentlyActive} repos active)`
        : `GitHub updates needed - ${github.totalOpenIssues} issues to triage`,
      projects.total >= 4
        ? `${projects.total} projects active - portfolio diversified`
        : `Consider focusing on core 2-3 projects`
    ];
    
    // Identify urgent items
    const urgent = [];
    if (github.totalOpenIssues > 10) urgent.push(`${github.totalOpenIssues} open GitHub issues need attention`);
    if (tasks.completionRate < 30) urgent.push('Task completion rate critically low');
    
    // Compile report
    const report = {
      recommendations,
      metrics: {
        completionRate: tasks.completionRate,
        trend: tasks.trend,
        activeRepos: github.recentlyActive,
        totalIssues: github.totalOpenIssues,
        projectCount: projects.total
      },
      urgent
    };
    
    // Send telegram
    const sent = await sendTelegramReport(report);
    if (sent) {
      log('✓ Business Council Report sent');
    } else {
      log('⚠ Failed to send report');
    }
    
  } catch (error) {
    log(`✗ Council failed: ${error.message}`);
  }
  
  log('===== Business Council Complete =====');
}

main();
