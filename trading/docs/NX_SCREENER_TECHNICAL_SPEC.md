# Deep Technical Dive — Trading System Components

Reference spec for the NX screener architecture and math. This document is the source of truth for formulas and interpretation; implementation status is noted at the end.

---

## COMPONENT 1: Screener Architecture & NX Math

### Data Ingestion Pipeline

```python
# yfinance fetch (daily OHLCV)
data = yf.download(ticker, period='1y', interval='1d')
# Returns: Open, High, Low, Close, Volume, Adj Close

# Calculate technical series
sma_20 = data['Close'].rolling(20).mean()
sma_50 = data['Close'].rolling(50).mean()
sma_200 = data['Close'].rolling(200).mean()
bb_upper, bb_middle, bb_lower = bollinger_bands(data['Close'], 20, 2)
rsi = RSI(data['Close'], 14)
atr = ATR(data['High'], data['Low'], data['Close'], 14)
```

---

### Metric 1: COMPOSITE SCORE (Trend Strength)

**Formula:**

- `momentum_20d = (Close[today] - Close[20d_ago]) / Close[20d_ago]`
- `bb_position = (Close[today] - BB_lower) / (BB_upper - BB_lower)`  
  - Range: 0.0 (at lower band) to 1.0 (at upper band)
- `rsi_normalized = (RSI - 30) / 40`  
  - Clamp to [0, 1]

**Composite:**

```text
composite = (momentum_20d_norm * 0.4) + (bb_position * 0.3) + (rsi_normalized * 0.3)
composite = clamp(composite, 0.0, 1.0)
```

**Interpretation:**

| Range    | Interpretation                                      |
|----------|-----------------------------------------------------|
| 0.0–0.2  | Dead/choppy (no clear trend)                        |
| 0.2–0.5  | Weak trend (some momentum)                          |
| 0.5–0.8  | Strong trend (clear direction)                      |
| 0.8–1.0  | Extreme trend (potential reversal risk)            |

**Short entry threshold:** composite **< 0.35** (confirms downtrend without being too extreme).

---

### Code Implementation (Spec)

```python
def calculate_composite_score(df):
    # Momentum (20-day return %)
    momentum = (df['Close'].iloc[-1] - df['Close'].iloc[-20]) / df['Close'].iloc[-20]
    momentum_norm = min(max(momentum, -0.15), 0.15) / 0.15   # Normalize to [-1, 1]
    momentum_norm = (momentum_norm + 1) / 2                   # Shift to [0, 1]

    # Bollinger Band position
    bb_upper = df['Close'].rolling(20).mean() + 2 * df['Close'].rolling(20).std()
    bb_lower = df['Close'].rolling(20).mean() - 2 * df['Close'].rolling(20).std()
    bb_range = bb_upper.iloc[-1] - bb_lower.iloc[-1]
    bb_pos = (df['Close'].iloc[-1] - bb_lower.iloc[-1]) / bb_range if bb_range > 0 else 0.5
    bb_pos = min(max(bb_pos, 0), 1)

    # RSI normalization
    rsi = calculate_rsi(df['Close'], 14)
    rsi_norm = (rsi.iloc[-1] - 30) / 40
    rsi_norm = min(max(rsi_norm, 0), 1)

    # Weighted average
    composite = (momentum_norm * 0.4) + (bb_pos * 0.3) + (rsi_norm * 0.3)
    return composite
```

---

### Metric 2: RELATIVE STRENGTH (RS)

**Formula:**

- `stock_return_252d = (Close[today] - Close[252d_ago]) / Close[252d_ago]`
- `spy_return_252d = (SPY_Close[today] - SPY_Close[252d_ago]) / SPY_Close[252d_ago]`
- `spy_volatility = StdDev(SPY_daily_returns, 252d)`
- `rs_pct = (stock_return_252d - spy_return_252d) / spy_volatility`
- Normalized to [-1.0, 1.0]: `rs_pct = clamp(rs_pct / 0.5, -1.0, 1.0)`

**Interpretation:**

| Range        | Interpretation |
|-------------|----------------|
| < -0.5      | Stock significantly underperforming market (bearish) |
| -0.5 to 0.0 | Underperforming (still ok for shorts) |
| 0.0 to 0.5  | Outperforming market (bullish) |
| > 0.5       | Stock significantly outperforming (very bullish) |

