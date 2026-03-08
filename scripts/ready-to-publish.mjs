#!/usr/bin/env node
/**
 * ready-to-publish.mjs
 * 
 * Manages the "Ready to Publish" folder
 * Provides:
 * - List of all approved content waiting to be published
 * - Publishing steps for each piece
 * - Quick access to manifests and drafts
 * - Daily summary email
 */

import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE = path.resolve(__dirname, '..');
const READY_FOLDER = path.join(WORKSPACE, 'content', 'ready-to-publish');

// ============================================================================
// LIST READY CONTENT
// ============================================================================

async function listReadyContent() {
  try {
    await fs.mkdir(READY_FOLDER, { recursive: true });
    
    const files = await fs.readdir(READY_FOLDER);
    const manifestFiles = files.filter(f => f.endsWith('_manifest.json'));
    
    const content = [];
    
    for (const manifestFile of manifestFiles) {
      try {
        const data = JSON.parse(
          await fs.readFile(path.join(READY_FOLDER, manifestFile), 'utf-8')
        );
        
        content.push({
          id: manifestFile.replace('_manifest.json', ''),
          stream: data.stream,
          approvedAt: data.approvedAt,
          contentTypes: data.content.spokes || [],
          manifestFile: manifestFile,
          publishingSteps: data.publishingSteps,
          files: data.files
        });
      } catch (err) {
        console.error(`Error reading ${manifestFile}: ${err.message}`);
      }
    }
    
    return content.sort((a, b) => 
      new Date(b.approvedAt) - new Date(a.approvedAt)
    );
  } catch (err) {
    console.error(`Error listing ready content: ${err.message}`);
    return [];
  }
}

// ============================================================================
// GET CONTENT DETAILS
// ============================================================================

async function getContentDetails(contentId) {
  try {
    const manifestFile = path.join(READY_FOLDER, `${contentId}_manifest.json`);
    const contentFile = path.join(READY_FOLDER, `${contentId}_ready.json`);
    
    const manifest = JSON.parse(await fs.readFile(manifestFile, 'utf-8'));
    const content = JSON.parse(await fs.readFile(contentFile, 'utf-8'));
    
    return {
      id: contentId,
      manifest: manifest,
      content: content,
      status: 'ready-to-publish'
    };
  } catch (err) {
    console.error(`Error getting details for ${contentId}: ${err.message}`);
    return null;
  }
}

// ============================================================================
// GENERATE SUMMARY
// ============================================================================

async function generateSummary() {
  const readyContent = await listReadyContent();
  
  if (readyContent.length === 0) {
    return {
      summary: 'No content ready to publish',
      count: 0,
      byStream: {}
    };
  }
  
  const byStream = {};
  for (const item of readyContent) {
    if (!byStream[item.stream]) {
      byStream[item.stream] = [];
    }
    byStream[item.stream].push(item);
  }
  
  return {
    summary: `${readyContent.length} piece(s) ready to publish`,
    count: readyContent.length,
    byStream: byStream,
    content: readyContent
  };
}

// ============================================================================
// FORMAT FOR EMAIL/TELEGRAM
// ============================================================================

async function formatForNotification() {
  const summary = await generateSummary();
  
  if (summary.count === 0) {
    return {
      message: '✅ All content published! No items waiting.',
      summary: summary
    };
  }
  
  let message = `📋 **${summary.count} pieces ready to publish:**\n\n`;
  
  for (const [stream, items] of Object.entries(summary.byStream)) {
    message += `**${stream.toUpperCase()}** (${items.length})\n`;
    
    for (const item of items) {
      const date = new Date(item.approvedAt).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
      
      message += `  • ${date} - ${item.contentTypes.join(', ')}\n`;
    }
    
    message += '\n';
  }
  
  message += '**Next steps:**\n';
  message += '1. Open Ready to Publish folder\n';
  message += '2. Review manifest files\n';
  message += '3. Follow publishing steps\n';
  message += '4. Mark as published when done\n';
  
  return {
    message: message,
    summary: summary
  };
}

// ============================================================================
// MARK AS PUBLISHED
// ============================================================================

async function markAsPublished(contentId, publishedAt = null) {
  try {
    const manifestFile = path.join(READY_FOLDER, `${contentId}_manifest.json`);
    const contentFile = path.join(READY_FOLDER, `${contentId}_ready.json`);
    
    // Update manifest
    const manifest = JSON.parse(await fs.readFile(manifestFile, 'utf-8'));
    manifest.publishedAt = publishedAt || new Date().toISOString();
    manifest.status = 'published';
    
    await fs.writeFile(manifestFile, JSON.stringify(manifest, null, 2), 'utf-8');
    
    // Move to published archive
    const publishedFolder = path.join(WORKSPACE, 'content', 'published');
    await fs.mkdir(publishedFolder, { recursive: true });
    
    const publishedManifestFile = path.join(publishedFolder, `${contentId}_manifest.json`);
    const publishedContentFile = path.join(publishedFolder, `${contentId}_published.json`);
    
    await fs.copyFile(manifestFile, publishedManifestFile);
    await fs.copyFile(contentFile, publishedContentFile);
    
    // Remove from ready folder
    await fs.unlink(manifestFile);
    await fs.unlink(contentFile);
    
    console.log(`✅ ${contentId} marked as published`);
    console.log(`📍 Archived to: ${publishedFolder}`);
    
    return {
      success: true,
      publishedAt: manifest.publishedAt,
      archiveFile: publishedManifestFile
    };
  } catch (err) {
    console.error(`Error marking as published: ${err.message}`);
    return { success: false, error: err.message };
  }
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  const command = process.argv[2] || 'list';
  const contentId = process.argv[3] || null;
  
  switch (command) {
    case 'list':
      {
        const content = await listReadyContent();
        console.log('\n📋 Content Ready to Publish:');
        console.log('='.repeat(60));
        
        if (content.length === 0) {
          console.log('No content ready to publish.');
        } else {
          for (const item of content) {
            const date = new Date(item.approvedAt).toLocaleDateString('en-US', {
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit'
            });
            
            console.log(`\n[${item.stream.toUpperCase()}] ${date}`);
            console.log(`  ID: ${item.id}`);
            console.log(`  Types: ${item.contentTypes.join(', ')}`);
          }
        }
        
        console.log('\n');
        break;
      }
      
    case 'details':
      {
        if (!contentId) {
          console.error('Usage: ready-to-publish.mjs details <contentId>');
          process.exit(1);
        }
        
        const details = await getContentDetails(contentId);
        
        if (!details) {
          console.error(`Content not found: ${contentId}`);
          process.exit(1);
        }
        
        console.log('\n📄 Content Details:');
        console.log('='.repeat(60));
        console.log(JSON.stringify(details, null, 2));
        break;
      }
      
    case 'summary':
      {
        const { message, summary } = await formatForNotification();
        console.log('\n' + message);
        break;
      }
      
    case 'published':
      {
        if (!contentId) {
          console.error('Usage: ready-to-publish.mjs published <contentId>');
          process.exit(1);
        }
        
        const result = await markAsPublished(contentId);
        console.log(JSON.stringify(result, null, 2));
        break;
      }
      
    default:
      console.error(`Unknown command: ${command}`);
      console.error('Usage: ready-to-publish.mjs [list|details|summary|published] [contentId]');
      process.exit(1);
  }
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});

export { listReadyContent, getContentDetails, generateSummary, markAsPublished, formatForNotification };
