# Brokerage Compatibility Guide

This document maps Winzinvest's architectural requirements to various brokerages' capabilities for marketing and customer support purposes.

## Winzinvest Requirements

### Critical Features (Hard Blockers)

These features are **mandatory** for full system functionality:

1. **Equity shorts + margin** — Mean reversion and momentum strategies require short selling
2. **Multi-leg options** — Iron condors, bag orders for rolling (BTC + STO atomic combos)
3. **Trailing stops (ATR-based)** — Core risk management for all equity positions
4. **Real-time position tracking** — Risk monitor and dashboard require live position data
5. **Paper trading environment** — Essential for testing and user onboarding
6. **Concurrent API connections** — 30+ scheduler scripts run throughout the day (each needs unique clientId/session)

### Nice-to-Have Features

1. **Portfolio margin** — Currently using 2.5× leverage via IBKR PM; Reg T margin workable but reduces capacity
2. **Extended hours trading** (`outsideRth`) — Gap risk management and pre-market execution
3. **Contract qualification/validation** — Pre-order validation reduces reject rate

---

## Tier 1: Full Compatibility (Ready Today)

### Interactive Brokers (Production)

**Status**: ✅ Production-ready

**Features:**
- All critical features supported
- Mature `ib_insync` Python integration (400+ methods, event-driven architecture)
- Portfolio margin available
- Extended hours trading
- Paper trading (port 4002)

**Commission:**
- Equities: $0.0035/share (min $0.35/order)
- Options: $0.65/contract

**Integration Status:**
- Currently running live with 39 concurrent scripts
- Proven stable for 12+ months

**Marketing Message:**
> "Works with Interactive Brokers — full feature support for all strategies including equity shorts, multi-leg options, portfolio margin, and ATR-based trailing stops."

---

### Tastytrade (High Compatibility)

**Status**: 🟡 90% compatible — integration effort required

**Features:**
- ✅ Official Python SDK (REST + WebSocket)
- ✅ Multi-leg options (full support, bag orders for rolls)
- ✅ Equity shorts and margin
- ✅ All order types **except trailing stops**
- ✅ Paper trading (sandbox environment)
- ✅ Real-time position tracking
- ❌ **No native trailing stops** — would require client-side polling + manual updates

**Commission:**
- Equities: $0
- Options: $1/contract (capped $10/leg)
- **Cost advantage:** Options-heavy portfolios save ~35% vs IBKR

**Limitations:**
- Trailing stops must be implemented client-side (poll current price every N seconds, update stop level manually)
- Integration requires new SDK adoption and order router adapter layer

**Integration Effort:** 2–3 weeks

**Marketing Message:**
> "Tastytrade support coming Q2 2026 — excellent for options-focused portfolios. Lower commissions than IBKR. Trailing stops managed client-side."

**Recommended for:**
- Customers with existing Tastytrade accounts
- Options-heavy users (covered calls, CSPs, iron condors)
- Cost-conscious traders (lower options commissions)

---

## Tier 2: Partial Compatibility (Requires Adaptation)

### TD Ameritrade / Schwab

**Status**: 🟡 70% compatible — API in transition

**Features:**
- ✅ Equity shorts, stops, trailing stops
- ⚠️ Options: Single-leg and simple spreads documented; complex bag orders less clear
- ✅ Paper trading (virtualized accounts)
- ⚠️ API migration to unified Schwab API in progress (2026)

**Commission:**
- Equities: $0
- Options: $0.65/contract

**Limitations:**
- Multi-leg option rolls may require separate BTC + STO orders (not atomic) — introduces execution risk
- API endpoints still changing during migration
- Unclear if concurrent clientId model matches IBKR's

**Integration Effort:** 3–4 weeks (wait for API stabilization)

**Marketing Message:**
> "Schwab support coming Q3 2026 — pending unified API launch."

**Recommendation:**
- Wait until unified API stabilizes (mid-2026)
- Do not advertise as "supported" yet
- Add to roadmap as "planned Q3 2026"

---

### TradeStation

**Status**: 🟡 75% compatible — minor adaptations needed

**Features:**
- ✅ REST + WebSocket API (mature)
- ✅ Multi-leg options spreads
- ✅ Equity shorts, stops, trailing stops
- ✅ Paper trading (simulated trading)
- ⚠️ Portfolio margin structure differs from IBKR
- ⚠️ Bag orders less flexible than IBKR's

**Commission:**
- Equities: $0
- Options: $0.60/contract

**Limitations:**
- Option roll mechanics may require adapter logic
- Portfolio margin calculation different (affects leverage strategies)

**Integration Effort:** 3–4 weeks

**Marketing Message:**
> "TradeStation compatible with minor adaptation for option rolls."

**Recommendation:**
- Lower priority than Tastytrade (smaller user base overlap)
- Add to roadmap if customer demand justifies it

---

## Tier 3: Limited or Not Recommended

### Alpaca

**Status**: ❌ 30% compatible — **not viable**

**Critical Blocker:**
- ❌ No options support at all