**Short entry threshold:** rs_pct **< 0.50** (underperforming SPY).

**Why this works:** Captures relative momentum, not absolute. A stock down 10% can have positive RS if SPY is down 20%. Filters out "rising tide lifts all boats" scenarios.

**Code:**

```python
def calculate_rs(stock_data, spy_data):
    # 1-year returns
    stock_return = (stock_data['Close'].iloc[-1] - stock_data['Close'].iloc[-252]) / stock_data['Close'].iloc[-252]
    spy_return = (spy_data['Close'].iloc[-1] - spy_data['Close'].iloc[-252]) / spy_data['Close'].iloc[-252]

    # SPY volatility (252-day)
    spy_daily_returns = spy_data['Close'].pct_change()
    spy_vol = spy_daily_returns.std()

    # RS calculation
    rs_pct = (stock_return - spy_return) / spy_vol if spy_vol > 0 else 0

    # Normalize to [-1, 1]
    rs_pct = max(min(rs_pct / 0.5, 1.0), -1.0)

    return rs_pct
```

---

### Metric 3: RELATIVE VOLATILITY (RVol)

**Formula:**

- `stock_atr = ATR(stock_high, stock_low, stock_close, 14)`
- `spy_atr = ATR(spy_high, spy_low, spy_close, 14)`
- `rvol = stock_atr / spy_atr`  
  Typical range: 0.5 to 2.0+

**ATR (Average True Range):**

- `true_range = max(high - low, abs(high - close_prev), abs(low - close_prev))`
- `atr_14 = true_range.rolling(14).mean()`

**Interpretation:**

| Range    | Interpretation |
|----------|----------------|
| < 0.7    | Low volatility (limited swing room) |
| 0.7–1.0  | Normal volatility |
| 1.0–1.5  | Higher volatility (good for swing traders) |
| > 1.5    | Extreme volatility (assignment/execution risk) |

**Short entry threshold:** rvol **> 1.0** (needs swing room to profit).

**Why:** If a stock moves only $0.50/day and we short 100 shares, that’s $50 profit potential before commissions. Need RVol > 1.0 to justify risk.

**Code:**

```python
def calculate_true_range(high, low, close_prev):
    return max(
        high - low,
        abs(high - close_prev),
        abs(low - close_prev)
    )

def calculate_atr(df, period=14):
    df['TR'] = df.apply(
        lambda row: calculate_true_range(row['High'], row['Low'],
                                        df['Close'].shift(1)),
        axis=1
    )
    df['ATR'] = df['TR'].rolling(period).mean()
    return df['ATR']

def calculate_rvol(stock_data, spy_data):
    stock_atr = calculate_atr(stock_data)
    spy_atr = calculate_atr(spy_data)

    rvol = stock_atr.iloc[-1] / spy_atr.iloc[-1] if spy_atr.iloc[-1] > 0 else 1.0
    return rvol
```

---

### Metric 4: STRUCTURE QUALITY (Confluence)

**Components:**

1. **Bollinger Band squeeze**  
   Width = (BB_upper - BB_lower) / Close. Normalized to [0, 1] where 1 = expanded (volatility coming).

2. **SMA alignment**  
   Check 20 SMA < 50 SMA < 200 SMA (downtrend = 1.0). Check price below all 3 (downtrend = 1.0). Alignment_score = 1.0 if both true, else proportion.

3. **RSI divergence**  
   RSI &lt; 30 (oversold) = 0.5; RSI &lt; 40 (weak) = 0.3; RSI &lt; 50 (neutral) = 0.1. Higher values = stronger signal.

4. **Volume confirmation**  
   Volume today vs 20-day avg. If today &gt; 1.2× avg and price down = 1.0, else = 0.5.

**Formula:**

```text
structure = (bb_squeeze * 0.25) + (sma_alignment * 0.35) +
            (rsi_divergence * 0.25) + (volume_confirm * 0.15)
```

**Interpretation:**

| Range    | Interpretation |
|----------|----------------|
| 0.0–0.2  | Chaotic price action (avoid) |
| 0.2–0.5  | Normal structure (acceptable) |
| 0.5–0.8  | Clean structure (preferred) |
| 0.8–1.0  | Perfect confluence (best setups) |

