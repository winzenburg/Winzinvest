# AGENTS.md - Mission Control

This file defines the agent system and workflow for Mission Control, a systematic algorithmic trading platform.

---

## Agent Philosophy

Mission Control follows the **Cultivate framework**:
1. **Gate enforcement** - Systematic quality checks at every phase
2. **Structured organization** - Clear workflows and decision criteria
3. **Automation** - Reduce manual overhead, increase consistency
4. **Decision frameworks** - Explicit rules, no ambiguity

---

## Core Agents

### 🎯 Trading System Agent
**Role**: Develop, test, and maintain trading strategies and execution logic

**Responsibilities:**
- Implement new strategies (momentum, mean reversion, pairs)
- Update risk management rules
- Optimize execution logic
- Backtest strategy changes
- Monitor live performance vs backtest

**Rules:**
- Must pass all trading system gates (see `.cursor/rules/020-mission-control-gates.mdc`)
- All trades logged to audit trail
- Paper trade new strategies for minimum 1 week
- Document all strategy parameters in code comments
- Use type guards for all external data (IBKR API)

**Key Files:**
- `trading/scripts/execute_*.py` - Strategy executors
- `trading/scripts/execution_gates.py` - Gate enforcement
- `trading/scripts/risk_config.py` - Risk configuration helpers
- `trading/risk.json` - Risk parameters

---

### 📊 Dashboard Agent
**Role**: Build and maintain institutional-grade trading dashboard

**Responsibilities:**
- Create new dashboard pages and components
- Fetch and display real-time data from IBKR
- Implement data visualizations (charts, tables)
- Ensure WCAG 2.2 AA compliance
- Optimize performance and responsiveness

**Rules:**
- Must pass all dashboard quality gates (see `.cursor/rules/020-mission-control-gates.mdc`)
- Follow design system (see `.cursor/rules/010-mission-control-design-system.mdc`)
- All data must show "last updated" timestamp
- Handle errors gracefully with helpful messages
- Test on mobile/tablet/desktop before deploying
- No console.log statements in production

**Key Files:**
- `trading-dashboard-public/app/**/*.tsx` - Next.js pages and components
- `trading-dashboard-public/app/api/**/*.ts` - API routes
- `trading/scripts/dashboard_data_aggregator.py` - Data collection script

---

### 🔍 Data Agent
**Role**: Aggregate, process, and serve trading data to dashboard

**Responsibilities:**
- Connect to IBKR API and fetch account data
- Calculate risk metrics (VaR, CVaR, beta, correlation)
- Calculate performance metrics (Sharpe, Sortino, win rate)
- Generate strategy-level breakdowns
- Compute trade analytics (MAE, MFE, slippage)
- Write data to `dashboard_snapshot.json`

**Rules:**
- Handle IBKR API errors gracefully
- Validate all data before calculations
- Log errors to `dashboard_aggregator.log`
- Never crash on missing data (use defaults)
- Run every 5 minutes via cron

**Key Files:**
- `trading/scripts/dashboard_data_aggregator.py` - Main aggregator
- `trading/scripts/run_dashboard_aggregator.sh` - Cron runner
- `trading/logs/dashboard_snapshot.json` - Output data

---

### 🛡️ Audit Agent
**Role**: Log and monitor all system decisions and gate rejections

**Responsibilities:**
- Log gate rejections with full context
- Log order lifecycle events (placed, filled, rejected)
- Log system events (startup, shutdown, errors)
- Log slippage events
- Provide audit trail summaries

**Rules:**
- Every gate rejection must be logged
- Include full context (symbol, notional, equity, failed gates)
- Timestamp everything
- Never modify historical audit entries
- Rotate logs monthly (keep last 12 months)

**Key Files:**
- `trading/scripts/audit_logger.py` - Audit logging functions
- `trading/logs/audit_trail.json` - Audit log
- `trading-dashboard-public/app/audit/page.tsx` - Audit viewer

---

### 🧪 Testing Agent
**Role**: Backtest strategies and validate system changes

**Responsibilities:**
- Run backtests on historical data
- Compare live performance to backtest expectations
- Identify strategy drift or degradation
- Validate risk parameter changes
- Generate backtest reports