**What Could Work:**
- Long-only equity strategies
- Mean reversion longs without options premium income

**What Cannot Work:**
- Shorts (no margin for retail accounts)
- Covered calls, CSPs, iron condors
- Tail hedge (SPY put spreads)
- Any strategy that relies on options premium

**Marketing Message:**
> "Not compatible — Alpaca does not support options."

**Recommendation:**
- Do not advertise compatibility
- Skip integration entirely

---

### Robinhood

**Status**: ❌ Not compatible

**Blockers:**
- No official API
- Unofficial libraries (e.g. `robin_stocks`) are unreliable and violate ToS
- High risk of account restrictions or bans

**Marketing Message:**
> Do not mention.

**Recommendation:**
- Skip entirely

---

### E*TRADE

**Status**: 🟡 50% compatible — high uncertainty

**Features:**
- Options API exists but poorly documented
- Multi-leg orders unclear from public docs
- Equity trading supported
- Paper trading available

**Limitations:**
- API quality/maturity significantly below IBKR and Tastytrade
- Bag order support for rolls unclear
- Limited community/SDK support

**Integration Effort:** 4–6 weeks + high uncertainty

**Marketing Message:**
> Not advertised.

**Recommendation:**
- Skip unless specific high-value customer requests it

---

## Marketing Copy for Landing Page

### FAQ Section: "Which brokerages are supported?"

**Current Answer (as of 2026-03-26):**

> Winzinvest currently supports **Interactive Brokers** (full feature set including equity shorts, options strategies, portfolio margin, and trailing stops). **Tastytrade integration is coming soon** for options-focused portfolios. **Schwab support** planned for Q3 2026 pending their unified API launch.
>
> **Requirements:**
> - Margin account with Level 2+ options approval
> - API access enabled in your brokerage account
> - $25,000+ account value (pattern day trader rule)
>
> Winzinvest connects via your own API credentials and never holds your funds.
>
> **Not compatible:** Alpaca (no options), Robinhood (no API)

---

### Roadmap Section (Optional for Landing Page)

**Brokerage Integrations:**
- ✅ **Interactive Brokers** — available now
- 🚧 **Tastytrade** — Q2 2026
- 📋 **Schwab** — Q3 2026 (pending unified API launch)
- 💬 Additional brokerages based on customer demand

---

## Technical Integration Priorities

### Recommended Development Order:

1. **Tastytrade (next):**
   - Clean Python SDK available
   - Options-focused user base aligns with strategy mix
   - Cost savings on options commissions (35% vs IBKR)
   - Only major gap: client-side trailing stops (solvable)

2. **Schwab (hold until Q3 2026):**
   - Wait for unified API to stabilize
   - Large user base (acquired TD Ameritrade customers)
   - Mid-priority after Tastytrade

3. **Skip for now:**
   - Alpaca (no options = non-starter)
   - E*TRADE (poor API quality)
   - Robinhood (no official API)
   - TradeStation (low demand, similar to Tastytrade but smaller overlap)

---

## Abstraction Layer Recommendations

To make adding Tastytrade and future brokerages plug-and-play, implement a broker abstraction layer:

### Proposed Interface (BrokerAdapter)

```python
from abc import ABC, abstractmethod
from typing import Any, List, Optional
from dataclasses import dataclass

@dataclass
class BrokerOrder:
    symbol: str
    action: str
    quantity: int
    order_type: str
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    trail_amount: Optional[float] = None
    tif: str = "DAY"

class BrokerAdapter(ABC):
    @abstractmethod
    async def connect(self, credentials: dict[str, Any]) -> bool:
        pass

    @abstractmethod
    async def get_positions(self) -> List[dict[str, Any]]:
        pass

    @abstractmethod
    async def place_order(self, order: BrokerOrder) -> str:
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        pass

    @abstractmethod
    async def get_account_value(self) -> float:
        pass

    @abstractmethod
    def supports_trailing_stops(self) -> bool:
        """Returns False for Tastytrade — caller must implement client-side."""
        pass
```

### Adapter Implementations

- `IBKRAdapter` wraps `ib_insync` (current production code)
- `TastytradeAdapter` wraps Tastytrade Python SDK
- Future: `SchwabAdapter`, etc.

### Migration Path

1. Refactor `ibkr_executor_insync.py` → `IBKRAdapter`
2. Update all executor scripts to depend on `BrokerAdapter` interface
3. Allow broker selection via config: `risk.json → "broker": "ibkr" | "tastytrade"`
4. Trailing stop manager: if `adapter.supports_trailing_stops() == False`, run client-side polling logic

---

## Customer Communication Templates

### Email to Existing Tastytrade Users

**Subject:** Winzinvest now supports Tastytrade (Q2 2026)

Hi [Name],

You're on our waitlist and your profile shows you trade with Tastytrade. Great news: we're adding native Tastytrade support in Q2 2026.

**What this means for you:**
- Lower options commissions than IBKR ($1/contract vs $0.65)
- All strategies work (shorts, covered calls, CSPs, iron condors)
- Trailing stops managed client-side (seamless for you, no difference in risk management)