**Short entry threshold:** structure **< 0.35** (confirms clean downtrend, not random noise).

**Code:**

```python
def calculate_structure_quality(df):
    # 1. BB squeeze
    bb_mean = df['Close'].rolling(20).mean()
    bb_std = df['Close'].rolling(20).std()
    bb_width = (2 * bb_std) / bb_mean
    bb_width_norm = min(bb_width.iloc[-1] / 0.1, 1.0)

    # 2. SMA alignment (for downtrend)
    sma20 = df['Close'].rolling(20).mean()
    sma50 = df['Close'].rolling(50).mean()
    sma200 = df['Close'].rolling(200).mean()

    if (sma20.iloc[-1] < sma50.iloc[-1] < sma200.iloc[-1] and
            df['Close'].iloc[-1] < sma20.iloc[-1]):
        sma_alignment = 1.0
    elif sma20.iloc[-1] < sma50.iloc[-1]:
        sma_alignment = 0.6
    else:
        sma_alignment = 0.0

    # 3. RSI divergence
    rsi = calculate_rsi(df['Close'], 14)
    if rsi.iloc[-1] < 30:
        rsi_div = 0.8
    elif rsi.iloc[-1] < 40:
        rsi_div = 0.6
    else:
        rsi_div = 0.2

    # 4. Volume confirmation
    vol_avg = df['Volume'].rolling(20).mean()
    if df['Volume'].iloc[-1] > 1.2 * vol_avg.iloc[-1] and df['Close'].iloc[-1] < df['Close'].iloc[-2]:
        vol_confirm = 1.0
    else:
        vol_confirm = 0.5

    structure = (bb_width_norm * 0.25) + (sma_alignment * 0.35) + \
                (rsi_div * 0.25) + (vol_confirm * 0.15)

    return structure
```

---

### Metric 5: HTF BIAS (Higher Timeframe Confirmation)

**Logic:**

- For each symbol, fetch 4-hour OHLC (last 252 bars ≈ 42 days).
- `sma_200_4h` = 200-period SMA on 4H chart.
- `current_price_4h` = Close[today] on 4H chart.

- If `current_price_4h > sma_200_4h` → htf_bias = 1.0 (uptrend = bullish).
- Elif `current_price_4h < sma_200_4h` → htf_bias = 0.0 (downtrend = bearish).
- Else: distance = abs(price - sma) / sma; if distance &lt; 0.02 (within 2%) → htf_bias = 0.5 (neutral), else linear interpolation.

**Interpretation:**

| Range    | Interpretation |
|----------|----------------|
| 0.0–0.2  | Strong downtrend on 4H (bearish, good for shorts) |
| 0.2–0.5  | Mixed bias |
| 0.5–0.8  | Mixed bias |
| 0.8–1.0  | Strong uptrend on 4H (bullish, avoid shorts) |

**Short entry threshold:** htf_bias **< 0.50** (4-hour downtrend or neutral).

**Why:** Prevents shorting stocks in multi-day uptrends. A stock can have a nice 1-day setup but be in a 4-day uptrend — HTF filter catches this.

**Code:**

```python
def calculate_htf_bias(ticker):
    df_4h = yf.download(ticker, period='250d', interval='4h')

    sma_200_4h = df_4h['Close'].rolling(200).mean()

    current_price = df_4h['Close'].iloc[-1]
    sma_val = sma_200_4h.iloc[-1]

    if current_price > sma_val:
        htf_bias = 1.0   # Uptrend
    elif current_price < sma_val:
        htf_bias = 0.0   # Downtrend
    else:
        dist_pct = abs(current_price - sma_val) / sma_val
        if dist_pct < 0.02:
            htf_bias = 0.5   # Neutral
        else:
            htf_bias = 0.3 if current_price < sma_val else 0.7

    return htf_bias
```

---

### Complete Screening Logic (Spec)

