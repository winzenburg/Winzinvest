# Trump/Policy News Monitoring System

**Objective:** Track market-moving policy announcements from Trump/administration  
**Sources:** X (@realDonaldTrump), Truth Social, White House announcements  
**Impact Levels:** CRITICAL (trading halt) → HIGH (position adjust) → MEDIUM (monitor) → LOW  
**Delivery:** Real-time Telegram alerts during market hours

---

## 1. WHAT WE'RE MONITORING

### CRITICAL Impact (🚨 Immediate Action)
- Tariff announcements (China, Mexico, Canada, EU)
- Fed policy directives (rate cuts/hikes)
- Major trade war escalations
- Emergency economic policies

**Market Effect:** +/- 2-5% intraday moves, sector rotations, gap opens

### HIGH Impact (⚠️ Position Adjustment)
- Tax reform proposals
- Trade agreements/deal announcements
- Deregulation moves (energy, finance, tech)
- Stock market comments (public pressure on markets)

**Market Effect:** Sector rotation, sector leaders shift

### MEDIUM Impact (📢 Monitor Closely)
- General policy direction signals
- Inflation/employment commentary
- Corporate tax guidance
- Stimulus announcements

**Market Effect:** Multi-day trend development

---

## 2. THREE-TIER SETUP (Easy → Comprehensive)

### TIER 1: Manual Alerts (5 minutes/day) ✅ EASIEST
**How it works:**
1. You check X/Truth Social manually
2. Forward market-moving posts to me
3. I classify impact and send Telegram alert
4. System adjusts positions automatically

**Setup:** None required. Start immediately.

**Example:**
```
User: "Trump just announced 25% tariffs on China starting Monday"
Agent: Sends CRITICAL alert to Telegram
       Recommends: Reduce Tech exposure, increase Energy
       Trading system: Adjusts position limits based on regime
```

### TIER 2: RSS Feed Monitoring (Hands-off) 🔄 MEDIUM
**How it works:**
1. Monitor RSS feeds from news sources
2. Filter for Trump/policy keywords
3. Auto-classify impact
4. Send alerts automatically

**Setup Required:**
```bash
pip install feedparser

# Monitor these feeds:
- White House: https://www.whitehouse.gov/feed/
- News aggregators (Reuters, Bloomberg, CNBC)
- Policy-focused sources
```

**Pros:** Automatic, covers major announcements  
**Cons:** Misses live X/Truth Social posts, slight delay

### TIER 3: Full API Monitoring (Real-time) 🚀 COMPREHENSIVE
**How it works:**
1. Twitter API v2 monitoring (@realDonaldTrump)
2. Truth Social scraping/API
3. Real-time alerts (< 1 minute latency)
4. Auto-execute position adjustments

**Setup Required:**

#### Step A: Twitter API v2
```
1. Go to: https://developer.twitter.com/
2. Create app "TrumpNewsMonitor"
3. Get Bearer Token
4. Add to .env:
   TWITTER_BEARER_TOKEN=<your_token>
5. Query: from:@realDonaldTrump -is:retweet
   Endpoint: /2/tweets/search/recent
```

#### Step B: Truth Social Monitoring
```
Option 1: Use web scraping (beautifulsoup)
  pip install beautifulsoup4 requests
  Monitor: https://truthsocial.com/@realDonaldTrump
  
Option 2: Truth Social API (if available)
  Check: https://truthsocial.com/api/docs
  Similar to X API v2
```

#### Step C: Schedule Monitoring
```
# Every 5 minutes during market hours
*/5 7-14 * * 1-5 python3 ~/.openclaw/workspace/trading/scripts/trump_news_monitor.py
```

---

## 3. KEYWORD TRACKING

### Tariff-Related 🎯
- "tariff", "tariffs", "import tax", "trade war"
- **Impact:** CRITICAL
- **Sectors Affected:** Tech, Manufacturing, Consumer, Energy

### Trade Policy 🤝
- "trade deal", "trade agreement", "NAFTA", "USMCA", "WTO"
- **Impact:** HIGH
- **Sectors Affected:** Manufacturing, Energy, Agriculture, Technology

### Tax Policy 💰
- "tax cut", "tax reform", "corporate tax", "capital gains"
- **Impact:** HIGH
- **Sectors Affected:** All (broad market impact)

### Fed Policy 🏦
- "Fed should", "interest rates", "rate cut", "rate hike"
- **Impact:** CRITICAL
- **Sectors Affected:** All (systematic impact)

### Deregulation ⚙️
- "deregulation", "EPA", "SEC rule", "environmental"
- **Impact:** MEDIUM
- **Sectors Affected:** Energy, Manufacturing, Finance, Healthcare

### Stimulus 🚧
- "stimulus", "infrastructure", "spending bill", "jobs"
- **Impact:** HIGH
- **Sectors Affected:** Construction, Energy, Technology

### Market Commentary 📈
- "stock market", "market crash", "market surge", "DOW", "NASDAQ"
- **Impact:** MEDIUM
- **Sectors Affected:** All (sentiment indicator)

---

## 4. ALERT ACTIONS

### CRITICAL Alerts (🚨)
**Action:** Pause new trades, review current exposure

```
Typical triggers:
- New tariff announcement
- Fed policy change proposal
- Major trade war escalation
- Emergency economic action

What we do:
1. Pause webhook (kill switch)
2. Alert you via Telegram with analysis
3. Review sector exposure
4. Adjust position limits if regime changes
5. Wait for market reaction before resuming
```