**Rules:**
- Backtest minimum 2 years of data
- Include transaction costs and slippage
- Test multiple market conditions (bull, bear, sideways)
- Document assumptions clearly
- Compare metrics: Sharpe, max drawdown, win rate, avg return

**Key Files:**
- `trading/backtest/nx_backtest.py` - Backtest engine
- `trading/backtest/results/` - Backtest outputs

---

### 🎨 Design Agent
**Role**: Ensure dashboard meets institutional design standards

**Responsibilities:**
- Implement design system consistently
- Ensure WCAG 2.2 AA compliance
- Create sophisticated visual design
- Implement micro-interactions
- Maintain brand consistency

**Rules:**
- Follow design system (`.cursor/rules/010-mission-control-design-system.mdc`)
- All text meets 4.5:1 contrast ratio
- All interactive elements keyboard accessible
- Use semantic HTML
- No marketing language (professional tone)
- Test on multiple screen sizes

**Key Files:**
- `.cursor/rules/010-mission-control-design-system.mdc` - Design system
- `trading-dashboard-public/app/components/*.tsx` - UI components
- `trading-dashboard-public/app/globals.css` - Global styles

---

### 🔧 Operations Agent
**Role**: Manage live system operations — scheduler, services, deployments

**Responsibilities:**
- Restart scheduler after code changes (code is loaded into memory at startup)
- Monitor and resolve service health issues (watchdog, IB Gateway, dashboard)
- Run manual pipeline executions when needed (missed jobs, parameter changes)
- Audit and resolve IB clientId conflicts
- Verify all services are running after restarts

**Rules:**
- After ANY code change to executor/screener scripts, the scheduler MUST be restarted
- Always update `.pids/scheduler.pid` after restarting the scheduler
- Run screeners BEFORE executors (screeners populate watchlist JSONs that executors read)
- Run executors sequentially (they share IB Gateway and must not conflict)
- After manual execution, always run `portfolio_snapshot.py` + `dashboard_data_aggregator.py` to refresh the dashboard
- Check `pgrep -af scheduler.py` for duplicate processes — kill extras before starting fresh
- The watchdog (`watchdog.py`) auto-restarts scheduler and dashboard if they die, with 60s check interval

**Manual Pipeline Execution Order:**
```
1. Kill stale scheduler: kill $(cat trading/.pids/scheduler.pid)
2. Start fresh: nohup python3 scheduler.py >> logs/scheduler.log 2>&1 &
3. Update PID: echo $! > .pids/scheduler.pid
4. Screeners (can parallel): nx_screener_longs.py, nx_screener_production.py --mode all
5. Screeners (sequential): mr_screener.py, pairs_screener.py
6. Executors (sequential): execute_longs.py → execute_dual_mode.py → execute_mean_reversion.py → execute_pairs.py → auto_options_executor.py
7. Refresh: portfolio_snapshot.py → dashboard_data_aggregator.py
```

**Key Files:**
- `trading/scripts/scheduler.py` - Central scheduler (APScheduler)
- `trading/scripts/watchdog.py` - Service monitor and auto-restarter
- `trading/start.sh` - Service lifecycle management (start/stop/status)
- `trading/.pids/` - PID files for service tracking

---

## Agent Workflow

### New Feature Development

```
1. Planning Phase
   ├─ Define requirements
   ├─ Identify affected systems
   ├─ Design data flow
   └─ Create implementation plan

2. Implementation Phase
   ├─ Write code (Trading/Dashboard/Data agent)
   ├─ Add type guards and error handling
   ├─ Follow design system
   └─ Add audit logging

3. Testing Phase
   ├─ Unit test (if applicable)
   ├─ Backtest (Trading agent)
   ├─ Manual test (Dashboard agent)
   └─ Check audit logs

4. Quality Gates
   ├─ Code quality gates
   ├─ Dashboard quality gates
   └─ Deployment gates

5. Deployment
   ├─ Commit with clear message
   ├─ Push to GitHub
   ├─ Verify Vercel deployment
   └─ Monitor for 24-48 hours

6. Monitoring
   ├─ Check audit trail
   ├─ Monitor dashboard for errors
   ├─ Compare live vs backtest
   └─ Adjust if needed
```

