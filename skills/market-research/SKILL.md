---
name: market-research
description: Conduct asynchronous market research across Reddit, X, and other platforms. Deliver synthesized reports via email. Optimized for the voice note → research → email report workflow.
---

# Market Research Skill

## Hedgehog Alignment

This skill embodies the core Hedgehog principle: **turning complex, high-stakes uncertainty into clear, actionable decisions**. Market research reduces uncertainty about customer needs, competitive landscape, and market opportunities. The asynchronous workflow creates leverage by allowing deep research while the human focuses on other high-value work.

## Why This Workflow Works

Based on real-world testing, this skill excels because:

| Factor | Benefit |
|--------|---------|
| **Latency as Feature** | Research tasks naturally take time; async delivery feels like delegating to a human employee |
| **Multimodal Input** | Voice notes allow quick, detailed task assignment while on the go |
| **Structured Output** | Email reports provide permanent, searchable documentation |
| **High-Quality Synthesis** | LLMs excel at synthesizing information from multiple sources into actionable insights |

## Supported Research Types

### Product Research
- What do users want from [product/category]?
- What pain points exist in [market]?
- How do users describe their ideal solution?

### Competitive Research
- What are people saying about [competitor]?
- What features do users wish [competitor] had?
- Where are competitors falling short?

### Market Validation
- Is there demand for [idea/feature]?
- What objections do potential users raise?
- What adjacent problems exist?

### Trend Analysis
- What topics are gaining traction in [space]?
- What emerging tools/techniques are people discussing?
- What shifts are happening in [industry]?

## Command Patterns

### Voice Note Workflow (Recommended)

Send a voice note via Telegram with your research request:

> "Go on Reddit and X. Find what people want from [topic]. Look at [specific subreddits or hashtags]. Email me a report with the key insights, pain points, and opportunities."

### Text Command Workflow

```
research [topic] on [platforms] for [purpose]
```

Examples:
- `research caregiver apps on Reddit for Kinlet feature ideas`
- `research fintech design systems on X for Design System positioning`
- `research SaaS onboarding on Reddit for Cultivate improvements`

## Research Process

When I receive a research request, I will:

1. **Clarify scope** (if needed): Confirm platforms, timeframe, and specific focus areas
2. **Gather data**: Search relevant subreddits, X hashtags, forums, and discussions
3. **Identify patterns**: Group findings into themes and insights
4. **Synthesize**: Create a structured report with actionable recommendations
5. **Deliver**: Email the report to your inbox with a Telegram notification

## Report Structure

All research reports follow this format:

```markdown
# [Topic] Research Report
**Date**: [Date]
**Platforms**: [Reddit, X, etc.]
**Focus**: [Specific question or area]

## Executive Summary
[2-3 sentences with the key takeaway]

## Key Insights
### Insight 1: [Title]
[Description with supporting evidence]
- Source: [Link]

### Insight 2: [Title]
[Description with supporting evidence]
- Source: [Link]

[Continue for 3-5 key insights]

## Pain Points Identified
| Pain Point | Frequency | Severity | Opportunity |
|------------|-----------|----------|-------------|
| [Issue 1]  | High/Med/Low | High/Med/Low | [How to address] |

## Opportunities
[Specific opportunities aligned with Hedgehog concept]

## Recommendations
1. [Actionable recommendation 1]
2. [Actionable recommendation 2]
3. [Actionable recommendation 3]

## Raw Sources
[Links to all referenced discussions]
```

## Platform-Specific Strategies

### Reddit Research
- Focus on niche subreddits over large ones
- Look for complaint threads and "I wish..." posts
- Check r/[industry] and r/[tool] subreddits
- Search for specific product mentions

### X (Twitter) Research
- Search hashtags and keywords
- Look at replies to industry influencers
- Check what's being shared and discussed
- Monitor relevant accounts

### Other Platforms
- Product Hunt comments and discussions
- Hacker News threads
- Industry-specific forums
- LinkedIn discussions (if accessible)

## Proactive Research

I will autonomously conduct research in these scenarios:

| Trigger | Research Focus |
|---------|----------------|
| Weekly (Sunday) | Trends in AI, trading, SaaS, design systems, caregiver tech |
| New feature discussion | Validation research on the proposed feature |
| Competitor mention | Competitive analysis on mentioned company |
| User feedback received | Pattern analysis across similar feedback |

## Integration with Projects

### For Kinlet
- Caregiver communities: r/Alzheimers, r/dementia, r/CaregiverSupport
- Focus: Pain points, feature requests, emotional needs

### For Cultivate
- SaaS communities: r/SaaS, r/startups, r/Entrepreneur
- Focus: Business operating system needs, workflow pain points

### For Design System
- Design communities: r/UI_Design, r/userexperience, Fintech Twitter
- Focus: Component needs, accessibility patterns, fintech-specific requirements

### For Swing Trading
- Trading communities: r/swingtrading, r/stocks, FinTwit
- Focus: Strategy discussions, tool preferences, market sentiment

## Quality Standards

Every research report must:

- Include at least 5 distinct sources
- Provide specific quotes and examples
- Connect findings to Hedgehog concept
- Offer actionable recommendations
- Be delivered within 2 hours of request (unless specified otherwise)

## Limitations

This skill works best for:
- Qualitative research and sentiment analysis
- Pattern identification across discussions
- Opportunity discovery and validation

This skill is NOT ideal for:
- Quantitative market sizing
- Real-time data requiring API access
- Proprietary or paywalled content