```python
def screen_for_shorts(ticker, mode='production'):
    try:
        stock_data = yf.download(ticker, period='1y')
        spy_data = yf.download('SPY', period='1y')

        composite = calculate_composite_score(stock_data)
        rs_pct = calculate_rs(stock_data, spy_data)
        rvol = calculate_rvol(stock_data, spy_data)
        structure = calculate_structure_quality(stock_data)
        htf_bias = calculate_htf_bias(ticker)

        thresholds = {
            'composite_min': 0.35,
            'rs_max': 0.50,
            'rvol_min': 1.00,
            'structure_min': 0.35,
            'htf_bias_max': 0.50
        }

        passes = (
            composite < thresholds['composite_min'] and
            rs_pct < thresholds['rs_max'] and
            rvol > thresholds['rvol_min'] and
            structure < thresholds['structure_min'] and
            htf_bias < thresholds['htf_bias_max']
        )

        if passes:
            return {
                'symbol': ticker,
                'composite': composite,
                'rs': rs_pct,
                'rvol': rvol,
                'structure': structure,
                'htf_bias': htf_bias,
                'price': stock_data['Close'].iloc[-1],
                'reason': f"Composite={composite:.2f}, RS={rs_pct:.3f}, Structure={structure:.2f}"
            }
        return None
    except Exception as e:
        logging.error(f"Error screening {ticker}: {e}")
        return None

# Run on full universe, save to watchlist_multimode.json
# results = [screen_for_shorts(t) for t in full_market_list]
# json.dump({'generated_at': ..., 'short_candidates': results, 'total': len(results)}, f)
```

---

## COMPONENT 2: ib_insync Integration

### Connection & Authentication

```python
from ib_insync import IB, Stock, Option, MarketOrder

ib = IB()
ib.connect('127.0.0.1', 4002, clientId=1)
ib.sleep(2)  # Wait for market data sync

print(ib.managedAccounts())  # e.g. ['DU4661622'] (paper)
```

**Connection flow:**

1. `ib.connect()` → TCP to IB Gateway (port 4002).
2. Authenticates with `clientId` (avoids conflicts).
3. Downloads account, positions, open orders.
4. Subscribes to market data for positions.
5. Waits for “Synchronization complete”.

**clientId separation:**

| clientId | Use |
|----------|-----|
| 1 | Production executor (equity shorts) |
| 2 | Premium call shorts |
| 3 | Additional equity shorts |
| 4 | EM shorts |
| 5–12 | Testing/verification |

Each clientId has its own order and fill queue to avoid race conditions.

---

### Contract Creation

**Stock orders:**

```python
from ib_insync import Stock, MarketOrder

contract = Stock(symbol='AAPL', exchange='SMART', currency='USD')
order = MarketOrder(action='SELL', totalQuantity=100)  # SELL = short
trade = ib.placeOrder(contract, order)
```

**Option orders:**

```python
from ib_insync import Option, MarketOrder

contract = Option(
    symbol='AAPL',
    lastTradeDateOrContractMonth='20260420',  # YYYYMMDD
    strike=267.0,
    right='C',  # C=call, P=put
    exchange='SMART',
    currency='USD'
)
order = MarketOrder(action='SELL', totalQuantity=1)
trade = ib.placeOrder(contract, order)
```

**Contract validation (`qualifyContracts`):**

```python
qualified_contracts = ib.qualifyContracts(contract)
if qualified_contracts:
    contract = qualified_contracts[0]  # correct conId, multiplier, etc.
else:
    # Contract not found — e.g. expiration "20260420" vs listed "20260424"
    pass
```

---

### Order Lifecycle & Status Tracking

| Status | Meaning |
|--------|--------|
| **PendingSubmit** | Created locally, not yet sent to IBKR |
| **PreSubmitted** | Sent to Gateway, waiting for validation (≈100–500 ms) |
| **Submitted** | Accepted by IBKR, sent to exchange, waiting for fill/rejection |
| **Filled** / **PartiallyFilled** | Executed; cash and positions updated |
| **Cancelled** | Rejected (e.g. contract doesn’t exist) or manually cancelled |

---

### Tracking Status in Real-Time

```python
trade = ib.placeOrder(contract, order)
ib.sleep(1)

print(trade.orderStatus.status)
print(trade.orderStatus.filled, trade.orderStatus.avgFillPrice, trade.orderStatus.remaining)

def onOrderStatus(trade):
    print(f"{trade.contract.symbol}: {trade.orderStatus.status} "
          f"({trade.orderStatus.filled}/{trade.order.totalQuantity})")

ib.orderStatusEvent += onOrderStatus

while not trade.isDone():
    ib.sleep(0.1)

print(f"Final: {trade.orderStatus.status} @ {trade.orderStatus.avgFillPrice}")
```