### Bug Fix Workflow

```
1. Reproduce
   ├─ Check audit trail
   ├─ Review error logs
   └─ Identify root cause

2. Fix
   ├─ Implement fix
   ├─ Add test case (prevent regression)
   └─ Document in commit message

3. Verify
   ├─ Test fix locally
   ├─ Check audit trail
   └─ Monitor for 24 hours

4. Document
   └─ Update relevant docs/comments
```

## Agent Coordination

### When Multiple Agents Work Together

**Example: Adding a new risk metric**

1. **Data Agent** - Fetch raw data from IBKR, calculate metric
2. **Dashboard Agent** - Display metric in UI
3. **Design Agent** - Ensure visualization meets standards
4. **Audit Agent** - Log when metric exceeds threshold

**Coordination:**
- Data Agent outputs to `dashboard_snapshot.json`
- Dashboard Agent reads from API route (which reads snapshot)
- Design Agent ensures component follows design system
- Audit Agent logs events when thresholds breached

### Communication Between Agents

Agents communicate via **files**, not direct calls:

| From | To | Via |
|------|-----|-----|
| Trading System | Audit | `audit_trail.json` |
| Data Agent | Dashboard | `dashboard_snapshot.json` |
| Trading System | Dashboard | `audit_trail.json`, `dashboard_snapshot.json` |
| All | All | Git commits, code comments |

## Decision Framework

### When to Add a New Strategy

**Criteria (all must be true):**
- [ ] Backtest Sharpe > 1.5
- [ ] Backtest max drawdown < 15%
- [ ] Backtest win rate > 45%
- [ ] Strategy uncorrelated with existing strategies (correlation < 0.5)
- [ ] Strategy makes intuitive sense (not just curve fitting)
- [ ] Paper traded successfully for 2+ weeks

### When to Disable a Strategy

**Criteria (any can trigger):**
- [ ] Live Sharpe < 0.5 for 30+ days
- [ ] Live max drawdown > 20%
- [ ] Live performance diverges significantly from backtest (>50% worse)
- [ ] Strategy causes frequent gate rejections
- [ ] Market regime change makes strategy invalid

### When to Adjust Risk Parameters

**Criteria:**
- [ ] Account size changed significantly (>20%)
- [ ] Strategy performance improved/degraded consistently
- [ ] New strategy added (rebalance sector limits)
- [ ] Market volatility changed significantly
- [ ] Backtest shows better risk-adjusted returns with new params

**Process:**
1. Backtest with new parameters
2. Compare to current parameters
3. Paper trade for 1 week
4. Deploy if results are better
5. Monitor for 2 weeks

## Memory & Context

### Session Startup
Before doing anything else, read:
1. `AGENTS.md` (this file)
2. `.cursor/rules/*.mdc` (design and gate rules)
3. Recent `trading/logs/audit_trail.json` entries
4. Latest `trading/logs/dashboard_snapshot.json`

### Daily Memory
Create `memory/YYYY-MM-DD.md` for each day with:
- Trades executed
- Gate rejections
- System changes
- Performance summary
- Issues encountered

### Long-Term Memory
Update `MEMORY.md` weekly with:
- Key decisions made
- Lessons learned
- Strategy performance trends
- System improvements
- Recurring issues and solutions

## Safety & Security

### Never Do (Without Explicit Approval)
- ❌ Push to main with `--force`
- ❌ Modify git config
- ❌ Commit secrets (.env files)
- ❌ Execute trades without gate checks
- ❌ Disable safety mechanisms
- ❌ Delete audit logs
- ❌ Bypass risk limits

### Always Do
- ✅ Validate external data with type guards
- ✅ Log all system decisions
- ✅ Handle errors gracefully
- ✅ Use `trash` instead of `rm` for recovery
- ✅ Test changes locally before deploying
- ✅ Monitor audit trail after changes
- ✅ Document breaking changes

## Quick Reference

