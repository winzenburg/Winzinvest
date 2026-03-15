# Outside RTH (Regular Trading Hours) Execution

Mission Control supports IBKR's **outside RTH** and **Outside RTH Take-Profit** so that orders can execute or fill in extended hours (pre-market and after-hours).

---

## What Is RTH vs Outside RTH?

- **RTH (Regular Trading Hours)**: 9:30 AM – 4:00 PM Eastern, Monday–Friday.
- **Outside RTH**: Pre-market (e.g. 4:00–9:30 AM ET) and after-hours (e.g. 4:00–8:00 PM ET), when the primary exchange is closed but IBKR allows trading for supported symbols.

---

## Configuration

In `trading/risk.json` the `execution` section controls RTH behavior:

```json
"execution": {
  "allow_outside_rth_entry": false,
  "outside_rth_take_profit": true,
  "outside_rth_stop": false
}
```

| Option | Default | Effect |
|--------|---------|--------|
| **allow_outside_rth_entry** | `false` | If `true`, entry orders use a limit order with `outsideRth=True` so they can fill in extended hours. If `false`, entry uses a market order (RTH only). |
| **outside_rth_take_profit** | `true` | If `true`, take-profit limit orders have `outsideRth=True` so they can fill in extended hours (IBKR “Outside RTH Take-Profit”). |
| **outside_rth_stop** | `false` | If `true`, stop and trailing-stop orders have `outsideRth=True` so they can trigger in extended hours. |

---

## Behavior

### Entry orders

- **allow_outside_rth_entry = false**  
  Entry is a **market order**. It only works during RTH. This is the default.

- **allow_outside_rth_entry = true**  
  Entry is a **limit order** at a small offset from the last price (e.g. 0.5% for BUY, 0.5% worse for SELL), with `outsideRth=True` and TIF GTC. It can fill in RTH or in extended hours.

IBKR does **not** allow market orders with `outsideRth` (error 2109), so when you allow outside-RTH entry we use a limit order.

### Take-profit orders (Outside RTH Take-Profit)

- With **outside_rth_take_profit = true** (default), every take-profit **limit** order is sent with `outsideRth=True`.
- So if price hits your target in pre-market or after-hours, the take-profit can fill instead of waiting for the next RTH open.

### Stop / trailing-stop orders

- With **outside_rth_stop = false** (default), stops and trailing stops are RTH-only.
- With **outside_rth_stop = true**, they are sent with `outsideRth=True` and can trigger in extended hours (if the exchange/IBKR supports it).

---

## Where It’s Applied

RTH settings are applied in:

- `execute_mean_reversion.py` – MR entries, trailing stops, take-profits  
- `execute_longs.py` – Long entries, trailing stops, take-profits  
- `execute_dual_mode.py` – Long and short entries, trailing stops, take-profits  
- `execute_pairs.py` – Pair entries, stops and take-profits for both legs  

All of these use the shared helpers in `order_rth.py`, which read `risk.json` and set `outsideRth` on the appropriate orders.

---

## Implementation Details

- **order_rth.py**
  - `apply_rth_to_order(order, kind, workspace)`  
    Sets `order.outsideRth` based on `execution` in `risk.json`.  
    `kind` is one of: `"entry"`, `"take_profit"`, `"stop"`.
  - `get_entry_order(action, quantity, price, workspace)`  
    Returns either a market order (RTH-only) or a limit order with `outsideRth=True` and a small price offset when `allow_outside_rth_entry` is true.

- **risk_config.py**
  - `get_allow_outside_rth_entry(workspace)`
  - `get_outside_rth_take_profit(workspace)`
  - `get_outside_rth_stop(workspace)`

---

## Recommendations

1. **Outside RTH Take-Profit**  
   Keep **outside_rth_take_profit: true** so take-profits can fill in extended hours when price gaps through your target.

2. **Entry outside RTH**  
   Use **allow_outside_rth_entry: true** only if you intentionally want entries to be possible in pre-market or after-hours. Expect wider spreads and more slippage; the 0.5% limit offset helps but does not remove risk.

3. **Stops outside RTH**  
   Use **outside_rth_stop: true** only if you want stops to be able to trigger in extended hours. Be aware that liquidity and gaps can make execution less predictable.

---

## References

- [IBKR: Trading Outside Regular Trading Hours (RTH)](https://www.interactivebrokers.com/campus/trading-lessons/trading-outside-regular-trading-hours-rth)
- [IBKR Glossary: Outside RTH](https://www.interactivebrokers.com/campus/glossary-terms/outside-rth)
- In ib_insync, set `order.outsideRth = True` on the Order object; market orders with `outsideRth` are rejected by IBKR (error 2109).
