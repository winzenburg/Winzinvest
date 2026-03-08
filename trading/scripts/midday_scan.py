#!/usr/bin/env python3
import json
import sys
from datetime import datetime, time
import pandas as pd
import numpy as np

try:
    import yfinance as yf
except Exception:
    print("ERR: Missing dependency yfinance. Please pip install yfinance")
    sys.exit(1)

ET = pd.Timestamp.now(tz='America/New_York').tz

def load_watchlist(path="trading/watchlist.json"):
    with open(path, 'r') as f:
        wl = json.load(f)
    # flatten
    tickers = []
    for v in wl.values():
        tickers.extend(v)
    # de-dup
    return sorted(list(dict.fromkeys(tickers)))


def compute_vwap(df):
    # typical price * volume cumulative / cumulative volume
    tp = (df['High'] + df['Low'] + df['Close']) / 3.0
    cum_vol = df['Volume'].cumsum().replace(0, np.nan)
    vwap = (tp * df['Volume']).cumsum() / cum_vol
    return vwap


def get_intraday(ticker):
    # 5m data for 1 day keeps today session
    df = yf.download(ticker, period='1d', interval='5m', progress=False, prepost=False)
    if df is None or df.empty:
        return None
    # Handle MultiIndex columns returned by yfinance
    if isinstance(df.columns, pd.MultiIndex):
        try:
            df = df.xs(ticker, axis=1, level=1)
        except Exception:
            # Fallback: take first level slice
            first = df.columns.get_level_values(1)[0]
            df = df.xs(first, axis=1, level=1)
    # Ensure ET timezone
    df = df.tz_convert('America/New_York') if df.index.tz is not None else df.tz_localize('UTC').tz_convert('America/New_York')
    df['VWAP'] = compute_vwap(df)
    # EMAs for momentum
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    # MACD fast/slow on 5m close
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    return df