---

### Portfolio & Position Tracking

```python
portfolio = ib.portfolio()

for item in portfolio:
    print(f"{item.contract.symbol}:")
    print(f"  Position: {item.position} shares")
    print(f"  Entry Price: ${item.averageCost}")
    print(f"  Current Price: ${item.marketPrice}")
    print(f"  Market Value: ${item.marketValue}")
    print(f"  Unrealized P&L: ${item.unrealizedPNL}")
# e.g. AAPL: Position: -100 (short), Entry $255.34, Unrealized P&L: -$57
```

---

### Account Summary

```python
account_values = ib.accountValues('DU4661622')
for av in account_values:
    if av.tag in ['NetLiquidation', 'MaintMarginReq', 'BuyingPower']:
        print(f"{av.tag}: {av.value} {av.currency}")
# NetLiquidation: $98,467.13 USD
# BuyingPower: $196,719.95 USD (2:1 leverage)
```

---

### Error Handling & Execution Failures

```python
def place_order_with_retry(contract, order, max_retries=3):
    for attempt in range(max_retries):
        try:
            trade = ib.placeOrder(contract, order)
            timeout, start = 10, time.time()

            while trade.orderStatus.status in ['PendingSubmit', 'PreSubmitted']:
                if time.time() - start > timeout:
                    raise TimeoutError(f"Order {trade.order.orderId} stuck")
                ib.sleep(0.5)

            if trade.orderStatus.status == 'Cancelled':
                error_msg = trade.log[-1].message if trade.log else "Unknown"
                if "No security definition" in error_msg:
                    logging.error("Contract doesn't exist"); return None
                elif "Buying Power" in error_msg:
                    logging.error("Insufficient buying power"); return None
                else:
                    logging.warning(f"Cancelled: {error_msg}, retry {attempt+1}/{max_retries}")
                    ib.sleep(2); continue

            logging.info(f"✓ Order {trade.order.orderId}: {contract.symbol} {trade.orderStatus.status}")
            return trade
        except Exception as e:
            logging.error(f"Attempt {attempt+1}: {e}")
            ib.sleep(2)
    return None
```

---

## COMPONENT 3: Risk Gates & Circuit Breaker

### Gate 1: Daily Trade Limit

```python
def check_daily_trade_limit(max_trades_per_day=10):
    today = datetime.now().date()
    trades_today = len([t for t in ib.trades()
                        if t.log[0].time.date() == today
                        and t.orderStatus.status == 'Filled'])
    if trades_today >= max_trades_per_day:
        logging.warning(f"[CIRCUIT BREAKER] Daily limit: {trades_today}/{max_trades_per_day}")
        return False
    return True
```

### Gate 2: Sector Concentration

```python
def check_sector_concentration(max_concentration=0.30):
    sector_map = {'AAPL': 'Technology', 'MSFT': 'Technology', 'JPM': 'Financials', ...}
    sector_exposure = {}
    total_short_notional = 0
    for item in ib.portfolio():
        if item.position < 0:
            sector = sector_map.get(item.contract.symbol, 'Unknown')
            notional = abs(item.position * item.marketPrice)
            sector_exposure[sector] = sector_exposure.get(sector, 0) + notional
            total_short_notional += notional
    for sector, exposure in sector_exposure.items():
        concentration = exposure / total_short_notional if total_short_notional > 0 else 0
        if concentration > max_concentration:
            logging.warning(f"[CIRCUIT BREAKER] {sector} = {concentration:.1%} (max {max_concentration:.1%})")
            return False
    return True
```

### Gate 3: Gap Risk (No Trades Before Close)

```python
def check_gap_risk_window(minutes_before_close=60):
    market_close = datetime.now().replace(hour=16, minute=0, second=0)  # 4 PM ET
    mins_to_close = (market_close - datetime.now()).total_seconds() / 60
    if mins_to_close < minutes_before_close:
        logging.warning(f"[CIRCUIT BREAKER] Too close to close: {mins_to_close:.0f} min")
        return False
    return True
```

### Gate 4: Regime Check

