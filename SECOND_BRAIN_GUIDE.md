# Second Brain Knowledge Base - Complete Guide

Your personal knowledge base is now live. Save articles, videos, research, and any online content to your Second Brain, then search and retrieve it later.

## 🧠 What You Have

**Storage Structure:**
```
knowledge/
├── ai/              (AI, machine learning, automation)
├── business/        (SaaS, startups, entrepreneurship)
├── health/          (Fitness, nutrition, wellness)
├── research/        (Academic papers, in-depth studies)
├── market/          (Market analysis, trading, economics)
├── design/          (UI/UX, design systems, visual design)
├── other/           (Miscellaneous)
├── search.html      (Web interface)
└── index.json       (Search index)
```

**Three Components:**
1. **Ingestion:** Save URLs → Automatic extraction and storage
2. **Indexing:** Scans knowledge/ folder → generates search index
3. **Interface:** Web-based search, filter, and view interface

## 🚀 Quick Start

### Step 1: Save Your First Item

In chat with me, send:
```
Save this: https://example.com/article
```

I'll:
1. Fetch the full content
2. Extract title, summary, key takeaways
3. Save as Markdown to `knowledge/ai/` (or other category)
4. Confirm it's saved

### Step 2: Open the Search Interface

```bash
open ~/.openclaw/workspace/knowledge/search.html
```

You'll see:
- All saved items as cards
- Search box (search by title, content, tags)
- Category filter (click to filter)
- Statistics (total items, categories, tags)
- Click any card to view full details

### Step 3: Ask Me Questions

When you ask me something, I'll:
1. Search your knowledge base for relevant items
2. Use saved content to answer your question
3. Cite which item I got the info from

Example:
```
"What did I learn about AI frameworks?"
→ I search your knowledge base
→ Find relevant saved articles
→ Synthesize an answer with citations
```

## 💾 How to Save Content

### Method 1: Simple URL (Recommended)

```
Save this: https://example.com/article
```

I'll auto-detect the category (ai, business, etc.). If uncertain, it goes to `other/`.

### Method 2: With Category and Tags

```
Save this: https://example.com/article category:ai tags:ml,learning
```

This gives me explicit category and tags.

### What Gets Saved

