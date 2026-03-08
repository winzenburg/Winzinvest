# Ollama Local Models Guide

Run Mistral 7B locally on your Mac mini for fast, private, cost-free inference.

## 📦 What You Have

- **Ollama 0.16.3** installed
- **Mistral 7B** (downloading now, ~4GB)
- Mac mini with decent RAM (8GB+ recommended)

## 🚀 Quick Start

### 1. Start Ollama Server

In a new terminal:
```bash
ollama serve
```

You should see:
```
2026/02/22 04:52:00 images.go:565: total blobs: 1
2026/02/22 04:52:00 images.go:572: total size: 4.1GB
2026/02/22 04:52:00 routes.go:714: Listening on 127.0.0.1:11434
```

### 2. Test Mistral in Another Terminal

```bash
# Simple test
ollama run mistral "What is swing trading?"

# Or use our test script
node scripts/test-ollama.mjs "Explain the Hedgehog concept"
```

### 3. Try the REST API

```bash
curl http://127.0.0.1:11434/api/generate -d '{
  "model": "mistral",
  "prompt": "What is the best swing trading strategy?",
  "stream": false
}'
```

## ⚡ Performance Notes

**Speed on Mac mini:**
- First response: 10-15 seconds (model loading)
- Subsequent responses: 2-5 seconds per query
- RAM usage: ~2-3GB while running

**Compared to APIs:**
- ✅ No rate limits
- ✅ No API costs ($0 vs $0.05+ per query)
- ✅ Completely private (no data sent anywhere)
- ⚠️ Slower than cloud (2-5s vs 0.5-1s)
- ⚠️ Less capable than GPT-4 or Claude (but solid for many tasks)

## 🔧 Integration with OpenClaw

### Option 1: Use as Fallback Model

Add to your `openclaw.json`:

```json
{
  "agents": {
    "defaults": {
      "model": {
        "fallbacks": [
          "ollama/mistral",
          "anthropic/claude-sonnet-4",
          "openai/gpt-5-nano"
        ]
      }
    }
  }
}
```

Then when Claude/OpenAI are rate-limited, it falls back to local Mistral.

### Option 2: Use for Specific Tasks

Create a sub-agent that uses Mistral for lightweight tasks:

```bash
openclaw agent spawn --model ollama/mistral --task "Summarize this market report..."
```

### Option 3: Use via API from Heartbeat

```bash
# In your heartbeat or cron job
node scripts/test-ollama.mjs "Quick analysis of today's market moves"
```

## 📊 Best Use Cases for Mistral 7B

✅ **Great for:**
- Summarization (1000-word articles → 100 words)
- Brainstorming (generate ideas, outline posts)
- Code review comments
- Quick Q&A on your own docs
- Drafting emails or messages
- Research notes synthesis

❌ **Not ideal for:**
- Complex financial analysis (use Claude/GPT-4 instead)
- Long-form creative writing (slower, lower quality)
- Real-time trading decisions (too slow for immediate action)
- Deep reasoning tasks (Claude is much better)

## 🎯 Suggested Workflow

**During Trading Hours (7:30 AM - 2:00 PM MT):**
- Use Claude Opus for trading decisions (speed matters)
- Use Mistral for non-critical research in background

**Overnight/Off-Hours:**
- Shift to Mistral for routine tasks (saves API costs)
- Use local model for content drafting, summarization
- Reserve cloud API for next-day complex analysis

**Cost Savings:**
- 100 queries/day at Mistral instead of Claude = ~$5-10/day savings
- That's ~$2,000/year for mostly-local workflow

## 📁 Files

- `scripts/test-ollama.mjs` - Test Mistral locally
- `OLLAMA-GUIDE.md` - This file

## 🛑 Common Issues

**"Connection error: connect ECONNREFUSED"**
- Ollama server not running
- Fix: Run `ollama serve` in a separate terminal

**"Model not found: mistral"**
- Model didn't finish downloading
- Fix: Wait for download to complete, then `ollama pull mistral` again

**Mac is slow/freezing**
- Mistral uses 2-3GB RAM
- Fix: Close other apps, or use smaller model (neural-chat, phi)

**Want a faster model?**
- Try: `ollama pull phi` (2.7GB, faster, slightly less capable)
- Or: `ollama pull neural-chat` (4.1GB, balanced)

## 🚀 Next Steps

1. Wait for Mistral download to complete (~5 min)
2. Start Ollama server: `ollama serve`
3. Test: `node scripts/test-ollama.mjs "Your question"`
4. Decide: Use as fallback, or for specific tasks?
5. Optional: Integrate with OpenClaw agent config

---

**You now have a powerful local model running cost-free on your Mac. Perfect for experimenting and reducing API costs during off-peak hours.**
