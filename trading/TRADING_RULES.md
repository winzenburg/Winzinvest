# Trading Rules & Position Management

**Established:** February 21, 2026  
**Strategy Type:** Swing Trading with Options Income  
**Account:** Paper Trading (DU4661622)  
**Time Horizon:** Multi-day to multi-week

---

## 1. POSITION SIZING RULES

### Research-Backed Framework

**Industry Standard: 2% Risk Rule**
- Risk no more than 2% of portfolio on any single trade
- E.g., $2M portfolio = $40,000 max risk per trade
- This allows ~50 losing trades before portfolio is wiped

**Our Implementation: Tiered Position Sizing**

Based on profitability tier and account size:

| Tier | Portfolio Allocation | Per-Trade Risk | Rationale |
|------|---------------------|-----------------|-----------|
| TIER 1 (Weeks 1-2) | <10% | 1% per trade | Conservative validation |
| TIER 2 (Weeks 3-4) | 10-20% | 1.5% per trade | Proven consistency |
| TIER 3 (Month 2+) | 30-50% | 2% per trade | Full scale |

### Per-Trade Sizing Formula

```
Position Size = (Portfolio × Risk %) / Stop Loss Distance

Example (TIER 1):
- Portfolio: $2,000,000
- Risk per trade: 1% = $20,000
- Stop loss: $400 away (e.g., $450 entry, $410 stop on stock at $450)
- Position size: $20,000 / $400 = 50 shares

Math check: 50 shares × $400 stop = $20,000 risk = 1% of portfolio ✅
```

### Canary Mode Rule (Current)
- **All trades start at 1 share** (canary mode)
- Once position proves thesis (3+ days, profitable), can scale
- If thesis wrong, 1-share loss = minimal damage
- This is how your system currently works — keep it

### Position Concentration Limits (See Section 6)

---

## 2. ENTRY/EXIT RULES

### Entry Criteria (ALL must be true)

**Technical (TradingView AMS):**
- ✅ Screener signal: Tier ≥2
- ✅ RS Percentile: ≥0.60 (long) or ≤0.40 (short)
- ✅ Relative Volume: ≥1.20x
- ✅ Trade Engine confirmation: Entry signal firing

**Macro (Regime Monitor):**
- ✅ Regime band: Optimal for entry type
  - Risk-On (score 0-1): Best for longs
  - Neutral (score 2-3): Both directions
  - Tightening (score 4-5): Shorts better
  - Defensive (score 6+): Cash preferred

**Policy (Trump Monitoring):**
- ✅ No CRITICAL alerts pending
- ✅ Recent HIGH alerts classified and priced in
- ✅ Sector not under tariff/sanction threat

**Risk Management:**
- ✅ Daily loss limit not breached
- ✅ Not in earnings blackout window
- ✅ Position count under limit (see Section 7)
- ✅ Sector concentration under limit (see Section 6)

**Trading Window:**
- ✅ 7:30 AM - 2:00 PM MT (US market hours)

### Exit Criteria — Take Profits

**Profit Targets (Partial Exits):**

Based on AMS indicator (1.5R partial targets + Chandelier stops):

```
Entry → First Target (1R profit) → Sell 50% position
       → Move stop to break-even

Entry → Second Target (1.5R profit) → Sell 25% position
       → Move stop to 1R profit

Entry → Trailing Stop → Trailing 2x ATR
       → Exit remaining 25% on stop hit
```

**Example:**
```
Entry: $100
Stop: $95 (Risk = $5 per share = 1R)

Target 1: $105 (Risk:Reward = 1:1)
  Action: Sell 50% at $105
  Remaining: 25 shares
  New stop: $100 (break-even)

Target 2: $107.50 (Risk:Reward = 1:1.5)
  Action: Sell 25% at $107.50
  Remaining: 25 shares
  New stop: $105 (1R profit)

Trailing Stop: 2x ATR trailing
  Action: Exit last 25% on stop hit
  
Max win: ($105 × 50) + ($107.50 × 25) + ($110+ × 25) = $6,156.25
Max loss: $100 initial risk
```