### HIGH Alerts (⚠️)
**Action:** Monitor sector rotation, prepare position adjustments

```
Typical triggers:
- Tax reform proposals
- Trade deal announcements
- Deregulation moves

What we do:
1. Send Telegram alert with sector recommendations
2. Suggest position adjustments (reduce exposure to affected sectors)
3. Monitor for follow-up announcements
4. Track sector leader rotations
```

### MEDIUM/LOW Alerts (📢/📌)
**Action:** Monitor, no immediate position changes

```
What we do:
1. Log in news system
2. Track as context for regime changes
3. Mention in daily portfolio email
4. Use for longer-term positioning
```

---

## 5. RECOMMENDED APPROACH (Hybrid)

**Week 1:** Start with TIER 1 (Manual) - Get feel for volume/frequency  
**Week 2:** Implement TIER 2 (RSS) - Automate news source monitoring  
**Week 3+:** Full TIER 3 (APIs) - Real-time X/Truth Social tracking  

**Why hybrid?**
- APIs require setup and have rate limits
- Manual gives you control and understanding
- RSS provides reliable baseline
- Full automation adds responsiveness

---

## 6. IMMEDIATE SETUP (Monday)

### To Start TIER 1 (Today/Monday):
1. Add Trump monitoring to your daily routine
2. Check X: https://twitter.com/realDonaldTrump (morning + midday)
3. Check Truth Social: https://truthsocial.com/@realDonaldTrump
4. Forward any market-moving posts to me
5. I'll send automatic alerts + adjust trading system

### To Implement TIER 2 (This Week):
```bash
pip install feedparser
python3 ~/.openclaw/workspace/trading/scripts/trump_news_monitor.py
```

### To Implement TIER 3 (Next Week):
1. Apply for Twitter API v2 access
2. Set up Truth Social scraping
3. Configure `.env` with credentials
4. Schedule monitoring every 5 minutes
5. Test with dummy announcements

---

## 7. INTEGRATION WITH TRADING SYSTEM

### Alert Flow
```
X/Truth Social Post
    ↓
Classify Impact Level (CRITICAL/HIGH/MEDIUM/LOW)
    ↓
Send Telegram Alert
    ↓
If CRITICAL:
  - Pause webhook (kill switch)
  - Alert you with analysis
  - Wait for confirmation
    ↓
If HIGH:
  - Send alert with sector recommendations
  - Suggest position adjustments
  - Continue monitoring for follow-ups
    ↓
If MEDIUM/LOW:
  - Log to news system
  - Include in daily portfolio email
  - Use for context only
    ↓
Resume trading (when appropriate)
```

### Position Adjustment Logic

**Tariff Announcement (e.g., China tariffs):**
- Reduce: Tech (chip makers, cloud), Consumer discretionary
- Increase: Energy (domestic substitution), Finance (lower growth)
- Watch: Earnings guidance changes

**Tax Reform (e.g., corporate tax cut):**
- Increase: Financials (higher returns), Tech (capex spending)
- Reduce: Utilities (defensive), Consumer staples
- Impact: Entire market rally likely

**Fed Policy Change (e.g., rate cut):**
- Market-wide impact
- Reduce: Financials (lower spreads), Utilities (bond competition)
- Increase: Growth tech, unprofitable growth
- Impact: Entire portfolio regime shift

---

## 8. EXAMPLE ALERT FLOW

**Monday 10:35 AM MT**
```
📰 Trump posts on X:
"Announcing 25% tariffs on China effective next Monday. 
This will boost American manufacturing and jobs. 
Stock market will love this!"

🚨 My response:
🚨 CRITICAL - Trump Tariff Announcement

📝 Post: Announcing 25% tariffs on China...

🎯 Topics: Tariffs, Trade Policy
⏰ Time: 10:35 AM MT
📱 Source: X (@realDonaldTrump)

🔄 Action Recommended:
- Check affected sectors: Tech, Manufacturing, Energy, Consumer
- Monitor position exposure to tariff-sensitive stocks
- Be ready to adjust if market gaps on open
- Watch sector rotation patterns

Suggested adjustments:
→ Reduce Tech exposure (chip makers)
→ Increase Energy exposure
→ Monitor earnings guide changes
→ Stand by for market reaction
```

---

## 9. MONITORING SCHEDULE

| Time | Action | Frequency |
|------|--------|-----------|
| 7:30 AM | Market open, check X/Truth Social | Daily |
| 10:00 AM | Mid-morning check | Daily |
| 12:00 PM | Midday scan | Daily |
| 2:00 PM | Before market close | Daily |
| 4:00 PM | After hours review | Daily |

**Automated (if TIER 2+):** Every 5 minutes during 7:30-14:00 MT

---

## 10. NEXT STEPS

**Pick your tier:**
- **TIER 1 (Manual):** Start immediately, no setup
- **TIER 2 (RSS):** Set up this week
- **TIER 3 (Full API):** Set up next week

**I recommend:** Start with TIER 1 tomorrow, add TIER 2 this week, upgrade to TIER 3 when APIs are set up.

---

## File Locations

- Main script: `~/.openclaw/workspace/trading/scripts/trump_news_monitor.py`
- Alerts log: `~/.openclaw/workspace/trading/logs/trump_news.json`
- This guide: `~/.openclaw/workspace/trading/TRUMP_MONITORING_SETUP.md`

**Ready to start Monday.** 🚀
