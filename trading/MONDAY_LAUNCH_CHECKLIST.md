# Monday Launch Checklist (Feb 24, 2026)

**Status:** ✅ ALL SYSTEMS READY  
**Go-Live:** Monday 7:30 AM MT  
**Objective:** Execute first trades using new strategy with complete rule set

---

## PRE-MARKET (Before 7:30 AM MT)

### Infrastructure Verification ✅
- [ ] OpenClaw gateway running (LaunchAgent loaded)
- [ ] IB Gateway connected (port 4002 open)
- [ ] Webhook listener running (port 5001)
- [ ] Daily portfolio email scheduled (4 PM)
- [ ] Weekly review scheduled (Friday 5 PM)
- [ ] Trump monitor scheduled (7:30, 10, 12, 2 PM)

### Security Check ✅
- [ ] .env file readable only by owner (600 permissions)
- [ ] .env in .gitignore
- [ ] Audit logging active
- [ ] Kill switch (.pause file) ready if needed

### Market Data Check ✅
- [ ] TradingView: AMS Screener NX deployed
- [ ] TradingView: AMS Trade Engine NX deployed
- [ ] Screener generating signals daily
- [ ] Indicator generating entry/exit signals

### Trading Rules Confirmed ✅
- [ ] Position sizing rules loaded (TRADING_RULES.md)
- [ ] Entry/exit criteria understood
- [ ] Stop loss rules confirmed (1.5x ATR)
- [ ] Concentration limits understood (25% sector, 8% stock)
- [ ] Daily loss limit confirmed (-$1,350)
- [ ] Covered call rules ready (>5% gain, ≥3 days)
- [ ] Cash-secured put rules ready (pullbacks 3-8%)

### Alert System Ready ✅
- [ ] Telegram bot token in .env
- [ ] Telegram chat ID in .env
- [ ] Email (Resend API) configured
- [ ] Backup alert system tested
- [ ] SMS phone number confirmed (303-359-3744)

### Monitoring Systems Ready ✅
- [ ] Regime monitor ready (5 indicators)
- [ ] Policy monitor ready (TIER 1 manual)
- [ ] Options scan ready (3 PM daily)
- [ ] News monitor ready
- [ ] Trade journal ready

---

## MARKET OPEN (7:30 AM MT - 2:00 PM MT)