### Stop Loss Rules

**ATR-Based Stops:**
- **Normal Conditions (Risk-On/Neutral):** 1.5x ATR below entry
- **Tightening Conditions:** 2.0x ATR below entry
- **Defensive Conditions:** 2.5x ATR below entry
- **Earnings Window:** No new entries (5 days before, 2 days after)

**Hard Stops (Automatic Exit):**
- Hit daily loss limit (-$1,350) → All positions close
- CRITICAL policy alert → Pause new entry, evaluate existing

**Trailing Stop (Current Position):**
- Once profitable: Trailing 2x ATR
- Locks in gains while allowing upside
- Exits on first pullback beyond threshold

### Hold Time Rules

**Minimum Hold:** 3 days (thesis validation)
**Maximum Hold:** 20 days (swing trade definition)
- If still holding after 20 days: Re-evaluate thesis
- Either add (thesis strengthening) or exit (time decay)

---

## 3. TRADE JOURNALING & ANALYSIS

### What Gets Logged (Automatically)

Each trade captures:

```
Entry:
- Date/Time: When trade entered
- Ticker: Stock symbol
- Direction: LONG or SHORT
- Entry Price: Execution price
- Position Size: Shares
- Entry Signal: Which screener/indicator fired
- Regime: Market regime at entry (Risk-On/Neutral/Tightening/Defensive)
- Policy Context: Any Trump alerts that day?
- Rationale: Why we entered (in Telegram message)

Exit:
- Exit Date/Time: When position closed
- Exit Price: Execution price
- P&L: Profit or loss
- Hold Time: Days held
- Exit Reason: Profit target / Stop loss / Time limit / Policy alert

Post-Analysis:
- Did thesis play out? YES/NO
- Win/Loss: Profitable or not
- Win Rate: # wins / # total trades
```

### Where Trades Are Logged

| Log | Purpose | Auto Updated |
|-----|---------|--------------|
| `trading/logs/webhook_listener.log` | Real-time alert log | YES |
| `trading/logs/audit.log` | Security audit trail | YES |
| Weekly performance email | P&L summary | YES |
| `trading/logs/portfolio_snapshot_[DATE].json` | End-of-day positions | YES |
| Trade analysis spreadsheet (manual) | Weekly review notes | MANUAL |

### Weekly Review (Every Friday 5 PM)

In your weekly email, we'll include:

```
WEEKLY TRADE JOURNAL

Entries This Week: X trades
Exits This Week: Y trades
Current Positions: Z

Trade-by-Trade Breakdown:
Ticker | Entry | Exit | Days | P&L | Win? | Notes
---    | ---   | ---  | ---  | --- | ---  | ---

Win Rate: __% (__W / __L)
Avg Winner: $____
Avg Loser: -$____
Profit Factor: ___ (avg winner / avg loser)

Thesis Analysis:
- Trades where thesis was RIGHT: __
- Trades where thesis was WRONG: __
- Improvement area: ___________
```

### Continuous Improvement

**Monthly Review (Last Friday of month):**
1. Identify losing trade patterns
2. Did we enter wrong? (screener miss?)
3. Did we exit too early? (took profit too soon?)
4. Did regime change mid-trade? (not our fault)
5. Propose rule modifications for next month
6. Test modifications in paper before implementing

---

## 4. PROFIT-TAKING RULES

### Swing Trades (Position Sizing Strategy Above)

**Partial Profit Taking:** 
- 50% at 1R profit
- 25% at 1.5R profit  
- 25% trailing stop

**Covered Calls (On Profitable Longs)**

Entry Criteria:
- ✅ Position profitable (>5% gain)
- ✅ Held ≥3 days
- ✅ Conviction still high (not exiting)

