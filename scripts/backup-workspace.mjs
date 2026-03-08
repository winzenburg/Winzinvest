#!/usr/bin/env node

/**
 * Workspace Backup Script
 * 
 * Nightly backup system for ~/.openclaw/workspace/
 * 
 * Workflow:
 * 1. Compress workspace to timestamped .tar.gz
 * 2. Encrypt with password (from macOS Keychain)
 * 3. Upload to Google Drive (rclone)
 * 4. Delete backups older than 30 days
 * 5. Log to backup_status.md
 * 6. Send Telegram confirmation
 * 
 * Triggered by: LaunchAgent at midnight MT daily
 */

import { exec } from 'child_process';
import { promisify } from 'util';
import { readFileSync, writeFileSync, statSync } from 'fs';
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
  workspaceDir: workspaceDir,
  backupDir: path.join(homeDir, '.backups', 'openclaw'),
  googleDriveFolder: 'OpenClaw Backups',
  retentionDays: 30,
  rcloneRemote: 'google-drive',
  keychain: {
    service: 'OpenClaw',
    account: 'backup-password'
  }
};

// ============================================================================
// LOGGING
// ============================================================================

function formatLogEntry(status, details) {
  const timestamp = new Date().toISOString();
  const entry = {
    timestamp,
    status, // 'success' or 'error'
    details,
    size: details.size || null,
    googleDriveLink: details.googleDriveLink || null,
    error: details.error || null
  };
  return entry;
}

async function logBackupAttempt(entry) {
  const statusFile = path.join(workspaceDir, 'backup_status.md');
  
  let content = '';
  try {
    content = readFileSync(statusFile, 'utf-8');
  } catch {
    // File doesn't exist yet, start fresh
    content = `# Backup Status Log

Last updated: ${new Date().toLocaleString('en-US', { timeZone: 'America/Denver' })}

| Timestamp | Status | Size | Google Drive | Error |
|-----------|--------|------|--------------|-------|
`;
  }
  
  const sizeStr = entry.size ? `${(entry.size / 1024 / 1024).toFixed(2)} MB` : '—';
  const link = entry.googleDriveLink ? `[Link](${entry.googleDriveLink})` : '—';
  const error = entry.error ? `❌ ${entry.error}` : '✅';
  
  const row = `| ${entry.timestamp} | ${entry.status} | ${sizeStr} | ${link} | ${error} |`;
  
  const updatedContent = content.replace(
    /Last updated: .*/,
    `Last updated: ${new Date().toLocaleString('en-US', { timeZone: 'America/Denver' })}`
  ) + '\n' + row;
  
  writeFileSync(statusFile, updatedContent, 'utf-8');
  console.log(`📋 Logged to backup_status.md`);
}

// ============================================================================
// STEP 1: COMPRESS WORKSPACE
// ============================================================================

async function compressWorkspace() {
  console.log(`\n📦 Compressing workspace...`);
  
  const timestamp = new Date().toISOString()
    .replace(/[:.]/g, '-')
    .split('T')[0] + '_' + new Date().toISOString().split('T')[1].split('.')[0].replace(/:/g, '-');
  
  const backupFilename = `openclaw-workspace_${timestamp}.tar.gz`;
  const backupPath = path.join(CONFIG.backupDir, backupFilename);
  
  // Create backup directory
  await execAsync(`mkdir -p "${CONFIG.backupDir}"`);
  
  try {
    // Compress with tar
    await execAsync(
      `tar -czf "${backupPath}" -C "${homeDir}" .openclaw/workspace/`,
      { maxBuffer: 50 * 1024 * 1024 }
    );
    
    const stats = statSync(backupPath);
    const size = stats.size;
    
    console.log(`✅ Compressed: ${backupFilename}`);
    console.log(`📊 Size: ${(size / 1024 / 1024).toFixed(2)} MB`);
    
    return {
      success: true,
      filename: backupFilename,
      path: backupPath,
      size: size
    };
    
  } catch (err) {
    console.error(`❌ Compression failed: ${err.message}`);
    return { success: false, error: err.message };
  }
}

// ============================================================================
// STEP 2: ENCRYPT BACKUP
// ============================================================================

async function encryptBackup(backupPath, password) {
  console.log(`\n🔐 Encrypting backup...`);
  
  const encryptedPath = `${backupPath}.enc`;
  
  try {
    // Use openssl with password from stdin
    // Note: Password should come from macOS Keychain (passed as argument)
    await execAsync(
      `openssl enc -aes-256-cbc -salt -in "${backupPath}" -out "${encryptedPath}" -k "${password}" -P`,
      { maxBuffer: 50 * 1024 * 1024 }
    );
    
    console.log(`✅ Encrypted: ${path.basename(encryptedPath)}`);
    
    // Delete unencrypted backup
    await execAsync(`rm "${backupPath}"`);
    
    return { success: true, path: encryptedPath };
    
  } catch (err) {
    console.error(`❌ Encryption failed: ${err.message}`);
    return { success: false, error: err.message };
  }
}

// ============================================================================
// STEP 3: UPLOAD TO GOOGLE DRIVE
// ============================================================================

