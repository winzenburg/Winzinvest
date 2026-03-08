# Trading Rules (Plain English)

Reference these in chat with `@docs` or in `.cursorrules`. They describe how the system is supposed to behave so the AI can match code to intent.

---

## What We Trade

- **Equity shorts:** Stocks we sell short when the screener says they are in downtrends (weak relative strength, structure, etc.). We cover with a stop loss above entry and a take-profit limit below entry.
- **Equity longs:** Stocks we buy when the long screener says they are in uptrends. We sell with a stop loss below entry and a take-profit limit above entry.
- **Options (premium selling):** Separate path (direct_premium_executor, auto_options_executor) with its own limits; not the focus of the equity NX pipeline.

---

## Entry Rules

- **Shorts:** Only add a new short if (1) the screener put the symbol in the short list, (2) we are not already short that symbol, (3) we have not hit max short positions, (4) we have not hit max new shorts per day, (5) all risk gates pass (daily loss, sector concentration, gap risk, regime, position size), and (6) we qualify the contract with IB before placing.
- **Longs:** Only add a new long if (1) the long screener put the symbol in the long list, (2) we are not already long that symbol, (3) long notional would not exceed the regime-based long allocation, and (4) sector concentration gate allows it (in dual-mode). Contract must be qualified before placing.
- **Position size:** Never hardcode. Always read from `risk.json` via `risk_config` (e.g. `get_position_size()` for equity shorts). One size per execution path unless the spec says otherwise.

---

## Exit Rules (Equity)

- **Stops and targets:** Every equity short must have a protective stop (e.g. 2% above entry) and a take-profit (e.g. 3% below entry) placed **after** the entry fill, using the **fill price**, not the signal price. Same idea for longs: stop below entry, target above entry.
- **Soft exits:** We may later add logic to exit early if relative strength or structure breaks down; that would live in a dedicated check (e.g. “exit if composite score drops below X”) and would not replace the hard stop/TP orders.

---

## Risk and Gates

- **Daily loss limit:** If today’s cumulative loss reaches the configured limit (e.g. 3% of equity), do not place any new orders for the rest of the day. Log and stop.
- **Sector concentration:** No single sector (e.g. Technology) may exceed the configured share of total notional (e.g. 30%). Check before each new order; skip if adding the order would breach the cap.
- **Gap risk:** Do not place new orders within a set number of minutes before market close (e.g. 60 minutes before 4 PM ET). Avoid trading into the close.
- **Regime:** Do not open new shorts when the market regime is “strong uptrend” (e.g. SPY above 200 SMA and VIX low). Regime is used for allocation (short/long mix) in dual-mode as well.
- **Position sizing gate:** No single order’s notional should exceed a fraction of account equity (e.g. 50% of buying power). Check before placing.
- **All five gates** (daily limit, sector, gap, regime, position size) must pass before placing an equity short. Use `execution_gates.check_all_gates()` so one place enforces them.

---

## Allocation (Dual-Mode)

- Regime (SPY vs 200 SMA + VIX) decides how much of the account can be in shorts vs longs: e.g. strong downtrend → mostly shorts, strong uptrend → mostly longs, mixed/choppy → balanced. Exact fractions come from `regime_detector.calculate_portfolio_allocation()`. Executors must not exceed these caps when adding new positions.

---

## Webhooks (TradingView or Other)

- Any HTTP endpoint that places orders must validate the payload (symbol, side, quantity, etc.) and must enforce the **same** risk limits and gates as the direct executors. Use `risk_config` and `execution_gates` (and sector_gates where relevant). Log every webhook request and its outcome to the same audit trail as direct executions (e.g. shared execution log with `source_script` or `source` set to the webhook name).

---

## Audit and Logging

- Every order path (direct or webhook) must write to the shared execution log with at least: symbol, type (SHORT/LONG), source_script/source, timestamp, status. Include prices and quantities where applicable. No silent failures: log errors and rejections with a clear reason.