Strike Selection:
- Target premium: $100-200 per contract (balance premium vs assignment risk)
- Delta: 0.20-0.30 (willing to be called away 20-30% of the time)
- Expiration: Weekly (expires Friday) if weekly premium good, otherwise monthly
- Example: Long 100 AAPL @ $150 (5% gain) → Sell weekly call @ $155 strike → Collect $75 premium

Exit Criteria:
- ✅ Profit target hit on underlying → Let call get assigned (profit on both)
- ✅ Stop hit on underlying → Buy back call, cut loss on underlying
- ✅ Expiration Friday → If called away, great. If not, roll to next Friday.

Target: 2-4 covered calls per month

### Cash-Secured Puts (Income on Pullbacks)

Entry Criteria:
- ✅ Market pullback 3-8% from recent highs
- ✅ Support level identified (from technicals)
- ✅ Regime still favorable (not Defensive)
- ✅ Stock fundamentals intact

Strike Selection:
- Target premium: $200-400 per contract
- Delta: 0.30-0.40 (willing to own at this price)
- Distance from current: 5-8% below current price (near support)
- Expiration: Monthly (30-45 DTE for better premium)

Exit Criteria:
- ✅ Called away (great, now own at discount price)
- ✅ Stock bounces, profit 50%+ of premium collected → Close early
- ✅ Expiration Friday → Expires worthless (keep premium)
- ⚠️ Support breaks → Buy back put, cut loss

Target: 2-4 cash-secured puts per month

### When to Close Winners Early

**Close if:**
- Thesis clearly wrong (new info contradicts entry)
- Regime changes dramatically (shift to Defensive from Risk-On)
- Policy alert changes sector fundamentals
- Profit target hit (per 50/25 rule above)
- Time limit reached (20 days, thesis not strengthening)

**DON'T close if:**
- Thesis still intact
- Profit is "only" 1.5R (let trailing stop work)
- Regime supportive (keep position)
- We're less than 5 days in (minimum hold)

---

## 5. LEVERAGE & MARGIN POLICY

### Paper Trading Specifics

**Account:** DU4661622 (Paper Trading)
- Starting balance: ~$2M
- Buying power available: ~$5M (2.5x margin available)
- **Our policy:** Only use 50% of available buying power max

### Max Margin Utilization

| Tier | Max Buying Power Usage | Buying Power Limit | Notes |
|-----|------------------------|-------------------|-------|
| TIER 1 | 25% ($1.25M positions) | Keep $750K cash | Conservative |
| TIER 2 | 40% ($2M positions) | Keep $1M cash | Growing |
| TIER 3 | 50% ($2.5M positions) | Keep $1.25M cash | Full scale |

**Why?**
- Paper margin is "free" but teaches bad habits
- Real money margin has interest costs
- Keeping cash = room to add to winners or buy dips
- Prevents overleveraging

### Specific Rule

```
IF (Current Positions Value + New Trade) > Max Buying Power for Tier
THEN
  REJECT trade
  ALERT: "Margin limit would be exceeded. Close a position first."
```

---

## 6. SECTOR & STOCK CONCENTRATION LIMITS

### Sector Concentration Rules

**Rule:** No more than 25% of portfolio in any single sector

| Sector | Max % | Why |
|--------|-------|-----|
| Technology | 25% | Leverage to mega-cap strength, but limit concentration |
| Financials | 15% | Interest rate sensitive, not primary |
| Energy | 15% | Isolated from tech trends, limits correlation |
| Healthcare | 15% | Defensive, but not core |
| Consumer | 15% | Discretionary, cyclical |
| Other | 15% | Balance |

**Example:** If 35% of portfolio is Tech already, we DON'T take MSFT/NVDA/AAPL entry signals until Tech weight drops to <25%

### Single Stock Concentration Rules

**Rule:** No more than 8% of portfolio in any single stock