```python
def check_regime_alignment(signal_type='SHORT'):
    spy_data = ib.reqHistoricalData(Contract(symbol='SPY', secType='STK', exchange='SMART', currency='USD'),
                                    endDateTime='', durationStr='1 Y', barSizeSetting='1 day', ...)
    sma_200 = spy_data[-200:].mean()
    current_price = spy_data[-1]
    is_uptrend = current_price > sma_200
    is_downtrend = current_price < sma_200
    if signal_type == 'SHORT' and is_uptrend:
        logging.warning("[CIRCUIT BREAKER] Shorting in uptrend (SPY > SMA200)"); return False
    if signal_type == 'LONG' and is_downtrend:
        logging.warning("[CIRCUIT BREAKER] Long in downtrend (SPY < SMA200)"); return False
    return True
```

### Gate 5: Position Size Validation

```python
def check_position_sizing(contract, order_quantity):
    ticker_data = ib.reqMktData(contract, '', False)
    notional = order_quantity * ticker_data.last
    buying_power = float([av for av in ib.accountValues('DU4661622') if av.tag == 'BuyingPower'][0].value)
    if notional > buying_power * 0.5:
        logging.warning(f"[CIRCUIT BREAKER] Position too large: ${notional:,.0f} vs ${buying_power:,.0f}")
        return False
    return True
```

### Complete Gate Check Before Execution

```python
def execute_with_all_gates(contract, order):
    gates = [
        ('Daily Limit', check_daily_trade_limit()),
        ('Sector Concentration', check_sector_concentration()),
        ('Gap Risk', check_gap_risk_window()),
        ('Regime', check_regime_alignment('SHORT')),
        ('Position Size', check_position_sizing(contract, order.totalQuantity))
    ]
    failed = [name for name, passed in gates if not passed]
    if failed:
        logging.error(f"[EXECUTION BLOCKED] Failed: {', '.join(failed)}")
        return None
    logging.info("✓ All gates passed")
    return place_order_with_retry(contract, order)
```

---

## COMPONENT 4: Stop Loss & Take Profit Automation

### Manual Order Placement (Legacy)

- Place short, then place separate StopOrder(BUY) and LimitOrder(BUY) for cover. Problems: two extra orders; if TP fills first, stop is still active; partial fills; manual management.

### Modern Approach: Bracket Orders

```python
from ib_insync import BracketOrder, Stock, MarketOrder, StopOrder, LimitOrder

parent_order = MarketOrder('SELL', 100)
stop_order = StopOrder('BUY', 100, 260.00)   # 2% above (cover on rise)
tp_order = LimitOrder('BUY', 100, 247.50)    # 3% below (cover on drop)
bracket_orders = BracketOrder(parent_order, stop_order, tp_order)
# IB: on parent fill, activates children; if one fills, cancels the other
```

### Current Implementation: Place Short + Stops After Fill

```python
def place_short_with_stops(contract, quantity=100):
    ticker_data = ib.reqMktData(contract, '', False)
    ib.sleep(1)
    current_price = ticker_data.last

    short_trade = ib.placeOrder(contract, MarketOrder('SELL', quantity))
    while not short_trade.isDone():
        ib.sleep(0.5)

    if short_trade.orderStatus.status != 'Filled':
        return None

    entry_price = short_trade.orderStatus.avgFillPrice
    stop_price = entry_price + (entry_price * 0.02)   # 2% above (BUY to cover)
    tp_price = entry_price - (entry_price * 0.03)      # 3% below

    ib.placeOrder(contract, StopOrder('BUY', quantity, stop_price))
    ib.placeOrder(contract, LimitOrder('BUY', quantity, tp_price))

    return {'symbol': contract.symbol, 'entry_price': entry_price, 'stop_price': stop_price, 'tp_price': tp_price, ...}
```

---

## COMPONENT 5: Account Reconciliation & Daily Reporting

### Portfolio Fetch & Snapshot

