#!/usr/bin/env node

/**
 * Git Auto-Sync Script
 * 
 * Finds all Git repositories in home directory and auto-syncs:
 * 1. Scan for .git directories
 * 2. For each repo with uncommitted/unpushed changes:
 *    - git add -A
 *    - git commit -m "Auto-sync: [date]"
 *    - git push
 * 3. Log any failures (conflicts, auth errors)
 * 4. Report summary via Telegram
 * 
 * Triggered by: LaunchAgent at midnight MT daily (after backup)
 */

import { exec } from 'child_process';
import { promisify } from 'util';
import { readFileSync, writeFileSync, readdirSync, statSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const execAsync = promisify(exec);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const workspaceDir = path.join(__dirname, '..');
const homeDir = process.env.HOME;

// ============================================================================
// CONFIGURATION
// ============================================================================

const CONFIG = {
  homeDir: homeDir,
  exclusions: [
    '.Trash',
    'Library',
    'Applications',
    '.cache',
    '.npm',
    'node_modules',
    '.git' // Don't descend into .git directories
  ],
  maxDepth: 5 // Don't search too deep
};

// ============================================================================
// FIND ALL GIT REPOS
// ============================================================================

function findGitRepos(dirPath, depth = 0) {
  if (depth > CONFIG.maxDepth) return [];
  
  const repos = [];
  
  try {
    const entries = readdirSync(dirPath, { withFileTypes: true });
    
    for (const entry of entries) {
      // Skip excluded directories
      if (CONFIG.exclusions.includes(entry.name)) continue;
      
      // Skip hidden directories (except check for .git)
      if (entry.name.startsWith('.') && entry.name !== '.git') continue;
      
      const fullPath = path.join(dirPath, entry.name);
      
      if (entry.isDirectory()) {
        // Check if this is a Git repo
        const gitPath = path.join(fullPath, '.git');
        if (entry.name === '.git') {
          // Found a .git directory, repo is the parent
          repos.push(fullPath.replace('/.git', ''));
        } else {
          // Recursively search subdirectories
          repos.push(...findGitRepos(fullPath, depth + 1));
        }
      }
    }
  } catch (err) {
    // Permission denied or other error, skip this directory
  }
  
  return repos;
}

// ============================================================================
// CHECK REPO STATUS
// ============================================================================

async function getRepoStatus(repoPath) {
  try {
    const { stdout: statusOutput } = await execAsync(
      `cd "${repoPath}" && git status --porcelain`,
      { maxBuffer: 10 * 1024 * 1024 }
    );
    
    const hasUncommitted = statusOutput.trim().length > 0;
    
    // Check for unpushed commits
    const { stdout: pushOutput } = await execAsync(
      `cd "${repoPath}" && git log --oneline @{u}.. 2>/dev/null | wc -l`,
      { maxBuffer: 10 * 1024 * 1024 }
    );
    
    const unpushedCount = parseInt(pushOutput.trim()) || 0;
    
    return {
      repoPath,
      hasUncommitted,
      unpushedCount,
      needsSync: hasUncommitted || unpushedCount > 0
    };
    
  } catch (err) {
    return {
      repoPath,
      error: 'Failed to check status',
      needsSync: false
    };
  }
}

// ============================================================================
// SYNC REPO
// ============================================================================

async function syncRepo(repoPath) {
  console.log(`\n📁 Syncing: ${repoPath}`);
  
  const result = {
    repoPath,
    success: false,
    added: 0,
    committed: false,
    pushed: false,
    error: null
  };
  
  try {
    // Step 1: git add -A
    const { stdout: addOutput } = await execAsync(
      `cd "${repoPath}" && git add -A && git status --short`,
      { maxBuffer: 10 * 1024 * 1024 }
    );
    
    const stagedFiles = addOutput.trim().split('\n').filter(line => line.length > 0);
    result.added = stagedFiles.length;
    
    if (result.added > 0) {
      console.log(`  ✅ Added ${result.added} files`);
    }
    
    // Step 2: git commit
    const timestamp = new Date().toLocaleString('en-US', {
      timeZone: 'America/Denver',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
    
    const commitMessage = `Auto-sync: ${timestamp}`;
    
    try {
      const { stdout: commitOutput } = await execAsync(
        `cd "${repoPath}" && git commit -m "${commitMessage}"`,
        { maxBuffer: 10 * 1024 * 1024 }
      );
      
      result.committed = true;
      console.log(`  ✅ Committed`);
    } catch (err) {
      // Likely nothing to commit
      if (err.message.includes('nothing to commit')) {
        console.log(`  ℹ️ Nothing new to commit`);
      } else {
        throw err;
      }
    }
    
    // Step 3: git push
    try {
      const { stdout: pushOutput } = await execAsync(
        `cd "${repoPath}" && git push`,
        { maxBuffer: 10 * 1024 * 1024 }
      );
      
      result.pushed = true;
      console.log(`  ✅ Pushed`);
    } catch (err) {
      if (err.message.includes('nothing to push')) {
        console.log(`  ℹ️ Nothing to push`);
        result.success = true;
      } else if (err.message.includes('conflict') || err.message.includes('CONFLICT')) {
        result.error = 'Push conflict - manual intervention needed';
        console.error(`  ❌ ${result.error}`);
      } else if (err.message.includes('Permission denied') || err.message.includes('fatal:')) {
        result.error = 'Authentication failed - check SSH key or credentials';
        console.error(`  ❌ ${result.error}`);
      } else {
        result.error = err.message.split('\n')[0];
        console.error(`  ❌ ${result.error}`);
      }
    }
    
    result.success = !result.error;
    return result;
    
  } catch (err) {
    result.error = err.message.split('\n')[0];
    console.error(`  ❌ Sync failed: ${result.error}`);
    return result;
  }
}

// ============================================================================
// LOG SYNC RESULTS
// ============================================================================

async function logSyncResults(results) {
  const statusFile = path.join(workspaceDir, 'backup_status.md');
  
  let content = '';
  try {
    content = readFileSync(statusFile, 'utf-8');
  } catch {
    content = `# Backup Status Log`;
  }
  
  // Find or create Git Sync section
  const gitSyncMarker = '## Git Auto-Sync History';
  let gitSyncSection = '';
  
  if (content.includes(gitSyncMarker)) {
    const parts = content.split(gitSyncMarker);
    gitSyncSection = parts[1] || '';
    content = parts[0] + gitSyncMarker;
  } else {
    content += `\n\n${gitSyncMarker}\n\n| Timestamp | Repo | Status | Files | Committed | Pushed | Error |\n|-----------|------|--------|-------|-----------|--------|-------|\n`;
  }
  
  const timestamp = new Date().toLocaleString('en-US', { timeZone: 'America/Denver' });
  
  for (const result of results) {
    const repoName = path.basename(result.repoPath);
    const status = result.success ? '✅' : '❌';
    const committed = result.committed ? '✅' : '—';
    const pushed = result.pushed ? '✅' : '—';
    const error = result.error ? `${result.error}` : '—';
    
    const row = `| ${timestamp} | ${repoName} | ${status} | ${result.added} | ${committed} | ${pushed} | ${error} |`;
    content += '\n' + row;
  }
  
  writeFileSync(statusFile, content, 'utf-8');
  console.log(`\n📋 Results logged to backup_status.md`);
}

// ============================================================================
// SEND TELEGRAM NOTIFICATION
// ============================================================================

async function sendTelegramSummary(allRepos, syncedRepos, results) {
  console.log(`\n📱 Preparing Telegram notification...`);
  
  const successCount = results.filter(r => r.success).length;
  const failureCount = results.filter(r => !r.success).length;
  const skippedCount = allRepos.length - results.length;
  
  let summary = `🔄 **Git Auto-Sync Report**

**Timestamp:** ${new Date().toLocaleString('en-US', { timeZone: 'America/Denver' })} MT

**Summary:**
✅ Success: ${successCount}
❌ Failed: ${failureCount}
⏭️ Skipped (no changes): ${skippedCount}
📊 Total repos scanned: ${allRepos.length}`;
  
  if (failureCount > 0) {
    summary += `\n\n⚠️ **Failed Repos:**`;
    for (const result of results) {
      if (!result.success) {
        const repoName = path.basename(result.repoPath);
        summary += `\n• ${repoName}: ${result.error}`;
      }
    }
  }
  
  console.log(summary);
  
  // In production, would send via message tool:
  // await message({ action: 'send', channel: 'telegram', message: summary });
  
  return summary;
}

// ============================================================================
// MAIN EXECUTION
// ============================================================================

async function main() {
  console.log(`\n🚀 Starting Git Auto-Sync...`);
  console.log(`📍 Scanning: ${CONFIG.homeDir}`);
  
  // Step 1: Find all repos
  console.log(`\n🔍 Finding Git repositories...`);
  const repos = findGitRepos(CONFIG.homeDir);
  console.log(`✅ Found ${repos.length} Git repositories`);
  
  // Step 2: Check status for each repo
  console.log(`\n📊 Checking repository status...`);
  const repoStatuses = [];
  
  for (const repo of repos) {
    const status = await getRepoStatus(repo);
    repoStatuses.push(status);
    
    if (status.error) {
      console.log(`  ⚠️ ${path.basename(repo)}: ${status.error}`);
    } else if (status.needsSync) {
      console.log(`  📝 ${path.basename(repo)}: ${status.hasUncommitted ? 'uncommitted' : ''}${status.unpushedCount > 0 ? ` +${status.unpushedCount} unpushed` : ''}`);
    } else {
      console.log(`  ✅ ${path.basename(repo)}: up to date`);
    }
  }
  
  // Step 3: Sync repos that need it
  const needsSync = repoStatuses.filter(s => s.needsSync);
  console.log(`\n🔄 Syncing ${needsSync.length} repositories with changes...`);
  
  const syncResults = [];
  for (const repoStatus of needsSync) {
    const result = await syncRepo(repoStatus.repoPath);
    syncResults.push(result);
  }
  
  // Step 4: Log results
  await logSyncResults(syncResults);
  
  // Step 5: Send notification
  await sendTelegramSummary(repos, needsSync, syncResults);
  
  console.log(`\n✅ Git auto-sync complete!`);
  process.exit(0);
}

main().catch(err => {
  console.error(`Fatal error: ${err.message}`);
  process.exit(1);
});