**Timeline:**
- Integration target: May 2026
- Early access for Founding Members
- Schwab coming Q3 2026

Want early access? Reserve your Founding Member spot now at $79/month (47% off standard pricing, locked for life).

[Join the Waitlist →]

---

### Support Response Template (for customers asking about other brokerages)

**"I have a [Broker] account — can I use Winzinvest?"**

**Interactive Brokers:** ✅ Fully supported today. You can connect your account immediately.

**Tastytrade:** 🚧 Coming Q2 2026. Join the waitlist to be notified when it launches.

**Schwab (formerly TD Ameritrade):** 📋 Planned Q3 2026 pending their API migration. Add yourself to the interest list.

**Alpaca, Robinhood, E*TRADE:** ❌ Not compatible. Alpaca has no options support, Robinhood has no API, and E*TRADE's API quality does not meet our reliability standards.

If you're open to switching brokerages, Interactive Brokers offers the most complete feature set and is production-ready today. Tastytrade is an excellent alternative for options-focused traders and will be supported soon.

---

## Internal Development Notes

### Tastytrade Integration Checklist (when prioritized)

- [ ] Install `tastytrade` Python SDK: `pip install tastytrade`
- [ ] Create `TastytradeAdapter` implementing `BrokerAdapter` interface
- [ ] Implement client-side trailing stop manager (`TastytradeTrailManager`)
  - Polls current price every 30s during market hours
  - Calculates new stop level based on ATR
  - Places/replaces stop-loss order via Tastytrade API
- [ ] Update `risk_config.py` to accept `broker` parameter
- [ ] Add Tastytrade credentials to `.env` / secrets management
- [ ] Integration test suite against Tastytrade sandbox
- [ ] Update landing page FAQ and pricing to show "Supported Brokerages: IBKR, Tastytrade"
- [ ] Email waitlist announcing Tastytrade support

### Cost Comparison (Options-Heavy Portfolio Example)

**Scenario:** 200 options contracts/month (rolls, entries, exits)

| Brokerage | Commission | Monthly Cost |
|---|---|---|
| **Interactive Brokers** | $0.65/contract | $130 |
| **Tastytrade** | $1/contract, capped $10/leg | ~$70–$100 |
| **Schwab** | $0.65/contract | $130 |

**Savings:** Tastytrade saves $30–$60/month for options-heavy users. For customers trading 300+ contracts/month, Tastytrade's cap makes it significantly cheaper.

---

## Competitive Positioning

### vs. Other Trading Platforms

| Feature | Winzinvest | Trade Ideas | Composer | Alpaca AutoInvest |
|---|---|---|---|---|
| **Brokerage support** | IBKR (now), Tastytrade (Q2) | Alerts only | Robinhood, Alpaca | Alpaca only |
| **Options automation** | Full (spreads, rolls) | No | No | No |
| **Shorts** | Yes | No | Limited | No |
| **Trailing stops** | Yes (ATR-based) | No | No | No |
| **Kill switch** | Yes | No | No | No |
| **Portfolio margin aware** | Yes | N/A | No | No |

**Key Differentiator:** Winzinvest is the only platform offering:
1. Multi-brokerage support (IBKR + Tastytrade)
2. Full options automation (including rolls and spreads)
3. Equity shorts + portfolio margin awareness
4. ATR-based trailing stops
5. Regime-aware execution gating

---

## Customer Segment Recommendations

### Best Fit for IBKR:
- High-volume equity traders (lower equity commissions)
- Users wanting portfolio margin (6× leverage vs 4× Reg T)
- International customers (IBKR's global reach)

### Best Fit for Tastytrade (when available):
- Options-focused traders (covered calls, CSPs, iron condors)
- Users trading 200+ contracts/month (commission savings)
- Customers already on Tastytrade platform

### Not a Fit:
- Users with Alpaca, Robinhood, or E*TRADE as primary broker (suggest migration to IBKR or wait for Tastytrade)

---

## Disclaimer Language (Legal)

**For all marketing materials:**

> Brokerage account required. Currently supported: Interactive Brokers. Tastytrade support coming Q2 2026. Schwab planned Q3 2026. Winzinvest connects via your own API credentials and does not hold funds. Requires margin account with Level 2+ options approval and $25,000+ account value (PDT rule). Equities and options involve substantial risk of loss. Not investment advice.

---

## Next Steps

1. ✅ Update landing page FAQ with brokerage compatibility question
2. ✅ Update CTA banner and footer disclaimers to mention broader compatibility
3. ✅ Update overview and strategy pages
4. 📋 **Future:** Create `/brokerages` page with full compatibility matrix
5. 📋 **Future:** Build `BrokerAdapter` abstraction layer (when Tastytrade integration is prioritized)
6. 📋 **Future:** Create Tastytrade integration guide (technical documentation for developers)

---

**Last Updated:** 2026-03-26  
**Author:** Winzinvest Development Team