### Live Monitoring
- [ ] Check regime score (should update every 30 min)
- [ ] Monitor screener for first signals
- [ ] First trade entry: Use 1 canary share to validate
- [ ] Watch for policy alerts
- [ ] Monitor daily P&L (don't exceed -$1,350)

### First Trade Protocol
1. **Signal Fires:** Screener says "Ready" + AMS indicator fires entry
2. **Check All Filters:**
   - Macro regime: Risk-On or Neutral? ✅
   - Policy: No CRITICAL alerts? ✅
   - Trading window: 7:30 AM - 2:00 PM? ✅
   - Concentration: Sector/stock limits OK? ✅
   - Position count: Under limit? ✅
3. **Enter Canary:** 1 share position
4. **Log Trade:** Record in webhook listener
5. **Set Bracket:** Stop 1.5x ATR, Target 1R
6. **Monitor:** Watch thesis development

### Record-Keeping
- [ ] Trade logged with entry reason
- [ ] Telegram confirmation received
- [ ] Email backup (if Telegram fails >30 min)

---

## END OF DAY (2:00 PM - 4:00 PM MT)

### Daily Close Review
- [ ] Check all open positions
- [ ] Verify P&L within daily limit
- [ ] Any policy alerts happened? Document impact
- [ ] Any trades hit stops? Log reason
- [ ] Regime score updated? Note if changed

### 4:00 PM Portfolio Email
- [ ] Should arrive in inbox
- [ ] Shows current positions
- [ ] Daily P&L summary
- [ ] Confirms all systems operational

### Overnight Preparation
- [ ] All positions secured with stops
- [ ] Kill switch ready if market gaps
- [ ] Review trades entered today
- [ ] Note wins/losses for journal

---

## WEEK 1 SUCCESS CRITERIA

**By end of Friday Feb 28:**
- [ ] At least 1-2 trades entered
- [ ] Daily loss limit never breached
- [ ] P&L positive (even $100 = thesis working)
- [ ] All systems delivered alerts/reports on schedule
- [ ] Trade journal filled out
- [ ] Friday 5 PM performance email received

**Scaling Decision (Friday evening):**
- If P&L > $0 AND win rate ≥50%: Continue TIER 1 ✅
- If P&L < $0: Pause, review, modify strategy
- If no trades yet: Increase monitoring, watch screener more carefully

---

## CRITICAL REMINDERS

### Daily Loss Limit: -$1,350
- This is HARD STOP
- If breached, all new trades blocked
- Existing positions protected
- Webhook listener auto-enforces this

### Daily Check Times
- **7:30 AM** - Market open, regime monitor starts
- **10:00 AM** - Mid-morning policy check
- **12:00 PM** - Midday check
- **2:00 PM** - Pre-close policy check
- **4:00 PM** - Portfolio email arrives

### First Week Mindset
- This is VALIDATION phase, not profit phase
- Goal: Prove strategy works, not maximize returns
- Use 1-share canary mode to learn
- Every trade is educational (win or lose)
- Trust the system, follow the rules

### If Something Breaks
1. **Telegram down:** Check email in 5 min
2. **Webhook listener down:** Check logs, restart manually
3. **IB Gateway disconnects:** Reconnect immediately
4. **Policy alert CRITICAL:** Pause trades, await analysis
5. **Daily limit breached:** Stop all new entry signals

### Rules Override Protocol
- Normal: Follow TRADING_RULES.md exactly
- Emergency: Use kill switch (.pause file)
- Recovery: Contact via email/SMS if needed

---

## File Reference

| File | Purpose | Use When |
|------|---------|----------|
| TRADING_RULES.md | Complete rule book | Every trade decision |
| ANALYSIS_SYSTEM_STATUS.md | System operational status | Debugging |
| TRUMP_MONITORING_SETUP.md | Policy alert rules | Policy news breaks |
| PERFORMANCE_TRACKING.md | Scaling framework | Friday review |
| MEMORY.md | Long-term context | Any session start |
| Daily portfolio email | P&L snapshot | Daily 4 PM |
| Weekly review email | Performance data | Friday 5 PM |

---

## Success Metrics (Week 1)

### Minimum (PASS)
- ✅ At least 1 trade entered
- ✅ P&L ≥ $0
- ✅ Daily loss limit never hit
- ✅ All systems operational

### Target (GREAT)
- ✅ 2-4 trades entered
- ✅ P&L ≥ $500
- ✅ Win rate ≥ 50%
- ✅ 1+ covered call or put trade

### Excellent (EXCEPTIONAL)
- ✅ 4-6 trades entered
- ✅ P&L ≥ $1,000
- ✅ Win rate ≥ 60%
- ✅ 2+ covered call/put trades
- ✅ Clear trade patterns identified

---

## Week 1 Journal Template (Friday 5 PM)

```
WEEK 1 REVIEW - Feb 24-28, 2026

Trades Entered: __
Entry Reasons: ________
Wins: __  Losses: __  Win Rate: ___%

Best Trade: __TICKER__ +$____ 
Worst Trade: __TICKER__ -$____

Daily Loss Limit Breaches: 0 ✅

P&L: +$____ (or -$____)

Thesis Validation:
- What worked? _____________
- What didn't? _____________

Rules Followed: YES / NO
- Entry filters respected? YES
- Exit rules executed? YES  
- Position sizing correct? YES
- Concentration limits OK? YES

Next Week Adjustments:
1. _______________
2. _______________

Confidence Level: [1-10]  ___

Ready for TIER 2? YES / NO
(Only if 2+ weeks consecutive positive P&L)
```

---

## GO-LIVE STATUS

✅ **All systems operational and tested**  
✅ **All rules documented and committed to memory**  
✅ **Alert system ready (primary + backup)**  
✅ **Trade journal ready**  
✅ **Weekly/monthly review scheduled**  
✅ **Scaling framework in place**  

**Ready for Monday 7:30 AM MT market open** 🚀

---

**Last updated:** Saturday, February 21, 2026 @ 8:15 PM MT  
**Next update:** Friday, February 28, 2026 @ 5:00 PM MT (after first week review)