```python
def save_portfolio_snapshot():
    portfolio_data = {
        'timestamp': datetime.now().isoformat(),
        'account': 'DU4661622',
        'positions': [],
        'summary': {}
    }
    for item in ib.portfolio():
        portfolio_data['positions'].append({
            'symbol': item.contract.symbol,
            'type': item.contract.secType,
            'position': item.position,
            'entry_price': item.averageCost,
            'current_price': item.marketPrice,
            'market_value': item.marketValue,
            'unrealized_pnl': item.unrealizedPNL,
            'pnl_pct': (item.unrealizedPNL / abs(item.marketValue) * 100) if item.marketValue != 0 else 0
        })
    total_short = sum(p['market_value'] for p in portfolio_data['positions'] if p['position'] < 0)
    total_long = sum(p['market_value'] for p in portfolio_data['positions'] if p['position'] > 0)
    total_pnl = sum(p['unrealized_pnl'] for p in portfolio_data['positions'])
    portfolio_data['summary'] = {
        'total_short_value': total_short,
        'total_long_value': total_long,
        'net_notional': total_short + total_long,
        'total_unrealized_pnl': total_pnl,
        'pnl_pct': (total_pnl / (abs(total_short) + abs(total_long)) * 100) if (total_short + total_long) != 0 else 0,
        'position_count': len([p for p in portfolio_data['positions'] if p['position'] != 0])
    }
    with open('trading/portfolio.json', 'w') as f:
        json.dump(portfolio_data, f, indent=2, default=str)
```

---

### Daily P&L Report

```python
def generate_daily_report():
    """Generate EOD performance summary"""

    with open('trading/portfolio.json') as f:
        current = json.load(f)

    try:
        with open('trading/portfolio_previous.json') as f:
            previous = json.load(f)
    except FileNotFoundError:
        previous = None

    report = {
        'date': datetime.now().date().isoformat(),
        'positions': current['positions'],
        'daily_change': {}
    }

    if previous:
        previous_total_pnl = previous['summary']['total_unrealized_pnl']
        current_total_pnl = current['summary']['total_unrealized_pnl']
        daily_pnl_change = current_total_pnl - previous_total_pnl

        report['daily_change'] = {
            'previous_pnl': previous_total_pnl,
            'current_pnl': current_total_pnl,
            'change': daily_pnl_change,
            'change_pct': (daily_pnl_change / abs(previous_total_pnl) * 100)
                         if previous_total_pnl != 0 else 0
        }

    report['summary'] = current['summary']

    Path('trading/daily_reports').mkdir(exist_ok=True)
    with open(f"trading/daily_reports/report_{datetime.now().date().isoformat()}.json", 'w') as f:
        json.dump(report, f, indent=2, default=str)

    return report
```

---

## COMPONENT 6: Complete Execution Flow

### Start of trading day (9:30 AM ET / 7:30 AM MT)

1. **Pre-market**
   - Connect to IB Gateway.
   - Fetch latest screener signals from JSON.
   - Load current portfolio.
   - Verify all risk gates pass.

2. **For each signal**
   - Create contract (Stock/Option).
   - Validate contract exists (`qualifyContracts`).
   - Run all risk gates:
     - Daily limit check
     - Sector concentration
     - Gap risk window
     - Regime alignment
     - Position sizing
   - **If all gates pass:**
     - Place short order (market).
     - Wait for fill (~1–2 s).
     - Calculate stop/TP levels.
     - Place stop order (2% above entry).
     - Place TP order (3% below entry).
     - Log trade record.
   - **If any gate fails:** Skip signal, log reason.

3. **Throughout day**
   - Monitor fills on all orders.
   - Track P&L in real time.
   - Alert if any circuit breaker triggered.
   - Handle fills (stop/TP auto-execute).

4. **Market close (4:00 PM ET / 2:00 PM MT)**
   - Cancel any unfilled stop/TP orders.
   - Generate end-of-day portfolio snapshot.
   - Calculate daily P&L (`generate_daily_report`).
   - Commit results (e.g. to GitHub).
   - Disconnect from IB Gateway.

---

## Implementation Status (vs. `nx_screener_production.py`)

### NX metrics (Component 1)