For each saved item:
- **Title:** Extracted from page title or metadata
- **Source:** Domain + full URL
- **Date Saved:** Today's date
- **Summary:** First 500 characters of extracted content
- **Key Takeaways:** 3-5 bullet points from the content
- **Full Content:** Complete extracted text (first 10K chars)
- **Category:** ai, business, health, research, market, design, or other
- **Tags:** Custom tags you provide (e.g., #ml, #learning)

## 🔍 Search & Retrieve

### In the Web Interface

**Search:** Type to search title, content, tags
**Filter:** Click category chips to filter
**View:** Click any card to see full details
**Details:** 
- Full source link (clickable)
- All metadata
- Key takeaways
- Full content preview

### Ask Me in Chat

I'll proactively search your knowledge base:

```
User: "What did that article say about AI frameworks?"
Me: <searches knowledge base>
    <finds relevant items>
    <synthesizes answer with citations>
```

## 📁 File Structure

### Ingestion Script
```bash
node scripts/save-to-knowledge.mjs <url> [category] [tags]

# Examples:
node scripts/save-to-knowledge.mjs "https://example.com" ai "ml,learning"
node scripts/save-to-knowledge.mjs "https://news.com/article" market "trading"
```

### Indexing Script
```bash
node scripts/index-knowledge.mjs

# Scans knowledge/ folder and generates index.json
# Run after adding new items manually
```

### Web Interface
```
knowledge/search.html  - Open this in browser
knowledge/index.json   - Search index (auto-generated)
```

## 🏷️ Categories

Use these when saving items:

| Category | Use For |
|----------|---------|
| **ai** | AI, machine learning, LLMs, automation |
| **business** | SaaS, startups, entrepreneurship, growth |
| **health** | Fitness, nutrition, wellness, longevity |
| **research** | Academic papers, in-depth studies, data |
| **market** | Stock market, trading, economics, macro |
| **design** | UI/UX, design systems, visual design |
| **other** | Miscellaneous or uncategorized |

## 📝 Example Workflow

### Scenario: You Find an Interesting Article

1. **In chat:** `Save this: https://www.example.com/article`
2. **I respond:**
   ```
   ✅ Knowledge saved!
   Title: The Future of AI-Powered Frameworks
   Category: ai
   File: knowledge/ai/1708582253-future-ai-frameworks.md
   ```

3. **You ask later:** `What did that article about AI frameworks say?`
4. **I respond:**
   ```
   From your saved article "The Future of AI-Powered Frameworks":
   - AI frameworks reduce decision uncertainty
   - Automation allows focus on strategy
   - Human oversight remains critical
   
   Source: The Future of AI-Powered Frameworks
   ```

### Scenario: Research Project

1. Save 10 related articles about market structure
2. Open search.html → filter by `market` tag
3. Read all summaries and takeaways
4. Ask me: "What patterns do these articles share?"
5. I synthesize your saved knowledge

## 🔐 Privacy & Storage

- All data is **local** (no cloud sync)
- Markdown files stored in `knowledge/` folder
- Full content is extracted and stored (not just links)
- You own all your data
- Can back up entire `knowledge/` folder anytime

## 🛠️ Advanced Usage

### Manual Addition (Without Chat)

```bash
# Create a knowledge item manually
cat > ~/.openclaw/workspace/knowledge/ai/my-notes.md << 'EOF'
# Title of Article

**Source:** [example.com](https://example.com)
**Date Saved:** 2026-02-22
**Category:** ai
**Tags:** #ai #learning

## Summary
Your summary here...

## Full Content
Your notes here...
EOF

# Re-index to add to search
node scripts/index-knowledge.mjs
```

### Batch Saving

```bash
# Save multiple URLs in a row
Save this: https://article1.com
Save this: https://article2.com
Save this: https://article3.com

# I'll save all three and confirm each one
```

### Update Index Manually

```bash
cd ~/.openclaw/workspace
node scripts/index-knowledge.mjs
```

Generates fresh `index.json` from all .md files in knowledge/ folder.

## 📊 How It Works Behind the Scenes

1. **Parse Request:** You send "Save this: [URL]"
2. **Fetch Content:** I fetch the full HTML
3. **Extract:** Remove HTML tags, extract text
4. **Summarize:** Generate summary + key takeaways
5. **Categorize:** Guess category from content (or you specify)
6. **Save:** Create Markdown file in `knowledge/[category]/`
7. **Index:** Re-index the knowledge base
8. **Confirm:** Tell you it's saved

The Markdown file includes:
- Metadata (title, source, date, tags, category)
- Summary section
- Key takeaways
- Full extracted content

## ✨ Features

✅ Automatic content extraction from URLs
✅ Intelligent categorization (or manual)
✅ Key takeaways generation
✅ Full-text indexing for search
✅ Web interface with filtering
✅ Citation tracking (where did I learn this?)
✅ Custom tagging
✅ Local storage (no cloud)
✅ Markdown-based (easy to edit/read)
✅ Integrates with my response system (I cite sources)

## 📋 Next Steps

1. **Open the interface:** `open knowledge/search.html`
2. **Save your first item:** `Save this: [URL]`
3. **Check it's there:** Refresh search.html
4. **Save more items:** Build up your knowledge base
5. **Search and filter:** Use the web interface
6. **Ask me questions:** I'll cite sources from your saved content

---

## 🚀 Files Created

| File | Purpose |
|------|---------|
| `knowledge/` | Main folder for all knowledge items |
| `knowledge/search.html` | Web interface for searching |
| `knowledge/index.json` | Auto-generated search index |
| `scripts/save-to-knowledge.mjs` | Ingestion script |
| `scripts/index-knowledge.mjs` | Indexing script |
| `SECOND_BRAIN_GUIDE.md` | This file |

---

**Your Second Brain is ready. Start saving!** 🧠

First item: `Save this: https://example.com`
