#!/usr/bin/env node

/**
 * Second Brain - Knowledge Base Ingestion Script
 * 
 * Fetches content from URL and saves to knowledge base
 * 
 * Usage:
 *   node scripts/save-to-knowledge.mjs <url> <category> [tags]
 * 
 * Example:
 *   node scripts/save-to-knowledge.mjs "https://example.com/article" ai "ai,ml,learning"
 * 
 * Categories: ai, business, health, research, market, design, other
 */

import https from 'https';
import http from 'http';
import fs from 'fs';
import path from 'path';

const KNOWLEDGE_PATH = './knowledge';
const VALID_CATEGORIES = ['ai', 'business', 'health', 'research', 'market', 'design', 'other'];
const LOG_FILE = './logs/knowledge-ingestion.log';

function log(message) {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] ${message}`);
  if (!fs.existsSync('./logs')) fs.mkdirSync('./logs', { recursive: true });
  fs.appendFileSync(LOG_FILE, `[${timestamp}] ${message}\n`);
}

function fetchContent(urlString) {
  return new Promise((resolve, reject) => {
    try {
      const url = new URL(urlString);
      const protocol = url.protocol === 'https:' ? https : http;

      const options = {
        method: 'GET',
        headers: {
          'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        },
        timeout: 10000
      };

      const req = protocol.get(url, options, (res) => {
        let data = '';

        res.on('data', chunk => {
          data += chunk;
        });

        res.on('end', () => {
          resolve({
            status: res.statusCode,
            headers: res.headers,
            body: data
          });
        });
      });

      req.on('error', reject);
      req.on('timeout', () => {
        req.destroy();
        reject(new Error('Request timeout'));
      });
    } catch (error) {
      reject(error);
    }
  });
}

function extractTextFromHTML(html) {
  // Remove script and style tags
  let text = html.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
  text = text.replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, '');
  
  // Remove HTML tags
  text = text.replace(/<[^>]+>/g, ' ');
  
  // Decode HTML entities
  text = text
    .replace(/&nbsp;/g, ' ')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
  
  // Clean up whitespace
  text = text.replace(/\s+/g, ' ').trim();
  
  return text;
}

function extractTitle(html, url) {
  // Try to get title from meta tag
  const titleMatch = html.match(/<meta\s+name=["']og:title["']\s+content=["']([^"']+)["']/i);
  if (titleMatch) return titleMatch[1];

  // Try to get from title tag
  const tagMatch = html.match(/<title\s*>([^<]+)<\/title>/i);
  if (tagMatch) return tagMatch[1];

  // Fall back to URL
  return new URL(url).hostname;
}

function generateSummary(text, title) {
  // Extract first 5 sentences as summary
  const sentences = text.match(/[^.!?]+[.!?]+/g) || [];
  const summaryText = sentences.slice(0, 10).join(' ').trim();
  
  // Generate key takeaways (simplified)
  const takeaways = [];
  const lines = text.split('\n').filter(l => l.trim());
  
  for (let i = 0; i < Math.min(5, lines.length); i++) {
    const line = lines[i].trim();
    if (line.length > 20 && line.length < 200) {
      takeaways.push(line);
    }
  }

  return {
    summary: summaryText.substring(0, 500),
    takeaways: takeaways.slice(0, 5)
  };
}

function createMarkdownFile(content, category, tags, url, title) {
  const filename = `${Date.now()}-${title.toLowerCase().replace(/[^a-z0-9]/g, '-').substring(0, 30)}.md`;
  const filepath = path.join(KNOWLEDGE_PATH, category, filename);

  const markdown = `# ${title}

**Source:** [${new URL(url).hostname}](${url})
**Date Saved:** ${new Date().toISOString().split('T')[0]}
**Category:** ${category}
**Tags:** ${tags.map(t => `#${t}`).join(' ')}

## Summary

${content.summary}

## Key Takeaways

${content.takeaways.map(t => `- ${t}`).join('\n')}

## Full Content

${content.fullText.substring(0, 10000)}${content.fullText.length > 10000 ? '\n\n[... content truncated ...]' : ''}

---

**Saved to:** \`knowledge/${category}/${filename}\`
`;

  fs.writeFileSync(filepath, markdown);
  return { filename, filepath, content: markdown };
}

async function main() {
  const url = process.argv[2];
  const category = (process.argv[3] || 'other').toLowerCase();
  const tagsArg = process.argv[4] || '';

  if (!url) {
    console.error('Usage: node save-to-knowledge.mjs <url> [category] [tags]');
    console.error('Categories: ' + VALID_CATEGORIES.join(', '));
    process.exit(1);
  }

  if (!VALID_CATEGORIES.includes(category)) {
    console.error(`Invalid category. Use one of: ${VALID_CATEGORIES.join(', ')}`);
    process.exit(1);
  }

  log('===== Knowledge Base Ingestion Start =====');
  log(`URL: ${url}`);
  log(`Category: ${category}`);

  try {
    log('Fetching content...');
    const response = await fetchContent(url);

    if (response.status !== 200) {
      throw new Error(`HTTP ${response.status}`);
    }

    log('Extracting content...');
    const title = extractTitle(response.body, url);
    const fullText = extractTextFromHTML(response.body);
    
    if (fullText.length < 100) {
      throw new Error('Extracted content too short, may be JavaScript-heavy');
    }

    const summary = generateSummary(fullText, title);
    const tags = tagsArg.split(',').map(t => t.trim()).filter(t => t);

    log('Creating markdown file...');
    const file = createMarkdownFile(
      {
        summary: summary.summary,
        takeaways: summary.takeaways,
        fullText
      },
      category,
      tags,
      url,
      title
    );

    log(`✓ Saved: ${file.filename}`);
    log(`Path: ${file.filepath}`);

    console.log('\n✅ Knowledge saved!');
    console.log(`Title: ${title}`);
    console.log(`Category: ${category}`);
    console.log(`File: knowledge/${category}/${file.filename}`);

    if (tags.length > 0) {
      console.log(`Tags: ${tags.join(', ')}`);
    }

  } catch (error) {
    log(`✗ Error: ${error.message}`);
    console.error(`\n❌ Failed to save: ${error.message}`);
    process.exit(1);
  }

  log('===== Knowledge Base Ingestion Complete =====');
}

main();
