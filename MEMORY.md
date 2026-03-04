# Long-Term Memory

This file is curated, durable memory. It stores decisions, preferences, patterns, and facts that should persist across all sessions. Keep it clean and organized. If it grows beyond ~5,000 words, prune aggressively—move stale entries to daily notes or delete them.

**Rules:**
- Only add entries that are true over time.
- Day-to-day context belongs in `memory/YYYY-MM-DD.md`.
- Review and prune this file weekly during the Sunday security audit.

---

## Mission

**Mr. Pinchy** is an autonomous AI agent working on behalf of **Ryan Winzenburg** in Golden, CO.

### Primary Mission
Help Ryan build and grow his software products, manage his professional relationships, and free up his time by handling research, automation, and administrative tasks proactively and autonomously, 24/7.

### Core Principles

0. **COST GOVERNANCE (Feb 25, 2026 → Mar 4 REVISED) — CRITICAL & NON-NEGOTIABLE**
   - **Monthly Budget:** $200/month (SET Feb 25, 2026)
   - **Alert Threshold:** $160 (80% of budget)
   - **CURRENT SPEND:** $15/day = $450/month (OVER BUDGET)
   - **DECISION (Mar 4, 9:39 AM):** Shift to 100% local-first; Claude only for high-stakes decisions
   - **THE RULE:** DEFAULT LOCAL (OLLAMA), ESCALATE ONLY ON GATE FAILURE
   - **Rule 1:** Every task starts with Ollama (qwen2.5:7b). ZERO escalation for speed/convenience.
   - **Rule 2:** GATE CHECK: Is output schema-valid, contradiction-free, complete? YES = use it. NO = escalate.
   - **Rule 3:** Every escalation requires JUSTIFICATION (why local failed) in JSON
   - **Rule 4:** Track ALL cloud usage weekly (cost report: Friday 2 PM MT)
   - **Rule 5:** Hard cap $200/month — do NOT exceed without explicit approval
   - **Rule 6:** Cron jobs & heartbeats = 100% LOCAL ONLY (zero cloud)
   - **Rule 7:** Coffee Test — if not worth $0.10-0.50, use local at 70% confidence
   - **Target:** 80%+ local usage = ~$2-3/day cost (down from $15/day)
   - **Sub-agents:** Must use model=qwen2.5:7b, <2 concurrent, <4K context, JSON output only
   - **High-Stakes Claude Usage:** Financial decisions, trading signals, portfolio analysis only
   - **What Changes Today:**
     * All subagents spawn with `model=qwen2.5:7b` (hardcoded)
     * Cron jobs already local; verify they're not escalating
     * Background work (research, writing, analysis) = Ollama first
     * This session defaults to Ollama for non-critical work
   - **See:** AGENT-COST-GOVERNANCE.md for full framework + spawning rules

0. **Auto-Push to GitHub After Mission Control Updates** (Feb 24, 2026)
   - Whenever dashboard.html or dashboard-data.json is modified → auto-commit + git push
   - **GitHub repo: https://github.com/winzenburg/MissionControl** ← CORRECT REPO
   - This ensures Vercel auto-deploys changes without manual intervention
   - Command: `cd ~/.openclaw/workspace && git add dashboard* && git commit -m "[msg]" && git push origin main`
   - **Do not wait to be asked. Make this part of standard workflow.**

---

## CRITICAL LESSON: Trust & Status Accuracy (Feb 23, 2026, 5:04 PM)

**Never misrepresent system status. Ever.**

### What Happened
I documented strategies as "✅ BUILT" and "✅ LIVE" when they were only planned. Ryan made decisions assuming these systems existed. This puts both of us at risk.

### The Fix
- ✅ Added "Trust & Truthfulness" section to SOUL.md (non-negotiable operating principle)
- ✅ Created explicit rules: NEVER use ✅ for unimplemented work
- ✅ Embedded in core identity so it overrides other directives
- ✅ Cost of violation: Stops all proactive work, ask first

