#!/usr/bin/env node
/**
 * article-to-linkedin-scanner.mjs
 * 
 * Scans winzenburg.com articles and generates LinkedIn content angles
 * 
 * Flow:
 * 1. Read article metadata from portfolio-2025
 * 2. Extract key insights (title, excerpt, category)
 * 3. Generate LinkedIn angles using Ollama
 * 4. Output ready-to-publish LinkedIn drafts
 * 5. Email for approval
 */

import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';
import { generate } from './ollama-client.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE = path.resolve(__dirname, '..');

// Article metadata (from portfolio-2025/COMPLETE_ARTICLES_METADATA.md)
const ARTICLES = [
  {
    id: "50",
    title: "Integration Documentation That Developers Actually Read",
    excerpt: "Last week, a developer integrated our API in 18 minutes. Another took 3 hours on the same integration. Same API. Same endpoints. Different documentation. Developer experience is a design problem.",
    date: "January 11, 2026",
    category: "Engineering",
    slug: "integration-docs-that-work"
  },
  {
    id: "49",
    title: "Compound Intelligence: How Documentation Makes Codebases Learn",
    excerpt: "My codebase got smarter last month without me touching a line of code. An autonomous agent documented its learnings. The next agent read that file and made better decisions. This is compound intelligence.",
    date: "January 11, 2026",
    category: "AI Workflow",
    slug: "compound-intelligence"
  },
  {
    id: "48",
    title: "Fresh Context Per Iteration: Why Autonomous Agents Don't Break Like Long Sessions",
    excerpt: "I spent 4 hours in an interactive AI session yesterday. By hour 3, the agent was making mistakes it wouldn't have made in hour 1. Context pollution had set in. Meanwhile, an autonomous agent built a feature overnight with zero context drift.",
    date: "January 11, 2026",
    category: "AI Workflow",
    slug: "fresh-context-per-iteration"
  },
  {
    id: "47",
    title: "Self-Validating AI Agents: When Acceptance Criteria Become Tests",
    excerpt: "Last night, an autonomous agent built a feature, tested it against 23 acceptance criteria, found 2 failures, fixed them, retested, and committed—all while I slept. Self-validation isn't magic. It's well-written acceptance criteria.",
    date: "January 11, 2026",
    category: "AI Workflow",
    slug: "self-validating-ai-agents"
  },
  {
    id: "46",
    title: "Writing PRDs That AI Agents Can Execute",
    excerpt: "I spent 45 minutes writing a PRD. The autonomous agent built the feature perfectly overnight for $42. Then I wrote another PRD in 20 minutes. The agent failed three times and wasted $60. The difference? Acceptance criteria specificity.",
    date: "January 11, 2026",
    category: "AI Workflow",
    slug: "writing-prds-for-ai-agents"
  },
  {
    id: "45",
    title: "Choosing Your AI Coding Mode: Interactive vs Autonomous",
    excerpt: "Last week, I wasted $60 and 8 hours trying to build a feature autonomously that should have been interactive. The mode wasn't wrong—my choice was. Here's the decision framework I should have used.",
    date: "January 11, 2026",
    category: "AI Workflow",
    slug: "choosing-ai-coding-mode"
  },
  {
    id: "44",
    title: "The Economics of AI-Assisted Coding: When $40 Beats 6 Hours",
    excerpt: "Last month, I spent $42 on API calls to build a feature that would have cost me $600 in time. The ROI was 14x. But the real story isn't about saving money—it's about what becomes possible when implementation stops being the constraint.",
    date: "January 11, 2026",
    category: "AI Workflow",
    slug: "ai-coding-economics"
  },
  {
    id: "43",
    title: "Autonomous AI Coding: Building Features Overnight",
    excerpt: "I went to bed with a PRD and five user stories. When I woke up, the feature was built, tested, and committed. Total cost: $42. Total time I spent coding: zero hours.",
    date: "January 11, 2026",
    category: "AI Workflow",
    slug: "autonomous-ai-coding"
  },
];

// ============================================================================
// EXTRACT LINKEDIN ANGLES
// ============================================================================

async function generateLinkedInAngle(article) {
  console.log(`\n📝 Generating LinkedIn angle for: "${article.title}"`);

  const prompt = `You are writing a LinkedIn post based on this article:

Title: ${article.title}
Excerpt: ${article.excerpt}
Category: ${article.category}

Create a LinkedIn post (2-3 paragraphs) that:
1. Opens with a personal observation or contrarian take
2. Extracts the core insight from the article
3. Makes it relevant to product builders, engineers, or entrepreneurs
4. Ends with a question to spark engagement
5. Includes a link to the article

Tone: Conversational, authentic, thought-provoking. Use "I" perspective.
Keep it under 200 words.`;

  const result = await generate('spoke-repurposing', prompt);

  if (!result.success) {
    console.error(`Error generating angle: ${result.error}`);
    return null;
  }

  return result.text;
}

// ============================================================================
// BATCH PROCESS ARTICLES
// ============================================================================

async function scanArticles() {
  console.log(`\n🔍 Scanning ${ARTICLES.length} articles for LinkedIn angles...\n`);

  const results = {
    timestamp: new Date().toISOString(),
    articles: []
  };

  for (const article of ARTICLES) {
    try {
      const linkedinPost = await generateLinkedInAngle(article);

      if (linkedinPost) {
        results.articles.push({
          id: article.id,
          title: article.title,
          slug: article.slug,
          linkedinPost: linkedinPost,
          generatedAt: new Date().toISOString(),
          ready: true
        });
      }
    } catch (err) {
      console.error(`Error processing article ${article.id}: ${err.message}`);
      results.articles.push({
        id: article.id,
        title: article.title,
        slug: article.slug,
        error: err.message,
        ready: false
      });
    }
  }

  // Save results
  const outputFile = path.join(WORKSPACE, 'content', 'article-linkedin-angles.json');
  await fs.mkdir(path.dirname(outputFile), { recursive: true });
  await fs.writeFile(outputFile, JSON.stringify(results, null, 2), 'utf-8');

  console.log(`\n✅ Scanned ${ARTICLES.length} articles`);
  console.log(`📊 Ready: ${results.articles.filter(a => a.ready).length}`);
  console.log(`❌ Failed: ${results.articles.filter(a => !a.ready).length}`);
  console.log(`📁 Output: ${outputFile}`);

  return results;
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  console.log('📰 Article-to-LinkedIn Scanner Starting...');
  console.log('='.repeat(60));

  const results = await scanArticles();

  console.log('\n📋 Summary:');
  console.log(JSON.stringify({
    totalArticles: ARTICLES.length,
    ready: results.articles.filter(a => a.ready).length,
    failed: results.articles.filter(a => !a.ready).length,
    outputFile: 'content/article-linkedin-angles.json'
  }, null, 2));

  process.exit(0);
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});

export { scanArticles, generateLinkedInAngle };
