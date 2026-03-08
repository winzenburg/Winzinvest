# Project Structure for AI Context

Keeping strategy, execution, risk, and webhooks in **separate modules** helps Cursor reason about each piece without confusion. Use this map when generating or refactoring code.

---

## Directory Layout

```
trading/
├── docs/                    # Plain-English rules and structure (reference with @docs)
│   ├── TRADING_RULES.md     # Entry/exit, risk, allocation, webhooks
│   ├── PROJECT_STRUCTURE.md # This file
│   ├── TRADINGVIEW_AMS_NX_REFERENCE.md  # TradingView Engine + Screener logic, webhooks, Python alignment
│   ├── NX_SCREENER_TECHNICAL_SPEC.md    # NX metrics (Composite, RS, RVol, Structure, HTF)
│   └── NX_TIER5_FULL_METRICS_STEPS.md   # Step-by-step plan for full NX metrics (Tier 5 #12)
├── scripts/                 # All runnable Python (screeners, executors, helpers)
│   ├── types.py             # Shared type definitions (signals, orders, positions)
│   ├── risk_config.py       # Risk: read limits from risk.json
│   ├── execution_gates.py   # Risk: pre-order gates (daily, sector, gap, regime, size)
│   ├── sector_gates.py      # Risk: sector map and concentration checks
│   ├── regime_detector.py   # Strategy: market regime and allocation
│   ├── position_filter.py   # Risk/state: current short symbols (exclude list)
│   ├── nx_screener_*.py     # Strategy: screeners (short/long candidates)
│   ├── execute_*.py         # Execution: place orders, stop/TP, log
│   ├── sync_current_shorts.py
│   └── ...
├── risk.json                # Config: position size, max positions, sector cap, etc.
├── watchlist_*.json         # Outputs: screener results (inputs to executors)
└── logs/                    # Execution logs, daily loss, etc.
```

---

## Module Roles

| Layer        | Purpose | Key modules | Do not mix with |
|-------------|---------|-------------|------------------|
| **Strategy** | What to trade (signals, regime, screening logic) | `regime_detector`, `nx_screener_production`, `nx_screener_longs` | Order placement, IB connection |
| **Execution** | Placing and managing orders (IB, fill, stop/TP, log) | `execute_candidates`, `execute_dual_mode`, `execute_longs`, `direct_premium_executor`, `auto_options_executor` | Screening logic, threshold tuning |
| **Risk**     | Limits and gates (position size, daily cap, sector, gap, regime) | `risk_config`, `execution_gates`, `sector_gates`, `position_filter` | Strategy rules (e.g. NX thresholds) |
| **Webhook**  | HTTP handlers that receive external signals and place orders | (To be added; must call risk + execution helpers) | Inline strategy or hardcoded limits |

- **TradingView:** AMS Trade Engine (indicator) and AMS Pro Screener run in TradingView and send webhooks. See **docs/TRADINGVIEW_AMS_NX_REFERENCE.md** for payloads and alignment with Signal Validator and executors.

- **Strategy** produces or consumes **signals** (e.g. short_candidates, long_candidates). It should not call `placeOrder` or hold IB connections long-term.
- **Execution** loads signals from files or queues, runs **risk** checks, then places orders and writes to the execution log. It should not define NX thresholds or regime rules.
- **Risk** is read by both strategy (e.g. “how many slots left”) and execution (e.g. “may I place this order?”). It should not place orders or compute screener metrics.
- **Webhook** handlers should validate input, then call the same **risk** and **execution** helpers as direct scripts so behavior and limits are consistent.

---

## Types (`scripts/types.py`)

- **Signals:** `ShortCandidate`, `LongCandidate` (symbol, price, and optional score/momentum/reason).
- **Orders / executions:** `ExecutionRecord` (symbol, type, source_script, timestamp, status, and optional orderId, entry_price, quantity, etc.).
- **Positions / allocation:** `PositionSnapshot`, `Allocation` (for regime-based short/long fractions).

Use these types in function signatures and when reading/writing JSON so the AI generates consistent, explicit code. Reference `types.py` in chat with `@types` or “use types from scripts/types.py” in `.cursorrules`.
