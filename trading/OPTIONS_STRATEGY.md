# Options Income Strategy

**Strategy Type:** Opportunistic with Minimum Deploy Rule

---

## Core Philosophy

**Primary Mode:** Wait for high-quality setups
- Sell premium when conditions are favorable
- Capture high IV opportunities
- Deploy on technical quality signals

**Safety Net:** Ensure consistent monthly income
- Target minimum 2-4 options trades per month
- Force deploy if under target by month-end
- Maintain steady income stream

---

## Deployment Rules

### Covered Calls (On Profitable Longs)

**Automatic Triggers:**
- Position up **≥5%** from entry
- Held for **≥3 days**
- Still **≥8% below target**

**Parameters:**
- Strike: +10-15% OTM
- DTE: 30-45 days
- Premium target: ≥1% monthly yield
- Delta: ≤0.30

### Cash-Secured Puts (On Watchlist Pullbacks)

**Automatic Triggers:**
- Stock on watchlist (not currently held)
- RS percentile still strong (≥0.55)
- Pulled back **3-8%** from recent high
- Price near support (50 EMA)
- Volume normal (not panic selling)

**Parameters:**
- Strike: At or slightly below support
- DTE: 30-45 days
- Premium target: ≥1.5% return
- Delta: 0.30-0.40

---

## Minimum Deploy Rule

### Monthly Target
- **Minimum:** 2 trades per month
- **Ideal:** 3-4 trades per month
- **Opportunistic bonus:** Additional trades when IV spikes or great setups appear

### End-of-Month Check (Last Week)

**If deployed < 2 trades:**
- Manual review of watchlist
- Deploy 1-2 best available CSPs
- Lower bar slightly (accept 2-7% pullbacks instead of 3-8%)
- Still require support levels and normal volume

**If deployed 2-3 trades:**
- Optional: Add 1 more if any quality setup exists
- Otherwise, month complete

**If deployed ≥4 trades:**
- Month complete, no forced deployments

---

## Position Management

### Covered Calls
- **Buy back at 50% profit** (captured most theta)
- **Roll up/out** if still bullish and in profit
- **Take assignment** if hit strike and satisfied with gain

### Cash-Secured Puts
- **Buy back at 50% profit** (captured most theta)
- **Roll down/out** if still want exposure but stock fell further
- **Take assignment** if fundamentals/technicals still strong
- **Let expire worthless** if OTM at expiry (keep 100% premium)

---

## Tracking & Reporting

### Daily (3:00 PM MT)
- Automated scan for opportunities
- Telegram notifications with approve/reject buttons
- Log all deployments

### Weekly (Sundays)
- Review deployed trades count vs. target
- Note any positions approaching expiry
- Plan for week ahead

### Monthly (Last Friday)
- Count total deployments for month
- Calculate premium collected
- Check if under minimum → force deploy if needed
- Calculate monthly yield on capital deployed

---

## Capital Allocation

### Per Trade Risk
- **Covered calls:** Already own stock, no additional capital
- **Cash-secured puts:** 100 × strike price in cash (or margin)

### Total Options Allocation
- **Max concurrent CSPs:** 3-4 positions
- **Max capital at risk:** $50,000 (assuming $500/contract premium average)
- **Leave buffer:** Don't tie up all trading capital

---

## Performance Targets

### Conservative (Year 1)
- **Monthly yield:** 1.5-2.5% on deployed capital
- **Annualized:** 18-30%
- **Win rate:** ≥70% (expire OTM or buy back at profit)

### Aggressive (Year 2+)
- **Monthly yield:** 2.5-4.0% on deployed capital
- **Annualized:** 30-48%
- **Win rate:** ≥75%

---

## Risk Controls

### Never Deploy If:
- VIX <12 (premiums too thin)
- Stock near earnings without explicit approval
- No clear support level for CSPs
- Would violate max concurrent position limits

### Always Deploy With:
- Clear technical level (support for CSPs, resistance for covered calls)
- Normal volume (avoid unusual conditions)
- Approval via Telegram (semi-automated, not fully automated)

---

## Automation Settings

### Daily Scan (3:00 PM MT)
- Run `options_monitor.py`
- Generate pending intents for quality setups
- Send Telegram with approve/reject buttons

### Monthly Check (Last Friday, 5:00 PM MT)
- Count deployments for current month
- If < minimum: Alert with watchlist review prompt
- Generate "force deploy" recommendations

---

## Notes

- **Start conservative:** 2 trades/month minimum for first 3 months
- **Scale up:** Increase to 3-4/month once comfortable
- **Track everything:** Every trade logged to `trading/options/` directory
- **Review quarterly:** Adjust strike selection, DTE, premium targets based on results

---

**Strategy Status:** ACTIVE  
**Last Updated:** February 18, 2026  
**Next Review:** May 18, 2026 (90 days)