| Spec element | Current code |
|--------------|--------------|
| Data: yfinance 1y daily | ✅ `fetch_symbol_data(..., period="1y")` |
| **Metric 1: Composite score** | ❌ Not computed (no BB, no RSI in metrics) |
| **Metric 2: RS (252d)** | ⚠️ Partial: `rs_pct` = 20d (sym_20d - spy_20d), not 252d return / SPY vol |
| **Metric 3: RVol (ATR 14)** | ⚠️ Partial: `rvol` = 20d log-return std ratio, not ATR ratio |
| **Metric 4: Structure quality** | ⚠️ Partial: `hl_ratio` (10d high-low position) only; no BB squeeze, SMA alignment, RSI div, volume confirm |
| **Metric 5: HTF bias (4H)** | ❌ Not computed (no 4H data fetch) |
| Short thresholds (all five) | ❌ Short mode uses only price_vs_50ma, price_vs_100ma, rs_pct (no composite, structure, htf_bias) |

**Current `calculate_nx_metrics()` returns:** `recent_return`, `rs_pct`, `rvol`, `hl_ratio`, `price_vs_50ma`, `price_vs_100ma`, `ma50`, `ma100`.

**To align with spec:** Implement full Composite (Metric 1), 252d RS with SPY vol (Metric 2), ATR-based RVol (Metric 3), Structure Quality (Metric 4), and optional HTF bias (Metric 5); add configurable thresholds to MODE_CONFIG and apply all five in short_opportunities (and/or a unified `screen_for_shorts`-style path).

### ib_insync (Component 2)

| Spec element | Current code |
|--------------|--------------|
| Connect host/port/clientId | ✅ `execute_candidates.py`: 127.0.0.1, 4002, clientId=101; `direct_premium_executor` similar |
| Stock contract + MarketOrder | ✅ `execute_candidates`: `Stock(symbol, 'SMART', 'USD')`, `MarketOrder(action, qty)` |
| Option contract + qualify | ✅ `direct_premium_executor`: listed expirations, `qualifyContracts` before place |
| Order status / rejection detail | ✅ Execution log includes status and rejection_detail |
| clientId separation (1–12) | ⚠️ 101/102/103 in use; align with 1–12 if desired for doc consistency |
| Order status polling / callback / isDone() | ❌ Not in execute_candidates (no wait loop or orderStatusEvent) |
| Portfolio / accountValues | ❌ Not used in executors for pre-trade checks; optional in scripts |
| place_order_with_retry | ❌ direct_premium_executor has no retry; execute_candidates no retry |

### Risk Gates (Component 3)

| Spec element | Current code |
|--------------|--------------|
| Daily trade limit | ⚠️ risk.json has max_new_shorts_per_day (null); not enforced in execute_candidates |
| Sector concentration | ❌ execute_candidates has no sector check; auto_options_executor has sector_concentration_manager (optional) |
| Gap risk (no trades before close) | ❌ Not in execute_candidates; auto_options has gap_risk_manager (optional) |
| Regime check (SPY vs 200 SMA) | ❌ Not in execute_candidates; auto_options has RegimeDetector (optional) |
| Position size vs buying power | ❌ Not in execute_candidates |
| execute_with_all_gates | ❌ No single “all gates” wrapper in repo |

### Stop Loss & Take Profit (Component 4)

| Spec element | Current code |
|--------------|--------------|
| Stop 2% above / TP 3% below (short) | ⚠️ execute_candidates computes stop/TP but formula was inverted (see TRADING_SETUP_HARDENING_AND_OPTIMIZATION.md); EXEC_PARAMS use 0.50/1.00 not 0.02/0.03 |
| BracketOrder (parent + stop + TP) | ❌ Not used; executor places market order only, no stop/TP orders |
| place_short_with_stops | ❌ Not in repo; would need to add or run separately |

### Account Reconciliation (Component 5)

| Spec element | Current code |
|--------------|--------------|
| save_portfolio_snapshot() | ❌ No portfolio.json writer in repo; logs/executions.json track executions only |
| generate_daily_report() | ❌ No daily report; no portfolio_previous.json or daily_reports/ in repo |

### Complete Execution Flow (Component 6)

| Spec element | Current code |
|--------------|--------------|
| Pre-market: connect, load signals, verify gates | ⚠️ execute_candidates connects and loads candidates; no single “all gates” check |
| Per-signal: qualify → gates → place → wait fill → stop/TP → log | ⚠️ Place only; no stop/TP orders, no gate wrapper |
| Throughout day: monitor fills, P&L, alerts | ❌ No real-time monitor or alerting in repo |
| EOD: cancel unfilled, snapshot, daily report, commit, disconnect | ❌ No EOD script; no portfolio snapshot or daily report writer |