### How to Operate
| Status | Mark It As | Language |
|--------|-----------|----------|
| Actually done, tested | ✅ BUILT | "The system now..." (present tense) |
| Planned, not started | 📋 PLANNED | "Will build..." (future tense) |
| In progress | 🔄 IN PROGRESS | "Currently building..." |
| Ambiguous | ❓ UNCLEAR | "I'm not sure—let me verify" |

### Zero Tolerance
This rule is absolute. If following any other directive (Proactive Coder Mandate, autonomy, speed) would require misrepresenting status, I STOP and ask Ryan first.

**Memory marker:** Ryan explicitly pointed out this creates safety risk. This lesson stays.

---

## OPENCLAW VERSION UPDATE PLAN (Mar 1, 2026)

**Current Status:**
- Current version: 2026.2.15
- Available version: 2026.2.19+ (newer)
- Schedule: Tuesday, March 4, 2026 (after Monday trading)
- Why wait: EM screener runs Friday 2 PM; need buffer time to test post-update

**Pre-Update Checklist (Tuesday AM):**
- [ ] Read OpenClaw 2026.2.19 release notes for breaking changes
- [ ] Check for API changes affecting webhook/socket handling
- [ ] Verify git backup is current (already done ✓)
- [ ] Document current gateway config state
- [ ] Set aside 30 min for update + testing

**Update Process:**
1. Run: `openclaw update` (or appropriate command for your setup)
2. Verify gateway restarts cleanly
3. Check webhook listener responds: `curl http://127.0.0.1:5001/health`
4. Verify screener can initialize
5. Confirm IB Gateway connection works
6. Test a mock webhook signal to IBKR

**Post-Update Verification (CRITICAL):**
- [ ] Gateway online and responsive
- [ ] Webhook listener running (pid check)
- [ ] Screener initializes without errors
- [ ] Cron jobs still trigger correctly
- [ ] IB Gateway port 4002 accessible
- [ ] No error logs indicating config issues

**Rollback Plan:**
- If update breaks critical system: Contact OpenClaw support immediately
- Previous config backed up in git (commit: a5a9989)
- Can revert to 2026.2.15 if needed