### File Structure
```
Mission Control/
├── .cursor/rules/          # Design and gate rules
├── trading/
│   ├── scripts/            # Executors, aggregators, utilities
│   ├── logs/               # Audit trail, dashboard snapshot
│   ├── backtest/           # Backtest engine and results
│   └── risk.json           # Risk configuration
├── trading-dashboard-public/
│   ├── app/                # Next.js pages and components
│   │   ├── api/            # API routes
│   │   └── components/     # React components
│   └── public/             # Static assets
├── memory/                 # Daily logs (YYYY-MM-DD.md)
├── MEMORY.md               # Long-term memory
└── AGENTS.md               # This file
```

### Common Commands
```bash
# Start dashboard dev server
cd trading-dashboard-public && npm run dev

# Run data aggregator
cd trading && python3 scripts/dashboard_data_aggregator.py

# Check audit trail
cd trading && tail -n 50 logs/audit_trail.json

# Deploy dashboard
cd trading-dashboard-public && npm run build && git push

# Run backtest
cd trading/backtest && python3 nx_backtest.py
```

---

## Lessons Learned (Updated 2026-03-11)

### Hardcoded Limits Don't Scale

**Problem**: Multiple scripts had hardcoded dollar amounts ($5K risk cap, $20K per leg, $100K default equity) that were appropriate for a small account but crippled a $1.9M portfolio.

**Fix**: All dollar-denominated limits must come from `risk.json` or be calculated as a percentage of NLV. See `050-position-sizing-and-scaling.mdc` for the full rule.

**Affected files (fixed)**: `auto_options_executor.py`, `execute_pairs.py`, `atr_stops.py`, all executors.

### Screener-Executor Pipeline Bottleneck

**Problem**: Screeners output top 10 candidates per side, but executors could process 15. The screener was the bottleneck — executors never saw candidates #11-15.

**Fix**: Screener output expanded to `[:25]` per side. Executor candidate caps: longs=15, dual=10, MR=10, pairs=8.

### clientId Conflicts Cause Silent Failures

**Problem**: `auto_options_executor.py` and `execute_dual_mode.py` both used clientId 103. When running near each other, the options executor got Error 10197 ("No market data during competing live session") and silently failed to price any contracts.

**Fix**: Every production script has a unique clientId. See `030-ib-client-ids.mdc` for the registry.

### Stale Scheduler = Stale Code

**Problem**: After updating script parameters, the scheduler continued running the old code because Python loads modules into memory at process startup. The changes had no effect until the scheduler was restarted.

**Fix**: Always restart the scheduler after code changes. The watchdog can also handle this automatically if the scheduler crashes.

### IB reqAccountSummary Fails Silently

**Problem**: `auto_options_executor.py` called `ib.reqAccountSummary()` but didn't wait for the async response. It always got $100K (the fallback) instead of $1.9M, making all position sizing 19x too small.

**Fix**: Call `ib.reqAccountSummary()`, then `ib.sleep(2)`, then read from `ib.accountSummary()`. Add fallback to `ib.accountValues()`. See `050-position-sizing-and-scaling.mdc`.

### yfinance API Changed Column Structure

**Problem**: `yf.download(ticker)` now returns multi-level columns (ticker as second level). Code like `float(hist['Close'].iloc[-1])` crashes with "float() argument must be a string or a real number, not 'Series'".

**Fix**: Always flatten: `close_col = hist['Close']; if hasattr(close_col, 'columns'): close_col = close_col.iloc[:, 0]`. See `040-trading-script-patterns.mdc`.

### Position Rebalance Scripts Must Be Idempotent

**Problem**: A one-time portfolio rebalance script was run multiple times due to IB Gateway disconnects, causing positions to flip (shorts became longs, longs became shorts).

**Fix**: Any script that places orders must check live positions before placing orders. Use the pattern in `portfolio_rebalance.py`: fetch positions first, skip if already at target.

### WebSocket Status Field Mismatch

**Problem**: Dashboard showed all services as "offline" on every WebSocket update because the JavaScript checked `info.status === 'running'` while the API returned `info.running` (boolean).

**Fix**: Always verify the actual JSON field names returned by the API when writing frontend display logic. The fix was `info.running === true`.

---

## Make It Yours

This agent system is a living document. As you learn what works and what doesn't, update this file. Add new agents, refine workflows, adjust gates. The goal is systematic improvement, not rigid adherence to outdated rules.
