#!/usr/bin/env python3
import sys
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta

ET = pd.Timestamp.now(tz='America/New_York').tz

def compute_vwap(df):
    tp = (df['High'] + df['Low'] + df['Close']) / 3.0
    cum_vol = df['Volume'].cumsum().replace(0, np.nan)
    return (tp * df['Volume']).cumsum() / cum_vol


def fetch_intraday(ticker):
    df = yf.download(ticker, period='1d', interval='5m', progress=False, prepost=False)
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        try:
            df = df.xs(ticker, axis=1, level=1)
        except Exception:
            first = df.columns.get_level_values(1)[0]
            df = df.xs(first, axis=1, level=1)
    df = df.tz_convert('America/New_York') if df.index.tz is not None else df.tz_localize('UTC').tz_convert('America/New_York')
    df['VWAP'] = compute_vwap(df)
    return df


def summarize(tickers):
    out = []
    for t in tickers:
        try:
            df = fetch_intraday(t)
            if df is None or df.empty:
                continue
            morning = df.between_time('09:30','11:00')
            if morning.empty:
                continue
            mhi = float(morning['High'].max())
            mlo = float(morning['Low'].min())
            last = df.iloc[-1]
            price = float(last['Close'])
            vwap = float(last['VWAP']) if not np.isnan(last['VWAP']) else None
            vol_med = float(df['Volume'].median()) if len(df) >= 5 else 0.0
            last_vol = float(last['Volume'])
            vol_x = (last_vol/vol_med) if vol_med>0 else 0.0
            # recent news via yfinance if available
            news_items = []
            try:
                info = yf.Ticker(t)
                news = info.news or []
                cutoff = datetime.now().timestamp() - 36*3600
                for n in news[:5]:
                    if n.get('provider') and n.get('title') and n.get('published_at',0) >= cutoff:
                        news_items.append(n['title'][:120])
            except Exception:
                pass
            out.append({
                't': t,
                'price': price,
                'mhi': mhi,
                'mlo': mlo,
                'vwap': vwap,
                'vol_x': vol_x,
                'has_unusual_vol': vol_x>=2.0,
                'news': news_items[:2]
            })
        except Exception as e:
            print(f"WARN {t}: {e}", file=sys.stderr)
            continue
    return out

if __name__ == '__main__':
    tickers = sys.argv[1:]
    data = summarize(tickers)
    for d in data:
        price = d['price']
        mhi = d['mhi']
        mlo = d['mlo']
        vwap = d['vwap']
        vol_tag = f"Vol x{d['vol_x']:.1f}" if d['vol_x']>0 else "Vol n/a"
        news = (" | ".join(d['news'])) if d['news'] else ""
        vwap_str = f"{vwap:.2f}" if vwap is not None else "n/a"
        print(f"{d['t']}|{price:.2f}|MornH {mhi:.2f}|MornL {mlo:.2f}|VWAP {vwap_str}|{vol_tag}|{news}")