def scan_ticker(t):
    df = get_intraday(t)
    if df is None or df.empty:
        return []
    # session window in ET
    idx = df.index
    # Morning window 09:30-11:00 ET
    morning = df.between_time('09:30', '11:00')
    if morning.empty:
        return []
    morning_high = morning['High'].max()
    morning_low = morning['Low'].min()

    now_row = df.iloc[-1]
    last_close = float(now_row['Close'])

    signals = []

    # Range breakout/breakdown after 11:00 ET
    post11 = df.between_time('11:00', '16:00')
    if not post11.empty:
        post11_high = post11['High'].max()
        post11_low = post11['Low'].min()
        # Check cross within last 3 bars to keep fresh
        recent = df.iloc[-3:]
        if (recent['High'] > morning_high).any():
            signals.append((t, f"Morn H {morning_high:.2f}", "Range Breakout", "Watch pullback/HL for entry"))
        if (recent['Low'] < morning_low).any():
            signals.append((t, f"Morn L {morning_low:.2f}", "Range Breakdown", "Watch LH/reject for entry"))

    # Support/resistance test: within 0.3% of morning H/L or VWAP
    def near(level, price, pct=0.003):
        return abs(price - level) / level <= pct

    if near(morning_high, last_close):
        signals.append((t, f"Morn H {morning_high:.2f}", "Retest R", "Look for breakout or rejection"))
    if near(morning_low, last_close):
        signals.append((t, f"Morn L {morning_low:.2f}", "Retest S", "Bounce vs fail setup"))
    if not np.isnan(now_row['VWAP']) and near(now_row['VWAP'], last_close, 0.002):
        signals.append((t, f"VWAP {now_row['VWAP']:.2f}", "VWAP Test", "Trend bias on hold vs reclaim"))

    # Unusual volume spike: last 5m volume > 2.0x median of day
    if len(df) >= 20:
        vol_med = float(df['Volume'].median())
        last_vol = float(now_row['Volume'])
        if vol_med > 0 and last_vol >= 2.0 * vol_med:
            signals.append((t, f"Vol x{last_vol/vol_med:.1f}", "Volume Spike", "Confirm direction, follow through"))

    # Midday reversal: morning trend strong then EMA20 break and MACD cross opposite
    open_row = df.between_time('09:30', '09:35').iloc[:1]
    if not open_row.empty:
        open_price = float(open_row['Open'].iloc[0])
        change_to_11 = (morning['Close'].iloc[-1] / open_price - 1.0) if open_price else 0.0
        strong_up = change_to_11 >= 0.015
        strong_down = change_to_11 <= -0.015
        recent = df.iloc[-3:]
        macd_cross_down = (recent['MACD'].iloc[-1] < recent['Signal'].iloc[-1]) and (recent['MACD'].iloc[-2] >= recent['Signal'].iloc[-2])
        macd_cross_up = (recent['MACD'].iloc[-1] > recent['Signal'].iloc[-1]) and (recent['MACD'].iloc[-2] <= recent['Signal'].iloc[-2])
        # EMA20 trend filter
        below_ema20 = last_close < float(now_row['EMA20'])
        above_ema20 = last_close > float(now_row['EMA20'])
        if strong_up and below_ema20 and macd_cross_down:
            signals.append((t, f"~{last_close:.2f}", "Midday Reversal Down", "Consider short/puts on LH or VWAP fail"))
        if strong_down and above_ema20 and macd_cross_up:
            signals.append((t, f"~{last_close:.2f}", "Midday Reversal Up", "Consider long/calls on HL or VWAP reclaim"))

    # Momentum shift: price crosses EMA20 with MACD confirmation (no strong morning trend required)
    recent = df.iloc[-3:]
    cross_up = (recent['Close'].iloc[-1] > recent['EMA20'].iloc[-1]) and (recent['Close'].iloc[-2] <= recent['EMA20'].iloc[-2]) and (recent['MACD'].iloc[-1] > recent['Signal'].iloc[-1])
    cross_down = (recent['Close'].iloc[-1] < recent['EMA20'].iloc[-1]) and (recent['Close'].iloc[-2] >= recent['EMA20'].iloc[-2]) and (recent['MACD'].iloc[-1] < recent['Signal'].iloc[-1])
    if cross_up:
        signals.append((t, f"EMA20 {now_row['EMA20']:.2f}", "Momentum ↑", "Potential continuation on dips"))
    if cross_down:
        signals.append((t, f"EMA20 {now_row['EMA20']:.2f}", "Momentum ↓", "Potential fade on pops"))

    # De-dupe by pattern type, keep priority order
    priority_order = {
        'Midday Reversal Down': 1,
        'Midday Reversal Up': 1,
        'Range Breakout': 2,
        'Range Breakdown': 2,
        'Volume Spike': 3,
        'Momentum ↑': 4,
        'Momentum ↓': 4,
        'Retest R': 5,
        'Retest S': 5,
        'VWAP Test': 6,
    }
    # Convert to dict with best priority per pattern
    # We'll emit multiple lines per ticker if distinct high-priority events exist
    signals_sorted = sorted(signals, key=lambda x: (priority_order.get(x[2], 9), x[0]))
    return signals_sorted


def main():
    tickers = load_watchlist()
    results = []
    for t in tickers:
        try:
            sigs = scan_ticker(t)
            results.extend(sigs)
        except Exception as e:
            print(f"WARN {t}: {e}", file=sys.stderr)
            continue
    # Global priority sort
    priority_order = {
        'Midday Reversal Down': 1,
        'Midday Reversal Up': 1,
        'Range Breakout': 2,
        'Range Breakdown': 2,
        'Volume Spike': 3,
        'Momentum ↑': 4,
        'Momentum ↓': 4,
        'Retest R': 5,
        'Retest S': 5,
        'VWAP Test': 6,
    }
    results_sorted = sorted(results, key=lambda x: (priority_order.get(x[2], 9), x[0]))
    # Format concise lines
    lines = []
    for t, level, pattern, action in results_sorted:
        lines.append(f"{t}: {level} | {pattern} | {action}")
    print("\n".join(lines))

if __name__ == '__main__':
    main()