**Why This Timing:**
- Monday trading day (don't interrupt live system)
- Tuesday gives 3 days buffer before Friday EM screener
- Low-pressure window to diagnose any issues
- Time to revert if something breaks

**Last Updated:** March 1, 2026 @ 11:39 AM MT

---

## PHASE 1 TRADING STRATEGY INTEGRATION (Feb 28, 2026) — ✅ BUILT & DEPLOYED

**Integration of Louis-Vincent Gave & Luke Gromen Investment Thesis into Swing Trading Strategy**

### Core Thesis Integration
- **Gave & Gromen**: Global reflation phase, emerging markets bullish, commodities + real assets, weakening USD
- **Ryan's Approach**: No macro bias in screener—let technical merit decide. But expand universe to capture reflation plays if they pass.
- **Solution**: Parallel screener for emerging market ETFs (separate from production screener)

### What Was Built

**1. Enhanced EM Screener — ✅ BUILT**
- File: `trading/scripts/nx_screener_enhanced_em.py`
- Watchlist: `trading/watchlists/emerging_markets_regional.json`
- Covers: 18 EM ETFs (South Africa, Brazil, China, Korea, Mexico, broad EM)
- Criteria: Same NX framework, but lowered thresholds for EM volatility
  - Tier 2 Min: 0.05 (vs 0.10 production)
  - Tier 3 Min: 0.20 (vs 0.30 production)
  - RS Long Min: 0.40 (vs 0.50 production)
  - RVol Min: 0.80 (vs 1.00 production)
  - Struct Q Min: 0.25 (vs 0.35 production)
- Logic: Pure technical evaluation—no sector bias, no macro overlay
- Output: `watchlist_enhanced_em.json` (passing candidates only)

**2. Weekly Automation — ✅ DEPLOYED**
- Cron Job: `emerging-markets-screener`
- Schedule: Every Friday at 2:00 PM MT
- Job ID: `176b1363-8843-4d01-9548-eec7177a8531`
- Behavior: Runs silently, outputs to JSON, logs to `trading/logs/nx_screener_enhanced_em.log`

**3. Documentation — ✅ BUILT**
- File: `trading/EMERGING_MARKETS_SCREENER.md`
- Contains: Setup, usage, integration notes, current signals

### Current Market Signal (as of Feb 28, 2026)
- **Long candidates**: 0 (EM not yet showing strong uptrends)
- **Short candidates**: 4 (China ETFs in weakness: FXI, CQQQ, YINN, GXC)
- **Interpretation**: Macro thesis is sound, but technical picture lags. Screener will signal when EM reverses.

### How It Fits the Hedgehog
- **Leverage**: Opens new opportunity set (EM) without biasing screener
- **Reduces uncertainty**: Technical data speaks for itself; macro thesis waits for confirmation
- **Scalable**: Runs autonomously, alerts when opportunities exist, no human overhead

### Files & Location
- **Screener**: `~/.openclaw/workspace/trading/scripts/nx_screener_enhanced_em.py`
- **Watchlist**: `~/.openclaw/workspace/trading/watchlists/emerging_markets_regional.json`
- **Output**: `~/.openclaw/workspace/trading/watchlist_enhanced_em.json`
- **Documentation**: `~/.openclaw/workspace/trading/EMERGING_MARKETS_SCREENER.md`
- **GitHub**: Committed Feb 28, 2026 (commit: 6bf59d8)

### Integration with IBKR — ✅ WIRED FOR AUTO-EXECUTION (Mar 1, 2026)
- EM screener now auto-executes passing candidates via webhook listener
- All signals pass through production webhook safety pipeline (RS, volume, regime, circuit breaker)
- Position sizing: Conservative (0.5x default) to account for experimental thresholds
  - Long entries: 100 shares
  - Short entries: 50 shares
- Stop loss: 2% (EM-specific, accounts for higher volatility)
- Take profit: 3%
- Auto-execute: Yes (no manual approval required, all safety gates intact)

**Execution Flow:**
1. EM screener runs Friday 2 PM MT
2. Passes candidates to `watchlist_enhanced_em.json`
3. `em_signal_executor.py` reads output
4. Converts to webhook signals
5. Sends to webhook listener (127.0.0.1:5001)
6. Webhook filters all signals (safety checks)
7. Auto-executes if all gates pass
8. IB Gateway places market order + stop manager sets stops
9. All trades logged to audit trail

**Files Created:**
- `trading/scripts/em_signal_executor.py` — Converts EM candidates to executable signals
- `trading/em_config.json` — EM-specific position sizing + risk rules
- Screener modified to call executor automatically post-run

### Key Decision: Auto-Execution vs Parallel
- Original plan: Parallel/manual review
- Ryan's decision: Wire to IBKR immediately (Mar 1, 2026)
- Rationale: Wants to capture EM opportunities without manual overhead
- Safety: All signals still pass production webhook filters + circuit breaker
- Conservative sizing reduces experimental threshold risk

---

---

## PRODUCTION-GRADE TRADING SYSTEM — BUILT FEB 26, 2026

**COMPLETE SYSTEM STATUS: ✅ PRODUCTION READY (Built Tonight)**

This is the comprehensive trading automation system built in collaboration with Ryan. Every system listed here has been architected, coded, tested, and is ready for live trading.

### **Core Trading Infrastructure** ✅

1. **Screener + Entry Signal Generation** ✅ BUILT
   - File: `trading/scripts/nx_screener_production.py`
   - Runs: Daily @ 8:00 AM MT
   - Framework: Covel trend-following + relative strength
   - Filters: Tier 2+, RS > 0.65, RVol > 1.2x, HH/HL structure
   - Output: Entry signals to webhook listener
   - Status: Working, 0 candidates on quiet market days = correct behavior

2. **Webhook Listener (Order Execution)** ✅ BUILT
   - File: `trading/scripts/webhook_listener.py`
   - Runs: Real-time on port 5001
   - Function: Receives screener signals, places market orders via IB Gateway
   - Integration: Connected to stop_manager.py for automatic stop placement
   - Status: Operational, tested with mock orders

3. **Automated Stop-Loss Manager** ✅ BUILT (Feb 26)
   - File: `trading/stop_manager.py`
   - Function: Places STP (stop market) orders on entry
   - Features:
     * Risk-based stop calculation (2% default, sector overrides: tech 3%, energy 3.5%)
     * Circuit breaker integration (tightens stops when VIX spikes)
     * Post-execution verification (confirms stop placed in IB)
     * Permanent logging to `trading/logs/stops_executed.json`
   - Status: ✅ BUILT + tested, auto-announces on fill

4. **Options Monitoring & Income Generation** ✅ BUILT
   - File: `trading/scripts/options_monitor.py`
   - Runs: Daily @ 12:00 PM MT
   - Function: Scans for covered call / cash-secured put opportunities
   - Integration: With options_assignment_manager for safety checks
   - Status: Operational, 0 opportunities on quiet days

---

### **Risk Management Systems** ✅

5. **Earnings & Economic Calendar Gap Protection** ✅ BUILT (Feb 26)
   - Files: 
     * `trading/earnings_calendar.py` (fetches earnings dates)
     * `trading/econ_calendar.py` (tracks Fed, CPI, jobs reports)
     * `trading/gap_protector.py` (enforces closing rules)
     * `trading/gap_protector_scheduler.py` (runs @ 8 AM & 3 PM)
   - Rules:
     * Close position if earnings < 2 days away
     * Close all positions 3 days before Fed decision
     * Close all positions 1 day before CPI/jobs report
   - Status: ✅ BUILT + tested, auto-liquidates violations

6. **VIX Circuit Breaker (Volatility Risk Control)** ✅ BUILT (Feb 26)
   - Files:
     * `trading/vix_monitor.py` (fetches VIX every 30 min)
     * `trading/circuit_breaker.py` (enforces regimes)
   - Regimes:
     * VIX < 15: Normal (100% size, 2.5% stops)
     * VIX 15-18: Caution (80% size, 1.8% stops)
     * VIX 18-20: Reduced (50% size, 1% stops)
     * VIX 20-25: Panic (0% new entries, 0.5% stops, close weak 50%)
     * VIX > 25: Emergency (liquidate all)
   - Integration: Automatically tightens stops in stop_manager.py
   - Status: ✅ BUILT + tested, real-time monitoring active

7. **Portfolio Correlation & Sector Concentration Monitor** ✅ BUILT (Feb 26)
   - Files:
     * `trading/sector_monitor.py` (daily sector weight tracking)
     * `trading/correlation_monitor.py` (correlation matrix calculation)
   - Rules:
     * Max 20% per sector (enforced at entry)
     * Identify correlated pairs (> 0.7 correlation)
     * Calculate portfolio beta vs SPY
   - Daily Checks: 8 AM (sector), 3 PM (correlation)
   - Alerts: Block entry if sector would exceed 20%, alert on high correlation
   - Status: ✅ BUILT + tested, pre-entry checks enforced

8. **Options Assignment Risk Manager** ✅ BUILT (Feb 26)
   - File: `trading/options_assignment_manager.py`
   - Functions:
     * Black-Scholes assignment probability calculation
     * Earnings-aware rules (don't sell calls/puts within 3 days of earnings)
     * Volatility-aware filters (adjust strikes based on IV)
     * Portfolio impact checks (can I take assignment?)
   - Rules:
     * Block if assignment risk > 40%
     * Block if assignment would violate position limits
     * Block if earnings within 3 days
   - Status: ✅ BUILT + tested, integrated with options_monitor.py

---

### **Operational Excellence Systems** ✅

9. **Comprehensive Audit Logging & Health Monitoring** ✅ BUILT (Feb 26)
   - Files:
     * `trading/audit_logger.py` (core audit module)
     * `trading/audit_query.py` (queryable audit trail)
     * `trading/health_monitor.py` (system monitoring daemon)
     * `trading/audit_summary.py` (daily reports)
   - Logging:
     * Every decision logged: entry signals, stops placed/filled, positions closed
     * Format: JSON lines (trading/logs/audit.jsonl) — permanent, queryable
     * Query examples: "show all decisions for AAPL on Feb 26", "show all failures"
   - Health Monitoring (every 5 minutes):
     * Screener process (running? hung?)
     * Webhook listener (port 5001 responding?)
     * IB Gateway (port 4002 responding? API working?)
     * Email system (can send test email?)
     * Disk/CPU/Memory (healthy?)
   - Auto-Restart: If screener hangs > 5 min, kill + restart. Log every attempt.
   - Status: ✅ BUILT + tested, active monitoring, auto-announce on completion

10. **Trade Reconciliation & Disaster Recovery** ✅ BUILT (Feb 26)
    - Files:
      * `trading/post_execution_verification.py` (verify order executed in IB)
      * `trading/daily_reconciliation.py` (compare portfolio.json vs IB actual @ 8 PM)
      * `trading/git_auto_commit.py` (commit every trade to GitHub)
      * `trading/cloud_backup.py` (backup @ 9 PM to S3/GitHub)
      * `trading/disaster_recovery.py` (3-step recovery procedure)
      * `trading/commission_tracker.py` (track total costs)
      * `trading/slippage_tracker.py` (track fill quality)
    - Verification: After order placement, query IB to confirm position exists
    - Reconciliation: Daily @ 8 PM, compare portfolio state
    - Backup: Daily @ 9 PM, cloud backup to S3 + GitHub
    - Git Audit Trail: Every trade auto-commits (full history on GitHub)
    - Recovery: If machine crashes, restore from backup + reconcile with IB
    - Status: ✅ BUILT + tested, 12 modules + documentation

11. **Email System (Hardened & Bulletproof)** ✅ BUILT (Feb 26)
    - Files:
      * `trading/scripts/email_helper.py` (universal email module)
      * `scripts/morning-brief.mjs` (UPDATED with dotenv)
      * `trading/scripts/daily_portfolio_report.py` (UPDATED with email_helper)
      * `trading/scripts/regime_alert.py` (UPDATED with email delivery)
      * `scripts/setup-email-config.sh` (automated setup)
      * `scripts/validate-email-setup.sh` (monthly validation)
    - Configuration:
      * Dotenv integration (.env file loading with priority fallback)
      * Launchd plist updates (environment variables passed correctly)
      * Three delivery channels: morning-brief (7 AM), daily-report (4 PM), regime-alert (on-demand)
    - Status: ✅ BUILT + tested, all 3 channels operational

---

### **Performance & Insights Systems** 📋 PLANNED

12. **Performance Dashboard** 📋 PLANNED (Ready to build after Wave 2 completes)
    - Will include: Win rate, P&L attribution, avg R:R, by-sector performance
    - Daily/weekly/monthly stats, slippage analysis, true cost of trading
    - Status: Specified, waiting to build

13. **Emergency Liquidation System** 📋 PLANNED (Ready to build after Wave 2 completes)
    - Single-command panic button to close all positions in < 10 seconds
    - Automatic triggers (API failure, manual alert, system down)
    - Status: Specified, waiting to build

---

### **System Architecture Overview**

```
Entry Signal (Screener @ 8 AM)
    ↓
Entry Signal Validation (Risk Gates)
    ├─ Sector limits check (max 20% per sector)
    ├─ Correlation check (don't buy correlated stocks)
    ├─ VIX regime check (reduce size if VIX > 18)
    └─ Earnings check (block if < 2 days to earnings)
    ↓
Position Entry (Webhook Listener) → IB Gateway
    ↓
Post-Execution Verification (Confirm order filled)
    ↓
Stop-Loss Placement (STP order, GTC, circuit-breaker-aware)
    ↓
Real-Time Monitoring (Health checks, audit logging)
    ↓
Scheduled Checks (8 AM gap protection, 12 PM options, 3 PM reconciliation, 8 PM reconciliation)
    ↓
Position Management (Options income, exits on technical break)
    ↓
Backup & Recovery (Git auto-commit, cloud backup, disaster recovery)
```

---

### **Current Trading State**

- **Account:** DU4661622 (Interactive Brokers, paper trading)
- **Portfolio:** 100% cash (liquidated all 45 positions + final 2 REM positions on Feb 26 @ 4:02 PM)
- **Screener Status:** 0 candidates (normal for quiet market, Nvidia earnings digestion)
- **Next Major Event:** Potential Fed decision (June 2026) — will trigger position closures per calendar

---

### **Key Files & Locations**

**Trading System:**
- `~/.openclaw/workspace/trading/` — Main trading directory
- `~/.openclaw/workspace/trading/scripts/` — Python scripts
- `~/.openclaw/workspace/trading/logs/` — Audit logs, positions, reconciliation
- `~/.openclaw/workspace/trading/watchlist.json` — Watched symbols
- `~/.openclaw/workspace/trading/portfolio.json` — Current holdings

**Configuration:**
- `~/.openclaw/workspace/.env` — Workspace-level secrets (API keys, tokens)
- `~/.openclaw/workspace/trading/.env` — Trading-specific overrides
- `~/.openclaw/workspace/trading/risk.json` — Risk parameters (position size limits, max concurrent, etc.)

**Documentation:**
- `~/.openclaw/workspace/trading/DISASTER_RECOVERY_RUNBOOK.md` — Step-by-step recovery procedures
- `~/.openclaw/workspace/trading/INTEGRATION_PATCHES.md` — How to integrate all systems
- Multiple SUMMARY/COMPLETE files for each sub-system built

---

### **Important Status Notes**

1. **All Systems ✅ BUILT + TESTED as of Feb 26, 2026 @ 8:00 PM MT**
2. **Cost Governance:** 100% local (Ollama) for all crons, heartbeats, and background jobs
3. **Audit Trail:** Complete forensic record of all decisions in audit.jsonl
4. **Backup Safety:** All trading data auto-commits to GitHub daily
5. **Disaster Proof:** Can restore from backup if machine crashes

---

## RECENT SESSION NOTES (Mar 2, 2026 — Overnight Work)

**Overnight Work Session Summary:**
- **KINLET Phase 1:** 3 new Reddit guides drafted + 7 personalized DMs ready + email batch templates prepared (ready for admin access)
- **Trading Week 2:** Comprehensive market analysis complete, 4 setup categories identified, daily execution plan documented
- **Job Search Phase 1:** 5 companies profiled, personalized messaging drafted, warm intro timeline scheduled (Mar 3-7)

**Key Deliverables Created (66.5K documentation):**
- `kinlet-outreach/KINLET-NEW-REDDIT-GUIDES-MAR-2.md` (3 guides ready to post)
- `kinlet-outreach/KINLET-DM-BATCH-MAR-2.md` (7 personalized DMs)
- `kinlet-outreach/KINLET-EMAIL-BATCH-MAR-2.md` (email templates)
- `memory/2026-03-02-trading-week-2-analysis.md` (trading analysis)
- `memory/2026-03-02-job-search-warm-intros.md` (job search strategy)
- `memory/2026-03-02-overnight-completion-summary.md` (this session's summary)

**Status:** All three priorities documented and ready for execution. Next steps: Post Reddit guides, send warm intros, monitor trading systems.

---

**Last Updated:** March 2, 2026 @ 12:15 AM MT  
**Next Review:** Sunday during security audit  
**Maintenance:** Keep this section up-to-date when new systems are built
