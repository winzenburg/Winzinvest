#!/usr/bin/env node

/**
 * Task Indexer
 * 
 * Scans tasks/ folder and generates index.json for Kanban board
 * 
 * Usage:
 *   node scripts/index-tasks.mjs
 */

import fs from 'fs';
import path from 'path';

const TASKS_PATH = './tasks';
const INDEX_FILE = './tasks/index.json';
const LOG_FILE = './logs/task-index.log';

function log(message) {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] ${message}`);
  if (!fs.existsSync('./logs')) fs.mkdirSync('./logs', { recursive: true });
  fs.appendFileSync(LOG_FILE, `[${timestamp}] ${message}\n`);
}

function parseTaskFile(filepath, filename) {
  const content = fs.readFileSync(filepath, 'utf-8');

  // Extract frontmatter
  const titleMatch = content.match(/^# (.+?)$/m);
  const idMatch = content.match(/\*\*ID:\*\*\s+(\w+)/);
  const goalMatch = content.match(/\*\*Goal:\*\*\s+(.+?)(?:\n|$)/);
  const priorityMatch = content.match(/\*\*Priority:\*\*\s+(\w+)/);
  const createdMatch = content.match(/\*\*Created:\*\*\s+(\d{4}-\d{2}-\d{2})/);
  const dueMatch = content.match(/\*\*Due:\*\*\s+(\d{4}-\d{2}-\d{2})/);
  const statusMatch = content.match(/\*\*Status:\*\*\s+(\w+)/);

  // Extract description (first line after ## Description)
  const descMatch = content.match(/## Description\n\n([\s\S]*?)(?=\n##|\Z)/);

  return {
    filename,
    id: idMatch ? idMatch[1] : 'unknown',
    title: titleMatch ? titleMatch[1] : 'Untitled',
    goal: goalMatch ? goalMatch[1].trim() : '',
    priority: priorityMatch ? priorityMatch[1] : 'Medium',
    created: createdMatch ? createdMatch[1] : '',
    due: dueMatch ? dueMatch[1] : '',
    status: statusMatch ? statusMatch[1] : 'Backlog',
    description: descMatch ? descMatch[1].trim().substring(0, 200) : '',
    fullContent: content
  };
}

function main() {
  log('===== Task Indexer Start =====');

  const index = {
    timestamp: new Date().toISOString(),
    tasks: [],
    byStatus: {
      'Backlog': [],
      'In Progress': [],
      'Done': []
    },
    stats: {
      total: 0,
      byPriority: {
        'Critical': 0,
        'High': 0,
        'Medium': 0,
        'Low': 0
      }
    }
  };

  // Scan all status folders
  ['backlog', 'in-progress', 'done'].forEach(folderName => {
    const folderPath = path.join(TASKS_PATH, folderName);
    
    if (!fs.existsSync(folderPath)) {
      log(`⚠ Folder not found: ${folderPath}`);
      return;
    }

    const files = fs.readdirSync(folderPath)
      .filter(f => f.endsWith('.md'))
      .sort();

    files.forEach(filename => {
      try {
        const filepath = path.join(folderPath, filename);
        const task = parseTaskFile(filepath, filename);
        
        index.tasks.push({
          ...task,
          path: `tasks/${folderName}/${filename}`
        });

        // Categorize by status
        const statusKey = folderName === 'in-progress' ? 'In Progress' : 
                         folderName === 'backlog' ? 'Backlog' : 'Done';
        index.byStatus[statusKey].push({
          id: task.id,
          title: task.title,
          priority: task.priority
        });

        // Update priority stats
        if (task.priority in index.stats.byPriority) {
          index.stats.byPriority[task.priority]++;
        }

        log(`✓ Indexed: ${task.id} - ${task.title}`);
      } catch (error) {
        log(`⚠ Error parsing ${filename}: ${error.message}`);
      }
    });
  });

  index.stats.total = index.tasks.length;

  // Write index file
  fs.writeFileSync(INDEX_FILE, JSON.stringify(index, null, 2));
  log(`✓ Generated index: ${INDEX_FILE}`);
  log(`  Total tasks: ${index.stats.total}`);
  log(`  Backlog: ${index.byStatus.Backlog.length}, In Progress: ${index.byStatus['In Progress'].length}, Done: ${index.byStatus.Done.length}`);

  log('===== Task Indexer Complete =====');
}

main();