| Position Type | Max % | Why |
|---------------|-------|-----|
| Swing Trade | 5% | Entry-level sizing |
| Covered Call | 5-8% | Profitable long with income |
| Directional Bet | 3-5% | High conviction |

**Example:** If AAPL is at 8% portfolio weight and screener fires, we DON'T take signal. Must wait for position to drop first.

### Tech Dominance Special Rule

**If Tech exceeds 30% of portfolio:**
- Focus new entries on other sectors
- Consider taking partial profits on Tech winners
- Rebalance toward underweight sectors
- This prevents "all eggs in one basket" trap

---

## 7. POSITION COUNT LIMITS

### Maximum Open Positions

| Tier | Max Positions | Max Capital | Rationale |
|------|---------------|-------------|-----------|
| TIER 1 | 5 positions | <10% of buying power | Easy to manage, validate |
| TIER 2 | 8 positions | 10-20% of buying power | Growing complexity |
| TIER 3 | 12 positions | 30-50% of buying power | Full diversification |

**Rule:**
```
IF current open positions == max for tier
THEN
  Do NOT take new entry signal
  WAIT for position to close or tier to advance
```

### Position Management at Limit

**When at position limit:**
1. Close smallest losing position first (cut loss)
2. OR close position closest to 20-day hold limit (time decay)
3. OR take partial profit on oldest winning position
4. THEN enter new signal

---

## 8. BACKUP ALERT METHODS

### Primary: Telegram
- Real-time alerts to: @pinchy_trading_bot
- Portfolio updates
- Policy alerts
- Trade confirmations

### Secondary: Email (Primary Backup)
- Daily portfolio email (4 PM MT)
- Weekly performance email (Friday 5 PM)
- Critical policy alerts (immediate)
- To: ryanwinzenburg@gmail.com

### Tertiary: SMS/Text (If Telegram Down)
**Phone:** 303-359-3744

**When to text you:**
- 🚨 CRITICAL policy alert (tariff, Fed policy)
- ❌ Daily loss limit breached
- ⚠️ Telegram bot not responding >30 min
- 🔴 Webhook listener crashed

**SMS Template:**
```
🚨 CRITICAL: Trump tariff announcement. Recommend reduce Tech 20%, increase Energy. 
Check email for full analysis.
```

### Failover Logic

```
IF Telegram fails
  THEN send backup Email
  WAIT 5 minutes for user to see email
  IF still no response
    THEN send SMS (303-359-3744)
    TEXT: Critical alert, check email
```

**Implementation:**
- Telegram alert function catches errors
- On error, triggers email fallback
- On critical alerts, triggers SMS

---

## 9. MANUAL TRADE ENTRY & OVERRIDE

### Can You Manually Enter?

**YES - Full Manual Entry Allowed**

Manual entry process:
1. You identify opportunity (outside screener)
2. Email agent with: Ticker, entry price, direction, size, rationale
3. Agent places trade with same risk management rules
4. Trade logged with "MANUAL" entry reason

Example:
```
Subject: Manual Entry Request
Body:
Ticker: TSLA
Direction: LONG
Desired Entry: $245
Reason: Broke above 200-day MA, good earnings setup
Sector: Auto/EV (check concentration first)
```

### Can You Override Filters?

**YES - Emergency Override Available**

Normal rules: Technical + Macro + Policy all say yes

**Emergency Override (use sparingly):**
```
Subject: OVERRIDE - Entry Request

Ticker: XYZ
Entry: $50
Reason: Unusual fundamental catalyst (merger, CEO change, etc)
Risk Acceptance: I understand this bypasses regime/policy filters

Note: Trades entered via OVERRIDE are tracked separately
and reviewed for improvement
```

**Rules for Override:**
- ✅ Can bypass regime filter (if conviction strong)
- ✅ CAN'T bypass daily loss limit or earnings blackout
- ✅ Can't exceed position sizing or concentration limits
- ✅ Must provide clear rationale
- ✅ Are tracked as "learning opportunities"

### Manual Position Adjustments

