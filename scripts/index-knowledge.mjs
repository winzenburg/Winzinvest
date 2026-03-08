#!/usr/bin/env node

/**
 * Knowledge Base Indexer
 * 
 * Scans knowledge/ folder and generates index for web interface
 * 
 * Usage:
 *   node scripts/index-knowledge.mjs
 */

import fs from 'fs';
import path from 'path';

const KNOWLEDGE_PATH = './knowledge';
const INDEX_FILE = './knowledge/index.json';
const LOG_FILE = './logs/knowledge-index.log';

function log(message) {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] ${message}`);
  if (!fs.existsSync('./logs')) fs.mkdirSync('./logs', { recursive: true });
  fs.appendFileSync(LOG_FILE, `[${timestamp}] ${message}\n`);
}

function parseMarkdownFile(filepath, filename) {
  const content = fs.readFileSync(filepath, 'utf-8');

  // Extract frontmatter
  const titleMatch = content.match(/^# (.+?)$/m);
  const sourceMatch = content.match(/\*\*Source:\*\*.*?\[([^\]]+)\]\(([^)]+)\)/);
  const dateMatch = content.match(/\*\*Date Saved:\*\*\s+(\d{4}-\d{2}-\d{2})/);
  const categoryMatch = content.match(/\*\*Category:\*\*\s+(\w+)/);
  const tagsMatch = content.match(/\*\*Tags:\*\*\s+(.+?)(?:\n|$)/);

  // Extract summary
  const summaryMatch = content.match(/## Summary\n\n([\s\S]*?)(?=\n##)/);

  // Extract takeaways
  const takeawaysMatch = content.match(/## Key Takeaways\n\n([\s\S]*?)(?=\n##)/);
  const takeaways = takeawaysMatch 
    ? takeawaysMatch[1].split('\n').filter(l => l.startsWith('-')).map(l => l.replace(/^-\s+/, ''))
    : [];

  return {
    filename,
    title: titleMatch ? titleMatch[1] : 'Untitled',
    source: sourceMatch ? sourceMatch[1] : 'Unknown',
    sourceUrl: sourceMatch ? sourceMatch[2] : '',
    dateSaved: dateMatch ? dateMatch[1] : '',
    category: categoryMatch ? categoryMatch[1] : 'other',
    tags: tagsMatch ? tagsMatch[1].split(' ').map(t => t.replace(/#/, '')) : [],
    summary: summaryMatch ? summaryMatch[1].trim() : '',
    takeaways: takeaways,
    fullContent: content
  };
}

function main() {
  log('===== Knowledge Base Indexer Start =====');

  const categories = fs.readdirSync(KNOWLEDGE_PATH)
    .filter(f => fs.statSync(path.join(KNOWLEDGE_PATH, f)).isDirectory());

  log(`Found ${categories.length} categories`);

  const index = {
    timestamp: new Date().toISOString(),
    items: [],
    totalItems: 0,
    categories: {}
  };

  categories.forEach(category => {
    const categoryPath = path.join(KNOWLEDGE_PATH, category);
    const files = fs.readdirSync(categoryPath)
      .filter(f => f.endsWith('.md'))
      .sort()
      .reverse(); // Newest first

    index.categories[category] = {
      count: files.length,
      items: []
    };

    files.forEach(filename => {
      try {
        const filepath = path.join(categoryPath, filename);
        const item = parseMarkdownFile(filepath, filename);
        
        index.items.push({
          ...item,
          path: `knowledge/${category}/${filename}`
        });

        index.categories[category].items.push({
          filename,
          title: item.title,
          dateSaved: item.dateSaved
        });

        log(`✓ Indexed: ${item.title}`);
      } catch (error) {
        log(`⚠ Error parsing ${filename}: ${error.message}`);
      }
    });
  });

  index.totalItems = index.items.length;

  // Write index file
  fs.writeFileSync(INDEX_FILE, JSON.stringify(index, null, 2));
  log(`✓ Generated index: ${INDEX_FILE}`);
  log(`  Total items: ${index.totalItems}`);
  log(`  Categories: ${categories.join(', ')}`);

  log('===== Knowledge Base Indexer Complete =====');
}

main();
