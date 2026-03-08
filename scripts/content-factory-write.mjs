#!/usr/bin/env node

/**
 * Content Factory - Writing Agent
 * 
 * Writes content based on research brief
 * 
 * Usage (content type can be: youtube-script, blog-post, twitter-thread):
 *   node scripts/content-factory-write.mjs "[TOPIC]" "[CONTENT_TYPE]" "[RESEARCH_JSON]"
 * 
 * Example:
 *   node scripts/content-factory-write.mjs "AI agents" "blog-post" '{"topic":"AI agents",...}'
 */

function generateYoutubeScript(topic, research) {
  return `# YouTube Script: ${topic}

## Hook (0-3 seconds)
"${research.trendingAngles[0].angle} — but most people get it completely wrong. In this video, I'll show you exactly how to [benefit from ${topic}] in your business, with real numbers backing it up."

---

## Introduction (3-30 seconds)
Hi, I'm [Your Name]. If you're looking at ${topic} right now, you're probably wondering:
- "Is this actually worth the investment?"
- "How do I get started?"
- "What am I missing?"

By the end of this video, you'll have a clear framework for understanding ${topic} and deciding if it's right for you. Let's dive in.

---

## Main Content - Section 1: What is ${topic}? (1:00-2:30)
${research.commonQuestions[0].question}

[Explain the concept simply]
- Definition: [clear explanation]
- How it works: [step-by-step overview]
- Why it matters now: [context and timing]

Key Point: ${research.recommendations[0].insight}

---

## Main Content - Section 2: The Business Impact (2:30-4:00)
${research.trendingAngles[0].angle}

[Show the numbers]
- Cost savings: [x% reduction]
- Time savings: [x hours/week]
- Revenue impact: [specific example]

Real example: [Case study from competitor research]

---

## Main Content - Section 3: How to Get Started (4:00-5:30)
${research.commonQuestions[4].question}

Step 1: Assess your needs
Step 2: Research options
Step 3: Start small
Step 4: Scale based on results

Common mistake: ${research.commonQuestions[3].question}
Avoid these pitfalls: [List key challenges]

---

## Main Content - Section 4: What to Avoid (5:30-6:30)
The mistakes people make when implementing ${topic}:
1. [Mistake 1 from competitor gaps]
2. [Mistake 2 from competitor gaps]
3. [Mistake 3 from competitor gaps]

---

## Call to Action (6:30-6:45)
If you found this helpful, hit the subscribe button and turn on notifications. I post weekly videos about [your domain]. 

Drop a comment: Are you considering ${topic}? What's your biggest question?

For more resources, check the description.

---

## Outro (6:45-7:00)
Thanks for watching. See you in the next one.

---

**Video Length Target:** 7 minutes
**Suggested Thumbnail:** "[Key number or stat] You Didn't Know About ${topic}"
**Tags:** ${topic}, ${research.trendingAngles[1].angle}, small business
`;
}