**Adding to Winner:**
- If position up 1R+ AND conviction high
- Can add up to 50% of original size
- Moves stop to break-even on new total

**Cutting Loss Early:**
- Can exit before stop if thesis proves wrong
- Logged with "thesis broken" reason
- Helps identify pattern misses

---

## 10. PAPER TRADING SPECIFICS

### Account Details

| Detail | Value |
|--------|-------|
| Account | DU4661622 |
| Type | Paper Trading (Interactive Brokers) |
| Starting Balance | ~$2,000,000 |
| Available Margin | ~$5,000,000 (2.5x) |
| **Our Max Usage** | $2,500,000 (50% of margin) |

### Dividend Handling

**Paper Account Behavior:**
- IB paper accounts DO receive dividends
- Dividends credited to cash balance
- Counts toward available buying power
- **Our Rule:** Use dividend cash for new entries or keep as buffer

### Account Reset Policy

**When Account Resets (if it does):**
1. IB may reset paper accounts periodically
2. **Our Response:** Use actual performance data from trade journal, not account value
3. **Scaling Decisions** based on trade P&L, not account reset balance

### IB-Specific Paper Account Rules

1. **Order Types:**
   - ✅ Market orders (instant execution)
   - ✅ Limit orders (patient entry)
   - ✅ Bracket orders (auto stop+target)
   - ✅ Trailing stops

2. **Restrictions None (paper account):**
   - ✅ Short selling allowed (any security)
   - ✅ Intraday trading allowed (no pattern day trader rule)
   - ✅ Margin available
   - ✅ Options allowed

3. **Fill Assumptions:**
   - Paper fills at mid-price (not realistic)
   - Real trading would have slippage (0.5-2% on entry)
   - When scaling to real account, expect worse fills

4. **Earnings Handling:**
   - Paper account gets dividend credits
   - Doesn't affect IB Gateway connection
   - But don't take earnings-week positions (our rule)

5. **Paper Account Conversion:**
   - When ready for real money, apply for live account
   - Transfer strategies directly (same position sizing rules)
   - First month on live: TIER 1 again (1% risk per trade)

---

## SUMMARY TABLE: All Trading Rules at a Glance

| Rule Category | TIER 1 | TIER 2 | TIER 3 |
|--------------|--------|--------|--------|
| **Position Sizing** | 1% risk/trade | 1.5% risk/trade | 2% risk/trade |
| **Entry Signal** | Tech + Macro + Policy | Tech + Macro + Policy | Tech + Macro + Policy |
| **Exit Strategy** | 50/25 + trailing stop | 50/25 + trailing stop | 50/25 + trailing stop |
| **Hold Time** | 3-20 days | 3-20 days | 3-20 days |
| **Daily Loss Limit** | -$1,350 | -$1,350 | -$1,350 |
| **Max Positions** | 5 | 8 | 12 |
| **Max Per Sector** | 25% | 25% | 25% |
| **Max Per Stock** | 5-8% | 5-8% | 5-8% |
| **Buying Power Usage** | 25% | 40% | 50% |
| **Covered Calls/mo** | 1-2 | 2-3 | 2-4 |
| **Cash Puts/mo** | 0-1 | 1-2 | 2-4 |

---

## Implementation Files

- This guide: `trading/TRADING_RULES.md`
- Trade journal: Weekly performance email
- Position tracking: `trading/logs/portfolio_snapshot_[DATE].json`
- Audit log: `trading/logs/audit.log`

**Every Friday:** Review actual trades against these rules. If pattern emerges, update rules.

**Every Month:** Analyze losses. If 2+ losses from same root cause, modify entry/exit rules to prevent.

---

**Status:** ✅ Rules established Feb 21, 2026. Ready for Monday market open.

**Review Schedule:**
- Weekly (Friday): Trade-by-trade analysis
- Monthly: Pattern analysis + rule updates
- Quarterly: Complete strategy review + tier reassessment