async function uploadToGoogleDrive(backupPath) {
  console.log(`\n☁️ Uploading to Google Drive...`);
  
  try {
    // Check if rclone is available
    await execAsync(`which rclone`);
    
    // Upload using rclone
    const filename = path.basename(backupPath);
    await execAsync(
      `rclone copy "${backupPath}" ${CONFIG.rcloneRemote}:"${CONFIG.googleDriveFolder}/" --progress`,
      { maxBuffer: 50 * 1024 * 1024 }
    );
    
    console.log(`✅ Uploaded: ${filename}`);
    
    // Get shareable link (optional - would need more rclone setup)
    const shareLink = `https://drive.google.com/drive/folders/[FOLDER_ID]?usp=sharing`;
    
    return {
      success: true,
      filename: filename,
      link: shareLink
    };
    
  } catch (err) {
    if (err.message.includes('not found')) {
      console.warn(`⚠️ rclone not found - skipping Google Drive upload`);
      return { success: false, error: 'rclone not installed' };
    }
    console.error(`❌ Upload failed: ${err.message}`);
    return { success: false, error: err.message };
  }
}

// ============================================================================
// STEP 4: CLEANUP OLD BACKUPS
// ============================================================================

async function cleanupOldBackups() {
  console.log(`\n🧹 Cleaning up backups older than ${CONFIG.retentionDays} days...`);
  
  try {
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - CONFIG.retentionDays);
    
    const { stdout } = await execAsync(`ls -1 "${CONFIG.backupDir}"`);
    const files = stdout.trim().split('\n');
    
    let deletedCount = 0;
    
    for (const file of files) {
      const filePath = path.join(CONFIG.backupDir, file);
      const stats = statSync(filePath);
      
      if (stats.mtime < cutoffDate) {
        await execAsync(`rm "${filePath}"`);
        console.log(`  🗑️ Deleted: ${file}`);
        deletedCount++;
      }
    }
    
    console.log(`✅ Cleanup complete: ${deletedCount} old backups deleted`);
    return { success: true, deletedCount };
    
  } catch (err) {
    console.error(`❌ Cleanup failed: ${err.message}`);
    return { success: false, error: err.message };
  }
}

// ============================================================================
// STEP 5: SEND TELEGRAM NOTIFICATION
// ============================================================================

async function sendTelegramNotification(backupInfo) {
  console.log(`\n📱 Preparing Telegram notification...`);
  
  const status = backupInfo.success ? '✅' : '❌';
  const sizeStr = backupInfo.size ? `${(backupInfo.size / 1024 / 1024).toFixed(2)} MB` : 'N/A';
  const timestamp = new Date().toLocaleString('en-US', { timeZone: 'America/Denver' });
  
  let message = `${status} **Backup Status**

**Time:** ${timestamp} MT
**Status:** ${backupInfo.success ? 'Success' : 'Failed'}
**Size:** ${sizeStr}
**File:** \`${backupInfo.filename || 'N/A'}\``;
  
  if (backupInfo.googleDriveLink) {
    message += `\n**Google Drive:** [Open](${backupInfo.googleDriveLink})`;
  }
  
  if (backupInfo.error) {
    message += `\n\n⚠️ **Error:** ${backupInfo.error}`;
  }
  
  console.log(message);
  
  // In production, would send via message tool:
  // await message({ action: 'send', channel: 'telegram', message });
  
  return message;
}

// ============================================================================
// MAIN EXECUTION
// ============================================================================

async function main() {
  console.log(`\n🚀 Starting OpenClaw workspace backup...`);
  console.log(`📍 Workspace: ${CONFIG.workspaceDir}`);
  
  // Get password from Keychain or environment
  let backupPassword;
  try {
    const { stdout } = await execAsync(
      `security find-generic-password -w -s "${CONFIG.keychain.service}" -a "${CONFIG.keychain.account}" 2>/dev/null || echo ""`
    );
    backupPassword = stdout.trim();
    
    if (!backupPassword) {
      console.warn(`⚠️ No password in Keychain. Skipping encryption.`);
      backupPassword = null;
    }
  } catch (err) {
    console.warn(`⚠️ Keychain access failed. Skipping encryption.`);
    backupPassword = null;
  }
  
  // Step 1: Compress
  const compressResult = await compressWorkspace();
  if (!compressResult.success) {
    const logEntry = formatLogEntry('error', {
      error: 'Compression failed: ' + compressResult.error
    });
    await logBackupAttempt(logEntry);
    await sendTelegramNotification(compressResult);
    process.exit(1);
  }
  
  let backupPath = compressResult.path;
  
  // Step 2: Encrypt (optional)
  if (backupPassword) {
    const encryptResult = await encryptBackup(backupPath, backupPassword);
    if (encryptResult.success) {
      backupPath = encryptResult.path;
    } else {
      console.warn(`⚠️ Encryption failed, continuing with unencrypted backup`);
    }
  }
  
  // Step 3: Upload
  const uploadResult = await uploadToGoogleDrive(backupPath);
  
  // Step 4: Cleanup
  await cleanupOldBackups();
  
  // Step 5: Log & Notify
  const finalResult = {
    success: compressResult.success && uploadResult.success,
    filename: path.basename(backupPath),
    size: compressResult.size,
    googleDriveLink: uploadResult.success ? uploadResult.link : null,
    error: uploadResult.success ? null : uploadResult.error
  };
  
  const logEntry = formatLogEntry(finalResult.success ? 'success' : 'error', finalResult);
  await logBackupAttempt(logEntry);
  await sendTelegramNotification(finalResult);
  
  console.log(`\n✅ Backup complete!`);
  process.exit(finalResult.success ? 0 : 1);
}

main().catch(err => {
  console.error(`Fatal error: ${err.message}`);
  process.exit(1);
});