function generateBlogPost(topic, research) {
  return `# ${research.trendingAngles[0].angle}

**Published:** ${new Date().toLocaleDateString()}  
**Reading Time:** ~8 minutes

---

## Introduction

${research.trendingAngles[0].angle} is more than a buzzword—it's becoming essential for businesses of all sizes. But here's what most people get wrong: they jump in without understanding the real impact.

In this post, I'll break down:
- What ${topic} actually is (and isn't)
- The real ROI for businesses
- How to get started without wasting money
- Common mistakes to avoid

Let's start with the basics.

---

## What is ${topic}?

### Definition
${research.commonQuestions[0].question}

${topic} is [clear, jargon-free explanation]. Unlike traditional approaches, ${topic} [key differentiator].

### How It Works

Think of it this way: [accessible metaphor]

The process typically involves:
1. [Step 1]
2. [Step 2]
3. [Step 3]

### Why This Matters Now

${research.trendingAngles[0].trend}

Three factors are driving adoption:
1. **Economic pressure:** Businesses need efficiency
2. **Technology maturity:** Tools are now accessible
3. **Proven ROI:** Early adopters show real results

---

## The Business Impact

### Key Numbers

Research shows businesses using ${topic} see:
- **${research.trendingAngles[0].examples[0]}**: [specific metric]
- **${research.trendingAngles[0].examples[1]}**: [specific metric]

### Real Example: Case Study

[From competitor research: what worked and why]

The key insight: [learning from their approach]

---

## How to Get Started

### Step 1: Assess Your Situation

${research.commonQuestions[2].question}

Ask yourself:
- [Assessment question 1]
- [Assessment question 2]
- [Assessment question 3]

### Step 2: Research Your Options

${research.commonQuestions[3].question}

Top platforms/approaches:
1. [Option 1]: [pros/cons]
2. [Option 2]: [pros/cons]
3. [Option 3]: [pros/cons]

### Step 3: Start Small

Don't bet the farm. Instead:
- Choose a pilot use case
- Set clear metrics
- Plan for 30-day test period

### Step 4: Scale Based on Results

Once you see wins, scale:
- Expand to additional use cases
- Invest in team training
- Integrate more deeply

---

## Mistakes to Avoid

### 1. [Common Mistake 1]
**Why it fails:** [explanation]  
**How to avoid it:** [solution]

### 2. [Common Mistake 2]
**Why it fails:** [explanation]  
**How to avoid it:** [solution]

### 3. [Common Mistake 3]
**Why it fails:** [explanation]  
**How to avoid it:** [solution]

---

## The Bottom Line

${topic} isn't a silver bullet—it's a tool. The right tool, used correctly, can deliver significant value.

**Key Takeaways:**
- ${topic} is [one-line summary]
- ROI is real, but depends on implementation
- Start small, measure, scale

**Ready to explore ${topic}?**

[Call to action: Download checklist / Schedule call / Read case study]

---

**Questions?** Drop a comment below. I read and respond to every one.

**Want more?** Subscribe to my newsletter for weekly insights on [your domain].

---

*What's your experience with ${topic}? Have you seen the benefits firsthand? Share in the comments.*
`;
}

function generateTwitterThread(topic, research) {
  const threadLength = 8; // 8-tweet thread
  
  return `# Twitter Thread: ${topic}

## Tweet 1 (Hook)
${research.trendingAngles[0].angle}?

Most people get this completely wrong. I spent [time period] researching this and found [surprising insight].

Let me share what I learned 🧵
[#${topic.replace(/\\s+/g, '')}]

---

## Tweet 2 (Problem)
Here's the disconnect:

Everyone talks about the benefits of ${topic}.

But nobody talks about the [gap from competitor research].

That's where most implementations fail.

---

## Tweet 3 (Trend)
${research.trendingAngles[0].trend}

This isn't hype. The numbers back it up:
- [stat 1]
- [stat 2]  
- [stat 3]

---

## Tweet 4 (Key Insight 1)
First thing to understand:

${research.commonQuestions[0].question}

In simple terms: [one-sentence explanation]

The impact? [consequence or benefit]

---

## Tweet 5 (Key Insight 2)
Second thing:

${research.trendingAngles[0].examples[0]}

This matters because [why it's important].

Most businesses miss this entirely.

---

## Tweet 6 (Warning)
Before you jump in, know this:

The biggest mistake people make with ${topic}?

${research.recommendations[2].insight}

Don't be that person.

---

## Tweet 7 (Action)
If you're thinking about implementing ${topic}:

1. Start here: [resource]
2. Then assess: [assessment question]
3. Finally: [action step]

It's that simple.

---

## Tweet 8 (CTA + Engagement)
That's the thread.

Big thanks to [research sources] for the insights.

Thoughts? Have you experienced ${topic}? Reply with your biggest question—I read every one.

[Link to full blog post / resource]

---

**Engagement Tips:**
- Pin Tweet 1 for visibility
- Retweet the thread yourself
- Follow up with detailed replies to comments
- Track performance over 48 hours
`;
}

async function main() {
  const topic = process.argv[2];
  const contentType = (process.argv[3] || 'blog-post').toLowerCase();
  const researchJson = process.argv[4];
  
  if (!topic) {
    process.stderr.write('Usage: node content-factory-write.mjs "[TOPIC]" "[youtube-script|blog-post|twitter-thread]" "[RESEARCH_JSON]"\n');
    process.exit(1);
  }
  
  try {
    let research = {};
    if (researchJson) {
      research = JSON.parse(researchJson);
    }
    
    let content = '';
    
    switch(contentType) {
      case 'youtube-script':
        content = generateYoutubeScript(topic, research);
        break;
      case 'twitter-thread':
        content = generateTwitterThread(topic, research);
        break;
      case 'blog-post':
      default:
        content = generateBlogPost(topic, research);
        break;
    }
    
    process.stdout.write(content);
    
  } catch (error) {
    process.stderr.write(`Writing failed: ${error.message}\n`);
    process.exit(1);
  }
}

main();
