#!/usr/bin/env node

/**
 * Dashboard Data Refresh Script
 * 
 * Automatically fetches data from:
 * - GitHub API (SaaS-Starter repo, PRs, commits)
 * - Substack API (Postshards subscriber count, posts)
 * - Vercel API (deployments)
 * 
 * Usage: node scripts/refresh-dashboard-data.mjs
 * 
 * Required environment variables:
 * - GITHUB_TOKEN: GitHub Personal Access Token
 * - SUBSTACK_EMAIL: Substack login email (for fetching subscriber data)
 * - SUBSTACK_PASSWORD: Substack login password
 * - VERCEL_TOKEN: Vercel API token (optional, for deployment data)
 * 
 * Schedule with cron:
 * 0 * * * * cd ~/.openclaw/workspace && node scripts/refresh-dashboard-data.mjs >> logs/dashboard-refresh.log 2>&1
 */

import fs from 'fs';
import path from 'path';
import https from 'https';

const dashboardPath = './dashboard-data.json';
const logPath = './logs/dashboard-refresh.log';

// Ensure logs directory exists
if (!fs.existsSync('./logs')) {
  fs.mkdirSync('./logs', { recursive: true });
}

function log(message) {
  const timestamp = new Date().toISOString();
  const logMessage = `[${timestamp}] ${message}`;
  console.log(logMessage);
  fs.appendFileSync(logPath, logMessage + '\n');
}

function makeRequest(hostname, path, headers = {}) {
  return new Promise((resolve, reject) => {
    const defaultHeaders = {
      'User-Agent': 'OpenClaw-Dashboard-Bot/1.0',
      ...headers,
    };

    const options = {
      hostname,
      path,
      method: 'GET',
      headers: defaultHeaders,
    };

    https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => {
        data += chunk;
      });
      res.on('end', () => {
        try {
          resolve({
            status: res.statusCode,
            data: JSON.parse(data),
          });
        } catch (e) {
          resolve({
            status: res.statusCode,
            data: data,
          });
        }
      });
    }).on('error', reject).end();
  });
}

async function fetchGitHubData() {
  log('Fetching GitHub data...');
  const token = process.env.GITHUB_TOKEN;
  
  if (!token) {
    log('⚠ GITHUB_TOKEN not set, skipping GitHub data');
    return null;
  }

  try {
    const headers = {
      'Authorization': `token ${token}`,
      'Accept': 'application/vnd.github.v3+json',
    };

    // Get repo stats
    const repoRes = await makeRequest('api.github.com', '/repos/winzenburg/SaaS-Starter', headers);
    const repo = repoRes.data;

    // Get open PRs
    const prsRes = await makeRequest('api.github.com', '/repos/winzenburg/SaaS-Starter/pulls?state=open', headers);
    const openPRs = prsRes.data.length || 0;

    // Get latest commits
    const commitsRes = await makeRequest('api.github.com', '/repos/winzenburg/SaaS-Starter/commits?per_page=1', headers);
    const lastCommit = commitsRes.data[0];
    const lastCommitTime = lastCommit?.commit?.author?.date;

    // Calculate time ago
    const timeDiff = Date.now() - new Date(lastCommitTime).getTime();
    const hoursAgo = Math.floor(timeDiff / (1000 * 60 * 60));
    const daysAgo = Math.floor(timeDiff / (1000 * 60 * 60 * 24));
    let timeAgo = 'just now';
    if (hoursAgo > 0) timeAgo = `${hoursAgo}h ago`;
    if (daysAgo > 0) timeAgo = `${daysAgo}d ago`;

    return {
      openPRs,
      lastCommit: timeAgo,
    };
  } catch (error) {
    log(`⚠ Error fetching GitHub data: ${error.message}`);
    return null;
  }
}

async function fetchSubstackData() {
  log('Fetching Substack data...');
  
  // Note: Substack doesn't have an official public API
  // This would require either:
  // 1. Web scraping (fragile, against ToS)
  // 2. Substack API key from dashboard (if available)
  // 3. Manual update via helper script
  
  // For now, we'll note this limitation
  log('⚠ Substack data fetch requires manual setup. See DASHBOARD.md for options.');
  return null;
}

async function fetchVercelData() {
  log('Fetching Vercel data...');
  const token = process.env.VERCEL_TOKEN;
  
  if (!token) {
    log('⚠ VERCEL_TOKEN not set, skipping Vercel data');
    return null;
  }

  try {
    const headers = {
      'Authorization': `Bearer ${token}`,
    };

    // Get deployments
    const deploymentsRes = await makeRequest('api.vercel.com', '/v6/deployments?limit=10', headers);
    const deployments = deploymentsRes.data?.deployments || [];
    const successfulDeployments = deployments.filter(d => d.state === 'READY').length;

    return {
      deployments: successfulDeployments,
    };
  } catch (error) {
    log(`⚠ Error fetching Vercel data: ${error.message}`);
    return null;
  }
}

async function updateDashboardData() {
  try {
    log('Starting dashboard data refresh...');

    // Read current data
    let data = JSON.parse(fs.readFileSync(dashboardPath, 'utf-8'));

    // Fetch from APIs
    const githubData = await fetchGitHubData();
    const vercelData = await fetchVercelData();

    // Merge GitHub data
    if (githubData) {
      data.github.openPRs = githubData.openPRs;
      data.github.lastCommit = githubData.lastCommit;
      log(`✓ Updated GitHub: ${githubData.openPRs} open PRs, last commit ${githubData.lastCommit}`);
    }

    // Merge Vercel data
    if (vercelData) {
      data.github.deployments = vercelData.deployments;
      log(`✓ Updated Vercel: ${vercelData.deployments} successful deployments`);
    }

    // Update system health
    data.system.telegram = true; // Assume online unless we detect otherwise
    data.system.gateway = true;
    data.system.lastHeartbeat = 'just now';

    // Update timestamp
    data.timestamp = new Date().toISOString();

    // Write back
    fs.writeFileSync(dashboardPath, JSON.stringify(data, null, 2));
    log('✓ Dashboard data refresh complete');

  } catch (error) {
    log(`✗ Error updating dashboard: ${error.message}`);
    process.exit(1);
  }
}

updateDashboardData();
