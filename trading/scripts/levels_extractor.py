#!/usr/bin/env python3
import sys, json
from datetime import time
import pandas as pd
import numpy as np
import yfinance as yf

ET = pd.Timestamp.now(tz='America/New_York').tz

def compute_vwap(df):
    tp = (df['High'] + df['Low'] + df['Close']) / 3.0
    cum_vol = df['Volume'].cumsum().replace(0, np.nan)
    vwap = (tp * df['Volume']).cumsum() / cum_vol
    return vwap

def get_intraday(ticker, prepost=False):
    df = yf.download(ticker, period='1d', interval='5m', progress=False, prepost=prepost)
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        try:
            df = df.xs(ticker, axis=1, level=1)
        except Exception:
            first = df.columns.get_level_values(1)[0]
            df = df.xs(first, axis=1, level=1)
    df = df.tz_convert('America/New_York') if df.index.tz is not None else df.tz_localize('UTC').tz_convert('America/New_York')
    return df


def levels_for(ticker):
    # Regular hours for VWAP and morning/OR
    dfr = get_intraday(ticker, prepost=False)
    if dfr is None or dfr.empty:
        return None
    dfr['VWAP'] = compute_vwap(dfr)
    # Morning window 09:30-11:00 ET
    morning = dfr.between_time('09:30','11:00')
    orng = dfr.between_time('09:30','10:00')
    morn_h = float(morning['High'].max()) if not morning.empty else None
    morn_l = float(morning['Low'].min()) if not morning.empty else None
    or_h = float(orng['High'].max()) if not orng.empty else None
    or_l = float(orng['Low'].min()) if not orng.empty else None
    vwap = float(dfr['VWAP'].iloc[-1]) if not dfr.empty else None
    last = float(dfr['Close'].iloc[-1]) if not dfr.empty else None
    # Premarket using prepost True
    dfp = get_intraday(ticker, prepost=True)
    pre = dfp.between_time('04:00','09:29') if dfp is not None else None
    pre_h = float(pre['High'].max()) if pre is not None and not pre.empty else None
    pre_l = float(pre['Low'].min()) if pre is not None and not pre.empty else None
    return {
        'ticker': ticker,
        'last': last,
        'vwap': vwap,
        'morning_high': morn_h,
        'morning_low': morn_l,
        'or_high': or_h,
        'or_low': or_l,
        'premarket_high': pre_h,
        'premarket_low': pre_l,
    }

if __name__ == '__main__':
    tickers = sys.argv[1:]
    out = []
    for t in tickers:
        try:
            lv = levels_for(t)
            if lv:
                out.append(lv)
        except Exception as e:
            print(f"WARN {t}: {e}", file=sys.stderr)
    print(json.dumps(out))
