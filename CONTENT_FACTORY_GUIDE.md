# Content Factory Pipeline - Complete Guide

Your autonomous content creation system is ready. Send one message and get a complete content package with research, draft, and delivery.

## 🚀 How to Use

### The Trigger Phrase

To kick off the entire pipeline, send a message like:

```
Content: AI agents for small business
```

or

```
Content: The future of remote work best practices
```

Format: `Content: [YOUR_TOPIC]`

To specify the content type (optional, defaults to blog-post):

```
Content: AI agents for small business | youtube-script
Content: Remote work | twitter-thread
Content: Data privacy | blog-post
```

### What Happens Next

1. **Research Agent spawns** (takes ~2-3 minutes)
   - Searches for trending angles on your topic
   - Analyzes 3 competitor pieces
   - Identifies common questions
   - Generates research brief

2. **Writing Agent spawns** (takes ~2-3 minutes)
   - Uses research as input
   - Writes complete content draft
   - Includes hook, structure, key takeaways, CTA

3. **Compilation** (instant)
   - Merges research + draft
   - Saves to `content/[topic]_[date].md`
   - Generates Telegram summary

4. **Delivery to Telegram** (instant)
   - Summary of findings
   - File path for full content
   - Ready to publish

## 📋 Content Types

### 1. Blog Post (Default)

**Length:** ~2,000-2,500 words  
**Structure:**
- Introduction with hook
- Definition & context
- Business impact with numbers
- How to get started (4 steps)
- Common mistakes
- Bottom line + CTA

**Best for:**
- SEO and long-form content
- Establishing thought leadership
- Detailed explanations

**File saved as:** `content/[topic]_[date].md`

---

### 2. YouTube Script

**Length:** ~7 minute script (1,800-2,000 words)  
**Structure:**
- 3-second hook
- Introduction
- 4 main sections (each ~1-2 min)
- Call to action
- Outro

**Includes:**
- Timestamp breakdowns
- Thumbnail suggestions
- Tag recommendations

**Best for:**
- Video content
- Building YouTube channel
- Tutorial/educational content

**File saved as:** `content/[topic]_[date]_youtube.md`

---

### 3. Twitter Thread

**Length:** 8-tweet thread  
**Structure:**
- Hook (Tweet 1)
- Problem/context (Tweet 2)
- Trend data (Tweet 3)
- Key insights (Tweets 4-6)
- Warning/gotcha (Tweet 7)
- CTA + engagement (Tweet 8)

**Includes:**
- Engagement tips
- Retweet strategy
- Performance tracking advice

**Best for:**
- Social media presence
- Quick distribution
- Building audience

**File saved as:** `content/[topic]_[date]_thread.md`

---

## 📊 Research Included

Every content piece includes a research brief with:

### 5 Trending Angles
Ranked by search interest and commercial intent. Includes:
- The angle itself
- Current trend (e.g., "45% MoM growth")
- Specific examples

**Example:**
- Angle: "The ROI Impact"
- Trend: "Growing search interest, 45% MoM increase"
- Examples: Cost savings case study, automation metrics

### 3 Competitor Pieces
Deep dive into what competitors are writing. For each:
- Title, source, URL
- Key points they cover
- Their strengths
- Gaps you can fill

**Example:**
- Competitor 1: "Expert Guide to [Topic]"
- Strengths: Comprehensive, data-driven
- Gaps: Limited competitor analysis, no challenges mentioned

### 5 Common Questions
What people search for about your topic. Includes:
- The question itself
- Search volume (High/Medium/Low)
- User intent (Educational vs. buying decision)

**Example:**
- "How much does [Topic] cost?" (High volume, purchasing intent)
- "Is [Topic] right for my business?" (High volume, evaluation intent)

### Strategic Recommendations
Opportunities and differentiation angles specific to your topic.

---

## 💾 Output Files

### File Location
```
~/.openclaw/workspace/content/[topic_slug]_[date].md
```

### What's Inside
1. **Metadata** - Topic, type, timestamp
2. **Full Research Brief** - All findings formatted
3. **Complete Content Draft** - Ready to publish
4. **Next Steps** - Publishing recommendations

### Example Filename
```
content/ai-agents-for-small-business_2026-02-22.md
content/remote-work-best-practices_2026-02-22_youtube.md
content/data-privacy-trends_2026-02-22_thread.md
```

---

## 📤 Telegram Delivery

When complete, you get a Telegram message like:

```
✅ Content Factory Complete

📌 Topic: AI agents for small business

📊 Research Findings:
- AI agents for small business: The ROI Impact
- Getting Started with AI agents for small business
- Search interest: Growing 45% MoM

❓ Top Questions:
1. What is AI agents for small business and how does it work?
2. How much does AI agents for small business cost?
3. Is AI agents for small business right for my business?

✍️ Content Draft: Ready for review
📄 File saved to: content/ai-agents-small-business_2026-02-22.md

Ready to publish!
```

---

## 🔄 The Pipeline Flow

```
User: "Content: [topic]"
  ↓
Detect trigger phrase
  ↓
Spawn Research Agent
  ├─ Find trending angles
  ├─ Analyze competitors
  └─ Identify common questions
  ↓
Receive research brief
  ↓
Spawn Writing Agent (with research as input)
  ├─ Generate hook
  ├─ Build content structure
  ├─ Add examples & insights
  └─ Create CTA
  ↓
Receive content draft
  ↓
Compile (merge research + draft)
  ↓
Save to file
  ↓
Send Telegram summary
  ↓
✅ DONE - Content ready to publish
```

---

## 🎯 Use Cases

### Content Marketing
```
Content: Email marketing automation | blog-post
```
→ Full blog post ready for your website
→ Optimized for SEO
→ Includes case studies & ROI data

### YouTube Channel Building
```
Content: How to start a podcast | youtube-script
```
→ Complete 7-minute script
→ Includes thumbnail suggestions
→ Ready to record

### Twitter Growth
```
Content: AI-powered customer service | twitter-thread
```
→ 8-tweet thread
→ Engagement optimization tips
→ Hashtag recommendations

### Product Launches
```
Content: New feature announcement | blog-post
```
→ Announcement post
→ Benefit/feature breakdown
→ CTA to try feature

---

## ✨ What Makes This Unique

✅ **Research-driven** - Every piece backed by competitor analysis + trend data  
✅ **Angle-focused** - Not generic, focused on what's trending  
✅ **Mistake-aware** - Includes what NOT to do  
✅ **Question-answering** - Addresses what people actually search for  
✅ **Multiple formats** - Blog, YouTube, Twitter (expand later)  
✅ **Ready to publish** - No additional editing needed  
✅ **Automated delivery** - Research + draft + file path all in one  

---

## 📋 Supported Content Types

Currently available:
- ✅ `blog-post` (2,000-2,500 words)
- ✅ `youtube-script` (7-minute script)
- ✅ `twitter-thread` (8-tweet thread)

Coming soon:
- LinkedIn post
- Email sequence
- Podcast outline
- Product copy
- Social media post pack

---

## 🚀 Getting Started

### Example 1: Blog Post

```
Content: The future of remote work
```

**Result:**
- Research brief with 5 trending angles
- 2,400-word blog post
- Saved to: `content/future-remote-work_[date].md`
- Telegram confirmation

### Example 2: YouTube Script

```
Content: Building a personal brand | youtube-script
```

**Result:**
- Research + competitor analysis
- 7-minute video script with timestamps
- Thumbnail ideas
- Saved to: `content/building-personal-brand_[date]_youtube.md`

### Example 3: Twitter Thread

```
Content: AI in healthcare | twitter-thread
```

**Result:**
- Research insights
- 8-tweet thread ready to schedule
- Engagement strategy
- Saved to: `content/ai-healthcare_[date]_thread.md`

---

## 📊 Files Created

| File | Purpose |
|------|---------|
| `scripts/content-factory-research.mjs` | Research sub-agent |
| `scripts/content-factory-write.mjs` | Writing sub-agent |
| `scripts/content-factory-orchestrate.mjs` | Pipeline coordinator |
| `content/` | Output folder |
| `CONTENT_FACTORY_GUIDE.md` | This file |

---

## 🔌 Integration With Your Workflow

### Telegram Trigger Detection

When you send a message starting with `Content:`, the system:

1. Detects the trigger phrase
2. Extracts the topic and content type
3. Spawns the research agent
4. Waits for completion
5. Spawns the writing agent
6. Compiles and delivers

**Automatic.** No additional commands needed.

---

## 📈 Next Steps

1. **Try it:** Send `Content: [your topic]` in chat
2. **Wait:** ~5-8 minutes for research + writing
3. **Review:** Open the saved file and check the draft
4. **Publish:** Copy to your blog, schedule on YouTube/Twitter, etc.
5. **Iterate:** Send `Content: [new topic]` for the next piece

---

**Your Content Factory is ready. Send a message starting with "Content:" to begin.** 🚀
